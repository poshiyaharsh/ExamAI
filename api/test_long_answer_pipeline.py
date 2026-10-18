import json
from unittest.mock import MagicMock, patch
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from api.models import AdminInstitution, Exam, PaperGenerationJob, Question
from api.utils.evaluation_config import (
    OLLAMA_BASE_URL,
    OLLAMA_TIMEOUT,
    canonicalize_model_tag,
)
from api.utils.exam_attempt_helper import sanitize_questions_for_attempt
from api.utils.extract_text import chunk_syllabus_by_topics, get_relevant_syllabus_chunk
from api.utils.ollama_client import call_ollama, parse_json_safely
from api.utils.prompts import (
    build_long_answer_step_a_prompt,
    build_long_answer_step_b_prompt,
    get_question_type_schema,
)
from api.utils.validate_paper import (
    canonicalize_type,
    compute_question_counts,
    repair_rubric_marks,
    validate_and_fix_paper,
    verify_grounding_evidence,
)
from api.generate_paper import deduplicate_questions

User = get_user_model()


class LongAnswerPipelineUnitTests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_user(
            username="admin@inst.edu",
            email="admin@inst.edu",
            password="AdminPassword123!",
        )
        self.institution = AdminInstitution.objects.create(
            admin=self.admin_user,
            institution_name="CyberSec University",
            institution_code="INST-2026-001",
            status=AdminInstitution.STATUS_ACTIVE,
        )
        self.faculty_user = User.objects.create_user(
            username="faculty_lead",
            email="faculty@cyber.local",
            password="FacultyPassword123!",
        )
        self.student_user = User.objects.create_user(
            username="student_lead",
            email="student@cyber.local",
            password="StudentPassword123!",
        )
        self.client = APIClient()

    # --- 1. JSON Repair & Tolerant Parsing ---
    def test_json_repair_unterminated_string(self):
        """Tests that unterminated JSON strings are safely repaired without eval."""
        raw = '{"model_answer": "This is a detailed essay answer that was cut off by token limit'
        parsed = parse_json_safely(raw)
        self.assertIn("model_answer", parsed)
        self.assertTrue(parsed["model_answer"].startswith("This is a detailed essay"))

    def test_json_repair_markdown_fences(self):
        """Tests stripping of markdown code fences and metadata preamble."""
        raw = """```json
        {
            "questions": [
                {
                    "type": "long_answer",
                    "text": "Explain public key infrastructure.",
                    "marks": 10
                }
            ]
        }
        ```"""
        parsed = parse_json_safely(raw)
        self.assertIn("questions", parsed)
        self.assertEqual(len(parsed["questions"]), 1)

    def test_json_repair_unescaped_newlines(self):
        """Tests repair of unescaped newlines inside JSON string fields."""
        raw = '{"model_answer": "Paragraph 1\nParagraph 2\nParagraph 3"}'
        parsed = parse_json_safely(raw)
        self.assertIn("model_answer", parsed)
        self.assertIn("Paragraph 1", parsed["model_answer"])

    # --- 2. Deterministic Rubric Marks Repair ---
    def test_rubric_marks_sum_repair_under(self):
        """Criteria summing to 6 must be scaled to exactly 10.0."""
        raw_rubric = [
            {"criterion": "Definitions", "marks": 2},
            {"criterion": "Architecture", "marks": 4},
        ]
        repaired = repair_rubric_marks(raw_rubric, 10.0)
        total = sum(item["marks"] for item in repaired)
        self.assertAlmostEqual(total, 10.0, places=1)

    def test_rubric_marks_sum_repair_over(self):
        """Criteria summing to 15 must be scaled down to exactly 10.0."""
        raw_rubric = [
            {"criterion": "Concepts", "marks": 5},
            {"criterion": "Mechanisms", "marks": 6},
            {"criterion": "Examples", "marks": 4},
        ]
        repaired = repair_rubric_marks(raw_rubric, 10.0)
        total = sum(item["marks"] for item in repaired)
        self.assertAlmostEqual(total, 10.0, places=1)

    def test_rubric_marks_sum_repair_empty(self):
        """Empty or invalid rubric must generate structured default criteria summing to target."""
        repaired = repair_rubric_marks([], 10.0)
        total = sum(item["marks"] for item in repaired)
        self.assertAlmostEqual(total, 10.0, places=1)
        self.assertTrue(len(repaired) >= 3)

    # --- 3. Grounding & Evidence Verification ---
    def test_grounding_evidence_exact_substring(self):
        """Exact verbatim quote from syllabus passes grounding."""
        syllabus = "Unit 1 covers Footprinting, Reconnaissance, and Port Scanning techniques using Nmap."
        evidence = "Footprinting, Reconnaissance, and Port Scanning"
        self.assertTrue(verify_grounding_evidence(evidence, syllabus))

    def test_grounding_evidence_fuzzy_window(self):
        """Slight punctuation or formatting variations in evidence still pass."""
        syllabus = "Buffer overflows occur when data exceeds the allocated stack memory buffer size."
        evidence = "data exceeds the allocated stack memory"
        self.assertTrue(verify_grounding_evidence(evidence, syllabus))

    def test_grounding_evidence_hallucination_rejected(self):
        """Completely hallucinated topic quote is flagged and rejected."""
        syllabus = "This course covers relational database design and SQL indexing strategies."
        evidence = "Quantum entanglement enables superluminal communication channels"
        self.assertFalse(verify_grounding_evidence(evidence, syllabus))

    # --- 4. Deduplication Logic ---
    def test_deduplicate_questions(self):
        """Questions with >= 85% similarity are pruned while preserving unique ones."""
        questions = [
            {"text": "Explain the difference between TCP and UDP protocols."},
            {"text": "Explain the differences between TCP and UDP protocols."},  # duplicate
            {"text": "Discuss the operation of the Border Gateway Protocol (BGP)."},  # distinct
        ]
        unique, dropped = deduplicate_questions(questions, similarity_threshold=0.85)
        self.assertEqual(len(unique), 2)
        self.assertEqual(dropped, 1)

    # --- 5. Structured Output Schemas ---
    def test_question_type_schemas(self):
        """Verifies schema structure for all five question types."""
        for q_type in ["mcq", "true_false", "fill_blank", "short_answer", "long_answer"]:
            schema = get_question_type_schema(q_type)
            self.assertEqual(schema["type"], "object")
            self.assertIn("questions", schema["properties"])
            self.assertIn("required", schema)

        step_b_schema = get_question_type_schema("long_answer_step_b")
        self.assertEqual(step_b_schema["type"], "object")
        self.assertIn("model_answer", step_b_schema["properties"])

    # --- 6. Blueprint Count Calculations ---
    def test_blueprint_counts_calculation(self):
        """Verifies correct calculation of question counts from blueprint."""
        blueprint = {
            "mcq": {"count": 10, "marksPerQuestion": 1, "enabled": True},
            "long_answer": {"count": 3, "marksPerQuestion": 10, "enabled": True},
        }
        counts, actual_total = compute_question_counts(["mcq", "long_answer"], 40, blueprint=blueprint)
        self.assertEqual(counts["mcq"], 10)
        self.assertEqual(counts["long_answer"], 3)
        self.assertEqual(actual_total, 40)

    # --- 7. Student Privacy (No Leakage) ---
    def test_student_attempt_privacy_guarantee(self):
        """Ensures student attempt payload strictly excludes model_answer, rubric, and correct answers."""
        exam = Exam.objects.create(
            institution=self.institution,
            title="Final Security Exam",
            created_by=self.faculty_user,
            duration_minutes=60,
            total_marks=20,
            ai_model_used="llama3.2-3b",
            status=Exam.Status.PUBLISHED,
        )
        q1 = Question.objects.create(
            exam=exam,
            institution=self.institution,
            order=1,
            question_type="long_answer",
            difficulty="hard",
            text="Explain zero trust architecture in detail.",
            marks=10,
            model_answer="Comprehensive SECRET model answer with internal keys.",
            rubric=[{"criterion": "Identity verification", "marks": 5}, {"criterion": "Micro-segmentation", "marks": 5}],
        )

        from api.models import StudentAttempt
        attempt = StudentAttempt.objects.create(
            exam=exam,
            student=self.student_user,
            institution=self.institution,
            question_order=[q1.id],
        )

        sanitized = sanitize_questions_for_attempt(attempt)
        self.assertEqual(len(sanitized), 1)
        item = sanitized[0]
        self.assertNotIn("model_answer", item)
        self.assertNotIn("rubric", item)
        self.assertNotIn("correct_answer", item)
        self.assertNotIn("accepted_answers", item)
        self.assertEqual(item["text"], "Explain zero trust architecture in detail.")
        self.assertEqual(item["marks"], 10.0)

    # --- 8. Syllabus Topic Chunking & Cache ---
    def test_syllabus_chunking(self):
        """Verifies topic chunking properly partitions syllabus text."""
        syllabus_text = """
        Unit 1: Fundamentals of Network Security
        Firewalls, IDS, IPS, and secure network design principles.
        
        Unit 2: Cryptography and PKI
        Symmetric and asymmetric encryption, RSA, AES, and digital certificates.
        """
        topics = ["Unit 1: Fundamentals of Network Security", "Unit 2: Cryptography and PKI"]
        chunks = chunk_syllabus_by_topics(syllabus_text, topics)
        self.assertIn("Unit 1: Fundamentals of Network Security", chunks)
        self.assertIn("Unit 2: Cryptography and PKI", chunks)

        chunk_1 = get_relevant_syllabus_chunk(syllabus_text, "Unit 1: Fundamentals of Network Security", chunks)
        self.assertIn("Firewalls", chunk_1)

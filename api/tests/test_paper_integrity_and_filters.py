import json
from unittest.mock import MagicMock, patch
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from admins.models import AdminInstitution
from faculty.models import FacultyProfile
from api.models import Exam, Question
from api.serializers import FacultyQuestionSerializer, QuestionSerializer
from api.utils.validate_paper import (
    canonicalize_type,
    canonicalize_difficulty,
    repair_rubric_marks,
    CANONICAL_TYPES,
    CANONICAL_DIFFICULTIES,
)
from api.generate_paper import (
    _generate_single_long_answer,
    _call_type_batch,
)

User = get_user_model()


class PaperIntegrityAndFiltersTestCase(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="admin@inst.edu",
            email="admin@inst.edu",
            password="AdminPassword123!",
        )
        self.institution = AdminInstitution.objects.create(
            admin=self.admin,
            institution_name="Test Engineering College",
            institution_code="TEC-2026",
            status=AdminInstitution.STATUS_ACTIVE,
        )
        self.faculty_user = User.objects.create_user(
            username="faculty_test",
            email="faculty@test.edu",
            password="FacultyPassword123!",
        )
        self.faculty_profile = FacultyProfile.objects.create(
            user=self.faculty_user,
            institution=self.institution,
            department="Computer Engineering",
        )
        self.client = APIClient()
        refresh = RefreshToken.for_user(self.faculty_user)
        refresh['role'] = 'Faculty'
        refresh['institution_id'] = self.institution.id
        access = refresh.access_token
        access['role'] = 'Faculty'
        access['institution_id'] = self.institution.id
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {str(access)}')

    # ---------------------------------------------------------
    # PROBLEM 1: Blueprint Contract & No Silent Type Substitution
    # ---------------------------------------------------------
    def test_canonicalize_type_all_variants(self):
        """All legacy and uppercase aliases must canonicalize to strict canonical strings."""
        test_cases = {
            "MCQ": "mcq",
            "mcq": "mcq",
            "MCQ_SINGLE": "mcq",
            "multiple_choice": "mcq",
            "TRUE_FALSE": "true_false",
            "true_false": "true_false",
            "truefalse": "true_false",
            "TF": "true_false",
            "tf": "true_false",
            "FILL_BLANK": "fill_blank",
            "fill_blank": "fill_blank",
            "fillblank": "fill_blank",
            "fill_in_the_blank": "fill_blank",
            "SHORT_ANSWER": "short_answer",
            "short_answer": "short_answer",
            "short": "short_answer",
            "LONG_ANSWER": "long_answer",
            "long_answer": "long_answer",
            "subjective": "long_answer",
            "SUBJECTIVE": "long_answer",
            "long": "long_answer",
        }
        for raw, expected in test_cases.items():
            self.assertEqual(canonicalize_type(raw), expected, f"Failed for {raw}")

    def test_canonicalize_difficulty_all_variants(self):
        """All casing variants of difficulty must normalize to easy, medium, hard."""
        test_cases = {
            "EASY": "easy",
            "easy": "easy",
            "MEDIUM": "medium",
            "medium": "medium",
            "med": "medium",
            "HARD": "hard",
            "hard": "hard",
        }
        for raw, expected in test_cases.items():
            self.assertEqual(canonicalize_difficulty(raw), expected, f"Failed for {raw}")

    def test_question_model_auto_canonicalizes_on_save(self):
        """Question.save() must canonicalize question_type and difficulty into DB."""
        exam = Exam.objects.create(
            title="Auto-canonicalize Test",
            institution=self.institution,
            department="Computer Engineering",
            created_by=self.faculty_user,
            total_marks=10,
            duration_minutes=60,
        )
        q = Question.objects.create(
            exam=exam,
            institution=self.institution,
            department="Computer Engineering",
            order=1,
            question_type="TRUE_FALSE",
            difficulty="HARD",
            text="Is Python interpreted?",
            correct_answer="True",
            marks=1,
        )
        self.assertEqual(q.question_type, "true_false")
        self.assertEqual(q.difficulty, "hard")

        # Reload from database to ensure persistence
        q.refresh_from_db()
        self.assertEqual(q.question_type, "true_false")
        self.assertEqual(q.difficulty, "hard")

    def test_call_type_batch_rejects_type_mismatches(self):
        """_call_type_batch must reject questions from LLM that do not match the requested type."""
        # LLM erroneously returned short_answer questions when MCQ was requested
        mock_response = json.dumps({
            "questions": [
                {
                    "type": "short_answer",
                    "text": "What is normalization?",
                    "marks": 5,
                    "difficulty": "medium",
                }
            ]
        })

        with patch("api.generate_paper.resolve_model", return_value="qwen2.5:3b-instruct"), \
             patch("api.generate_paper.call_ollama", return_value=mock_response):
            results = _call_type_batch(
                question_type="mcq",
                count=1,
                marks_per_q=1,
                model_key="qwen2.5:3b-instruct",
                topics=["Database Systems"],
                difficulty_distribution={"medium": 100},
                syllabus_chunk="DBMS Syllabus Chunk",
            )
            # The mismatched short_answer question must be rejected, yielding 0 valid questions
            self.assertEqual(len(results), 0)

    # ---------------------------------------------------------
    # PROBLEM 2: Serializer Filtering & Student Masking
    # ---------------------------------------------------------
    def test_faculty_question_serializer_canonicalizes_fields(self):
        """FacultyQuestionSerializer must output canonical question_type and difficulty."""
        exam = Exam.objects.create(
            title="Serializer Test",
            institution=self.institution,
            department="Computer Engineering",
            created_by=self.faculty_user,
            total_marks=10,
            duration_minutes=60,
        )
        # Directly bypass model save to test serializer defense-in-depth
        q = Question(
            exam=exam,
            institution=self.institution,
            department="Computer Engineering",
            order=1,
            question_type="SUBJECTIVE",
            difficulty="MEDIUM",
            text="Discuss database indexing techniques.",
            marks=10,
        )
        data = FacultyQuestionSerializer(q).data
        self.assertEqual(data["question_type"], "long_answer")
        self.assertEqual(data["difficulty"], "medium")

    def test_student_serializer_never_exposes_rubric_or_model_answer(self):
        """Student exam questions payload MUST NOT leak rubric, model_answer, or correct_answer (Ground Rule 5)."""
        from api.models import StudentAttempt
        from api.utils.exam_attempt_helper import sanitize_questions_for_attempt
        exam = Exam.objects.create(
            title="Student Security Test",
            institution=self.institution,
            department="Computer Engineering",
            created_by=self.faculty_user,
            total_marks=10,
            duration_minutes=60,
        )
        q = Question.objects.create(
            exam=exam,
            institution=self.institution,
            department="Computer Engineering",
            order=1,
            question_type="long_answer",
            difficulty="medium",
            text="Explain ACID properties.",
            marks=10,
            model_answer="Atomicity, Consistency, Isolation, Durability details...",
            rubric=[{"criterion": "Atomicity", "marks": 2.5}],
        )
        attempt = StudentAttempt.objects.create(
            student=self.faculty_user,
            institution=self.institution,
            exam=exam,
            question_order=[q.id],
        )
        student_questions = sanitize_questions_for_attempt(attempt)
        self.assertEqual(len(student_questions), 1)
        self.assertNotIn("rubric", student_questions[0])
        self.assertNotIn("model_answer", student_questions[0])
        self.assertNotIn("correct_answer", student_questions[0])

    # ---------------------------------------------------------
    # PROBLEM 3: Long Answer Generation & Step B Rubric Sum Repair
    # ---------------------------------------------------------
    def test_rubric_marks_sum_repair_exact(self):
        """Rubric marks repair must rescale and round criteria so sum equals total marks."""
        rubric = [
            {"criterion": "Syntax & Semantics", "marks": 3},
            {"criterion": "Analysis", "marks": 4},
        ]
        # Sum is 7, but question is worth 10 marks
        repaired = repair_rubric_marks(rubric, 10.0)
        repaired_sum = sum(float(r["marks"]) for r in repaired)
        self.assertAlmostEqual(repaired_sum, 10.0, places=2)

    def test_generate_single_long_answer_executes_step_b(self):
        """_generate_single_long_answer must execute Step B to populate model_answer and rubric."""
        step_a_resp = json.dumps({
            "questions": [
                {
                    "type": "long_answer",
                    "text": "Explain relational calculus with formal expressions.",
                    "marks": 10,
                    "difficulty": "hard",
                    "rubric": [
                        {"criterion": "Tuple relational calculus", "marks": 5},
                        {"criterion": "Domain relational calculus", "marks": 5},
                    ],
                }
            ]
        })

        step_b_resp = json.dumps({
            "model_answer": (
                "Relational calculus is a non-procedural query language that describes "
                "the desired information without giving a specific procedure for obtaining it. "
                "In Tuple Relational Calculus (TRC), queries are of the form {t | P(t)} where t is a tuple "
                "variable and P(t) is a formula expressing the predicate condition..."
            ),
            "rubric": [
                {"criterion": "Tuple relational calculus definition and examples", "marks": 5.0},
                {"criterion": "Domain relational calculus definition and examples", "marks": 5.0},
            ],
        })

        call_ollama_mock = MagicMock(side_effect=[step_a_resp, step_b_resp])

        with patch("api.generate_paper.OLLAMA_LONG_ANSWER_SINGLE_PASS", False), \
             patch("api.generate_paper.call_ollama", call_ollama_mock):
            q_res = _generate_single_long_answer(
                model_tag="qwen2.5:3b-instruct",
                marks_per_q=10.0,
                topic="Relational Calculus",
                difficulty="hard",
                syllabus_chunk="Unit 2: Relational Calculus and Formal Query Languages",
            )
            self.assertIsNotNone(q_res)
            self.assertEqual(q_res["type"], "long_answer")
            self.assertTrue(len(q_res["model_answer"].split()) >= 25)
            self.assertNotIn("generating in background", q_res["model_answer"].lower())
            self.assertEqual(len(q_res["rubric"]), 2)

    def test_regenerate_question_mode_answer_only(self):
        """RegenerateQuestionView with mode='answer_only' regenerates model_answer without modifying question text."""
        exam = Exam.objects.create(
            title="Answer Only Regen Test",
            institution=self.institution,
            department="Computer Engineering",
            created_by=self.faculty_user,
            total_marks=10,
            duration_minutes=60,
            source_syllabus_text="Relational Database Systems and Query Optimization.",
            topics=["Query Optimization"],
        )
        q = Question.objects.create(
            exam=exam,
            institution=self.institution,
            department="Computer Engineering",
            order=1,
            question_type="long_answer",
            difficulty="medium",
            text="Describe cost-based query optimization algorithms.",
            marks=10,
            model_answer="",  # empty originally
            rubric=[],
        )

        mock_step_b = json.dumps({
            "model_answer": (
                "Cost-based query optimization evaluates alternative execution plans based on "
                "estimated disk I/O, CPU time, and communication costs using catalog statistics. "
                "The optimizer explores plan spaces via join order permutations and index scans."
            ),
            "rubric": [
                {"criterion": "Cost metrics (I/O, CPU, network)", "marks": 5.0},
                {"criterion": "Plan space search and dynamic programming", "marks": 5.0},
            ],
        })

        with patch("api.generate_paper.resolve_model", return_value="qwen2.5:3b-instruct"), \
             patch("api.generate_paper.call_ollama", return_value=mock_step_b):
            url = f"/api/faculty/exams/{exam.id}/questions/{q.id}/regenerate/"
            response = self.client.post(url, {"mode": "answer_only"}, format="json")

            self.assertEqual(response.status_code, status.HTTP_200_OK)
            q.refresh_from_db()
            # Question text and order must be strictly preserved
            self.assertEqual(q.text, "Describe cost-based query optimization algorithms.")
            self.assertEqual(q.order, 1)
            # Model answer and rubric must be freshly populated
            self.assertIn("Cost-based query optimization", q.model_answer)
            self.assertEqual(len(q.rubric), 2)
            self.assertEqual(sum(r["marks"] for r in q.rubric), 10.0)

    # ---------------------------------------------------------
    # PHASE 5: Audit Paper Integrity Management Command
    # ---------------------------------------------------------
    def test_audit_paper_integrity_dry_run_command(self):
        """audit_paper_integrity in --dry-run mode must report issues without altering DB."""
        exam = Exam.objects.create(
            title="Integrity Audit Test",
            institution=self.institution,
            department="Computer Engineering",
            created_by=self.faculty_user,
            total_marks=10,
            duration_minutes=60,
        )
        # Create a question with non-canonical fields and empty rubric
        Question.objects.create(
            exam=exam,
            institution=self.institution,
            department="Computer Engineering",
            order=1,
            question_type="subjective",  # legacy non-canonical
            difficulty="EASY",           # uppercase non-canonical
            text="Explain cloud virtualization.",
            marks=10,
            model_answer="(Model answer: generating in background...)",
            rubric=[],
        )

        from io import StringIO
        out = StringIO()
        call_command("audit_paper_integrity", "--dry-run", stdout=out)
        output = out.getvalue()

        self.assertIn("PAPER INTEGRITY AUDIT LEDGER (DRY-RUN (READ-ONLY))", output)
        self.assertIn("Non-canonical Types:", output)
        self.assertIn("Empty/Defective Rubrics:", output)

        # Verify DB remained untouched in dry-run mode
        q = Question.objects.get(exam=exam)
        self.assertIn("generating in background", q.model_answer)

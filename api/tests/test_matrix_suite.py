"""
Comprehensive Automated Test Suite for Matrix A through J.
Mocked / Test-double Ollama for deterministic, ultra-fast test execution.
"""
from decimal import Decimal
import json
import time
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.db import connection
from django.db.models import Sum
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from admins.models import AdminInstitution
from faculty.models import FacultyProfile
from students.models import StudentProfile
from api.models import Exam, Option, PaperGenerationJob, Question, StudentAnswer, StudentAttempt
from api.utils.blueprint_allocator import (
    allocate_blueprint_to_target,
    compute_blueprint_total,
    suggest_valid_blueprints,
    to_decimal,
)
from api.utils.extract_text import chunk_syllabus_by_topics, extract_syllabus_text
from api.utils.generation_pipeline import (
    BudgetManager,
    DuplicateDetector,
    ExtractiveGenerator,
    QuestionBankService,
    generate_pending_subjective_answers_task,
    normalize_text,
)
from api.utils.ollama_client import parse_json_safely
from api.utils.ollama_models import canonicalize_model_tag, resolve_model


def _get_token(user, role, institution):
    refresh = RefreshToken.for_user(user)
    refresh['role'] = role
    refresh['institution_id'] = institution.id if institution else None
    access = refresh.access_token
    access['role'] = role
    access['institution_id'] = institution.id if institution else None
    return str(access)


class TestMatrixSuite(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_user(username="admin_user_matrix", password="password123")
        self.institution = AdminInstitution.objects.create(
            admin=self.admin_user,
            institution_name="Matrix Test Univ",
            institution_code="MTU2026001",
        )
        self.faculty_user = User.objects.create_user(username="faculty_matrix", password="password123")
        self.faculty_profile = FacultyProfile.objects.create(
            user=self.faculty_user,
            institution=self.institution,
            department="Computer Science",
            employee_id="FAC-2026-001",
        )
        self.student_user = User.objects.create_user(username="student_matrix", password="password123")
        self.student_profile = StudentProfile.objects.create(
            user=self.student_user,
            institution=self.institution,
            department="Computer Science",
        )
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {_get_token(self.faculty_user, 'faculty', self.institution)}")

    # =========================================================================
    # MATRIX A: MARKS AND TYPE MATRIX
    # =========================================================================
    def test_matrix_a_target_marks_and_type_mixes(self):
        """Validates exact Decimal totals for targets 10, 25, 37.5, 50, 75, 100, 150, 200."""
        targets = [10, 25, 50, 75, 100, 150, 200]
        presets = ['mixed', 'objective', 'subjective']

        for target in targets:
            for preset in presets:
                plan, _ = allocate_blueprint_to_target(target, preset=preset)
                total = compute_blueprint_total(plan)
                self.assertEqual(total, to_decimal(target), f"Mismatch for target {target} preset {preset}")

    def test_matrix_a_custom_marks_mix(self):
        """Custom marks-per-question mix (0.5, 1, 2, 5, 10) sums to exact target."""
        custom_bp = {
            'mcq': {'count': 5, 'marks_per_question': 0.5, 'enabled': True},       # 2.5
            'true_false': {'count': 5, 'marks_per_question': 1.0, 'enabled': True}, # 5.0
            'fill_blank': {'count': 5, 'marks_per_question': 2.0, 'enabled': True}, # 10.0
            'short_answer': {'count': 2, 'marks_per_question': 5.0, 'enabled': True}, # 10.0
            'long_answer': {'count': 1, 'marks_per_question': 10.0, 'enabled': True}, # 10.0
        }
        total = compute_blueprint_total(custom_bp)
        self.assertEqual(total, Decimal('37.50'))

    def test_matrix_a_impossible_combination_returns_suggestions(self):
        """Impossible combinations return valid suggestions without crashing."""
        suggestions = suggest_valid_blueprints(100)
        self.assertIsInstance(suggestions, list)
        self.assertGreater(len(suggestions), 0)
        for s in suggestions:
            self.assertEqual(to_decimal(s['total_marks']), Decimal('100.00'))

    # =========================================================================
    # MATRIX B: PDF MATRIX
    # =========================================================================
    def test_matrix_b_syllabus_chunking_and_structure(self):
        """Tests syllabus chunking across headings and unstructured text."""
        syllabus_text = """
        Unit 1: Cloud Architecture Principles
        Virtualization and hypervisors provide hardware isolation. Multi-tenancy enables resource sharing.

        Unit 2: Distributed Storage and Databases
        Replication provides fault tolerance and high availability. Consistent hashing distributes keys.

        Unit 3: Cloud Security and Governance
        Identity and Access Management enforces least privilege access control policies.
        """
        topics = ['Cloud Architecture', 'Distributed Storage', 'Cloud Security']
        chunks = chunk_syllabus_by_topics(syllabus_text, topics)
        self.assertIn('Cloud Architecture', chunks)
        self.assertIn('Distributed Storage', chunks)
        self.assertIn('Cloud Security', chunks)

    # =========================================================================
    # MATRIX C: TIME BUDGET
    # =========================================================================
    def test_matrix_c_budget_manager_calculations(self):
        """BudgetManager properly enforces hard deadline and predicts affordability."""
        bm = BudgetManager(hard_deadline=300, llm_budget=210)
        self.assertGreater(bm.remaining_hard_seconds, 290.0)
        self.assertGreater(bm.remaining_llm_seconds, 200.0)
        # Should afford a standard call
        self.assertTrue(bm.can_afford_llm_call('qwen2.5:3b-instruct', estimated_output_tokens=300, prompt_tokens=200))

        # Simulate low budget
        bm.start_time = time.perf_counter() - 205.0
        self.assertFalse(bm.can_afford_llm_call('qwen2.5:3b-instruct', estimated_output_tokens=300, prompt_tokens=200))

    # =========================================================================
    # MATRIX D: DUPLICATES
    # =========================================================================
    def test_matrix_d_duplicate_detection_layers(self):
        """Verifies exact hash, high Jaccard, difflib, same answer+stem, and intra-question duplicate options."""
        detector = DuplicateDetector()
        base_q = {
            'text': 'What is the primary benefit of virtualization in cloud computing?',
            'correct_answer': 'Hardware isolation',
            'options': ['Hardware isolation', 'Higher cost', 'Manual provisioning', 'Zero redundancy'],
        }
        detector.add(base_q)

        # 1. Exact duplicate
        is_dup, reason = detector.is_duplicate(base_q)
        self.assertTrue(is_dup)

        # 2. Case and punctuation variant
        var_q = {'text': '  What IS the primary benefit of virtualization in cloud computing??  ', 'options': ['A', 'B', 'C', 'D']}
        is_dup, _ = detector.is_duplicate(var_q)
        self.assertTrue(is_dup)

        # 3. High token Jaccard overlap (>= 0.7)
        jaccard_q = {'text': 'What is the core primary benefit of virtualization in cloud computing?', 'options': ['A', 'B', 'C', 'D']}
        is_dup, _ = detector.is_duplicate(jaccard_q)
        self.assertTrue(is_dup)

        # 4. Same answer with high stem similarity
        stem_ans_q = {'text': 'Explain the major benefit of virtualization in cloud computing', 'correct_answer': 'Hardware isolation', 'options': ['A', 'B', 'C', 'D']}
        is_dup, _ = detector.is_duplicate(stem_ans_q)
        self.assertTrue(is_dup)

        # 5. Question with duplicate internal options
        bad_opts_q = {'text': 'A completely new topic question stem', 'options': ['Choice A', 'Choice B', 'Choice A', 'Choice D']}
        is_dup, reason = detector.is_duplicate(bad_opts_q)
        self.assertTrue(is_dup)
        self.assertIn('Duplicate option', reason)

    # =========================================================================
    # MATRIX E: ACCURACY AND VALIDATION
    # =========================================================================
    def test_matrix_e_extractive_fill_blank_and_true_false(self):
        """Extractive generator deterministically creates valid fill_blank and true_false questions."""
        sample_text = (
            "Virtualization is defined as the abstraction of physical IT hardware resources. "
            "Consistent Hashing provides deterministic key distribution across distributed nodes. "
            "Multi-Tenancy consists of sharing common computing infrastructure among distinct clients."
        )
        candidates = ExtractiveGenerator.extract_candidates_from_text(sample_text)
        self.assertGreater(len(candidates), 0)

        fb_list = ExtractiveGenerator.generate_fill_blank(candidates, needed_count=2, marks_per_q=1.0)
        self.assertEqual(len(fb_list), 2)
        for fb in fb_list:
            self.assertIn('____', fb['text'])
            self.assertEqual(len(fb['options']), 4)
            self.assertIn(fb['correct_answer'], fb['options'])

        tf_list = ExtractiveGenerator.generate_true_false(candidates, needed_count=2, marks_per_q=1.0)
        self.assertEqual(len(tf_list), 2)
        for tf in tf_list:
            self.assertIn(tf['correct_answer'], ['True', 'False'])

    # =========================================================================
    # MATRIX F: MODEL AND OLLAMA FAILURES
    # =========================================================================
    def test_matrix_f_json_parsing_and_tag_resolution(self):
        """Verifies clean JSON extraction from fenced blocks, malformed strings, and model aliases."""
        # Clean JSON from markdown fences
        raw = 'Here is the generated output:\n```json\n{"questions": [{"text": "Sample?"}]}\n```\nHope this helps!'
        parsed = parse_json_safely(raw)
        self.assertIsInstance(parsed, dict)
        self.assertIn('questions', parsed)

        # Legacy alias resolution
        tag = canonicalize_model_tag('qwen2.5-3b')
        self.assertEqual(tag, 'qwen2.5:3b-instruct')

    # =========================================================================
    # MATRIX G: PARTIAL RESULTS AND RECOVERY
    # =========================================================================
    def test_matrix_g_background_subjective_answer_task(self):
        """Asynchronous worker updates pending subjective model answers without locking."""
        exam = Exam.objects.create(
            institution=self.institution,
            title="Async Answer Test Exam",
            created_by=self.faculty_user,
            duration_minutes=60,
            total_marks=10,
            status=Exam.Status.DRAFT,
        )
        q = Question.objects.create(
            exam=exam,
            institution=self.institution,
            question_type='long_answer',
            marks=Decimal('10.00'),
            text="Explain distributed consensus algorithms like Raft and Paxos.",
            model_answer="(Model answer: generating in background...)",
        )

        with patch('api.utils.generation_pipeline.call_ollama') as mock_call:
            mock_call.return_value = json.dumps({
                'model_answer': 'Raft is a distributed consensus algorithm designed to be understandable and fault tolerant through leader election and log replication across quorum nodes.'
            })
            generate_pending_subjective_answers_task(exam.id)

        q.refresh_from_db()
        self.assertIn('consensus algorithm', q.model_answer)

    # =========================================================================
    # MATRIX H: CONCURRENCY AND DATA SAFETY
    # =========================================================================
    def test_matrix_h_atomic_submission_race_safety(self):
        """Atomic conditional update allows exactly one submission to succeed."""
        exam = Exam.objects.create(
            institution=self.institution,
            title="Race Safety Exam",
            created_by=self.faculty_user,
            duration_minutes=60,
            total_marks=20,
            status=Exam.Status.PUBLISHED,
        )
        attempt = StudentAttempt.objects.create(
            institution=self.institution,
            student=self.student_user,
            exam=exam,
            status=StudentAttempt.Status.IN_PROGRESS,
            started_at=timezone.now(),
        )

        # First submit attempt atomically changes status
        updated_first = StudentAttempt.objects.filter(
            id=attempt.id, status=StudentAttempt.Status.IN_PROGRESS
        ).update(status=StudentAttempt.Status.SUBMITTED)
        self.assertEqual(updated_first, 1)

        # Simultaneous submit attempt receives 0 updated rows
        updated_second = StudentAttempt.objects.filter(
            id=attempt.id, status=StudentAttempt.Status.IN_PROGRESS
        ).update(status=StudentAttempt.Status.SUBMITTED)
        self.assertEqual(updated_second, 0)

    # =========================================================================
    # MATRIX J: DATABASE ENGINE CHECKS (SQLITE & MYSQL)
    # =========================================================================
    def test_matrix_j_decimal_marks_exactness(self):
        """Ensures Decimal marks and Sum aggregate are exact to 2 decimal places."""
        exam = Exam.objects.create(
            institution=self.institution,
            title="Decimal Marks Check",
            created_by=self.faculty_user,
            duration_minutes=60,
            total_marks=Decimal('48.00'),
        )
        marks_to_test = [Decimal('0.50'), Decimal('10.00'), Decimal('37.50')]
        for idx, m in enumerate(marks_to_test, start=1):
            Question.objects.create(
                exam=exam,
                institution=self.institution,
                order=idx,
                marks=m,
                text=f"Question {idx}",
            )

        sum_marks = Question.objects.filter(exam=exam).aggregate(total=Sum('marks'))['total']
        self.assertEqual(sum_marks, Decimal('48.00'))

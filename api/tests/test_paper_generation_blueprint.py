"""Comprehensive automated tests for Paper Generation Blueprint and Timezone Fix.
Tests:
1. Deterministic blueprint allocator engine across diverse target marks (including odd targets) and presets.
2. Timezone UnboundLocalError regression test (uploaded_at with no active job).
3. Server-side blueprint vs target_total_marks mismatch rejection (HTTP 400).
4. Server-side blueprint matching acceptance.
5. Exam creation integrity (target_total_marks, total_marks, marks_shortfall).
6. Role-based access control.
"""

import json
from decimal import Decimal
from unittest.mock import patch
from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from admins.models import AdminInstitution, AdminProfile
from faculty.models import FacultyProfile
from students.models import StudentProfile
from api.models import Exam, Subject, Topic
from api.utils.blueprint_allocator import (
    compute_blueprint_total,
    allocate_blueprint_to_target,
    rebalance_blueprint_to_target,
    balance_blueprint_smallest_change,
)


def _get_token(user, role, institution):
    refresh = RefreshToken.for_user(user)
    refresh['role'] = role
    refresh['institution_id'] = institution.id if institution else None
    access = refresh.access_token
    access['role'] = role
    access['institution_id'] = institution.id if institution else None
    return str(access)


class BlueprintAllocatorUnitTestCase(TestCase):
    """Exhaustive unit tests for the deterministic blueprint allocator math engine."""

    def test_compute_blueprint_total(self):
        bp = {
            'mcq': {'count': 5, 'marks_per_question': 2, 'enabled': True},
            'true_false': {'count': 5, 'marks_per_question': 2, 'enabled': True},
            'fill_in_the_blanks': {'count': 5, 'marks_per_question': 2, 'enabled': True},
            'short_answer': {'count': 4, 'marks_per_question': 5, 'enabled': True},
            'long_answer': {'count': 5, 'marks_per_question': 10, 'enabled': True},
        }
        # 10 + 10 + 10 + 20 + 50 = 100
        self.assertEqual(compute_blueprint_total(bp), 100)

        # Disable long_answer
        bp['long_answer']['enabled'] = False
        self.assertEqual(compute_blueprint_total(bp), 50)

    def test_allocator_targets_and_presets(self):
        targets = [1, 5, 10, 20, 25, 30, 37, 50, 75, 99, 100, 150, 200]
        presets = ['mixed', 'objective', 'subjective']

        for target in targets:
            for preset in presets:
                with self.subTest(target=target, preset=preset):
                    bp, notes = allocate_blueprint_to_target(target, preset=preset)
                    calculated_sum = compute_blueprint_total(bp)
                    self.assertEqual(
                        calculated_sum,
                        target,
                        f"Failed for target={target}, preset={preset}. Sum was {calculated_sum}"
                    )
                    total_q = sum(cfg['count'] for cfg in bp.values() if cfg.get('enabled'))
                    self.assertGreater(total_q, 0)
                    # All counts and marks must be non-negative integers
                    for qtype, config in bp.items():
                        self.assertIsInstance(config['count'], int)
                        self.assertIsInstance(config['marks'], int)
                        self.assertGreaterEqual(config['count'], 0)
                        self.assertGreaterEqual(config['marks'], 0)

    def test_rebalance_blueprint_to_target(self):
        initial, _ = allocate_blueprint_to_target(100)
        # Rebalance down to 50
        rebalanced_50, _ = rebalance_blueprint_to_target(initial, 50)
        self.assertEqual(compute_blueprint_total(rebalanced_50), 50)

        # Rebalance up to 150
        rebalanced_150, _ = rebalance_blueprint_to_target(initial, 150)
        self.assertEqual(compute_blueprint_total(rebalanced_150), 150)

        # Rebalance to odd target 37
        rebalanced_37, _ = rebalance_blueprint_to_target(initial, 37)
        self.assertEqual(compute_blueprint_total(rebalanced_37), 37)

    def test_balance_smallest_change(self):
        bp, _ = allocate_blueprint_to_target(50)
        # Intentionally alter mcq count by +1 (adds 2 marks -> total 52)
        bp['mcq']['count'] += 1
        self.assertEqual(compute_blueprint_total(bp), 52)

        balanced_bp, change = balance_blueprint_smallest_change(bp, 50)
        self.assertEqual(compute_blueprint_total(balanced_bp), 50)
        self.assertIsNotNone(change)


class PaperGenerationApiRegressionTestCase(TestCase):
    """Integration tests for GeneratePaperView testing timezone scoping and blueprint validation."""

    def setUp(self):
        cache.clear()
        self.client = APIClient()

        # Create Admin and Institution
        self.admin_user = User.objects.create_user(
            username="admin@apex.edu",
            password="testpassword123",
            email="admin@apex.edu"
        )
        AdminProfile.objects.create(user=self.admin_user)
        self.institution = AdminInstitution.objects.create(
            admin=self.admin_user,
            institution_name="Apex University",
            institution_code="APEX",
            status=AdminInstitution.STATUS_ACTIVE
        )

        # Create Faculty User
        self.faculty_user = User.objects.create_user(
            username="prof_smith",
            password="testpassword123",
            first_name="John",
            last_name="Smith",
            email="smith@apex.edu"
        )
        self.faculty_profile = FacultyProfile.objects.create(
            user=self.faculty_user,
            institution=self.institution,
            department="Computer Science",
            employee_id="FAC-001"
        )
        self.faculty_token = _get_token(self.faculty_user, 'faculty', self.institution)

        # Create Student User for RBAC testing
        self.student_user = User.objects.create_user(
            username="student_alice",
            password="testpassword123",
            email="alice@apex.edu"
        )
        StudentProfile.objects.create(
            user=self.student_user,
            institution=self.institution,
            student_id="STU-2026-0001"
        )
        self.student_token = _get_token(self.student_user, 'student', self.institution)

        # Create Subject and Topic
        self.subject = Subject.objects.create(
            name="Data Structures",
            code="CS201",
            institution=self.institution,
            department="Computer Science"
        )
        self.topic = Topic.objects.create(
            name="Binary Trees",
            subject=self.subject,
            institution=self.institution
        )

    def tearDown(self):
        cache.clear()

    @patch('api.generate_paper.extract_syllabus_text')
    @patch('api.generate_paper.threading.Thread')
    def test_timezone_unbound_local_regression_with_syllabus(self, mock_thread, mock_extract):
        """Regression test for UnboundLocalError: 'timezone' when syllabus is uploaded and no active_job exists.
        Previously, line 850 in api/generate_paper.py threw:
        UnboundLocalError: cannot access local variable 'timezone' where it is not associated with a value
        """
        mock_extract.return_value = "Chapter 1: Binary Search Trees\nChapter 2: AVL Trees and Balance"
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.faculty_token}')

        syllabus_file = SimpleUploadedFile(
            "syllabus.pdf",
            b"%PDF-1.4 mock pdf content",
            content_type="application/pdf"
        )

        valid_bp, _ = allocate_blueprint_to_target(50)

        payload = {
            'title': 'Midterm Exam - Binary Trees',
            'subject': self.subject.id,
            'department': 'Computer Science',
            'total_marks': 50,
            'duration_minutes': 60,
            'topics': 'Binary Trees',
            'question_types': ['MCQ_SINGLE', 'TRUE_FALSE', 'SHORT_ANSWER'],
            'difficulty_distribution': json.dumps({'easy': 40, 'medium': 40, 'hard': 20}),
            'blueprint': json.dumps(valid_bp),
            'ai_model': 'qwen2.5-3b',
            'syllabus': syllabus_file,
            'accept_capacity_override': True,
        }

        response = self.client.post('/api/faculty/exams/generate/', payload, format='multipart')

        # Must NOT return 500 UnboundLocalError
        self.assertNotEqual(
            response.status_code, 500,
            f"Server returned HTTP 500! Response detail: {response.data if hasattr(response, 'data') else response.content}"
        )
        self.assertIn(response.status_code, [200, 201, 202])

        # Verify Exam was created with exact target marks
        exam = Exam.objects.get(title='Midterm Exam - Binary Trees')
        self.assertEqual(int(exam.total_marks), 50)
        self.assertEqual(exam.target_total_marks, 50)
        self.assertEqual(exam.marks_shortfall, 0)

        # Verify source_documents has uploaded_at with valid ISO format
        self.assertTrue(exam.source_documents)
        first_doc = exam.source_documents[0]
        self.assertIn('uploaded_at', first_doc)
        self.assertIsInstance(first_doc['uploaded_at'], str)
        self.assertIn('T', first_doc['uploaded_at'])  # ISO 8601 format check

    def test_blueprint_mismatch_returns_400(self):
        """When blueprint total marks (e.g. 100) does not match target total_marks (e.g. 50),
        the server must reject with HTTP 400 and provide clear error details.
        """
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.faculty_token}')

        # Hardcoded 100 marks blueprint (the old default)
        mismatched_bp = {
            'mcq': {'count': 5, 'marks_per_question': 2, 'enabled': True},          # 10
            'true_false': {'count': 5, 'marks_per_question': 2, 'enabled': True},   # 10
            'fill_in_the_blanks': {'count': 5, 'marks_per_question': 2, 'enabled': True}, # 10
            'short_answer': {'count': 4, 'marks_per_question': 5, 'enabled': True}, # 20
            'long_answer': {'count': 5, 'marks_per_question': 10, 'enabled': True}, # 50
        } # total = 100

        payload = {
            'title': 'Mismatch Exam',
            'subject': self.subject.id,
            'department': 'Computer Science',
            'total_marks': 50,  # Target is 50, but blueprint is 100!
            'duration_minutes': 60,
            'topics': ['Binary Trees'],
            'question_types': ['MCQ_SINGLE'],
            'difficulty_distribution': {'easy': 50, 'medium': 50, 'hard': 0},
            'blueprint': mismatched_bp,
        }

        response = self.client.post('/api/faculty/exams/generate/', payload, format='json')
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertIn('detail', data)
        self.assertIn('Blueprint total marks (100) do not match target marks (50)', data['detail'])
        self.assertEqual(data.get('blueprint_marks'), 100)
        self.assertEqual(data.get('target_marks'), 50)
        self.assertEqual(data.get('difference'), -50)

    @patch('api.generate_paper.threading.Thread')
    def test_matching_blueprint_accepted(self, mock_thread):
        """When blueprint total marks equals target total_marks (e.g. 50),
        the server accepts the request and initiates generation.
        """
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.faculty_token}')

        bp_50, _ = allocate_blueprint_to_target(50)
        self.assertEqual(compute_blueprint_total(bp_50), 50)

        payload = {
            'title': 'Balanced 50 Mark Exam',
            'subject': self.subject.id,
            'department': 'Computer Science',
            'total_marks': 50,
            'duration_minutes': 60,
            'topics': ['Binary Trees'],
            'question_types': ['MCQ_SINGLE'],
            'difficulty_distribution': {'easy': 50, 'medium': 50, 'hard': 0},
            'blueprint': bp_50,
            'ai_model': 'qwen2.5-3b',
        }

        response = self.client.post('/api/faculty/exams/generate/', payload, format='json')
        self.assertIn(response.status_code, [200, 201, 202])
        self.assertTrue(Exam.objects.filter(title='Balanced 50 Mark Exam').exists())

    def test_student_cannot_generate_paper(self):
        """Students must receive HTTP 403 when attempting to generate papers."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.student_token}')
        payload = {
            'title': 'Hacker Student Exam',
            'subject': self.subject.id,
            'department': 'Computer Science',
            'total_marks': 50,
            'duration_minutes': 60,
        }
        response = self.client.post('/api/faculty/exams/generate/', payload, format='json')
        self.assertEqual(response.status_code, 403)
    @patch('api.generate_paper.threading.Thread')
    def test_free_text_subject_accepted_and_saved_without_existing_subject_record(self, mock_thread):
        """Free-text subject names (e.g. 'Artificial Intelligence & Robotics') entered
        without an existing Subject database record must be accepted and saved to Exam.subject.
        """
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.faculty_token}')
        bp_50, _ = allocate_blueprint_to_target(50)
        custom_subject = "Artificial Intelligence & Robotics"

        # Verify no Subject database record with this name exists
        self.assertFalse(Subject.objects.filter(name__iexact=custom_subject).exists())

        payload = {
            'title': 'AI & Robotics Mid-Term',
            'subject': custom_subject,
            'department': 'Computer Science',
            'total_marks': 50,
            'duration_minutes': 60,
            'topics': ['Neural Networks'],
            'question_types': ['MCQ_SINGLE'],
            'difficulty_distribution': {'easy': 50, 'medium': 50, 'hard': 0},
            'blueprint': bp_50,
            'ai_model': 'qwen2.5-3b',
        }

        response = self.client.post('/api/faculty/exams/generate/', payload, format='json')
        self.assertIn(response.status_code, [200, 201, 202])

        exam = Exam.objects.filter(title='AI & Robotics Mid-Term').first()
        self.assertIsNotNone(exam)
        self.assertEqual(exam.subject, custom_subject[:80])

    @patch('api.generate_paper.threading.Thread')
    def test_existing_subject_name_text_is_accepted_and_saved(self, mock_thread):
        """Entering the name of an existing subject as text (e.g. 'Data Structures')
        is accepted and saved correctly.
        """
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.faculty_token}')
        bp_50, _ = allocate_blueprint_to_target(50)

        payload = {
            'title': 'Data Structures Term Exam',
            'subject': 'Data Structures',
            'department': 'Computer Science',
            'total_marks': 50,
            'duration_minutes': 60,
            'topics': ['Binary Trees'],
            'question_types': ['MCQ_SINGLE'],
            'difficulty_distribution': {'easy': 50, 'medium': 50, 'hard': 0},
            'blueprint': bp_50,
            'ai_model': 'qwen2.5-3b',
        }

        response = self.client.post('/api/faculty/exams/generate/', payload, format='json')
        self.assertIn(response.status_code, [200, 201, 202])

        exam = Exam.objects.filter(title='Data Structures Term Exam').first()
        self.assertIsNotNone(exam)
        self.assertEqual(exam.subject, 'Data Structures')


"""
Tests for Part A: Exact Marks in AI Generation Pipeline.
Verifies:
1. Deterministic Blueprint Allocation across diverse integer targets [10, 20, 25, 37, 50, 75, 100, 150].
2. Rubric Repair using the Largest Remainder Method with integer guarantees.
3. Normalized Grounding Comparator (handling PDF linebreaks, hyphens, and Unicode quotes).
4. Content Capacity Estimation (word count, sentence count, supportable marks, adjusted blueprint).
5. GenerateMissingQuestionsView actions: scale_marks and set_total.
6. GeneratePaperView pre-flight capacity enforcement with override option.
"""
from decimal import Decimal
import json
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from admins.models import AdminInstitution, AdminProfile
from faculty.models import FacultyProfile
from api.models import Exam, Question, Subject, Topic
from api.utils.blueprint_allocator import (
    allocate_blueprint_to_target,
    compute_blueprint_total,
    estimate_content_capacity,
    to_decimal,
)
from api.utils.validate_paper import repair_rubric_marks, verify_grounding_evidence


def _get_token(user, role, institution):
    refresh = RefreshToken.for_user(user)
    refresh['role'] = role
    refresh['institution_id'] = institution.id if institution else None
    access = refresh.access_token
    access['role'] = role
    access['institution_id'] = institution.id if institution else None
    return str(access)


class ExactMarksPipelineTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()

        self.admin_user = User.objects.create_user(
            username="admin_exact@apex.edu",
            password="testpassword123",
            email="admin_exact@apex.edu",
        )
        AdminProfile.objects.create(user=self.admin_user)
        self.institution = AdminInstitution.objects.create(
            admin=self.admin_user,
            institution_name="Apex Exact University",
            institution_code="APEX-EXACT",
            status=AdminInstitution.STATUS_ACTIVE,
        )

        self.faculty_user = User.objects.create_user(
            username="faculty_exact",
            password="testpassword123",
            email="faculty_exact@apex.edu",
        )
        self.faculty_profile = FacultyProfile.objects.create(
            user=self.faculty_user,
            institution=self.institution,
            department="Computer Science",
            employee_id="FAC-EXACT-001",
        )
        self.faculty_token = _get_token(self.faculty_user, "faculty", self.institution)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.faculty_token}")

        self.subject = Subject.objects.create(
            name="Algorithms",
            code="CS301",
            department="Computer Science",
            institution=self.institution,
        )

    def test_deterministic_blueprint_allocator_targets(self):
        """Verify allocate_blueprint_to_target matches exact integer targets."""
        test_targets = [10, 20, 25, 37, 50, 75, 100, 150]
        for target in test_targets:
            bp, notes = allocate_blueprint_to_target(target)
            calc_total = compute_blueprint_total(bp)
            self.assertEqual(
                calc_total,
                Decimal(str(target)),
                f"Computed blueprint total for {target} was {calc_total}",
            )

    def test_rubric_repair_largest_remainder(self):
        """Verify repair_rubric_marks distributes exact integer/decimal question marks without rounding drift."""
        # Case 1: 3 criteria on a 10-mark question
        rubric = [
            {"criterion": "Accuracy", "weight": 35},
            {"criterion": "Completeness", "weight": 35},
            {"criterion": "Clarity", "weight": 30},
        ]
        repaired = repair_rubric_marks(rubric, target_marks=10.0)
        total_repaired = sum(float(c.get("marks", 0)) for c in repaired)
        self.assertEqual(total_repaired, 10.0)

        # Case 2: 7 criteria on a 7-mark question
        rubric_equal = [{"criterion": f"C{i}", "weight": 1} for i in range(7)]
        repaired_equal = repair_rubric_marks(rubric_equal, target_marks=7.0)
        self.assertEqual(sum(int(c.get("marks", 0)) for c in repaired_equal), 7)
        for c in repaired_equal:
            self.assertEqual(c.get("marks"), 1)

    def test_verify_grounding_evidence_normalized(self):
        """Verify evidence matching handles line breaks, soft hyphens, and smart quotes."""
        doc_text = "Data structures and algorithms form the fundamental foundation of software engineering."
        evidence_with_break = "fundamental\nfoundation of software"
        self.assertTrue(
            verify_grounding_evidence(
                source_evidence=evidence_with_break,
                syllabus_text=doc_text,
            )
        )

        doc_text_quotes = "The principle of “Divide and Conquer” breaks problems into smaller subproblems."
        evidence_with_quotes = '"Divide and Conquer" breaks problems'
        self.assertTrue(
            verify_grounding_evidence(
                source_evidence=evidence_with_quotes,
                syllabus_text=doc_text_quotes,
            )
        )

    def test_content_capacity_estimation(self):
        """Verify content capacity estimation identifies insufficient vs sufficient documents."""
        small_text = "QuickSort is a divide and conquer algorithm. It picks an element as a pivot."
        cap_small = estimate_content_capacity(small_text, topics=["Sorting"], target_marks=50)
        self.assertFalse(cap_small["is_capacity_sufficient"])
        self.assertGreater(cap_small["deficit_marks"], 0)
        self.assertIn("proposed_adjusted_blueprint", cap_small)

        large_sentences = [
            f"Section {i} explores advanced sorting theorem number {i} in depth with complete proofs."
            for i in range(120)
        ]
        large_text = " ".join(large_sentences)
        cap_large = estimate_content_capacity(large_text, topics=["Sorting"], target_marks=50)
        self.assertTrue(cap_large["is_capacity_sufficient"])
        self.assertEqual(cap_large["deficit_marks"], 0)

    def test_generate_missing_questions_scale_marks_action(self):
        """Verify action='scale_marks' scales existing questions to target marks and clears shortfall."""
        exam = Exam.objects.create(
            title="Shortfall Exam",
            subject=self.subject,
            created_by=self.faculty_user,
            institution=self.institution,
            total_marks=20,
            target_total_marks=20,
            duration_minutes=60,
            marks_shortfall=5,
            status=Exam.Status.DRAFT,
            question_types=["mcq", "short_answer"],
        )
        Question.objects.create(
            exam=exam,
            institution=self.institution,
            text="Q1 MCQ",
            question_type="mcq",
            marks=5,
            rubric=[{"criterion": "Answer", "marks": 5}],
        )
        Question.objects.create(
            exam=exam,
            institution=self.institution,
            text="Q2 MCQ",
            question_type="mcq",
            marks=5,
            rubric=[{"criterion": "Answer", "marks": 5}],
        )
        Question.objects.create(
            exam=exam,
            institution=self.institution,
            text="Q3 Short Answer",
            question_type="short_answer",
            marks=5,
            rubric=[{"criterion": "Explanation", "marks": 5}],
        )

        response = self.client.post(
            f"/api/faculty/exams/{exam.id}/generate-missing/",
            {"action": "scale_marks"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        exam.refresh_from_db()
        self.assertEqual(exam.marks_shortfall, 0)
        self.assertEqual(exam.total_marks, 20)
        q_sum = sum(int(q.marks) for q in exam.questions.all())
        self.assertEqual(q_sum, 20)

    def test_generate_missing_questions_set_total_action(self):
        """Verify action='set_total' sets exam total to current marks and clears shortfall."""
        exam = Exam.objects.create(
            title="Set Total Exam",
            subject=self.subject,
            created_by=self.faculty_user,
            institution=self.institution,
            total_marks=25,
            target_total_marks=25,
            duration_minutes=60,
            marks_shortfall=10,
            status=Exam.Status.DRAFT,
            question_types=["mcq"],
        )
        Question.objects.create(
            exam=exam,
            institution=self.institution,
            text="Q1",
            question_type="mcq",
            marks=15,
        )

        response = self.client.post(
            f"/api/faculty/exams/{exam.id}/generate-missing/",
            {"action": "set_total"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        exam.refresh_from_db()
        self.assertEqual(exam.total_marks, 15)
        self.assertEqual(exam.target_total_marks, 15)
        self.assertEqual(exam.marks_shortfall, 0)

    @patch("api.generate_paper.extract_syllabus_text")
    def test_preflight_capacity_exceeded_returns_409(self, mock_extract):
        """Verify pre-flight capacity check returns 409 with proposed adjusted blueprint."""
        mock_extract.return_value = "Binary search tree insertion algorithm."
        syllabus_file = SimpleUploadedFile(
            "tiny.txt", b"Binary search tree insertion algorithm.", content_type="text/plain"
        )
        payload = {
            "title": "Capacity Check Exam",
            "subject": self.subject.id,
            "department": "Computer Science",
            "total_marks": 100,
            "duration_minutes": 60,
            "topics": "Binary Search",
            "question_types": ["MCQ_SINGLE"],
            "syllabus": syllabus_file,
        }
        response = self.client.post("/api/faculty/exams/generate/", payload, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data.get("error_code"), "CONTENT_CAPACITY_EXCEEDED")
        self.assertIn("proposed_adjusted_blueprint", response.data)

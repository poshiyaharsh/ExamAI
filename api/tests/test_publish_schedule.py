from datetime import timedelta
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status

from api.models import (
    AdminInstitution,
    Exam,
    Question,
    User,
)
from api.utils.schedule import get_exam_schedule_errors, validate_exam_schedule


class PublishExamScheduleTests(TestCase):
    def setUp(self):
        self.client = APIClient()

        # Admin User & Institution
        self.admin_user = User.objects.create_user(
            username="admin@publish.edu",
            email="admin@publish.edu",
            password="Password123!",
        )
        from admins.models import AdminProfile
        AdminProfile.objects.create(user=self.admin_user)
        self.institution = AdminInstitution.objects.create(
            admin=self.admin_user,
            institution_name="Publish Test Inst",
            institution_code="INST-PUB",
            status=AdminInstitution.STATUS_ACTIVE,
        )

        # Faculty User
        self.faculty = User.objects.create_user(
            username="prof_publish",
            email="prof@publish.edu",
            password="Password123!",
            first_name="Grace",
            last_name="Hopper",
        )
        from faculty.models import FacultyProfile
        FacultyProfile.objects.create(
            user=self.faculty,
            institution=self.institution,
            department="Computer Science",
        )

        self.client.force_authenticate(user=self.faculty)

    def _create_draft_exam(self, starts_at=None, ends_at=None, is_reviewed=True):
        exam = Exam.objects.create(
            institution=self.institution,
            title="Cloud Computing Unit 1",
            created_by=self.faculty,
            department="Computer Science",
            duration_minutes=60,
            total_marks=20,
            target_total_marks=20,
            status=Exam.Status.DRAFT,
            is_reviewed=is_reviewed,
            starts_at=starts_at,
            ends_at=ends_at,
            display_timezone="Asia/Kolkata",
        )
        Question.objects.create(
            institution=self.institution,
            exam=exam,
            order=1,
            text="Explain MapReduce model.",
            question_type="short_answer",
            correct_answer="Model for distributed data processing",
            marks=20.0,
            created_by=self.faculty,
        )
        return exam

    def test_publish_without_schedule_fails_with_structured_errors(self):
        exam = self._create_draft_exam(starts_at=None, ends_at=None)

        url = f"/api/faculty/exams/{exam.id}/publish/"
        response = self.client.post(url, {})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data.get("code"), "SCHEDULE_REQUIRED")
        self.assertIn("errors", response.data)

        fields = [err["field"] for err in response.data["errors"]]
        self.assertIn("starts_at", fields)
        self.assertIn("ends_at", fields)

        # Ensure exam remains in draft
        exam.refresh_from_db()
        self.assertEqual(exam.status, Exam.Status.DRAFT)
        self.assertFalse(exam.is_immutable)

    def test_publish_with_invalid_schedule_window_fails(self):
        exam = self._create_draft_exam(starts_at=None, ends_at=None)
        now = timezone.now()

        # Send invalid schedule where ends_at < starts_at
        payload = {
            "starts_at": (now + timedelta(hours=2)).isoformat(),
            "ends_at": (now + timedelta(hours=1)).isoformat(),
        }
        url = f"/api/faculty/exams/{exam.id}/publish/"
        response = self.client.post(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data.get("code"), "INVALID_SCHEDULE")

    def test_publish_with_window_smaller_than_duration_fails(self):
        exam = self._create_draft_exam(starts_at=None, ends_at=None)
        now = timezone.now()

        # Duration is 60m, window is 30m
        payload = {
            "starts_at": (now + timedelta(hours=1)).isoformat(),
            "ends_at": (now + timedelta(hours=1, minutes=30)).isoformat(),
        }
        url = f"/api/faculty/exams/{exam.id}/publish/"
        response = self.client.post(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data.get("code"), "INVALID_SCHEDULE")
        self.assertIn("at least as long as the exam duration", response.data.get("detail", ""))

    def test_publish_with_inline_schedule_succeeds(self):
        exam = self._create_draft_exam(starts_at=None, ends_at=None)
        now = timezone.now()

        future_start = (now + timedelta(hours=1)).isoformat()
        future_end = (now + timedelta(hours=3)).isoformat()

        payload = {
            "starts_at": future_start,
            "ends_at": future_end,
            "display_timezone": "Asia/Kolkata",
        }
        url = f"/api/faculty/exams/{exam.id}/publish/"
        response = self.client.post(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data.get("status"), Exam.Status.PUBLISHED)

        exam.refresh_from_db()
        self.assertEqual(exam.status, Exam.Status.PUBLISHED)
        self.assertTrue(exam.is_immutable)
        self.assertIsNotNone(exam.starts_at)
        self.assertIsNotNone(exam.ends_at)
        self.assertEqual(exam.display_timezone, "Asia/Kolkata")

    def test_publish_is_idempotent(self):
        now = timezone.now()
        exam = self._create_draft_exam(
            starts_at=now + timedelta(hours=1),
            ends_at=now + timedelta(hours=3),
        )

        url = f"/api/faculty/exams/{exam.id}/publish/"

        # First publish
        res1 = self.client.post(url, {})
        self.assertEqual(res1.status_code, status.HTTP_200_OK)
        self.assertFalse(res1.data.get("already_published", False))

        # Second publish (should not fail with 400 or crash)
        res2 = self.client.post(url, {})
        self.assertEqual(res2.status_code, status.HTTP_200_OK)
        self.assertTrue(res2.data.get("already_published"))

    def test_get_exam_schedule_errors_utility(self):
        now = timezone.now()

        # Both missing
        errors = get_exam_schedule_errors(None, None, 60, is_publishing=True)
        self.assertIn("starts_at", errors)
        self.assertIn("ends_at", errors)

        # Only ends_at missing
        errors = get_exam_schedule_errors(now, None, 60, is_publishing=True)
        self.assertNotIn("starts_at", errors)
        self.assertIn("ends_at", errors)

        # Valid schedule
        errors = get_exam_schedule_errors(
            now + timedelta(hours=1),
            now + timedelta(hours=3),
            60,
            is_publishing=True,
        )
        self.assertEqual(len(errors), 0)

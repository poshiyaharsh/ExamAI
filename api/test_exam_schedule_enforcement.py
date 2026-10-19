from datetime import timedelta
from decimal import Decimal
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status

from api.models import (
    AdminInstitution,
    Exam,
    Question,
    StudentAttempt,
    User,
)
from api.utils.schedule import (
    compute_attempt_expiry,
    finalize_overdue_attempts,
    format_exam_schedule_display,
    get_exam_schedule_phase,
    normalize_to_utc,
    validate_exam_schedule,
)


class ExamScheduleEnforcementTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin_user = User.objects.create_user(
            username="admin@sched.edu",
            email="admin@sched.edu",
            password="Password123!",
        )
        from admins.models import AdminProfile
        AdminProfile.objects.create(user=self.admin_user)
        self.institution = AdminInstitution.objects.create(
            admin=self.admin_user,
            institution_name="Schedule Test Inst",
            institution_code="INST-SCHED",
            status=AdminInstitution.STATUS_ACTIVE,
        )

        # Faculty user
        self.faculty = User.objects.create_user(
            username="prof_schedule",
            email="prof@sched.edu",
            password="Password123!",
            first_name="Alan",
            last_name="Turing",
        )
        from faculty.models import FacultyProfile
        FacultyProfile.objects.create(
            user=self.faculty,
            institution=self.institution,
            department="Computer Science",
        )

        # Student user
        self.student = User.objects.create_user(
            username="student_schedule",
            email="student@sched.edu",
            password="Password123!",
            first_name="Ada",
            last_name="Lovelace",
        )
        from students.models import StudentProfile
        StudentProfile.objects.create(
            user=self.student,
            institution=self.institution,
            student_id="CS-2026-001",
            department="Computer Science",
        )

    def test_schedule_validation_rules(self):
        now = timezone.now()

        # 1. Missing dates when publishing -> Invalid
        ok, err = validate_exam_schedule(None, None, 60, is_publishing=True, raise_exception=False)
        self.assertFalse(ok)
        self.assertIn("required", err.lower())

        # 2. End before start -> Invalid
        ok, err = validate_exam_schedule(now + timedelta(hours=2), now + timedelta(hours=1), 60, is_publishing=True, raise_exception=False)
        self.assertFalse(ok)
        self.assertIn("after", err.lower())

        # 3. Window less than duration -> Invalid
        ok, err = validate_exam_schedule(now + timedelta(hours=1), now + timedelta(hours=1, minutes=30), 60, is_publishing=True, raise_exception=False)
        self.assertFalse(ok)
        self.assertIn("at least", err.lower())

        # 4. Start in the past (> 5 min) when publishing -> Invalid
        past_start = now - timedelta(minutes=10)
        ok, err = validate_exam_schedule(past_start, now + timedelta(hours=2), 60, is_publishing=True, raise_exception=False)
        self.assertFalse(ok)
        self.assertIn("past", err.lower())

        # 5. Start within 5 min grace period -> Valid
        grace_start = now - timedelta(minutes=2)
        ok, err = validate_exam_schedule(grace_start, now + timedelta(hours=2), 60, is_publishing=True, raise_exception=False)
        self.assertTrue(ok)

        # 6. Valid future schedule -> Valid
        future_start = now + timedelta(hours=1)
        future_end = now + timedelta(hours=3)
        ok, err = validate_exam_schedule(future_start, future_end, 60, is_publishing=True, raise_exception=False)
        self.assertTrue(ok)
        self.assertIsNone(err)

    def test_get_exam_schedule_phase_and_display(self):
        now = timezone.now()
        exam_upcoming = Exam(
            starts_at=now + timedelta(hours=2),
            ends_at=now + timedelta(hours=5),
            duration_minutes=60,
            status=Exam.Status.PUBLISHED,
            display_timezone="Asia/Kolkata",
        )
        self.assertEqual(get_exam_schedule_phase(exam_upcoming, now), "upcoming")

        exam_live = Exam(
            starts_at=now - timedelta(minutes=15),
            ends_at=now + timedelta(hours=2),
            duration_minutes=60,
            status=Exam.Status.PUBLISHED,
            display_timezone="Asia/Kolkata",
        )
        self.assertEqual(get_exam_schedule_phase(exam_live, now), "live")

        exam_ended = Exam(
            starts_at=now - timedelta(hours=4),
            ends_at=now - timedelta(minutes=10),
            duration_minutes=60,
            status=Exam.Status.PUBLISHED,
            display_timezone="Asia/Kolkata",
        )
        self.assertEqual(get_exam_schedule_phase(exam_ended, now), "ended")

        display = format_exam_schedule_display(exam_live)
        self.assertEqual(display["timezone"], "Asia/Kolkata")
        self.assertEqual(display["phase"], "live")
        self.assertIn("Opens", display["summary"])

    def test_compute_attempt_expiry(self):
        now = timezone.now()

        # Regular case: started at now, duration 60m, window closes in 180m -> expires at now + 60m
        exam_wide = Exam(
            starts_at=now - timedelta(minutes=10),
            ends_at=now + timedelta(minutes=180),
            duration_minutes=60,
        )
        expiry = compute_attempt_expiry(exam_wide, started_at=now, now=now)
        self.assertEqual(expiry, now + timedelta(minutes=60))

        # Window capped case: started at now, duration 60m, window closes in 25m -> expires at now + 25m
        exam_narrow = Exam(
            starts_at=now - timedelta(minutes=35),
            ends_at=now + timedelta(minutes=25),
            duration_minutes=60,
        )
        expiry = compute_attempt_expiry(exam_narrow, started_at=now, now=now)
        self.assertEqual(expiry, exam_narrow.ends_at)

    def _create_published_exam(self, starts_at, ends_at, duration_minutes=30):
        exam = Exam.objects.create(
            institution=self.institution,
            title="Algorithm Assessment",
            created_by=self.faculty,
            department="Computer Science",
            duration_minutes=duration_minutes,
            total_marks=10,
            target_total_marks=10,
            status=Exam.Status.PUBLISHED,
            is_reviewed=True,
            is_immutable=True,
            starts_at=starts_at,
            ends_at=ends_at,
            display_timezone="Asia/Kolkata",
        )
        Question.objects.create(
            institution=self.institution,
            exam=exam,
            order=1,
            text="What is the worst-case complexity of Quicksort?",
            question_type="mcq",
            options=["O(n log n)", "O(n^2)", "O(n)", "O(1)"],
            correct_answer="O(n^2)",
            marks=10.0,
            created_by=self.faculty,
        )
        return exam

    def test_student_cannot_start_before_starts_at(self):
        now = timezone.now()
        future_exam = self._create_published_exam(
            starts_at=now + timedelta(hours=1),
            ends_at=now + timedelta(hours=3),
        )

        self.client.force_authenticate(user=self.student)
        url = f"/api/student/exams/{future_exam.id}/start/"
        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data.get("error_code"), "EXAM_NOT_STARTED")
        self.assertIn("has not started yet", response.data.get("detail", ""))
        self.assertIn("server_now", response.data)

    def test_student_cannot_start_after_ends_at(self):
        now = timezone.now()
        past_exam = self._create_published_exam(
            starts_at=now - timedelta(hours=3),
            ends_at=now - timedelta(minutes=5),
        )

        self.client.force_authenticate(user=self.student)
        url = f"/api/student/exams/{past_exam.id}/start/"
        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data.get("error_code"), "EXAM_ENDED")
        self.assertIn("closed", response.data.get("detail", "").lower())
        self.assertIn("server_now", response.data)

    def test_student_can_start_within_window(self):
        now = timezone.now()
        live_exam = self._create_published_exam(
            starts_at=now - timedelta(minutes=10),
            ends_at=now + timedelta(hours=2),
            duration_minutes=30,
        )

        self.client.force_authenticate(user=self.student)
        url = f"/api/student/exams/{live_exam.id}/start/"
        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("attempt_id", response.data)
        self.assertIn("server_now", response.data)
        self.assertFalse(response.data["is_window_capped"])

        attempt = StudentAttempt.objects.get(id=response.data["attempt_id"])
        self.assertEqual(attempt.status, StudentAttempt.Status.IN_PROGRESS)
        self.assertIsNotNone(attempt.expires_at)

    def test_window_capped_attempt_and_save_answer_expiry(self):
        now = timezone.now()
        # Window ends in only 15 minutes, but exam duration is 30 minutes
        capped_exam = self._create_published_exam(
            starts_at=now - timedelta(minutes=45),
            ends_at=now + timedelta(minutes=15),
            duration_minutes=30,
        )

        self.client.force_authenticate(user=self.student)
        url = f"/api/student/exams/{capped_exam.id}/start/"
        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["is_window_capped"])
        attempt_id = response.data["attempt_id"]

        # Fast-forward attempt expires_at to simulate expiry
        attempt = StudentAttempt.objects.get(id=attempt_id)
        attempt.expires_at = now - timedelta(seconds=10)
        attempt.save(update_fields=['expires_at'])

        # Attempt to save answer after expiry
        save_url = f"/api/student/attempts/{attempt_id}/save/"
        save_res = self.client.post(save_url, {
            'question_id': capped_exam.questions.first().id,
            'answer_text': 'O(n^2)',
        })
        self.assertEqual(save_res.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(save_res.data.get("error_code"), "EXAM_EXPIRED")

        # Verify attempt auto-submitted
        attempt.refresh_from_db()
        self.assertEqual(attempt.status, StudentAttempt.Status.AUTO_SUBMITTED)
        self.assertIn(attempt.submit_reason, ["time_up", "window_closed"])

    def test_finalize_overdue_attempts_background_job(self):
        now = timezone.now()
        exam = self._create_published_exam(
            starts_at=now - timedelta(hours=2),
            ends_at=now - timedelta(minutes=10),
            duration_minutes=30,
        )

        # Create an abandoned in-progress attempt whose window closed
        attempt = StudentAttempt.objects.create(
            exam=exam,
            institution=self.institution,
            student=self.student,
            attempt_number=1,
            status=StudentAttempt.Status.IN_PROGRESS,
            started_at=now - timedelta(hours=1),
            expires_at=exam.ends_at,
        )

        finalized = finalize_overdue_attempts(now=now)
        self.assertEqual(finalized, 1)

        attempt.refresh_from_db()
        self.assertEqual(attempt.status, StudentAttempt.Status.AUTO_SUBMITTED)
        self.assertEqual(attempt.submit_reason, "window_closed")
        self.assertIsNotNone(attempt.total_score)

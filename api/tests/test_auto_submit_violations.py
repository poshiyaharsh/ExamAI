import json
from datetime import timedelta
from unittest.mock import patch
import uuid

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from admins.models import AdminDepartment, AdminInstitution, AdminProfile
from api.constants import MAX_WARNINGS
from api.models import AttemptEvent, Exam, Question, StudentAnswer, StudentAttempt
from api.utils.schedule import finalize_overdue_attempts
from faculty.models import FacultyProfile
from students.models import StudentProfile

User = get_user_model()


def jwt_token(user, role, institution):
    refresh = RefreshToken.for_user(user)
    refresh["role"] = role
    refresh["institution_id"] = institution.id if institution else None
    access = refresh.access_token
    access["role"] = role
    access["institution_id"] = institution.id if institution else None
    return str(access)


class AutoSubmitViolationsTests(TestCase):
    def setUp(self):
        self.client = APIClient()

        # Institution and Admin
        self.admin_user = User.objects.create_user(
            username="admin@test.edu",
            email="admin@test.edu",
            password="AdminPassword123!",
        )
        self.admin_profile = AdminProfile.objects.create(user=self.admin_user)
        self.institution = AdminInstitution.objects.create(
            admin=self.admin_user,
            institution_name="Test University",
            institution_code="TEST_UNI",
            status=AdminInstitution.STATUS_ACTIVE,
        )

        self.dept = AdminDepartment.objects.create(
            institution=self.institution,
            department_name="Computer Science",
        )

        # Faculty
        self.faculty_user = User.objects.create_user(
            username="faculty@test.edu",
            email="faculty@test.edu",
            password="password123",
            first_name="Alan",
            last_name="Turing",
        )
        self.faculty_profile = FacultyProfile.objects.create(
            user=self.faculty_user,
            institution=self.institution,
            department="Computer Science",
            designation="Professor",
        )
        self.faculty_token = jwt_token(self.faculty_user, "faculty", self.institution)

        # Student
        self.student = User.objects.create_user(
            username="student@test.edu",
            email="student@test.edu",
            password="password123",
            first_name="Grace",
            last_name="Hopper",
        )
        self.student_profile = StudentProfile.objects.create(
            user=self.student,
            institution=self.institution,
            department="Computer Science",
            student_id="CS-GRACE",
        )
        self.student_token = jwt_token(self.student, "student", self.institution)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.student_token}")

        # Exam with default MAX_WARNINGS (1 warning allowed, 2nd auto-submits)
        self.exam = Exam.objects.create(
            institution=self.institution,
            title="Operating Systems Midterm",
            created_by=self.faculty_user,
            department="Computer Science",
            duration_minutes=60,
            total_marks=20,
            status=Exam.Status.PUBLISHED,
            max_warnings=MAX_WARNINGS,
            allow_retakes=False,
            starts_at=timezone.now() - timedelta(hours=1),
            ends_at=timezone.now() + timedelta(hours=5),
        )

        # Questions: 1 MCQ and 1 Short Answer
        self.q_mcq = Question.objects.create(
            institution=self.institution,
            exam=self.exam,
            order=1,
            question_type=Question.QuestionType.MCQ_SINGLE,
            difficulty=Question.Difficulty.EASY,
            text="What is a process?",
            options=["A program in execution", "A disk sector", "A compiler", "An OS kernel"],
            correct_answer="A program in execution",
            marks=10.0,
        )
        self.q_short = Question.objects.create(
            institution=self.institution,
            exam=self.exam,
            order=2,
            question_type=Question.QuestionType.SHORT_ANSWER,
            difficulty=Question.Difficulty.MEDIUM,
            text="Explain virtual memory in one sentence.",
            model_answer="Virtual memory provides an illusion of a large contiguous address space.",
            marks=10.0,
        )

    def test_violation_1_returns_final_warning_and_violation_2_auto_submits(self):
        """Violation 1 issues the final warning; Violation 2 immediately auto-submits."""
        # 1. Start the exam
        start_res = self.client.post(f"/api/student/exams/{self.exam.id}/start/")
        self.assertEqual(start_res.status_code, status.HTTP_200_OK)
        attempt_id = start_res.json()["attempt_id"]

        attempt = StudentAttempt.objects.get(id=attempt_id)
        self.assertEqual(attempt.status, StudentAttempt.Status.IN_PROGRESS)
        self.assertEqual(attempt.violation_count, 0)

        # 2. Violation 1: Tab hidden -> returns final warning (warnings_left: 0)
        v1_res = self.client.post(
            f"/api/student/attempts/{attempt_id}/violation/",
            data={
                "event_type": AttemptEvent.EventType.TAB_HIDDEN,
                "event_id": str(uuid.uuid4()),
                "metadata": {"details": "Left window"},
            },
            format="json",
        )
        self.assertEqual(v1_res.status_code, status.HTTP_200_OK)
        v1_data = v1_res.json()
        self.assertEqual(v1_data["violation_count"], 1)
        self.assertEqual(v1_data["warnings_left"], 0)
        self.assertFalse(v1_data["auto_submitted"])
        self.assertIn("Final warning", v1_data["message"])

        attempt.refresh_from_db()
        self.assertEqual(attempt.status, StudentAttempt.Status.IN_PROGRESS)
        self.assertEqual(attempt.violation_count, 1)

        # Sleep past the 1-second debounce window to represent a distinct 2nd incident
        import time
        time.sleep(1.05)

        # 3. Violation 2: Fullscreen exit -> 2nd violation exceeds max_warnings (1) -> AUTO-SUBMITS
        v2_res = self.client.post(
            f"/api/student/attempts/{attempt_id}/violation/",
            data={
                "event_type": AttemptEvent.EventType.FULLSCREEN_EXIT,
                "event_id": str(uuid.uuid4()),
                "answers": [
                    {
                        "question_id": self.q_mcq.id,
                        "answer_text": "A program in execution",
                    }
                ],
            },
            format="json",
        )
        self.assertEqual(v2_res.status_code, status.HTTP_200_OK)
        v2_data = v2_res.json()
        self.assertEqual(v2_data["violation_count"], 2)
        self.assertTrue(v2_data["auto_submitted"])
        self.assertEqual(v2_data["warnings_left"], 0)
        self.assertEqual(v2_data["status"], StudentAttempt.Status.AUTO_SUBMITTED)
        self.assertEqual(v2_data["submit_reason"], "violations")
        self.assertEqual(v2_data["redirect_url"], f"/student/results/{attempt_id}")

        # Check DB state
        attempt.refresh_from_db()
        self.assertEqual(attempt.status, StudentAttempt.Status.AUTO_SUBMITTED)
        self.assertEqual(attempt.submit_reason, "violations")
        self.assertIsNotNone(attempt.submitted_at)

        # Verify buffered answers were saved and graded
        saved_ans = StudentAnswer.objects.get(attempt=attempt, question=self.q_mcq)
        self.assertEqual(saved_ans.answer_text, "A program in execution")
        self.assertTrue(saved_ans.is_correct)
        self.assertEqual(saved_ans.score_awarded, 10.0)

    def test_idempotent_event_id_prevents_duplicate_increments(self):
        """Retrying the same event_id must not double count or trigger premature auto-submit."""
        start_res = self.client.post(f"/api/student/exams/{self.exam.id}/start/")
        attempt_id = start_res.json()["attempt_id"]

        event_id = str(uuid.uuid4())
        # First attempt
        res1 = self.client.post(
            f"/api/student/attempts/{attempt_id}/violation/",
            data={"event_type": AttemptEvent.EventType.TAB_HIDDEN, "event_id": event_id},
            format="json",
        )
        self.assertEqual(res1.status_code, status.HTTP_200_OK)
        self.assertEqual(res1.json()["violation_count"], 1)
        self.assertFalse(res1.json()["auto_submitted"])

        # Immediate network retry with SAME event_id
        res2 = self.client.post(
            f"/api/student/attempts/{attempt_id}/violation/",
            data={"event_type": AttemptEvent.EventType.TAB_HIDDEN, "event_id": event_id},
            format="json",
        )
        self.assertEqual(res2.status_code, status.HTTP_200_OK)
        self.assertEqual(res2.json()["violation_count"], 1)
        self.assertTrue(res2.json()["already_recorded"])
        self.assertFalse(res2.json()["auto_submitted"])

        attempt = StudentAttempt.objects.get(id=attempt_id)
        self.assertEqual(attempt.violation_count, 1)

    def test_one_combined_fullscreen_exit_and_blur_counts_once(self):
        """Fullscreen exit and window blur firing within 1 second for one user action count as 1 violation."""
        start_res = self.client.post(f"/api/student/exams/{self.exam.id}/start/")
        attempt_id = start_res.json()["attempt_id"]

        # Action: student exits fullscreen
        res_fs = self.client.post(
            f"/api/student/attempts/{attempt_id}/violation/",
            data={"event_type": AttemptEvent.EventType.FULLSCREEN_EXIT, "event_id": str(uuid.uuid4())},
            format="json",
        )
        self.assertEqual(res_fs.status_code, status.HTTP_200_OK)
        self.assertEqual(res_fs.json()["violation_count"], 1)
        self.assertFalse(res_fs.json()["auto_submitted"])

        # Immediately (same action), window blur fires
        res_blur = self.client.post(
            f"/api/student/attempts/{attempt_id}/violation/",
            data={"event_type": AttemptEvent.EventType.WINDOW_BLUR, "event_id": str(uuid.uuid4())},
            format="json",
        )
        self.assertEqual(res_blur.status_code, status.HTTP_200_OK)
        blur_data = res_blur.json()
        self.assertTrue(blur_data.get("debounced"))
        self.assertEqual(blur_data["violation_count"], 1)
        self.assertFalse(blur_data["auto_submitted"])

        attempt = StudentAttempt.objects.get(id=attempt_id)
        self.assertEqual(attempt.violation_count, 1)
        self.assertEqual(attempt.status, StudentAttempt.Status.IN_PROGRESS)

    def test_two_violations_finalize_once(self):
        """Attempt transitions to AUTO_SUBMITTED on violation 2 and subsequent calls are idempotent."""
        start_res = self.client.post(f"/api/student/exams/{self.exam.id}/start/")
        attempt_id = start_res.json()["attempt_id"]

        # Violation 1
        self.client.post(
            f"/api/student/attempts/{attempt_id}/violation/",
            data={"event_type": AttemptEvent.EventType.FULLSCREEN_EXIT, "event_id": str(uuid.uuid4())},
            format="json",
        )

        # Violation 2: Finalizes attempt
        res2 = self.client.post(
            f"/api/student/attempts/{attempt_id}/violation/",
            data={"event_type": AttemptEvent.EventType.FULLSCREEN_EXIT, "event_id": str(uuid.uuid4())},
            format="json",
        )
        self.assertEqual(res2.status_code, status.HTTP_200_OK)
        self.assertTrue(res2.json()["auto_submitted"])

        # Third call: Already submitted
        res3 = self.client.post(
            f"/api/student/attempts/{attempt_id}/violation/",
            data={"event_type": AttemptEvent.EventType.FULLSCREEN_EXIT, "event_id": str(uuid.uuid4())},
            format="json",
        )
        self.assertEqual(res3.status_code, status.HTTP_200_OK)
        self.assertTrue(res3.json()["already_submitted"])
        self.assertTrue(res3.json()["auto_submitted"])

        attempt = StudentAttempt.objects.get(id=attempt_id)
        self.assertEqual(attempt.status, StudentAttempt.Status.AUTO_SUBMITTED)
        self.assertEqual(attempt.submit_reason, "violations")

    def test_finalize_error_leaves_needs_finalize_and_scheduler_fixes_it(self):
        """If scoring fails during finalize, needs_finalize is flagged and background scheduler completes it."""
        start_res = self.client.post(f"/api/student/exams/{self.exam.id}/start/")
        attempt_id = start_res.json()["attempt_id"]

        # Violation 1
        self.client.post(
            f"/api/student/attempts/{attempt_id}/violation/",
            data={"event_type": AttemptEvent.EventType.FULLSCREEN_EXIT, "event_id": str(uuid.uuid4())},
            format="json",
        )

        # Mock calculate_and_save_attempt_score raising an exception on violation 2
        with patch("api.student_exam.calculate_and_save_attempt_score", side_effect=RuntimeError("Grading engine timeout")):
            v2_res = self.client.post(
                f"/api/student/attempts/{attempt_id}/violation/",
                data={
                    "event_type": AttemptEvent.EventType.FULLSCREEN_EXIT,
                    "event_id": str(uuid.uuid4()),
                    "answers": [{"question_id": self.q_mcq.id, "answer_text": "A program in execution"}],
                },
                format="json",
            )
            self.assertEqual(v2_res.status_code, status.HTTP_200_OK)
            self.assertTrue(v2_res.json()["auto_submitted"])

        # Attempt is transitioned to AUTO_SUBMITTED (never left in progress) but needs_finalize is True
        attempt = StudentAttempt.objects.get(id=attempt_id)
        self.assertEqual(attempt.status, StudentAttempt.Status.AUTO_SUBMITTED)
        self.assertEqual(attempt.submit_reason, "violations")
        self.assertTrue(attempt.needs_finalize)

        # Now background scheduler runs
        finalized_count = finalize_overdue_attempts()
        self.assertEqual(finalized_count, 1)

        # Verify attempt has been scored and needs_finalize is cleared
        attempt.refresh_from_db()
        self.assertFalse(attempt.needs_finalize)
        self.assertEqual(attempt.status, StudentAttempt.Status.AUTO_SUBMITTED)
        saved_ans = StudentAnswer.objects.get(attempt=attempt, question=self.q_mcq)
        self.assertEqual(saved_ans.score_awarded, 10.0)

    def test_post_submission_behavior_on_all_endpoints(self):
        """After auto-submit, violation, save-answer, heartbeat, and start endpoints handle cleanly."""
        start_res = self.client.post(f"/api/student/exams/{self.exam.id}/start/")
        attempt_id = start_res.json()["attempt_id"]

        # 2 violations to auto-submit the exam
        for _ in range(2):
            self.client.post(
                f"/api/student/attempts/{attempt_id}/violation/",
                data={"event_type": AttemptEvent.EventType.FULLSCREEN_EXIT, "event_id": str(uuid.uuid4())},
                format="json",
            )

        attempt = StudentAttempt.objects.get(id=attempt_id)
        self.assertEqual(attempt.status, StudentAttempt.Status.AUTO_SUBMITTED)

        # 1. Save answer on auto-submitted attempt: returns HTTP 400 with already_submitted
        save_res = self.client.post(
            f"/api/student/attempts/{attempt_id}/save/",
            data={"question_id": self.q_mcq.id, "answer_text": "Option B"},
            format="json",
        )
        self.assertEqual(save_res.status_code, status.HTTP_400_BAD_REQUEST)
        save_data = save_res.json()
        self.assertTrue(save_data.get("already_submitted"))
        self.assertEqual(save_data.get("redirect_url"), f"/student/results/{attempt_id}")

        # 2. Heartbeat on auto-submitted attempt: returns auto_submitted: True, already_submitted: True
        hb_res = self.client.post(
            f"/api/student/attempts/{attempt_id}/heartbeat/",
            format="json",
        )
        self.assertEqual(hb_res.status_code, status.HTTP_200_OK)
        hb_data = hb_res.json()
        self.assertTrue(hb_data.get("auto_submitted"))
        self.assertTrue(hb_data.get("already_submitted"))
        self.assertEqual(hb_data.get("redirect_url"), f"/student/results/{attempt_id}")

        # 3. Violation on auto-submitted attempt: returns already_submitted: True
        v_res = self.client.post(
            f"/api/student/attempts/{attempt_id}/violation/",
            data={"event_type": AttemptEvent.EventType.TAB_HIDDEN, "event_id": str(uuid.uuid4())},
            format="json",
        )
        self.assertEqual(v_res.status_code, status.HTTP_200_OK)
        v_data = v_res.json()
        self.assertTrue(v_data.get("already_submitted"))
        self.assertTrue(v_data.get("auto_submitted"))
        self.assertEqual(v_data.get("redirect_url"), f"/student/results/{attempt_id}")

        # 4. Start / Resume on auto-submitted attempt: returns ALREADY_SUBMITTED error with redirect_url
        start_again_res = self.client.post(f"/api/student/exams/{self.exam.id}/start/")
        self.assertEqual(start_again_res.status_code, status.HTTP_400_BAD_REQUEST)
        st_data = start_again_res.json()
        self.assertTrue(st_data.get("already_submitted"))
        self.assertEqual(st_data.get("redirect_url"), f"/student/results/{attempt_id}")

    def test_refresh_page_maintains_violation_count(self):
        """Reloading or resuming the exam attempt does not reset the violation count."""
        start_res = self.client.post(f"/api/student/exams/{self.exam.id}/start/")
        attempt_id = start_res.json()["attempt_id"]

        # 1 violation occurs
        v1 = self.client.post(
            f"/api/student/attempts/{attempt_id}/violation/",
            data={"event_type": AttemptEvent.EventType.FULLSCREEN_EXIT, "event_id": str(uuid.uuid4())},
            format="json",
        )
        self.assertEqual(v1.json()["violation_count"], 1)

        attempt = StudentAttempt.objects.get(id=attempt_id)
        self.assertEqual(attempt.violation_count, 1)

        # Student refreshes browser (hits start/resume endpoint)
        resume_res = self.client.post(f"/api/student/exams/{self.exam.id}/start/")
        self.assertEqual(resume_res.status_code, status.HTTP_200_OK)
        resume_data = resume_res.json()
        self.assertEqual(resume_data["attempt_id"], attempt_id)
        self.assertEqual(resume_data["violation_count"], 1)

        # 2nd violation -> triggers auto submit
        v2 = self.client.post(
            f"/api/student/attempts/{attempt_id}/violation/",
            data={"event_type": AttemptEvent.EventType.FULLSCREEN_EXIT, "event_id": str(uuid.uuid4())},
            format="json",
        )
        self.assertEqual(v2.json()["violation_count"], 2)
        self.assertTrue(v2.json()["auto_submitted"])

    def test_faculty_can_open_submitted_attempt(self):
        """Faculty can open and review the attempt auto-submitted due to violations."""
        start_res = self.client.post(f"/api/student/exams/{self.exam.id}/start/")
        attempt_id = start_res.json()["attempt_id"]

        # Violations 1 and 2
        for _ in range(2):
            self.client.post(
                f"/api/student/attempts/{attempt_id}/violation/",
                data={"event_type": AttemptEvent.EventType.FULLSCREEN_EXIT, "event_id": str(uuid.uuid4())},
                format="json",
            )

        # Switch credentials to Faculty
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.faculty_token}")
        review_res = self.client.get(f"/api/faculty/attempts/{attempt_id}/")
        self.assertEqual(review_res.status_code, status.HTTP_200_OK)
        review_data = review_res.json()
        self.assertEqual(review_data["attempt_id"], attempt_id)
        self.assertEqual(review_data["status"], StudentAttempt.Status.AUTO_SUBMITTED)
        self.assertEqual(review_data["submit_reason"], "violations")

    def test_backstop_auto_submits_if_violation_count_exceeded_on_heartbeat_or_save(self):
        """If an attempt somehow has violation_count > max_warnings while IN_PROGRESS, backstop finalizes it."""
        start_res = self.client.post(f"/api/student/exams/{self.exam.id}/start/")
        attempt_id = start_res.json()["attempt_id"]

        # Simulate out-of-band violation count update
        StudentAttempt.objects.filter(id=attempt_id).update(violation_count=2)

        # Heartbeat hits backstop
        hb_res = self.client.post(f"/api/student/attempts/{attempt_id}/heartbeat/")
        self.assertEqual(hb_res.status_code, status.HTTP_200_OK)
        hb_data = hb_res.json()
        self.assertTrue(hb_data.get("auto_submitted"))
        self.assertEqual(hb_data.get("submit_reason"), "violations")

        attempt = StudentAttempt.objects.get(id=attempt_id)
        self.assertEqual(attempt.status, StudentAttempt.Status.AUTO_SUBMITTED)
        self.assertEqual(attempt.submit_reason, "violations")

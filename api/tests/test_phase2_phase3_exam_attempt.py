import json
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from admins.models import AdminDepartment, AdminInstitution, AdminProfile
from api.models import AttemptEvent, Exam, Question, StudentAnswer, StudentAttempt
from students.models import StudentProfile
from faculty.models import FacultyProfile

User = get_user_model()


def jwt_token(user, role, institution):
    refresh = RefreshToken.for_user(user)
    refresh['role'] = role
    refresh['institution_id'] = institution.id if institution else None
    access = refresh.access_token
    access['role'] = role
    access['institution_id'] = institution.id if institution else None
    return str(access)


class ExamAttemptSecurityAndShuffleTests(TestCase):
    def setUp(self):
        self.client = APIClient()

        # Admin user
        self.admin_user = User.objects.create_user(
            username="admin@tech.edu",
            email="admin@tech.edu",
            password="AdminPassword123!",
        )
        self.admin_profile = AdminProfile.objects.create(user=self.admin_user)
        self.institution = AdminInstitution.objects.create(
            admin=self.admin_user,
            institution_name="Tech University",
            institution_code="TECH_UNI",
            status=AdminInstitution.STATUS_ACTIVE,
        )

        self.dept_cs = AdminDepartment.objects.create(
            institution=self.institution,
            department_name="Computer Science",
        )
        self.dept_me = AdminDepartment.objects.create(
            institution=self.institution,
            department_name="Mechanical Engineering",
        )

        # Faculty user
        self.faculty_user = User.objects.create_user(
            username="faculty@tech.edu",
            email="faculty@tech.edu",
            password="password123",
            first_name="Prof",
            last_name="Turing",
        )
        self.faculty_profile = FacultyProfile.objects.create(
            user=self.faculty_user,
            institution=self.institution,
            department="Computer Science",
            designation="Professor",
        )

        # Student user 1 (Computer Science)
        self.student1 = User.objects.create_user(
            username="student1@tech.edu",
            email="student1@tech.edu",
            password="password123",
            first_name="Alice",
            last_name="Smith",
        )
        self.student1_profile = StudentProfile.objects.create(
            user=self.student1,
            institution=self.institution,
            department="Computer Science",
            student_id="CS101",
        )
        self.token_student1 = jwt_token(self.student1, "student", self.institution)

        # Student user 2 (Computer Science)
        self.student2 = User.objects.create_user(
            username="student2@tech.edu",
            email="student2@tech.edu",
            password="password123",
            first_name="Bob",
            last_name="Jones",
        )
        self.student2_profile = StudentProfile.objects.create(
            user=self.student2,
            institution=self.institution,
            department="Computer Science",
            student_id="CS102",
        )
        self.token_student2 = jwt_token(self.student2, "student", self.institution)

        # Student user 3 (Mechanical Engineering - wrong department)
        self.student3 = User.objects.create_user(
            username="student3@tech.edu",
            email="student3@tech.edu",
            password="password123",
            first_name="Charlie",
            last_name="Brown",
        )
        self.student3_profile = StudentProfile.objects.create(
            user=self.student3,
            institution=self.institution,
            department="Mechanical Engineering",
            student_id="ME101",
        )
        self.token_student3 = jwt_token(self.student3, "student", self.institution)

        # Create published exam with 6 questions
        self.exam = Exam.objects.create(
            institution=self.institution,
            title="Data Structures & Algorithms",
            created_by=self.faculty_user,
            department="Computer Science",
            duration_minutes=60,
            total_marks=30,
            status=Exam.Status.PUBLISHED,
            shuffle_questions=True,
            shuffle_options=True,
            max_warnings=1,
            allow_retakes=False,
            starts_at=timezone.now() - timedelta(hours=1),
            ends_at=timezone.now() + timedelta(hours=5),
        )

        self.questions = []
        for i in range(1, 7):
            q = Question.objects.create(
                institution=self.institution,
                exam=self.exam,
                order=i,
                question_type=Question.QuestionType.MCQ_SINGLE,
                difficulty=Question.Difficulty.EASY if i <= 2 else Question.Difficulty.MEDIUM,
                text=f"Question {i}: What is the time complexity of operation {i}?",
                options=[f"O({i})", f"O(log {i})", f"O({i}^2)", f"O(2^{i})"],
                correct_answer=f"O({i})",
                marks=5.0,
            )
            self.questions.append(q)

    def auth_student(self, token):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def test_department_isolation_prevents_wrong_department_student(self):
        """Student from different department cannot start exam."""
        self.auth_student(self.token_student3)
        res = self.client.post(f"/api/student/exams/{self.exam.id}/start/")
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    def test_start_attempt_shuffles_and_persists_order(self):
        """Starting attempt returns sanitized questions and persists order on reload."""
        self.auth_student(self.token_student1)
        res1 = self.client.post(f"/api/student/exams/{self.exam.id}/start/")
        self.assertEqual(res1.status_code, status.HTTP_200_OK)
        data1 = res1.json()

        attempt_id = data1["attempt_id"]
        q_order1 = [q["id"] for q in data1["exam"]["questions"]]
        self.assertEqual(len(q_order1), 6)

        # Check sanitization: no correct_answer or explanation leaked
        for q in data1["exam"]["questions"]:
            self.assertNotIn("correct_answer", q)
            self.assertNotIn("model_answer", q)
            self.assertNotIn("explanation", q)

        # Reloading (calling start again) must return the EXACT same question order
        res2 = self.client.post(f"/api/student/exams/{self.exam.id}/start/")
        self.assertEqual(res2.status_code, status.HTTP_200_OK)
        data2 = res2.json()
        self.assertEqual(data2["attempt_id"], attempt_id)
        q_order2 = [q["id"] for q in data2["exam"]["questions"]]
        self.assertEqual(q_order1, q_order2)

        # Option order must also be identical on reload
        options_order1 = [q["options"] for q in data1["exam"]["questions"]]
        options_order2 = [q["options"] for q in data2["exam"]["questions"]]
        self.assertEqual(options_order1, options_order2)

    def test_save_answer_maps_shuffled_option_to_canonical_correctly(self):
        """Saving shuffled option letter or text maps back to canonical option in DB."""
        self.auth_student(self.token_student1)
        start_res = self.client.post(f"/api/student/exams/{self.exam.id}/start/")
        data = start_res.json()
        attempt_id = data["attempt_id"]
        first_q = data["exam"]["questions"][0]
        qid = first_q["id"]
        displayed_options = first_q["options"]

        # Say student chooses Option "A" (which is displayed_options[0])
        save_res = self.client.post(
            f"/api/student/attempts/{attempt_id}/save/",
            {"question_id": qid, "answer_text": "A"},
            format="json",
        )
        self.assertEqual(save_res.status_code, status.HTTP_200_OK)
        self.assertTrue(save_res.json()["saved"])

        # Check in DB that the answer saved is the canonical text for displayed_options[0]
        ans = StudentAnswer.objects.get(attempt_id=attempt_id, question_id=qid)
        expected_canonical = displayed_options[0]
        self.assertEqual(ans.answer_text, expected_canonical)

    def test_violation_tracking_and_auto_submit_on_exceeding_max_warnings(self):
        """
        Max warnings = 1 (Root rule: 1 warning, 2nd auto-submits).
        Violation 1 returns final warning.
        Violation 2 automatically submits attempt with reason 'violations'.
        """
        self.auth_student(self.token_student1)
        start_res = self.client.post(f"/api/student/exams/{self.exam.id}/start/")
        attempt_id = start_res.json()["attempt_id"]

        # Violation 1: Returns final warning (warnings_left=0)
        res1 = self.client.post(
            f"/api/student/attempts/{attempt_id}/violation/",
            {"event_type": "fullscreen_exit", "metadata": {"attempt": 1}},
            format="json",
        )
        self.assertEqual(res1.status_code, status.HTTP_200_OK)
        self.assertFalse(res1.json()["auto_submitted"])
        self.assertEqual(res1.json()["violation_count"], 1)
        self.assertEqual(res1.json()["warnings_left"], 0)

        # Violation 2: Exceeds limit of 1 -> triggers auto submit
        res2 = self.client.post(
            f"/api/student/attempts/{attempt_id}/violation/",
            {"event_type": "fullscreen_exit", "metadata": {"reason": "exited fullscreen second time"}},
            format="json",
        )
        self.assertEqual(res2.status_code, status.HTTP_200_OK)
        data2 = res2.json()
        self.assertTrue(data2["auto_submitted"])
        self.assertEqual(data2["submit_reason"], "violations")
        self.assertEqual(data2["violation_count"], 2)

        # Verify attempt state in DB
        attempt = StudentAttempt.objects.get(id=attempt_id)
        self.assertEqual(attempt.status, StudentAttempt.Status.AUTO_SUBMITTED)
        self.assertEqual(attempt.submit_reason, "violations")
        self.assertEqual(attempt.violation_count, 2)

        # Verify AttemptEvent logs created
        events = AttemptEvent.objects.filter(attempt=attempt)
        self.assertEqual(events.count(), 2)

    def test_server_deadline_auto_submits_expired_attempt(self):
        """When student attempt passes deadline, save answer or heartbeat auto-submits."""
        self.auth_student(self.token_student1)
        start_res = self.client.post(f"/api/student/exams/{self.exam.id}/start/")
        attempt_id = start_res.json()["attempt_id"]

        # Backdate attempt expiry to simulate time expiring
        attempt = StudentAttempt.objects.get(id=attempt_id)
        attempt.expires_at = timezone.now() - timedelta(minutes=1)
        attempt.save(update_fields=["expires_at"])

        # Heartbeat detects expiry
        hb_res = self.client.post(
            f"/api/student/attempts/{attempt_id}/heartbeat/",
            {"session_token": attempt.active_session_token},
            format="json",
        )
        self.assertEqual(hb_res.status_code, status.HTTP_200_OK)
        self.assertTrue(hb_res.json().get("expired"))

        attempt.refresh_from_db()
        self.assertEqual(attempt.status, StudentAttempt.Status.AUTO_SUBMITTED)
        self.assertEqual(attempt.submit_reason, "time_up")

    def test_concurrent_session_detection_via_heartbeat(self):
        """Heartbeat with old session token returns 409 conflict."""
        self.auth_student(self.token_student1)
        start_res = self.client.post(f"/api/student/exams/{self.exam.id}/start/")
        attempt_id = start_res.json()["attempt_id"]

        # Simulate second session token
        res = self.client.post(
            f"/api/student/attempts/{attempt_id}/heartbeat/",
            {"session_token": "stale_token_123"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_409_CONFLICT)
        self.assertTrue(res.json().get("concurrent_session"))

    def test_retakes_disallowed_when_exam_retakes_false(self):
        """Retakes are rejected if allow_retakes is False."""
        self.auth_student(self.token_student1)
        start_res = self.client.post(f"/api/student/exams/{self.exam.id}/start/")
        attempt_id = start_res.json()["attempt_id"]

        # Submit attempt
        sub_res = self.client.post(f"/api/student/attempts/{attempt_id}/submit/")
        self.assertEqual(sub_res.status_code, status.HTTP_200_OK)

        # Attempt to start again
        start_again_res = self.client.post(f"/api/student/exams/{self.exam.id}/start/")
        self.assertEqual(start_again_res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("already been submitted", start_again_res.json().get("detail", ""))

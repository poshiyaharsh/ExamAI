from datetime import timedelta
from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone
from admins.models import AdminInstitution, AdminDepartment
from faculty.models import FacultyProfile
from api.models import Exam, Question
from rest_framework.test import APIClient
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken


def _auth_token(user, role, institution):
    refresh = RefreshToken.for_user(user)
    refresh['role'] = role
    refresh['institution_id'] = institution.id if institution else None
    access = refresh.access_token
    access['role'] = role
    access['institution_id'] = institution.id if institution else None
    return str(access)


class ScopeMarksListsTestCase(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_user(
            username="admin@inst.edu",
            email="admin@inst.edu",
            password="AdminPassword123!",
        )
        self.institution = AdminInstitution.objects.create(
            admin=self.admin_user,
            institution_name="Global Tech University",
            institution_code="INST-GTU-001",
            status=AdminInstitution.STATUS_ACTIVE,
        )
        self.dept_cs = AdminDepartment.objects.create(
            institution=self.institution,
            department_name="Computer Science",
        )
        self.faculty_user = User.objects.create_user(
            username="faculty_os",
            password="testpassword123",
            email="os_prof@techu.edu",
        )
        self.faculty_profile = FacultyProfile.objects.create(
            user=self.faculty_user,
            institution=self.institution,
            department="Computer Science",
            employee_id="FAC001",
        )

        token = _auth_token(self.faculty_user, "faculty", self.institution)
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        now = timezone.now()
        self.exam = Exam.objects.create(
            institution=self.institution,
            created_by=self.faculty_user,
            title="OS With Linux CH_1",
            subject="Operating Systems",
            department="Computer Science",
            duration_minutes=60,
            total_marks=73,
            target_total_marks=100,
            marks_shortfall=27,
            topics=["Operating System Overview", "Process Management"],
            source_syllabus_text="Chapter 1: Operating System Overview. An operating system is system software that manages computer hardware and software resources. Process management involves process scheduling, context switching, and PCB.",
            source_documents=[{"filename": "OS_Linux_Syllabus.pdf", "pages": 12}],
            status=Exam.Status.DRAFT,
            starts_at=now + timedelta(minutes=10),
            ends_at=now + timedelta(hours=3),
            is_reviewed=True,
        )

        # 2 In-scope questions
        self.q1 = Question.objects.create(
            institution=self.institution,
            exam=self.exam,
            department="Computer Science",
            order=1,
            question_type=Question.QuestionType.MCQ,
            difficulty=Question.Difficulty.EASY,
            text="What is the primary role of an operating system?",
            marks=5,
            topic_text="Operating System Overview",
            explanation="An operating system is system software that manages computer hardware",
        )
        self.q2 = Question.objects.create(
            institution=self.institution,
            exam=self.exam,
            department="Computer Science",
            order=2,
            question_type=Question.QuestionType.SHORT_ANSWER,
            difficulty=Question.Difficulty.MEDIUM,
            text="Explain the role of PCB in process management.",
            marks=10,
            topic_text="Process Management",
            explanation="Process management involves process scheduling, context switching, and PCB.",
        )
        # 1 Off-scope bleeding question (Java topic carrying 58 marks)
        self.q3_offscope = Question.objects.create(
            institution=self.institution,
            exam=self.exam,
            department="Computer Science",
            order=3,
            question_type=Question.QuestionType.LONG_ANSWER,
            difficulty=Question.Difficulty.HARD,
            text="Explain JVM architecture, bytecode verification, and Garbage Collection algorithms in Java.",
            marks=58,
            topic_text="Java Virtual Machine",
            explanation="JVM Garbage Collection",
        )

    def test_scope_check_audit(self):
        """Scope audit must detect off-scope questions and report grounding status."""
        response = self.client.post(f"/api/faculty/exams/{self.exam.id}/scope-check/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data
        self.assertEqual(data["total_questions"], 3)
        self.assertEqual(data["in_scope_count"], 2)
        self.assertEqual(data["off_scope_count"], 1)

        off_scope_qs = [q for q in data["questions"] if q["is_off_scope"]]
        self.assertEqual(len(off_scope_qs), 1)
        self.assertEqual(off_scope_qs[0]["id"], self.q3_offscope.id)
        self.assertEqual(off_scope_qs[0]["scope_status"], "off_scope")

    def test_publish_blocked_on_shortfall_without_confirmation(self):
        """Publishing must fail with HTTP 400 when shortfall > 0 without confirm_shortfall."""
        response = self.client.post(f"/api/faculty/exams/{self.exam.id}/publish/", {})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(response.data.get("requires_shortfall_confirmation"))
        self.assertEqual(response.data.get("marks_shortfall"), 27)

    def test_publish_allowed_with_explicit_shortfall_confirmation(self):
        """Publishing must succeed when confirm_shortfall=True is provided."""
        response = self.client.post(f"/api/faculty/exams/{self.exam.id}/publish/", {
            "confirm_shortfall": True,
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.exam.refresh_from_db()
        self.assertEqual(self.exam.status, Exam.Status.PUBLISHED)
        self.assertTrue(self.exam.is_immutable)
        self.assertIn("shortfall_publish_confirmed", self.exam.validation_report)

    def test_adjust_marks_set_actual(self):
        """Action 'set_actual' updates target_total_marks to match actual marks and clears shortfall."""
        response = self.client.post(f"/api/faculty/exams/{self.exam.id}/adjust-marks/", {
            "action": "set_actual",
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.exam.refresh_from_db()
        self.assertEqual(self.exam.target_total_marks, 73)
        self.assertEqual(self.exam.total_marks, 73)
        self.assertEqual(self.exam.marks_shortfall, 0)

    def test_adjust_marks_preview_scale(self):
        """Action 'preview_scale' returns scaling preview without modifying database."""
        response = self.client.post(f"/api/faculty/exams/{self.exam.id}/adjust-marks/", {
            "action": "preview_scale",
            "target_marks": 100,
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        preview = response.data.get("preview")
        self.assertIsNotNone(preview)
        self.assertEqual(preview["target_marks"], 100)
        self.assertEqual(preview["current_marks"], 73)
        self.assertEqual(len(preview["question_previews"]), 3)

        # Database remains untouched
        self.exam.refresh_from_db()
        self.assertEqual(self.exam.total_marks, 73)
        self.assertEqual(self.exam.marks_shortfall, 27)

    def test_adjust_marks_scale_target(self):
        """Action 'scale_target' scales question marks to match requested target."""
        response = self.client.post(f"/api/faculty/exams/{self.exam.id}/adjust-marks/", {
            "action": "scale_target",
            "target_marks": 100,
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.exam.refresh_from_db()
        self.assertEqual(self.exam.total_marks, 100)
        self.assertEqual(self.exam.target_total_marks, 100)
        self.assertEqual(self.exam.marks_shortfall, 0)

        # Verify sum of question marks equals 100
        new_sum = sum(q.marks for q in self.exam.questions.all())
        self.assertEqual(new_sum, 100)

    def test_faculty_dashboard_loads_cleanly(self):
        """Faculty dashboard returns 200 with all required sections and violation stats."""
        response = self.client.get("/api/faculty/dashboard/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data.get("data", {})
        self.assertIn("profile", data)
        self.assertIn("stats", data)
        self.assertIn("ongoing_exams", data)
        self.assertIn("recent_exams", data)

        # Verify recent exams data structure
        recent = data["recent_exams"]
        self.assertGreaterEqual(len(recent), 1)
        r0 = recent[0]
        self.assertEqual(r0["id"], self.exam.id)
        self.assertEqual(r0["target_total_marks"], 100)
        self.assertEqual(r0["total_marks"], 73)
        self.assertEqual(r0["marks_shortfall"], 27)

    def test_faculty_dashboard_isolation(self):
        """Second faculty user only sees their own data, and cannot see other faculty exams."""
        faculty_user_2 = User.objects.create_user(
            username="faculty_math",
            password="testpassword123",
            email="math_prof@techu.edu",
        )
        FacultyProfile.objects.create(
            user=faculty_user_2,
            institution=self.institution,
            department="Mathematics",
            employee_id="FAC002",
        )
        exam_2 = Exam.objects.create(
            institution=self.institution,
            created_by=faculty_user_2,
            title="Calculus I",
            subject="Mathematics",
            department="Mathematics",
            duration_minutes=90,
            total_marks=50,
            target_total_marks=50,
            marks_shortfall=0,
            status=Exam.Status.PUBLISHED,
        )

        client_2 = APIClient()
        token_2 = _auth_token(faculty_user_2, "faculty", self.institution)
        client_2.credentials(HTTP_AUTHORIZATION=f"Bearer {token_2}")

        resp_2 = client_2.get("/api/faculty/dashboard/")
        self.assertEqual(resp_2.status_code, status.HTTP_200_OK)
        data_2 = resp_2.data.get("data", {})
        recent_2 = data_2["recent_exams"]
        self.assertEqual(len(recent_2), 1)
        self.assertEqual(recent_2[0]["id"], exam_2.id)

        # First faculty dashboard must NOT include exam_2
        resp_1 = self.client.get("/api/faculty/dashboard/")
        data_1 = resp_1.data.get("data", {})
        recent_1 = data_1["recent_exams"]
        self.assertTrue(all(e["id"] != exam_2.id for e in recent_1))

    def test_faculty_dashboard_zero_exams(self):
        """Faculty with zero exams loads dashboard with 200 and empty lists."""
        empty_faculty = User.objects.create_user(
            username="faculty_empty",
            password="testpassword123",
            email="empty_prof@techu.edu",
        )
        FacultyProfile.objects.create(
            user=empty_faculty,
            institution=self.institution,
            department="Physics",
            employee_id="FAC003",
        )
        client_empty = APIClient()
        token_empty = _auth_token(empty_faculty, "faculty", self.institution)
        client_empty.credentials(HTTP_AUTHORIZATION=f"Bearer {token_empty}")

        resp = client_empty.get("/api/faculty/dashboard/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.data.get("data", {})
        self.assertEqual(len(data["recent_exams"]), 0)
        self.assertEqual(len(data["ongoing_exams"]), 0)
        self.assertEqual(data["stats"]["total_exams"], 0)

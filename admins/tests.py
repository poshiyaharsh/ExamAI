import json
from django.test import TestCase
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from rest_framework import status

from admins.models import AdminInstitution, AdminProfile, AdminActionAuditLog
from faculty.models import FacultyProfile
from students.models import StudentProfile


class AdminActionsTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()

        # Admin user and institution
        self.admin = User.objects.create_user(
            username="admin@pits.example.edu",
            email="admin@pits.example.edu",
            password="Password123!",
        )
        self.admin_profile = AdminProfile.objects.create(user=self.admin)
        self.inst1 = AdminInstitution.objects.create(
            admin=self.admin,
            institution_name="PITS Institute",
            institution_code="INST-26-0001",
            short_code="PITS",
        )

        # Faculty user
        self.faculty_user = User.objects.create_user(
            username="faculty@pits.example.edu",
            email="faculty@pits.example.edu",
            password="OldPassword123!",
        )
        self.faculty_profile = FacultyProfile.objects.create(
            user=self.faculty_user,
            institution=self.inst1,
            department="Computer Science",
            designation="Assistant Professor",
            employee_id="FPITCS01",
        )

        # Student user
        self.student_user = User.objects.create_user(
            username="student@pits.example.edu",
            email="student@pits.example.edu",
            password="OldPassword123!",
        )
        self.student_profile = StudentProfile.objects.create(
            user=self.student_user,
            institution=self.inst1,
            department="Computer Science",
            student_id="SPITCS01",
        )

        # Other Admin & Institution for scoping test
        self.other_admin = User.objects.create_user(
            username="otheradmin@other.example.edu",
            email="otheradmin@other.example.edu",
            password="Password123!",
        )
        self.other_admin_profile = AdminProfile.objects.create(user=self.other_admin)
        self.inst2 = AdminInstitution.objects.create(
            admin=self.other_admin,
            institution_name="Other Institute",
            institution_code="INST-26-0002",
            short_code="OTHER",
        )
        self.other_faculty_user = User.objects.create_user(
            username="otherfaculty@other.example.edu",
            email="otherfaculty@other.example.edu",
            password="Password123!",
        )
        self.other_faculty = FacultyProfile.objects.create(
            user=self.other_faculty_user,
            institution=self.inst2,
            department="Mechanical",
            employee_id="FOTHER01",
        )

    def test_faculty_reset_password_success_and_audit(self):
        self.client.force_authenticate(user=self.admin)
        url = f"/api/admins/faculty/{self.faculty_profile.id}/reset-password/"
        response = self.client.post(
            url,
            {"new_password": "NewSecretPass@2026!"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.faculty_user.refresh_from_db()
        self.assertTrue(self.faculty_user.check_password("NewSecretPass@2026!"))

        # Verify audit log
        audit = AdminActionAuditLog.objects.filter(
            admin=self.admin,
            target_user=self.faculty_user,
            action="reset_password",
        ).first()
        self.assertIsNotNone(audit)
        self.assertEqual(audit.institution, self.inst1)

    def test_student_reset_password_success_and_audit(self):
        self.client.force_authenticate(user=self.admin)
        url = f"/api/admins/students/{self.student_profile.id}/reset-password/"
        response = self.client.post(
            url,
            {"new_password": "StudentPass@2026!"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.student_user.refresh_from_db()
        self.assertTrue(self.student_user.check_password("StudentPass@2026!"))

        audit = AdminActionAuditLog.objects.filter(
            admin=self.admin,
            target_user=self.student_user,
            action="reset_password",
        ).first()
        self.assertIsNotNone(audit)

    def test_cross_institute_reset_password_blocked(self):
        self.client.force_authenticate(user=self.admin)
        url = f"/api/admins/faculty/{self.other_faculty.id}/reset-password/"
        response = self.client.post(
            url,
            {"new_password": "HackerPass@2026!"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_change_department_and_audit(self):
        from admins.models import DepartmentChangeAuditLog
        self.client.force_authenticate(user=self.admin)
        url = f"/api/admins/users/{self.faculty_user.id}/change-department/"
        response = self.client.post(
            url,
            {"department": "Information Technology", "reason": "Transfer"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.faculty_profile.refresh_from_db()
        self.assertEqual(self.faculty_profile.department, "Information Technology")

        audit = DepartmentChangeAuditLog.objects.filter(
            changed_by=self.admin,
            user=self.faculty_user,
            new_department="Information Technology",
        ).first()
        self.assertIsNotNone(audit)
    def test_student_detail_api_enriched_metrics(self):
        self.client.force_authenticate(user=self.admin)
        url = f"/api/admins/students/{self.student_profile.id}/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data.get('data', {})
        self.assertEqual(data.get('id'), self.student_profile.id)
        self.assertEqual(data.get('email'), self.student_user.email)
        self.assertIn('number_of_exams', data)
        self.assertIn('average_score', data)
        self.assertIn('highest_score', data)
        self.assertIn('performance_status', data)

    def test_faculty_detail_api_enriched_metrics(self):
        from api.models import Exam, Question
        exam = Exam.objects.create(
            title="CS101 Midterm Exam",
            subject="Computer Science",
            institution=self.inst1,
            created_by=self.faculty_user,
            duration_minutes=60,
            total_marks=50,
            status=Exam.Status.PUBLISHED,
        )
        Question.objects.create(
            institution=self.inst1,
            created_by=self.faculty_user,
            question_type="mcq",
            text="Detail Test Question",
            marks=5,
        )

        self.client.force_authenticate(user=self.admin)
        url = f"/api/admins/faculty/{self.faculty_profile.id}/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data.get('data', {})
        self.assertEqual(data.get('id'), self.faculty_profile.id)
        self.assertEqual(data.get('exams_count'), 1)
        self.assertEqual(data.get('active_exams_count'), 1)
        self.assertEqual(data.get('questions_count'), 1)
        self.assertEqual(len(data.get('recent_exams', [])), 1)
        self.assertEqual(data['recent_exams'][0]['title'], "CS101 Midterm Exam")

    def test_cross_institute_detail_access_blocked(self):
        self.client.force_authenticate(user=self.admin)
        # Other faculty
        resp_f = self.client.get(f"/api/admins/faculty/{self.other_faculty.id}/")
        self.assertEqual(resp_f.status_code, status.HTTP_404_NOT_FOUND)


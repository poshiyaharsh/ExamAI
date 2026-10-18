from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from admins.models import AdminDepartment, AdminInstitution, AdminProfile, DepartmentChangeAuditLog
from faculty.models import FacultyProfile
from students.models import StudentProfile


def _auth_token(user, role, institution):
    refresh = RefreshToken.for_user(user)
    refresh['role'] = role
    refresh['institution_id'] = institution.id if institution else None
    access = refresh.access_token
    access['role'] = role
    access['institution_id'] = institution.id if institution else None
    return str(access)


class Phase1DepartmentTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin_user = User.objects.create_user(
            username="admin@inst.edu",
            email="admin@inst.edu",
            password="AdminPassword123!",
        )
        self.admin_profile = AdminProfile.objects.create(user=self.admin_user)
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
        self.dept_it = AdminDepartment.objects.create(
            institution=self.institution,
            department_name="Information Technology",
        )

    def test_student_signup_requires_department(self):
        # 1. Missing department
        payload = {
            "first_name": "Alice",
            "last_name": "Smith",
            "email": "alice@student.edu",
            "password": "Password123!",
            "institution_id": self.institution.id,
        }
        res = self.client.post("/api/students/signup/", payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("department", str(res.data))

        # 2. Invalid department
        payload["department"] = "NonExistent Department"
        res = self.client.post("/api/students/signup/", payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

        # 3. Valid department
        payload["department"] = "Computer Science"
        res = self.client.post("/api/students/signup/", payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        student_user = User.objects.get(email="alice@student.edu")
        self.assertEqual(student_user.student_profile.department, "Computer Science")

    def test_faculty_signup_requires_department(self):
        # 1. Missing department
        payload = {
            "first_name": "Bob",
            "last_name": "Faculty",
            "email": "bob@faculty.edu",
            "password": "Password123!",
            "institution_id": self.institution.id,
        }
        res = self.client.post("/api/faculty/signup/", payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("department", str(res.data))

        # 2. Invalid department
        payload["department"] = "Astronomy And Astrology"
        res = self.client.post("/api/faculty/signup/", payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

        # 3. Valid department
        payload["department"] = "Information Technology"
        res = self.client.post("/api/faculty/signup/", payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        fac_user = User.objects.get(email="bob@faculty.edu")
        self.assertEqual(fac_user.faculty_profile.department, "Information Technology")

    def test_student_department_immutable(self):
        user = User.objects.create_user(
            username="charlie@student.edu",
            email="charlie@student.edu",
            password="Password123!",
        )
        profile = StudentProfile.objects.create(
            user=user,
            institution=self.institution,
            department="Computer Science",
        )
        token = _auth_token(user, "student", self.institution)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        # Attempt to change department via PUT
        res = self.client.put("/api/students/profile/", {"department": "Information Technology"}, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

        profile.refresh_from_db()
        self.assertEqual(profile.department, "Computer Science")

        # Attempt direct ORM modification without override
        profile.department = "Mechanical Engineering"
        with self.assertRaises(ValidationError):
            profile.save()

    def test_faculty_department_immutable(self):
        user = User.objects.create_user(
            username="prof@faculty.edu",
            email="prof@faculty.edu",
            password="Password123!",
        )
        profile = FacultyProfile.objects.create(
            user=user,
            institution=self.institution,
            department="Information Technology",
        )
        token = _auth_token(user, "faculty", self.institution)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        # Attempt to change department via PUT
        res = self.client.put("/api/faculty/profile/", {"department": "Computer Science"}, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

        profile.refresh_from_db()
        self.assertEqual(profile.department, "Information Technology")

        # Attempt direct ORM modification without override
        profile.department = "Civil Engineering"
        with self.assertRaises(ValidationError):
            profile.save()

    def test_admin_can_override_department_with_audit_log(self):
        user = User.objects.create_user(
            username="student_dept_change@student.edu",
            email="student_dept_change@student.edu",
            password="Password123!",
        )
        profile = StudentProfile.objects.create(
            user=user,
            institution=self.institution,
            department="Computer Science",
        )
        token = _auth_token(self.admin_user, "admin", self.institution)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        payload = {
            "department": "Information Technology",
            "reason": "Student requested transfer to IT dept after approval by Dean",
        }
        res = self.client.post(f"/api/admins/users/{user.id}/change-department/", payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        profile.refresh_from_db()
        self.assertEqual(profile.department, "Information Technology")

        # Verify audit log
        audit = DepartmentChangeAuditLog.objects.filter(user=user).first()
        self.assertIsNotNone(audit)
        self.assertEqual(audit.previous_department, "Computer Science")
        self.assertEqual(audit.new_department, "Information Technology")
        self.assertEqual(audit.changed_by, self.admin_user)
        self.assertIn("Dean", audit.reason)

    def test_faculty_department_isolation_on_exam_create(self):
        user = User.objects.create_user(
            username="fac_cs@faculty.edu",
            email="fac_cs@faculty.edu",
            password="Password123!",
        )
        FacultyProfile.objects.create(
            user=user,
            institution=self.institution,
            department="Computer Science",
        )
        token = _auth_token(user, "faculty", self.institution)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        payload = {
            "title": "Unauthorized Exam",
            "department": "Information Technology",
            "duration": 60,
            "total_marks": 50,
            "topics": ["Algorithms"],
            "question_types": ["mcq"],
            "difficulty_mix": {"Easy": 50, "Medium": 50, "Hard": 0},
        }
        res = self.client.post("/api/faculty/exams/generate/", payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("Faculty may only create exams for their own department", res.data.get("detail", ""))

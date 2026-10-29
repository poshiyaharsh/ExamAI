import json
from decimal import Decimal
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from admins.models import AdminDepartment, AdminInstitution, AdminProfile
from api.generate_paper import GeneratePaperView
from api.models import Exam, Option, Question, Subject
from api.serializers import StudentExamSerializer
from api.views_faculty_materials import (
    FacultyStudyMaterialDetailView,
    FacultyStudyMaterialsView,
    FacultySubjectsListView,
)
from faculty.models import FacultyProfile, SyllabusUpload

User = get_user_model()


class FacultyMaterialsAndScheduleTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

        # Admin & Tenant
        self.admin_user = User.objects.create_user(
            username="admin@inst.edu",
            email="admin@inst.edu",
            password="Password123!",
        )
        AdminProfile.objects.create(user=self.admin_user)

        self.institution = AdminInstitution.objects.create(
            admin=self.admin_user,
            institution_name="Tech University",
        )
        self.dept = AdminDepartment.objects.create(
            department_name="Computer Science",
            institution=self.institution,
        )

        # Faculty User
        self.faculty_user = User.objects.create_user(
            username="faculty@inst.edu",
            email="faculty@inst.edu",
            password="Password123!",
            first_name="Ada",
            last_name="Lovelace",
        )
        self.faculty_user.institution = self.institution
        self.faculty_user.department = self.dept
        self.faculty_user.save()
        self.faculty_profile = FacultyProfile.objects.create(
            user=self.faculty_user,
            institution=self.institution,
            department="Computer Science",
        )

        # Subjects
        self.subject_java = Subject.objects.create(
            name="Java Programming",
            code="CS201",
            department="Computer Science",
            institution=self.institution,
            created_by=self.faculty_user,
        )
        self.subject_python = Subject.objects.create(
            name="Python Programming",
            code="CS202",
            department="Computer Science",
            institution=self.institution,
            created_by=self.faculty_user,
        )

    def test_list_and_create_faculty_subjects(self):
        view = FacultySubjectsListView.as_view()

        # GET subjects
        request = self.factory.get("/api/faculty/subjects/")
        request.user = self.faculty_user
        request.tenant = self.institution
        force_authenticate(request, user=self.faculty_user)
        response = view(request)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        subject_names = [s["name"] for s in response.data["subjects"]]
        self.assertIn("Java Programming", subject_names)
        self.assertIn("Python Programming", subject_names)

        # POST new subject
        post_request = self.factory.post(
            "/api/faculty/subjects/",
            data={"name": "Web Systems", "code": "CS301"},
            format="json",
        )
        post_request.user = self.faculty_user
        post_request.tenant = self.institution
        force_authenticate(post_request, user=self.faculty_user)
        post_response = view(post_request)
        self.assertEqual(post_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(post_response.data["name"], "Web Systems")
        self.assertTrue(
            Subject.objects.filter(name="Web Systems", institution=self.institution).exists()
        )

    def test_upload_and_filter_subject_materials(self):
        view = FacultyStudyMaterialsView.as_view()

        # Upload material for Java
        sample_file = SimpleUploadedFile(
            "java_concurrency.txt",
            b"Chapter 1: Threads and Synchronization in Java. Locks and deadlocks.",
            content_type="text/plain",
        )
        request = self.factory.post(
            "/api/faculty/materials/upload/",
            data={
                "subject_id": self.subject_java.id,
                "file": sample_file,
            },
            format="multipart",
        )
        request.user = self.faculty_user
        request.tenant = self.institution
        force_authenticate(request, user=self.faculty_user)
        response = view(request)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("material", response.data)
        java_mat_id = response.data["material"]["id"]

        # GET materials for Java
        get_request = self.factory.get(f"/api/faculty/materials/?subject_id={self.subject_java.id}")
        get_request.user = self.faculty_user
        get_request.tenant = self.institution
        force_authenticate(get_request, user=self.faculty_user)
        get_response = view(get_request)
        self.assertEqual(get_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(get_response.data["materials"]), 1)
        self.assertEqual(get_response.data["materials"][0]["id"], java_mat_id)

        # GET materials for Python (must be empty)
        py_request = self.factory.get(f"/api/faculty/materials/?subject_id={self.subject_python.id}")
        py_request.user = self.faculty_user
        py_request.tenant = self.institution
        force_authenticate(py_request, user=self.faculty_user)
        py_response = view(py_request)
        self.assertEqual(py_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(py_response.data["materials"]), 0)

    def test_cross_subject_material_rejection(self):
        """
        Verify that passing a material belonging to Subject A (Python)
        when generating an exam for Subject B (Java) triggers HTTP 400 Bad Request.
        """
        # Create a material for Python
        py_material = SyllabusUpload.objects.create(
            faculty=self.faculty_profile,
            institution=self.institution,
            subject=self.subject_python,
            original_filename="python_basics.txt",
            extracted_text="Python data structures: lists, dicts, tuples, sets.",
            detected_topics=["Lists", "Dictionaries"],
        )

        view = GeneratePaperView.as_view()
        request = self.factory.post(
            "/api/faculty/exams/generate/",
            data={
                "title": "Java Final Exam",
                "duration_minutes": 60,
                "total_marks": 50,
                "subject": "Java Programming",
                "subject_id": self.subject_java.id,
                "topics": ["Threads"],
                "question_types": ["mcq"],
                "difficulty_distribution": json.dumps({"easy": 30, "medium": 50, "hard": 20}),
                "material_ids": [py_material.id],  # VIOLATION: Python material used for Java exam!
            },
            format="multipart",
        )
        request.user = self.faculty_user
        request.tenant = self.institution
        force_authenticate(request, user=self.faculty_user)
        response = view(request)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        detail_msg = response.data.get("detail", "")
        self.assertIn("Cross-subject violation", detail_msg)
        self.assertIn("python_basics.txt", detail_msg)

    def test_student_schedule_display_serialization(self):
        """
        Verify that StudentExamSerializer provides clean, non-truncated schedule_display
        with starts_at_display, ends_at_display, and timezone.
        """
        now = timezone.now()
        start = now + timedelta(days=1)
        end = now + timedelta(days=1, hours=3)

        exam = Exam.objects.create(
            title="Algorithm Analysis",
            institution=self.institution,
            department="Computer Science",
            created_by=self.faculty_user,
            total_marks=100,
            duration_minutes=90,
            starts_at=start,
            ends_at=end,
            display_timezone="Asia/Kolkata",
            status="published",
        )

        serializer = StudentExamSerializer(exam)
        data = serializer.data

        self.assertIn("schedule_display", data)
        sched = data["schedule_display"]
        self.assertIsNotNone(sched)
        self.assertEqual(sched["timezone"], "Asia/Kolkata")
        self.assertIn("starts_at_display", sched)
        self.assertIn("ends_at_display", sched)
        self.assertIsNotNone(sched["starts_at_display"])
        self.assertIsNotNone(sched["ends_at_display"])
        self.assertIn("summary", sched)

"""Automated tests for stale topic prevention, syllabus topic validation, and exam topic pruning.

Tests:
1. Topic validation utility (validate_topics_against_syllabus):
   - Accepts topics present in syllabus text
   - Handles chapter/unit prefixes and casing
   - Rejects alien topics not present in syllabus
2. Server API validation (GeneratePaperView):
   - Rejects alien topics with HTTP 400 and returns invalid_topics list
   - Accepts matching topics when syllabus is uploaded
3. Exam paper topic pruning:
   - Generator prunes exam.topics strictly to the unique topics of saved active questions
4. Management command audit_exam_topics:
   - Dry-run identifies alien topics without modifying exam.topics
   - Apply updates exam.topics to match question topics
"""

import json
from unittest.mock import patch
from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase
from io import StringIO
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from admins.models import AdminInstitution, AdminProfile
from faculty.models import FacultyProfile
from api.models import Exam, Question, Subject, Topic
from api.utils.extract_text import validate_topics_against_syllabus
from api.utils.blueprint_allocator import allocate_blueprint_to_target
from api.paper_engine.generator import generate_exam_paper


def _get_token(user, role, institution):
    refresh = RefreshToken.for_user(user)
    refresh["role"] = role
    refresh["institution_id"] = institution.id if institution else None
    access = refresh.access_token
    access["role"] = role
    access["institution_id"] = institution.id if institution else None
    return str(access)


class StaleTopicsValidationTestCase(TestCase):
    def test_validate_topics_against_syllabus_valid(self):
        syllabus = (
            "Unit 1: Process Management and Thread Scheduling\n"
            "Unit 2: Memory Management, Paging, and Virtual Memory\n"
            "Unit 3: File System Implementation and Storage Architecture"
        )
        topics = [
            "Process Management",
            "Virtual Memory",
            "File System",
        ]
        is_valid, invalid = validate_topics_against_syllabus(topics, syllabus)
        self.assertTrue(is_valid)
        self.assertEqual(invalid, [])

    def test_validate_topics_against_syllabus_alien_rejected(self):
        syllabus = (
            "Unit 1: Process Management and Scheduling\n"
            "Unit 2: Memory Management and Virtual Memory"
        )
        # Java topics submitted for an OS syllabus
        topics = [
            "Process Management",
            "JDK and Java Runtime Environment",
            "Java Garbage Collection",
        ]
        is_valid, invalid = validate_topics_against_syllabus(topics, syllabus)
        self.assertFalse(is_valid)
        self.assertIn("JDK and Java Runtime Environment", invalid)
        self.assertIn("Java Garbage Collection", invalid)
        self.assertEqual(len(invalid), 2)

    def test_validate_topics_strips_unit_chapter_numbers(self):
        syllabus = "Content discusses Database Normalization, 1NF, 2NF, 3NF and BCNF."
        topics = ["Chapter 3: Database Normalization"]
        is_valid, invalid = validate_topics_against_syllabus(topics, syllabus)
        self.assertTrue(is_valid)
        self.assertEqual(invalid, [])


class StaleTopicsApiTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()

        self.admin_user = User.objects.create_user(
            username="admin_topics@apex.edu",
            password="AdminPassword123!",
            email="admin_topics@apex.edu",
        )
        AdminProfile.objects.create(user=self.admin_user)
        self.institution = AdminInstitution.objects.create(
            admin=self.admin_user,
            institution_name="Tech University",
            institution_code="TECH_UNI",
            status=AdminInstitution.STATUS_ACTIVE,
        )

        self.faculty_user = User.objects.create_user(
            username="faculty_topics@apex.edu",
            password="FacultyPassword123!",
            email="faculty_topics@apex.edu",
        )
        self.faculty_profile = FacultyProfile.objects.create(
            user=self.faculty_user,
            institution=self.institution,
            department="Computer Engineering",
            designation="Assistant Professor",
        )
        self.faculty_token = _get_token(self.faculty_user, "faculty", self.institution)

        self.subject = Subject.objects.create(
            name="Operating Systems",
            code="OS101",
            institution=self.institution,
            department="Computer Engineering",
        )

    def tearDown(self):
        cache.clear()

    @patch("api.generate_paper.extract_syllabus_text")
    def test_generate_paper_rejects_alien_topics(self, mock_extract):
        """When an uploaded syllabus text does not contain submitted topics, server returns HTTP 400."""
        mock_extract.return_value = (
            "Course: Operating Systems\n"
            "Unit 1: Process Scheduling and Dispatching\n"
            "Unit 2: Inter-Process Communication and Deadlocks"
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.faculty_token}")

        syllabus_file = SimpleUploadedFile(
            "os_syllabus.pdf",
            b"%PDF-1.4 mock os syllabus",
            content_type="application/pdf",
        )

        valid_bp, _ = allocate_blueprint_to_target(50)

        # Payload contains old Java topics from a prior exam
        payload = {
            "title": "OS Midterm",
            "subject": self.subject.id,
            "department": "Computer Engineering",
            "total_marks": 50,
            "duration_minutes": 60,
            "topics": ["Process Scheduling", "Java Virtual Machine (JVM) Architecture", "Spring Boot Framework"],
            "question_types": ["MCQ_SINGLE", "SHORT_ANSWER"],
            "difficulty_distribution": json.dumps({"easy": 50, "medium": 50, "hard": 0}),
            "blueprint": json.dumps(valid_bp),
            "syllabus": syllabus_file,
        }

        response = self.client.post("/api/faculty/exams/generate/", payload, format="multipart")
        self.assertEqual(response.status_code, 400)
        self.assertIn("invalid_topics", response.data)
        self.assertIn("Java Virtual Machine (JVM) Architecture", response.data["invalid_topics"])
        self.assertIn("Spring Boot Framework", response.data["invalid_topics"])

    @patch("api.generate_paper.extract_syllabus_text")
    @patch("api.generate_paper.threading.Thread")
    def test_generate_paper_accepts_valid_topics(self, mock_thread, mock_extract):
        """When submitted topics belong to the uploaded syllabus, server accepts generation."""
        mock_extract.return_value = (
            "Course: Operating Systems\n"
            "Unit 1: Process Scheduling and Dispatching\n"
            "Unit 2: Inter-Process Communication and Deadlocks"
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.faculty_token}")

        syllabus_file = SimpleUploadedFile(
            "os_syllabus.pdf",
            b"%PDF-1.4 mock os syllabus",
            content_type="application/pdf",
        )

        valid_bp, _ = allocate_blueprint_to_target(50)

        payload = {
            "title": "OS Midterm Valid",
            "subject": self.subject.id,
            "department": "Computer Engineering",
            "total_marks": 50,
            "duration_minutes": 60,
            "topics": ["Process Scheduling", "Inter-Process Communication"],
            "question_types": ["MCQ_SINGLE", "SHORT_ANSWER"],
            "difficulty_distribution": json.dumps({"easy": 50, "medium": 50, "hard": 0}),
            "blueprint": json.dumps(valid_bp),
            "ai_model": "qwen2.5-3b",
            "syllabus": syllabus_file,
        }

        response = self.client.post("/api/faculty/exams/generate/", payload, format="multipart")
        self.assertIn(response.status_code, [200, 201, 202])


class TopicPruningTestCase(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_user(
            username="admin_prune@apex.edu",
            password="AdminPassword123!",
            email="admin_prune@apex.edu",
        )
        self.institution = AdminInstitution.objects.create(
            admin=self.admin_user,
            institution_name="Prune Uni",
            institution_code="PRUNE_UNI",
            status=AdminInstitution.STATUS_ACTIVE,
        )
        self.faculty_user = User.objects.create_user(
            username="faculty_prune@apex.edu",
            password="FacultyPassword123!",
            email="faculty_prune@apex.edu",
        )
        self.subject = Subject.objects.create(
            name="Computer Networks",
            code="CN301",
            institution=self.institution,
            department="Computer Science",
        )
        self.exam = Exam.objects.create(
            title="CN Quiz",
            institution=self.institution,
            department="Computer Science",
            created_by=self.faculty_user,
            total_marks=30,
            duration_minutes=45,
            topics=[
                "IP Addressing",
                "Subnetting",
                "Stale Java Topic 1",
                "Stale Java Topic 2",
            ],
        )

    def test_audit_exam_topics_dry_run_and_apply(self):
        # Create questions only for IP Addressing and Subnetting
        Question.objects.create(
            exam=self.exam,
            institution=self.institution,
            created_by=self.faculty_user,
            question_type="MCQ_SINGLE",
            topic_text="IP Addressing",
            text="What is IPv4 length?",
            marks=5,
            is_deleted=False,
        )
        Question.objects.create(
            exam=self.exam,
            institution=self.institution,
            created_by=self.faculty_user,
            question_type="SHORT_ANSWER",
            topic_text="Subnetting",
            text="Explain CIDR notation.",
            marks=10,
            is_deleted=False,
        )

        # 1. Run dry-run
        out = StringIO()
        call_command("audit_exam_topics", f"--exam-id={self.exam.id}", stdout=out)
        output = out.getvalue()
        self.assertIn("DRY-RUN", output)
        self.assertIn("Stale/Alien Topics to prune (2)", output)

        # Verify DB was NOT changed
        self.exam.refresh_from_db()
        self.assertEqual(len(self.exam.topics), 4)
        self.assertIn("Stale Java Topic 1", self.exam.topics)

        # 2. Run apply
        out_apply = StringIO()
        call_command("audit_exam_topics", f"--exam-id={self.exam.id}", "--apply", stdout=out_apply)
        output_apply = out_apply.getvalue()
        self.assertIn("APPLY", output_apply)
        self.assertIn("Successfully updated exam.topics", output_apply)

        # Verify DB WAS changed to only actual question topics
        self.exam.refresh_from_db()
        self.assertCountEqual(self.exam.topics, ["IP Addressing", "Subnetting"])
        self.assertNotIn("Stale Java Topic 1", self.exam.topics)
        self.assertNotIn("Stale Java Topic 2", self.exam.topics)

    def test_generate_exam_paper_prunes_exam_topics_to_accepted_questions(self):
        """When generate_exam_paper executes, exam.topics is pruned to strictly unique topics of accepted questions."""
        # Create question bank pool questions
        Question.objects.create(
            institution=self.institution,
            created_by=self.faculty_user,
            department="Computer Science",
            subject=self.subject,
            topic_text="Subnetting",
            text="Explain in detail the mathematical derivation of CIDR subnet masks and supernetting.",
            question_type="LONG_ANSWER",
            difficulty="medium",
            marks=10,
            is_deleted=False,
            status="ACTIVE",
        )

        payload = {
            "title": "CN Test Paper",
            "department": "Computer Science",
            "subject": self.subject.id,
            "total_marks": 10,
            "duration_minutes": 30,
            # Payload contains the real topic plus old/stale topics from previous exams
            "topics": ["Subnetting", "Old Java Topic 1", "Old OS Topic 2"],
            "question_types": ["subjective"],
            "difficulty_distribution": {"easy": 0, "medium": 100, "hard": 0},
        }

        data, from_cache = generate_exam_paper(
            payload=payload,
            user=self.faculty_user,
            tenant=self.institution,
            force_regenerate=True,
        )

        created_exam = Exam.objects.get(id=data["id"])
        # Topics must be strictly pruned to the actual question topic
        self.assertEqual([t.lower() for t in created_exam.topics], ["subnetting"])
        self.assertNotIn("Old Java Topic 1", created_exam.topics)
        self.assertNotIn("Old OS Topic 2", created_exam.topics)


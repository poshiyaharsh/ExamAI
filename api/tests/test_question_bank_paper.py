from decimal import Decimal
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIRequestFactory, force_authenticate

from admins.models import AdminDepartment, AdminInstitution, AdminProfile
from faculty.models import FacultyProfile
from api.models import Exam, Option, Question, Subject
from api.serializers import FacultyQuestionSerializer
from api.utils.options import clean_options_list
from api.utils.validate_paper import audit_question_scope
from api.views_faculty_question_bank import AssemblePaperFromBankView

User = get_user_model()


class QuestionBankPaperTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

        self.admin_user = User.objects.create_user(
            username="admin@test.edu",
            email="admin@test.edu",
            password="Password123!",
        )
        AdminProfile.objects.create(user=self.admin_user)

        self.institution = AdminInstitution.objects.create(
            admin=self.admin_user,
            institution_name="Test Univ",
        )
        self.dept = AdminDepartment.objects.create(
            department_name="Computer Science",
            institution=self.institution,
        )

        self.faculty_user = User.objects.create_user(
            username="prof@test.edu",
            email="prof@test.edu",
            password="Password123!",
            first_name="Alan",
            last_name="Turing",
        )
        self.faculty_user.institution = self.institution
        self.faculty_user.department = self.dept
        self.faculty_user.save()
        FacultyProfile.objects.create(user=self.faculty_user, department="Computer Science")

        self.subject = Subject.objects.create(
            name="Data Structures",
            code="CS101",
            department="Computer Science",
            institution=self.institution,
        )

        # Seed question bank with various types
        # 3 MCQs
        for i in range(1, 4):
            Question.objects.create(
                institution=self.institution,
                department="Computer Science",
                subject=self.subject,
                topic_text="Arrays",
                created_by=self.faculty_user,
                question_type="mcq",
                difficulty="easy",
                text=f"MCQ Question {i} text",
                marks=Decimal("1"),
                status=Question.Status.ACTIVE,
                source="faculty_upload",
                is_shared=True,
                options=[
                    {"text": f"Opt A{i}", "is_correct": True, "order": 1},
                    {"text": f"Opt B{i}", "is_correct": False, "order": 2},
                    {"text": f"Opt C{i}", "is_correct": False, "order": 3},
                    {"text": f"Opt D{i}", "is_correct": False, "order": 4},
                ],
                correct_answer=f"Opt A{i}",
                exam=None,
            )

        # 2 True/False
        for i in range(1, 3):
            Question.objects.create(
                institution=self.institution,
                department="Computer Science",
                subject=self.subject,
                topic_text="Logic",
                created_by=self.faculty_user,
                question_type="true_false",
                difficulty="medium",
                text=f"True False Question {i} text",
                marks=Decimal("1"),
                status=Question.Status.ACTIVE,
                source="faculty_upload",
                is_shared=True,
                options=[
                    {"text": "True", "is_correct": True, "order": 1},
                    {"text": "False", "is_correct": False, "order": 2},
                ],
                correct_answer="True",
                exam=None,
            )

        # 1 Short answer
        Question.objects.create(
            institution=self.institution,
            department="Computer Science",
            subject=self.subject,
            topic_text="Trees",
            created_by=self.faculty_user,
            question_type="short",
            difficulty="hard",
            text="Explain AVL tree balance factor.",
            marks=Decimal("5"),
            status=Question.Status.ACTIVE,
            source="faculty_upload",
            is_shared=True,
            options=[],
            model_answer="Balance factor is height(left) - height(right).",
            exam=None,
        )

    def test_clean_options_list_utility(self):
        # List of dicts
        raw = [
            {"text": "Option 1", "is_correct": True},
            {"text": "B. Option 2", "is_correct": False},
        ]
        cleaned = clean_options_list(raw)
        self.assertEqual(cleaned, ["Option 1", "Option 2"])

        # Already list of strings
        self.assertEqual(clean_options_list(["A", "B"]), ["A", "B"])

        # None or invalid
        self.assertEqual(clean_options_list(None), [])
        self.assertEqual(clean_options_list("not a list"), [])

    def test_assemble_paper_from_bank_with_blueprint(self):
        view = AssemblePaperFromBankView.as_view()
        start = timezone.now() + timedelta(days=1)
        end = start + timedelta(hours=2)

        payload = {
            "title": "Algorithms Exam from Bank",
            "subject": "Data Structures",
            "target_marks": 7,  # 2 MCQs (2) + 0 TF + 1 Short (5) = 7
            "duration_minutes": 60,
            "starts_at": start.isoformat(),
            "ends_at": end.isoformat(),
            "auto_assemble": True,
            "blueprint": {
                "mcq": 2,
                "short": 1,
            },
        }

        req = self.factory.post("/api/faculty/exams/assemble-from-bank/", payload, format="json")
        req.tenant = self.institution
        force_authenticate(req, user=self.faculty_user)

        res = view(req)
        self.assertEqual(res.status_code, 200)
        exam_id = res.data["exam_id"]
        exam = Exam.objects.get(id=exam_id)

        self.assertEqual(exam.title, "Algorithms Exam from Bank")
        self.assertEqual(exam.total_marks, 7)
        self.assertEqual(exam.status, Exam.Status.DRAFT)
        self.assertIn("mcq", exam.question_types)
        self.assertIn("short_answer", exam.question_types)
        self.assertTrue(len(exam.topics) >= 1)

        # Verify Question.options is normalized to string list
        for q in exam.questions.all():
            if q.question_type == "mcq":
                self.assertIsInstance(q.options, list)
                self.assertTrue(all(isinstance(opt, str) for opt in q.options))

    def test_faculty_question_serializer_normalizes_options(self):
        # Create a question with dict options
        q = Question.objects.create(
            institution=self.institution,
            department="Computer Science",
            subject=self.subject,
            topic_text="Lists",
            created_by=self.faculty_user,
            question_type="mcq",
            difficulty="easy",
            text="What is a linked list?",
            marks=Decimal("1"),
            status=Question.Status.ACTIVE,
            source="question_bank",
            options=[
                {"text": "Linear structure", "is_correct": True, "order": 1},
                {"text": "Tree structure", "is_correct": False, "order": 2},
            ],
            correct_answer="Linear structure",
        )

        serializer = FacultyQuestionSerializer(q)
        data = serializer.data
        self.assertEqual(data["options"], ["Linear structure", "Tree structure"])
        self.assertTrue(all(isinstance(opt, str) for opt in data["options"]))

    def test_audit_question_scope_exempts_bank_questions(self):
        q = Question.objects.create(
            institution=self.institution,
            department="Computer Science",
            subject=self.subject,
            topic_text="Lists",
            created_by=self.faculty_user,
            question_type="mcq",
            difficulty="easy",
            text="Unrelated topic question",
            marks=Decimal("1"),
            status=Question.Status.ACTIVE,
            source="question_bank",
        )

        # Audit with empty syllabus text
        audit = audit_question_scope(q, syllabus_text="")
        self.assertTrue(audit["in_scope"])
        self.assertTrue(audit["is_manual"])

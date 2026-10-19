import json
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from admins.models import AdminInstitution, AdminDepartment
from api.models import Exam, Question, StudentAttempt, StudentAnswer
from api.serializers import StudentQuestionSerializer
from api.utils.scoring import is_objective_answer_correct, evaluate_fill_blank, is_objective_question

User = get_user_model()


def get_token(user, role, institution):
    refresh = RefreshToken.for_user(user)
    refresh['role'] = role
    refresh['institution_id'] = institution.id if institution else None
    access = refresh.access_token
    access['role'] = role
    access['institution_id'] = institution.id if institution else None
    return str(access)


class QuestionTypesAndDifficultyTests(TestCase):
    def setUp(self):
        self.client = APIClient()
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

        self.faculty = User.objects.create_user(
            username="prof_turing",
            email="turing@university.edu",
            password="password123",
        )
        self.student = User.objects.create_user(
            username="ada_student",
            email="ada@university.edu",
            password="password123",
        )

        from students.models import StudentProfile
        self.student_profile = StudentProfile.objects.create(
            user=self.student,
            institution=self.institution,
            department="Computer Science",
            student_id="STU-2026-0001",
        )

        self.exam = Exam.objects.create(
            institution=self.institution,
            created_by=self.faculty,
            title="Advanced Systems & Protocols",
            duration_minutes=60,
            total_marks=20,
            department="Computer Science",
            status="published",
            difficulty_distribution={"easy": 30, "medium": 50, "hard": 20},
            question_types=["mcq", "true_false", "fill_blank", "short_answer", "long_answer"],
        )

    def test_model_fields_and_all_five_types(self):
        """Verify Question model supports all 5 types, rubrics, accepted_answers, and word limits."""
        q_mcq = Question.objects.create(
            institution=self.institution,
            exam=self.exam,
            question_type="mcq",
            difficulty="easy",
            text="Which layer is IP?",
            options=["Application", "Network", "Transport", "Physical"],
            correct_answer="B",
            marks=2,
            order=1,
        )
        q_tf = Question.objects.create(
            institution=self.institution,
            exam=self.exam,
            question_type="true_false",
            difficulty="easy",
            text="TCP guarantees ordered packet delivery.",
            correct_answer="True",
            marks=2,
            order=2,
        )
        q_fb = Question.objects.create(
            institution=self.institution,
            exam=self.exam,
            question_type="fill_blank",
            difficulty="medium",
            text="DNS translates ____ into ____.",
            correct_answer="domain names, IP addresses",
            accepted_answers=[["hostname", "domain name", "domain names"], ["ip", "ip address", "ip addresses"]],
            marks=4,
            order=3,
        )
        q_sa = Question.objects.create(
            institution=self.institution,
            exam=self.exam,
            question_type="short_answer",
            difficulty="medium",
            text="Explain the three-way handshake.",
            model_answer="SYN, SYN-ACK, ACK establishing seq numbers.",
            rubric=["1 mark for SYN/ACK sequence", "1 mark for sequence numbers"],
            word_limit=60,
            marks=4,
            order=4,
        )
        q_la = Question.objects.create(
            institution=self.institution,
            exam=self.exam,
            question_type="long_answer",
            difficulty="hard",
            text="Compare TCP congestion control algorithms Cubic and BBR.",
            model_answer="Cubic uses cubic function for window growth; BBR models bottleneck bandwidth and RTT.",
            rubric=["4 marks for window dynamics", "4 marks for delay vs loss model"],
            word_limit=300,
            marks=8,
            order=5,
        )

        self.assertEqual(self.exam.questions.count(), 5)
        self.assertEqual(q_fb.accepted_answers[0][0], "hostname")
        self.assertEqual(q_sa.word_limit, 60)
        self.assertEqual(q_la.difficulty, "hard")

    def test_student_serializer_zero_leakage(self):
        """Verify StudentQuestionSerializer strictly hides answer keys, rubrics, and accepted answers."""
        q = Question.objects.create(
            institution=self.institution,
            exam=self.exam,
            question_type="fill_blank",
            difficulty="medium",
            text="The speed of light in vacuum is approx ____ m/s.",
            correct_answer="3x10^8",
            accepted_answers=[["3x10^8", "300000000", "3*10^8"]],
            model_answer="300 million meters per second",
            rubric="Full credit for accurate orders of magnitude.",
            marks=2,
            order=1,
        )
        serializer = StudentQuestionSerializer(q)
        data = serializer.data

        self.assertNotIn("correct_answer", data)
        self.assertNotIn("accepted_answers", data)
        self.assertNotIn("model_answer", data)
        self.assertNotIn("rubric", data)
        self.assertEqual(data["text"], q.text)
        self.assertEqual(data["question_type"], "fill_blank")

    def test_proportional_fill_blank_scoring(self):
        """Test proportional partial marks for multi-blank and synonyms without negative scores."""
        q = Question.objects.create(
            institution=self.institution,
            exam=self.exam,
            question_type="fill_blank",
            difficulty="medium",
            text="Water contains ____ and ____.",
            correct_answer="hydrogen, oxygen",
            accepted_answers=[["H", "hydrogen"], ["O", "oxygen"]],
            marks=4,
            order=1,
        )

        class MockAnswer:
            def __init__(self, blanks=None, text=""):
                self.blank_answers = blanks or []
                self.answer_text = text

        # Both correct
        score, is_correct, _ = evaluate_fill_blank(q, MockAnswer(["hydrogen", "oxygen"]))
        self.assertTrue(is_correct)
        self.assertEqual(score, 4.0)

        # Synonyms match
        score, is_correct, _ = evaluate_fill_blank(q, MockAnswer(["H", "O"]))
        self.assertTrue(is_correct)
        self.assertEqual(score, 4.0)

        # 1 of 2 blanks correct -> exactly 2.0 marks (proportional partial credit)
        score, is_correct, _ = evaluate_fill_blank(q, MockAnswer(["hydrogen", "nitrogen"]))
        self.assertFalse(is_correct)
        self.assertEqual(score, 2.0)

        # 0 of 2 correct -> 0 marks
        score, is_correct, _ = evaluate_fill_blank(q, MockAnswer(["carbon", "helium"]))
        self.assertFalse(is_correct)
        self.assertEqual(score, 0.0)

        # Empty/whitespace inputs
        score, is_correct, _ = evaluate_fill_blank(q, MockAnswer(["", "   "]))
        self.assertFalse(is_correct)
        self.assertEqual(score, 0.0)

    def test_true_false_scoring(self):
        """Test objective scoring for true_false questions."""
        q = Question.objects.create(
            institution=self.institution,
            exam=self.exam,
            question_type="true_false",
            difficulty="easy",
            text="UDP is a connection-oriented protocol.",
            correct_answer="False",
            marks=2,
            order=1,
        )
        self.assertTrue(is_objective_question(q))

        self.assertTrue(is_objective_answer_correct(q, "False"))
        self.assertTrue(is_objective_answer_correct(q, "false"))
        self.assertFalse(is_objective_answer_correct(q, "True"))

    def test_save_batch_answers_with_blanks(self):
        """Verify student exam API saves both blank_answers and answer_text."""
        q = Question.objects.create(
            institution=self.institution,
            exam=self.exam,
            question_type="fill_blank",
            text="Sun rises in the ____ and sets in the ____.",
            correct_answer="east, west",
            accepted_answers=[["east"], ["west"]],
            marks=4,
            order=1,
        )
        attempt = StudentAttempt.objects.create(
            institution=self.institution,
            exam=self.exam,
            student=self.student,
            status="in_progress",
        )

        token = get_token(self.student, "Student", self.institution)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        payload = {
            "answers": [
                {
                    "question_id": q.id,
                    "answer_text": "east, west",
                    "blank_answers": ["east", "west"],
                }
            ]
        }
        response = self.client.post(
            f"/api/student/attempts/{attempt.id}/save/",
            data=payload,
            format="json",
        )
        self.assertEqual(response.status_code, 200)

        ans = StudentAnswer.objects.get(attempt=attempt, question=q)
        self.assertEqual(ans.blank_answers, ["east", "west"])
        self.assertEqual(ans.answer_text, "east, west")

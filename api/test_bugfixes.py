from decimal import Decimal
from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from admins.models import AdminInstitution
from api.models import Exam, Option, Question, StudentAnswer, StudentAttempt
from api.serializers import StudentExamSerializer, StudentQuestionSerializer
from api.utils.options import clean_option_text, clean_options_list, validate_mcq_options
from api.utils.scoring import calculate_and_save_attempt_score, is_objective_answer_correct
from api.utils.validate_paper import validate_and_fix_paper


def _token(user, role, institution):
    refresh = RefreshToken.for_user(user)
    refresh['role'] = role
    refresh['institution_id'] = institution.id if institution else None
    access = refresh.access_token
    access['role'] = role
    access['institution_id'] = institution.id if institution else None
    return str(access)


class BugfixesTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin_user = User.objects.create_user(
            username="admin_test@college.edu",
            email="admin_test@college.edu",
            password="Password123!",
        )
        self.institution = AdminInstitution.objects.create(
            admin=self.admin_user,
            institution_name="Test Engineering College",
            institution_code="INST-TEST-999",
            status=AdminInstitution.STATUS_ACTIVE,
        )
        self.student_user = User.objects.create_user(
            username="student_test@college.edu",
            email="student_test@college.edu",
            password="Password123!",
        )
        from students.models import StudentProfile
        StudentProfile.objects.create(
            user=self.student_user,
            institution=self.institution,
            department="Computer Science",
            student_id="STU-TEST-001",
        )
        self.token = _token(self.student_user, "student", self.institution)

        self.exam = Exam.objects.create(
            institution=self.institution,
            created_by=self.admin_user,
            title="Cloud & Distributed Systems Exam",
            department="Computer Science",
            duration_minutes=60,
            total_marks=22,
            status=Exam.Status.PUBLISHED,
        )

        # Q1: MCQ with prefix in options (to test cleaning)
        self.q1 = Question.objects.create(
            exam=self.exam,
            institution=self.institution,
            department="Computer Science",
            order=1,
            question_type="mcq",
            difficulty="easy",
            text="Which component handles authentication in the AAA model?",
            options=["A. AuthN", "B. AuthZ", "C. Accounting", "D. Auditing"],
            correct_answer="A",
            marks=1,
        )

        # Q2: True/False
        self.q2 = Question.objects.create(
            exam=self.exam,
            institution=self.institution,
            department="Computer Science",
            order=2,
            question_type="truefalse",
            difficulty="easy",
            text="Single-Factor Authentication requires two or more evidence categories.",
            options=["True", "False"],
            correct_answer="B",
            marks=1,
        )

        # Q3: Subjective question (10 marks)
        self.q3 = Question.objects.create(
            exam=self.exam,
            institution=self.institution,
            department="Computer Science",
            order=3,
            question_type="subjective",
            difficulty="medium",
            text="Explain the three main components of the AAA model in cloud computing.",
            options=None,
            correct_answer="",
            model_answer="Comprehensive model answer about Authentication, Authorization, and Accounting in cloud computing.",
            marks=10,
        )

        # Q4: Another subjective question (10 marks)
        self.q4 = Question.objects.create(
            exam=self.exam,
            institution=self.institution,
            department="Computer Science",
            order=4,
            question_type="subjective",
            difficulty="medium",
            text="Explain Single-Factor Authentication vulnerabilities in cloud environments.",
            options=None,
            correct_answer="",
            model_answer="Comprehensive model answer detailing password vulnerability, credential stuffing, and defense-in-depth.",
            marks=10,
        )

        # Attempt
        self.attempt = StudentAttempt.objects.create(
            institution=self.institution,
            student=self.student_user,
            exam=self.exam,
            status=StudentAttempt.Status.IN_PROGRESS,
            total_score=0,
        )

    # ==========================================
    # BUG 1 TESTS: Unanswered Questions Integrity
    # ==========================================
    def test_submit_with_unanswered_questions_creates_student_answers_with_institution(self):
        """Unanswered questions must have StudentAnswer created with non-null institution without IntegrityError."""
        # Answer ONLY Q1; leave Q2, Q3, Q4 completely unanswered
        StudentAnswer.objects.create(
            institution=self.institution,
            attempt=self.attempt,
            question=self.q1,
            answer_text="AuthN",
        )

        # Call calculate_and_save_attempt_score
        result = calculate_and_save_attempt_score(self.attempt)
        self.assertIsNotNone(result)

        # Check all questions have answers and institution is properly populated
        answers = StudentAnswer.objects.filter(attempt=self.attempt)
        self.assertEqual(answers.count(), 4)
        for ans in answers:
            self.assertEqual(ans.institution_id, self.institution.id)

        # Q1 was answered correctly ('AuthN' matches 'A. AuthN' / 'A')
        q1_ans = answers.get(question=self.q1)
        self.assertTrue(q1_ans.is_correct)
        self.assertEqual(q1_ans.score_awarded, Decimal("1.00"))

        # Q2 was unanswered
        q2_ans = answers.get(question=self.q2)
        self.assertFalse(q2_ans.is_correct)
        self.assertEqual(q2_ans.score_awarded, Decimal("0.00"))

    def test_submit_with_zero_answers_succeeds(self):
        """Student submits an exam without answering any questions."""
        result = calculate_and_save_attempt_score(self.attempt)
        self.assertEqual(result["marks_obtained"], 0)
        self.assertEqual(result["percentage"], 0.0)
        self.assertFalse(result["is_passed"])

        answers = StudentAnswer.objects.filter(attempt=self.attempt)
        self.assertEqual(answers.count(), 4)
        for ans in answers:
            self.assertEqual(ans.institution_id, self.institution.id)
            self.assertEqual(ans.score_awarded, Decimal("0.00"))

    def test_submit_attempt_endpoint_idempotency(self):
        """Double submission must return 200 with serialized attempt data rather than 400 error."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token}')

        # First submission
        resp1 = self.client.post(f'/api/student/attempts/{self.attempt.id}/submit/')
        self.assertEqual(resp1.status_code, status.HTTP_200_OK)

        # Second submission (network retry / double click)
        resp2 = self.client.post(f'/api/student/attempts/{self.attempt.id}/submit/')
        self.assertEqual(resp2.status_code, status.HTTP_200_OK)
        self.assertEqual(resp1.data['id'], resp2.data['id'])

    # ==========================================
    # BUG 2 TESTS: MCQ Option Cleaning & Dedupe
    # ==========================================
    def test_clean_option_text(self):
        """Prefixes like 'A. ', 'B) ', '(C) ' must be stripped cleanly."""
        self.assertEqual(clean_option_text("A. Unauthorized"), "Unauthorized")
        self.assertEqual(clean_option_text("B) Permitted"), "Permitted")
        self.assertEqual(clean_option_text("(C) Restricted"), "Restricted")
        self.assertEqual(clean_option_text("1. First Option"), "First Option")
        self.assertEqual(clean_option_text("Apple"), "Apple")
        self.assertEqual(clean_option_text(""), "")

    def test_validate_mcq_options_rejects_duplicates(self):
        """MCQs with duplicate options must fail validation."""
        dupe_options = ["A. Unauthorized", "B. Permitted", "C. Unauthorized", "D. Permitted"]
        is_valid, errors = validate_mcq_options(dupe_options, "B")
        self.assertFalse(is_valid)
        self.assertTrue(any("Duplicate options" in err for err in errors))

        valid_options = ["A. Unauthorized", "B. Permitted", "C. Restricted", "D. Unmonitored"]
        is_valid, errors = validate_mcq_options(valid_options, "B")
        self.assertTrue(is_valid)
        self.assertEqual(len(errors), 0)

    def test_student_question_serializer_cleans_options(self):
        """StudentQuestionSerializer must strip option prefixes so the UI never doubles labels."""
        serializer = StudentQuestionSerializer(self.q1)
        cleaned_opts = serializer.data['options']
        self.assertEqual(cleaned_opts, ["AuthN", "AuthZ", "Accounting", "Auditing"])

    def test_objective_answer_evaluation_with_cleaned_and_raw_matches(self):
        """Student submitting clean text or letter matches correct option even if DB had prefixes."""
        # Clean text match
        self.assertTrue(is_objective_answer_correct(self.q1, "AuthN"))
        # Raw prefixed match
        self.assertTrue(is_objective_answer_correct(self.q1, "A. AuthN"))
        # Letter match
        self.assertTrue(is_objective_answer_correct(self.q1, "A"))
        # Case insensitive
        self.assertTrue(is_objective_answer_correct(self.q1, "authn"))
        # Incorrect option
        self.assertFalse(is_objective_answer_correct(self.q1, "AuthZ"))

    # ==========================================
    # BUG 3 TESTS: Marks Header Serialization
    # ==========================================
    def test_marks_serialized_as_numbers_not_strings(self):
        """Marks in StudentQuestionSerializer and StudentExamSerializer must be numeric float."""
        q_serializer = StudentQuestionSerializer(self.q1)
        self.assertIsInstance(q_serializer.data['marks'], float)
        self.assertEqual(q_serializer.data['marks'], 1.0)

        exam_serializer = StudentExamSerializer(self.exam)
        self.assertIsInstance(exam_serializer.data['total_marks'], float)
        self.assertEqual(exam_serializer.data['total_marks'], 22.0)

    # ==========================================
    # BUG 4 TESTS: Subjective Validation & Fix
    # ==========================================
    def test_validate_and_fix_paper_rejects_empty_mcq_and_handles_subjective(self):
        """validate_and_fix_paper rejects invalid MCQ options and preserves model_answer."""
        raw_paper = {
            "questions": [
                {
                    "type": "mcq",
                    "difficulty": "medium",
                    "text": "Valid question text?",
                    "options": ["A. Opt 1", "B. Opt 2", "C. Opt 3", "D. Opt 4"],
                    "correct_answer": "A",
                    "marks": 1,
                },
                {
                    "type": "mcq",
                    "difficulty": "medium",
                    "text": "Bad question with duplicates?",
                    "options": ["A. Same", "B. Same", "C. Diff 1", "D. Diff 2"],
                    "correct_answer": "A",
                    "marks": 1,
                },
                {
                    "type": "subjective",
                    "difficulty": "hard",
                    "text": "Explain distributed consensus algorithms in detail.",
                    "options": None,
                    "correct_answer": "",
                    "model_answer": "Paxos and Raft are distributed consensus algorithms that guarantee safety under network partitions.",
                    "marks": 10,
                }
            ]
        }
        fixed_data, actual_marks = validate_and_fix_paper(raw_paper)
        questions = fixed_data["questions"]

        # The bad question with duplicates must be rejected, leaving 2 valid questions
        self.assertEqual(len(questions), 2)
        # First question options must be cleaned
        self.assertEqual(questions[0]["options"], ["Opt 1", "Opt 2", "Opt 3", "Opt 4"])
        # Subjective question options must be None and model_answer preserved
        self.assertIsNone(questions[1]["options"])
        self.assertIn("Paxos and Raft", questions[1]["model_answer"])
        self.assertEqual(actual_marks, 11)

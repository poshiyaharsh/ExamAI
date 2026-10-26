from decimal import Decimal
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from admins.models import AdminDepartment, AdminInstitution, AdminProfile
from api.models import (
    Exam,
    Question,
    StudentAnswer,
    StudentAttempt,
    EvaluationChangeAuditLog,
    Notification,
)
from faculty.models import FacultyProfile
from students.models import StudentProfile

User = get_user_model()


def get_jwt(user, role, institution):
    refresh = RefreshToken.for_user(user)
    refresh["role"] = role
    refresh["institution_id"] = institution.id if institution else None
    access = refresh.access_token
    access["role"] = role
    access["institution_id"] = institution.id if institution else None
    return str(access)


class FacultyReviewDecoupledTests(TestCase):
    def setUp(self):
        self.client = APIClient()

        # Admin
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

        # Faculty 1 (CS)
        self.faculty_1 = User.objects.create_user(
            username="faculty1@tech.edu",
            email="faculty1@tech.edu",
            password="password123",
            first_name="Alice",
            last_name="Smith",
        )
        self.faculty_1_profile = FacultyProfile.objects.create(
            user=self.faculty_1,
            institution=self.institution,
            department="Computer Science",
            designation="Professor",
        )
        self.token_faculty_1 = get_jwt(self.faculty_1, "faculty", self.institution)

        # Faculty 2 (ME)
        self.faculty_2 = User.objects.create_user(
            username="faculty2@tech.edu",
            email="faculty2@tech.edu",
            password="password123",
            first_name="Bob",
            last_name="Jones",
        )
        self.faculty_2_profile = FacultyProfile.objects.create(
            user=self.faculty_2,
            institution=self.institution,
            department="Mechanical Engineering",
            designation="Associate Professor",
        )
        self.token_faculty_2 = get_jwt(self.faculty_2, "faculty", self.institution)

        # Student (CS)
        self.student_user = User.objects.create_user(
            username="student@tech.edu",
            email="student@tech.edu",
            password="password123",
            first_name="Charlie",
            last_name="Brown",
        )
        self.student_profile = StudentProfile.objects.create(
            user=self.student_user,
            institution=self.institution,
            department="Computer Science",
            student_id="CS202",
        )
        self.token_student = get_jwt(self.student_user, "student", self.institution)

        # Create Exam by Faculty 1
        self.exam = Exam.objects.create(
            institution=self.institution,
            title="Data Structures & Algorithms",
            created_by=self.faculty_1,
            department="Computer Science",
            status=Exam.Status.PUBLISHED,
            total_marks=20,
            duration_minutes=60,
        )

        # Questions: 1 MCQ, 1 FillBlank, 1 ShortAnswer (legacy uppercase type), 1 LongAnswer
        self.q_mcq = Question.objects.create(
            institution=self.institution,
            exam=self.exam,
            order=1,
            question_type="mcq",
            text="What is time complexity of binary search?",
            marks=5,
            options=["O(1)", "O(log n)", "O(n)", "O(n^2)"],
            correct_answer="O(log n)",
        )
        self.q_fill = Question.objects.create(
            institution=self.institution,
            exam=self.exam,
            order=2,
            question_type="fill_blank",
            text="Python was created by Guido van _____.",
            marks=5,
            accepted_answers=[["Rossum"]],
        )
        self.q_short = Question.objects.create(
            institution=self.institution,
            exam=self.exam,
            order=3,
            question_type="SHORT_ANSWER",  # legacy uppercase type
            text="Explain difference between stack and queue.",
            marks=5,
            model_answer="Stack is LIFO, Queue is FIFO.",
            rubric="2 marks for LIFO/FIFO, 3 marks for examples.",
        )
        self.q_long = Question.objects.create(
            institution=self.institution,
            exam=self.exam,
            order=4,
            question_type="LONG_ANSWER",  # legacy uppercase type
            text="Describe quicksort algorithm in detail.",
            marks=5,
            model_answer="Quicksort divides and conquers using pivot.",
        )

        # Create an in-progress attempt for student
        self.attempt = StudentAttempt.objects.create(
            institution=self.institution,
            exam=self.exam,
            student=self.student_user,
            attempt_number=1,
            status=StudentAttempt.Status.IN_PROGRESS,
            question_order=[self.q_mcq.id, self.q_fill.id, self.q_short.id, self.q_long.id],
            max_score=20,
        )

    def test_submit_exam_with_ollama_down(self):
        """
        When student submits an exam and Ollama is completely down/stopped,
        submit succeeds immediately without error, objective answers are evaluated,
        and subjective answers wait for faculty review.
        """
        # Save answers for MCQ, fill_blank, and short_answer (leave long_answer empty)
        StudentAnswer.objects.create(
            institution=self.institution,
            attempt=self.attempt,
            question=self.q_mcq,
            answer_text="O(log n)",
        )
        StudentAnswer.objects.create(
            institution=self.institution,
            attempt=self.attempt,
            question=self.q_fill,
            blank_answers=["Rossum"],
        )
        StudentAnswer.objects.create(
            institution=self.institution,
            attempt=self.attempt,
            question=self.q_short,
            answer_text="Stack uses LIFO order whereas queue uses FIFO order.",
        )

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token_student}")
        
        # Even if Ollama or external LLM raises ConnectionError, submit MUST NOT fail
        with patch("urllib.request.urlopen", side_effect=Exception("Ollama unreachable")):
            url = f"/api/student/attempts/{self.attempt.id}/submit/"
            response = self.client.post(url)
            self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.attempt.refresh_from_db()
        # Attempt should be SUBMITTED (awaiting faculty manual review of subjective question)
        self.assertEqual(self.attempt.status, StudentAttempt.Status.SUBMITTED)
        # Total score reflects 5 (MCQ) + 5 (Fill) = 10
        self.assertEqual(self.attempt.total_score, 10.0)

        # MCQ answer should be reviewed and correct
        ans_mcq = StudentAnswer.objects.get(attempt=self.attempt, question=self.q_mcq)
        self.assertEqual(ans_mcq.evaluation_status, StudentAnswer.EvaluationStatus.REVIEWED)
        self.assertTrue(ans_mcq.is_correct)
        self.assertEqual(ans_mcq.score_awarded, 5.0)

        # Short answer should be pending faculty review
        ans_short = StudentAnswer.objects.get(attempt=self.attempt, question=self.q_short)
        self.assertEqual(ans_short.evaluation_status, StudentAnswer.EvaluationStatus.PENDING_REVIEW)
        self.assertIsNone(ans_short.is_correct)
        self.assertEqual(ans_short.score_awarded, 0.0)

        # Long answer (unattempted) should have been automatically created with empty score
        ans_long = StudentAnswer.objects.get(attempt=self.attempt, question=self.q_long)
        self.assertEqual(ans_long.evaluation_status, StudentAnswer.EvaluationStatus.REVIEWED)
        self.assertFalse(ans_long.is_correct)
        self.assertEqual(ans_long.score_awarded, 0.0)

    def test_faculty_scoping_enforcement(self):
        """
        Faculty A can access attempts of exams they created.
        Faculty B (different faculty / department) cannot access them (returns 403 or 404).
        """
        # Faculty 1 (owner) can list attempts
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token_faculty_1}")
        url = f"/api/faculty/exams/{self.exam.id}/attempts/"
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data["attempts"]), 1)

        # Faculty 2 (not owner) cannot list attempts
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token_faculty_2}")
        resp2 = self.client.get(url)
        self.assertIn(resp2.status_code, [status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND])

        # Faculty 2 cannot view attempt detail
        detail_url = f"/api/faculty/attempts/{self.attempt.id}/"
        resp3 = self.client.get(detail_url)
        self.assertIn(resp3.status_code, [status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND])

    def test_faculty_manual_grading_validation(self):
        """
        Faculty can manually grade an answer.
        Validation rejects scores < 0 or > question.marks with HTTP 400.
        Valid score updates score_awarded and recalculates attempt total_score.
        """
        ans = StudentAnswer.objects.create(
            institution=self.institution,
            attempt=self.attempt,
            question=self.q_short,
            answer_text="Stack is LIFO and Queue is FIFO.",
            evaluation_status=StudentAnswer.EvaluationStatus.PENDING_REVIEW,
        )

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token_faculty_1}")
        url = f"/api/faculty/answers/{ans.id}/manual-grade/"

        # Score exceeding question marks (6 > 5) should fail with 400
        resp_invalid = self.client.post(url, {"score": 6.0, "feedback": "Too generous"})
        self.assertEqual(resp_invalid.status_code, status.HTTP_400_BAD_REQUEST)

        # Negative score should fail with 400
        resp_neg = self.client.post(url, {"score": -1.0})
        self.assertEqual(resp_neg.status_code, status.HTTP_400_BAD_REQUEST)

        # Valid score (4.5 / 5) succeeds
        resp_valid = self.client.post(url, {"score": 4.5, "feedback": "Good explanation"})
        self.assertEqual(resp_valid.status_code, status.HTTP_200_OK)

        ans.refresh_from_db()
        self.assertEqual(ans.score_awarded, 4.5)
        self.assertEqual(ans.evaluation_status, StudentAnswer.EvaluationStatus.REVIEWED)
        self.assertEqual(ans.teacher_feedback, "Good explanation")

        self.attempt.refresh_from_db()
        self.assertEqual(self.attempt.total_score, 4.5)

    def test_faculty_finalize_grading(self):
        """
        Faculty finalizes attempt grading.
        Status transitions to EVALUATED, and total score is confirmed.
        """
        # Create answers
        StudentAnswer.objects.create(
            institution=self.institution,
            attempt=self.attempt,
            question=self.q_mcq,
            answer_text="O(log n)",
            score_awarded=5.0,
            is_correct=True,
            evaluation_status=StudentAnswer.EvaluationStatus.REVIEWED,
        )
        StudentAnswer.objects.create(
            institution=self.institution,
            attempt=self.attempt,
            question=self.q_short,
            answer_text="Stack is LIFO and Queue is FIFO.",
            score_awarded=4.0,
            evaluation_status=StudentAnswer.EvaluationStatus.REVIEWED,
        )

        self.attempt.status = StudentAttempt.Status.SUBMITTED
        self.attempt.save()

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token_faculty_1}")
        url = f"/api/faculty/attempts/{self.attempt.id}/finalize/"
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["status"], "evaluated")
        self.assertEqual(resp.data["total_score"], 9.0)

        self.attempt.refresh_from_db()
        self.assertEqual(self.attempt.status, StudentAttempt.Status.EVALUATED)
        self.assertEqual(self.attempt.total_score, 9.0)

    def test_ai_suggestion_non_blocking_and_safe(self):
        """
        AI Suggestion endpoint:
        - When Ollama is unreachable/fails, returns 200 with suggestion_status: 'failed'.
        - When AI succeeds, saves only to ai_suggested_score and ai_suggested_feedback.
          Does NOT mutate score_awarded or mark answer as reviewed.
        """
        ans = StudentAnswer.objects.create(
            institution=self.institution,
            attempt=self.attempt,
            question=self.q_short,
            answer_text="Stack is LIFO and Queue is FIFO.",
            score_awarded=0.0,
            evaluation_status=StudentAnswer.EvaluationStatus.PENDING_REVIEW,
        )

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token_faculty_1}")
        url = f"/api/faculty/answers/{ans.id}/suggest-grade/"

        # 1. Failure case: Ollama down
        with patch("api.faculty_evaluation.generate_ai_grading_suggestion", return_value=(False, None, "", "Ollama connection refused")):
            resp_fail = self.client.post(url)
            self.assertEqual(resp_fail.status_code, status.HTTP_200_OK)
            self.assertEqual(resp_fail.data["suggestion_status"], "failed")

        ans.refresh_from_db()
        # Stored score and status remain unchanged
        self.assertEqual(ans.score_awarded, 0.0)
        self.assertEqual(ans.evaluation_status, StudentAnswer.EvaluationStatus.PENDING_REVIEW)

        # 2. Success case: AI returns suggestion
        with patch("api.faculty_evaluation.generate_ai_grading_suggestion", return_value=(True, 4.0, "Accurate LIFO/FIFO definition", "")):
            resp_success = self.client.post(url)
            self.assertEqual(resp_success.status_code, status.HTTP_200_OK)
            self.assertEqual(resp_success.data["suggestion_status"], "ready")
            self.assertEqual(resp_success.data["ai_suggested_score"], 4.0)

        ans.refresh_from_db()
        # Verified: AI suggestion is saved in suggested fields, but score_awarded is NOT mutated
        self.assertEqual(ans.ai_suggested_score, 4.0)
        self.assertEqual(ans.ai_suggested_feedback, "Accurate LIFO/FIFO definition")
        self.assertEqual(ans.score_awarded, 0.0)
        self.assertEqual(ans.evaluation_status, StudentAnswer.EvaluationStatus.PENDING_REVIEW)

    def test_canonical_types_and_unattempted_questions(self):
        """
        Faculty review detail view handles:
        - Legacy uppercase question types (SHORT_ANSWER, LONG_ANSWER) canonicalized cleanly.
        - Missing StudentAnswer records for unattempted questions dynamically created.
        """
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token_faculty_1}")
        url = f"/api/faculty/attempts/{self.attempt.id}/"
        resp = self.client.get(url)

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        answers = resp.data["answers"]
        # All 4 questions from question_order should be present
        self.assertEqual(len(answers), 4)

        # Check types are canonicalized to lowercase
        q_types = [a["question_type"] for a in answers]
        self.assertIn("short_answer", q_types)
        self.assertIn("long_answer", q_types)
        self.assertIn("mcq", q_types)
        self.assertIn("fill_blank", q_types)

    def test_override_all_question_types(self):
        """
        Faculty can override evaluation on all question types (MCQ, Fill-blank, Subjective).
        Overrides update final_marks, final_is_correct, final_comment, increment version,
        and write audit logs.
        """
        # Create answers with initial automatic grading
        ans_mcq = StudentAnswer.objects.create(
            institution=self.institution,
            attempt=self.attempt,
            question=self.q_mcq,
            answer_text="O(n)",
            auto_marks=0.0,
            auto_is_correct=False,
            auto_source="rule",
            score_awarded=0.0,
            is_correct=False,
            evaluation_status=StudentAnswer.EvaluationStatus.REVIEWED,
        )
        ans_fill = StudentAnswer.objects.create(
            institution=self.institution,
            attempt=self.attempt,
            question=self.q_fill,
            blank_answers=["van Rossum"],
            auto_marks=0.0,
            auto_is_correct=False,
            auto_source="rule",
            score_awarded=0.0,
            is_correct=False,
            evaluation_status=StudentAnswer.EvaluationStatus.REVIEWED,
        )
        ans_short = StudentAnswer.objects.create(
            institution=self.institution,
            attempt=self.attempt,
            question=self.q_short,
            answer_text="Stack is LIFO and Queue is FIFO.",
            auto_marks=2.0,
            auto_is_correct=False,
            auto_source="ai",
            score_awarded=2.0,
            is_correct=False,
            evaluation_status=StudentAnswer.EvaluationStatus.REVIEWED,
        )

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token_faculty_1}")

        # 1. Override MCQ: 0.0 -> 5.0 (Accepted alternative)
        url_mcq = f"/api/faculty/attempts/{self.attempt.id}/questions/{self.q_mcq.id}/override/"
        resp_mcq = self.client.patch(url_mcq, {
            "final_marks": 5.0,
            "final_is_correct": "correct",
            "final_comment": "Accepted alternative answer due to problem statement ambiguity",
            "reason": "Alternative option accepted",
            "version": 1,
        })
        self.assertEqual(resp_mcq.status_code, status.HTTP_200_OK)
        self.assertEqual(resp_mcq.data["version"], 2)

        ans_mcq.refresh_from_db()
        self.assertTrue(ans_mcq.overridden)
        self.assertEqual(ans_mcq.final_marks, 5.0)
        self.assertEqual(ans_mcq.effective_marks, 5.0)
        self.assertEqual(ans_mcq.final_is_correct, "correct")
        self.assertEqual(ans_mcq.effective_is_correct, True)
        self.assertEqual(ans_mcq.overridden_by, self.faculty_1)

        # 2. Override Fill in Blank: 0.0 -> 4.0 (partial credit)
        url_fill = f"/api/faculty/attempts/{self.attempt.id}/questions/{self.q_fill.id}/override/"
        resp_fill = self.client.patch(url_fill, {
            "final_marks": 4.0,
            "final_is_correct": "partial",
            "final_comment": "Included prefix van, awarding partial credit",
            "reason": "Minor syntax variance",
            "version": 2,
        })
        self.assertEqual(resp_fill.status_code, status.HTTP_200_OK)
        self.assertEqual(resp_fill.data["version"], 3)

        ans_fill.refresh_from_db()
        self.assertTrue(ans_fill.overridden)
        self.assertEqual(ans_fill.final_marks, 4.0)
        self.assertEqual(ans_fill.effective_marks, 4.0)

        # 3. Override Short Answer: 2.0 -> 5.0 (full marks)
        url_short = f"/api/faculty/attempts/{self.attempt.id}/questions/{self.q_short.id}/override/"
        resp_short = self.client.patch(url_short, {
            "final_marks": 5.0,
            "final_is_correct": "correct",
            "final_comment": "Clear and concise explanation",
            "reason": "AI scored too strictly",
            "version": 3,
        })
        self.assertEqual(resp_short.status_code, status.HTTP_200_OK)
        self.assertEqual(resp_short.data["version"], 4)

        # Verify audit logs created
        logs = EvaluationChangeAuditLog.objects.filter(attempt=self.attempt).order_by("created_at")
        self.assertEqual(logs.count(), 3)
        self.assertEqual(logs[0].question, self.q_mcq)
        self.assertEqual(logs[0].old_marks, 0.0)
        self.assertEqual(logs[0].new_marks, 5.0)
        self.assertEqual(logs[0].reason, "Alternative option accepted")
        self.assertEqual(logs[0].changed_by, self.faculty_1)

        self.assertEqual(logs[1].question, self.q_fill)
        self.assertEqual(logs[1].old_marks, 0.0)
        self.assertEqual(logs[1].new_marks, 4.0)
        self.assertEqual(logs[1].new_correctness, "partial")

        # Recalculated total
        self.attempt.refresh_from_db()
        self.assertEqual(self.attempt.final_total, 14.0)
        self.assertEqual(self.attempt.total_score, 14.0)

    def test_override_validation_bounds_and_reason(self):
        """
        Override endpoint validates:
        - 0 <= marks <= question.marks (rejects outside with HTTP 400).
        - requires non-empty reason when deviating from auto evaluation.
        """
        ans = StudentAnswer.objects.create(
            institution=self.institution,
            attempt=self.attempt,
            question=self.q_mcq,
            answer_text="O(n)",
            auto_marks=0.0,
            auto_is_correct=False,
            auto_source="rule",
            score_awarded=0.0,
            is_correct=False,
        )

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token_faculty_1}")
        url = f"/api/faculty/attempts/{self.attempt.id}/questions/{self.q_mcq.id}/override/"

        # Score > question.marks (6.0 > 5.0)
        resp_over = self.client.patch(url, {
            "final_marks": 6.0,
            "final_is_correct": "correct",
            "reason": "Extra credit",
            "version": 1,
        })
        self.assertEqual(resp_over.status_code, status.HTTP_400_BAD_REQUEST)

        # Negative score (-1.0)
        resp_neg = self.client.patch(url, {
            "final_marks": -1.0,
            "final_is_correct": "wrong",
            "reason": "Penalty",
            "version": 1,
        })
        self.assertEqual(resp_neg.status_code, status.HTTP_400_BAD_REQUEST)

        # Changing score without providing reason
        resp_no_reason = self.client.patch(url, {
            "final_marks": 5.0,
            "final_is_correct": "correct",
            "reason": "",
            "version": 1,
        })
        self.assertEqual(resp_no_reason.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Reason is required", resp_no_reason.data["detail"])

    def test_concurrency_optimistic_locking_409(self):
        """
        Optimistic concurrency check rejects requests with outdated attempt version with HTTP 409 Conflict.
        """
        self.attempt.version = 3
        self.attempt.save()

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token_faculty_1}")
        url = f"/api/faculty/attempts/{self.attempt.id}/questions/{self.q_mcq.id}/override/"

        # Send stale version 2
        resp = self.client.patch(url, {
            "final_marks": 5.0,
            "final_is_correct": "correct",
            "reason": "Alternative option accepted",
            "version": 2,
        })
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(resp.data["latest_version"], 3)

    def test_reset_override_to_auto(self):
        """
        Faculty can reset an overridden question back to automatic evaluation.
        Clears final_marks, sets overridden=False, updates effective_marks, logs audit.
        """
        ans = StudentAnswer.objects.create(
            institution=self.institution,
            attempt=self.attempt,
            question=self.q_mcq,
            answer_text="O(n)",
            auto_marks=0.0,
            auto_is_correct=False,
            auto_source="rule",
            score_awarded=5.0,
            is_correct=True,
            overridden=True,
            final_marks=5.0,
            final_is_correct="correct",
            final_comment="Temporary override",
            overridden_by=self.faculty_1,
        )
        self.attempt.version = 1
        self.attempt.save()

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token_faculty_1}")
        url = f"/api/faculty/attempts/{self.attempt.id}/questions/{self.q_mcq.id}/reset/"

        resp = self.client.post(url, {"version": 1})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["version"], 2)

        ans.refresh_from_db()
        self.assertFalse(ans.overridden)
        self.assertIsNone(ans.final_marks)
        self.assertEqual(ans.final_is_correct, "")
        self.assertEqual(ans.effective_marks, 0.0)

        # Audit log created
        log = EvaluationChangeAuditLog.objects.filter(attempt=self.attempt, question=self.q_mcq).last()
        self.assertIsNotNone(log)
        self.assertEqual(log.old_marks, 5.0)
        self.assertEqual(log.new_marks, 0.0)
        self.assertIn("Reset to automatic evaluation", log.reason)

    def test_finalize_review_and_student_notification(self):
        """
        Finalizing review transitions review_status to finalized, sets finalized_at,
        creates an in-app notification for the student, and updates attempt status to evaluated.
        """
        StudentAnswer.objects.create(
            institution=self.institution,
            attempt=self.attempt,
            question=self.q_mcq,
            score_awarded=5.0,
            auto_marks=5.0,
            is_correct=True,
            evaluation_status=StudentAnswer.EvaluationStatus.REVIEWED,
        )
        self.attempt.status = StudentAttempt.Status.SUBMITTED
        self.attempt.review_status = StudentAttempt.ReviewStatus.IN_REVIEW
        self.attempt.save()

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token_faculty_1}")
        url = f"/api/faculty/attempts/{self.attempt.id}/finalize/"

        resp = self.client.post(url, {"version": 1})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["review_status"], "finalized")

        self.attempt.refresh_from_db()
        self.assertEqual(self.attempt.review_status, StudentAttempt.ReviewStatus.FINALIZED)
        self.assertEqual(self.attempt.reviewed_by, self.faculty_1)
        self.assertIsNotNone(self.attempt.finalized_at)
        self.assertEqual(self.attempt.status, StudentAttempt.Status.EVALUATED)

        # Verify student notification was dispatched
        notif = Notification.objects.filter(user=self.student_user, institution=self.institution).first()
        self.assertIsNotNone(notif)
        self.assertIn(self.exam.title, notif.title)
        self.assertEqual(notif.type, Notification.NotificationType.SUCCESS)

    def test_approve_as_is(self):
        """
        Faculty can approve results as-is with one click.
        Attempt transitions to finalized immediately without question modifications.
        """
        self.attempt.status = StudentAttempt.Status.SUBMITTED
        self.attempt.review_status = StudentAttempt.ReviewStatus.AUTO_EVALUATED
        self.attempt.save()

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token_faculty_1}")
        url = f"/api/faculty/attempts/{self.attempt.id}/approve-as-is/"

        resp = self.client.post(url, {"version": 1})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["review_status"], "finalized")

        self.attempt.refresh_from_db()
        self.assertEqual(self.attempt.review_status, StudentAttempt.ReviewStatus.FINALIZED)
        self.assertEqual(self.attempt.reviewed_by, self.faculty_1)
        self.assertIsNotNone(self.attempt.finalized_at)

    def test_reopen_review(self):
        """
        Faculty can reopen a finalized review back to in_review.
        """
        self.attempt.review_status = StudentAttempt.ReviewStatus.FINALIZED
        self.attempt.finalized_at = timezone.now()
        self.attempt.reviewed_by = self.faculty_1
        self.attempt.version = 1
        self.attempt.save()

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token_faculty_1}")
        url = f"/api/faculty/attempts/{self.attempt.id}/reopen/"

        resp = self.client.post(url, {"version": 1, "reason": "Need to re-check student submission"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["review_status"], "in_review")

        self.attempt.refresh_from_db()
        self.assertEqual(self.attempt.review_status, StudentAttempt.ReviewStatus.IN_REVIEW)
        self.assertEqual(self.attempt.version, 2)

    def test_student_results_view_privacy_and_provisional(self):
        """
        Student results endpoint:
        - Shows provisional banner (is_provisional=True) when review_status is not finalized.
        - Shows finalized banner when finalized.
        - Exposes is_overridden and faculty_comment on overridden questions.
        - Never leaks rubrics or model answers to students.
        """
        ans = StudentAnswer.objects.create(
            institution=self.institution,
            attempt=self.attempt,
            question=self.q_short,
            answer_text="Stack is LIFO, queue is FIFO.",
            auto_marks=2.0,
            auto_is_correct=False,
            auto_source="ai",
            score_awarded=4.5,
            is_correct=True,
            overridden=True,
            final_marks=4.5,
            final_is_correct="correct",
            final_comment="Great technical explanation.",
            evaluation_status=StudentAnswer.EvaluationStatus.REVIEWED,
        )

        self.attempt.status = StudentAttempt.Status.SUBMITTED
        self.attempt.review_status = StudentAttempt.ReviewStatus.AUTO_EVALUATED
        self.attempt.save()

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token_student}")
        url = f"/api/student/attempts/{self.attempt.id}/"

        # 1. Provisional view
        resp_prov = self.client.get(url)
        self.assertEqual(resp_prov.status_code, status.HTTP_200_OK)
        self.assertTrue(resp_prov.data.get("is_provisional"))
        res_status = resp_prov.data.get("result_status", {})
        self.assertTrue(res_status.get("is_provisional"))
        self.assertTrue("Provisional" in res_status.get("label", "") or "Provisional" in res_status.get("sub_label", ""))

        # 2. Finalize attempt
        self.attempt.review_status = StudentAttempt.ReviewStatus.FINALIZED
        self.attempt.finalized_at = timezone.now()
        self.attempt.reviewed_by = self.faculty_1
        self.attempt.save()

        resp_final = self.client.get(url)
        self.assertEqual(resp_final.status_code, status.HTTP_200_OK)
        self.assertFalse(resp_final.data.get("is_provisional"))

        # Find answer in response
        student_answers = resp_final.data.get("answers", [])
        q_ans = next((a for a in student_answers if a.get("question") == self.q_short.id or a.get("question_id") == self.q_short.id), None)
        self.assertIsNotNone(q_ans)
        self.assertTrue(q_ans.get("is_overridden"))
        self.assertEqual(q_ans.get("faculty_comment"), "Great technical explanation.")
        self.assertEqual(q_ans.get("score_awarded"), 4.5)

        # Rubrics and audit logs must NOT be exposed
        self.assertNotIn("rubric", q_ans)
        self.assertNotIn("audit_history", q_ans)


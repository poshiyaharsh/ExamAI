import logging
from django.db import transaction
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from api.models import Exam, StudentAnswer, StudentAttempt
from api.permissions import IsFacultyUser
from api.tenant import get_user_institution
from api.evaluation import evaluate_attempt_subjectives
from api.utils.evaluation_service import evaluate_subjective_chain

logger = logging.getLogger(__name__)


class FacultyEvaluationBaseView(APIView):
    permission_classes = [IsAuthenticated, IsFacultyUser]

    def get_tenant(self, request):
        return getattr(request, 'tenant', None) or get_user_institution(request.user)


class FacultyExamAttemptsListView(FacultyEvaluationBaseView):
    """
    List all student attempts for a specific exam owned by the faculty's institution.
    """
    def get(self, request, exam_id):
        tenant = self.get_tenant(request)
        if not tenant:
            return Response({'detail': 'No active institution found.'}, status=status.HTTP_404_NOT_FOUND)

        exam = Exam.objects.filter(id=exam_id, institution=tenant).first()
        if not exam:
            return Response({'detail': 'Exam not found.'}, status=status.HTTP_404_NOT_FOUND)

        attempts = StudentAttempt.objects.filter(
            exam=exam,
            institution=tenant,
        ).select_related('student').order_by('-submitted_at', '-started_at')

        data = []
        for att in attempts:
            data.append({
                'id': att.id,
                'student_id': att.student_id,
                'student_name': f"{att.student.first_name} {att.student.last_name}".strip() or att.student.username,
                'student_email': att.student.email,
                'started_at': att.started_at,
                'submitted_at': att.submitted_at,
                'status': att.status,
                'total_score': att.total_score,
                'exam_total_marks': exam.total_marks,
            })
        return Response({'exam_id': exam.id, 'exam_title': exam.title, 'attempts': data})


class FacultyAttemptDetailView(FacultyEvaluationBaseView):
    """
    Detailed attempt breakdown for faculty review, showing all answers, scores,
    and evaluation provenance (model, provider, status, technical errors).
    """
    def get(self, request, attempt_id):
        tenant = self.get_tenant(request)
        if not tenant:
            return Response({'detail': 'No active institution found.'}, status=status.HTTP_404_NOT_FOUND)

        attempt = StudentAttempt.objects.filter(
            id=attempt_id,
            institution=tenant,
        ).select_related('exam', 'student').first()

        if not attempt:
            return Response({'detail': 'Attempt not found.'}, status=status.HTTP_404_NOT_FOUND)

        answers = StudentAnswer.objects.filter(
            attempt=attempt,
            institution=tenant,
        ).select_related('question').order_by('question_id')

        ans_data = []
        for ans in answers:
            ans_data.append({
                'id': ans.id,
                'question_id': ans.question_id,
                'question_text': ans.question.text,
                'question_type': ans.question.question_type,
                'marks': float(ans.question.marks or 1.0),
                'model_answer': getattr(ans.question, 'model_answer', ''),
                'rubric': getattr(ans.question, 'rubric', ''),
                'accepted_answers': getattr(ans.question, 'accepted_answers', []),
                'correct_answer': ans.question.correct_answer,
                'student_answer': ans.answer_text,
                'blank_answers': getattr(ans, 'blank_answers', []),
                'is_correct': ans.is_correct,
                'score_awarded': ans.score_awarded,
                'ai_feedback': ans.ai_feedback,
                'teacher_feedback': getattr(ans, 'teacher_feedback', ''),
                'ai_suggested_score': getattr(ans, 'ai_suggested_score', None),
                'ai_suggested_feedback': getattr(ans, 'ai_suggested_feedback', ''),
                'evaluation_status': ans.evaluation_status,
                'evaluation_provider': ans.evaluation_provider,
                'evaluation_model': ans.evaluation_model,
                'technical_error': ans.technical_error,
            })

        return Response({
            'attempt_id': attempt.id,
            'exam_id': attempt.exam_id,
            'exam_title': attempt.exam.title,
            'exam_total_marks': attempt.exam.total_marks,
            'student_name': f"{attempt.student.first_name} {attempt.student.last_name}".strip() or attempt.student.username,
            'student_email': attempt.student.email,
            'status': attempt.status,
            'total_score': attempt.total_score,
            'submitted_at': attempt.submitted_at,
            'answers': ans_data,
        })


class FacultyReevaluateAttemptView(FacultyEvaluationBaseView):
    """
    Re-evaluates all subjective answers for a given student attempt.
    """
    def post(self, request, attempt_id):
        tenant = self.get_tenant(request)
        if not tenant:
            return Response({'detail': 'No active institution found.'}, status=status.HTTP_404_NOT_FOUND)

        attempt = StudentAttempt.objects.filter(id=attempt_id, institution=tenant).first()
        if not attempt:
            return Response({'detail': 'Attempt not found.'}, status=status.HTTP_404_NOT_FOUND)

        force = bool(request.data.get('force', False))
        evaluate_attempt_subjectives(attempt.id, force=force)

        # Refetch fresh values
        attempt.refresh_from_db()
        return Response({
            'detail': 'Attempt subjective evaluation completed successfully.',
            'attempt_id': attempt.id,
            'status': attempt.status,
            'total_score': attempt.total_score,
        })


class FacultyReevaluateAnswerView(FacultyEvaluationBaseView):
    """
    Re-evaluates a single subjective answer using the fallback chain.
    """
    def post(self, request, answer_id):
        tenant = self.get_tenant(request)
        if not tenant:
            return Response({'detail': 'No active institution found.'}, status=status.HTTP_404_NOT_FOUND)

        answer = StudentAnswer.objects.filter(
            id=answer_id,
            institution=tenant,
        ).select_related('attempt', 'question', 'attempt__exam').first()

        if not answer:
            return Response({'detail': 'Answer not found.'}, status=status.HTTP_404_NOT_FOUND)

        if answer.question.question_type not in ['subjective', 'short_answer', 'long_answer']:
            return Response({'detail': 'Only subjective questions can be re-evaluated with AI.'}, status=status.HTTP_400_BAD_REQUEST)

        force = bool(request.data.get('force', False))
        res = evaluate_subjective_chain(answer, force=force)

        # Recalculate attempt totals
        with transaction.atomic():
            att = StudentAttempt.objects.select_for_update().get(id=answer.attempt_id)
            all_ans = list(StudentAnswer.objects.select_related('question').filter(attempt=att))
            att.total_score = round(sum(float(a.score_awarded or 0.0) for a in all_ans), 2)
            has_pending = any(
                a.evaluation_status in [
                    StudentAnswer.EvaluationStatus.PENDING_REVIEW,
                    StudentAnswer.EvaluationStatus.FAILED,
                ]
                for a in all_ans
                if a.question.question_type in ['subjective', 'short_answer', 'long_answer']
            )
            att.status = StudentAttempt.Status.SUBMITTED if has_pending else StudentAttempt.Status.EVALUATED
            att.save(update_fields=['total_score', 'status'])

        return Response({
            'detail': 'Answer re-evaluated successfully.',
            'answer_id': answer.id,
            'score_awarded': answer.score_awarded,
            'ai_feedback': answer.ai_feedback,
            'ai_suggested_score': answer.ai_suggested_score,
            'ai_suggested_feedback': answer.ai_suggested_feedback,
            'evaluation_status': answer.evaluation_status,
            'evaluation_provider': answer.evaluation_provider,
            'evaluation_model': answer.evaluation_model,
            'technical_error': answer.technical_error,
            'attempt_total_score': att.total_score,
            'attempt_status': att.status,
        })


class FacultySuggestGradeView(FacultyEvaluationBaseView):
    """
    Generates an optional AI grading suggestion for a subjective answer without finalizing it.
    Saves to ai_suggested_score and ai_suggested_feedback on StudentAnswer.
    """
    def post(self, request, answer_id):
        tenant = self.get_tenant(request)
        if not tenant:
            return Response({'detail': 'No active institution found.'}, status=status.HTTP_404_NOT_FOUND)

        answer = StudentAnswer.objects.filter(
            id=answer_id,
            institution=tenant,
        ).select_related('attempt', 'question').first()

        if not answer:
            return Response({'detail': 'Answer not found.'}, status=status.HTTP_404_NOT_FOUND)

        if answer.question.question_type not in ['subjective', 'short_answer', 'long_answer']:
            return Response({'detail': 'Only subjective answers can receive AI grading suggestions.'}, status=status.HTTP_400_BAD_REQUEST)

        # Call AI evaluation chain to obtain suggestion
        from .utils.evaluation_service import evaluate_subjective_chain
        res = evaluate_subjective_chain(answer, force=True)

        return Response({
            'detail': 'AI suggestion generated.',
            'answer_id': answer.id,
            'ai_suggested_score': answer.ai_suggested_score,
            'ai_suggested_feedback': answer.ai_suggested_feedback,
            'evaluation_status': answer.evaluation_status,
        })


class FacultyManualGradeAnswerView(FacultyEvaluationBaseView):
    """
    Allows a teacher to manually adjust score and feedback for an answer.
    Sets evaluation_status to 'reviewed', protecting it from being overwritten.
    """
    def patch(self, request, answer_id):
        return self._apply_grade(request, answer_id)

    def post(self, request, answer_id):
        return self._apply_grade(request, answer_id)

    def _apply_grade(self, request, answer_id):
        tenant = self.get_tenant(request)
        if not tenant:
            return Response({'detail': 'No active institution found.'}, status=status.HTTP_404_NOT_FOUND)

        answer = StudentAnswer.objects.filter(
            id=answer_id,
            institution=tenant,
        ).select_related('attempt', 'question').first()

        if not answer:
            return Response({'detail': 'Answer not found.'}, status=status.HTTP_404_NOT_FOUND)

        raw_score = request.data.get('score')
        feedback = request.data.get('feedback', '')

        if raw_score is None:
            return Response({'detail': "'score' field is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            score = float(raw_score)
        except (ValueError, TypeError):
            return Response({'detail': "'score' must be a numeric value."}, status=status.HTTP_400_BAD_REQUEST)

        max_marks = float(answer.question.marks or 10.0)
        if score < 0 or score > max_marks:
            return Response({
                'detail': f"Score must be between 0 and {max_marks} marks."
            }, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            clean_fb = str(feedback).strip()
            answer.score_awarded = round(score, 2)
            answer.ai_feedback = clean_fb
            answer.teacher_feedback = clean_fb
            answer.is_correct = (score >= (0.4 * max_marks))
            answer.evaluation_status = StudentAnswer.EvaluationStatus.REVIEWED
            answer.evaluation_provider = "manual"
            answer.evaluation_model = "teacher"
            answer.technical_error = ""
            answer.save(update_fields=[
                'score_awarded', 'ai_feedback', 'teacher_feedback', 'is_correct',
                'evaluation_status', 'evaluation_provider', 'evaluation_model', 'technical_error'
            ])

            # Recalculate attempt total score
            att = StudentAttempt.objects.select_for_update().get(id=answer.attempt_id)
            all_ans = list(StudentAnswer.objects.select_related('question').filter(attempt=att))
            att.total_score = round(sum(float(a.score_awarded or 0.0) for a in all_ans), 2)
            has_pending = any(
                a.evaluation_status in [
                    StudentAnswer.EvaluationStatus.PENDING_REVIEW,
                    StudentAnswer.EvaluationStatus.FAILED,
                ]
                for a in all_ans
                if a.question.question_type in ['subjective', 'short_answer', 'long_answer']
            )
            att.status = StudentAttempt.Status.SUBMITTED if has_pending else StudentAttempt.Status.EVALUATED
            att.save(update_fields=['total_score', 'status'])

        return Response({
            'detail': 'Manual grade saved successfully.',
            'answer_id': answer.id,
            'score_awarded': answer.score_awarded,
            'ai_feedback': answer.ai_feedback,
            'teacher_feedback': answer.teacher_feedback,
            'evaluation_status': answer.evaluation_status,
            'attempt_total_score': att.total_score,
            'attempt_status': att.status,
        })

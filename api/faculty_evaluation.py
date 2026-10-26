import logging
from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from api.models import Exam, StudentAnswer, StudentAttempt, Question
from api.permissions import IsFacultyUser
from api.tenant import get_user_institution
from api.utils.departments import get_faculty_department
from api.utils.validate_paper import canonicalize_type
from api.utils.evaluation_service import (
    evaluate_subjective_chain,
    generate_ai_grading_suggestion,
)
from api.evaluation import evaluate_attempt_subjectives

logger = logging.getLogger(__name__)


class FacultyEvaluationBaseView(APIView):
    permission_classes = [IsAuthenticated, IsFacultyUser]

    def get_tenant(self, request):
        return getattr(request, 'tenant', None) or get_user_institution(request.user)

    def verify_exam_access(self, request, exam):
        """
        Server is the source of truth (Rule 2):
        Faculty member may only access attempts of their OWN exams (same institution & department).
        Returns (is_allowed, error_response).
        """
        if not exam:
            return False, Response({'detail': 'Exam not found.'}, status=status.HTTP_404_NOT_FOUND)

        tenant = self.get_tenant(request)
        if not tenant or exam.institution_id != tenant.id:
            return False, Response({'detail': 'Exam not found.'}, status=status.HTTP_404_NOT_FOUND)

        # Faculty must be the creator of this exam
        if exam.created_by_id != request.user.id:
            return False, Response(
                {'detail': 'You can only access student attempts for exams that you created.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Department scoping
        faculty_dept = get_faculty_department(request.user)
        if faculty_dept and faculty_dept.lower() not in ('', 'unassigned'):
            if exam.department and exam.department.lower() != faculty_dept.lower():
                return False, Response(
                    {'detail': 'Department mismatch: exam belongs to another department.'},
                    status=status.HTTP_403_FORBIDDEN,
                )

        return True, None


class FacultyExamAttemptsListView(FacultyEvaluationBaseView):
    """
    List all student attempts for a specific exam owned by the requesting faculty member.
    """
    def get(self, request, exam_id):
        tenant = self.get_tenant(request)
        if not tenant:
            return Response({'detail': 'No active institution found.'}, status=status.HTTP_404_NOT_FOUND)

        exam = Exam.objects.filter(id=exam_id, institution=tenant).first()
        allowed, err_resp = self.verify_exam_access(request, exam)
        if not allowed:
            return err_resp

        attempts = StudentAttempt.objects.filter(
            exam=exam,
            institution=tenant,
        ).select_related('student').order_by('-submitted_at', '-started_at')

        data = []
        for att in attempts:
            student_name = f"{att.student.first_name} {att.student.last_name}".strip() if att.student else ""
            data.append({
                'id': att.id,
                'student_id': att.student_id,
                'student_name': student_name or (att.student.username if att.student else f"Student #{att.student_id}"),
                'student_email': att.student.email if att.student else "",
                'started_at': att.started_at,
                'submitted_at': att.submitted_at,
                'status': att.status,
                'submit_reason': att.submit_reason,
                'total_score': float(att.total_score or 0.0),
                'exam_total_marks': float(exam.total_marks or 0.0),
            })
        return Response({'exam_id': exam.id, 'exam_title': exam.title, 'attempts': data})


class FacultyAttemptDetailView(FacultyEvaluationBaseView):
    """
    Detailed attempt breakdown for faculty review, showing all exam questions,
    student answers, rubrics, model answers, scores, and evaluation status.
    Ensures that every question is included and question types are canonicalized.
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

        allowed, err_resp = self.verify_exam_access(request, attempt.exam)
        if not allowed:
            return err_resp

        exam = attempt.exam

        # Order of questions according to student's attempt order
        questions = list(exam.questions.all())
        if attempt.question_order:
            order_map = {qid: idx for idx, qid in enumerate(attempt.question_order)}
            questions.sort(key=lambda q: order_map.get(q.id, q.order or 0))
        else:
            questions.sort(key=lambda q: q.order or 0)

        existing_answers = {
            ans.question_id: ans
            for ans in StudentAnswer.objects.filter(attempt=attempt, institution=tenant).select_related('question')
        }

        ans_data = []
        for q in questions:
            ans = existing_answers.get(q.id)
            # If student never answered this question, auto-create a default StudentAnswer record
            if not ans:
                ans, _ = StudentAnswer.objects.get_or_create(
                    attempt=attempt,
                    question=q,
                    defaults={
                        'institution': tenant,
                        'answer_text': '',
                        'is_correct': False,
                        'score_awarded': 0.0,
                        'ai_feedback': 'No answer provided.',
                        'evaluation_status': StudentAnswer.EvaluationStatus.REVIEWED,
                    }
                )
                existing_answers[q.id] = ans

            canon_type = canonicalize_type(q.question_type)
            ans_data.append({
                'id': ans.id,
                'question_id': q.id,
                'question_text': q.text,
                'question_type': canon_type,
                'marks': float(q.marks or 1.0),
                'model_answer': getattr(q, 'model_answer', '') or '',
                'rubric': getattr(q, 'rubric', '') or '',
                'accepted_answers': getattr(q, 'accepted_answers', []) or [],
                'correct_answer': q.correct_answer or '',
                'student_answer': ans.answer_text or '',
                'blank_answers': getattr(ans, 'blank_answers', []) or [],
                'is_correct': ans.is_correct,
                'score_awarded': ans.score_awarded if ans.score_awarded is not None else 0.0,
                'ai_feedback': ans.ai_feedback or '',
                'teacher_feedback': getattr(ans, 'teacher_feedback', '') or '',
                'ai_suggested_score': getattr(ans, 'ai_suggested_score', None),
                'ai_suggested_feedback': getattr(ans, 'ai_suggested_feedback', '') or '',
                'evaluation_status': ans.evaluation_status,
                'evaluation_provider': ans.evaluation_provider or '',
                'evaluation_model': ans.evaluation_model or '',
                'technical_error': ans.technical_error or '',
            })

        student_name = f"{attempt.student.first_name} {attempt.student.last_name}".strip() if attempt.student else ""
        return Response({
            'attempt_id': attempt.id,
            'exam_id': exam.id,
            'exam_title': exam.title,
            'exam_total_marks': float(exam.total_marks or 0.0),
            'student_name': student_name or (attempt.student.username if attempt.student else f"Student #{attempt.student_id}"),
            'student_email': attempt.student.email if attempt.student else "",
            'status': attempt.status,
            'submit_reason': attempt.submit_reason,
            'total_score': float(attempt.total_score or 0.0),
            'submitted_at': attempt.submitted_at,
            'answers': ans_data,
        })


class FacultySuggestGradeView(FacultyEvaluationBaseView):
    """
    Generates an optional, non-blocking AI grading suggestion for a subjective answer.
    Saves to ai_suggested_score and ai_suggested_feedback on StudentAnswer.
    NEVER overwrites score_awarded or auto-finalizes marks (Rule 3).
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

        allowed, err_resp = self.verify_exam_access(request, answer.attempt.exam)
        if not allowed:
            return err_resp

        canon_type = canonicalize_type(answer.question.question_type)
        if canon_type not in ['subjective', 'short_answer', 'long_answer']:
            return Response(
                {'detail': 'Only subjective questions can receive AI grading suggestions.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        clean_ans = str(answer.answer_text or '').strip()
        if not clean_ans:
            return Response({
                'detail': 'Student submitted an empty answer.',
                'suggestion_status': 'ready',
                'answer_id': answer.id,
                'ai_suggested_score': 0.0,
                'ai_suggested_feedback': 'No answer was submitted.',
            })

        preferred_model = getattr(answer.attempt.exam, 'ai_model_used', None)
        success, suggested_score, suggested_feedback, error_reason = generate_ai_grading_suggestion(
            question=answer.question,
            student_answer=clean_ans,
            preferred_model=preferred_model,
            timeout=20,
        )

        if success and suggested_score is not None:
            answer.ai_suggested_score = round(suggested_score, 2)
            answer.ai_suggested_feedback = suggested_feedback
            answer.save(update_fields=['ai_suggested_score', 'ai_suggested_feedback'])
            return Response({
                'detail': 'AI suggestion generated successfully.',
                'suggestion_status': 'ready',
                'answer_id': answer.id,
                'ai_suggested_score': answer.ai_suggested_score,
                'ai_suggested_feedback': answer.ai_suggested_feedback,
            })
        else:
            return Response({
                'detail': 'AI suggestion unavailable.',
                'suggestion_status': 'failed',
                'error': error_reason or 'Ollama service unavailable.',
                'answer_id': answer.id,
                'ai_suggested_score': answer.ai_suggested_score,
                'ai_suggested_feedback': answer.ai_suggested_feedback or '',
            }, status=status.HTTP_200_OK)


class FacultyManualGradeAnswerView(FacultyEvaluationBaseView):
    """
    Allows a teacher to manually assign/adjust score and feedback for an answer.
    Sets evaluation_status to 'reviewed' and recalculates total score.
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
        ).select_related('attempt', 'question', 'attempt__exam').first()

        if not answer:
            return Response({'detail': 'Answer not found.'}, status=status.HTTP_404_NOT_FOUND)

        allowed, err_resp = self.verify_exam_access(request, answer.attempt.exam)
        if not allowed:
            return err_resp

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
            clean_fb = str(feedback or '').strip()
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
                if canonicalize_type(a.question.question_type) in ['subjective', 'short_answer', 'long_answer']
            )
            if not has_pending:
                att.status = StudentAttempt.Status.EVALUATED
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


class FacultyFinalizeAttemptGradingView(FacultyEvaluationBaseView):
    """
    Finalizes grading for an entire student attempt:
    - Verifies faculty ownership and department
    - Confirms all pending subjective answers as 'reviewed'
    - Recalculates total_score
    - Transitions attempt status to EVALUATED
    - Returns updated attempt payload
    """
    def post(self, request, attempt_id):
        tenant = self.get_tenant(request)
        if not tenant:
            return Response({'detail': 'No active institution found.'}, status=status.HTTP_404_NOT_FOUND)

        attempt = StudentAttempt.objects.filter(
            id=attempt_id,
            institution=tenant,
        ).select_related('exam').first()

        if not attempt:
            return Response({'detail': 'Attempt not found.'}, status=status.HTTP_404_NOT_FOUND)

        allowed, err_resp = self.verify_exam_access(request, attempt.exam)
        if not allowed:
            return err_resp

        with transaction.atomic():
            attempt = StudentAttempt.objects.select_for_update().get(id=attempt.id)
            answers = list(StudentAnswer.objects.filter(attempt=attempt).select_related('question'))

            # Mark any still pending questions as reviewed
            for ans in answers:
                if ans.evaluation_status in [
                    StudentAnswer.EvaluationStatus.PENDING_REVIEW,
                    StudentAnswer.EvaluationStatus.FAILED,
                ]:
                    ans.evaluation_status = StudentAnswer.EvaluationStatus.REVIEWED
                    ans.evaluation_provider = ans.evaluation_provider or "manual"
                    ans.evaluation_model = ans.evaluation_model or "teacher"
                    ans.score_awarded = round(float(ans.score_awarded or 0.0), 2)
                    ans.save(update_fields=[
                        'evaluation_status', 'evaluation_provider', 'evaluation_model', 'score_awarded'
                    ])

            attempt.total_score = round(sum(float(a.score_awarded or 0.0) for a in answers), 2)
            attempt.status = StudentAttempt.Status.EVALUATED
            attempt.save(update_fields=['total_score', 'status'])

        return Response({
            'detail': 'Attempt grading finalized successfully.',
            'attempt_id': attempt.id,
            'status': attempt.status,
            'total_score': attempt.total_score,
            'exam_total_marks': float(attempt.exam.total_marks or 0.0),
        })


class FacultyReevaluateAttemptView(FacultyEvaluationBaseView):
    """
    Re-evaluates all subjective answers for a given student attempt using background/safe evaluation.
    """
    def post(self, request, attempt_id):
        tenant = self.get_tenant(request)
        if not tenant:
            return Response({'detail': 'No active institution found.'}, status=status.HTTP_404_NOT_FOUND)

        attempt = StudentAttempt.objects.filter(id=attempt_id, institution=tenant).select_related('exam').first()
        if not attempt:
            return Response({'detail': 'Attempt not found.'}, status=status.HTTP_404_NOT_FOUND)

        allowed, err_resp = self.verify_exam_access(request, attempt.exam)
        if not allowed:
            return err_resp

        force = bool(request.data.get('force', False))
        evaluate_attempt_subjectives(attempt.id, force=force)

        attempt.refresh_from_db()
        return Response({
            'detail': 'Attempt evaluation refreshed.',
            'attempt_id': attempt.id,
            'status': attempt.status,
            'total_score': float(attempt.total_score or 0.0),
        })


class FacultyReevaluateAnswerView(FacultyEvaluationBaseView):
    """
    Re-evaluates a single subjective answer.
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

        allowed, err_resp = self.verify_exam_access(request, answer.attempt.exam)
        if not allowed:
            return err_resp

        canon_type = canonicalize_type(answer.question.question_type)
        if canon_type not in ['subjective', 'short_answer', 'long_answer']:
            return Response({'detail': 'Only subjective questions can be re-evaluated.'}, status=status.HTTP_400_BAD_REQUEST)

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
                if canonicalize_type(a.question.question_type) in ['subjective', 'short_answer', 'long_answer']
            )
            if not has_pending:
                att.status = StudentAttempt.Status.EVALUATED
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

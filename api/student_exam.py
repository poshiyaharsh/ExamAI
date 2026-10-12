from datetime import timedelta
import logging
import threading

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Exam, Question, StudentAnswer, StudentAttempt
from .permissions import IsStudentUser
from .serializers import StudentAttemptSerializer, StudentExamSerializer

logger = logging.getLogger(__name__)


class StudentExamPermissionMixin:
    permission_classes = [IsAuthenticated, IsStudentUser]


def _available_exam_queryset(user=None):
    now = timezone.now()
    qs = Exam.objects.filter(status=Exam.Status.PUBLISHED).filter(
        Q(starts_at__isnull=True) | Q(starts_at__lte=now),
        Q(ends_at__isnull=True) | Q(ends_at__gte=now),
    ).prefetch_related('questions')
    if user:
        from .utils.departments import get_student_department
        dept = get_student_department(user)
        if not dept:
            return qs.none()
        qs = qs.filter(department__iexact=dept)
    return qs


def _deadline(attempt):
    return attempt.started_at + timedelta(minutes=attempt.exam.duration_minutes)


def _normalise(value):
    return ' '.join(str(value if value is not None else '').split()).casefold()


def _is_objective(question):
    return question.question_type in {'mcq', 'truefalse', 'fillblank'}


def _objective_correct(question, answer_text):
    from .utils.scoring import is_objective_answer_correct
    return is_objective_answer_correct(question, answer_text)


class StudentExamListView(StudentExamPermissionMixin, APIView):
    def get(self, request):
        from .utils.departments import get_student_department
        student_dept = get_student_department(request.user)
        if not student_dept:
            return Response([])

        exams = Exam.objects.filter(
            status=Exam.Status.PUBLISHED,
            department__iexact=student_dept,
        ).prefetch_related('questions')

        attempts = {
            attempt.exam_id: attempt
            for attempt in StudentAttempt.objects.filter(student=request.user, exam__in=exams)
        }
        now = timezone.now()
        result = []
        for exam in exams.order_by('-created_at'):
            attempt = attempts.get(exam.id)
            result.append(
                {
                    'exam': StudentExamSerializer(exam).data,
                    'completed': bool(attempt and attempt.status in {'submitted', 'auto_submitted', 'evaluated'}),
                    'attempt_id': attempt.id if attempt else None,
                    'available': (
                        (exam.starts_at is None or exam.starts_at <= now)
                        and (exam.ends_at is None or exam.ends_at >= now)
                    ),
                }
            )
        return Response(result)


class StartAttemptView(StudentExamPermissionMixin, APIView):
    def post(self, request, exam_id):
        from .utils.departments import check_student_exam_access
        exam = Exam.objects.filter(id=exam_id).first()
        if not exam:
            return Response({'detail': 'Exam not found.'}, status=status.HTTP_404_NOT_FOUND)

        allowed, reason = check_student_exam_access(request.user, exam)
        if not allowed:
            return Response({'detail': reason}, status=status.HTTP_403_FORBIDDEN)

        now = timezone.now()
        if exam.status != Exam.Status.PUBLISHED or (exam.starts_at and exam.starts_at > now) or (exam.ends_at and exam.ends_at < now):
            return Response({'detail': 'Exam is not currently available.'}, status=status.HTTP_400_BAD_REQUEST)

        attempt, created = StudentAttempt.objects.get_or_create(
            exam=exam,
            student=request.user,
            defaults={'status': StudentAttempt.Status.IN_PROGRESS},
        )
        if attempt.status in {'submitted', 'auto_submitted', 'evaluated'}:
            return Response({'detail': 'This exam attempt has already been submitted.'}, status=status.HTTP_400_BAD_REQUEST)
        if timezone.now() >= _deadline(attempt):
            attempt.status = StudentAttempt.Status.AUTO_SUBMITTED
            attempt.submitted_at = timezone.now()
            attempt.save(update_fields=['status', 'submitted_at'])
            return Response({'detail': 'The exam deadline has passed.'}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            {
                'attempt_id': attempt.id,
                'exam': StudentExamSerializer(exam).data,
                'started_at': attempt.started_at,
                'deadline': _deadline(attempt),
                'created': created,
            }
        )


class SaveAnswerView(StudentExamPermissionMixin, APIView):
    def post(self, request, attempt_id):
        attempt = StudentAttempt.objects.filter(id=attempt_id, student=request.user).select_related('exam').first()
        if not attempt:
            return Response({'detail': 'Attempt not found.'}, status=status.HTTP_404_NOT_FOUND)
        from .utils.departments import check_student_exam_access
        allowed, reason = check_student_exam_access(request.user, attempt.exam)
        if not allowed:
            return Response({'detail': reason}, status=status.HTTP_403_FORBIDDEN)

        if attempt.status != StudentAttempt.Status.IN_PROGRESS:
            return Response({'detail': 'This attempt is no longer active.'}, status=status.HTTP_400_BAD_REQUEST)
        if timezone.now() >= _deadline(attempt):
            attempt.status = StudentAttempt.Status.AUTO_SUBMITTED
            attempt.submitted_at = timezone.now()
            attempt.save(update_fields=['status', 'submitted_at'])
            return Response({'detail': 'The exam deadline has passed.'}, status=status.HTTP_400_BAD_REQUEST)

        question = Question.objects.filter(id=request.data.get('question_id'), exam=attempt.exam).first()
        if not question:
            return Response({'detail': 'Question not found for this exam.'}, status=status.HTTP_400_BAD_REQUEST)
        answer, _ = StudentAnswer.objects.update_or_create(
            attempt=attempt,
            question=question,
            defaults={'answer_text': str(request.data.get('answer_text', ''))},
        )
        return Response({'saved': True, 'question_id': question.id, 'answer_text': answer.answer_text})


class SubmitAttemptView(StudentExamPermissionMixin, APIView):
    def post(self, request, attempt_id):
        try:
            return self._post(request, attempt_id)
        except Exception:
            logger.exception('Student attempt submission failed attempt_id=%s user_id=%s', attempt_id, request.user.id)
            return Response({'detail': 'Unable to submit the exam.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def _post(self, request, attempt_id):
        attempt = StudentAttempt.objects.filter(id=attempt_id, student=request.user).select_related('exam').prefetch_related('answers__question').first()
        if not attempt:
            return Response({'detail': 'Attempt not found.'}, status=status.HTTP_404_NOT_FOUND)
        from .utils.departments import check_student_exam_access
        allowed, reason = check_student_exam_access(request.user, attempt.exam)
        if not allowed:
            return Response({'detail': reason}, status=status.HTTP_403_FORBIDDEN)

        if attempt.status != StudentAttempt.Status.IN_PROGRESS:
            return Response({'detail': 'This attempt has already been submitted.'}, status=status.HTTP_400_BAD_REQUEST)

        now = timezone.now()
        auto_submitted = now >= _deadline(attempt)
        from .utils.scoring import calculate_and_save_attempt_score
        calculate_and_save_attempt_score(attempt, is_auto_submit=auto_submitted)

        return Response(StudentAttemptSerializer(attempt).data)


class StudentAttemptDetailView(StudentExamPermissionMixin, APIView):
    def get(self, request, attempt_id):
        attempt = StudentAttempt.objects.filter(id=attempt_id, student=request.user).select_related('exam').prefetch_related('answers__question').first()
        if not attempt:
            return Response({'detail': 'Attempt not found.'}, status=status.HTTP_404_NOT_FOUND)
        from .utils.departments import check_student_exam_access
        allowed, reason = check_student_exam_access(request.user, attempt.exam)
        if not allowed:
            return Response({'detail': reason}, status=status.HTTP_403_FORBIDDEN)
        return Response(StudentAttemptSerializer(attempt).data)

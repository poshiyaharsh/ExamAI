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


def _available_exam_queryset():
    now = timezone.now()
    return Exam.objects.filter(status=Exam.Status.PUBLISHED).filter(
        Q(starts_at__isnull=True) | Q(starts_at__lte=now),
        Q(ends_at__isnull=True) | Q(ends_at__gte=now),
    ).prefetch_related('questions')


def _deadline(attempt):
    return attempt.started_at + timedelta(minutes=attempt.exam.duration_minutes)


def _normalise(value):
    return ' '.join(str(value if value is not None else '').split()).casefold()


def _is_objective(question):
    return question.question_type in {'mcq', 'truefalse', 'fillblank'}


def _objective_correct(question, answer_text):
    submitted = _normalise(answer_text)
    correct = question.correct_answer
    if question.question_type in {'mcq', 'truefalse', 'fillblank'}:
        try:
            option_index = {'A': 0, 'B': 1, 'C': 2, 'D': 3}[str(correct).upper()]
            options = question.options or (['True', 'False'] if question.question_type == 'truefalse' else [])
            return submitted == _normalise(options[option_index])
        except (KeyError, TypeError, ValueError, IndexError):
            return submitted == _normalise(correct)
    return submitted == _normalise(correct)


class StudentExamListView(StudentExamPermissionMixin, APIView):
    def get(self, request):
        exams = Exam.objects.filter(status=Exam.Status.PUBLISHED).prefetch_related('questions')
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
        exam = _available_exam_queryset().filter(id=exam_id).first()
        if not exam:
            return Response({'detail': 'Exam is not available.'}, status=status.HTTP_404_NOT_FOUND)
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
        if attempt.status != StudentAttempt.Status.IN_PROGRESS:
            return Response({'detail': 'This attempt has already been submitted.'}, status=status.HTTP_400_BAD_REQUEST)

        now = timezone.now()
        auto_submitted = now >= _deadline(attempt)
        subjective_questions = []
        with transaction.atomic():
            for question in attempt.exam.questions.all():
                answer, _ = StudentAnswer.objects.get_or_create(attempt=attempt, question=question)
                if _is_objective(question):
                    correct = _objective_correct(question, answer.answer_text)
                    answer.is_correct = correct
                    answer.score_awarded = question.marks if correct else 0
                    answer.save(update_fields=['is_correct', 'score_awarded'])
                else:
                    subjective_questions.append(answer)
            attempt.submitted_at = now
            attempt.status = StudentAttempt.Status.SUBMITTED if subjective_questions else (
                StudentAttempt.Status.AUTO_SUBMITTED if auto_submitted else StudentAttempt.Status.EVALUATED
            )
            attempt.total_score = sum(answer.score_awarded or 0 for answer in attempt.answers.all())
            attempt.save(update_fields=['submitted_at', 'status', 'total_score'])

        if subjective_questions:
            from .evaluation import evaluate_attempt_subjectives
            threading.Thread(target=evaluate_attempt_subjectives, args=(attempt.id,), daemon=True).start()

        return Response(StudentAttemptSerializer(attempt).data)


class StudentAttemptDetailView(StudentExamPermissionMixin, APIView):
    def get(self, request, attempt_id):
        attempt = StudentAttempt.objects.filter(id=attempt_id, student=request.user).prefetch_related('answers__question').first()
        if not attempt:
            return Response({'detail': 'Attempt not found.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(StudentAttemptSerializer(attempt).data)

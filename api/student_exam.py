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
        from .utils.departments import get_student_accessible_exams_queryset, is_exam_visible_to_student
        from api.tenant import get_tenant_cache_key, get_user_institution
        from django.core.cache import cache

        tenant = getattr(request, 'tenant', None) or get_user_institution(request.user)
        if not tenant:
            return Response([])

        cache_key = get_tenant_cache_key(tenant.id, 'student_exam_list', user_id=request.user.id)
        cached_data = cache.get(cache_key)
        if cached_data is not None:
            return Response(cached_data)

        exams = get_student_accessible_exams_queryset(request.user, tenant).prefetch_related('questions')

        attempts = {
            attempt.exam_id: attempt
            for attempt in StudentAttempt.objects.filter(institution=tenant, student=request.user, exam__in=exams)
        }
        result = []
        for exam in exams.order_by('-created_at'):
            attempt = attempts.get(exam.id)
            visible, can_start, reason = is_exam_visible_to_student(exam, request.user)
            if not visible:
                continue
            result.append(
                {
                    'exam': StudentExamSerializer(exam).data,
                    'completed': bool(attempt and attempt.status in {'submitted', 'auto_submitted', 'evaluated'}),
                    'attempt_id': attempt.id if attempt else None,
                    'available': can_start,
                    'availability_reason': reason,
                }
            )
        cache.set(cache_key, result, timeout=60)
        return Response(result)


class StartAttemptView(StudentExamPermissionMixin, APIView):
    def post(self, request, exam_id):
        from .utils.departments import is_exam_visible_to_student
        from api.tenant import get_user_institution
        tenant = getattr(request, 'tenant', None) or get_user_institution(request.user)
        if not tenant:
            return Response({'detail': 'No active institution found.'}, status=status.HTTP_404_NOT_FOUND)

        exam = Exam.objects.filter(id=exam_id, institution=tenant).first()
        if not exam:
            return Response({'detail': 'Exam not found.'}, status=status.HTTP_404_NOT_FOUND)

        visible, can_start, reason = is_exam_visible_to_student(exam, request.user)
        if not visible:
            return Response({'detail': 'Exam not found.'}, status=status.HTTP_404_NOT_FOUND)
        if not can_start:
            return Response({'detail': reason or 'Exam is not currently available.'}, status=status.HTTP_400_BAD_REQUEST)

        attempt, created = StudentAttempt.objects.get_or_create(
            exam=exam,
            student=request.user,
            defaults={'institution': tenant, 'status': StudentAttempt.Status.IN_PROGRESS},
        )
        if not attempt.institution:
            attempt.institution = tenant
            attempt.save(update_fields=['institution'])

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
        import random
        import time
        from django.db import IntegrityError, OperationalError, transaction
        from api.tenant import get_user_institution

        tenant = getattr(request, 'tenant', None) or get_user_institution(request.user)
        if not tenant:
            return Response({'detail': 'No active institution found.'}, status=status.HTTP_404_NOT_FOUND)

        attempt = StudentAttempt.objects.filter(
            id=attempt_id, student=request.user, institution=tenant
        ).select_related('exam').first()
        if not attempt:
            return Response({'detail': 'Attempt not found.'}, status=status.HTTP_404_NOT_FOUND)

        from .utils.departments import check_student_exam_access
        allowed, reason = check_student_exam_access(request.user, attempt.exam)
        if not allowed:
            return Response({'detail': reason}, status=status.HTTP_403_FORBIDDEN)

        if attempt.status != StudentAttempt.Status.IN_PROGRESS:
            return Response({'detail': 'This attempt is no longer active.'}, status=status.HTTP_400_BAD_REQUEST)

        now = timezone.now()
        if (attempt.exam.ends_at and attempt.exam.ends_at < now) or now >= _deadline(attempt):
            if attempt.status == StudentAttempt.Status.IN_PROGRESS:
                attempt.status = StudentAttempt.Status.AUTO_SUBMITTED
                attempt.submitted_at = now
                attempt.save(update_fields=['status', 'submitted_at'])
            return Response({'detail': 'The exam deadline has passed.'}, status=status.HTTP_400_BAD_REQUEST)

        # Support both batch ({'answers': [...]}) and single ({'question_id': ..., 'answer_text': ...})
        raw_answers = request.data.get('answers')
        if raw_answers is not None and isinstance(raw_answers, list):
            items_to_save = raw_answers
        else:
            q_id = request.data.get('question_id')
            if q_id is None:
                return Response({'detail': 'question_id or answers list is required.'}, status=status.HTTP_400_BAD_REQUEST)
            items_to_save = [{'question_id': q_id, 'answer_text': request.data.get('answer_text', '')}]

        if not items_to_save:
            return Response({'saved': True, 'count': 0})

        # Pre-validate all questions belonging to this exam and tenant BEFORE transaction
        question_ids = [item.get('question_id') for item in items_to_save if item.get('question_id') is not None]
        valid_questions = {
            q.id: q
            for q in Question.objects.filter(id__in=question_ids, exam=attempt.exam, institution=tenant)
        }

        validated_items = []
        for item in items_to_save:
            qid = item.get('question_id')
            if qid in valid_questions:
                validated_items.append((valid_questions[qid], str(item.get('answer_text', ''))))

        if not validated_items:
            return Response({'detail': 'No valid questions found for this exam.'}, status=status.HTTP_404_NOT_FOUND)

        # Execute write inside a minimal atomic block with SQLite lock retries
        max_retries = 3
        for attempt_idx in range(max_retries):
            try:
                with transaction.atomic():
                    for question, ans_text in validated_items:
                        try:
                            StudentAnswer.objects.update_or_create(
                                attempt=attempt,
                                question=question,
                                defaults={'institution': tenant, 'answer_text': ans_text},
                            )
                        except IntegrityError:
                            StudentAnswer.objects.filter(
                                attempt=attempt,
                                question=question,
                            ).update(institution=tenant, answer_text=ans_text)

                if len(validated_items) == 1:
                    q, text = validated_items[0]
                    return Response({'saved': True, 'question_id': q.id, 'answer_text': text})
                return Response({'saved': True, 'count': len(validated_items)})

            except OperationalError as exc:
                err_msg = str(exc).lower()
                if 'database is locked' in err_msg or 'database table is locked' in err_msg:
                    if attempt_idx < max_retries - 1:
                        sleep_time = (0.1 * (2 ** attempt_idx)) + random.uniform(0.02, 0.08)
                        logger.warning(
                            'SQLite database locked on save answer, retrying in %.3fs (retry %d/%d)',
                            sleep_time, attempt_idx + 1, max_retries
                        )
                        time.sleep(sleep_time)
                        continue
                    logger.error('SQLite database locked after %d retries on save answer attempt_id=%s', max_retries, attempt_id)
                    return Response(
                        {'detail': 'Database busy, please retry.'},
                        status=status.HTTP_503_SERVICE_UNAVAILABLE,
                        headers={'Retry-After': '1'},
                    )
                raise


class SubmitAttemptView(StudentExamPermissionMixin, APIView):
    def post(self, request, attempt_id):
        try:
            return self._post(request, attempt_id)
        except Exception:
            logger.exception('Student attempt submission failed attempt_id=%s user_id=%s', attempt_id, request.user.id)
            return Response({'detail': 'Unable to submit the exam.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def _post(self, request, attempt_id):
        from api.tenant import get_user_institution
        tenant = getattr(request, 'tenant', None) or get_user_institution(request.user)
        if not tenant:
            return Response({'detail': 'No active institution found.'}, status=status.HTTP_404_NOT_FOUND)

        attempt = StudentAttempt.objects.filter(id=attempt_id, student=request.user, institution=tenant).select_related('exam').prefetch_related('answers__question').first()
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
        from api.tenant import get_user_institution
        tenant = getattr(request, 'tenant', None) or get_user_institution(request.user)
        if not tenant:
            return Response({'detail': 'No active institution found.'}, status=status.HTTP_404_NOT_FOUND)

        attempt = StudentAttempt.objects.filter(id=attempt_id, student=request.user, institution=tenant).select_related('exam').prefetch_related('answers__question').first()
        if not attempt:
            return Response({'detail': 'Attempt not found.'}, status=status.HTTP_404_NOT_FOUND)
        from .utils.departments import check_student_exam_access
        allowed, reason = check_student_exam_access(request.user, attempt.exam)
        if not allowed:
            return Response({'detail': reason}, status=status.HTTP_403_FORBIDDEN)
        return Response(StudentAttemptSerializer(attempt).data)

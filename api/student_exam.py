from datetime import timedelta
import logging
import random
import secrets
import time
import uuid

from django.core.cache import cache
from django.db import IntegrityError, OperationalError, connection, transaction
from django.db.models import F, Q
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from api.tenant import get_tenant_cache_key, get_user_institution
from .models import AttemptEvent, Exam, Question, StudentAnswer, StudentAttempt
from .permissions import IsStudentUser
from .serializers import StudentAttemptSerializer, StudentExamSerializer
from .utils.departments import get_student_accessible_exams_queryset, is_exam_visible_to_student
from .utils.exam_attempt_helper import (
    initialize_attempt_orders,
    map_submitted_answer_to_canonical,
    sanitize_questions_for_attempt,
)
from .utils.schedule import compute_attempt_expiry, format_exam_schedule_display, get_exam_schedule_phase
from .utils.scoring import calculate_and_save_attempt_score

logger = logging.getLogger(__name__)


def finalize_student_attempt(attempt, submit_reason='violations', buffered_answers=None, request_id=None):
    """
    Idempotent single source of truth for finalizing and scoring a student attempt.
    - Saves any buffered answers provided by the client
    - Transitions attempt status to AUTO_SUBMITTED (or SUBMITTED if manual)
    - Triggers grading via calculate_and_save_attempt_score
    - In case of scoring failure, marks needs_finalize=True without leaving attempt in progress
    """
    now = timezone.now()
    tenant = attempt.institution

    # 1. Save any buffered answers submitted with the finalization request
    if buffered_answers and isinstance(buffered_answers, list):
        for item in buffered_answers:
            if not isinstance(item, dict):
                continue
            qid = item.get('question_id')
            if not qid:
                continue
            ans_text = str(item.get('answer_text', ''))
            blanks = item.get('blank_answers')
            q_obj = Question.objects.filter(id=qid, exam=attempt.exam, institution=tenant).first()
            if not q_obj:
                continue
            canonical_text, applied_perm = map_submitted_answer_to_canonical(attempt, q_obj, ans_text)
            defaults = {
                'institution': tenant,
                'answer_text': canonical_text,
                'selected_option_order': applied_perm,
            }
            if blanks is not None and isinstance(blanks, list):
                defaults['blank_answers'] = blanks
            try:
                StudentAnswer.objects.update_or_create(
                    attempt=attempt,
                    question=q_obj,
                    defaults=defaults,
                )
            except IntegrityError:
                StudentAnswer.objects.filter(
                    attempt=attempt,
                    question=q_obj,
                ).update(**defaults)

    # 2. Check if already in terminal status
    is_terminal = attempt.status in {
        StudentAttempt.Status.SUBMITTED,
        StudentAttempt.Status.AUTO_SUBMITTED,
        StudentAttempt.Status.EVALUATED,
    }
    if is_terminal and not attempt.needs_finalize:
        return attempt, False

    # 3. Transition status from IN_PROGRESS to AUTO_SUBMITTED
    if not is_terminal:
        target_status = StudentAttempt.Status.SUBMITTED if submit_reason == 'manual' else StudentAttempt.Status.AUTO_SUBMITTED
        StudentAttempt.objects.filter(
            id=attempt.id,
            status=StudentAttempt.Status.IN_PROGRESS,
        ).update(
            status=target_status,
            submit_reason=submit_reason,
            submitted_at=now,
        )

    # 4. Score the attempt
    try:
        attempt.refresh_from_db()
        calculate_and_save_attempt_score(attempt, is_auto_submit=(submit_reason != 'manual'), trigger_ai=True)
        if attempt.needs_finalize:
            StudentAttempt.objects.filter(id=attempt.id).update(needs_finalize=False)
            attempt.needs_finalize = False
    except Exception as exc:
        req_str = f" req_id={request_id}" if request_id else ""
        logger.error(
            "Finalize grading failed for attempt_id=%s%s: %s",
            attempt.id, req_str, exc, exc_info=True
        )
        target_status = StudentAttempt.Status.SUBMITTED if submit_reason == 'manual' else StudentAttempt.Status.AUTO_SUBMITTED
        StudentAttempt.objects.filter(id=attempt.id).update(
            status=target_status,
            submit_reason=submit_reason,
            needs_finalize=True,
        )
        attempt.needs_finalize = True

    attempt.refresh_from_db()
    return attempt, True


class StudentExamPermissionMixin:
    permission_classes = [IsAuthenticated, IsStudentUser]


def _deadline(attempt):
    if attempt.expires_at:
        return attempt.expires_at
    return compute_attempt_expiry(attempt.exam, attempt.started_at)


def _normalise(value):
    return ' '.join(str(value if value is not None else '').split()).casefold()


class StudentExamListView(StudentExamPermissionMixin, APIView):
    def get(self, request):
        from .utils.departments import get_student_accessible_exams_queryset, is_exam_visible_to_student
        from api.tenant import get_tenant_cache_key, get_user_institution
        from api.utils.schedule import compute_attempt_expiry, format_exam_schedule_display, get_exam_schedule_phase
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
            for attempt in StudentAttempt.objects.filter(
                institution=tenant, student=request.user, exam__in=exams
            ).order_by('attempt_number')
        }
        now = timezone.now()
        result = []
        for exam in exams.order_by('-created_at'):
            attempt = attempts.get(exam.id)
            visible, can_start, reason = is_exam_visible_to_student(exam, request.user)
            if not visible:
                continue

            phase = get_exam_schedule_phase(exam, now)
            sched_display = format_exam_schedule_display(exam)
            potential_expiry = compute_attempt_expiry(exam, started_at=now, now=now)
            available_seconds = max(0, int((potential_expiry - now).total_seconds()))
            is_window_capped = bool(
                exam.ends_at and potential_expiry == exam.ends_at and
                (now + timedelta(minutes=exam.duration_minutes)) > exam.ends_at
            )

            result.append(
                {
                    'exam': StudentExamSerializer(exam).data,
                    'completed': bool(attempt and attempt.status in {'submitted', 'auto_submitted', 'evaluated'}),
                    'attempt_id': attempt.id if attempt else None,
                    'available': can_start and (phase == 'live'),
                    'availability_reason': reason,
                    'schedule_phase': phase,
                    'server_now': now.isoformat(),
                    'starts_at': exam.starts_at.isoformat() if exam.starts_at else None,
                    'ends_at': exam.ends_at.isoformat() if exam.ends_at else None,
                    'display_timezone': getattr(exam, 'display_timezone', 'Asia/Kolkata'),
                    'schedule_display': sched_display,
                    'is_window_capped': is_window_capped,
                    'available_minutes': int(round(available_seconds / 60.0)),
                    'allow_retakes': exam.allow_retakes,
                    'max_warnings': exam.max_warnings,
                }
            )
        cache.set(cache_key, result, timeout=15)
        return Response(result)


class StartAttemptView(StudentExamPermissionMixin, APIView):
    def post(self, request, exam_id):
        from .utils.departments import is_exam_visible_to_student
        from api.tenant import get_user_institution
        from api.utils.schedule import compute_attempt_expiry, format_exam_schedule_display, get_exam_schedule_phase

        tenant = getattr(request, 'tenant', None) or get_user_institution(request.user)
        if not tenant:
            return Response({'detail': 'No active institution found.'}, status=status.HTTP_404_NOT_FOUND)

        exam = Exam.objects.filter(id=exam_id, institution=tenant).first()
        if not exam:
            return Response({'detail': 'Exam not found.'}, status=status.HTTP_404_NOT_FOUND)

        now = timezone.now()
        sched_info = format_exam_schedule_display(exam)
        phase = get_exam_schedule_phase(exam, now)

        if phase == 'upcoming':
            return Response(
                {
                    'detail': f"Exam has not started yet. Opens on {sched_info.get('starts_at_display')} ({sched_info.get('timezone')}).",
                    'error_code': 'EXAM_NOT_STARTED',
                    'starts_at': exam.starts_at.isoformat() if exam.starts_at else None,
                    'server_now': now.isoformat(),
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        if phase == 'ended':
            return Response(
                {
                    'detail': f"Exam window closed on {sched_info.get('ends_at_display')} ({sched_info.get('timezone')}).",
                    'error_code': 'EXAM_ENDED',
                    'ends_at': exam.ends_at.isoformat() if exam.ends_at else None,
                    'server_now': now.isoformat(),
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        visible, can_start, reason = is_exam_visible_to_student(exam, request.user)
        if not visible:
            return Response({'detail': 'Exam not found.'}, status=status.HTTP_404_NOT_FOUND)
        if not can_start:
            return Response({'detail': reason or 'Exam is not currently available.', 'error_code': 'EXAM_UNAVAILABLE'}, status=status.HTTP_403_FORBIDDEN)

        with transaction.atomic():
            # Lock the exam record inside transaction to verify boundary race condition
            locked_exam = Exam.objects.select_for_update().get(id=exam.id)
            phase_locked = get_exam_schedule_phase(locked_exam, now)
            if phase_locked == 'upcoming':
                return Response(
                    {
                        'detail': 'Exam has not started yet.',
                        'error_code': 'EXAM_NOT_STARTED',
                        'starts_at': locked_exam.starts_at.isoformat() if locked_exam.starts_at else None,
                        'server_now': now.isoformat(),
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )
            if phase_locked == 'ended':
                return Response(
                    {
                        'detail': 'Exam window has closed.',
                        'error_code': 'EXAM_ENDED',
                        'ends_at': locked_exam.ends_at.isoformat() if locked_exam.ends_at else None,
                        'server_now': now.isoformat(),
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )

            existing_attempts = list(
                StudentAttempt.objects.select_for_update()
                .filter(exam=locked_exam, student=request.user, institution=tenant)
                .order_by('-attempt_number')
            )

            active_attempt = next(
                (att for att in existing_attempts if att.status == StudentAttempt.Status.IN_PROGRESS),
                None,
            )

            if active_attempt:
                # Backstop: Check if violation count exceeded or needs finalize
                if active_attempt.violation_count > locked_exam.max_warnings or active_attempt.needs_finalize:
                    finalize_student_attempt(active_attempt, submit_reason='violations')
                    return Response({
                        'detail': 'The exam was automatically submitted due to proctoring violations.',
                        'error_code': 'EXAM_SUBMITTED_VIOLATIONS',
                        'auto_submitted': True,
                        'submit_reason': 'violations',
                        'redirect_url': f'/student/results/{active_attempt.id}',
                        'server_now': now.isoformat(),
                    }, status=status.HTTP_403_FORBIDDEN)

                deadline = active_attempt.expires_at or compute_attempt_expiry(locked_exam, active_attempt.started_at, now)
                # Check if deadline or exam window passed
                if now >= deadline or (locked_exam.ends_at and now >= locked_exam.ends_at):
                    reason = 'window_closed' if (locked_exam.ends_at and now >= locked_exam.ends_at) else 'time_up'
                    finalize_student_attempt(active_attempt, submit_reason=reason)
                    return Response({
                        'detail': 'The exam deadline has passed.',
                        'error_code': 'EXAM_EXPIRED',
                        'auto_submitted': True,
                        'submit_reason': reason,
                        'redirect_url': f'/student/results/{active_attempt.id}',
                        'server_now': now.isoformat(),
                    }, status=status.HTTP_403_FORBIDDEN)

                # Resume existing active attempt
                attempt = active_attempt
                created = False
            elif existing_attempts:
                # Previous attempt exists and is finished
                last_att = existing_attempts[0]
                if not locked_exam.allow_retakes:
                    return Response(
                        {
                            'detail': 'This exam attempt has already been submitted.',
                            'error_code': 'ALREADY_SUBMITTED',
                            'already_submitted': True,
                            'auto_submitted': True,
                            'status': last_att.status,
                            'submit_reason': last_att.submit_reason,
                            'redirect_url': f'/student/results/{last_att.id}',
                            'server_now': now.isoformat(),
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                # Retake allowed
                next_number = existing_attempts[0].attempt_number + 1
                session_token = secrets.token_hex(24)
                expires_at = compute_attempt_expiry(locked_exam, started_at=now, now=now)
                attempt = StudentAttempt(
                    exam=locked_exam,
                    institution=tenant,
                    student=request.user,
                    attempt_number=next_number,
                    status=StudentAttempt.Status.IN_PROGRESS,
                    expires_at=expires_at,
                    active_session_token=session_token,
                )
                initialize_attempt_orders(attempt, locked_exam)
                attempt.save()
                created = True
            else:
                # Brand new attempt
                session_token = secrets.token_hex(24)
                expires_at = compute_attempt_expiry(locked_exam, started_at=now, now=now)
                attempt = StudentAttempt(
                    exam=locked_exam,
                    institution=tenant,
                    student=request.user,
                    attempt_number=1,
                    status=StudentAttempt.Status.IN_PROGRESS,
                    expires_at=expires_at,
                    active_session_token=session_token,
                )
                initialize_attempt_orders(attempt, locked_exam)
                attempt.save()
                created = True

            # If existing attempt didn't have orders (created prior to shuffle feature)
            if not attempt.question_order:
                initialize_attempt_orders(attempt, locked_exam)
                if not attempt.active_session_token:
                    attempt.active_session_token = secrets.token_hex(24)
                if not attempt.expires_at:
                    attempt.expires_at = compute_attempt_expiry(locked_exam, attempt.started_at, now)
                attempt.save(update_fields=['question_order', 'option_orders', 'max_score', 'active_session_token', 'expires_at'])

        sanitized_questions = sanitize_questions_for_attempt(attempt)
        deadline = attempt.expires_at or compute_attempt_expiry(exam, attempt.started_at, now)
        is_window_capped = bool(
            exam.ends_at and deadline == exam.ends_at and
            (attempt.started_at + timedelta(minutes=exam.duration_minutes)) > exam.ends_at
        )

        exam_payload = {
            'id': exam.id,
            'title': exam.title,
            'department': exam.department,
            'duration_minutes': exam.duration_minutes,
            'total_marks': float(attempt.max_score or exam.total_marks or 0.0),
            'topics': exam.topics,
            'starts_at': exam.starts_at.isoformat() if exam.starts_at else None,
            'ends_at': exam.ends_at.isoformat() if exam.ends_at else None,
            'display_timezone': getattr(exam, 'display_timezone', 'Asia/Kolkata'),
            'questions': sanitized_questions,
            'shuffle_questions': exam.shuffle_questions,
            'shuffle_options': exam.shuffle_options,
            'max_warnings': exam.max_warnings,
        }

        return Response(
            {
                'attempt_id': attempt.id,
                'exam': exam_payload,
                'started_at': attempt.started_at.isoformat() if attempt.started_at else now.isoformat(),
                'deadline': deadline.isoformat(),
                'expires_at': deadline.isoformat(),
                'server_now': now.isoformat(),
                'duration_seconds': max(0, int((deadline - now).total_seconds())),
                'is_window_capped': is_window_capped,
                'session_token': attempt.active_session_token,
                'violation_count': attempt.violation_count,
                'max_warnings': exam.max_warnings,
                'created': created,
            }
        )


class SaveAnswerView(StudentExamPermissionMixin, APIView):
    def post(self, request, attempt_id):
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
            return Response({
                'saved': False,
                'already_submitted': True,
                'auto_submitted': True,
                'status': attempt.status,
                'submit_reason': attempt.submit_reason,
                'detail': 'This attempt has already been submitted and is no longer active.',
                'error_code': 'ATTEMPT_NOT_ACTIVE',
                'redirect_url': f'/student/results/{attempt.id}',
                'server_now': timezone.now().isoformat(),
            }, status=status.HTTP_400_BAD_REQUEST)

        # Backstop: Check if violation count exceeded or needs finalize
        if attempt.violation_count > attempt.exam.max_warnings or attempt.needs_finalize:
            finalize_student_attempt(attempt, submit_reason='violations')
            return Response({
                'saved': False,
                'already_submitted': True,
                'auto_submitted': True,
                'status': attempt.status,
                'submit_reason': 'violations',
                'detail': 'The exam was automatically submitted due to proctoring violations and is no longer active.',
                'error_code': 'EXAM_SUBMITTED_VIOLATIONS',
                'redirect_url': f'/student/results/{attempt.id}',
                'server_now': timezone.now().isoformat(),
            }, status=status.HTTP_400_BAD_REQUEST)

        now = timezone.now()
        deadline = attempt.expires_at or _deadline(attempt)
        grace_period = timedelta(seconds=5)

        # Enforce server-side timer with 5-second network grace period
        window_passed = bool(attempt.exam.ends_at and now > (attempt.exam.ends_at + grace_period))
        deadline_passed = bool(now > (deadline + grace_period))
        if window_passed or deadline_passed:
            reason = 'window_closed' if window_passed else 'time_up'
            finalize_student_attempt(attempt, submit_reason=reason)
            return Response({
                'detail': 'The exam deadline has passed.',
                'error_code': 'EXAM_EXPIRED',
                'already_submitted': True,
                'auto_submitted': True,
                'submit_reason': reason,
                'redirect_url': f'/student/results/{attempt.id}',
                'server_now': now.isoformat(),
            }, status=status.HTTP_403_FORBIDDEN)

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
            return Response({'saved': True, 'count': 0, 'saved_at': now.isoformat(), 'server_now': now.isoformat()})

        # Pre-validate questions: must belong to exam and attempt.question_order (if set)
        question_ids = [item.get('question_id') for item in items_to_save if item.get('question_id') is not None]
        allowed_qids = set(attempt.question_order) if attempt.question_order else None

        q_query = Question.objects.filter(id__in=question_ids, exam=attempt.exam, institution=tenant)
        if allowed_qids is not None:
            q_query = q_query.filter(id__in=allowed_qids)

        valid_questions = {q.id: q for q in q_query}

        validated_items = []
        for item in items_to_save:
            qid = item.get('question_id')
            if qid in valid_questions:
                raw_text = str(item.get('answer_text', ''))
                blanks = item.get('blank_answers')
                if (not raw_text.strip()) and blanks and isinstance(blanks, list):
                    raw_text = " | ".join(str(b) for b in blanks)
                # Map option back to canonical choice before storing
                canonical_text, applied_perm = map_submitted_answer_to_canonical(
                    attempt, valid_questions[qid], raw_text
                )
                validated_items.append((valid_questions[qid], canonical_text, applied_perm, blanks))

        if not validated_items:
            return Response({'detail': 'No valid questions found for this exam attempt.'}, status=status.HTTP_404_NOT_FOUND)

        max_retries = 3
        for attempt_idx in range(max_retries):
            try:
                with transaction.atomic():
                    for question, ans_text, perm, blanks in validated_items:
                        defaults = {
                            'institution': tenant,
                            'answer_text': ans_text,
                            'selected_option_order': perm,
                        }
                        if blanks is not None and isinstance(blanks, list):
                            defaults['blank_answers'] = blanks
                        try:
                            StudentAnswer.objects.update_or_create(
                                attempt=attempt,
                                question=question,
                                defaults=defaults,
                            )
                        except IntegrityError:
                            StudentAnswer.objects.filter(
                                attempt=attempt,
                                question=question,
                            ).update(**defaults)

                if len(validated_items) == 1:
                    q, text, _, _blanks = validated_items[0]
                    return Response({
                        'saved': True,
                        'question_id': q.id,
                        'answer_text': text,
                        'saved_at': now.isoformat(),
                        'server_now': now.isoformat(),
                    })
                return Response({
                    'saved': True,
                    'count': len(validated_items),
                    'saved_at': now.isoformat(),
                    'server_now': now.isoformat(),
                })

            except OperationalError as exc:
                from .utils.db_retry import is_lock_or_deadlock
                if is_lock_or_deadlock(exc):
                    if attempt_idx < max_retries - 1:
                        sleep_time = (0.1 * (2 ** attempt_idx)) + random.uniform(0.02, 0.08)
                        logger.warning(
                            'Database lock/deadlock on save answer, retrying in %.3fs (retry %d/%d): %s',
                            sleep_time, attempt_idx + 1, max_retries, exc
                        )
                        time.sleep(sleep_time)
                        continue
                    logger.error('Database lock/deadlock after %d retries on save answer attempt_id=%s', max_retries, attempt_id)
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
        from django.db import transaction

        tenant = getattr(request, 'tenant', None) or get_user_institution(request.user)
        if not tenant:
            return Response({'detail': 'No active institution found.'}, status=status.HTTP_404_NOT_FOUND)

        with transaction.atomic():
            from django.db import connection
            attempt_qs = StudentAttempt.objects.filter(id=attempt_id, student=request.user, institution=tenant)
            if getattr(connection.features, 'has_select_for_update', False):
                attempt_qs = attempt_qs.select_for_update()
            attempt = attempt_qs.select_related('exam', 'institution').first()
            if not attempt:
                return Response({'detail': 'Attempt not found.'}, status=status.HTTP_404_NOT_FOUND)

            from .utils.departments import check_student_exam_access
            allowed, reason = check_student_exam_access(request.user, attempt.exam)
            if not allowed:
                return Response({'detail': reason}, status=status.HTTP_403_FORBIDDEN)

            # Idempotent response if already submitted
            if attempt.status in {
                StudentAttempt.Status.SUBMITTED,
                StudentAttempt.Status.AUTO_SUBMITTED,
                StudentAttempt.Status.EVALUATED,
            }:
                data = StudentAttemptSerializer(attempt).data
                data['server_now'] = timezone.now().isoformat()
                return Response(data, status=status.HTTP_200_OK)

            if attempt.status != StudentAttempt.Status.IN_PROGRESS:
                return Response({'detail': 'This attempt cannot be submitted.'}, status=status.HTTP_400_BAD_REQUEST)

            now = timezone.now()
            deadline = attempt.expires_at or _deadline(attempt)
            requested_reason = request.data.get('reason')

            window_closed = bool(attempt.exam.ends_at and now >= attempt.exam.ends_at)
            time_up = (now >= deadline)

            if requested_reason in {'time_up', 'violations', 'manual', 'window_closed'}:
                submit_reason = requested_reason
            elif window_closed:
                submit_reason = 'window_closed'
            elif time_up:
                submit_reason = 'time_up'
            else:
                submit_reason = 'manual'

            # Guard against student claiming manual when deadline or window passed
            if window_closed and submit_reason != 'violations':
                submit_reason = 'window_closed'
            elif time_up and submit_reason == 'manual':
                submit_reason = 'time_up'

            auto_submitted = (submit_reason in {'time_up', 'violations', 'window_closed'}) or time_up or window_closed
            target_status = StudentAttempt.Status.AUTO_SUBMITTED if auto_submitted else StudentAttempt.Status.SUBMITTED

            finalize_student_attempt(attempt, submit_reason=submit_reason)

        attempt.refresh_from_db()
        data = StudentAttemptSerializer(attempt).data
        data['server_now'] = timezone.now().isoformat()
        return Response(data, status=status.HTTP_200_OK)


class ViolationEventView(StudentExamPermissionMixin, APIView):
    """
    Records proctoring violation events (fullscreen exit, tab hidden, window blur, etc.).
    Automatically submits attempt if violation_count exceeds exam.max_warnings.
    """
    throttle_classes = []  # Exempt from aggressive rate limiting to allow proctoring bursts

    def post(self, request, attempt_id):
        tenant = getattr(request, 'tenant', None) or get_user_institution(request.user)
        if not tenant:
            return Response({'detail': 'No active institution found.'}, status=status.HTTP_404_NOT_FOUND)

        event_type = request.data.get('event_type', AttemptEvent.EventType.CUSTOM)
        event_id = str(request.data.get('event_id', '')).strip()
        metadata = request.data.get('metadata') or {}
        if not isinstance(metadata, dict):
            metadata = {'raw': str(metadata)}
        buffered_answers = request.data.get('answers') or request.data.get('buffered_answers')

        with transaction.atomic():
            attempt_qs = StudentAttempt.objects.filter(id=attempt_id, student=request.user, institution=tenant)
            if getattr(connection.features, 'has_select_for_update', False):
                attempt_qs = attempt_qs.select_for_update()
            attempt = attempt_qs.select_related('exam').first()
            if not attempt:
                return Response({'detail': 'Attempt not found.'}, status=status.HTTP_404_NOT_FOUND)

            max_warnings = attempt.exam.max_warnings

            # 1. Idempotent check: if already submitted / finalized
            if attempt.status != StudentAttempt.Status.IN_PROGRESS:
                return Response({
                    'already_submitted': True,
                    'auto_submitted': True,
                    'status': attempt.status,
                    'submit_reason': attempt.submit_reason,
                    'violation_count': attempt.violation_count,
                    'max_warnings': max_warnings,
                    'warnings_left': 0,
                    'message': 'This exam attempt has already been submitted.',
                    'redirect_url': f'/student/results/{attempt.id}',
                    'server_now': timezone.now().isoformat(),
                }, status=status.HTTP_200_OK)

            # 2. Idempotent check: if event_id already recorded (network retry)
            if event_id and AttemptEvent.objects.filter(attempt=attempt, event_id=event_id).exists():
                current_count = attempt.violation_count
                warnings_left = max(0, max_warnings - current_count)
                is_auto = current_count > max_warnings
                return Response({
                    'already_recorded': True,
                    'auto_submitted': is_auto,
                    'submit_reason': attempt.submit_reason if is_auto else None,
                    'violation_count': current_count,
                    'max_warnings': max_warnings,
                    'warnings_left': warnings_left,
                    'redirect_url': f'/student/results/{attempt.id}' if is_auto else None,
                    'server_now': timezone.now().isoformat(),
                }, status=status.HTTP_200_OK)

            # 3. Atomically increment violation count in database
            StudentAttempt.objects.filter(id=attempt.id).update(
                violation_count=F('violation_count') + 1
            )
            attempt.refresh_from_db(fields=['violation_count'])
            new_count = attempt.violation_count

            # 4. Log event record
            AttemptEvent.objects.create(
                attempt=attempt,
                institution=tenant,
                event_type=event_type,
                event_id=event_id,
                metadata=metadata,
                timestamp=timezone.now(),
            )

            # 5. Check auto-submit threshold (4th violation when max_warnings=3)
            if new_count > max_warnings:
                req_id = str(uuid.uuid4())
                attempt, _ = finalize_student_attempt(
                    attempt=attempt,
                    submit_reason='violations',
                    buffered_answers=buffered_answers,
                    request_id=req_id,
                )
                return Response({
                    'auto_submitted': True,
                    'status': attempt.status,
                    'submit_reason': 'violations',
                    'violation_count': new_count,
                    'max_warnings': max_warnings,
                    'warnings_left': 0,
                    'message': f'Violation limit exceeded ({new_count}/{max_warnings}). The exam has been automatically submitted.',
                    'redirect_url': f'/student/results/{attempt.id}',
                    'server_now': timezone.now().isoformat(),
                }, status=status.HTTP_200_OK)

            # 6. Warnings 1, 2, 3
            warnings_left = max(0, max_warnings - new_count)
            return Response({
                'auto_submitted': False,
                'violation_count': new_count,
                'max_warnings': max_warnings,
                'warnings_left': warnings_left,
                'message': f'Warning {new_count} of {max_warnings}: Proctoring violation detected ({event_type}).',
                'server_now': timezone.now().isoformat(),
            }, status=status.HTTP_200_OK)


class HeartbeatView(StudentExamPermissionMixin, APIView):
    """
    Heartbeat endpoint to track active session, check for concurrent tabs,
    and monitor remaining time against both exam window and personal timer.
    """
    def post(self, request, attempt_id):
        tenant = getattr(request, 'tenant', None) or get_user_institution(request.user)
        if not tenant:
            return Response({'detail': 'No active institution found.'}, status=status.HTTP_404_NOT_FOUND)

        attempt = StudentAttempt.objects.filter(
            id=attempt_id, student=request.user, institution=tenant
        ).select_related('exam').first()
        if not attempt:
            return Response({'detail': 'Attempt not found.'}, status=status.HTTP_404_NOT_FOUND)

        now = timezone.now()
        if attempt.status != StudentAttempt.Status.IN_PROGRESS:
            return Response({
                'active': False,
                'already_submitted': True,
                'auto_submitted': True,
                'status': attempt.status,
                'submit_reason': attempt.submit_reason,
                'redirect_url': f'/student/results/{attempt.id}',
                'server_now': now.isoformat(),
            }, status=status.HTTP_200_OK)

        # Backstop: Check if violation count already exceeded or needs finalize
        if attempt.violation_count > attempt.exam.max_warnings or attempt.needs_finalize:
            finalize_student_attempt(attempt, submit_reason='violations')
            return Response({
                'active': False,
                'already_submitted': True,
                'auto_submitted': True,
                'status': attempt.status,
                'submit_reason': 'violations',
                'redirect_url': f'/student/results/{attempt.id}',
                'server_now': now.isoformat(),
            }, status=status.HTTP_200_OK)

        # Check session token concurrency
        session_token = request.data.get('session_token')
        if attempt.active_session_token and session_token and session_token != attempt.active_session_token:
            AttemptEvent.objects.create(
                attempt=attempt,
                institution=tenant,
                event_type=AttemptEvent.EventType.CONCURRENT_TAB,
                metadata={'provided_token': session_token[:8] + '...'},
            )
            return Response({
                'active': False,
                'concurrent_session': True,
                'message': 'A newer session has been opened in another window or tab.',
                'server_now': now.isoformat(),
            }, status=status.HTTP_409_CONFLICT)

        deadline = attempt.expires_at or _deadline(attempt)
        window_passed = bool(attempt.exam.ends_at and now >= attempt.exam.ends_at)
        time_up = (now >= deadline)

        if window_passed or time_up:
            reason = 'window_closed' if window_passed else 'time_up'
            finalize_student_attempt(attempt, submit_reason=reason)
            return Response({
                'active': False,
                'expired': True,
                'auto_submitted': True,
                'submit_reason': reason,
                'redirect_url': f'/student/results/{attempt.id}',
                'server_now': now.isoformat(),
            }, status=status.HTTP_200_OK)

        seconds_left = max(0, int((deadline - now).total_seconds()))
        return Response({
            'active': True,
            'seconds_left': seconds_left,
            'server_now': now.isoformat(),
            'violation_count': attempt.violation_count,
            'max_warnings': attempt.exam.max_warnings,
        })


class StudentAttemptDetailView(StudentExamPermissionMixin, APIView):
    def get(self, request, attempt_id):
        from api.tenant import get_user_institution
        tenant = getattr(request, 'tenant', None) or get_user_institution(request.user)
        if not tenant:
            return Response({'detail': 'No active institution found.'}, status=status.HTTP_404_NOT_FOUND)

        attempt = (
            StudentAttempt.objects.filter(id=attempt_id, student=request.user, institution=tenant)
            .select_related('exam')
            .prefetch_related('answers__question')
            .first()
        )
        if not attempt:
            return Response({'detail': 'Attempt not found.'}, status=status.HTTP_404_NOT_FOUND)
        from .utils.departments import check_student_exam_access
        allowed, reason = check_student_exam_access(request.user, attempt.exam)
        if not allowed:
            return Response({'detail': reason}, status=status.HTTP_403_FORBIDDEN)
        return Response(StudentAttemptSerializer(attempt).data)

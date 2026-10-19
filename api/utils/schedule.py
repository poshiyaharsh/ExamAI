"""
Schedule utilities for exam time windows, timezone conversions,
phase calculations, attempt expiration, and auto-finalization.
"""

from datetime import datetime, timedelta
import logging
import threading
import time
from typing import Any, Dict, Optional, Tuple
import zoneinfo

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_datetime

logger = logging.getLogger(__name__)

DEFAULT_TIMEZONE = 'Asia/Kolkata'
MAX_WINDOW_DAYS = 30
PUBLISH_PAST_GRACE_MINUTES = 5
SUBMIT_NETWORK_GRACE_SECONDS = 5


def get_valid_timezone(tz_name: Optional[str]) -> str:
    """Validates and returns an IANA timezone name, defaulting to Asia/Kolkata."""
    if not tz_name or not isinstance(tz_name, str):
        return DEFAULT_TIMEZONE
    clean_tz = tz_name.strip()
    try:
        zoneinfo.ZoneInfo(clean_tz)
        return clean_tz
    except (zoneinfo.ZoneInfoNotFoundError, ValueError):
        return DEFAULT_TIMEZONE


def normalize_to_utc(value: Any, client_timezone: str = DEFAULT_TIMEZONE) -> Optional[datetime]:
    """
    Parses a date-time value (ISO string, datetime object, or naive datetime)
    and normalizes it to a timezone-aware UTC datetime.
    
    If the input is naive (e.g. from HTML <input type="datetime-local"> like "2026-10-19T13:36"),
    it is localized in `client_timezone` first, then converted to UTC.
    """
    if value is None or value == '':
        return None

    tz_str = get_valid_timezone(client_timezone)
    target_tz = zoneinfo.ZoneInfo(tz_str)

    if isinstance(value, str):
        val_str = value.strip()
        if not val_str:
            return None
        parsed = parse_datetime(val_str)
        if parsed is None:
            # Fallback for ISO strings with format variations
            try:
                parsed = datetime.fromisoformat(val_str.replace('Z', '+00:00'))
            except (ValueError, TypeError) as exc:
                raise ValidationError(f"Invalid date format: '{val_str}'. Use ISO 8601 format.") from exc
    elif isinstance(value, datetime):
        parsed = value
    else:
        raise ValidationError(f"Unsupported datetime value type: {type(value)}")

    if timezone.is_naive(parsed):
        aware_dt = parsed.replace(tzinfo=target_tz)
    else:
        aware_dt = parsed

    return aware_dt.astimezone(zoneinfo.ZoneInfo('UTC'))


def validate_exam_schedule(
    starts_at: Optional[datetime],
    ends_at: Optional[datetime],
    duration_minutes: int,
    is_publishing: bool = False,
    allow_past_grace_minutes: int = PUBLISH_PAST_GRACE_MINUTES,
    max_window_days: int = MAX_WINDOW_DAYS,
    now: Optional[datetime] = None,
    raise_exception: bool = False,
) -> Tuple[bool, Optional[str]]:
    """
    Validates exam schedule boundaries.
    If raise_exception=True, raises ValidationError with field-specific errors.
    Otherwise returns (is_valid, error_message_or_None).
    """
    current_time = now or timezone.now()
    errors = {}

    if is_publishing:
        if not starts_at:
            errors['starts_at'] = "Start time ('Available From') is required to publish an exam."
        if not ends_at:
            errors['ends_at'] = "End time ('Deadline') is required to publish an exam."

    if starts_at and ends_at:
        if ends_at <= starts_at:
            errors['ends_at'] = "Deadline (end time) must be after the start time."
        else:
            window_delta = ends_at - starts_at
            min_window = timedelta(minutes=duration_minutes or 1)
            if window_delta < min_window:
                errors['ends_at'] = (
                    f"Exam window ({int(window_delta.total_seconds() // 60)} minutes) must be at least as long as the "
                    f"exam duration ({duration_minutes} minutes)."
                )
            if window_delta > timedelta(days=max_window_days):
                errors['ends_at'] = f"Exam window cannot exceed {max_window_days} days."

    if is_publishing and starts_at:
        past_limit = current_time - timedelta(minutes=allow_past_grace_minutes)
        if starts_at < past_limit:
            errors['starts_at'] = (
                f"Start time cannot be in the past (allowed grace: {allow_past_grace_minutes} minutes)."
            )

    if errors:
        if raise_exception:
            raise ValidationError(errors)
        err_msg = "; ".join(errors.values())
        return False, err_msg

    return True, None


def get_exam_schedule_phase(exam: Any, now: Optional[datetime] = None) -> str:
    """
    Single source of truth deriving the exam schedule phase:
    - 'draft': If exam status is not published.
    - 'upcoming': If now < starts_at.
    - 'live': If starts_at <= now < ends_at (or open window).
    - 'ended': If now >= ends_at (or exam status is closed).
    
    Uses half-open intervals [starts_at, ends_at) so boundaries are consistent across
    student attempts, faculty dashboards, and admin views.
    """
    if getattr(exam, 'status', None) != 'published':
        return getattr(exam, 'status', 'draft')

    current_time = now or timezone.now()
    starts_at = getattr(exam, 'starts_at', None)
    ends_at = getattr(exam, 'ends_at', None)

    if starts_at and current_time < starts_at:
        return 'upcoming'

    if ends_at and current_time >= ends_at:
        return 'ended'

    return 'live'


def compute_attempt_expiry(exam: Any, started_at: Optional[datetime] = None, now: Optional[datetime] = None) -> datetime:
    """
    Computes a student's personal attempt deadline:
    expires_at = min(started_at + duration, ends_at) if ends_at is defined.
    """
    start = started_at or (now or timezone.now())
    duration_delta = timedelta(minutes=getattr(exam, 'duration_minutes', 60))
    natural_deadline = start + duration_delta

    ends_at = getattr(exam, 'ends_at', None)
    if ends_at and ends_at < natural_deadline:
        return ends_at
    return natural_deadline


def format_exam_schedule_display(exam: Any, target_timezone: Optional[str] = None) -> Dict[str, Any]:
    """
    Formats the exam schedule with human-readable timestamps localized to the
    exam's display timezone (e.g. Asia/Kolkata).
    """
    tz_str = get_valid_timezone(target_timezone or getattr(exam, 'display_timezone', None))
    tz = zoneinfo.ZoneInfo(tz_str)
    starts_at = getattr(exam, 'starts_at', None)
    ends_at = getattr(exam, 'ends_at', None)

    def _fmt(dt):
        if not dt:
            return None
        dt_local = dt.astimezone(tz)
        return dt_local.strftime('%d %b %Y, %I:%M %p')

    starts_local = _fmt(starts_at)
    ends_local = _fmt(ends_at)

    summary = ""
    if starts_local and ends_local:
        summary = f"Opens {starts_local} and closes {ends_local} ({tz_str})"
    elif starts_local:
        summary = f"Opens {starts_local} ({tz_str})"
    elif ends_local:
        summary = f"Closes {ends_local} ({tz_str})"
    else:
        summary = "Open schedule (Always available)"

    return {
        'timezone': tz_str,
        'starts_at_iso': starts_at.isoformat() if starts_at else None,
        'ends_at_iso': ends_at.isoformat() if ends_at else None,
        'starts_at_display': starts_local,
        'ends_at_display': ends_local,
        'summary': summary,
        'phase': get_exam_schedule_phase(exam),
    }


def finalize_overdue_attempts(batch_size: int = 100, now: Optional[datetime] = None) -> int:
    """
    Auto-finalizes all in-progress student attempts that have exceeded either:
    1. Their personal `expires_at` deadline.
    2. The exam window's `ends_at` time.

    Safe, idempotent, uses select_for_update() row locking to prevent race conditions
    with student manual submissions.
    Returns the count of attempts finalized.
    """
    from api.models import StudentAttempt
    from api.utils.scoring import calculate_and_save_attempt_score

    current_time = now or timezone.now()
    grace_delta = timedelta(seconds=SUBMIT_NETWORK_GRACE_SECONDS)
    effective_cutoff = current_time - grace_delta

    # Find attempts where personal deadline OR exam window has passed
    overdue_qs = StudentAttempt.objects.filter(
        status=StudentAttempt.Status.IN_PROGRESS
    ).filter(
        Q(expires_at__isnull=False, expires_at__lte=effective_cutoff) |
        Q(exam__ends_at__isnull=False, exam__ends_at__lte=effective_cutoff)
    ).values_list('id', flat=True)[:batch_size]

    candidate_ids = list(overdue_qs)
    if not candidate_ids:
        return 0

    finalized_count = 0

    from django.db import connection

    for attempt_id in candidate_ids:
        try:
            with transaction.atomic():
                attempt_qs = StudentAttempt.objects.filter(
                    id=attempt_id, status=StudentAttempt.Status.IN_PROGRESS
                ).select_related('exam')

                if getattr(connection.features, 'has_select_for_update', False):
                    if getattr(connection.features, 'has_select_for_update_skip_locked', False):
                        attempt_qs = attempt_qs.select_for_update(skip_locked=True)
                    else:
                        attempt_qs = attempt_qs.select_for_update()

                attempt = attempt_qs.first()
                if not attempt:
                    continue

                exam_ends = attempt.exam.ends_at
                personal_expires = attempt.expires_at or (attempt.started_at + timedelta(minutes=attempt.exam.duration_minutes))

                # Determine submit reason
                if exam_ends and current_time >= exam_ends:
                    reason = 'window_closed'
                    official_submit_time = min(current_time, exam_ends)
                else:
                    reason = 'time_up'
                    official_submit_time = min(current_time, personal_expires)

                attempt.status = StudentAttempt.Status.AUTO_SUBMITTED
                attempt.submitted_at = official_submit_time
                attempt.submit_reason = reason
                attempt.save(update_fields=['status', 'submitted_at', 'submit_reason'])

                calculate_and_save_attempt_score(attempt, is_auto_submit=True)
                finalized_count += 1
                logger.info(
                    "Auto-finalized overdue attempt id=%s student_id=%s reason=%s submit_time=%s",
                    attempt.id, attempt.student_id, reason, official_submit_time
                )
        except Exception as exc:
            logger.exception("Error auto-finalizing attempt id=%s: %s", attempt_id, exc)

    return finalized_count


_daemon_started = False
_daemon_lock = threading.Lock()


def start_schedule_cleaner_daemon(interval_seconds: int = 30):
    """
    Starts an in-process daemon thread that periodically runs `finalize_overdue_attempts()`.
    Only started once per process, and skips test/migration/CLI commands.
    """
    global _daemon_started
    with _daemon_lock:
        if _daemon_started:
            return
        import sys
        import os
        argv = ' '.join(sys.argv).lower()
        if any(cmd in argv for cmd in ['test', 'makemigrations', 'migrate', 'collectstatic', 'finalize_overdue_attempts', 'shell']):
            return
        if 'runserver' in argv and os.environ.get('RUN_MAIN') != 'true':
            return

        def _cleaner_loop():
            logger.info("Exam schedule background cleaner daemon started (interval=%ss).", interval_seconds)
            while True:
                try:
                    time.sleep(interval_seconds)
                    finalize_overdue_attempts()
                except Exception as exc:
                    logger.warning("Error in exam schedule cleaner daemon: %s", exc)
                    time.sleep(10)

        thread = threading.Thread(target=_cleaner_loop, daemon=True, name="ExamScheduleCleanerDaemon")
        thread.start()
        _daemon_started = True

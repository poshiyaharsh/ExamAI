"""
Shared Server-Side Result Status Engine.
Single source of truth for student attempt evaluation statuses across:
- Student Dashboard
- Student Performance Page
- Faculty Live Monitoring & History
- Admin Exam Analytics

Guarantees:
- Safe against divide-by-zero on 0-mark exams.
- 'Pass'/'Fail' only emitted when fully evaluated.
- 'Pending grading' emitted for attempts awaiting subjective review (provisional score).
- 'Auto-submitted' retains exact submit reason (time up vs violations).
- 'Not attempted' / 'Absent' never displays 0% or Fail.
"""

from typing import Any, Dict, Optional
from django.utils import timezone
from .scoring import PASSING_PERCENTAGE


class ResultStatusCode:
    PASS = 'pass'
    FAIL = 'fail'
    PENDING_GRADING = 'pending_grading'
    AUTO_SUBMITTED = 'auto_submitted'
    IN_PROGRESS = 'in_progress'
    EXPIRED = 'expired'
    NOT_ATTEMPTED = 'not_attempted'


def compute_attempt_result_status(
    attempt: Optional[Any],
    exam: Optional[Any] = None,
    passing_threshold_pct: float = PASSING_PERCENTAGE,
    has_pending_subjectives: Optional[bool] = None,
) -> Dict[str, Any]:
    """
    Computes canonical status dictionary for an attempt and/or exam.
    Returns:
        {
            'status_code': str,          # pass, fail, pending_grading, auto_submitted, in_progress, not_attempted, expired
            'label': str,                # Human-readable short label for badges ('Pass', 'Fail', 'Pending grading', etc.)
            'sub_label': str,            # Secondary hint ('Provisional', 'Time up', 'Rule violations')
            'tooltip': str,              # Accessible description explaining the state
            'badge_variant': str,        # emerald, rose, amber, blue, slate
            'is_passed': Optional[bool], # True, False, or None (if pending/not attempted)
            'is_provisional': bool,      # True if score is pending further grading
            'marks_obtained': Optional[float],
            'total_marks': float,
            'percentage': Optional[float],
            'submit_reason': str,
            'requires_grading': bool,
        }
    """
    if exam is None and attempt is not None:
        exam = getattr(attempt, 'exam', None)

    exam_total = 0.0
    if attempt and getattr(attempt, 'max_score', 0):
        try:
            exam_total = float(attempt.max_score)
        except (ValueError, TypeError):
            exam_total = 0.0
    if not exam_total and exam and getattr(exam, 'total_marks', 0):
        try:
            exam_total = float(exam.total_marks)
        except (ValueError, TypeError):
            exam_total = 0.0

    # 1. Not Attempted (Absent)
    if attempt is None:
        return {
            'status_code': ResultStatusCode.NOT_ATTEMPTED,
            'label': 'Not attempted',
            'sub_label': 'Absent',
            'tooltip': 'The exam window ended without an attempt being started.',
            'badge_variant': 'slate',
            'is_passed': None,
            'is_provisional': False,
            'marks_obtained': None,
            'total_marks': exam_total,
            'percentage': None,
            'submit_reason': '',
            'requires_grading': False,
        }

    status_str = str(getattr(attempt, 'status', '')).lower()
    submit_reason = str(getattr(attempt, 'submit_reason', '') or '').lower()
    total_score = float(getattr(attempt, 'total_score', 0.0) or 0.0)
    violation_count = int(getattr(attempt, 'violation_count', 0) or 0)

    # Calculate percentage safely
    percentage = 0.0
    if exam_total > 0:
        percentage = round((total_score / exam_total) * 100.0, 1)

    # 2. In Progress
    if status_str in {'in_progress', 'started'}:
        # Check if already expired
        expires_at = getattr(attempt, 'expires_at', None)
        if expires_at and timezone.now() > expires_at:
            return {
                'status_code': ResultStatusCode.EXPIRED,
                'label': 'Expired',
                'sub_label': 'Unsubmitted',
                'tooltip': 'Exam testing duration expired before submission.',
                'badge_variant': 'slate',
                'is_passed': False,
                'is_provisional': False,
                'marks_obtained': total_score,
                'total_marks': exam_total,
                'percentage': percentage,
                'submit_reason': 'expired',
                'requires_grading': False,
            }
        return {
            'status_code': ResultStatusCode.IN_PROGRESS,
            'label': 'In progress',
            'sub_label': 'Active session',
            'tooltip': 'Student is actively taking this examination.',
            'badge_variant': 'blue',
            'is_passed': None,
            'is_provisional': True,
            'marks_obtained': total_score,
            'total_marks': exam_total,
            'percentage': percentage,
            'submit_reason': submit_reason,
            'requires_grading': False,
        }

    # 3. Check if subjective answers are pending review
    pending_grading = False
    if has_pending_subjectives is not None:
        pending_grading = has_pending_subjectives
    else:
        # Check if status is submitted (which scoring sets when subjectives exist)
        # or if any StudentAnswer has evaluation_status == 'pending_review'
        if status_str == 'submitted':
            pending_grading = True
        elif hasattr(attempt, 'answers'):
            try:
                from ..models import StudentAnswer
                pending_grading = attempt.answers.filter(
                    evaluation_status=StudentAnswer.EvaluationStatus.PENDING_REVIEW
                ).exclude(
                    answer_text='', blank_answers=[]
                ).exists()
            except Exception:
                pending_grading = False

    if pending_grading:
        return {
            'status_code': ResultStatusCode.PENDING_GRADING,
            'label': 'Pending grading',
            'sub_label': 'Provisional score',
            'tooltip': 'Subjective answers are awaiting faculty review. Displayed marks are provisional.',
            'badge_variant': 'amber',
            'is_passed': None,  # Neither pass nor fail until all questions are graded
            'is_provisional': True,
            'marks_obtained': total_score,
            'total_marks': exam_total,
            'percentage': percentage,
            'submit_reason': submit_reason,
            'requires_grading': True,
        }

    # Determine pass/fail outcome for fully graded attempts
    is_passed = percentage >= passing_threshold_pct

    # If attempt has not yet been finalized by faculty, mark as provisional
    review_status = getattr(attempt, 'review_status', None)
    if review_status in {'auto_evaluated', 'in_review'}:
        sub_text = "In review" if review_status == 'in_review' else "Provisional, not yet reviewed"
        return {
            'status_code': ResultStatusCode.PENDING_GRADING if pending_grading else ('pass' if is_passed else 'fail'),
            'label': 'Provisional Result',
            'sub_label': sub_text,
            'tooltip': f"Evaluated automatically ({total_score}/{exam_total} marks, {percentage}%). Subject to faculty review.",
            'badge_variant': 'amber',
            'is_passed': is_passed,
            'is_provisional': True,
            'marks_obtained': total_score,
            'total_marks': exam_total,
            'percentage': percentage,
            'submit_reason': submit_reason,
            'requires_grading': True,
        }

    # 4. Auto-Submitted
    if status_str == 'auto_submitted' or submit_reason in {'violations', 'time_up'}:
        reason_desc = (
            f"Auto-submitted due to rule violations ({violation_count} warnings logged)."
            if submit_reason == 'violations'
            else "Auto-submitted when testing time limit was reached."
            if submit_reason == 'time_up'
            else "Auto-submitted by system."
        )
        sub_text = "Rule violations" if submit_reason == 'violations' else ("Time limit" if submit_reason == 'time_up' else "Auto")
        return {
            'status_code': ResultStatusCode.AUTO_SUBMITTED,
            'label': 'Auto-submitted',
            'sub_label': sub_text,
            'tooltip': f"{reason_desc} Scored {total_score}/{exam_total} ({percentage}%). Outcome: {'Pass' if is_passed else 'Fail'}.",
            'badge_variant': 'rose' if not is_passed else 'amber',
            'is_passed': is_passed,
            'is_provisional': False,
            'marks_obtained': total_score,
            'total_marks': exam_total,
            'percentage': percentage,
            'submit_reason': submit_reason,
            'requires_grading': False,
        }

    # 5. Normal Completed (Pass or Fail)
    if is_passed:
        return {
            'status_code': ResultStatusCode.PASS,
            'label': 'Pass',
            'sub_label': f"≥ {passing_threshold_pct:.0f}%",
            'tooltip': f"Scored {total_score}/{exam_total} ({percentage}%). Passed the required threshold of {passing_threshold_pct:.0f}%.",
            'badge_variant': 'emerald',
            'is_passed': True,
            'is_provisional': False,
            'marks_obtained': total_score,
            'total_marks': exam_total,
            'percentage': percentage,
            'submit_reason': submit_reason,
            'requires_grading': False,
        }
    else:
        return {
            'status_code': ResultStatusCode.FAIL,
            'label': 'Fail',
            'sub_label': f"< {passing_threshold_pct:.0f}%",
            'tooltip': f"Scored {total_score}/{exam_total} ({percentage}%). Below the required passing mark of {passing_threshold_pct:.0f}%.",
            'badge_variant': 'rose',
            'is_passed': False,
            'is_provisional': False,
            'marks_obtained': total_score,
            'total_marks': exam_total,
            'percentage': percentage,
            'submit_reason': submit_reason,
            'requires_grading': False,
        }

"""Centralized, reusable service for exam eligibility and live status.
Single source of truth used across Admin Dashboard, Faculty Dashboard, and Student Exam views.
Guarantees strict multi-tenant isolation, department normalization, and invariant counts.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple
from django.db import models
from django.db.models import Count, Q, QuerySet
from django.utils import timezone

from api.models import Exam, StudentAttempt
from students.models import StudentProfile
from api.utils.departments import get_faculty_department, normalize_department


COMPLETED_STATUSES = [
    StudentAttempt.Status.SUBMITTED,
    StudentAttempt.Status.AUTO_SUBMITTED,
    StudentAttempt.Status.EVALUATED,
]


def get_exam_canonical_department(exam: Exam) -> str:
    """Return the normalized department for an exam, falling back to the creator faculty's department."""
    dept = normalize_department(getattr(exam, 'department', ''))
    if not dept and getattr(exam, 'created_by', None):
        dept = get_faculty_department(exam.created_by)
    return dept


def eligible_students_queryset(exam: Exam) -> QuerySet[StudentProfile]:
    """
    Returns a QuerySet of StudentProfile records eligible for a given Exam.
    Guarantees:
    1. student.institution == exam.institution (never trust request input)
    2. student.department matches exam.department (normalized comparison)
    3. student.user.is_active is True
    4. future-proof: if batch/semester/section is specified on exam, matches student
    """
    if not exam or not exam.institution_id:
        return StudentProfile.objects.none()

    exam_dept = get_exam_canonical_department(exam)
    if not exam_dept:
        return StudentProfile.objects.none()

    qs = StudentProfile.objects.filter(
        institution_id=exam.institution_id,
        user__is_active=True,
    ).select_related('user', 'institution')

    # Department normalized matching
    qs = qs.filter(department__iexact=exam_dept)

    # Future-proof optional batch / semester / section filtering if present on exam
    if hasattr(exam, 'batch') and getattr(exam, 'batch', None):
        if hasattr(StudentProfile, 'batch'):
            qs = qs.filter(batch__iexact=exam.batch)

    if hasattr(exam, 'semester') and getattr(exam, 'semester', None):
        if hasattr(StudentProfile, 'semester'):
            qs = qs.filter(semester=exam.semester)

    return qs


def live_exams_queryset(institution: Any, now: Optional[datetime] = None) -> QuerySet[Exam]:
    """
    Returns a QuerySet of exams currently live for an institution.
    Guarantees:
    1. exam.institution == admin's institution
    2. status is published
    3. start_time <= now < end_time (or open schedule if starts_at/ends_at are null)
    """
    now = now or timezone.now()
    inst_id = getattr(institution, 'id', institution)
    if not inst_id:
        return Exam.objects.none()

    return Exam.objects.filter(
        institution_id=inst_id,
        status=Exam.Status.PUBLISHED,
    ).filter(
        Q(starts_at__isnull=True) | Q(starts_at__lte=now),
        Q(ends_at__isnull=True) | Q(ends_at__gt=now),
    ).select_related('created_by', 'created_by__faculty_profile', 'institution')


def is_student_eligible(exam: Exam, student_user: Any) -> Tuple[bool, str]:
    """
    Single source of truth boolean helper checking if a student user is eligible for an exam.
    Used by student list, start-exam, and submit-exam.
    Returns:
        (is_eligible: bool, reason_message: str)
    """
    if not student_user or not student_user.is_authenticated:
        return False, "Authentication required."

    if not student_user.is_active:
        return False, "Student account is inactive."

    profile = getattr(student_user, 'student_profile', None)
    if not profile or not profile.institution_id:
        return False, "Student profile or institution missing."

    if profile.institution_id != exam.institution_id:
        return False, "Exam belongs to a different institution."

    if exam.status != Exam.Status.PUBLISHED:
        return False, "Exam is not published."

    exam_dept = get_exam_canonical_department(exam)
    student_dept = normalize_department(profile.department)
    if not student_dept or student_dept.lower() != exam_dept.lower():
        return False, f"Department mismatch: student is in '{student_dept}', exam is for '{exam_dept}'."

    # Batch / semester check if applicable
    if hasattr(exam, 'batch') and getattr(exam, 'batch', None):
        student_batch = getattr(profile, 'batch', '')
        if student_batch and student_batch.lower() != exam.batch.lower():
            return False, f"Batch mismatch: student is in '{student_batch}', exam is for '{exam.batch}'."

    return True, ""


def compute_live_exam_metrics(
    exam: Exam,
    now: Optional[datetime] = None,
    eligible_students_qs: Optional[QuerySet[StudentProfile]] = None,
) -> Dict[str, Any]:
    """
    Computes participation metrics for a single live exam while strictly enforcing the invariant:
    not_started + in_progress + submitted == eligible_count
    """
    now = now or timezone.now()
    eligible_qs = eligible_students_qs if eligible_students_qs is not None else eligible_students_queryset(exam)
    eligible_count = eligible_qs.count()
    eligible_user_ids: Set[int] = set(eligible_qs.values_list('user_id', flat=True))

    attempts = StudentAttempt.objects.filter(
        exam=exam,
    ).values('student_id', 'status', 'violation_count')

    submitted_count = 0
    in_progress_count = 0
    ineligible_attempts = 0
    flagged_user_ids: Set[int] = set()
    total_violations = 0

    for att in attempts:
        s_id = att['student_id']
        st = att['status']
        vc = int(att['violation_count'] or 0)
        total_violations += vc
        if vc > 0:
            flagged_user_ids.add(s_id)

        if s_id in eligible_user_ids:
            if st in COMPLETED_STATUSES:
                submitted_count += 1
            elif st == StudentAttempt.Status.IN_PROGRESS:
                in_progress_count += 1
        else:
            ineligible_attempts += 1

    not_started_count = max(0, eligible_count - (submitted_count + in_progress_count))

    participation_percent = (
        round((submitted_count / eligible_count) * 100.0, 1) if eligible_count > 0 else 0.0
    )

    seconds_remaining = None
    if exam.ends_at:
        seconds_remaining = max(0, int((exam.ends_at - now).total_seconds()))

    window_total_seconds = None
    if exam.starts_at and exam.ends_at:
        window_total_seconds = max(1, int((exam.ends_at - exam.starts_at).total_seconds()))

    creator = exam.created_by
    f_name = f"{creator.first_name} {creator.last_name}".strip() or creator.username if creator else "Faculty"

    return {
        'id': exam.id,
        'title': exam.title,
        'department': get_exam_canonical_department(exam),
        'faculty_name': f_name,
        'duration_minutes': exam.duration_minutes,
        'total_marks': exam.total_marks,
        'starts_at': exam.starts_at.isoformat() if exam.starts_at else None,
        'ends_at': exam.ends_at.isoformat() if exam.ends_at else None,
        'server_now': now.isoformat(),
        'seconds_remaining': seconds_remaining,
        'window_total_seconds': window_total_seconds,
        'assigned_total': eligible_count,
        'eligible_count': eligible_count,
        'eligible_students': eligible_count,  # backward compatibility alias
        'submitted_count': submitted_count,
        'submitted': submitted_count,
        'in_progress_count': in_progress_count,
        'in_progress': in_progress_count,
        'not_started_count': not_started_count,
        'not_started': not_started_count,
        'flagged_students': len(flagged_user_ids),
        'total_violations': total_violations,
        'participation_percent': participation_percent,
        'ineligible_attempts': ineligible_attempts,
    }


def compute_batch_live_exam_metrics(
    exams: List[Exam],
    institution: Any,
    now: Optional[datetime] = None,
    all_live_exams: Optional[List[Exam]] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Computes live metrics for a list of exams in CONSTANT DATABASE QUERIES (O(1) queries).
    If all_live_exams is provided, summary totals (live_exams_count, total_eligible_unique, etc.)
    are aggregated across all_live_exams, while metrics_list is returned for the shown exams.
    Returns:
        (exams_metrics_list, summary_totals_dict)
    """
    now = now or timezone.now()
    summary_source = all_live_exams if all_live_exams is not None else exams
    if not exams and not summary_source:
        return [], {
            'live_exams_count': 0,
            'total_eligible_unique': 0,
            'total_in_progress': 0,
            'total_submitted': 0,
            'total_not_started': 0,
        }

    inst_id = getattr(institution, 'id', institution)

    # Query 1: Fetch all active student profiles for this institution
    all_students = list(
        StudentProfile.objects.filter(
            institution_id=inst_id,
            user__is_active=True,
        ).select_related('user')
    )

    # Index students by normalized department
    students_by_dept: Dict[str, List[StudentProfile]] = {}
    for sp in all_students:
        d = normalize_department(sp.department).lower()
        students_by_dept.setdefault(d, []).append(sp)

    # Query 2: Fetch all attempts for these exams in ONE query
    needed_exam_ids = list({e.id for e in (exams + summary_source)})
    all_attempts = list(
        StudentAttempt.objects.filter(
            exam_id__in=needed_exam_ids,
        ).values('exam_id', 'student_id', 'status')
    ) if needed_exam_ids else []

    attempts_by_exam: Dict[int, List[Dict[str, Any]]] = {}
    for att in all_attempts:
        attempts_by_exam.setdefault(att['exam_id'], []).append(att)

    # Compute summary totals across summary_source (all live exams in institution)
    unique_eligible_users: Set[int] = set()
    total_in_progress = 0
    total_submitted = 0
    total_not_started = 0

    for e in summary_source:
        dept_key = get_exam_canonical_department(e).lower()
        dept_students = students_by_dept.get(dept_key, [])
        eligible_count = len(dept_students)
        eligible_user_ids = {s.user_id for s in dept_students}
        unique_eligible_users.update(eligible_user_ids)

        e_attempts = attempts_by_exam.get(e.id, [])
        submitted_cnt = 0
        in_prog_cnt = 0
        for att in e_attempts:
            s_id = att['student_id']
            st = att['status']
            if s_id in eligible_user_ids:
                if st in COMPLETED_STATUSES:
                    submitted_cnt += 1
                elif st == StudentAttempt.Status.IN_PROGRESS:
                    in_prog_cnt += 1

        not_started_cnt = max(0, eligible_count - (submitted_cnt + in_prog_cnt))
        total_in_progress += in_prog_cnt
        total_submitted += submitted_cnt
        total_not_started += not_started_cnt

    # Compute detailed metrics list for the shown exams
    metrics_list: List[Dict[str, Any]] = []
    for e in exams:
        dept_key = get_exam_canonical_department(e).lower()
        dept_students = students_by_dept.get(dept_key, [])
        eligible_count = len(dept_students)
        eligible_user_ids = {s.user_id for s in dept_students}

        e_attempts = attempts_by_exam.get(e.id, [])
        submitted_cnt = 0
        in_prog_cnt = 0
        inelig_att = 0

        for att in e_attempts:
            s_id = att['student_id']
            st = att['status']
            if s_id in eligible_user_ids:
                if st in COMPLETED_STATUSES:
                    submitted_cnt += 1
                elif st == StudentAttempt.Status.IN_PROGRESS:
                    in_prog_cnt += 1
            else:
                inelig_att += 1

        not_started_cnt = max(0, eligible_count - (submitted_cnt + in_prog_cnt))
        part_pct = round((submitted_cnt / eligible_count) * 100.0, 1) if eligible_count > 0 else 0.0

        seconds_remaining = None
        if e.ends_at:
            seconds_remaining = max(0, int((e.ends_at - now).total_seconds()))

        u = e.created_by
        f_name = f"{u.first_name} {u.last_name}".strip() or u.username if u else "Faculty"

        metrics_list.append({
            'id': e.id,
            'title': e.title,
            'department': get_exam_canonical_department(e),
            'faculty_name': f_name,
            'duration_minutes': e.duration_minutes,
            'total_marks': e.total_marks,
            'starts_at': e.starts_at.isoformat() if e.starts_at else None,
            'ends_at': e.ends_at.isoformat() if e.ends_at else None,
            'seconds_remaining': seconds_remaining,
            'eligible_count': eligible_count,
            'eligible_students': eligible_count,  # backward compatibility alias
            'submitted_count': submitted_cnt,
            'in_progress_count': in_prog_cnt,
            'not_started_count': not_started_cnt,
            'participation_percent': part_pct,
            'ineligible_attempts': inelig_att,
        })

    summary = {
        'live_exams_count': len(summary_source),
        'total_eligible_unique': len(unique_eligible_users),
        'total_in_progress': total_in_progress,
        'total_submitted': total_submitted,
        'total_not_started': total_not_started,
    }

    return metrics_list, summary

"""Centralized department utilities and permissions for ExamAI."""

import logging
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

DEFAULT_DEPARTMENT_NAMES = [
    'Computer Science',
    'Information Technology',
    'Electronics and Communication',
    'Mechanical Engineering',
    'Civil Engineering',
    'Electrical Engineering',
    'Business Administration',
    'Commerce',
    'Mathematics',
    'Physics',
    'Chemistry',
]

# Canonical lookup mapping lowercased names to proper title-cased standard department
DEPARTMENT_LOOKUP = {
    dept.strip().lower(): dept.strip()
    for dept in DEFAULT_DEPARTMENT_NAMES
}


def normalize_department(value: Optional[str]) -> str:
    """Normalize a department string by trimming and matching standard casing."""
    if not value:
        return ''
    cleaned = ' '.join(str(value).strip().split())
    lower_cleaned = cleaned.lower()
    return DEPARTMENT_LOOKUP.get(lower_cleaned, cleaned)


def get_valid_department_names(institution=None):
    """
    Returns the list of valid department names.
    If an institution is provided, uses its AdminDepartment catalog, initializing
    missing defaults if necessary. Otherwise returns DEFAULT_DEPARTMENT_NAMES.
    """
    if not institution:
        return list(DEFAULT_DEPARTMENT_NAMES)

    try:
        from admins.models import AdminDepartment
        existing = list(
            AdminDepartment.objects.filter(institution=institution)
            .order_by('department_name')
            .values_list('department_name', flat=True)
        )
        if not existing:
            # Seed default departments for institution if none exist
            AdminDepartment.objects.bulk_create(
                [AdminDepartment(institution=institution, department_name=dept) for dept in DEFAULT_DEPARTMENT_NAMES],
                ignore_conflicts=True,
            )
            existing = list(
                AdminDepartment.objects.filter(institution=institution)
                .order_by('department_name')
                .values_list('department_name', flat=True)
            )
        return existing or list(DEFAULT_DEPARTMENT_NAMES)
    except Exception:
        return list(DEFAULT_DEPARTMENT_NAMES)


def validate_department_name(value: Optional[str], institution=None) -> Tuple[bool, str]:
    """
    Validates whether a department string is allowed.
    Returns (is_valid, normalized_department_name).
    """
    if not value or not str(value).strip():
        return False, ''

    cleaned = ' '.join(str(value).strip().split())
    valid_names = get_valid_department_names(institution)
    valid_lookup = {name.lower(): name for name in valid_names}

    if cleaned.lower() in valid_lookup:
        return True, valid_lookup[cleaned.lower()]

    if cleaned.lower() in DEPARTMENT_LOOKUP:
        return True, DEPARTMENT_LOOKUP[cleaned.lower()]

    return False, cleaned


def get_student_department(user) -> str:
    """Safely retrieve the normalized department for a student user."""
    if not user or not user.is_authenticated:
        return ''
    profile = getattr(user, 'student_profile', None)
    if profile and profile.department:
        return normalize_department(profile.department)
    return ''


def get_faculty_department(user) -> str:
    """Safely retrieve the normalized department for a faculty user."""
    if not user or not user.is_authenticated:
        return ''
    profile = getattr(user, 'faculty_profile', None)
    if profile and profile.department:
        return normalize_department(profile.department)
    return ''


from django.db import models
from django.utils import timezone


def is_exam_visible_to_student(exam, user) -> Tuple[bool, bool, str]:
    """
    Determine if an exam is visible to a student and whether they can start it now.
    Returns:
        (visible: bool, can_start: bool, reason_message: str)
    Rules:
        - Only published exams are visible to students.
        - Tenant isolation: student and exam must belong to the exact same institution.
        - Department matching: student department must match exam department
          (or creating faculty's department as an approved fallback).
        - Schedule window:
          * If scheduled in the future: visible as upcoming, but can_start is False.
          * If ended: visible=False (or not startable if viewing past results).
          * If active: visible=True, can_start=True.
    """
    if not user or not user.is_authenticated:
        return False, False, 'Authentication required.'

    from api.exams.eligibility import is_student_eligible
    eligible, reason = is_student_eligible(exam, user)
    if not eligible:
        return False, False, reason

    # Schedule validation
    from api.utils.schedule import get_exam_schedule_phase, format_exam_schedule_display
    now = timezone.now()
    phase = get_exam_schedule_phase(exam, now)
    sched = format_exam_schedule_display(exam)

    if phase == 'upcoming':
        # Scheduled in the future: visible to students in list as upcoming, but cannot start yet
        return True, False, f"Exam is scheduled for {sched.get('starts_at_display', '')} ({sched.get('timezone', 'Asia/Kolkata')}). You cannot start it yet."

    if phase == 'ended':
        # Exam window closed: visible to students as ended/missed, but cannot start
        return True, False, f"Exam window closed on {sched.get('ends_at_display', '')} ({sched.get('timezone', 'Asia/Kolkata')})."

    return True, True, ''


def get_student_accessible_exams_queryset(user, tenant=None):
    """
    Return a queryset of published exams belonging to the student's tenant and department.
    Guarantees that students only see exams for their specific institution and department,
    with automatic fallback matching to the creating faculty's department.
    """
    from api.models import Exam
    from api.tenant import get_user_institution

    if not tenant:
        tenant = get_user_institution(user)
    if not tenant:
        return Exam.objects.none()

    student_dept = get_student_department(user)
    if not student_dept:
        return Exam.objects.none()

    return Exam.objects.filter(
        institution=tenant,
        status=Exam.Status.PUBLISHED,
    ).filter(
        models.Q(department__iexact=student_dept) |
        (models.Q(department='') & models.Q(created_by__faculty_profile__department__iexact=student_dept))
    )


def check_student_exam_access(user, exam) -> Tuple[bool, str]:
    """
    Backward-compatible gatekeeper for starting/saving exam attempts.
    Returns (allowed: bool, reason: str).
    """
    visible, can_start, reason = is_exam_visible_to_student(exam, user)
    if not visible:
        return False, reason or 'Access denied. Exam is not available.'
    if not can_start:
        return False, reason or 'Exam is not currently available for taking.'
    return True, ''


def get_exam_visibility_status_for_faculty(exam) -> dict:
    """
    Diagnostic helper for faculty and admin: explains exactly why students can
    or cannot see this exam, and displays eligible student counts.
    """
    from students.models import StudentProfile
    reasons = []

    # 1. Status check
    is_published = getattr(exam, 'status', '') == 'published'
    if not is_published:
        reasons.append(f"Not published (current status is '{getattr(exam, 'status', 'draft')}')")

    # 2. Questions check
    questions_count = exam.questions.count()
    if questions_count == 0:
        reasons.append("Exam has 0 questions")

    # 3. Department check
    exam_dept = normalize_department(getattr(exam, 'department', ''))
    if not exam_dept:
        faculty = getattr(exam, 'created_by', None)
        if faculty:
            exam_dept = get_faculty_department(faculty)
    if not exam_dept:
        reasons.append("No department assigned to this exam")

    # 4. Schedule check
    from api.utils.schedule import get_exam_schedule_phase, format_exam_schedule_display
    now = timezone.now()
    schedule_state = get_exam_schedule_phase(exam, now)
    sched_info = format_exam_schedule_display(exam)
    if schedule_state == 'upcoming':
        reasons.append(f"Scheduled in future (starts {sched_info.get('starts_at_display')} {sched_info.get('timezone')})")
    elif schedule_state == 'ended':
        reasons.append(f"Exam window closed (ended {sched_info.get('ends_at_display')} {sched_info.get('timezone')})")

    # 5. Eligible students count
    eligible_students = 0
    inst = getattr(exam, 'institution', None)
    inst_name = inst.institution_name if inst else "Unknown Institution"
    if inst and exam_dept:
        eligible_students = StudentProfile.objects.filter(
            institution=inst,
            department__iexact=exam_dept,
            user__is_active=True,
        ).count()

    is_visible_now = is_published and (schedule_state in {'live', 'active', 'upcoming'}) and bool(exam_dept) and questions_count > 0
    can_start_now = is_published and (schedule_state in {'live', 'active'}) and bool(exam_dept) and questions_count > 0

    if is_visible_now:
        status_summary = f"Visible to {eligible_students} student{'s' if eligible_students != 1 else ''} of {exam_dept}, {inst_name}"
    else:
        status_summary = f"Hidden from students: {', '.join(reasons)}"

    return {
        'is_visible': is_visible_now,
        'can_start_now': can_start_now,
        'schedule_state': schedule_state,
        'department': exam_dept,
        'institution_name': inst_name,
        'eligible_students_count': eligible_students,
        'status_summary': status_summary,
        'reasons': reasons,
    }


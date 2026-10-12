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


def check_student_exam_access(user, exam) -> Tuple[bool, str]:
    """
    Check if a student has permission to view or take an exam based on department.
    Returns (allowed: bool, reason_or_error_message: str).
    """
    if not user or not user.is_authenticated:
        return False, 'Authentication required.'

    from api.tenant import get_user_institution
    stu_inst = get_user_institution(user)
    exam_inst_id = getattr(exam, 'institution_id', None)
    if stu_inst and exam_inst_id and stu_inst.id != exam_inst_id:
        return False, 'Access denied. This exam belongs to a different institution.'

    student_dept = get_student_department(user)
    if not student_dept:
        return False, 'Your student profile does not have a department assigned.'

    exam_dept = normalize_department(getattr(exam, 'department', ''))
    if not exam_dept:
        # Fallback to creating faculty's department if exam.department is not set
        faculty = getattr(exam, 'created_by', None)
        if faculty:
            exam_dept = get_faculty_department(faculty)

    if not exam_dept:
        return False, 'This exam has no department assigned.'

    if student_dept.lower() != exam_dept.lower():
        return False, f'Access denied. This exam belongs to {exam_dept}, but your department is {student_dept}.'

    return True, ''

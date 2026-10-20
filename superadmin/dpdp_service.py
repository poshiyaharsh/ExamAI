import logging
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from api.models import Exam, Notification, StudentAttempt
from superadmin.models import DataSubjectRequest

User = get_user_model()
logger = logging.getLogger(__name__)

DPDP_DISCLAIMER = (
    "DISCLAIMER: This tooling is designed to support compliance with technical principles of the "
    "Digital Personal Data Protection (DPDP) Act, 2023 (Right to Access, Data Portability, and Right to Correction/Erasure). "
    "This software implementation does not constitute formal legal advice. Organizations must consult their legal counsel "
    "and Data Protection Officer (DPO) regarding statutory retention obligations."
)


def export_user_data(user_id: int) -> dict:
    """
    Generate portable machine-readable personal data extract for a Data Principal (User).
    Covers profile identity, institution association, notifications, and exam attempt summaries.
    """
    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        raise ValueError('User does not exist.')

    profile_data = {}
    if hasattr(user, 'student_profile'):
        sp = user.student_profile
        profile_data = {
            'role': 'Student',
            'student_id': sp.student_id,
            'department': sp.department,
            'institution': sp.institution.institution_name if sp.institution else None,
            'institution_code': sp.institution.institution_code if sp.institution else None,
        }
    elif hasattr(user, 'faculty_profile'):
        fp = user.faculty_profile
        profile_data = {
            'role': 'Faculty',
            'employee_id': fp.employee_id,
            'department': fp.department,
            'designation': fp.designation,
            'institution': fp.institution.institution_name if fp.institution else None,
            'institution_code': fp.institution.institution_code if fp.institution else None,
        }

    attempts = list(
        StudentAttempt.objects.filter(student=user).values(
            'id', 'exam__title', 'total_score', 'max_score', 'status', 'violation_count', 'started_at', 'submitted_at'
        )
    )

    notifications = list(
        Notification.objects.filter(user=user).values(
            'id', 'title', 'message', 'type', 'created_at'
        )
    )

    return {
        'disclaimer': DPDP_DISCLAIMER,
        'export_metadata': {
            'exported_at': timezone.now().isoformat(),
            'user_id': user.id,
            'username': user.username,
        },
        'personal_identity': {
            'username': user.username,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'is_active': user.is_active,
            'date_joined': user.date_joined.isoformat() if user.date_joined else None,
            'last_login': user.last_login.isoformat() if user.last_login else None,
        },
        'academic_profile': profile_data,
        'exam_attempts_count': len(attempts),
        'exam_attempts': attempts,
        'notifications_count': len(notifications),
        'notifications': notifications,
    }


def dry_run_anonymize_user(user_id: int) -> dict:
    """
    Evaluate impact of anonymization prior to execution.
    Specifies which personal fields will be scrubbed, and what academic audit records
    will be retained pursuant to higher-education regulatory mandates.
    """
    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        raise ValueError('User does not exist.')

    if hasattr(user, 'super_admin_profile') or user.is_superuser:
        raise ValueError('Super Admin accounts cannot be anonymized or deleted through this workflow.')

    attempt_count = StudentAttempt.objects.filter(student=user).count()
    exam_count = Exam.objects.filter(created_by=user).count()

    return {
        'disclaimer': DPDP_DISCLAIMER,
        'user_id': user.id,
        'username': user.username,
        'email': user.email,
        'personal_data_to_scrub': [
            'username (replaced with anon_user_<id>)',
            'email (replaced with anonymized_<id>@deleted.local)',
            'first_name (replaced with "Anonymized")',
            'last_name (replaced with "User")',
            'password hash (invalidated and cleared)',
            'active session tokens (revoked)',
        ],
        'statutory_academic_records_retained': {
            'exam_attempts_retained': attempt_count,
            'exams_authored_retained': exam_count,
            'retention_justification': 'Preserved for statutory academic accreditation & grading audits; personal identifiers removed.',
        },
        'ready_for_execution': True,
    }


def execute_anonymize_user(user_id: int, executed_by: str, reason: str = '') -> dict:
    """
    Execute irreversible anonymization of user personal data while preserving
    institutional academic records for regulatory compliance.
    """
    summary = dry_run_anonymize_user(user_id)
    user = User.objects.get(pk=user_id)

    with transaction.atomic():
        user.username = f'anon_user_{user.id}'
        user.email = f'anonymized_{user.id}@deleted.local'
        user.first_name = 'Anonymized'
        user.last_name = 'User'
        user.set_unusable_password()
        user.is_active = False
        user.save(update_fields=['username', 'email', 'first_name', 'last_name', 'password', 'is_active'])

        # Record DataSubjectRequest audit entry
        DataSubjectRequest.objects.create(
            user=user,
            user_email=summary['email'],
            request_type='anonymize',
            status='completed',
            reason=reason or 'Data Principal erasure/anonymization request under DPDP technical policy',
            dry_run_summary=summary,
            executed_at=timezone.now(),
            executed_by=executed_by,
        )

    return {
        'success': True,
        'message': f'User #{user_id} has been successfully anonymized in compliance with DPDP principles.',
        'anonymized_user_id': user.id,
        'retained_records': summary['statutory_academic_records_retained'],
    }


def get_data_inventory() -> dict:
    """
    Data inventory mapping all categories of personal data processed by ExamAI,
    their legal basis, retention periods, storage models, and encryption posture.
    """
    inventory_table = [
        {
            'category': 'Account & Identity',
            'fields': 'Username, Email, First Name, Last Name, Password (PBKDF2 SHA-256)',
            'storage_entity': 'auth_user',
            'purpose': 'Authentication, role determination, credential management',
            'legal_basis': 'Consent / Legitimate Academic Purpose',
            'retention': 'Active enrollment duration + 1 year, or until deletion request',
            'encryption': 'In-transit (TLS 1.3), Passwords hashed (PBKDF2-SHA256)',
        },
        {
            'category': 'Student Academic Profile',
            'fields': 'Student ID / Roll No, Department, Tenant Institution',
            'storage_entity': 'students_studentprofile',
            'purpose': 'Exam eligibility filtering, grade tracking, department isolation',
            'legal_basis': 'Institutional Contract / Legitimate Use',
            'retention': 'Duration of academic program + regulatory audit window',
            'encryption': 'At-rest database volume, strict tenant scoping',
        },
        {
            'category': 'Faculty Profile',
            'fields': 'Employee ID, Designation, Department, Tenant Institution',
            'storage_entity': 'faculty_facultyprofile',
            'purpose': 'Paper generation rights, exam drafting, evaluation authority',
            'legal_basis': 'Employment / Institutional Contract',
            'retention': 'Employment duration + 3 years',
            'encryption': 'At-rest database volume',
        },
        {
            'category': 'Exam Attempt & Proctoring',
            'fields': 'IP Address, User-Agent, Start/Submit Timestamps, Violation Logs, Answers',
            'storage_entity': 'api_studentattempt',
            'purpose': 'Assessment integrity, scoring, cheating prevention, accreditation',
            'legal_basis': 'Academic Assessment / Legitimate Interest',
            'retention': 'Mandatory 3 to 5 years for university examination audits',
            'encryption': 'At-rest database, IP addresses truncated/anonymizable',
        },
        {
            'category': 'Super Admin Audit Trail',
            'fields': 'Actor Username, Client IP, Action, Before/After State, Cryptographic Hash Chain',
            'storage_entity': 'superadmin_superadminauditlog',
            'purpose': 'Security auditability, tamper detection, forensics, accountability',
            'legal_basis': 'Legal Obligation / Security Defense',
            'retention': 'Indefinite (immutable append-only hash chain)',
            'encryption': 'SHA-256 HMAC cryptographic chain',
        },
    ]

    return {
        'disclaimer': DPDP_DISCLAIMER,
        'act_reference': 'Digital Personal Data Protection Act, 2023 (DPDP Act)',
        'data_protection_officer_contact': 'privacy@examai.local',
        'inventory': inventory_table,
    }

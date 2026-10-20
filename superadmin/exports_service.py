import csv
import io
import logging
from django.contrib.auth import get_user_model
from django.utils import timezone

from admins.models import AdminInstitution
from api.models import Exam, StudentAttempt
from superadmin.models import SuperAdminAuditLog

User = get_user_model()
logger = logging.getLogger(__name__)


def sanitize_csv_cell(value) -> str:
    """
    Prevent CSV / Formula Injection (CWE-1236).
    If cell begins with '=', '+', '-', '@', '\t', or '\r', prefix with single quote.
    """
    if value is None:
        return ''
    val_str = str(value)
    if val_str and val_str[0] in ('=', '+', '-', '@', '\t', '\r'):
        return f"'{val_str}"
    return val_str


def export_entities_to_csv(entity_type: str, filters: dict = None) -> tuple[str, str]:
    """
    Generate sanitized CSV content for users, exams, attempts, or audit logs.
    Returns (csv_string, filename).
    """
    filters = filters or {}
    output = io.StringIO()
    writer = csv.writer(output)
    timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')

    if entity_type == 'users':
        filename = f'examai_users_export_{timestamp}.csv'
        writer.writerow(['User ID', 'Username', 'Email', 'Role', 'Institution', 'Department', 'Is Active', 'Date Joined'])
        qs = User.objects.select_related('student_profile', 'faculty_profile', 'admin_profile').all().order_by('-id')

        inst_id = filters.get('institution_id')
        if inst_id:
            qs = qs.filter(
                student_profile__institution_id=inst_id
            ) | qs.filter(
                faculty_profile__institution_id=inst_id
            ) | qs.filter(
                admin_institution__id=inst_id
            )

        for u in qs[:1000]:  # limit to safe batch size
            role = 'User'
            dept = ''
            inst_name = ''
            if hasattr(u, 'student_profile'):
                role = 'Student'
                dept = u.student_profile.department
                inst_name = u.student_profile.institution.institution_name if u.student_profile.institution else ''
            elif hasattr(u, 'faculty_profile'):
                role = 'Faculty'
                dept = u.faculty_profile.department
                inst_name = u.faculty_profile.institution.institution_name if u.faculty_profile.institution else ''
            elif hasattr(u, 'admin_profile'):
                role = 'Admin'
                inst_name = u.admin_institution.institution_name if hasattr(u, 'admin_institution') else ''

            writer.writerow([
                sanitize_csv_cell(u.id),
                sanitize_csv_cell(u.username),
                sanitize_csv_cell(u.email),
                sanitize_csv_cell(role),
                sanitize_csv_cell(inst_name),
                sanitize_csv_cell(dept),
                sanitize_csv_cell(u.is_active),
                sanitize_csv_cell(u.date_joined.strftime('%Y-%m-%d %H:%M:%S')),
            ])

    elif entity_type == 'exams':
        filename = f'examai_exams_export_{timestamp}.csv'
        writer.writerow(['Exam ID', 'Title', 'Institution', 'Department', 'Created By', 'Status', 'Total Marks', 'Starts At', 'Ends At'])
        qs = Exam.objects.select_related('institution', 'created_by').all().order_by('-id')
        if filters.get('institution_id'):
            qs = qs.filter(institution_id=filters['institution_id'])

        for e in qs[:1000]:
            writer.writerow([
                sanitize_csv_cell(e.id),
                sanitize_csv_cell(e.title),
                sanitize_csv_cell(e.institution.institution_name if e.institution else 'N/A'),
                sanitize_csv_cell(e.department),
                sanitize_csv_cell(e.created_by.username if e.created_by else 'N/A'),
                sanitize_csv_cell(e.status),
                sanitize_csv_cell(e.total_marks),
                sanitize_csv_cell(e.starts_at.isoformat() if e.starts_at else ''),
                sanitize_csv_cell(e.ends_at.isoformat() if e.ends_at else ''),
            ])

    elif entity_type == 'attempts':
        filename = f'examai_attempts_export_{timestamp}.csv'
        writer.writerow(['Attempt ID', 'Exam Title', 'Student Username', 'Institution', 'Score', 'Max Score', 'Status', 'Violations', 'Submitted At'])
        qs = StudentAttempt.objects.select_related('exam', 'student', 'exam__institution').all().order_by('-id')
        if filters.get('institution_id'):
            qs = qs.filter(exam__institution_id=filters['institution_id'])

        for a in qs[:1000]:
            writer.writerow([
                sanitize_csv_cell(a.id),
                sanitize_csv_cell(a.exam.title if a.exam else 'N/A'),
                sanitize_csv_cell(a.student.username if a.student else 'N/A'),
                sanitize_csv_cell(a.exam.institution.institution_name if (a.exam and a.exam.institution) else 'N/A'),
                sanitize_csv_cell(a.total_score),
                sanitize_csv_cell(a.max_score),
                sanitize_csv_cell(a.status),
                sanitize_csv_cell(a.violation_count),
                sanitize_csv_cell(a.submitted_at.isoformat() if a.submitted_at else ''),
            ])

    elif entity_type == 'audit_logs':
        filename = f'examai_audit_logs_export_{timestamp}.csv'
        writer.writerow(['ID', 'Timestamp', 'Actor', 'Action', 'Target Entity', 'Target ID', 'IP Address', 'Entry Hash'])
        qs = SuperAdminAuditLog.objects.all().order_by('-id')[:1000]
        for log in qs:
            writer.writerow([
                sanitize_csv_cell(log.id),
                sanitize_csv_cell(log.created_at.isoformat()),
                sanitize_csv_cell(log.actor_username),
                sanitize_csv_cell(log.action),
                sanitize_csv_cell(log.target_entity),
                sanitize_csv_cell(log.target_id),
                sanitize_csv_cell(log.ip_address),
                sanitize_csv_cell(log.entry_hash),
            ])

    else:
        raise ValueError(f'Unsupported export entity "{entity_type}".')

    return output.getvalue(), filename

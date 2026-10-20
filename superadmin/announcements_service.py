import html
import logging
from django.contrib.auth import get_user_model
from django.utils import timezone

from admins.models import AdminInstitution
from api.models import Notification
from faculty.models import FacultyProfile
from students.models import StudentProfile
from superadmin.models import SystemAnnouncement

User = get_user_model()
logger = logging.getLogger(__name__)


def sanitize_text(text: str) -> str:
    """Escape HTML special characters to completely prevent Cross-Site Scripting (XSS)."""
    if not text:
        return ''
    return html.escape(text.strip())


def create_and_dispatch_announcement(
    title: str,
    message: str,
    target_type: str = 'all',
    target_institute_id: int = None,
    target_department: str = '',
    target_role: str = '',
    start_date=None,
    end_date=None,
    created_by: str = 'superadmin',
) -> SystemAnnouncement:
    """
    Persist sanitized announcement and optionally create notification items for targeted users.
    """
    clean_title = sanitize_text(title)
    clean_message = sanitize_text(message)

    target_institute = None
    if target_institute_id:
        target_institute = AdminInstitution.objects.filter(pk=target_institute_id).first()

    announcement = SystemAnnouncement.objects.create(
        title=clean_title,
        message=clean_message,
        target_type=target_type,
        target_institute=target_institute,
        target_department=target_department,
        target_role=target_role,
        start_date=start_date or timezone.now(),
        end_date=end_date,
        is_active=True,
        created_by=created_by,
    )

    # Resolve target recipient users
    users_qs = User.objects.filter(is_active=True)
    if target_type == 'institute' and target_institute:
        student_user_ids = StudentProfile.objects.filter(institution=target_institute).values_list('user_id', flat=True)
        faculty_user_ids = FacultyProfile.objects.filter(institution=target_institute).values_list('user_id', flat=True)
        users_qs = users_qs.filter(id__in=set(student_user_ids) | set(faculty_user_ids) | {target_institute.admin_id})
    elif target_type == 'department' and target_department:
        s_ids = StudentProfile.objects.filter(department__iexact=target_department).values_list('user_id', flat=True)
        f_ids = FacultyProfile.objects.filter(department__iexact=target_department).values_list('user_id', flat=True)
        users_qs = users_qs.filter(id__in=set(s_ids) | set(f_ids))
    elif target_type == 'role' and target_role:
        if target_role == 'student':
            users_qs = users_qs.filter(student_profile__isnull=False)
        elif target_role == 'faculty':
            users_qs = users_qs.filter(faculty_profile__isnull=False)
        elif target_role == 'admin':
            users_qs = users_qs.filter(admin_profile__isnull=False)

    # Fan out up to 500 notifications (prevent huge bulk write blocks)
    recipient_users = list(users_qs[:500])
    notifications = [
        Notification(
            user=u,
            institution=target_institute,
            title=clean_title,
            message=clean_message,
            type=Notification.NotificationType.INFO,
        )
        for u in recipient_users
    ]
    if notifications:
        Notification.objects.bulk_create(notifications)
        logger.info('Dispatched announcement "%s" to %d users', clean_title, len(notifications))

    return announcement

import logging
import threading
from typing import Any, Dict, List, Optional, Tuple

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import connection, transaction
from django.db.models import Count, Q
from django.utils import timezone

from admins.models import AdminInstitution, AdminProfile
from api.models import Notification
from faculty.models import FacultyProfile
from students.models import StudentProfile
from superadmin.audit import GENESIS_HASH, compute_audit_hash
from superadmin.models import CampaignDeliveryRecord, NotificationCampaign, SuperAdminAuditLog

User = get_user_model()
logger = logging.getLogger(__name__)


def record_notify_audit(
    actor_username: str,
    action: str,
    target_entity: str = 'NotificationCampaign',
    target_id: str = '',
    description: str = '',
    before_state: Optional[Dict[str, Any]] = None,
    after_state: Optional[Dict[str, Any]] = None,
):
    """Writes an immutable audit log entry for notification campaigns."""
    try:
        last_entry = SuperAdminAuditLog.objects.order_by('-id').first()
        prev_hash = last_entry.entry_hash if (last_entry and last_entry.entry_hash) else GENESIS_HASH
        entry_hash = compute_audit_hash(
            prev_hash=prev_hash,
            actor_username=actor_username or 'system',
            action=action,
            target_entity=target_entity,
            target_id=str(target_id),
            description=description,
            ip_address='127.0.0.1',
            before_state=before_state or {},
            after_state=after_state or {},
        )
        return SuperAdminAuditLog.objects.create(
            actor_username=actor_username or 'system',
            action=action,
            target_entity=target_entity,
            target_id=str(target_id),
            description=description,
            before_state=before_state or {},
            after_state=after_state or {},
            ip_address='127.0.0.1',
            user_agent='ExamAI-NotificationEngine',
            prev_hash=prev_hash,
            entry_hash=entry_hash,
        )
    except Exception as exc:
        logger.error('Failed to log notification audit: %s', exc)
        return None


def get_recipients_queryset(
    target_audience: str,
    target_role: str = '',
    target_institute_id: Optional[int] = None,
    target_department: str = '',
    target_user_ids: Optional[List[int]] = None,
):
    """
    Resolves audience criteria to a filtered User queryset.
    Excludes super administrator accounts from broadcast blasts.
    """
    base_qs = User.objects.filter(is_active=True, is_superuser=False).exclude(username='harshposhiya')

    if target_audience == 'all':
        return base_qs

    elif target_audience == 'role':
        role = (target_role or '').lower()
        if role == 'student':
            return base_qs.filter(student_profile__isnull=False)
        elif role == 'faculty':
            return base_qs.filter(faculty_profile__isnull=False)
        elif role == 'admin':
            return base_qs.filter(admin_profile__isnull=False)
        return base_qs.none()

    elif target_audience == 'institute':
        if not target_institute_id:
            return base_qs.none()
        return base_qs.filter(
            Q(student_profile__institution_id=target_institute_id)
            | Q(faculty_profile__institution_id=target_institute_id)
            | Q(admin_profile__institution_id=target_institute_id)
        ).distinct()

    elif target_audience == 'department':
        if not target_department:
            return base_qs.none()
        dept = target_department.strip()
        qs = base_qs.filter(
            Q(student_profile__department__iexact=dept)
            | Q(faculty_profile__department__iexact=dept)
        )
        if target_institute_id:
            qs = qs.filter(
                Q(student_profile__institution_id=target_institute_id)
                | Q(faculty_profile__institution_id=target_institute_id)
            )
        return qs.distinct()

    elif target_audience == 'individual':
        if not target_user_ids:
            return base_qs.none()
        return base_qs.filter(id__in=target_user_ids)

    return base_qs.none()


def preview_campaign_audience(
    target_audience: str,
    target_role: str = '',
    target_institute_id: Optional[int] = None,
    target_department: str = '',
    target_user_ids: Optional[List[int]] = None,
) -> Dict[str, Any]:
    """
    Calculates recipient count and returns sample recipients for real-time live preview.
    """
    qs = get_recipients_queryset(
        target_audience=target_audience,
        target_role=target_role,
        target_institute_id=target_institute_id,
        target_department=target_department,
        target_user_ids=target_user_ids,
    )
    total_count = qs.count()

    sample_users = []
    for u in qs.order_by('id')[:6]:
        role = 'User'
        dept = ''
        inst_name = ''
        if hasattr(u, 'student_profile'):
            role = 'Student'
            dept = u.student_profile.department or ''
            inst_name = u.student_profile.institution.institution_name if u.student_profile.institution else ''
        elif hasattr(u, 'faculty_profile'):
            role = 'Faculty'
            dept = u.faculty_profile.department or ''
            inst_name = u.faculty_profile.institution.institution_name if u.faculty_profile.institution else ''
        elif hasattr(u, 'admin_profile'):
            role = 'Admin'
            inst_name = u.admin_profile.institution.institution_name if u.admin_profile.institution else ''

        sample_users.append({
            'id': u.id,
            'username': u.username,
            'email': u.email,
            'full_name': f'{u.first_name} {u.last_name}'.strip() or u.username,
            'role': role,
            'department': dept,
            'institute': inst_name,
        })

    return {
        'total_recipients': total_count,
        'sample_recipients': sample_users,
        'target_audience': target_audience,
        'email_enabled': False,
        'email_status_banner': 'Email dispatch is disabled (SMTP host unconfigured). In-app notifications will be delivered instantly to user bell indicators.',
    }


def dispatch_campaign_background(campaign_id: int):
    """
    Background worker that resolves users and delivers notifications in batches of 250.
    Creates both api.Notification (for bell integration) and CampaignDeliveryRecord (for tracking).
    """
    import sys
    is_testing = 'test' in sys.argv or getattr(settings, 'TESTING', False)
    if not is_testing:
        connection.close()
    logger.info('Starting background dispatch for campaign #%s', campaign_id)

    try:
        campaign = NotificationCampaign.objects.get(id=campaign_id)
        campaign.status = 'sending'
        campaign.save(update_fields=['status'])

        recipients_qs = get_recipients_queryset(
            target_audience=campaign.target_audience,
            target_role=campaign.target_role,
            target_institute_id=campaign.target_institute_id,
            target_department=campaign.target_department,
            target_user_ids=campaign.target_user_ids,
        )

        all_user_ids = list(recipients_qs.values_list('id', flat=True))
        campaign.recipients_count = len(all_user_ids)
        campaign.save(update_fields=['recipients_count'])

        batch_size = 250
        delivered_total = 0

        for i in range(0, len(all_user_ids), batch_size):
            chunk_ids = all_user_ids[i : i + batch_size]
            users_chunk = User.objects.filter(id__in=chunk_ids)

            with transaction.atomic():
                delivery_records = []
                for u in users_chunk:
                    inst = None
                    if hasattr(u, 'student_profile') and u.student_profile.institution:
                        inst = u.student_profile.institution
                    elif hasattr(u, 'faculty_profile') and u.faculty_profile.institution:
                        inst = u.faculty_profile.institution
                    elif hasattr(u, 'admin_profile') and u.admin_profile.institution:
                        inst = u.admin_profile.institution

                    notif = Notification.objects.create(
                        user=u,
                        institution=inst,
                        title=campaign.title,
                        message=campaign.message,
                        type=campaign.notification_type,
                        link=campaign.link or '',
                        is_read=False,
                    )
                    delivery_records.append(
                        CampaignDeliveryRecord(
                            campaign=campaign,
                            user=u,
                            notification=notif,
                            status='delivered',
                        )
                    )
                CampaignDeliveryRecord.objects.bulk_create(delivery_records)

            delivered_total += len(chunk_ids)
            NotificationCampaign.objects.filter(id=campaign_id).update(delivered_count=delivered_total)

        # Mark campaign completed
        campaign.refresh_from_db()
        campaign.status = 'completed'
        campaign.dispatched_at = timezone.now()
        campaign.save(update_fields=['status', 'dispatched_at', 'delivered_count'])

        record_notify_audit(
            actor_username=campaign.created_by,
            action='campaign.dispatched',
            target_entity='NotificationCampaign',
            target_id=str(campaign.id),
            description=f'Dispatched campaign "{campaign.title}" to {delivered_total} recipients',
            after_state={
                'campaign_id': campaign.id,
                'delivered_count': delivered_total,
                'status': 'completed',
            },
        )
        logger.info('Finished background dispatch for campaign #%s (delivered=%s)', campaign_id, delivered_total)

    except Exception as exc:
        logger.error('Failed to dispatch campaign #%s: %s', campaign_id, exc)
        NotificationCampaign.objects.filter(id=campaign_id).update(status='failed')
    finally:
        if not is_testing:
            connection.close()


def create_and_send_campaign(data: Dict[str, Any], actor_username: str) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """
    Validates input, creates campaign record, and dispatches immediately or schedules.
    """
    title = str(data.get('title', '')).strip()
    message = str(data.get('message', '')).strip()
    if not title or not message:
        return False, 'Title and message are required.', None

    notif_type = data.get('notification_type', 'info')
    if notif_type not in ('info', 'warning', 'success', 'error'):
        notif_type = 'info'

    target_audience = data.get('target_audience', 'all')
    target_role = str(data.get('target_role', '')).strip()
    target_institute_id = data.get('target_institute_id')
    target_department = str(data.get('target_department', '')).strip()
    target_user_ids = data.get('target_user_ids', [])
    link = str(data.get('link', '')).strip()

    scheduled_at_str = data.get('scheduled_at')
    scheduled_at = None
    if scheduled_at_str:
        try:
            scheduled_at = timezone.datetime.fromisoformat(scheduled_at_str)
            if timezone.is_naive(scheduled_at):
                scheduled_at = timezone.make_aware(scheduled_at)
        except Exception:
            return False, 'Invalid scheduled_at date format. Use ISO 8601.', None

    recipients_qs = get_recipients_queryset(
        target_audience=target_audience,
        target_role=target_role,
        target_institute_id=target_institute_id,
        target_department=target_department,
        target_user_ids=target_user_ids,
    )
    recipients_count = recipients_qs.count()
    if recipients_count == 0:
        return False, 'Selected target audience resolves to 0 recipients.', None

    # Determine status
    now = timezone.now()
    is_scheduled_future = scheduled_at and scheduled_at > now
    status_str = 'scheduled' if is_scheduled_future else 'sending'

    campaign = NotificationCampaign.objects.create(
        title=title,
        message=message,
        notification_type=notif_type,
        link=link,
        target_audience=target_audience,
        target_role=target_role,
        target_institute_id=target_institute_id,
        target_department=target_department,
        target_user_ids=target_user_ids,
        scheduled_at=scheduled_at if is_scheduled_future else None,
        status=status_str,
        recipients_count=recipients_count,
        channels=['in_app'],
        created_by=actor_username,
    )

    record_notify_audit(
        actor_username=actor_username,
        action='campaign.created',
        target_entity='NotificationCampaign',
        target_id=str(campaign.id),
        description=f'Created campaign "{title}" targeting {recipients_count} recipients (status={status_str})',
        after_state={'campaign_id': campaign.id, 'status': status_str, 'recipients': recipients_count},
    )

    if not is_scheduled_future:
        import sys
        if 'test' in sys.argv or getattr(settings, 'TESTING', False):
            dispatch_campaign_background(campaign.id)
        else:
            thread = threading.Thread(
                target=dispatch_campaign_background,
                args=(campaign.id,),
                daemon=True,
                name=f'campaign-dispatch-{campaign.id}',
            )
            thread.start()
        return True, f'Campaign created and dispatch started for {recipients_count} users.', {'id': campaign.id, 'status': 'sending'}

    return True, f'Campaign scheduled for {scheduled_at.strftime("%Y-%m-%d %H:%M UTC")}.', {'id': campaign.id, 'status': 'scheduled'}


def serialize_campaign_row(c: NotificationCampaign) -> Dict[str, Any]:
    """Serializes a campaign with delivery performance metrics."""
    read_count = c.delivery_records.filter(notification__is_read=True).count()
    read_percent = round((read_count / c.delivered_count) * 100, 1) if c.delivered_count > 0 else 0

    return {
        'id': c.id,
        'title': c.title,
        'message': c.message,
        'notification_type': c.notification_type,
        'link': c.link,
        'target_audience': c.target_audience,
        'target_role': c.target_role,
        'target_institute_name': c.target_institute.institution_name if c.target_institute else 'All Institutes',
        'target_department': c.target_department or 'All Departments',
        'status': c.status,
        'recipients_count': c.recipients_count,
        'delivered_count': c.delivered_count,
        'read_count': read_count,
        'read_percent': read_percent,
        'scheduled_at': c.scheduled_at.isoformat() if c.scheduled_at else None,
        'dispatched_at': c.dispatched_at.isoformat() if c.dispatched_at else None,
        'created_by': c.created_by,
        'created_at': c.created_at.isoformat(),
    }


def list_campaigns_paginated(
    page: int = 1,
    page_size: int = 10,
    search: str = '',
    status_filter: str = 'all',
) -> Dict[str, Any]:
    """Returns paginated campaigns and summary cards."""
    qs = NotificationCampaign.objects.all().select_related('target_institute').order_by('-created_at')

    if status_filter != 'all':
        qs = qs.filter(status=status_filter)

    if search:
        qs = qs.filter(Q(title__icontains=search) | Q(message__icontains=search) | Q(created_by__icontains=search))

    total_items = qs.count()
    total_pages = max(1, (total_items + page_size - 1) // page_size)
    offset = (page - 1) * page_size
    campaigns = qs[offset : offset + page_size]

    data = [serialize_campaign_row(c) for c in campaigns]

    # Global KPI counts
    total_broadcasts = NotificationCampaign.objects.count()
    total_notifications_sent = Notification.objects.count()
    total_scheduled = NotificationCampaign.objects.filter(status='scheduled').count()

    return {
        'campaigns': data,
        'pagination': {
            'page': page,
            'page_size': page_size,
            'total_items': total_items,
            'total_pages': total_pages,
        },
        'kpis': {
            'total_campaigns': total_broadcasts,
            'total_notifications_sent': total_notifications_sent,
            'scheduled_count': total_scheduled,
            'smtp_configured': False,
        },
    }


def cancel_scheduled_campaign(campaign_id: int, actor_username: str) -> Tuple[bool, str]:
    """Cancels a scheduled or draft campaign."""
    try:
        c = NotificationCampaign.objects.get(id=campaign_id)
    except NotificationCampaign.DoesNotExist:
        return False, 'Campaign not found.'

    if c.status not in ('scheduled', 'draft'):
        return False, f'Cannot cancel campaign in "{c.status}" status.'

    c.status = 'cancelled'
    c.save(update_fields=['status'])

    record_notify_audit(
        actor_username=actor_username,
        action='campaign.cancelled',
        target_entity='NotificationCampaign',
        target_id=str(c.id),
        description=f'Cancelled campaign "{c.title}"',
        after_state={'campaign_id': c.id, 'status': 'cancelled'},
    )
    return True, f'Campaign "{c.title}" cancelled successfully.'

import logging
from django.conf import settings
from superadmin.models import SuperAdminAuditLog

logger = logging.getLogger(__name__)


def get_client_ip(request) -> str:
    """Safely resolve client IP, respecting proxy configuration if present."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for and not getattr(settings, 'DEBUG', False):
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR', '')
    return ip or '127.0.0.1'


def log_super_admin_action(
    request,
    action: str,
    target_entity: str = '',
    target_id: str = '',
    description: str = '',
    before_state: dict | None = None,
    after_state: dict | None = None,
) -> SuperAdminAuditLog | None:
    """
    Log an event to the immutable SuperAdminAuditLog.
    """
    try:
        actor_username = 'anonymous'
        if request and hasattr(request, 'user') and request.user.is_authenticated:
            actor_username = request.user.username

        ip_address = get_client_ip(request) if request else '127.0.0.1'
        user_agent = request.META.get('HTTP_USER_AGENT', '')[:255] if request else 'CLI'

        log_entry = SuperAdminAuditLog.objects.create(
            actor_username=actor_username,
            action=action,
            target_entity=target_entity,
            target_id=str(target_id),
            description=description,
            before_state=before_state or {},
            after_state=after_state or {},
            ip_address=ip_address,
            user_agent=user_agent,
        )
        return log_entry
    except Exception as exc:
        logger.error('Failed to write SuperAdminAuditLog: %s', exc)
        return None

import hashlib
import hmac
import json
import logging
from django.conf import settings
from superadmin.models import SuperAdminAuditLog

logger = logging.getLogger(__name__)

GENESIS_HASH = '0' * 64


def compute_audit_hash(
    prev_hash: str,
    actor_username: str,
    action: str,
    target_entity: str,
    target_id: str,
    description: str,
    ip_address: str,
    before_state: dict,
    after_state: dict,
) -> str:
    """Compute HMAC-SHA256 signature for an audit log entry."""
    data = (
        f'{prev_hash}|{actor_username}|{action}|{target_entity}|{target_id}|'
        f'{description}|{ip_address}|'
        f'{json.dumps(before_state or {}, sort_keys=True)}|'
        f'{json.dumps(after_state or {}, sort_keys=True)}'
    )
    secret = getattr(settings, 'SECRET_KEY', 'examai-audit-key').encode('utf-8')
    return hmac.new(secret, data.encode('utf-8'), hashlib.sha256).hexdigest()


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
    Log an event to the immutable, cryptographically chained SuperAdminAuditLog.
    """
    try:
        actor_username = 'anonymous'
        if request and hasattr(request, 'user') and request.user.is_authenticated:
            actor_username = request.user.username

        ip_address = get_client_ip(request) if request else '127.0.0.1'
        user_agent = request.META.get('HTTP_USER_AGENT', '')[:255] if request else 'CLI'

        # Chaining: get latest entry's hash
        last_entry = SuperAdminAuditLog.objects.order_by('-id').first()
        prev_hash = last_entry.entry_hash if (last_entry and last_entry.entry_hash) else GENESIS_HASH

        entry_hash = compute_audit_hash(
            prev_hash=prev_hash,
            actor_username=actor_username,
            action=action,
            target_entity=target_entity,
            target_id=str(target_id),
            description=description,
            ip_address=ip_address,
            before_state=before_state or {},
            after_state=after_state or {},
        )

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
            prev_hash=prev_hash,
            entry_hash=entry_hash,
        )
        return log_entry
    except Exception as exc:
        logger.error('Failed to write SuperAdminAuditLog: %s', exc)
        return None


def verify_audit_log_integrity() -> tuple[bool, int | None]:
    """
    Validate the cryptographic hash chain of all SuperAdminAuditLog entries.
    Returns (True, None) if completely valid, or (False, corrupted_entry_id) if tampered.
    """
    entries = SuperAdminAuditLog.objects.order_by('id')
    expected_prev = GENESIS_HASH

    for entry in entries:
        # If entry predates hash chaining, initialize expected_prev if present
        if not entry.entry_hash:
            continue

        if entry.prev_hash != expected_prev:
            logger.error('Audit chain broken at entry %d: prev_hash mismatch', entry.id)
            return False, entry.id

        recalculated = compute_audit_hash(
            prev_hash=entry.prev_hash,
            actor_username=entry.actor_username,
            action=entry.action,
            target_entity=entry.target_entity,
            target_id=entry.target_id,
            description=entry.description,
            ip_address=entry.ip_address,
            before_state=entry.before_state,
            after_state=entry.after_state,
        )

        if not hmac.compare_digest(recalculated, entry.entry_hash):
            logger.error('Audit entry %d tampered: hash mismatch', entry.id)
            return False, entry.id

        expected_prev = entry.entry_hash

    return True, None


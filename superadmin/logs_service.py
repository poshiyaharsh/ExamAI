import os
import re
from collections import defaultdict
from datetime import datetime, timedelta
from django.conf import settings
from django.utils import timezone

from superadmin.models import SuperAdminAuditLog

LOGS_DIR = os.path.join(settings.BASE_DIR, 'logs')

# Sensitive regex patterns to mask
MASK_PATTERNS = [
    # Passwords in JSON, form data, or URL query
    (re.compile(r'("password"|"admin_password"|"old_password"|"new_password")\s*:\s*"[^"]+"', re.IGNORECASE), r'\1: "[MASKED_PASSWORD]"'),
    (re.compile(r'(password=)[^\s&]+', re.IGNORECASE), r'\1[MASKED_PASSWORD]'),
    # Bearer Tokens
    (re.compile(r'Bearer\s+[A-Za-z0-9\-_.]+', re.IGNORECASE), 'Bearer [MASKED_TOKEN]'),
    # JWT tokens
    (re.compile(r'eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}'), '[MASKED_JWT]'),
    # TOTP secrets / keys (Base32 format 16-32 chars)
    (re.compile(r'(totp_secret|secret)\s*:\s*"[A-Z2-7]{16,32}"', re.IGNORECASE), r'\1: "[MASKED_SECRET]"'),
    # Recovery codes
    (re.compile(r'\b[A-Za-z0-9]{4}-[A-Za-z0-9]{4}\b'), '[MASKED_CODE]'),
    # Secret slug if configured
    *(
        [(re.compile(re.escape(settings.SUPER_ADMIN_PATH)), '[SECRET_SLUG]')]
        if getattr(settings, 'SUPER_ADMIN_PATH', '')
        else []
    ),
]


def mask_sensitive_data(text: str) -> str:
    """Mask secrets, tokens, passwords, and sensitive keys from log entries."""
    if not text or not isinstance(text, str):
        return text
    masked = text
    for pattern, replacement in MASK_PATTERNS:
        masked = pattern.sub(replacement, masked)
    return masked


def get_system_logs(level: str = None, query: str = None, limit: int = 150) -> list[dict]:
    """
    Read latest system logs from logs/examai.log or logs/error.log.
    Applies secret masking, level filtering, and search keyword matching.
    """
    log_file = os.path.join(LOGS_DIR, 'examai.log')
    if level in ['ERROR', 'CRITICAL']:
        err_file = os.path.join(LOGS_DIR, 'error.log')
        if os.path.exists(err_file):
            log_file = err_file

    entries = []
    if os.path.exists(log_file):
        try:
            with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
            # Read from bottom (most recent)
            for line in reversed(lines):
                if not line.strip():
                    continue
                # Match standard format: [2026-10-20 22:30:00] [LEVEL] [logger] Message
                masked_line = mask_sensitive_data(line.strip())

                # Level filter
                if level and f'[{level.upper()}]' not in masked_line and not masked_line.startswith(level.upper()):
                    continue

                # Query filter
                if query and query.lower() not in masked_line.lower():
                    continue

                entries.append({
                    'raw': masked_line,
                    'timestamp': masked_line[:20] if masked_line.startswith('[20') else timezone.now().isoformat(),
                })

                if len(entries) >= limit:
                    break
        except Exception:
            pass

    return entries


def get_error_summary_grouped(days: int = 7) -> list[dict]:
    """
    Group recent errors by cause/exception type from error logs and audit logs.
    Returns: list of {cause: str, count: int, first_seen: str, last_seen: str, sample: str}
    """
    groups = defaultdict(lambda: {'count': 0, 'first_seen': None, 'last_seen': None, 'sample': ''})
    err_file = os.path.join(LOGS_DIR, 'error.log')

    if os.path.exists(err_file):
        try:
            with open(err_file, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()

            for line in lines:
                if not line.strip():
                    continue
                masked = mask_sensitive_data(line.strip())
                # Extract exception pattern if available e.g. "Exception: ...", "Error: ..."
                match = re.search(r'([A-Za-z0-9_]+(?:Error|Exception|Failed|Timeout)):?\s*(.*)', masked)
                if match:
                    cause = match.group(1)
                    detail = match.group(2)[:100]
                else:
                    cause = masked[:60]
                    detail = masked[:100]

                g = groups[cause]
                g['count'] += 1
                if not g['sample']:
                    g['sample'] = detail
                timestamp = masked[:19] if masked.startswith('[20') else timezone.now().strftime('%Y-%m-%d %H:%M:%S')
                if not g['first_seen']:
                    g['first_seen'] = timestamp
                g['last_seen'] = timestamp
        except Exception:
            pass

    # Include failed audit events as well
    failed_audits = SuperAdminAuditLog.objects.filter(
        action__icontains='failed',
        created_at__gte=timezone.now() - timedelta(days=days),
    )
    for a in failed_audits:
        cause = f'AuditFailed: {a.action}'
        g = groups[cause]
        g['count'] += 1
        g['sample'] = a.description[:100]
        ts = a.created_at.strftime('%Y-%m-%d %H:%M:%S')
        if not g['first_seen']:
            g['first_seen'] = ts
        g['last_seen'] = ts

    result = [
        {'cause': k, **v}
        for k, v in groups.items()
    ]
    result.sort(key=lambda x: x['count'], reverse=True)
    return result

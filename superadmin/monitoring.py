import logging
import os
import shutil
import time
from datetime import timedelta
import requests
from django.conf import settings
from django.core.mail import send_mail
from django.db import connection
from django.utils import timezone

from api.models import Exam, PaperGenerationJob, StudentAttempt
from superadmin.models import AlertNotificationRecord, DatabaseBackupRecord, SuperAdminAuditLog

logger = logging.getLogger(__name__)


def check_database_health() -> dict:
    """Check database connectivity and query latency."""
    t0 = time.time()
    try:
        connection.ensure_connection()
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1;')
            row = cursor.fetchone()
        latency_ms = round((time.time() - t0) * 1000, 2)
        if row and row[0] == 1:
            return {'status': 'healthy', 'latency_ms': latency_ms, 'message': f'Connected ({latency_ms} ms)'}
        return {'status': 'degraded', 'latency_ms': latency_ms, 'message': 'Unexpected query response'}
    except Exception as exc:
        logger.error('Database health check failed: %s', exc)
        return {'status': 'down', 'latency_ms': None, 'message': str(exc)}


def check_ollama_health() -> dict:
    """Check local Ollama AI engine connectivity, response latency, and installed models."""
    ollama_url = getattr(settings, 'OLLAMA_API_URL', 'http://127.0.0.1:11434')
    tags_url = f'{ollama_url.rstrip("/")}/api/tags'
    t0 = time.time()
    try:
        resp = requests.get(tags_url, timeout=3)
        latency_ms = round((time.time() - t0) * 1000, 2)
        if resp.status_code == 200:
            data = resp.json()
            models = [m.get('name') for m in data.get('models', []) if isinstance(m, dict)]
            return {
                'status': 'healthy',
                'latency_ms': latency_ms,
                'models': models,
                'model_count': len(models),
                'message': f'Reachable ({latency_ms} ms, {len(models)} model(s) loaded)',
            }
        return {'status': 'degraded', 'latency_ms': latency_ms, 'models': [], 'message': f'HTTP {resp.status_code}'}
    except Exception as exc:
        return {'status': 'down', 'latency_ms': None, 'models': [], 'message': f'Unreachable: {str(exc)}'}


def check_disk_space() -> dict:
    """Check disk partition capacity where project and backups reside."""
    try:
        total, used, free = shutil.disk_usage(settings.BASE_DIR)
        total_gb = round(total / (1024 ** 3), 2)
        used_gb = round(used / (1024 ** 3), 2)
        free_gb = round(free / (1024 ** 3), 2)
        percent_used = round((used / total) * 100, 1)

        status_label = 'healthy'
        if percent_used >= 90:
            status_label = 'critical'
        elif percent_used >= 80:
            status_label = 'warning'

        return {
            'status': status_label,
            'total_gb': total_gb,
            'used_gb': used_gb,
            'free_gb': free_gb,
            'percent_used': percent_used,
            'message': f'{percent_used}% used ({free_gb} GB free of {total_gb} GB)',
        }
    except Exception as exc:
        return {'status': 'unknown', 'message': str(exc)}


def check_background_jobs_health() -> dict:
    """Check background generation jobs, detecting stuck or failing jobs."""
    now = timezone.now()
    cutoff_15m = now - timedelta(minutes=15)
    cutoff_24h = now - timedelta(hours=24)

    stuck_jobs = PaperGenerationJob.objects.filter(
        status__in=['pending', 'processing'],
        created_at__lt=cutoff_15m,
    ).count()

    recent_failed_24h = PaperGenerationJob.objects.filter(
        status='failed',
        created_at__gte=cutoff_24h,
    ).count()

    active_jobs = PaperGenerationJob.objects.filter(status__in=['pending', 'processing']).count()

    status_label = 'healthy'
    if stuck_jobs > 0:
        status_label = 'warning'
    if stuck_jobs >= 5:
        status_label = 'critical'

    return {
        'status': status_label,
        'active_jobs': active_jobs,
        'stuck_jobs': stuck_jobs,
        'failed_24h': recent_failed_24h,
        'message': f'{active_jobs} active, {stuck_jobs} stuck (>15m), {recent_failed_24h} failed in 24h',
    }


def check_system_health() -> dict:
    """Aggregate health status across database, Ollama, disk space, and jobs."""
    db_health = check_database_health()
    ollama_health = check_ollama_health()
    disk_health = check_disk_space()
    jobs_health = check_background_jobs_health()

    latest_backup = DatabaseBackupRecord.objects.filter(status='completed').order_by('-created_at').first()
    backup_summary = {
        'last_backup_at': latest_backup.created_at.isoformat() if latest_backup else None,
        'last_backup_file': latest_backup.filename if latest_backup else None,
        'last_restore_test_status': latest_backup.restore_test_status if latest_backup else 'not_tested',
    }

    # Overall system status
    overall = 'healthy'
    if db_health['status'] == 'down':
        overall = 'critical'
    elif disk_health.get('status') == 'critical' or ollama_health['status'] == 'down':
        overall = 'degraded'
    elif jobs_health['status'] in ['warning', 'critical'] or disk_health.get('status') == 'warning':
        overall = 'warning'

    return {
        'overall_status': overall,
        'timestamp': timezone.now().isoformat(),
        'database': db_health,
        'ollama': ollama_health,
        'disk': disk_health,
        'jobs': jobs_health,
        'backup': backup_summary,
    }


def send_deduplicated_alert(
    alert_key: str,
    subject: str,
    message: str,
    severity: str = 'warning',
    cooldown_minutes: int = 60,
) -> bool:
    """
    Send an email alert to the configured super admin owner with strict deduplication.
    Prevents alert storms (e.g., 100 emails when Ollama goes down or disk fills up).
    Returns True if an email was sent, False if suppressed due to cooldown.
    """
    now = timezone.now()
    cooldown_delta = timedelta(minutes=cooldown_minutes)

    rec, created = AlertNotificationRecord.objects.get_or_create(
        alert_key=alert_key,
        defaults={
            'severity': severity,
            'subject': subject,
            'message': message,
            'sent_count': 1,
        },
    )

    if not created:
        if now - rec.last_sent_at < cooldown_delta:
            rec.sent_count += 1
            rec.save(update_fields=['sent_count'])
            logger.info('Alert [%s] suppressed (cooldown active, count=%d)', alert_key, rec.sent_count)
            return False

        # Cooldown expired: re-send alert
        rec.sent_count += 1
        rec.subject = subject
        rec.message = message
        rec.severity = severity
        rec.save(update_fields=['sent_count', 'subject', 'message', 'severity', 'last_sent_at'])

    # Deliver alert email
    to_email = getattr(settings, 'SUPER_ADMIN_ALERT_EMAIL', None) or 'harshposhiya92@gmail.com'
    formatted_subject = f'[ExamAI SuperAdmin ALERT] [{severity.upper()}] {subject}'
    formatted_body = (
        f'ExamAI System Operational Alert\n'
        f'Severity: {severity.upper()}\n'
        f'Key: {alert_key}\n'
        f'Triggered At: {now.isoformat()}\n\n'
        f'{message}\n\n'
        f'--\n'
        f'This notification was generated automatically by ExamAI Super Admin Monitoring.\n'
        f'Repeated occurrences of this alert are throttled with a {cooldown_minutes}-minute cooldown.'
    )

    try:
        send_mail(
            subject=formatted_subject,
            message=formatted_body,
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'security@examai.local'),
            recipient_list=[to_email],
            fail_silently=False,
        )
        logger.info('Dispatched deduplicated alert [%s] to %s', alert_key, to_email)
        return True
    except Exception as exc:
        logger.error('Failed to send alert email [%s]: %s', alert_key, exc)
        return False

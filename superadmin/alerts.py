import logging
from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)


def send_super_admin_security_alert(subject: str, message: str) -> bool:
    """
    Send high-priority security notifications to the Super Admin alert email.
    Logs gracefully if email delivery fails.
    """
    recipient = getattr(settings, 'SUPER_ADMIN_ALERT_EMAIL', 'harshposhiya92@gmail.com')
    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@examai.local')

    full_subject = f'[ExamAI SECURITY ALERT] {subject}'
    full_message = (
        f'{message}\n\n'
        f'--------------------------------------------------\n'
        f'System: ExamAI Super Admin Security Service\n'
        f'Recipient: {recipient}\n'
    )

    try:
        send_mail(
            subject=full_subject,
            message=full_message,
            from_email=from_email,
            recipient_list=[recipient],
            fail_silently=False,
        )
        logger.info('Super Admin security alert email dispatched: %s', subject)
        return True
    except Exception as exc:
        logger.error('Failed to send Super Admin security alert email: %s', exc)
        return False

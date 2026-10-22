import sys
from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.utils import timezone


class Command(BaseCommand):
    help = 'Sends a diagnostic test email to verify SMTP configuration or console fallback.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--to',
            dest='recipient',
            required=True,
            help='Recipient email address to send the diagnostic email to.',
        )

    def handle(self, *args, **options):
        recipient = options['recipient'].strip()
        try:
            validate_email(recipient)
        except ValidationError:
            self.stderr.write(self.style.ERROR(f'Invalid email address: "{recipient}"'))
            sys.exit(1)

        backend = getattr(settings, 'EMAIL_BACKEND', '')
        host = getattr(settings, 'EMAIL_HOST', '') or '(none - console)'
        port = getattr(settings, 'EMAIL_PORT', 587)
        user = getattr(settings, 'EMAIL_HOST_USER', '') or '(none)'
        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@examai.local')
        use_tls = getattr(settings, 'EMAIL_USE_TLS', True)
        use_ssl = getattr(settings, 'EMAIL_USE_SSL', False)

        self.stdout.write(self.style.NOTICE('=== ExamAI Email Diagnostic Test ==='))
        self.stdout.write(f'Backend:    {backend}')
        self.stdout.write(f'Host:       {host}:{port}')
        self.stdout.write(f'User:       {user}')
        self.stdout.write(f'From:       {from_email}')
        self.stdout.write(f'TLS / SSL:  TLS={use_tls}, SSL={use_ssl}')
        self.stdout.write(f'Recipient:  {recipient}')
        self.stdout.write('----------------------------------------')

        subject = f'[ExamAI] Diagnostic Test Email - {timezone.now().strftime("%Y-%m-%d %H:%M:%S UTC")}'
        message = (
            f"Hello,\n\n"
            f"This is an automated diagnostic test from ExamAI Super Admin Console.\n"
            f"If you received this message, outbound email delivery is working successfully.\n\n"
            f"Configuration Details:\n"
            f"- Host: {host}:{port}\n"
            f"- From: {from_email}\n"
            f"- Dispatched at: {timezone.now().isoformat()}\n\n"
            f"Regards,\n"
            f"ExamAI Platform Administration"
        )

        try:
            self.stdout.write('Attempting delivery...')
            sent_count = send_mail(
                subject=subject,
                message=message,
                from_email=from_email,
                recipient_list=[recipient],
                fail_silently=False,
            )
            if sent_count > 0:
                self.stdout.write(self.style.SUCCESS(f'SUCCESS: Test email successfully dispatched to {recipient}.'))
                if 'console' in backend.lower():
                    self.stdout.write(self.style.WARNING('NOTE: Using console backend; output was printed to console above.'))
            else:
                self.stdout.write(self.style.WARNING(f'DISPATCH RETURNED 0: No email was dispatched.'))
        except Exception as exc:
            self.stderr.write(self.style.ERROR(f'FAILED: Email dispatch failed with error: {exc}'))
            self.stderr.write(self.style.NOTICE(
                '\nTroubleshooting Tips:\n'
                '1. If using Gmail: verify 2-Step Verification is ON and use an App Password (16 characters).\n'
                '2. If using Brevo: verify sender email in Brevo Senders list and use the SMTP key (not API key).\n'
                '3. Check firewall / outbound port 587 blocking on your network.\n'
                '4. Refer to docs/email-setup.md for full configuration details.'
            ))
            sys.exit(1)

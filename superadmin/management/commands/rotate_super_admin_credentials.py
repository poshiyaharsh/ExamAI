import getpass
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from superadmin.models import SuperAdminAuditLog, SuperAdminProfile
from superadmin.totp import generate_recovery_codes, generate_totp_secret

User = get_user_model()


class Command(BaseCommand):
    help = 'Rotate Super Admin credentials (password and/or 2FA secret and recovery codes).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--username',
            type=str,
            default='harshposhiya',
            help='Super Admin username (default: harshposhiya)',
        )
        parser.add_argument(
            '--reset-password',
            action='store_true',
            help='Rotate Super Admin password securely via hidden prompt.',
        )
        parser.add_argument(
            '--reset-2fa',
            action='store_true',
            help='Reset TOTP 2FA secret and regenerate recovery codes.',
        )

    def handle(self, *args, **options):
        username = options['username'].strip()
        do_reset_pwd = options['reset_password']
        do_reset_2fa = options['reset_2fa']

        if not do_reset_pwd and not do_reset_2fa:
            raise CommandError('Specify at least one rotation action: --reset-password and/or --reset-2fa.')

        profile = SuperAdminProfile.objects.filter(user__username=username).select_related('user').first()
        if not profile:
            raise CommandError(f'Super Admin account with username "{username}" does not exist.')

        user = profile.user
        new_password = None

        if do_reset_pwd:
            self.stdout.write(self.style.NOTICE(f'\nRotating password for Super Admin: {username}'))
            while True:
                new_password = getpass.getpass('Enter New Super Admin Password (hidden): ')
                if not new_password:
                    self.stdout.write(self.style.ERROR('Password cannot be empty.'))
                    continue

                new_password_confirm = getpass.getpass('Confirm New Super Admin Password (hidden): ')
                if new_password != new_password_confirm:
                    self.stdout.write(self.style.ERROR('Passwords do not match. Try again.\n'))
                    continue

                try:
                    validate_password(new_password, user=user)
                    break
                except ValidationError as err:
                    self.stdout.write(self.style.ERROR(f'Password validation failed: {"; ".join(err.messages)}\n'))
                    continue

        plain_recovery_codes = []
        with transaction.atomic():
            audit_actions = []
            if do_reset_pwd and new_password:
                user.set_password(new_password)
                user.save(update_fields=['password'])
                audit_actions.append('password_rotated')

            if do_reset_2fa:
                new_totp_secret = generate_totp_secret()
                plain_recovery_codes, hashed_recovery_codes = generate_recovery_codes(count=8)
                profile.totp_secret = new_totp_secret
                profile.is_totp_enrolled = False
                profile.recovery_codes_hash = hashed_recovery_codes
                audit_actions.append('totp_2fa_reset')

            # Reset lockout flags if any
            profile.failed_login_attempts = 0
            profile.locked_until = None
            profile.save()

            SuperAdminAuditLog.objects.create(
                actor_username=username,
                action=','.join(audit_actions),
                target_entity='SuperAdminProfile',
                target_id=str(profile.id),
                description=f'Super Admin credentials rotated ({", ".join(audit_actions)}) via CLI.',
                before_state={},
                after_state={'actions': audit_actions, 'totp_enrolled': False if do_reset_2fa else profile.is_totp_enrolled},
                ip_address='127.0.0.1 (CLI)',
                user_agent='manage.py rotate_super_admin_credentials',
            )

        self.stdout.write(self.style.SUCCESS('\n✓ Super Admin credentials rotated successfully!'))
        if do_reset_2fa:
            self.stdout.write(self.style.WARNING('\n-----------------------------------------------------------------'))
            self.stdout.write(self.style.WARNING('  NEW ONE-TIME RECOVERY CODES'))
            self.stdout.write(self.style.WARNING('  Save these recovery codes offline. Previous codes are invalid.'))
            self.stdout.write(self.style.WARNING('-----------------------------------------------------------------'))
            for code in plain_recovery_codes:
                self.stdout.write(self.style.MIGRATE_HEADING(f'    {code}'))
            self.stdout.write(self.style.NOTICE(
                '\nNext Steps: Re-enroll in your authenticator app upon next login.'
            ))

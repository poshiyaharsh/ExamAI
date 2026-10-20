import getpass
import sys
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from superadmin.models import SuperAdminAuditLog, SuperAdminProfile
from superadmin.totp import generate_recovery_codes, generate_totp_secret

User = get_user_model()


class Command(BaseCommand):
    help = 'Create the designated platform Super Admin owner account.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--username',
            type=str,
            default='harshposhiya',
            help='Super Admin username (default: harshposhiya)',
        )
        parser.add_argument(
            '--email',
            type=str,
            default='harshposhiya92@gmail.com',
            help='Super Admin email address (default: harshposhiya92@gmail.com)',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force overwrite/re-creation of existing Super Admin account.',
        )

    def handle(self, *args, **options):
        username = options['username'].strip()
        email = options['email'].strip().lower()
        force = options['force']

        self.stdout.write(self.style.SUCCESS('\n================================================================='))
        self.stdout.write(self.style.SUCCESS('  EXAMAI SUPER ADMIN - OWNER ACCOUNT CREATION'))
        self.stdout.write(self.style.SUCCESS('=================================================================\n'))

        # Check existing super admin
        existing_profile = SuperAdminProfile.objects.select_related('user').first()
        if existing_profile and not force:
            raise CommandError(
                f'A Super Admin account already exists (username: "{existing_profile.user.username}").\n'
                f'System security policy enforces at most one Super Admin.\n'
                f'To replace or update this account, re-run with --force.'
            )

        if existing_profile and force:
            self.stdout.write(self.style.WARNING(
                f'WARNING: Existing Super Admin account "{existing_profile.user.username}" will be overwritten.\n'
            ))
            if sys.stdin.isatty():
                confirmation = input('Type "CONFIRM" to proceed with replacement: ')
                if confirmation != 'CONFIRM':
                    self.stdout.write(self.style.ERROR('Operation aborted by user.'))
                    return

        # Check if user already exists under different role
        existing_user = User.objects.filter(username=username).first()
        if existing_user and not hasattr(existing_user, 'super_admin_profile') and not force:
            raise CommandError(
                f'A standard user account with username "{username}" already exists.\n'
                f'Use a different username or run with --force.'
            )

        # Prompt for password securely via getpass (hidden input)
        while True:
            password = getpass.getpass('Enter Super Admin Password (hidden): ')
            if not password:
                self.stdout.write(self.style.ERROR('Password cannot be empty.'))
                continue

            password_confirm = getpass.getpass('Confirm Super Admin Password (hidden): ')
            if password != password_confirm:
                self.stdout.write(self.style.ERROR('Passwords do not match. Please try again.\n'))
                continue

            # Validate against configured Django password validators
            temp_user = User(username=username, email=email)
            try:
                validate_password(password, user=temp_user)
                break
            except ValidationError as err:
                self.stdout.write(self.style.ERROR(f'Password validation failed: {"; ".join(err.messages)}\n'))
                continue

        with transaction.atomic():
            # Create or update User
            if existing_user:
                user = existing_user
                user.email = email
                user.set_password(password)
                user.is_staff = False  # Keep standard Django admin flags decoupled
                user.is_superuser = False
                user.save()
            else:
                user = User.objects.create_user(
                    username=username,
                    email=email,
                    password=password,
                    is_staff=False,
                    is_superuser=False,
                )

            # Generate TOTP secret and recovery codes
            totp_secret = generate_totp_secret()
            plain_recovery_codes, hashed_recovery_codes = generate_recovery_codes(count=8)

            profile, created = SuperAdminProfile.objects.get_or_create(
                user=user,
                defaults={
                    'totp_secret': totp_secret,
                    'is_totp_enrolled': False,
                    'recovery_codes_hash': hashed_recovery_codes,
                    'failed_login_attempts': 0,
                    'locked_until': None,
                },
            )

            if not created:
                profile.totp_secret = totp_secret
                profile.is_totp_enrolled = False
                profile.recovery_codes_hash = hashed_recovery_codes
                profile.failed_login_attempts = 0
                profile.locked_until = None
                profile.save()

            # Record in immutable SuperAdminAuditLog
            SuperAdminAuditLog.objects.create(
                actor_username=username,
                action='super_admin_account_created' if created else 'super_admin_account_recreated',
                target_entity='SuperAdminProfile',
                target_id=str(profile.id),
                description=f'Super Admin account created for {username} ({email}) via CLI.',
                before_state={},
                after_state={'username': username, 'email': email, 'totp_enrolled': False},
                ip_address='127.0.0.1 (CLI)',
                user_agent='manage.py create_super_admin',
            )

        self.stdout.write(self.style.SUCCESS('\n✓ Super Admin account successfully created!'))
        self.stdout.write(f'  Username : {username}')
        self.stdout.write(f'  Email    : {email}')
        self.stdout.write(self.style.WARNING('\n-----------------------------------------------------------------'))
        self.stdout.write(self.style.WARNING('  IMPORTANT: ONE-TIME RECOVERY CODES'))
        self.stdout.write(self.style.WARNING('  Save these recovery codes offline in a secure password manager.'))
        self.stdout.write(self.style.WARNING('  They will NOT be shown again.'))
        self.stdout.write(self.style.WARNING('-----------------------------------------------------------------'))
        for code in plain_recovery_codes:
            self.stdout.write(self.style.MIGRATE_HEADING(f'    {code}'))
        self.stdout.write(self.style.NOTICE(
            '\nNext Steps:\n'
            '1. On your first login to the Super Admin portal, 2FA setup is required.\n'
            '2. Scan the QR code or enter your secret key in your authenticator app.\n'
        ))

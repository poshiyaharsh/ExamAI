import time
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.utils import timezone

from superadmin.models import SuperAdminAuditLog, SuperAdminProfile
from superadmin.totp import (
    generate_recovery_codes,
    generate_totp_secret,
    get_totp_code,
    verify_and_consume_recovery_code,
    verify_totp,
)

User = get_user_model()


class SuperAdminSecurityTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='harshposhiya',
            email='harshposhiya92@gmail.com',
            password='TestSecurePassword123!',
        )
        self.secret = generate_totp_secret()
        self.profile = SuperAdminProfile.objects.create(
            user=self.user,
            totp_secret=self.secret,
            is_totp_enrolled=True,
        )

    def test_totp_generation_and_verification(self):
        """Test TOTP generates valid code and verifies accurately within time window."""
        current_step = int(time.time() // 30)
        valid_code = get_totp_code(self.secret, current_step)

        self.assertEqual(len(valid_code), 6)
        self.assertTrue(verify_totp(self.secret, valid_code, window=1))

        # Rejection of invalid code
        self.assertFalse(verify_totp(self.secret, '000000', window=1))
        self.assertFalse(verify_totp(self.secret, 'invalid', window=1))

        # Rejection of expired code (5 minutes in past)
        expired_code = get_totp_code(self.secret, current_step - 10)
        self.assertFalse(verify_totp(self.secret, expired_code, window=1))

    def test_recovery_codes_generation_and_single_use(self):
        """Test recovery codes generation, validation, and single-use consumption."""
        plain_codes, hashed_codes = generate_recovery_codes(count=8)
        self.assertEqual(len(plain_codes), 8)
        self.assertEqual(len(hashed_codes), 8)

        first_code = plain_codes[0]

        # Valid consumption
        success, remaining_hashes = verify_and_consume_recovery_code(first_code, hashed_codes)
        self.assertTrue(success)
        self.assertEqual(len(remaining_hashes), 7)

        # Single-use enforcement: re-using the same code must fail
        success2, remaining_hashes2 = verify_and_consume_recovery_code(first_code, remaining_hashes)
        self.assertFalse(success2)
        self.assertEqual(len(remaining_hashes2), 7)

        # Invalid recovery code rejection
        bad_success, _ = verify_and_consume_recovery_code('XXXX-YYYY', remaining_hashes)
        self.assertFalse(bad_success)

    def test_super_admin_hard_limit_constraint(self):
        """Ensure system rejects creating more than the configured maximum Super Admin accounts."""
        second_user = User.objects.create_user(
            username='attacker_sa',
            email='attacker@example.com',
            password='AttackPassword123!',
        )
        second_profile = SuperAdminProfile(user=second_user)
        with self.assertRaises(ValidationError):
            second_profile.save()

    def test_audit_log_immutability(self):
        """Ensure SuperAdminAuditLog records can never be updated or deleted."""
        log = SuperAdminAuditLog.objects.create(
            actor_username='harshposhiya',
            action='test_action',
            description='Test audit entry',
            ip_address='127.0.0.1',
        )
        self.assertIsNotNone(log.id)

        # Block update
        log.description = 'Tampered description'
        with self.assertRaises(PermissionDenied):
            log.save()

        # Block delete
        with self.assertRaises(PermissionDenied):
            log.delete()

    def test_lockout_and_reauth_helpers(self):
        """Test lockout expiry and re-authentication window evaluation."""
        self.assertFalse(self.profile.is_locked())
        self.assertFalse(self.profile.is_reauth_valid())

        # Test locked
        self.profile.locked_until = timezone.now() + timedelta(minutes=15)
        self.profile.save()
        self.assertTrue(self.profile.is_locked())

        # Test lockout expired
        self.profile.locked_until = timezone.now() - timedelta(seconds=1)
        self.profile.save()
        self.assertFalse(self.profile.is_locked())

        # Test re-authentication validity
        self.profile.last_reauth_at = timezone.now()
        self.profile.save()
        self.assertTrue(self.profile.is_reauth_valid(max_age_seconds=300))

        # Re-auth expired (after 10 minutes)
        self.profile.last_reauth_at = timezone.now() - timedelta(minutes=10)
        self.profile.save()
        self.assertFalse(self.profile.is_reauth_valid(max_age_seconds=300))

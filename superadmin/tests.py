import json
import time
from datetime import timedelta
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from admins.models import AdminInstitution
from api.models import Exam
from superadmin.authentication import generate_super_admin_token
from superadmin.models import SuperAdminAuditLog, SuperAdminProfile, SystemSetting
from superadmin.totp import (
    generate_recovery_codes,
    generate_totp_secret,
    get_totp_code,
    verify_and_consume_recovery_code,
    verify_totp,
)

User = get_user_model()


class SuperAdminSecurityUnitTests(TestCase):
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


class SuperAdminApiIntegrationTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.slug = getattr(settings, 'SUPER_ADMIN_PATH', 'test_secret_slug_12345')
        self.user = User.objects.create_user(
            username='harshposhiya',
            email='harshposhiya92@gmail.com',
            password='StrongPassword@2026!',
        )
        self.secret = generate_totp_secret()
        self.plain_codes, self.hashed_codes = generate_recovery_codes(count=8)
        self.profile = SuperAdminProfile.objects.create(
            user=self.user,
            totp_secret=self.secret,
            is_totp_enrolled=True,
            recovery_codes_hash=self.hashed_codes,
        )
        self.token = generate_super_admin_token(self.user)

    def test_uniform_404_on_unauthenticated_or_invalid_probes(self):
        """Unauthenticated or unauthorized access to protected superadmin APIs returns 404."""
        # Missing auth header to protected endpoint
        res = self.client.get(f'/{self.slug}/api/dashboard/')
        self.assertEqual(res.status_code, 404)

        # Non-superadmin probe (e.g. invalid token)
        res = self.client.get(f'/{self.slug}/api/dashboard/', HTTP_AUTHORIZATION='Bearer invalid_token_here')
        self.assertEqual(res.status_code, 404)

        # Probing default disabled /admin/
        res = self.client.get('/admin/')
        self.assertEqual(res.status_code, 404)

    def test_login_flow_invalid_credentials_and_lockout(self):
        """Test failed login rate limiting and 15-minute progressive lockout."""
        url = f'/{self.slug}/api/auth/login/'

        for attempt in range(1, 5):
            res = self.client.post(url, data={'username': 'harshposhiya', 'password': 'WrongPassword!'}, content_type='application/json')
            self.assertEqual(res.status_code, 401)
            self.assertEqual(res.json()['status'], 'error')

        # 5th attempt triggers lockout
        res5 = self.client.post(url, data={'username': 'harshposhiya', 'password': 'WrongPassword!'}, content_type='application/json')
        self.assertEqual(res5.status_code, 401)

        # 6th attempt is blocked with 423 Locked
        res6 = self.client.post(url, data={'username': 'harshposhiya', 'password': 'StrongPassword@2026!'}, content_type='application/json')
        self.assertEqual(res6.status_code, 423)
        self.assertEqual(res6.json()['status'], 'locked')

    def test_login_flow_success_with_totp(self):
        """Test successful login using password and valid TOTP code."""
        url = f'/{self.slug}/api/auth/login/'
        current_step = int(time.time() // 30)
        totp_code = get_totp_code(self.secret, current_step)

        res = self.client.post(
            url,
            data={
                'username': 'harshposhiya',
                'password': 'StrongPassword@2026!',
                'totp_code': totp_code,
            },
            content_type='application/json',
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data['status'], 'success')
        self.assertIn('token', data)

        # Verify audit log was recorded
        self.assertTrue(SuperAdminAuditLog.objects.filter(action='super_admin_login_success').exists())

    def test_login_flow_success_with_recovery_code(self):
        """Test successful login using a one-time recovery code and verifying consumption."""
        url = f'/{self.slug}/api/auth/login/'
        recovery_code = self.plain_codes[0]

        res = self.client.post(
            url,
            data={
                'username': 'harshposhiya',
                'password': 'StrongPassword@2026!',
                'recovery_code': recovery_code,
            },
            content_type='application/json',
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['status'], 'success')

        # Single-use check: profile should now have 7 remaining codes
        self.profile.refresh_from_db()
        self.assertEqual(len(self.profile.recovery_codes_hash), 7)

    def test_dashboard_endpoint_metrics(self):
        """Test dashboard returns aggregated counts, health indicators, and audits."""
        url = f'/{self.slug}/api/dashboard/'
        res = self.client.get(url, HTTP_AUTHORIZATION=f'Bearer {self.token}')
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data['status'], 'success')
        self.assertIn('totals', data)
        self.assertIn('health', data)
        self.assertIn('database', data['health'])
        self.assertEqual(data['health']['database']['status'], 'healthy')

    def test_dangerous_action_reauth_enforcement(self):
        """Ensure high-risk actions (e.g. force-closing exam) require recent step-up re-auth."""
        # Create an institution and live exam
        inst_user = User.objects.create_user(username='inst_admin', email='inst@example.com', password='Pass@12345678!')
        inst = AdminInstitution.objects.create(admin=inst_user, institution_name='Test College', institution_code='INST-2026-999')
        exam = Exam.objects.create(
            institution=inst,
            created_by=inst_user,
            title='Live Test Exam',
            duration_minutes=60,
            status=Exam.Status.PUBLISHED,
        )

        force_close_url = f'/{self.slug}/api/exams/{exam.id}/force-close/'

        # Without recent re-auth: must be rejected with reauth_required
        self.profile.last_reauth_at = None
        self.profile.save()

        res_blocked = self.client.post(
            force_close_url,
            data={'reason': 'Emergency protocol violation'},
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Bearer {self.token}',
        )
        self.assertEqual(res_blocked.status_code, 403)
        self.assertIn('reauth_required', str(res_blocked.content))

        # Perform step-up re-authentication
        reauth_url = f'/{self.slug}/api/auth/reauth/'
        current_step = int(time.time() // 30)
        totp_code = get_totp_code(self.secret, current_step)

        res_reauth = self.client.post(
            reauth_url,
            data={'password': 'StrongPassword@2026!', 'totp_code': totp_code},
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Bearer {self.token}',
        )
        self.assertEqual(res_reauth.status_code, 200)

        # Now force-close should succeed
        res_allowed = self.client.post(
            force_close_url,
            data={'reason': 'Emergency protocol violation'},
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Bearer {self.token}',
        )
        self.assertEqual(res_allowed.status_code, 200)
        exam.refresh_from_db()
        self.assertEqual(exam.status, Exam.Status.CLOSED)

    def test_maintenance_mode_middleware(self):
        """When maintenance mode is enabled, regular APIs return 503 while Super Admin passes."""
        SystemSetting.set_setting('maintenance_mode', {'enabled': True, 'message': 'Upgrading servers'})

        # Regular API receives 503
        reg_res = self.client.get('/api/departments/')
        self.assertEqual(reg_res.status_code, 503)
        self.assertEqual(reg_res.json()['status'], 'maintenance')

        # Super Admin API under secret prefix still responds normally (200)
        sa_res = self.client.get(f'/{self.slug}/api/dashboard/', HTTP_AUTHORIZATION=f'Bearer {self.token}')
        self.assertEqual(sa_res.status_code, 200)

        # Disable maintenance mode
        SystemSetting.set_setting('maintenance_mode', {'enabled': False})
        reg_res_restored = self.client.get('/api/departments/')
        self.assertEqual(reg_res_restored.status_code, 200)

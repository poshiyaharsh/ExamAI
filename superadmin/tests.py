import json
import time
from datetime import timedelta
from io import StringIO
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import Client, TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from admins.models import AdminInstitution, AdminProfile
from api.models import Exam, Notification, PaperGenerationJob
from faculty.models import FacultyProfile
from students.models import StudentProfile
from superadmin.authentication import generate_super_admin_token
from superadmin.backups import compute_file_sha256, prune_backups
from superadmin.jobs_service import detect_and_cleanup_stuck_jobs, get_jobs_summary
from superadmin.logs_service import mask_sensitive_data
from superadmin.models import (
    AIModel,
    AlertNotificationRecord,
    CampaignDeliveryRecord,
    DatabaseBackupRecord,
    MaintenanceWindow,
    NotificationCampaign,
    SuperAdminAuditLog,
    SuperAdminProfile,
    SystemSetting,
)
from superadmin.monitoring import check_system_health, send_deduplicated_alert
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
        valid, step = verify_totp(self.secret, valid_code, window=1)
        self.assertTrue(valid)
        self.assertEqual(step, current_step)

        # Rejection of replay with same or older step
        replayed, _ = verify_totp(self.secret, valid_code, window=1, last_used_step=step)
        self.assertFalse(replayed)

        # Rejection of invalid code
        self.assertFalse(verify_totp(self.secret, '000000', window=1)[0])
        self.assertFalse(verify_totp(self.secret, 'invalid', window=1)[0])

        # Rejection of expired code (5 minutes in past)
        expired_code = get_totp_code(self.secret, current_step - 10)
        self.assertFalse(verify_totp(self.secret, expired_code, window=1)[0])

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
        self.session_id = 'test_session_id_123'
        self.profile.active_session_id = self.session_id
        self.profile.last_activity_at = timezone.now()
        self.profile.save()
        self.token = generate_super_admin_token(self.user, session_id=self.session_id)

    def test_totp_replay_protection_enforced(self):
        """Ensure a TOTP code cannot be replayed within the same time window."""
        url = f'/{self.slug}/api/auth/login/'
        current_step = int(time.time() // 30)
        totp_code = get_totp_code(self.secret, current_step)

        # 1st attempt with code succeeds
        res1 = self.client.post(
            url,
            data={'username': 'harshposhiya', 'password': 'StrongPassword@2026!', 'totp_code': totp_code},
            content_type='application/json',
        )
        self.assertEqual(res1.status_code, 200)

        # 2nd attempt with exact same code within same window MUST be rejected (replay attack)
        res2 = self.client.post(
            url,
            data={'username': 'harshposhiya', 'password': 'StrongPassword@2026!', 'totp_code': totp_code},
            content_type='application/json',
        )
        self.assertEqual(res2.status_code, 401)
        self.assertIn('already used', res2.json().get('message', ''))

    def test_audit_log_cryptographic_hash_chain_and_tampering_detection(self):
        """Test HMAC hash chaining and verify that manual tampering is detected."""
        from superadmin.audit import log_super_admin_action, verify_audit_log_integrity

        # Create two chained audit entries
        entry1 = log_super_admin_action(None, action='event_1', description='First event')
        entry2 = log_super_admin_action(None, action='event_2', description='Second event')

        self.assertIsNotNone(entry1)
        self.assertIsNotNone(entry2)
        self.assertEqual(entry2.prev_hash, entry1.entry_hash)

        # Whole chain verification passes
        is_valid, corrupted_id = verify_audit_log_integrity()
        self.assertTrue(is_valid)
        self.assertIsNone(corrupted_id)

        # Simulate direct DB tampering (bypassing model save)
        SuperAdminAuditLog.objects.filter(id=entry1.id).update(description='Attacker modified this directly in SQL')
        is_valid_after_tamper, corrupted_id_after_tamper = verify_audit_log_integrity()
        self.assertFalse(is_valid_after_tamper)
        self.assertEqual(corrupted_id_after_tamper, entry1.id)

    def test_token_revocation_on_logout(self):
        """Ensure that logging out invalidates the active session and revokes the JWT token."""
        dashboard_url = f'/{self.slug}/api/dashboard/'
        logout_url = f'/{self.slug}/api/auth/logout/'

        # Valid before logout
        res_before = self.client.get(dashboard_url, HTTP_AUTHORIZATION=f'Bearer {self.token}')
        self.assertEqual(res_before.status_code, 200)

        # Perform logout
        res_logout = self.client.post(logout_url, HTTP_AUTHORIZATION=f'Bearer {self.token}')
        self.assertEqual(res_logout.status_code, 200)

        # Token must now be rejected
        res_after = self.client.get(dashboard_url, HTTP_AUTHORIZATION=f'Bearer {self.token}')
        self.assertEqual(res_after.status_code, 403)
        self.assertIn('ended or been revoked', str(res_after.content))

    def test_super_admin_blocked_from_public_forgot_password(self):
        """Ensure public forgot-password API cannot initiate reset for super admin accounts."""
        from api.models import PasswordResetOTP

        res = self.client.post(
            '/api/auth/forgot-password/',
            data={'email': 'harshposhiya92@gmail.com'},
            content_type='application/json',
        )
        self.assertEqual(res.status_code, 200)
        # Verify no OTP was created for the super admin
        self.assertFalse(PasswordResetOTP.objects.filter(user=self.user).exists())
        self.assertNotIn('debug_otp', res.json())

    def test_institute_creation_requires_reauth(self):
        """Ensure POST /institutes/ enforces step-up re-authentication."""
        url = f'/{self.slug}/api/institutes/'
        payload = {
            'institution_name': 'New Testing Institute',
            'admin_email': 'test_admin_new@example.com',
            'admin_first_name': 'Admin',
            'admin_last_name': 'User',
            'admin_password': 'SecureAdminPassword@2026!',
            'city': 'Ahmedabad',
            'state': 'Gujarat',
        }

        # Blocked without recent re-auth
        self.profile.last_reauth_at = None
        self.profile.save()
        res_blocked = self.client.post(url, data=payload, content_type='application/json', HTTP_AUTHORIZATION=f'Bearer {self.token}')
        self.assertEqual(res_blocked.status_code, 403)
        self.assertIn('reauth_required', str(res_blocked.content))

        # Allowed after re-auth
        self.profile.last_reauth_at = timezone.now()
        self.profile.save()
        res_ok = self.client.post(url, data=payload, content_type='application/json', HTTP_AUTHORIZATION=f'Bearer {self.token}')
        self.assertEqual(res_ok.status_code, 201)

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

    def test_monitoring_health_endpoint(self):
        """Test monitoring health API reports DB, Ollama, disk, and jobs status."""
        url = f'/{self.slug}/api/monitoring/health/'
        res = self.client.get(url, HTTP_AUTHORIZATION=f'Bearer {self.token}')
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data['status'], 'success')
        self.assertIn('database', data['health'])
        self.assertIn('ollama', data['health'])
        self.assertIn('disk', data['health'])
        self.assertIn('jobs', data['health'])
        self.assertIn('backup', data['health'])

    def test_logs_secrets_masking(self):
        """Test log viewer masks passwords, Bearer tokens, JWTs, and recovery codes."""
        raw_log = 'User login failed with password="SecretPassword123!" using Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.e30.fake token code=ABCD-1234'
        masked = mask_sensitive_data(raw_log)
        self.assertNotIn('SecretPassword123!', masked)
        self.assertNotIn('eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9', masked)
        self.assertIn('[MASKED_PASSWORD]', masked)
        self.assertIn('[MASKED_TOKEN]', masked)
        self.assertIn('[MASKED_CODE]', masked)

        # API check
        url = f'/{self.slug}/api/monitoring/logs/'
        res = self.client.get(url, HTTP_AUTHORIZATION=f'Bearer {self.token}')
        self.assertEqual(res.status_code, 200)
        self.assertIn('logs', res.json())

        # Error summary API check
        err_url = f'/{self.slug}/api/monitoring/error-summary/'
        err_res = self.client.get(err_url, HTTP_AUTHORIZATION=f'Bearer {self.token}')
        self.assertEqual(err_res.status_code, 200)
        self.assertIn('summary', err_res.json())

    def test_alert_deduplication(self):
        """Test email alerts suppress duplicates within cooldown window and track sent count."""
        key = 'disk_space_warning_test'
        # 1st alert triggers send
        sent1 = send_deduplicated_alert(
            alert_key=key,
            subject='Disk Space Warning',
            message='Disk usage reached 85%',
            severity='warning',
            cooldown_minutes=60,
        )
        self.assertTrue(sent1)

        # 2nd alert immediately after is throttled/suppressed
        sent2 = send_deduplicated_alert(
            alert_key=key,
            subject='Disk Space Warning',
            message='Disk usage reached 86%',
            severity='warning',
            cooldown_minutes=60,
        )
        self.assertFalse(sent2)

        # Record counts two occurrences
        rec = AlertNotificationRecord.objects.get(alert_key=key)
        self.assertEqual(rec.sent_count, 2)

    def test_jobs_center_stuck_job_detector_and_actions(self):
        """Test job center detects stuck jobs (>15m) and enables retry and cancel actions."""
        admin_inst = AdminInstitution.objects.create(
            admin=self.user,
            institution_name='Jobs Test Institute',
            institution_code='INST-2026-099',
        )
        old_time = timezone.now() - timedelta(minutes=25)
        job = PaperGenerationJob.objects.create(
            institution=admin_inst,
            faculty=self.user,
            department='Computer Science',
            model='qwen2.5:3b',
            status=PaperGenerationJob.Status.RUNNING,
        )
        # Manually backdate created_at to simulate stuck state
        PaperGenerationJob.objects.filter(pk=job.id).update(created_at=old_time)

        # List jobs: should be flagged as is_stuck
        jobs_url = f'/{self.slug}/api/jobs/'
        res_list = self.client.get(jobs_url, HTTP_AUTHORIZATION=f'Bearer {self.token}')
        self.assertEqual(res_list.status_code, 200)
        job_item = next(j for j in res_list.json()['jobs'] if j['id'] == job.id)
        self.assertTrue(job_item['is_stuck'])

        # Stuck detector auto-fail
        detect_url = f'/{self.slug}/api/jobs/stuck-detector/'
        res_detect = self.client.post(
            detect_url,
            data={'timeout': 15, 'auto_fail': True},
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Bearer {self.token}',
        )
        self.assertEqual(res_detect.status_code, 200)
        self.assertIn(job.id, res_detect.json()['stuck_ids'])
        job.refresh_from_db()
        self.assertEqual(job.status, PaperGenerationJob.Status.FAILED)

        # Retry action
        retry_url = f'/{self.slug}/api/jobs/{job.id}/retry/'
        res_retry = self.client.post(retry_url, HTTP_AUTHORIZATION=f'Bearer {self.token}')
        self.assertEqual(res_retry.status_code, 200)
        job.refresh_from_db()
        self.assertEqual(job.status, PaperGenerationJob.Status.QUEUED)

        # Cancel action
        cancel_url = f'/{self.slug}/api/jobs/{job.id}/cancel/'
        res_cancel = self.client.post(cancel_url, HTTP_AUTHORIZATION=f'Bearer {self.token}')
        self.assertEqual(res_cancel.status_code, 200)
        job.refresh_from_db()
        self.assertEqual(job.status, PaperGenerationJob.Status.CANCELLED)

    def test_maintenance_window_configuration_and_reauth(self):
        """Test configuring MaintenanceWindow via API enforces re-auth and activates correctly."""
        url = f'/{self.slug}/api/operations/maintenance/'

        # Blocked without recent re-auth
        self.profile.last_reauth_at = None
        self.profile.save()
        res_blocked = self.client.post(
            url,
            data={'is_enabled': True, 'custom_message': 'Scheduled Maintenance v2'},
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Bearer {self.token}',
        )
        self.assertEqual(res_blocked.status_code, 403)

        # Allowed after re-auth
        self.profile.last_reauth_at = timezone.now()
        self.profile.save()
        res_ok = self.client.post(
            url,
            data={'is_enabled': True, 'custom_message': 'Scheduled Maintenance v2'},
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Bearer {self.token}',
        )
        self.assertEqual(res_ok.status_code, 200)

        # Verify active maintenance window returns 503 for non-superadmin
        reg_res = self.client.get('/api/departments/')
        self.assertEqual(reg_res.status_code, 503)
        self.assertIn('Scheduled Maintenance v2', reg_res.json()['message'])

        # Turn off maintenance
        self.client.post(
            url,
            data={'is_enabled': False},
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Bearer {self.token}',
        )
        reg_res_off = self.client.get('/api/departments/')
        self.assertEqual(reg_res_off.status_code, 200)

    def test_backup_retention_pruning(self):
        """Test backup retention pruning deletes records and files exceeding thresholds."""
        old_time = timezone.now() - timedelta(days=20)
        old_rec = DatabaseBackupRecord.objects.create(
            filename='examai_backup_old_test.sql',
            file_path='e:/03 Study/Django/backups/examai_backup_old_test.sql',
            file_size_bytes=1000,
            backup_type='daily',
            status='completed',
        )
        DatabaseBackupRecord.objects.filter(pk=old_rec.id).update(created_at=old_time)

        fresh_rec = DatabaseBackupRecord.objects.create(
            filename='examai_backup_fresh_test.sql',
            file_path='e:/03 Study/Django/backups/examai_backup_fresh_test.sql',
            file_size_bytes=1000,
            backup_type='daily',
            status='completed',
        )

        pruned = prune_backups(daily_retention_days=14)
        self.assertGreaterEqual(pruned, 1)
        self.assertFalse(DatabaseBackupRecord.objects.filter(pk=old_rec.id).exists())
        self.assertTrue(DatabaseBackupRecord.objects.filter(pk=fresh_rec.id).exists())
        fresh_rec.delete()

    def test_institute_policy_and_quotas_update(self):
        """Test configuring institute quotas, policy overrides, and feature flags."""
        admin_inst = AdminInstitution.objects.create(
            admin=self.user,
            institution_name='Policy Test Institute',
            institution_code='INST-2026-088',
        )
        url = f'/{self.slug}/api/institutes/{admin_inst.id}/policy/'

        # Get initial usage
        res_get = self.client.get(url, HTTP_AUTHORIZATION=f'Bearer {self.token}')
        self.assertEqual(res_get.status_code, 200)
        self.assertIn('usage_and_policy', res_get.json())

        # Update policy with re-auth
        self.profile.last_reauth_at = timezone.now()
        self.profile.save()
        payload = {
            'max_students': 8000,
            'max_faculty': 350,
            'max_ai_generations_per_month': 1200,
            'faculty_can_publish_without_review': False,
            'feature_flags': {'camera_required': True, 'audio_monitoring': True},
        }
        res_post = self.client.post(url, data=payload, content_type='application/json', HTTP_AUTHORIZATION=f'Bearer {self.token}')
        self.assertEqual(res_post.status_code, 200)
        updated_data = res_post.json()['usage_and_policy']
        self.assertEqual(updated_data['students']['quota'], 8000)
        self.assertEqual(updated_data['faculty']['quota'], 350)
        self.assertEqual(updated_data['policy']['faculty_can_publish_without_review'], False)

    def test_bulk_import_template_and_dry_run_validation(self):
        """Test bulk import template download and dry-run row-by-row error detection."""
        # 1. Download template
        tpl_url = f'/{self.slug}/api/institutes/bulk-import/template/?role=student'
        res_tpl = self.client.get(tpl_url, HTTP_AUTHORIZATION=f'Bearer {self.token}')
        self.assertEqual(res_tpl.status_code, 200)
        self.assertIn('email,first_name,last_name,department,roll_number', str(res_tpl.content))

        # 2. Dry-run with an invalid row (bad email and unauthorized department)
        admin_inst = AdminInstitution.objects.create(
            admin=self.user,
            institution_name='Bulk Test Institute',
            institution_code='INST-2026-077',
        )
        from admins.models import AdminDepartment
        AdminDepartment.objects.create(institution=admin_inst, department_name='Computer Science')

        csv_content = (
            "email,first_name,last_name,department,roll_number\n"
            "valid.student@college.edu,Valid,Student,Computer Science,CS101\n"
            "bad-email-format,Invalid,Student,NonExistentDept,CS102\n"
        )

        import_url = f'/{self.slug}/api/institutes/{admin_inst.id}/bulk-import/'
        self.profile.last_reauth_at = timezone.now()
        self.profile.save()

        res_dry = self.client.post(
            import_url,
            data={'role': 'student', 'dry_run': 'true', 'content': csv_content},
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Bearer {self.token}',
        )
        self.assertEqual(res_dry.status_code, 400)
        summary = res_dry.json()
        self.assertEqual(summary['error_count'], 1)
        self.assertEqual(summary['valid_count'], 1)
        # Verify no student was created during dry run
        self.assertFalse(User.objects.filter(email='valid.student@college.edu').exists())

    def test_bulk_import_atomic_execution(self):
        """Test atomic bulk import creates users and student profiles with random credentials."""
        admin_inst = AdminInstitution.objects.create(
            admin=self.user,
            institution_name='Atomic Test Institute',
            institution_code='INST-2026-066',
        )
        from admins.models import AdminDepartment
        AdminDepartment.objects.create(institution=admin_inst, department_name='Information Technology')

        csv_content = (
            "email,first_name,last_name,department,roll_number\n"
            "onboard1@college.edu,Onboard1,User,Information Technology,IT001\n"
            "onboard2@college.edu,Onboard2,User,Information Technology,IT002\n"
        )

        import_url = f'/{self.slug}/api/institutes/{admin_inst.id}/bulk-import/'
        self.profile.last_reauth_at = timezone.now()
        self.profile.save()

        res = self.client.post(
            import_url,
            data={'role': 'student', 'dry_run': 'false', 'content': csv_content},
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Bearer {self.token}',
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data['imported_count'], 2)
        self.assertEqual(len(data['credentials']), 2)

        # Verify users exist in database with correct immutable department
        from students.models import StudentProfile
        p1 = StudentProfile.objects.filter(user__email='onboard1@college.edu').first()
        self.assertIsNotNone(p1)
        self.assertEqual(p1.department, 'Information Technology')

    def test_announcements_creation_and_xss_sanitization(self):
        """Test announcement creation escapes raw HTML tags to prevent XSS attacks."""
        url = f'/{self.slug}/api/announcements/'
        self.profile.last_reauth_at = timezone.now()
        self.profile.save()

        xss_title = '<script>alert("hack")</script>Urgent Server Maintenance'
        xss_message = '<img src=x onerror=alert(1)>Scheduled downtime tonight.'

        res = self.client.post(
            url,
            data={'title': xss_title, 'message': xss_message, 'target_type': 'all'},
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Bearer {self.token}',
        )
        self.assertEqual(res.status_code, 201)

        # Retrieve and verify sanitized
        from superadmin.models import SystemAnnouncement
        ann = SystemAnnouncement.objects.get(pk=res.json()['announcement_id'])
        self.assertNotIn('<script>', ann.title)
        self.assertIn('&lt;script&gt;', ann.title)
        self.assertNotIn('<img', ann.message)

    def test_permissions_matrix_generation(self):
        """Test permissions matrix endpoint returns capabilities across all 4 system roles."""
        url = f'/{self.slug}/api/permissions/matrix/'
        res = self.client.get(url, HTTP_AUTHORIZATION=f'Bearer {self.token}')
        self.assertEqual(res.status_code, 200)
        matrix_data = res.json()['permissions_matrix']
        self.assertIn('roles', matrix_data)
        self.assertIn('matrix', matrix_data)
        self.assertIn('detected_permission_classes', matrix_data)
        self.assertGreater(len(matrix_data['matrix']), 5)

    def test_impersonation_session_and_superadmin_block(self):
        """Test time-limited impersonation token creation and ensure super admins cannot be impersonated."""
        target_student = User.objects.create_user(
            username='student_support_test',
            email='support.student@college.edu',
            password='SupportTestPassword123!',
        )
        admin_inst = AdminInstitution.objects.create(
            admin=self.user,
            institution_name='Support Institute',
            institution_code='INST-2026-055',
        )
        from students.models import StudentProfile
        StudentProfile.objects.create(user=target_student, institution=admin_inst, department='Civil')

        imp_url = f'/{self.slug}/api/users/{target_student.id}/impersonate/'

        # Blocked without re-auth
        self.profile.last_reauth_at = None
        self.profile.save()
        res_blocked = self.client.post(
            imp_url,
            data={'reason': 'Resolving proctoring camera issue'},
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Bearer {self.token}',
        )
        self.assertEqual(res_blocked.status_code, 403)

        # Success with re-auth
        self.profile.last_reauth_at = timezone.now()
        self.profile.save()
        res_ok = self.client.post(
            imp_url,
            data={'reason': 'Resolving proctoring camera issue'},
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Bearer {self.token}',
        )
        self.assertEqual(res_ok.status_code, 200)
        data = res_ok.json()
        self.assertTrue(data['impersonation']['is_impersonated'])
        self.assertEqual(data['impersonation']['target_user']['role'], 'student')
        self.assertIn('access_token', data['impersonation'])

        # Prohibit impersonation of Super Admin
        res_sa_block = self.client.post(
            f'/{self.slug}/api/users/{self.user.id}/impersonate/',
            data={'reason': 'Illegal admin impersonation attempt'},
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Bearer {self.token}',
        )
        self.assertEqual(res_sa_block.status_code, 400)
        self.assertIn('strictly prohibited', str(res_sa_block.content))

    def test_cross_institute_analytics(self):
        """Test platform-wide aggregate analytics returns summary metrics."""
        url = f'/{self.slug}/api/analytics/cross-institute/'
        res = self.client.get(url, HTTP_AUTHORIZATION=f'Bearer {self.token}')
        self.assertEqual(res.status_code, 200)
        data = res.json()['analytics']
        self.assertIn('institutions', data)
        self.assertIn('users', data)
        self.assertIn('exams_and_results', data)
        self.assertIn('ai_generation', data)
        self.assertIn('growth_trend_30d', data)

    def test_exports_csv_formula_injection_defense(self):
        """Test CSV export escapes dangerous formula injection characters (=, +, -, @)."""
        from superadmin.exports_service import sanitize_csv_cell
        self.assertEqual(sanitize_csv_cell('=1+1'), "'=1+1")
        self.assertEqual(sanitize_csv_cell('@SUM(A1:A10)'), "'@SUM(A1:A10)")
        self.assertEqual(sanitize_csv_cell('+cmd|"/C calc"'), "'+cmd|\"/C calc\"")
        self.assertEqual(sanitize_csv_cell('-2+3'), "'-2+3")
        self.assertEqual(sanitize_csv_cell('NormalText'), 'NormalText')

        # API export with re-auth
        self.profile.last_reauth_at = timezone.now()
        self.profile.save()
        exp_url = f'/{self.slug}/api/data/exports/?entity=users'
        res = self.client.get(exp_url, HTTP_AUTHORIZATION=f'Bearer {self.token}')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res['Content-Type'], 'text/csv; charset=utf-8')
        self.assertIn('attachment;', res['Content-Disposition'])

    def test_dpdp_user_data_portability_export(self):
        """Test DPDP data portability export generates machine-readable JSON package."""
        target_student = User.objects.create_user(
            username='dpdp_export_student',
            email='dpdp.student@college.edu',
            password='TestPassword123!',
        )
        admin_inst = AdminInstitution.objects.create(
            admin=self.user,
            institution_name='DPDP Test Institute',
            institution_code='INST-2026-044',
        )
        from students.models import StudentProfile
        StudentProfile.objects.create(user=target_student, institution=admin_inst, department='IT')

        url = f'/{self.slug}/api/privacy/dpdp/export/{target_student.id}/'
        self.profile.last_reauth_at = timezone.now()
        self.profile.save()

        res = self.client.get(url, HTTP_AUTHORIZATION=f'Bearer {self.token}')
        self.assertEqual(res.status_code, 200)
        pkg = res.json()['data_package']
        self.assertIn('personal_identity', pkg)
        self.assertIn('academic_profile', pkg)
        self.assertIn('disclaimer', pkg)
        self.assertEqual(pkg['personal_identity']['username'], 'dpdp_export_student')

    def test_dpdp_dry_run_and_execution_anonymization(self):
        """Test DPDP anonymization dry-run impact report and atomic personal data scrubbing."""
        target_student = User.objects.create_user(
            username='anonymize_student_test',
            email='to_anonymize@college.edu',
            first_name='RealFirstName',
            last_name='RealLastName',
            password='TestPassword123!',
        )
        admin_inst = AdminInstitution.objects.create(
            admin=self.user,
            institution_name='Anonymize Institute',
            institution_code='INST-2026-033',
        )
        from students.models import StudentProfile
        StudentProfile.objects.create(user=target_student, institution=admin_inst, department='Civil')

        # Create academic attempt
        exam = Exam.objects.create(
            institution=admin_inst,
            department='Civil',
            title='Hydraulics Exam',
            created_by=self.user,
            status=Exam.Status.PUBLISHED,
            duration_minutes=60,
            starts_at=timezone.now() - timedelta(hours=2),
            ends_at=timezone.now() + timedelta(hours=2),
        )
        from api.models import StudentAttempt
        attempt = StudentAttempt.objects.create(
            exam=exam,
            institution=admin_inst,
            student=target_student,
            status=StudentAttempt.Status.EVALUATED,
            total_score=85.0,
            max_score=100.0,
        )

        anon_url = f'/{self.slug}/api/privacy/dpdp/anonymize/{target_student.id}/'
        self.profile.last_reauth_at = timezone.now()
        self.profile.save()

        # 1. Dry run: verifies preview without altering user
        res_dry = self.client.post(
            anon_url,
            data={'dry_run': 'true'},
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Bearer {self.token}',
        )
        self.assertEqual(res_dry.status_code, 200)
        self.assertIn('personal_data_to_scrub', res_dry.json()['dry_run_summary'])
        target_student.refresh_from_db()
        self.assertEqual(target_student.first_name, 'RealFirstName')

        # 2. Execution: scrubs personal data, preserves academic attempt
        res_exec = self.client.post(
            anon_url,
            data={'dry_run': 'false', 'reason': 'Data Principal requested erasure under DPDP Section 12'},
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Bearer {self.token}',
        )
        self.assertEqual(res_exec.status_code, 200)
        target_student.refresh_from_db()
        self.assertEqual(target_student.username, f'anon_user_{target_student.id}')
        self.assertEqual(target_student.first_name, 'Anonymized')
        self.assertEqual(target_student.last_name, 'User')
        self.assertFalse(target_student.has_usable_password())

        # Academic attempt remains intact in the database for institutional audits!
        attempt.refresh_from_db()
        self.assertEqual(attempt.student_id, target_student.id)
        self.assertEqual(attempt.total_score, 85.0)

    def test_dpdp_data_inventory(self):
        """Test DPDP data inventory endpoint returns complete personal data catalog."""
        url = f'/{self.slug}/api/privacy/dpdp/inventory/'
        res = self.client.get(url, HTTP_AUTHORIZATION=f'Bearer {self.token}')
        self.assertEqual(res.status_code, 200)
        inv = res.json()['data_inventory']
        self.assertIn('inventory', inv)
        self.assertIn('disclaimer', inv)
        self.assertGreater(len(inv['inventory']), 3)


class SuperAdminUserManagementModuleATests(TestCase):
    def setUp(self):
        self.slug = 'a1b2c3d4e5f67890123456789abcdef0'
        settings.SUPER_ADMIN_PATH = self.slug
        self.sa_user = User.objects.create_user(
            username='harshposhiya',
            email='harshposhiya92@gmail.com',
            password='TestSecurePassword123!',
        )
        self.profile = SuperAdminProfile.objects.create(
            user=self.sa_user,
            totp_secret=generate_totp_secret(),
            is_totp_enrolled=True,
            active_session_id='sess_test_123',
            last_reauth_at=timezone.now(),
        )
        self.token = generate_super_admin_token(self.sa_user, session_id='sess_test_123')
        self.client = Client()

        # Seed institution
        self.inst = AdminInstitution.objects.create(
            admin=self.sa_user,  # Temporary admin
            institution_name='Apex University',
            institution_code='INST-2026-999',
            city='Vadodara',
            state='Gujarat',
        )

        # Seed students
        self.stu1_user = User.objects.create_user(username='stu_alice', email='alice@apex.edu', password='pw')
        self.stu1_profile = StudentProfile.objects.create(
            user=self.stu1_user, institution=self.inst, student_id='STU-2026-0001', department='Computer Engineering'
        )

        self.stu2_user = User.objects.create_user(username='stu_bob', email='bob@apex.edu', password='pw')
        self.stu2_profile = StudentProfile.objects.create(
            user=self.stu2_user, institution=self.inst, student_id='STU-2025-0042', department='Information Technology'
        )

        # Seed faculty
        self.fac_user = User.objects.create_user(username='fac_dr_smith', email='smith@apex.edu', password='pw')
        self.fac_profile = FacultyProfile.objects.create(
            user=self.fac_user, institution=self.inst, employee_id='FAC-2026-010', department='Computer Engineering', designation='Professor'
        )

        # Seed institute admin
        self.admin_user = User.objects.create_user(username='admin_john', email='john@apex.edu', password='pw')
        AdminProfile.objects.create(user=self.admin_user)
        self.inst.admin = self.admin_user
        self.inst.save(update_fields=['admin'])

    def test_role_separated_user_listing_and_counts(self):
        """Verify Students, Faculty, and Admins are listed separately with accurate tab counts."""
        url = f'/{self.slug}/api/users/'
        res_stu = self.client.get(f'{url}?role=student', HTTP_AUTHORIZATION=f'Bearer {self.token}')
        self.assertEqual(res_stu.status_code, 200)
        data_stu = res_stu.json()
        self.assertEqual(data_stu['counts']['students'], 2)
        self.assertEqual(data_stu['counts']['faculty'], 1)
        self.assertEqual(data_stu['counts']['admins'], 1)
        self.assertEqual(len(data_stu['data']), 2)
        self.assertEqual(data_stu['data'][0]['role'], 'student')

        # Faculty Tab
        res_fac = self.client.get(f'{url}?role=faculty', HTTP_AUTHORIZATION=f'Bearer {self.token}')
        self.assertEqual(res_fac.status_code, 200)
        data_fac = res_fac.json()
        self.assertEqual(len(data_fac['data']), 1)
        self.assertEqual(data_fac['data'][0]['username'], 'fac_dr_smith')
        self.assertEqual(data_fac['data'][0]['designation'], 'Professor')

        # Admins Tab
        res_adm = self.client.get(f'{url}?role=admin', HTTP_AUTHORIZATION=f'Bearer {self.token}')
        self.assertEqual(res_adm.status_code, 200)
        data_adm = res_adm.json()
        self.assertEqual(len(data_adm['data']), 1)
        self.assertEqual(data_adm['data'][0]['username'], 'admin_john')

        # Super admin account is NEVER listed in the directory
        all_usernames = [u['username'] for u in data_stu['data'] + data_fac['data'] + data_adm['data']]
        self.assertNotIn('harshposhiya', all_usernames)

    def test_student_batch_and_search_filters(self):
        """Test batch year filtering and search across identifiers."""
        url = f'/{self.slug}/api/users/'
        # Filter batch 2026
        res = self.client.get(f'{url}?role=student&batch_year=2026', HTTP_AUTHORIZATION=f'Bearer {self.token}')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.json()['data']), 1)
        self.assertEqual(res.json()['data'][0]['username'], 'stu_alice')

        # Search by enrollment ID
        res_search = self.client.get(f'{url}?role=student&search=STU-2025-0042', HTTP_AUTHORIZATION=f'Bearer {self.token}')
        self.assertEqual(res_search.status_code, 200)
        self.assertEqual(len(res_search.json()['data']), 1)
        self.assertEqual(res_search.json()['data'][0]['username'], 'stu_bob')

    def test_user_detail_drawer_endpoint(self):
        """Test comprehensive drawer returns activity summary and notifications."""
        Notification.objects.create(
            user=self.stu1_user,
            institution=self.inst,
            title='Midterm Schedule Posted',
            message='Please review syllabus',
            type='info',
        )
        url = f'/{self.slug}/api/users/{self.stu1_user.id}/drawer/'
        res = self.client.get(url, HTTP_AUTHORIZATION=f'Bearer {self.token}')
        self.assertEqual(res.status_code, 200)
        data = res.json()['data']
        self.assertEqual(data['profile']['username'], 'stu_alice')
        self.assertEqual(data['profile']['department'], 'Computer Engineering')
        self.assertEqual(len(data['notifications']), 1)
        self.assertEqual(data['notifications'][0]['title'], 'Midterm Schedule Posted')

    def test_create_user_and_super_admin_forbidden(self):
        """Verify user creation and strict prohibition of creating a second super admin."""
        url = f'/{self.slug}/api/users/create/'
        # 1. Prohibit super admin creation
        res_bad = self.client.post(
            url,
            data={'role': 'super_admin', 'email': 'evil@hacker.com', 'username': 'fake_super'},
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Bearer {self.token}',
        )
        self.assertEqual(res_bad.status_code, 400)

        # 2. Valid Student Creation
        res_good = self.client.post(
            url,
            data={
                'role': 'student',
                'email': 'new_student@apex.edu',
                'first_name': 'Charlie',
                'last_name': 'Brown',
                'institution_id': self.inst.id,
                'department': 'Mechanical Engineering',
            },
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Bearer {self.token}',
        )
        self.assertEqual(res_good.status_code, 201)
        new_u = User.objects.filter(email='new_student@apex.edu').first()
        self.assertIsNotNone(new_u)
        self.assertTrue(hasattr(new_u, 'student_profile'))
        self.assertTrue(new_u.student_profile.student_id.startswith('STU-'))

    def test_activate_deactivate_and_last_super_admin_safety(self):
        """Verify activation/deactivation and enforcement that Super Admin cannot be deactivated."""
        # 1. Cannot deactivate super admin
        url_sa = f'/{self.slug}/api/users/{self.sa_user.id}/toggle-active/'
        res_sa = self.client.post(url_sa, HTTP_AUTHORIZATION=f'Bearer {self.token}')
        self.assertEqual(res_sa.status_code, 400)

        # 2. Toggle student active -> inactive
        url_stu = f'/{self.slug}/api/users/{self.stu1_user.id}/toggle-active/'
        res = self.client.post(url_stu, HTTP_AUTHORIZATION=f'Bearer {self.token}')
        self.assertEqual(res.status_code, 200)
        self.stu1_user.refresh_from_db()
        self.assertFalse(self.stu1_user.is_active)

    def test_bulk_actions_atomic(self):
        """Test atomic bulk operations on users."""
        url = f'/{self.slug}/api/users/bulk-action/'
        res = self.client.post(
            url,
            data={
                'action': 'deactivate',
                'user_ids': [self.stu1_user.id, self.stu2_user.id],
            },
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Bearer {self.token}',
        )
        self.assertEqual(res.status_code, 200)
        self.stu1_user.refresh_from_db()
        self.stu2_user.refresh_from_db()
        self.assertFalse(self.stu1_user.is_active)
        self.assertFalse(self.stu2_user.is_active)


class SuperAdminAIModelManagementModuleBTests(TestCase):
    """
    Automated regression and security tests for Module B: AI Model Management.
    """

    def setUp(self):
        self.slug = 'a1b2c3d4e5f67890123456789abcdef0'
        settings.SUPER_ADMIN_PATH = self.slug
        self.user = User.objects.create_superuser('aimodel_sa', 'aimodel_sa@example.com', 'SuperPass123!@#')
        self.profile = SuperAdminProfile.objects.create(
            user=self.user,
            is_totp_enrolled=True,
            totp_secret='JBSWY3DPEHPK3PXP',
            active_session_id='sess_aimodel_123',
            last_reauth_at=timezone.now(),
        )
        self.token = generate_super_admin_token(self.user, session_id='sess_aimodel_123')
        self.client = Client()

    def test_get_ai_models_and_catalog(self):
        """GET /api/ai/models/ returns registered models and free online models catalog."""
        url = f'/{self.slug}/api/ai/models/'
        res = self.client.get(url, HTTP_AUTHORIZATION=f'Bearer {self.token}')
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(body['status'], 'success')
        self.assertIn('models', body)
        self.assertIn('catalog', body)
        self.assertGreater(len(body['catalog']), 0)

    def test_initiate_pull_validation(self):
        """POST /api/ai/models/ validates model tags and rejects malicious strings."""
        url = f'/{self.slug}/api/ai/models/'

        # Malicious tag with shell injection characters
        res_bad = self.client.post(
            url,
            data={'name': 'llama3.2; rm -rf /'},
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Bearer {self.token}',
        )
        self.assertEqual(res_bad.status_code, 400)

        # Valid tag creates pulling record
        res_good = self.client.post(
            url,
            data={'name': 'smollm2:135m'},
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Bearer {self.token}',
        )
        self.assertEqual(res_good.status_code, 202)
        self.assertTrue(AIModel.objects.filter(name='smollm2:135m').exists())

    def test_toggle_and_set_default_model(self):
        """Test enabling, disabling, and designating default model."""
        m1 = AIModel.objects.create(name='test-model-1:latest', is_enabled=True, is_default=False, status='ready')
        m2 = AIModel.objects.create(name='test-model-2:latest', is_enabled=True, is_default=True, status='ready')

        # Set m1 as default
        url_default = f'/{self.slug}/api/ai/models/{m1.id}/default/'
        res_def = self.client.post(url_default, HTTP_AUTHORIZATION=f'Bearer {self.token}')
        self.assertEqual(res_def.status_code, 200)

        m1.refresh_from_db()
        m2.refresh_from_db()
        self.assertTrue(m1.is_default)
        self.assertFalse(m2.is_default)

        # Disable m2
        url_toggle = f'/{self.slug}/api/ai/models/{m2.id}/toggle/'
        res_tog = self.client.post(
            url_toggle,
            data={'is_enabled': False},
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Bearer {self.token}',
        )
        self.assertEqual(res_tog.status_code, 200)
        m2.refresh_from_db()
        self.assertFalse(m2.is_enabled)

    def test_delete_model_requires_reauth(self):
        """Deleting an AI model enforces step-up re-authentication."""
        m = AIModel.objects.create(name='test-delete-model:latest', is_enabled=False, is_default=False, status='ready')
        # Ensure a default exists so deletion is permitted
        AIModel.objects.create(name='test-fallback:latest', is_enabled=True, is_default=True, status='ready')

        url = f'/{self.slug}/api/ai/models/{m.id}/delete/'

        # Expired reauth -> 403
        self.profile.last_reauth_at = timezone.now() - timedelta(minutes=10)
        self.profile.save()

        res_forbidden = self.client.post(url, HTTP_AUTHORIZATION=f'Bearer {self.token}')
        self.assertEqual(res_forbidden.status_code, 403)
        self.assertEqual(res_forbidden.json().get('status'), 'reauth_required')

        # Fresh reauth -> 200 deleted
        self.profile.last_reauth_at = timezone.now()
        self.profile.save()

        res_ok = self.client.post(url, HTTP_AUTHORIZATION=f'Bearer {self.token}')
        self.assertEqual(res_ok.status_code, 200)
        self.assertFalse(AIModel.objects.filter(id=m.id).exists())


class SuperAdminNotificationEngineModuleCTests(TestCase):
    """
    Automated tests for Module C: Notifications Engine, Audience Resolution, and Delivery Tracking.
    """

    def setUp(self):
        self.slug = 'a1b2c3d4e5f67890123456789abcdef0'
        settings.SUPER_ADMIN_PATH = self.slug
        self.sa_user = User.objects.create_superuser('notify_sa', 'notify_sa@example.com', 'SuperPass123!@#')
        self.profile = SuperAdminProfile.objects.create(
            user=self.sa_user,
            is_totp_enrolled=True,
            totp_secret='JBSWY3DPEHPK3PXP',
            active_session_id='sess_notify_123',
            last_reauth_at=timezone.now(),
        )
        self.token = generate_super_admin_token(self.sa_user, session_id='sess_notify_123')
        self.client = Client()

        # Seed test institution, students, and faculty
        self.inst = AdminInstitution.objects.create(
            admin=self.sa_user,
            institution_name='Notification Test Institute',
            institution_code='INST-N01',
        )
        self.stu = User.objects.create_user(username='stu_notify', email='stu_notify@test.edu', password='pw')
        self.stu_profile = StudentProfile.objects.create(
            user=self.stu,
            institution=self.inst,
            student_id='STU-NOTIF-01',
            department='Computer Engineering',
        )

        self.fac = User.objects.create_user(username='fac_notify', email='fac_notify@test.edu', password='pw')
        self.fac_profile = FacultyProfile.objects.create(
            user=self.fac,
            institution=self.inst,
            department='Computer Engineering',
            designation='Assistant Professor',
        )

    def test_audience_preview_resolutions(self):
        """Test audience preview for all, role-based, and department-based filters."""
        url = f'/{self.slug}/api/notifications/audience-preview/'

        # Preview: All
        res_all = self.client.post(url, data={'target_audience': 'all'}, content_type='application/json', HTTP_AUTHORIZATION=f'Bearer {self.token}')
        self.assertEqual(res_all.status_code, 200)
        body_all = res_all.json()
        self.assertGreaterEqual(body_all['total_recipients'], 2)

        # Preview: Students only
        res_stu = self.client.post(
            url,
            data={'target_audience': 'role', 'target_role': 'student'},
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Bearer {self.token}',
        )
        self.assertEqual(res_stu.status_code, 200)
        self.assertEqual(res_stu.json()['total_recipients'], 1)
        self.assertEqual(res_stu.json()['sample_recipients'][0]['username'], 'stu_notify')

        # Preview: Faculty only
        res_fac = self.client.post(
            url,
            data={'target_audience': 'role', 'target_role': 'faculty'},
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Bearer {self.token}',
        )
        self.assertEqual(res_fac.status_code, 200)
        self.assertEqual(res_fac.json()['total_recipients'], 1)
        self.assertEqual(res_fac.json()['sample_recipients'][0]['username'], 'fac_notify')

    def test_create_and_dispatch_campaign_immediate(self):
        """Creating an immediate campaign dispatches api.Notification to users and creates delivery tracking records."""
        url = f'/{self.slug}/api/notifications/campaigns/'
        payload = {
            'title': 'Emergency Server Maintenance Scheduled',
            'message': 'Platform will undergo brief maintenance at 11 PM.',
            'notification_type': 'warning',
            'target_audience': 'role',
            'target_role': 'student',
            'link': '/exams',
        }

        res = self.client.post(url, data=payload, content_type='application/json', HTTP_AUTHORIZATION=f'Bearer {self.token}')
        self.assertEqual(res.status_code, 201)
        c_id = res.json()['data']['id']

        # Give background worker a brief moment to write records
        time.sleep(0.5)

        campaign = NotificationCampaign.objects.get(id=c_id)
        self.assertIn(campaign.status, ('sending', 'completed'))
        self.assertEqual(campaign.recipients_count, 1)

        # Verify that student received the notification (bell integration)
        notif = Notification.objects.filter(user=self.stu, title='Emergency Server Maintenance Scheduled').first()
        self.assertIsNotNone(notif)
        self.assertEqual(notif.type, 'warning')
        self.assertFalse(notif.is_read)

        # Verify campaign delivery record exists
        deliv = CampaignDeliveryRecord.objects.filter(campaign=campaign, user=self.stu).first()
        self.assertIsNotNone(deliv)
        self.assertEqual(deliv.status, 'delivered')

    def test_schedule_and_cancel_campaign(self):
        """Test scheduling a campaign for future execution and cancelling before dispatch."""
        url = f'/{self.slug}/api/notifications/campaigns/'
        future_time = timezone.now() + timedelta(days=2)

        payload = {
            'title': 'Next Term Registration Opens',
            'message': 'Registration opens next Monday.',
            'notification_type': 'info',
            'target_audience': 'all',
            'scheduled_at': future_time.isoformat(),
        }

        res = self.client.post(url, data=payload, content_type='application/json', HTTP_AUTHORIZATION=f'Bearer {self.token}')
        self.assertEqual(res.status_code, 201)
        c_id = res.json()['data']['id']

        campaign = NotificationCampaign.objects.get(id=c_id)
        self.assertEqual(campaign.status, 'scheduled')

        # Cancel the scheduled campaign
        cancel_url = f'/{self.slug}/api/notifications/campaigns/{c_id}/cancel/'
        res_cancel = self.client.post(cancel_url, HTTP_AUTHORIZATION=f'Bearer {self.token}')
        self.assertEqual(res_cancel.status_code, 200)

        campaign.refresh_from_db()
        self.assertEqual(campaign.status, 'cancelled')


class SuperAdminReportsAndToolsModuleDTests(TestCase):
    """
    Automated regression and security tests for Module D & E:
    Reports Catalog, Data Engine, CSV/XLSX/PDF Exports, Formula Sanitization,
    Emergency Session Revocation, and Global Quick Search.
    """

    def setUp(self):
        self.slug = 'a1b2c3d4e5f67890123456789abcdef0'
        settings.SUPER_ADMIN_PATH = self.slug
        self.sa_user = User.objects.create_superuser('reports_sa', 'reports_sa@example.com', 'SuperPass123!@#')
        self.profile = SuperAdminProfile.objects.create(
            user=self.sa_user,
            is_totp_enrolled=True,
            totp_secret='JBSWY3DPEHPK3PXP',
            active_session_id='sess_reports_123',
            last_reauth_at=timezone.now(),
        )
        self.token = generate_super_admin_token(self.sa_user, session_id='sess_reports_123')
        self.client = Client()

        # Seed test institution and exam
        self.inst = AdminInstitution.objects.create(
            admin=self.sa_user,
            institution_name='Apex University of Science',
            institution_code='APEX-TEST',
        )
        self.exam = Exam.objects.create(
            title='Database Security Midterm',
            subject='Cybersecurity',
            department='Computer Science',
            institution=self.inst,
            created_by=self.sa_user,
            total_marks=100,
            duration_minutes=60,
            status=Exam.Status.PUBLISHED,
        )

    def test_report_catalog_and_all_report_data(self):
        """Verify report catalog lists 8 reports and each report generates valid structured data."""
        url_cat = f'/{self.slug}/api/reports/'
        res_cat = self.client.get(url_cat, HTTP_AUTHORIZATION=f'Bearer {self.token}')
        self.assertEqual(res_cat.status_code, 200)
        catalog = res_cat.json()['catalog']
        self.assertEqual(len(catalog), 8)

        # Test data generation for all 8 catalog reports
        for item in catalog:
            r_id = item['id']
            url_data = f'/{self.slug}/api/reports/{r_id}/'
            res_data = self.client.get(url_data, HTTP_AUTHORIZATION=f'Bearer {self.token}')
            self.assertEqual(res_data.status_code, 200, f'Report {r_id} failed to generate data.')
            body = res_data.json()
            self.assertEqual(body['status'], 'success')
            report = body['report']
            self.assertIn('summary', report)
            self.assertIn('chart_data', report)
            self.assertIn('headers', report)
            self.assertIn('rows', report)

    def test_exports_csv_xlsx_pdf_and_signed_download(self):
        """Test exporting reports to CSV, XLSX, and PDF and validating signed token downloads."""
        from superadmin.reports_service import sanitize_formula_cell

        # 1. Formula injection test
        self.assertEqual(sanitize_formula_cell('=1+1'), "'=1+1")
        self.assertEqual(sanitize_formula_cell('+cmd|/c'), "'+cmd|/c")
        self.assertEqual(sanitize_formula_cell('@SUM(A1:A10)'), "'@SUM(A1:A10)")
        self.assertEqual(sanitize_formula_cell('-2+5'), "'-2+5")
        self.assertEqual(sanitize_formula_cell('Safe Value'), 'Safe Value')

        # 2. Export to CSV and download
        url_export = f'/{self.slug}/api/reports/system_usage/export/'
        res_csv = self.client.post(url_export, data={'format': 'csv'}, content_type='application/json', HTTP_AUTHORIZATION=f'Bearer {self.token}')
        self.assertEqual(res_csv.status_code, 200)
        token_csv = res_csv.json()['token']

        download_url_csv = f'/{self.slug}/api/reports/download/{token_csv}/'
        res_dl_csv = self.client.get(download_url_csv)
        self.assertEqual(res_dl_csv.status_code, 200)
        self.assertIn('text/csv', res_dl_csv['Content-Type'])
        self.assertIn('attachment;', res_dl_csv['Content-Disposition'])

        # 3. Export to XLSX
        res_xlsx = self.client.post(url_export, data={'format': 'xlsx'}, content_type='application/json', HTTP_AUTHORIZATION=f'Bearer {self.token}')
        self.assertEqual(res_xlsx.status_code, 200)
        token_xlsx = res_xlsx.json()['token']

        download_url_xlsx = f'/{self.slug}/api/reports/download/{token_xlsx}/'
        res_dl_xlsx = self.client.get(download_url_xlsx)
        self.assertEqual(res_dl_xlsx.status_code, 200)
        self.assertIn('spreadsheetml', res_dl_xlsx['Content-Type'])

        # 4. Export to PDF
        res_pdf = self.client.post(url_export, data={'format': 'pdf'}, content_type='application/json', HTTP_AUTHORIZATION=f'Bearer {self.token}')
        self.assertEqual(res_pdf.status_code, 200)
        token_pdf = res_pdf.json()['token']

        download_url_pdf = f'/{self.slug}/api/reports/download/{token_pdf}/'
        res_dl_pdf = self.client.get(download_url_pdf)
        self.assertEqual(res_dl_pdf.status_code, 200)
        self.assertIn('application/pdf', res_dl_pdf['Content-Type'])

    def test_emergency_revocation_requires_reauth(self):
        """Emergency session revocation mandates step-up re-authentication."""
        url = f'/{self.slug}/api/operations/emergency-revoke-sessions/'

        # Expired reauth -> 403
        self.profile.last_reauth_at = timezone.now() - timedelta(minutes=15)
        self.profile.save()

        res_forbidden = self.client.post(
            url,
            data={'reason': 'Suspected platform intrusion'},
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Bearer {self.token}',
        )
        self.assertEqual(res_forbidden.status_code, 403)
        self.assertEqual(res_forbidden.json().get('status'), 'reauth_required')

        # Fresh reauth -> 200
        self.profile.last_reauth_at = timezone.now()
        self.profile.save()

        res_ok = self.client.post(
            url,
            data={'reason': 'Suspected platform intrusion'},
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Bearer {self.token}',
        )
        self.assertEqual(res_ok.status_code, 200)
        self.assertEqual(res_ok.json()['status'], 'success')
        self.assertTrue(SuperAdminAuditLog.objects.filter(action='emergency.sessions_revoked').exists())

    def test_global_quick_search(self):
        """Global quick search finds institutes, exams, and users by query."""
        url = f'/{self.slug}/api/system/quick-search/?q=Apex'
        res = self.client.get(url, HTTP_AUTHORIZATION=f'Bearer {self.token}')
        self.assertEqual(res.status_code, 200)
        results = res.json()['results']
        self.assertTrue(any(r['title'] == 'Apex University of Science' for r in results))


class SuperAdminGlobalExamsManagerModuleTests(TestCase):
    """
    Automated tests for Global Exams Manager filtering, metadata, and export:
    - Search by title, subject, department, faculty username
    - Multi-select status and phase filters
    - Institute, department, faculty hierarchy
    - Date range, marks range, question types
    - CSV/XLSX export with formula injection sanitization (CWE-1236)
    """

    def setUp(self):
        self.slug = 'a1b2c3d4e5f67890123456789abcdef0'
        settings.SUPER_ADMIN_PATH = self.slug
        self.sa_user = User.objects.create_superuser('exams_sa', 'exams_sa@example.com', 'SuperPass123!@#')
        self.profile = SuperAdminProfile.objects.create(
            user=self.sa_user,
            is_totp_enrolled=True,
            totp_secret='JBSWY3DPEHPK3PXP',
            active_session_id='sess_exams_123',
            last_reauth_at=timezone.now(),
        )
        self.token = generate_super_admin_token(self.sa_user, session_id='sess_exams_123')
        self.client = Client()

        # Seed institutions
        self.admin2_user = User.objects.create_user(
            username='admin_beacon',
            email='admin_beacon@example.com',
            password='AdminPassword123!',
        )
        self.inst1 = AdminInstitution.objects.create(
            admin=self.sa_user,
            institution_name='Apex University of Science',
            institution_code='APEX-01',
        )
        self.inst2 = AdminInstitution.objects.create(
            admin=self.admin2_user,
            institution_name='Beacon Engineering Institute',
            institution_code='BEACON-02',
        )

        # Seed Faculty
        self.fac_user = User.objects.create_user(
            username='fac_exam_mgr',
            email='fac_exam_mgr@example.com',
            password='FacultyPassword123!',
        )
        self.fac_profile = FacultyProfile.objects.create(
            user=self.fac_user,
            department='Computer Science',
            employee_id='FAC-CS-001',
        )

        # Seed Exams
        self.exam1 = Exam.objects.create(
            title='Calculus I Final',
            subject='Mathematics',
            department='Mathematics',
            institution=self.inst1,
            created_by=self.sa_user,
            total_marks=100,
            duration_minutes=120,
            status=Exam.Status.PUBLISHED,
        )
        self.exam2 = Exam.objects.create(
            title='Intro to Algorithms',
            subject='Algorithms',
            department='Computer Science',
            institution=self.inst1,
            created_by=self.fac_user,
            total_marks=50,
            duration_minutes=60,
            status=Exam.Status.DRAFT,
        )
        self.exam3 = Exam.objects.create(
            title='=2+5 Dangerous Formula Midterm',
            subject='Computer Networks',
            department='Electronics',
            institution=self.inst2,
            created_by=self.fac_user,
            total_marks=75,
            duration_minutes=90,
            status=Exam.Status.CLOSED,
        )

    def test_exams_filter_metadata(self):
        """Metadata endpoint returns available institutes, departments, faculties, statuses, ai_models."""
        url = f'/{self.slug}/api/exams/metadata/'
        res = self.client.get(url, HTTP_AUTHORIZATION=f'Bearer {self.token}')
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(body['status'], 'success')
        meta = body['data']
        self.assertIn('institutions', meta)
        self.assertIn('departments', meta)
        self.assertIn('faculty', meta)
        self.assertIn('allowed_statuses', meta)
        self.assertIn('ai_models', meta)
        inst_names = [i.get('institution_name') or i.get('name') for i in meta['institutions']]
        self.assertIn('Apex University of Science', inst_names)
        self.assertIn('Beacon Engineering Institute', inst_names)

    def test_exams_list_filtering(self):
        """Exams list endpoint filters correctly by search, status, department, and marks."""
        base_url = f'/{self.slug}/api/exams/'

        # 1. Search by title
        res1 = self.client.get(f'{base_url}?q=Calculus', HTTP_AUTHORIZATION=f'Bearer {self.token}')
        self.assertEqual(res1.status_code, 200)
        data1 = res1.json()['data']
        self.assertEqual(len(data1), 1)
        self.assertEqual(data1[0]['title'], 'Calculus I Final')

        # 2. Filter by status (single)
        res2 = self.client.get(f'{base_url}?status=draft', HTTP_AUTHORIZATION=f'Bearer {self.token}')
        self.assertEqual(res2.status_code, 200)
        data2 = res2.json()['data']
        self.assertEqual(len(data2), 1)
        self.assertEqual(data2[0]['title'], 'Intro to Algorithms')

        # 3. Filter by status (comma-separated multi-select)
        res3 = self.client.get(f'{base_url}?status=draft,closed', HTTP_AUTHORIZATION=f'Bearer {self.token}')
        self.assertEqual(res3.status_code, 200)
        data3 = res3.json()['data']
        self.assertEqual(len(data3), 2)

        # 4. Filter by department
        res4 = self.client.get(f'{base_url}?department=Computer Science', HTTP_AUTHORIZATION=f'Bearer {self.token}')
        self.assertEqual(res4.status_code, 200)
        data4 = res4.json()['data']
        self.assertEqual(len(data4), 1)
        self.assertEqual(data4[0]['title'], 'Intro to Algorithms')

        # 5. Filter by marks range
        res5 = self.client.get(f'{base_url}?min_marks=70&max_marks=100', HTTP_AUTHORIZATION=f'Bearer {self.token}')
        self.assertEqual(res5.status_code, 200)
        data5 = res5.json()['data']
        titles = [e['title'] for e in data5]
        self.assertIn('Calculus I Final', titles)
        self.assertIn('=2+5 Dangerous Formula Midterm', titles)
        self.assertNotIn('Intro to Algorithms', titles)

    def test_exams_export_csv_with_formula_sanitization(self):
        """CSV export sanitizes formulas starting with '=', '+', '-', '@' to prevent CSV injection (CWE-1236)."""
        url = f'/{self.slug}/api/exams/export/?format=csv'
        res = self.client.get(url, HTTP_AUTHORIZATION=f'Bearer {self.token}')
        self.assertEqual(res.status_code, 200)
        self.assertIn('text/csv', res['Content-Type'])
        self.assertIn('attachment;', res['Content-Disposition'])
        content = res.content.decode('utf-8')
        self.assertIn('Title,Subject,Department,Institution', content)
        # Verify formula cell was sanitized: '=2+5' should be escaped to "'=2+5"
        self.assertIn("'=2+5 Dangerous Formula Midterm", content)

    def test_exams_export_xlsx(self):
        """XLSX export generates a valid openxml spreadsheet byte stream."""
        url = f'/{self.slug}/api/exams/export/?format=xlsx'
        res = self.client.get(url, HTTP_AUTHORIZATION=f'Bearer {self.token}')
        self.assertEqual(res.status_code, 200)
        self.assertIn('spreadsheetml', res['Content-Type'])
        self.assertGreater(len(res.content), 100)


class SuperAdminEmailAndNotificationsModuleTests(TestCase):
    """
    Automated tests for Super Admin Email Status, test email command,
    and Outbound Email / Pop-Up notifications delivery.
    """

    def setUp(self):
        self.slug = 'a1b2c3d4e5f67890123456789abcdef0'
        settings.SUPER_ADMIN_PATH = self.slug
        self.sa_user = User.objects.create_superuser('email_sa', 'email_sa@example.com', 'SuperPass123!@#')
        self.profile = SuperAdminProfile.objects.create(
            user=self.sa_user,
            is_totp_enrolled=True,
            totp_secret='JBSWY3DPEHPK3PXP',
            active_session_id='sess_email_123',
            last_reauth_at=timezone.now(),
        )
        self.token = generate_super_admin_token(self.sa_user, session_id='sess_email_123')
        self.client = Client()

    def test_email_status_endpoint(self):
        """Email status endpoint returns active backend, provider info, and rate limits."""
        url = f'/{self.slug}/api/notifications/email-status/'
        res = self.client.get(url, HTTP_AUTHORIZATION=f'Bearer {self.token}')
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(body['status'], 'success')
        data = body['data']
        self.assertIn('backend', data)
        self.assertIn('is_configured', data)
        self.assertIn('daily_limit', data)
        self.assertIn('sent_today', data)
        self.assertIn('remaining_today', data)

    def test_test_email_management_command(self):
        """Test the test_email management command runs and outputs delivery summary."""
        out = StringIO()
        call_command('test_email', recipient='verify@example.com', stdout=out)
        output = out.getvalue()
        self.assertIn('successfully dispatched', output.lower())
        self.assertIn('verify@example.com', output)

    def test_send_test_email_endpoint(self):
        """Sending a test email via API requires Super Admin authentication and dispatches successfully."""
        url = f'/{self.slug}/api/notifications/send-test-email/'
        res = self.client.post(
            url,
            data={'to': 'testuser@example.com'},
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Bearer {self.token}',
        )
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(body['status'], 'success')
        self.assertIn('testuser@example.com', body['message'])


class NotificationPopupApiTests(TestCase):
    """
    Automated tests for first-time user pop-up notifications:
    - GET /api/notifications/popups/
    - POST /api/notifications/<id>/dismiss-popup/
    - POST /api/notifications/dismiss-all-popups/
    """

    def setUp(self):
        self.student_user = User.objects.create_user(
            username='popup_student',
            email='popup_student@example.com',
            password='StudentPass123!',
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.student_user)

        self.notif1 = Notification.objects.create(
            user=self.student_user,
            title='Campus Closure Notice',
            message='Severe weather alert: campus will be closed tomorrow.',
            type='warning',
            is_popup=True,
        )
        self.notif2 = Notification.objects.create(
            user=self.student_user,
            title='System Update Scheduled',
            message='Scheduled maintenance this Saturday at 2 AM.',
            type='info',
            is_popup=True,
        )

    def test_popup_workflow(self):
        """Verify fetching popups, timestamp marking, and dismissal."""
        # 1. Fetch pending popups
        res = self.client.get('/api/notifications/popups/')
        self.assertEqual(res.status_code, 200)
        data = res.json()['popups']
        self.assertEqual(len(data), 2)
        titles = [p['title'] for p in data]
        self.assertIn('Campus Closure Notice', titles)
        self.assertIn('System Update Scheduled', titles)

        # Verify popup_shown_at was set
        self.notif1.refresh_from_db()
        self.assertIsNotNone(self.notif1.popup_shown_at)

        # 2. Dismiss first popup
        dismiss_res = self.client.post(f'/api/notifications/{self.notif1.id}/dismiss-popup/')
        self.assertEqual(dismiss_res.status_code, 200)
        self.notif1.refresh_from_db()
        self.assertIsNotNone(self.notif1.popup_dismissed_at)

        # 3. Subsequent fetch only returns notif2
        res2 = self.client.get('/api/notifications/popups/')
        self.assertEqual(res2.status_code, 200)
        data2 = res2.json()['popups']
        self.assertEqual(len(data2), 1)
        self.assertEqual(data2[0]['id'], self.notif2.id)

        # 4. Dismiss all remaining
        dismiss_all_res = self.client.post('/api/notifications/dismiss-all-popups/')
        self.assertEqual(dismiss_all_res.status_code, 200)
        self.notif2.refresh_from_db()
        self.assertIsNotNone(self.notif2.popup_dismissed_at)

        # 5. Fetch now returns zero
        res3 = self.client.get('/api/notifications/popups/')
        self.assertEqual(res3.status_code, 200)
        self.assertEqual(len(res3.json()['popups']), 0)









import logging
from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import models
from django.utils import timezone

logger = logging.getLogger(__name__)


class SuperAdminProfile(models.Model):
    """
    Profile for platform super administrator.
    Strictly constrained to a hard maximum (default 1) accounts across the system.
    """
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='super_admin_profile',
    )
    totp_secret = models.CharField(max_length=255, blank=True, default='')
    is_totp_enrolled = models.BooleanField(default=False, db_index=True)
    recovery_codes_hash = models.JSONField(default=list, blank=True)
    last_totp_step = models.BigIntegerField(default=0, help_text='Tracks consumed RFC 6238 time step to prevent replay')
    active_session_id = models.CharField(max_length=64, blank=True, default='', help_text='Active session ID; cleared on logout to revoke JWTs')
    failed_login_attempts = models.PositiveIntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True, db_index=True)
    last_reauth_at = models.DateTimeField(null=True, blank=True)
    last_activity_at = models.DateTimeField(null=True, blank=True)
    last_login_ip = models.CharField(max_length=45, blank=True, default='')
    last_login_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Super Admin Profile'
        verbose_name_plural = 'Super Admin Profiles'

    def clean(self):
        super().clean()
        max_allowed = getattr(settings, 'MAX_SUPER_ADMIN_COUNT', 1)
        existing_count = SuperAdminProfile.objects.exclude(pk=self.pk).count()
        if existing_count >= max_allowed:
            raise ValidationError(
                f'System policy permits at most {max_allowed} Super Admin account(s).'
            )

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def is_locked(self) -> bool:
        """Check if account is temporarily locked due to failed attempts."""
        if not self.locked_until:
            return False
        return timezone.now() < self.locked_until

    def is_reauth_valid(self, max_age_seconds: int = 300) -> bool:
        """Check if user has successfully re-authenticated within recent window."""
        if not self.last_reauth_at:
            return False
        age = (timezone.now() - self.last_reauth_at).total_seconds()
        return age <= max_age_seconds

    def __str__(self):
        return f'SuperAdmin: {self.user.username}'


class SuperAdminAuditLog(models.Model):
    """
    Tamper-evident, immutable audit trail for all Super Admin operations.
    Updates and deletions are strictly blocked at model and database level.
    Each entry is linked cryptographically via SHA-256 HMAC hash chain.
    """
    id = models.BigAutoField(primary_key=True)
    actor_username = models.CharField(max_length=150, db_index=True)
    action = models.CharField(max_length=64, db_index=True)
    target_entity = models.CharField(max_length=64, blank=True, default='', db_index=True)
    target_id = models.CharField(max_length=64, blank=True, default='')
    description = models.TextField(blank=True, default='')
    before_state = models.JSONField(default=dict, blank=True)
    after_state = models.JSONField(default=dict, blank=True)
    ip_address = models.CharField(max_length=45, blank=True, default='')
    user_agent = models.CharField(max_length=255, blank=True, default='')
    prev_hash = models.CharField(max_length=64, blank=True, default='', db_index=True)
    entry_hash = models.CharField(max_length=64, blank=True, default='', db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = 'Super Admin Audit Log'
        verbose_name_plural = 'Super Admin Audit Logs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['actor_username', 'created_at']),
            models.Index(fields=['action', 'created_at']),
            models.Index(fields=['target_entity', 'target_id']),
            models.Index(fields=['prev_hash', 'entry_hash']),
        ]

    def save(self, *args, **kwargs):
        if self.pk:
            raise PermissionDenied('SuperAdminAuditLog records are immutable and cannot be updated.')
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise PermissionDenied('SuperAdminAuditLog records cannot be deleted.')

    def __str__(self):
        return f'[{self.created_at}] {self.actor_username} - {self.action}'


class SystemSetting(models.Model):
    """
    Centralized key-value platform configuration.
    Controls dynamic maintenance mode, rate limits, and default parameters.
    """
    key = models.CharField(max_length=64, unique=True, db_index=True)
    value = models.JSONField(default=dict)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.CharField(max_length=150, blank=True, default='')

    class Meta:
        verbose_name = 'System Setting'
        verbose_name_plural = 'System Settings'

    @classmethod
    def get_setting(cls, key: str, default=None):
        record = cls.objects.filter(key=key).first()
        if record:
            return record.value
        return default

    @classmethod
    def set_setting(cls, key: str, value, updated_by: str = ''):
        record, _ = cls.objects.update_or_create(
            key=key,
            defaults={'value': value, 'updated_by': updated_by},
        )
        return record

    def __str__(self):
        return f'Setting: {self.key}'


class DatabaseBackupRecord(models.Model):
    """
    Metadata registry for all platform backups.
    Tracks checksums, retention lifecycle, and scratch-database restore test results.
    """
    BACKUP_TYPE_CHOICES = [
        ('manual', 'Manual'),
        ('daily', 'Scheduled Daily'),
        ('weekly', 'Scheduled Weekly'),
    ]
    STATUS_CHOICES = [
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('restoring', 'Restoring'),
    ]
    RESTORE_TEST_CHOICES = [
        ('not_tested', 'Not Tested'),
        ('passed', 'Passed'),
        ('failed', 'Failed'),
    ]

    filename = models.CharField(max_length=255, unique=True, db_index=True)
    file_path = models.CharField(max_length=512)
    file_size_bytes = models.BigIntegerField(default=0)
    checksum_sha256 = models.CharField(max_length=64, blank=True, default='')
    backup_type = models.CharField(max_length=32, choices=BACKUP_TYPE_CHOICES, default='manual')
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default='completed')
    restore_test_status = models.CharField(max_length=32, choices=RESTORE_TEST_CHOICES, default='not_tested')
    restore_test_details = models.TextField(blank=True, default='')
    restore_test_at = models.DateTimeField(null=True, blank=True)
    created_by = models.CharField(max_length=150, default='system')
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = 'Database Backup Record'
        verbose_name_plural = 'Database Backup Records'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.filename} ({self.status})'


class AlertNotificationRecord(models.Model):
    """
    Record of sent security/operations alerts to enforce deduplication cooldowns.
    """
    alert_key = models.CharField(max_length=128, unique=True, db_index=True)
    severity = models.CharField(max_length=32, default='warning')
    subject = models.CharField(max_length=255)
    message = models.TextField()
    last_sent_at = models.DateTimeField(auto_now=True)
    sent_count = models.PositiveIntegerField(default=1)

    class Meta:
        verbose_name = 'Alert Notification Record'
        verbose_name_plural = 'Alert Notification Records'

    def __str__(self):
        return f'{self.alert_key} (sent {self.sent_count} times)'


class MaintenanceWindow(models.Model):
    """
    Platform-wide maintenance window configuration with bypass for super admin.
    """
    is_enabled = models.BooleanField(default=False)
    start_time = models.DateTimeField(null=True, blank=True)
    end_time = models.DateTimeField(null=True, blank=True)
    custom_message = models.TextField(
        default='System is temporarily undergoing scheduled maintenance. Please check back shortly.'
    )
    bypass_superadmin = models.BooleanField(default=True)
    updated_by = models.CharField(max_length=150, blank=True, default='')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Maintenance Window'
        verbose_name_plural = 'Maintenance Windows'

    @classmethod
    def is_currently_active(cls) -> tuple[bool, str]:
        record = cls.objects.first()
        if not record or not record.is_enabled:
            return False, ''
        now = timezone.now()
        if record.start_time and record.end_time:
            if record.start_time <= now <= record.end_time:
                return True, record.custom_message
            return False, ''
        if record.start_time and not record.end_time:
            if now >= record.start_time:
                return True, record.custom_message
            return False, ''
        return True, record.custom_message

    def __str__(self):
        return f'Maintenance Active: {self.is_enabled}'


class InstitutePolicy(models.Model):
    """
    Per-institute quotas, operational overrides, and custom policy settings.
    """
    institution = models.OneToOneField(
        'admins.AdminInstitution',
        on_delete=models.CASCADE,
        related_name='policy',
    )
    logo_path = models.CharField(max_length=512, blank=True, default='')
    timezone_name = models.CharField(max_length=64, default='Asia/Kolkata')
    academic_year = models.CharField(max_length=32, default='2025-2026')
    max_students = models.PositiveIntegerField(default=5000)
    max_faculty = models.PositiveIntegerField(default=200)
    max_ai_generations_per_month = models.PositiveIntegerField(default=500)
    used_ai_generations_this_month = models.PositiveIntegerField(default=0)
    max_storage_mb = models.PositiveIntegerField(default=10240)
    exam_window_buffer_minutes = models.PositiveIntegerField(default=15)
    violation_limit_override = models.PositiveIntegerField(default=3)
    faculty_can_publish_without_review = models.BooleanField(default=True)
    allowed_departments = models.JSONField(default=list, blank=True)
    feature_flags = models.JSONField(default=dict, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.CharField(max_length=150, blank=True, default='')

    class Meta:
        verbose_name = 'Institute Policy'
        verbose_name_plural = 'Institute Policies'

    def __str__(self):
        return f'Policy: {self.institution.institution_name}'


class SystemAnnouncement(models.Model):
    """
    Targeted system-wide or scoped announcements with HTML/XSS sanitization.
    """
    TARGET_TYPE_CHOICES = [
        ('all', 'All Institutes'),
        ('institute', 'Single Institute'),
        ('department', 'Specific Department'),
        ('role', 'Specific Role'),
    ]
    title = models.CharField(max_length=255)
    message = models.TextField()
    target_type = models.CharField(max_length=32, choices=TARGET_TYPE_CHOICES, default='all')
    target_institute = models.ForeignKey(
        'admins.AdminInstitution',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='announcements',
    )
    target_department = models.CharField(max_length=128, blank=True, default='')
    target_role = models.CharField(max_length=32, blank=True, default='')
    start_date = models.DateTimeField(default=timezone.now)
    end_date = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.CharField(max_length=150, default='system')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'System Announcement'
        verbose_name_plural = 'System Announcements'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.title} ({self.target_type})'


class DataSubjectRequest(models.Model):
    """
    DPDP-aligned user data management (Export, Anonymize, Delete).
    Enforces dry-run previews, immutable audit trail, and retention policies.
    """
    REQUEST_TYPE_CHOICES = [
        ('export', 'Export Data'),
        ('anonymize', 'Anonymize User'),
        ('delete', 'Delete User'),
    ]
    STATUS_CHOICES = [
        ('pending', 'Pending Review'),
        ('dry_run_ready', 'Dry Run Ready'),
        ('completed', 'Completed'),
        ('rejected', 'Rejected'),
    ]
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='dpdp_requests')
    user_email = models.EmailField(blank=True, default='')
    request_type = models.CharField(max_length=32, choices=REQUEST_TYPE_CHOICES)
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default='pending')
    reason = models.TextField(blank=True, default='')
    dry_run_summary = models.JSONField(default=dict, blank=True)
    executed_at = models.DateTimeField(null=True, blank=True)
    executed_by = models.CharField(max_length=150, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Data Subject Request'
        verbose_name_plural = 'Data Subject Requests'
        ordering = ['-created_at']

    def __str__(self):
        return f'DPDP {self.request_type} - {self.user_email or (self.user.username if self.user else "Unknown")}'


class AIModel(models.Model):
    """
    Registry of Ollama models available for exam generation, question answering, and platform AI.
    Super Admin can add (pull from Ollama library), enable, disable, set default, test, and delete.
    Changes apply immediately to paper generation without requiring code changes or redeployments.
    """
    STATUS_CHOICES = [
        ('ready', 'Ready'),
        ('pulling', 'Pulling'),
        ('failed', 'Failed'),
        ('offline', 'Offline'),
    ]

    name = models.CharField(max_length=120, unique=True, db_index=True, help_text='Ollama tag e.g. llama3.2:3b or phi3:mini')
    display_name = models.CharField(max_length=150, blank=True, default='')
    family = models.CharField(max_length=80, blank=True, default='')
    parameter_size = models.CharField(max_length=50, blank=True, default='')
    quantization_level = models.CharField(max_length=50, blank=True, default='')
    size_bytes = models.BigIntegerField(default=0)
    context_window = models.IntegerField(default=4096)
    is_enabled = models.BooleanField(default=True, db_index=True)
    is_default = models.BooleanField(default=False, db_index=True)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='ready')
    pull_progress_percent = models.IntegerField(default=100)
    pull_status_message = models.CharField(max_length=255, blank=True, default='')
    last_tested_at = models.DateTimeField(null=True, blank=True)
    last_test_latency_ms = models.IntegerField(null=True, blank=True)
    last_test_success = models.BooleanField(null=True, blank=True)
    last_test_error = models.TextField(blank=True, default='')
    notes = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'AI Model'
        verbose_name_plural = 'AI Models'
        ordering = ['-is_default', 'name']

    def __str__(self):
        return f"{self.name} ({'Enabled' if self.is_enabled else 'Disabled'})"


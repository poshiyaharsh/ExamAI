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
    failed_login_attempts = models.PositiveIntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True, db_index=True)
    last_reauth_at = models.DateTimeField(null=True, blank=True)
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
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = 'Super Admin Audit Log'
        verbose_name_plural = 'Super Admin Audit Logs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['actor_username', 'created_at']),
            models.Index(fields=['action', 'created_at']),
            models.Index(fields=['target_entity', 'target_id']),
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

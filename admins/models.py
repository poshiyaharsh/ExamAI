from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone


class AdminProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='admin_profile')
    is_seed = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Admin: {self.user.username}'


class AdminInstitution(models.Model):
    admin = models.OneToOneField(User, on_delete=models.CASCADE, related_name='admin_institution')
    institution_name = models.CharField(max_length=255)
    institution_code = models.CharField(max_length=13, unique=True, editable=False)
    short_code = models.CharField(max_length=30, blank=True, default='', db_index=True)
    institution_type = models.CharField(max_length=100, blank=True, default='')
    city = models.CharField(max_length=100, blank=True, default='')
    state = models.CharField(max_length=100, blank=True, default='')
    established_year = models.PositiveIntegerField(null=True, blank=True)
    website = models.CharField(max_length=255, blank=True, default='')
    address = models.CharField(max_length=500, blank=True, default='')
    phone = models.CharField(max_length=20, blank=True, default='')
    STATUS_ACTIVE = 'active'
    STATUS_SUSPENDED = 'suspended'
    STATUS_CHOICES = (
        (STATUS_ACTIVE, 'Active'),
        (STATUS_SUSPENDED, 'Suspended'),
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_ACTIVE, db_index=True)
    is_seed = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @staticmethod
    def build_next_institution_code():
        year = timezone.now().year
        prefix = f'INST-{year}-'
        latest_code = (
            AdminInstitution.objects.filter(institution_code__startswith=prefix)
            .order_by('-institution_code')
            .values_list('institution_code', flat=True)
            .first()
        )

        if latest_code:
            try:
                next_counter = int(latest_code.split('-')[-1]) + 1
            except (TypeError, ValueError):
                next_counter = 1
        else:
            next_counter = 1

        return f'{prefix}{next_counter:03d}'

    @classmethod
    def generate_unique_institution_code(cls):
        for _ in range(10):
            candidate = cls.build_next_institution_code()
            if not cls.objects.filter(institution_code=candidate).exists():
                return candidate
        raise ValueError('Unable to generate unique institution code. Please try again.')

    def save(self, *args, **kwargs):
        if not self.institution_code:
            self.institution_code = self.generate_unique_institution_code()
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.institution_name} ({self.institution_code})'


class AdminDepartment(models.Model):
    institution = models.ForeignKey(
        AdminInstitution,
        on_delete=models.CASCADE,
        related_name='departments',
    )
    department_name = models.CharField(max_length=120)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['institution', 'department_name'],
                name='unique_department_per_institution',
            )
        ]
        ordering = ['department_name']

    def __str__(self):
        return f'{self.department_name} ({self.institution.institution_code})'


class DepartmentChangeAuditLog(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='department_audit_logs',
    )
    institution = models.ForeignKey(
        AdminInstitution,
        on_delete=models.CASCADE,
        related_name='department_audit_logs',
        null=True,
        blank=True,
    )
    changed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='admin_dept_changes',
    )
    previous_department = models.CharField(max_length=120)
    new_department = models.CharField(max_length=120)
    reason = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f'{self.user.username}: {self.previous_department} -> {self.new_department}'


class AdminActionAuditLog(models.Model):
    ACTION_RESET_PASSWORD = 'reset_password'
    ACTION_DEACTIVATE = 'deactivate'
    ACTION_ACTIVATE = 'activate'
    ACTION_DELETE = 'delete'
    ACTION_CHOICES = (
        (ACTION_RESET_PASSWORD, 'Reset Password'),
        (ACTION_DEACTIVATE, 'Deactivate User'),
        (ACTION_ACTIVATE, 'Activate User'),
        (ACTION_DELETE, 'Delete User'),
    )
    admin = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='admin_actions_performed',
    )
    target_user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='admin_actions_received',
    )
    institution = models.ForeignKey(
        AdminInstitution,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='admin_action_audit_logs',
    )
    action = models.CharField(max_length=50, choices=ACTION_CHOICES, db_index=True)
    reason = models.TextField(blank=True, default='')
    details = models.JSONField(default=dict, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f'Admin {self.admin_id} performed {self.action} on user {self.target_user_id}'

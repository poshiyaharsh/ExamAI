from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone

from admins.models import AdminInstitution


class FacultyProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='faculty_profile')
    institution = models.ForeignKey(
        AdminInstitution,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='faculty_profiles',
    )
    employee_id = models.CharField(max_length=12, unique=True, blank=True, null=True)
    department = models.CharField(max_length=120, blank=True, default='')
    designation = models.CharField(max_length=120, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    @staticmethod
    def build_next_employee_id():
        year = timezone.now().year
        prefix = f'FAC-{year}-'
        latest_employee_id = (
            FacultyProfile.objects.filter(employee_id__startswith=prefix)
            .order_by('-employee_id')
            .values_list('employee_id', flat=True)
            .first()
        )

        if latest_employee_id:
            try:
                next_counter = int(latest_employee_id.split('-')[-1]) + 1
            except (TypeError, ValueError):
                next_counter = 1
        else:
            next_counter = 1

        return f'{prefix}{next_counter:03d}'

    def ensure_employee_id(self):
        if self.employee_id:
            return self.employee_id

        for _ in range(5):
            candidate = self.build_next_employee_id()
            if not FacultyProfile.objects.filter(employee_id=candidate).exists():
                self.employee_id = candidate
                self.save(update_fields=['employee_id'])
                return self.employee_id

        raise ValueError('Unable to allocate a unique employee ID. Please try again.')

    def __str__(self):
        return f'Faculty: {self.user.username}'

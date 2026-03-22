from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone

from admins.models import AdminInstitution


class StudentProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='student_profile')
    institution = models.ForeignKey(
        AdminInstitution,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='student_profiles',
    )
    student_id = models.CharField(max_length=13, unique=True, blank=True, null=True)
    department = models.CharField(max_length=120, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    @staticmethod
    def build_next_student_id():
        year = timezone.now().year
        prefix = f'STU-{year}-'
        latest_student_id = (
            StudentProfile.objects.filter(student_id__startswith=prefix)
            .order_by('-student_id')
            .values_list('student_id', flat=True)
            .first()
        )

        if latest_student_id:
            try:
                next_counter = int(latest_student_id.split('-')[-1]) + 1
            except (TypeError, ValueError):
                next_counter = 1
        else:
            next_counter = 1

        return f'{prefix}{next_counter:04d}'

    def ensure_student_id(self):
        if self.student_id:
            return self.student_id

        for _ in range(5):
            candidate = self.build_next_student_id()
            if not StudentProfile.objects.filter(student_id=candidate).exists():
                self.student_id = candidate
                self.save(update_fields=['student_id'])
                return self.student_id

        raise ValueError('Unable to allocate a unique student ID. Please try again.')

    def __str__(self):
        return f'Student: {self.user.username}'

from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone

from admins.models import AdminInstitution
from faculty.models import Paper


class StudentProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='student_profile')
    institution = models.ForeignKey(
        AdminInstitution,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='student_profiles',
    )
    student_id = models.CharField(max_length=13, blank=True, null=True)
    department = models.CharField(max_length=120, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['institution', 'student_id'],
                name='unique_institution_student_id',
            ),
        ]

    @staticmethod
    def build_next_student_id(institution=None):
        year = timezone.now().year
        prefix = f'STU-{year}-'
        qs = StudentProfile.objects.filter(student_id__startswith=prefix)
        if institution:
            qs = qs.filter(institution=institution)
        latest_student_id = (
            qs.order_by('-student_id')
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
            candidate = self.build_next_student_id(institution=self.institution)
            if not StudentProfile.objects.filter(institution=self.institution, student_id=candidate).exists():
                self.student_id = candidate
                self.save(update_fields=['student_id'])
                return self.student_id

    def clean(self):
        super().clean()
        if self.pk:
            orig_dept = StudentProfile.objects.filter(pk=self.pk).values_list('department', flat=True).first()
            if orig_dept and orig_dept.strip() not in ('', 'Unassigned', 'unassigned'):
                if self.department != orig_dept and not getattr(self, '_allow_department_change', False):
                    from django.core.exceptions import ValidationError
                    raise ValidationError({'department': 'Department is immutable once assigned. Contact admin to request a change.'})

    def save(self, *args, **kwargs):
        if self.pk:
            orig_dept = StudentProfile.objects.filter(pk=self.pk).values_list('department', flat=True).first()
            if orig_dept and orig_dept.strip() not in ('', 'Unassigned', 'unassigned'):
                if self.department != orig_dept and not getattr(self, '_allow_department_change', False):
                    from django.core.exceptions import ValidationError
                    raise ValidationError({'department': 'Department is immutable once assigned. Contact admin to request a change.'})
        super().save(*args, **kwargs)

    def __str__(self):
        return f'Student: {self.user.username}'


class ExamAttempt(models.Model):
    STATUS_STARTED = 'started'
    STATUS_SUBMITTED = 'submitted'
    STATUS_CHOICES = (
        (STATUS_STARTED, 'Started'),
        (STATUS_SUBMITTED, 'Submitted'),
    )

    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, related_name='exam_attempts')
    institution = models.ForeignKey(
        AdminInstitution,
        on_delete=models.CASCADE,
        related_name='legacy_exam_attempts',
        db_index=True,
    )
    paper = models.ForeignKey(Paper, on_delete=models.CASCADE, related_name='attempts')
    answers = models.JSONField(default=dict)
    score = models.PositiveIntegerField(default=0)
    max_score = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_STARTED)
    started_at = models.DateTimeField(auto_now_add=True)
    submitted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-started_at']
        indexes = [
            models.Index(fields=['student', 'paper', 'status']),
            models.Index(fields=['institution', 'student']),
            models.Index(fields=['institution', 'paper']),
        ]

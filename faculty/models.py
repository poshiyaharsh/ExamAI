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


def faculty_syllabus_upload_path(instance, filename):
    return f'syllabi/faculty_{instance.faculty_id}/{filename}'


class SyllabusUpload(models.Model):
    faculty = models.ForeignKey(FacultyProfile, on_delete=models.CASCADE, related_name='syllabus_uploads')
    institution = models.ForeignKey(AdminInstitution, on_delete=models.CASCADE, related_name='syllabus_uploads')
    original_file = models.FileField(upload_to=faculty_syllabus_upload_path)
    original_filename = models.CharField(max_length=255)
    content_type = models.CharField(max_length=120, blank=True, default='')
    extracted_text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.original_filename


class Paper(models.Model):
    faculty = models.ForeignKey(FacultyProfile, on_delete=models.CASCADE, related_name='papers')
    institution = models.ForeignKey(AdminInstitution, on_delete=models.CASCADE, related_name='papers')
    title = models.CharField(max_length=255)
    syllabus_file = models.FileField(upload_to=faculty_syllabus_upload_path)
    syllabus_filename = models.CharField(max_length=255)
    extracted_syllabus_text = models.TextField()
    ai_model = models.CharField(max_length=50)
    topics = models.JSONField(default=list)
    question_types = models.JSONField(default=list)
    difficulty_distribution = models.JSONField(default=dict)
    duration = models.PositiveIntegerField()
    total_marks = models.PositiveIntegerField()
    generated_questions = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title


class PaperQuestion(models.Model):
    paper = models.ForeignKey(Paper, on_delete=models.CASCADE, related_name='questions')
    question_number = models.PositiveIntegerField()
    question_type = models.CharField(max_length=40)
    difficulty = models.CharField(max_length=20)
    marks = models.PositiveIntegerField()
    question = models.TextField()
    options = models.JSONField(default=list, blank=True)
    answer = models.TextField(blank=True, default='')

    class Meta:
        ordering = ['question_number']
        unique_together = ('paper', 'question_number')

    def __str__(self):
        return f'{self.paper_id} Q{self.question_number}'

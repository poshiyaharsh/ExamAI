from django.db import models
from django.utils import timezone


class GenerationJob(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        RUNNING = 'running', 'Running'
        COMPLETED = 'completed', 'Completed'
        FAILED = 'failed', 'Failed'
        CANCELLED = 'cancelled', 'Cancelled'

    faculty = models.ForeignKey(
        'faculty.FacultyProfile',
        on_delete=models.CASCADE,
        related_name='ai_generation_jobs',
        db_index=True,
    )
    institution = models.ForeignKey(
        'admins.AdminInstitution',
        on_delete=models.CASCADE,
        related_name='ai_generation_jobs',
        db_index=True,
    )
    title = models.CharField(max_length=255)
    subject = models.CharField(max_length=255)
    class_semester = models.CharField(max_length=120, blank=True, default='')
    exam_type = models.CharField(max_length=120, blank=True, default='Final Examination')

    total_marks = models.PositiveIntegerField(default=50)
    allocated_marks = models.PositiveIntegerField(default=0)
    duration = models.PositiveIntegerField(default=60)  # minutes

    blueprint = models.JSONField(default=list)
    status = models.CharField(
        max_length=30,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    progress_percent = models.PositiveIntegerField(default=0)
    progress_message = models.CharField(max_length=255, default='Job created')
    current_slot_index = models.PositiveIntegerField(default=0)

    generated_questions = models.JSONField(default=list)
    model_assignments = models.JSONField(default=dict)
    rag_sources = models.JSONField(default=list)
    summary = models.JSONField(default=dict)

    error_message = models.TextField(blank=True, default='')
    saved_paper_id = models.PositiveIntegerField(null=True, blank=True)
    saved_exam_id = models.PositiveIntegerField(null=True, blank=True)
    language = models.CharField(max_length=20, blank=True, default="en", help_text="Detected ISO language code for generated paper")

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['institution', 'faculty', 'status']),
        ]

    def __str__(self):
        return f"Job #{self.id} - {self.title} ({self.status})"


class GenerationLog(models.Model):
    job = models.ForeignKey(
        GenerationJob,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='logs',
        db_index=True,
    )
    faculty = models.ForeignKey(
        'faculty.FacultyProfile',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ai_generation_logs',
        db_index=True,
    )
    institution = models.ForeignKey(
        'admins.AdminInstitution',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ai_generation_logs',
        db_index=True,
    )
    level = models.CharField(max_length=20, default='INFO', db_index=True)
    category = models.CharField(max_length=50, default='GENERATION', db_index=True)
    slot_number = models.PositiveIntegerField(null=True, blank=True)
    model_name = models.CharField(max_length=120, blank=True, default='')
    message = models.TextField()
    details = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['job', 'level']),
            models.Index(fields=['institution', 'created_at']),
        ]

    def __str__(self):
        return f"[{self.level}] [{self.category}] Job {self.job_id}: {self.message[:60]}"


class PaperDraft(models.Model):
    """
    Persists faculty wizard paper drafts across devices and sessions.
    """
    faculty = models.OneToOneField(
        'faculty.FacultyProfile',
        on_delete=models.CASCADE,
        related_name='ai_paper_draft',
        db_index=True,
    )
    draft_data = models.JSONField(default=dict)
    version = models.PositiveIntegerField(default=1)
    updated_at = models.DateTimeField(auto_now=True, db_index=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return f"Draft for {self.faculty} (v{self.version})"

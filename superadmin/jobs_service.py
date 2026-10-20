import logging
from datetime import timedelta
from django.utils import timezone

from api.models import PaperGenerationJob, StudentAttempt
from superadmin.models import DatabaseBackupRecord

logger = logging.getLogger(__name__)


def get_jobs_summary() -> dict:
    """Return high-level summary of background jobs across platform."""
    now = timezone.now()
    cutoff_15m = now - timedelta(minutes=15)
    cutoff_24h = now - timedelta(hours=24)

    total_24h = PaperGenerationJob.objects.filter(created_at__gte=cutoff_24h).count()
    completed_24h = PaperGenerationJob.objects.filter(
        status__in=[PaperGenerationJob.Status.COMPLETED, PaperGenerationJob.Status.COMPLETED_WITH_WARNINGS],
        created_at__gte=cutoff_24h,
    ).count()
    failed_24h = PaperGenerationJob.objects.filter(
        status=PaperGenerationJob.Status.FAILED,
        created_at__gte=cutoff_24h,
    ).count()

    active_jobs = PaperGenerationJob.objects.filter(
        status__in=[PaperGenerationJob.Status.QUEUED, PaperGenerationJob.Status.RUNNING],
    ).count()

    stuck_jobs = PaperGenerationJob.objects.filter(
        status__in=[PaperGenerationJob.Status.QUEUED, PaperGenerationJob.Status.RUNNING],
        created_at__lt=cutoff_15m,
    ).count()

    success_rate = round((completed_24h / total_24h * 100), 1) if total_24h > 0 else 100.0

    return {
        'total_24h': total_24h,
        'completed_24h': completed_24h,
        'failed_24h': failed_24h,
        'active_jobs': active_jobs,
        'stuck_jobs': stuck_jobs,
        'success_rate_percent': success_rate,
    }


def list_background_jobs(status_filter: str = None, limit: int = 50) -> list[dict]:
    """List recent paper generation jobs with execution duration, institution, and status."""
    qs = PaperGenerationJob.objects.select_related('institution', 'faculty').all()
    if status_filter:
        qs = qs.filter(status=status_filter)

    jobs = []
    for job in qs[:limit]:
        duration_sec = None
        if job.started_at:
            end_t = job.completed_at or timezone.now()
            duration_sec = round((end_t - job.started_at).total_seconds(), 1)

        is_stuck = False
        if job.status in [PaperGenerationJob.Status.QUEUED, PaperGenerationJob.Status.RUNNING]:
            age = (timezone.now() - job.created_at).total_seconds()
            if age > 900:  # 15 minutes
                is_stuck = True

        jobs.append({
            'id': job.id,
            'institution_name': job.institution.institution_name if job.institution else 'N/A',
            'faculty_username': job.faculty.username if job.faculty else 'N/A',
            'department': job.department,
            'model': job.model,
            'status': job.status,
            'progress': job.progress,
            'current_step': job.current_step,
            'error_message': job.error_message,
            'question_count_generated': job.question_count_generated,
            'target_marks': job.target_marks,
            'actual_marks': job.actual_marks,
            'duration_seconds': duration_sec,
            'is_stuck': is_stuck,
            'created_at': job.created_at.isoformat() if job.created_at else None,
            'started_at': job.started_at.isoformat() if job.started_at else None,
            'completed_at': job.completed_at.isoformat() if job.completed_at else None,
        })

    return jobs


def detect_and_cleanup_stuck_jobs(threshold_minutes: int = 15, auto_fail: bool = False) -> list[int]:
    """
    Detect jobs that have been running or queued for longer than threshold_minutes.
    If auto_fail is True, mark them as FAILED with an explanatory error message.
    Returns list of stuck job IDs.
    """
    cutoff = timezone.now() - timedelta(minutes=threshold_minutes)
    stuck_qs = PaperGenerationJob.objects.filter(
        status__in=[PaperGenerationJob.Status.QUEUED, PaperGenerationJob.Status.RUNNING],
        created_at__lt=cutoff,
    )
    stuck_ids = list(stuck_qs.values_list('id', flat=True))

    if auto_fail and stuck_ids:
        stuck_qs.update(
            status=PaperGenerationJob.Status.FAILED,
            error_message=f'Job timed out and marked as failed by Stuck-Job Detector after {threshold_minutes} minutes of inactivity.',
            completed_at=timezone.now(),
        )
        logger.warning('Stuck-Job Detector automatically failed %d jobs: %s', len(stuck_ids), stuck_ids)

    return stuck_ids


def retry_paper_generation_job(job_id: int) -> dict:
    """Reset a failed or cancelled generation job back to QUEUED."""
    try:
        job = PaperGenerationJob.objects.get(pk=job_id)
        if job.status not in [PaperGenerationJob.Status.FAILED, PaperGenerationJob.Status.CANCELLED]:
            return {'success': False, 'message': f'Cannot retry job with status "{job.status}".'}

        job.status = PaperGenerationJob.Status.QUEUED
        job.progress = 0
        job.current_step = 'Queued for retry by Super Admin'
        job.error_message = ''
        job.started_at = None
        job.completed_at = None
        job.is_cancelled = False
        job.save()

        return {'success': True, 'message': f'Job #{job_id} reset to queued for processing.'}
    except PaperGenerationJob.DoesNotExist:
        return {'success': False, 'message': 'Job not found.'}


def cancel_paper_generation_job(job_id: int) -> dict:
    """Cancel an active or queued generation job."""
    try:
        job = PaperGenerationJob.objects.get(pk=job_id)
        if job.status in [PaperGenerationJob.Status.COMPLETED, PaperGenerationJob.Status.COMPLETED_WITH_WARNINGS]:
            return {'success': False, 'message': 'Cannot cancel already completed job.'}

        job.status = PaperGenerationJob.Status.CANCELLED
        job.is_cancelled = True
        job.current_step = 'Cancelled by Super Admin'
        job.error_message = 'Job was manually cancelled by Super Admin.'
        job.completed_at = timezone.now()
        job.save()

        return {'success': True, 'message': f'Job #{job_id} successfully cancelled.'}
    except PaperGenerationJob.DoesNotExist:
        return {'success': False, 'message': 'Job not found.'}

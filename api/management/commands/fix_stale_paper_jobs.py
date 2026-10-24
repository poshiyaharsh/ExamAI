from datetime import timedelta
import logging
from django.core.management.base import BaseCommand
from django.utils import timezone

from api.models import Exam, PaperGenerationJob
from api.utils.evaluation_config import PAPER_JOB_MAX_SECONDS

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Identifies and cleans up stale paper generation jobs stuck in queued or running states.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            default=False,
            help='Report stale jobs without modifying database records.',
        )
        parser.add_argument(
            '--apply',
            action='store_true',
            default=False,
            help='Apply updates to mark stale jobs appropriately.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        apply_changes = options['apply']

        if not dry_run and not apply_changes:
            self.stdout.write(self.style.WARNING('Neither --dry-run nor --apply specified. Defaulting to --dry-run.'))
            dry_run = True

        now = timezone.now()
        active_jobs = PaperGenerationJob.objects.filter(
            status__in=[PaperGenerationJob.Status.QUEUED, PaperGenerationJob.Status.RUNNING]
        ).select_related('exam')

        stale_jobs = []
        for job in active_jobs:
            req_count = job.question_count_requested or 10
            scaled_timeout = min(PAPER_JOB_MAX_SECONDS, max(300, req_count * 90))
            ref_time = job.started_at or job.created_at
            elapsed = (now - ref_time).total_seconds() if ref_time else 0
            if elapsed > scaled_timeout:
                stale_jobs.append((job, int(elapsed), int(scaled_timeout)))

        self.stdout.write(f'Found {len(stale_jobs)} stale generation job(s) out of {active_jobs.count()} active job(s).')

        for job, elapsed, timeout in stale_jobs:
            exam = job.exam
            q_count = exam.questions.filter(is_deleted=False).count() if exam else 0
            action_desc = f'Preserve {q_count} questions -> COMPLETED_WITH_WARNINGS' if q_count > 0 else 'Mark as FAILED'

            self.stdout.write(
                f'Job #{job.id} (status={job.status}, model={job.model}, elapsed={elapsed}s, timeout={timeout}s, '
                f'exam_id={job.exam_id}, questions={q_count}) -> {action_desc}'
            )

            if apply_changes:
                if q_count > 0:
                    questions = exam.questions.filter(is_deleted=False)
                    actual_marks = sum(float(q.marks) for q in questions)
                    target = job.target_marks or (exam.target_total_marks if exam else actual_marks)
                    shortfall = max(0, int(target - actual_marks))
                    job.status = PaperGenerationJob.Status.COMPLETED_WITH_WARNINGS
                    job.current_step = 'Cleaned up: preserved partial questions after timeout'
                    job.warnings = (job.warnings or []) + [
                        f'Stale job recovered. {q_count} questions ({int(actual_marks)}/{int(target)} marks) preserved.'
                    ]
                    job.actual_marks = int(actual_marks)
                    job.marks_shortfall = shortfall
                    job.question_count_generated = q_count
                    job.completed_at = now
                    job.save(update_fields=[
                        'status', 'current_step', 'warnings', 'actual_marks',
                        'marks_shortfall', 'question_count_generated', 'completed_at'
                    ])
                    if exam:
                        exam.status = Exam.Status.DRAFT
                        exam.total_marks = int(actual_marks)
                        exam.marks_shortfall = shortfall
                        exam.save(update_fields=['status', 'total_marks', 'marks_shortfall'])
                else:
                    job.status = PaperGenerationJob.Status.FAILED
                    job.error_message = f'Generation timed out after {timeout // 60} minutes.'
                    job.completed_at = now
                    job.save(update_fields=['status', 'error_message', 'completed_at'])
                    if exam and exam.status == Exam.Status.GENERATING:
                        exam.status = Exam.Status.FAILED
                        exam.error_message = job.error_message
                        exam.save(update_fields=['status', 'error_message'])

        if apply_changes:
            self.stdout.write(self.style.SUCCESS(f'Successfully updated {len(stale_jobs)} stale job(s).'))
        else:
            self.stdout.write(self.style.SUCCESS('Dry run completed. No changes written to database.'))

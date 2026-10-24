from django.apps import AppConfig
from django.db.backends.signals import connection_created


def configure_sqlite_connection(sender, connection, **kwargs):
    if connection.vendor == 'sqlite':
        try:
            with connection.cursor() as cursor:
                cursor.execute('PRAGMA journal_mode=WAL;')
                cursor.execute('PRAGMA synchronous=NORMAL;')
                cursor.execute('PRAGMA busy_timeout=20000;')
        except Exception:
            pass


def cleanup_stuck_generation_jobs(**kwargs):
    try:
        from api.models import PaperGenerationJob, Exam
        from django.utils import timezone
        now = timezone.now()
        stuck_jobs = PaperGenerationJob.objects.filter(
            status__in=[PaperGenerationJob.Status.QUEUED, PaperGenerationJob.Status.RUNNING]
        ).select_related('exam')
        for job in stuck_jobs:
            exam = job.exam
            q_count = exam.questions.filter(is_deleted=False).count() if exam else 0
            if q_count > 0:
                questions = exam.questions.filter(is_deleted=False)
                actual_marks = sum(float(q.marks) for q in questions)
                target = job.target_marks or (exam.target_total_marks if exam else actual_marks)
                shortfall = max(0, int(target - actual_marks))
                job.status = PaperGenerationJob.Status.COMPLETED_WITH_WARNINGS
                job.current_step = 'Cleaned up: preserved partial questions after server restart'
                job.warnings = (job.warnings or []) + [
                    f'Stale job recovered on server restart. {q_count} questions ({int(actual_marks)}/{int(target)} marks) preserved.'
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
                job.error_message = 'Generation interrupted due to server restart.'
                job.completed_at = now
                job.save(update_fields=['status', 'error_message', 'completed_at'])
                if exam and exam.status == Exam.Status.GENERATING:
                    exam.status = Exam.Status.FAILED
                    exam.error_message = 'Generation interrupted due to server restart.'
                    exam.save(update_fields=['status', 'error_message'])
    except Exception:
        pass


class ApiConfig(AppConfig):
    name = 'api'

    def ready(self):
        from django.db.models.signals import post_migrate
        connection_created.connect(configure_sqlite_connection)
        post_migrate.connect(cleanup_stuck_generation_jobs, sender=self)

        from api.utils.schedule import start_schedule_cleaner_daemon
        start_schedule_cleaner_daemon()

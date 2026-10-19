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
        )
        for job in stuck_jobs:
            job.status = PaperGenerationJob.Status.FAILED
            job.error_message = 'Generation interrupted due to server restart.'
            job.completed_at = now
            job.save(update_fields=['status', 'error_message', 'completed_at'])
            if job.exam and job.exam.status == Exam.Status.GENERATING:
                job.exam.status = Exam.Status.FAILED
                job.exam.error_message = 'Generation interrupted due to server restart.'
                job.exam.save(update_fields=['status', 'error_message'])
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

import logging
from django.core.management.base import BaseCommand
from superadmin.jobs_service import detect_and_cleanup_stuck_jobs
from superadmin.monitoring import send_deduplicated_alert

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Scans for paper generation jobs stuck in queued or running state (>15 min) and cleans them up.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--timeout',
            type=int,
            default=15,
            help='Inactivity threshold in minutes (default 15)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Only report stuck jobs without failing them',
        )

    def handle(self, *args, **options):
        timeout = options['timeout']
        dry_run = options['dry_run']

        stuck_ids = detect_and_cleanup_stuck_jobs(threshold_minutes=timeout, auto_fail=not dry_run)

        if not stuck_ids:
            self.stdout.write(self.style.SUCCESS('No stuck background jobs detected.'))
            return

        if dry_run:
            self.stdout.write(self.style.WARNING(f'Detected {len(stuck_ids)} stuck job(s): {stuck_ids} (dry-run mode).'))
        else:
            self.stdout.write(self.style.NOTICE(f'Cleaned up {len(stuck_ids)} stuck job(s): {stuck_ids}.'))
            send_deduplicated_alert(
                alert_key='stuck_jobs_detected',
                subject=f'Stuck Background Jobs Cleaned Up ({len(stuck_ids)} jobs)',
                message=f'The Stuck-Job Detector identified and automatically failed {len(stuck_ids)} job(s) pending for > {timeout} minutes:\nJob IDs: {stuck_ids}',
                severity='warning',
            )

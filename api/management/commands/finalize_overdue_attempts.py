"""
Management command to finalize all overdue student exam attempts.
Can be executed manually or scheduled via Windows Task Scheduler or Cron.
Usage:
    python manage.py finalize_overdue_attempts [--batch-size 100]
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from api.utils.schedule import finalize_overdue_attempts


class Command(BaseCommand):
    help = 'Auto-submits and grades all in-progress student attempts that have exceeded their personal deadline or the exam window.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--batch-size',
            type=int,
            default=100,
            help='Maximum number of attempts to finalize in a single run (default: 100)',
        )

    def handle(self, *args, **options):
        batch_size = options.get('batch_size', 100)
        now = timezone.now()
        self.stdout.write(f"[{now.isoformat()}] Scanning for overdue in-progress student attempts...")

        count = finalize_overdue_attempts(batch_size=batch_size, now=now)
        if count > 0:
            self.stdout.write(self.style.SUCCESS(f"Successfully finalized and graded {count} overdue attempt(s)."))
        else:
            self.stdout.write(self.style.SUCCESS("No overdue in-progress attempts found."))

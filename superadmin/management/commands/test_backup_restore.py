import logging
from django.core.management.base import BaseCommand
from superadmin.backups import test_restore_backup
from superadmin.models import DatabaseBackupRecord

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Tests restoring a database backup into a temporary scratch schema and verifies table counts.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--backup-id',
            type=int,
            default=None,
            help='ID of DatabaseBackupRecord to test. If omitted, tests the latest completed backup.',
        )

    def handle(self, *args, **options):
        backup_id = options.get('backup_id')

        if not backup_id:
            latest = DatabaseBackupRecord.objects.filter(status='completed').order_by('-created_at').first()
            if not latest:
                self.stdout.write(self.style.ERROR('No completed backup records found to test.'))
                return
            backup_id = latest.id

        self.stdout.write(self.style.NOTICE(f'Testing restore of backup ID #{backup_id}...'))
        res = test_restore_backup(backup_id)

        if res['success']:
            self.stdout.write(self.style.SUCCESS(f'Restore test PASSED: {res["message"]}'))
        else:
            self.stdout.write(self.style.ERROR(f'Restore test FAILED: {res["message"]}'))

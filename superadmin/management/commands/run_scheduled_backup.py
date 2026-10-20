import logging
from django.core.management.base import BaseCommand
from superadmin.backups import create_database_backup, prune_backups, test_restore_backup
from superadmin.monitoring import send_deduplicated_alert

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Executes a scheduled database backup with SHA-256 checksum, scratch restore test, and retention pruning.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--type',
            type=str,
            default='daily',
            choices=['daily', 'weekly', 'manual'],
            help='Backup frequency category for retention rules',
        )
        parser.add_argument(
            '--no-test',
            action='store_true',
            help='Skip scratch restore verification',
        )

    def handle(self, *args, **options):
        backup_type = options['type']
        skip_test = options['no_test']

        self.stdout.write(self.style.NOTICE(f'Starting scheduled {backup_type} database backup...'))

        try:
            record = create_database_backup(backup_type=backup_type, created_by='scheduler')
            self.stdout.write(
                self.style.SUCCESS(
                    f'Backup created successfully: {record.filename} '
                    f'({round(record.file_size_bytes / (1024*1024), 2)} MB) '
                    f'[SHA256: {record.checksum_sha256[:16]}...]'
                )
            )

            # Retention pruning
            pruned = prune_backups()
            if pruned:
                self.stdout.write(self.style.NOTICE(f'Pruned {pruned} expired backup(s).'))

            # Scratch restore test
            if not skip_test:
                self.stdout.write(self.style.NOTICE('Running scratch restore test...'))
                test_result = test_restore_backup(record.id)
                if test_result['success']:
                    self.stdout.write(self.style.SUCCESS(f'Restore test PASSED: {test_result["message"]}'))
                else:
                    self.stdout.write(self.style.ERROR(f'Restore test FAILED: {test_result["message"]}'))
                    send_deduplicated_alert(
                        alert_key='backup_restore_test_failed',
                        subject=f'Backup Scratch Restore Test FAILED: {record.filename}',
                        message=f'The scratch restore test for backup {record.filename} failed:\n{test_result["message"]}',
                        severity='critical',
                    )

        except Exception as exc:
            logger.critical('Scheduled backup command failed: %s', exc)
            self.stdout.write(self.style.ERROR(f'Scheduled backup FAILED: {exc}'))
            send_deduplicated_alert(
                alert_key='database_backup_failed',
                subject='Database Backup Execution FAILED',
                message=f'Scheduled database backup failed with error:\n{str(exc)}',
                severity='critical',
            )
            raise exc

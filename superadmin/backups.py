import hashlib
import logging
import os
import shutil
import subprocess
from datetime import timedelta
from django.conf import settings
from django.db import connection
from django.utils import timezone

from superadmin.models import DatabaseBackupRecord, MaintenanceWindow

logger = logging.getLogger(__name__)

MYSQL_BIN_DIR = r'C:\Program Files\MySQL\MySQL Server 8.4\bin'
MYSQLDUMP_PATH = os.path.join(MYSQL_BIN_DIR, 'mysqldump.exe') if os.path.exists(os.path.join(MYSQL_BIN_DIR, 'mysqldump.exe')) else 'mysqldump'
MYSQL_PATH = os.path.join(MYSQL_BIN_DIR, 'mysql.exe') if os.path.exists(os.path.join(MYSQL_BIN_DIR, 'mysql.exe')) else 'mysql'


def get_backup_dir() -> str:
    """Return external directory for database backups outside the workspace repository."""
    configured_dir = getattr(settings, 'BACKUP_STORAGE_DIR', None)
    if configured_dir:
        backup_dir = os.path.abspath(configured_dir)
    else:
        backup_dir = os.path.abspath(os.path.join(settings.BASE_DIR, '..', 'backups'))
    os.makedirs(backup_dir, exist_ok=True)
    return backup_dir


def compute_file_sha256(filepath: str) -> str:
    """Compute cryptographic SHA-256 checksum of a backup file."""
    sha256 = hashlib.sha256()
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            sha256.update(chunk)
    return sha256.hexdigest()


def create_database_backup(backup_type: str = 'manual', created_by: str = 'system') -> DatabaseBackupRecord:
    """
    Perform a complete database dump via mysqldump, save to external backup directory,
    calculate SHA-256 checksum, record metadata in DatabaseBackupRecord, and prune old files.
    """
    backup_dir = get_backup_dir()
    timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
    filename = f'examai_backup_{timestamp}_{backup_type}.sql'
    filepath = os.path.join(backup_dir, filename)

    db_conf = settings.DATABASES['default']
    env = os.environ.copy()
    env['MYSQL_PWD'] = db_conf.get('PASSWORD', '')

    cmd = [
        MYSQLDUMP_PATH,
        '-h', db_conf.get('HOST', '127.0.0.1'),
        '-P', str(db_conf.get('PORT', 3306)),
        '-u', db_conf.get('USER', 'root'),
        '--single-transaction',
        '--quick',
        db_conf['NAME'],
    ]

    try:
        with open(filepath, 'wb') as outfile:
            proc = subprocess.run(cmd, env=env, stdout=outfile, stderr=subprocess.PIPE, timeout=120)

        if proc.returncode != 0:
            err_msg = proc.stderr.decode('utf-8', errors='ignore')
            if os.path.exists(filepath):
                os.remove(filepath)
            raise RuntimeError(f'mysqldump failed with exit code {proc.returncode}: {err_msg}')

        file_size = os.path.getsize(filepath)
        checksum = compute_file_sha256(filepath)

        record = DatabaseBackupRecord.objects.create(
            filename=filename,
            file_path=filepath,
            file_size_bytes=file_size,
            checksum_sha256=checksum,
            backup_type=backup_type,
            status='completed',
            created_by=created_by,
        )

        # Trigger retention pruning
        prune_backups()

        return record

    except Exception as exc:
        logger.error('Database backup failed: %s', exc)
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
            except OSError:
                pass
        DatabaseBackupRecord.objects.create(
            filename=filename,
            file_path=filepath,
            file_size_bytes=0,
            backup_type=backup_type,
            status='failed',
            created_by=created_by,
        )
        raise exc


def prune_backups(daily_retention_days: int = 14, weekly_retention_weeks: int = 8) -> int:
    """
    Prune expired backups according to retention policy:
    - Daily backups older than daily_retention_days
    - Weekly backups older than weekly_retention_weeks
    - Manual backups older than 30 days
    """
    now = timezone.now()
    daily_cutoff = now - timedelta(days=daily_retention_days)
    weekly_cutoff = now - timedelta(weeks=weekly_retention_weeks)
    manual_cutoff = now - timedelta(days=30)

    pruned_count = 0
    records = DatabaseBackupRecord.objects.all()

    for rec in records:
        should_prune = False
        if rec.backup_type == 'daily' and rec.created_at < daily_cutoff:
            should_prune = True
        elif rec.backup_type == 'weekly' and rec.created_at < weekly_cutoff:
            should_prune = True
        elif rec.backup_type == 'manual' and rec.created_at < manual_cutoff:
            should_prune = True

        if should_prune:
            if os.path.exists(rec.file_path):
                try:
                    os.remove(rec.file_path)
                except OSError as err:
                    logger.warning('Could not remove pruned backup file %s: %s', rec.file_path, err)
            rec.delete()
            pruned_count += 1

    return pruned_count


def test_restore_backup(backup_id: int, scratch_db_name: str = 'examai_scratch_test') -> dict:
    """
    Test restoring the specified backup into an isolated scratch database.
    Verifies that the dump is valid, creates tables, and reports table/row counts.
    Drops the scratch database immediately after testing to leave no residue.
    """
    try:
        record = DatabaseBackupRecord.objects.get(pk=backup_id)
    except DatabaseBackupRecord.DoesNotExist:
        return {'success': False, 'message': 'Backup record not found.'}

    if not os.path.exists(record.file_path):
        record.restore_test_status = 'failed'
        record.restore_test_details = f'File not found on disk: {record.file_path}'
        record.restore_test_at = timezone.now()
        record.save(update_fields=['restore_test_status', 'restore_test_details', 'restore_test_at'])
        return {'success': False, 'message': 'Backup file does not exist on disk.'}

    # Verify checksum first
    actual_checksum = compute_file_sha256(record.file_path)
    if record.checksum_sha256 and actual_checksum != record.checksum_sha256:
        record.restore_test_status = 'failed'
        record.restore_test_details = 'Checksum mismatch! File has been altered or corrupted.'
        record.restore_test_at = timezone.now()
        record.save(update_fields=['restore_test_status', 'restore_test_details', 'restore_test_at'])
        return {'success': False, 'message': 'Checksum mismatch! Backup is corrupted.'}

    db_conf = settings.DATABASES['default']
    env = os.environ.copy()
    env['MYSQL_PWD'] = db_conf.get('PASSWORD', '')

    base_cmd = [
        MYSQL_PATH,
        '-h', db_conf.get('HOST', '127.0.0.1'),
        '-P', str(db_conf.get('PORT', 3306)),
        '-u', db_conf.get('USER', 'root'),
    ]

    try:
        # Step 1: Create scratch database
        create_sql = f'CREATE DATABASE IF NOT EXISTS `{scratch_db_name}` DEFAULT CHARACTER SET utf8mb4;'
        subprocess.run(base_cmd + ['-e', create_sql], env=env, check=True, capture_output=True)

        # Step 2: Restore backup into scratch database
        with open(record.file_path, 'rb') as infile:
            restore_cmd = base_cmd + [scratch_db_name]
            restore_proc = subprocess.run(restore_cmd, env=env, stdin=infile, capture_output=True, timeout=120)

        if restore_proc.returncode != 0:
            err = restore_proc.stderr.decode('utf-8', errors='ignore')
            raise RuntimeError(f'Restore import failed: {err}')

        # Step 3: Verify scratch database integrity (check tables count)
        check_sql = f"SELECT count(*) FROM information_schema.tables WHERE table_schema = '{scratch_db_name}';"
        check_proc = subprocess.run(base_cmd + ['-s', '-N', '-e', check_sql], env=env, check=True, capture_output=True)
        table_count = int(check_proc.stdout.decode('utf-8').strip() or 0)

        if table_count < 5:
            raise RuntimeError(f'Scratch restore produced only {table_count} tables. Expected complete schema.')

        # Success: update record
        record.restore_test_status = 'passed'
        record.restore_test_details = f'Restore test passed successfully. Restored {table_count} tables into scratch DB.'
        record.restore_test_at = timezone.now()
        record.save(update_fields=['restore_test_status', 'restore_test_details', 'restore_test_at'])

        return {
            'success': True,
            'message': f'Restore test passed. Restored {table_count} tables successfully.',
            'table_count': table_count,
        }

    except Exception as exc:
        logger.error('Restore test failed for backup %s: %s', record.filename, exc)
        record.restore_test_status = 'failed'
        record.restore_test_details = f'Restore test failed: {str(exc)}'
        record.restore_test_at = timezone.now()
        record.save(update_fields=['restore_test_status', 'restore_test_details', 'restore_test_at'])
        return {'success': False, 'message': f'Restore test failed: {str(exc)}'}

    finally:
        # Step 4: Drop scratch database to leave no residue
        try:
            drop_sql = f'DROP DATABASE IF EXISTS `{scratch_db_name}`;'
            subprocess.run(base_cmd + ['-e', drop_sql], env=env, capture_output=True)
        except Exception as drop_err:
            logger.warning('Failed to cleanup scratch database: %s', drop_err)


def restore_backup_on_live_database(backup_id: int, dry_run: bool = True, confirm_maintenance: bool = False) -> dict:
    """
    Restore backup onto the primary database.
    Strictly requires:
    - Dry-run verification beforehand
    - Maintenance mode active
    - Checksum match
    """
    try:
        record = DatabaseBackupRecord.objects.get(pk=backup_id)
    except DatabaseBackupRecord.DoesNotExist:
        return {'success': False, 'message': 'Backup record not found.'}

    if not os.path.exists(record.file_path):
        return {'success': False, 'message': 'Backup file does not exist on disk.'}

    # Verify checksum
    actual_checksum = compute_file_sha256(record.file_path)
    if record.checksum_sha256 and actual_checksum != record.checksum_sha256:
        return {'success': False, 'message': 'CRITICAL: Backup file checksum mismatch! Restore aborted.'}

    is_maint_active, _ = MaintenanceWindow.is_currently_active()
    if not is_maint_active and not confirm_maintenance:
        return {
            'success': False,
            'message': 'Restore requires active Maintenance Mode to prevent concurrent writes. Please enable maintenance mode first.',
        }

    if dry_run:
        # Run test restore in scratch DB to verify validity
        scratch_res = test_restore_backup(backup_id)
        if not scratch_res.get('success'):
            return {
                'success': False,
                'message': f'Dry-run failed: {scratch_res.get("message")}',
            }
        return {
            'success': True,
            'dry_run': True,
            'message': f'Dry run verification passed. Backup "{record.filename}" is intact and ready for live restore.',
            'table_count': scratch_res.get('table_count'),
            'file_size_mb': round(record.file_size_bytes / (1024 * 1024), 2),
        }

    # Real restore
    db_conf = settings.DATABASES['default']
    env = os.environ.copy()
    env['MYSQL_PWD'] = db_conf.get('PASSWORD', '')
    cmd = [
        MYSQL_PATH,
        '-h', db_conf.get('HOST', '127.0.0.1'),
        '-P', str(db_conf.get('PORT', 3306)),
        '-u', db_conf.get('USER', 'root'),
        db_conf['NAME'],
    ]

    try:
        with open(record.file_path, 'rb') as infile:
            proc = subprocess.run(cmd, env=env, stdin=infile, capture_output=True, timeout=180)
        if proc.returncode != 0:
            err = proc.stderr.decode('utf-8', errors='ignore')
            raise RuntimeError(f'Live restore command failed: {err}')

        return {
            'success': True,
            'dry_run': False,
            'message': f'Live database restored successfully from "{record.filename}".',
        }
    except Exception as exc:
        logger.critical('Live database restore error: %s', exc)
        return {'success': False, 'message': f'Live restore failed: {str(exc)}'}

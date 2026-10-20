# ExamAI Database Backup, Verification & Disaster Recovery Runbook

This runbook outlines the operational procedures for creating database snapshots, verifying backup integrity via isolated dry-run restores, and executing disaster recovery procedures.

---

## 1. Backup Strategy Overview

- **Storage Location**: Backups are stored in the directory defined by `EXAMAI_BACKUP_DIR` outside the application web root (e.g., `/var/backups/examai`).
- **Integrity Guarantee**: Every backup file has an accompanying SHA-256 cryptographic checksum computed immediately upon file writing and recorded in the `DatabaseBackupRecord` model.
- **Retention Policy**: Controlled by `EXAMAI_BACKUP_RETENTION_DAYS` (default: 14 days). Backups older than this threshold are pruned automatically by `prune_backups()` during scheduled runs.
- **Dry-run Test Restores**: Tested in an isolated scratch database without touching live production tables.

---

## 2. Triggering Backups

### Method A: Automated Cron / Scheduled Command
```bash
python manage.py run_scheduled_backup
```
Output:
```
[INFO] Initiating automated database backup...
[SUCCESS] Backup created successfully:
  - Filename: examai_backup_20261020_020000.sql
  - Size: 3,745,120 bytes
  - SHA-256: 3a7b9c...
  - Retention: Pruned 0 expired backup archives.
```

### Method B: Super Admin Console
1. Navigate to **Super Admin Console** -> **Backups & Recovery**.
2. Click **Create New Backup**.
3. Choose whether to add an optional operator note (e.g., "Pre-upgrade snapshot v2.1").
4. The system triggers `create_database_backup()`, registers the record, and displays the SHA-256 hash.

---

## 3. Dry-Run Integrity Verification (Scratch Restore)

Before trusting any backup for disaster recovery, test restore it in an isolated scratch database:

```bash
python manage.py test_backup_restore --filename examai_backup_20261020_020000.sql
```

What the verification script does:
1. Re-computes SHA-256 of the backup file and matches against `DatabaseBackupRecord.checksum_sha256`.
2. Creates an ephemeral temporary SQLite/Postgres scratch database in the scratch directory.
3. Loads schema and data into the scratch database.
4. Executes consistency queries (counts users, institutes, exams).
5. Destroys the ephemeral scratch database immediately.
6. Records `test_restore_status='passed'` and `last_test_restore_at` in the database.

---

## 4. Disaster Recovery Live Restore Procedure

> [!CAUTION]
> A live restore replaces existing database tables with data from the backup file. Follow this step-by-step checklist strictly.

### Step 1: Activate Maintenance Mode
Prevent users from submitting exams or modifying data during recovery:
```bash
python -c "from superadmin.models import MaintenanceWindow; from django.utils import timezone, timedelta; MaintenanceWindow.objects.create(title='Emergency Database Restoration', is_active=True, start_time=timezone.now(), end_time=timezone.now() + timedelta(hours=1), reason='Database maintenance in progress.')"
```
Or toggle Maintenance Mode in the **Super Admin System Settings** tab.

### Step 2: Stop Application Workers
Stop Gunicorn and background workers to release active database locks:
```bash
sudo systemctl stop examai.service
```

### Step 3: Take a Pre-Restore Safety Snapshot of Current State
Always capture the current state (even if corrupted) before restoring:
```bash
python manage.py run_scheduled_backup
```

### Step 4: Execute Live Restore
Run the restore utility pointing to the verified backup file:
```bash
python -c "from superadmin.backups import restore_backup_on_live_database; success, msg = restore_backup_on_live_database('examai_backup_20261020_020000.sql'); print('Status:', success, msg)"
```

### Step 5: Verify Data Consistency
Run Django check and verify essential model counts:
```bash
python manage.py check
python -c "from api.models import User, Institution, Exam; print(f'Users: {User.objects.count()}, Institutes: {Institution.objects.count()}, Exams: {Exam.objects.count()}')"
```

### Step 6: Restart Application & Disable Maintenance Mode
1. Restart application server:
   ```bash
   sudo systemctl start examai.service
   ```
2. Run smoke tests:
   ```bash
   python scripts/smoke_test.py --url https://examai.yourdomain.com
   ```
3. Disable Maintenance Mode in Super Admin Console.
4. Verify audit log entry recording the live restoration action with HMAC hash chain integrity.

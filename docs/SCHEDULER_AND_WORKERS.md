# ExamAI Scheduled Tasks & Background Operations Guide

This guide describes how to configure periodic tasks, background job monitoring, automated backups, and cleanup workers for ExamAI.

---

## 1. Overview of Periodic Commands

ExamAI provides dedicated management commands designed to run as periodic cron jobs or systemd timers:

| Command | Recommended Schedule | Description |
| :--- | :--- | :--- |
| `python manage.py run_scheduled_backup` | Daily at 02:00 UTC | Creates an atomic database snapshot, computes SHA-256 hash, registers metadata in `DatabaseBackupRecord`, and prunes backups older than retention policy. |
| `python manage.py check_stuck_jobs` | Every 10 minutes | Detects AI generation tasks stuck in `pending` or `processing` states for longer than 15 minutes, marks them failed, and triggers deduplicated alerts. |
| `python manage.py test_backup_restore` | Weekly on Sunday at 04:00 UTC | Performs an isolated dry-run test restore into a temporary scratch database to verify backup integrity without affecting live data. |

---

## 2. Linux Deployment (Crontab)

To install these scheduled tasks on Linux servers, edit the crontab for the service user (`www-data` or `examai`):

```bash
sudo crontab -u www-data -e
```

Add the following entries:

```cron
# ExamAI Periodic Background Tasks
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin
PROJECT_DIR=/opt/examai
PYTHON=/opt/examai/venv/bin/python

# 1. Stuck Job Detector & Remediation (Every 10 minutes)
*/10 * * * * cd $PROJECT_DIR && $PYTHON manage.py check_stuck_jobs >> /var/log/examai/jobs.log 2>&1

# 2. Daily Automated Database Backup & Prune (Daily at 02:00)
0 2 * * * cd $PROJECT_DIR && $PYTHON manage.py run_scheduled_backup >> /var/log/examai/backups.log 2>&1

# 3. Weekly Test Restore Verification (Sunday at 04:00)
0 4 * * 0 cd $PROJECT_DIR && $PYTHON manage.py test_backup_restore >> /var/log/examai/restore_test.log 2>&1
```

---

## 3. Linux Deployment (Systemd Timers Alternative)

For enterprise environments requiring centralized journald logging and restart policies, use systemd service & timer units:

### Example: Stuck Job Detector (`/etc/systemd/system/examai-stuck-jobs.service`)
```ini
[Unit]
Description=ExamAI Stuck Job Cleanup Worker
After=network.target

[Service]
Type=oneshot
User=www-data
WorkingDirectory=/opt/examai
EnvironmentFile=/etc/examai/.env
ExecStart=/opt/examai/venv/bin/python manage.py check_stuck_jobs
```

### Timer (`/etc/systemd/system/examai-stuck-jobs.timer`)
```ini
[Unit]
Description=Run ExamAI Stuck Job Cleanup every 10 minutes

[Timer]
OnBootSec=5min
OnUnitActiveSec=10min
Unit=examai-stuck-jobs.service

[Install]
WantedBy=timers.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now examai-stuck-jobs.timer
```

---

## 4. Windows Server Deployment (Task Scheduler)

On Windows Server or local development:

1. Open **Task Scheduler** (`taskschd.msc`).
2. Click **Create Task** -> Name: `ExamAI Daily Backup`.
3. Under **Triggers**, set Daily at `02:00:00`.
4. Under **Actions**, set:
   - **Program/script**: `powershell.exe`
   - **Arguments**: `-NoProfile -ExecutionPolicy Bypass -Command "& 'E:\03 Study\Django\Mini-Project\.venv\Scripts\python.exe' 'E:\03 Study\Django\Mini-Project\manage.py' run_scheduled_backup"`
5. Repeat for `check_stuck_jobs` with trigger set to repeat every 10 minutes indefinitely.

---

## 5. Job Status & Alerting

When `check_stuck_jobs` identifies a stuck job or an AI service timeout:
1. The job record is transitioned to status `failed` with error reason: `"Job execution exceeded timeout threshold (15 minutes). Automatically terminated by system scheduler."`.
2. A deduplicated notification is dispatched to configured `ALERT_EMAIL_RECIPIENTS` via `send_deduplicated_alert()`.
3. An audit record is written with cryptographic HMAC-SHA256 signature for immutable tracking in the Super Admin Console.

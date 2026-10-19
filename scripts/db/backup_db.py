#!/usr/bin/env python
"""
Secure automated database backup script for ExamAI.

Supports MySQL (via mysqldump using temporary secure credentials config)
and SQLite (via online backup API).
Automatically compresses backup archives (.sql.gz) and applies retention policy.
"""

import gzip
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

# Initialize Django environment
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')

try:
    import django
    django.setup()
    from django.conf import settings
except Exception as exc:
    print(f"Error initializing Django: {exc}", file=sys.stderr)
    sys.exit(1)


def find_mysqldump():
    """Locate the mysqldump binary in PATH or standard installation directories."""
    candidate = shutil.which("mysqldump")
    if candidate:
        return candidate

    standard_paths = [
        r"C:\Program Files\MySQL\MySQL Server 8.4\bin\mysqldump.exe",
        r"C:\Program Files\MySQL\MySQL Server 8.0\bin\mysqldump.exe",
        r"C:\Program Files\MySQL\MySQL Server 5.7\bin\mysqldump.exe",
        r"C:\xampp\mysql\bin\mysqldump.exe",
        "/usr/bin/mysqldump",
        "/usr/local/bin/mysqldump",
    ]
    for p in standard_paths:
        if os.path.isfile(p):
            return p
    return None


def backup_mysql(db_config, output_file):
    """Dump MySQL database using secure option file to avoid password exposure in process table."""
    mysqldump_bin = find_mysqldump()
    if not mysqldump_bin:
        raise RuntimeError("mysqldump binary not found. Please install MySQL client tools or add to PATH.")

    db_name = db_config.get('NAME')
    db_user = db_config.get('USER', 'examai_user')
    db_pass = db_config.get('PASSWORD', '')
    db_host = db_config.get('HOST', '127.0.0.1')
    db_port = str(db_config.get('PORT', '3306'))

    # Create temporary option file for mysqldump
    temp_cnf = tempfile.NamedTemporaryFile(mode='w', suffix='.cnf', delete=False)
    try:
        temp_cnf.write(
            f"[client]\n"
            f"user={db_user}\n"
            f"password={db_pass}\n"
            f"host={db_host}\n"
            f"port={db_port}\n"
        )
        temp_cnf.flush()
        temp_cnf.close()

        cmd = [
            mysqldump_bin,
            f"--defaults-extra-file={temp_cnf.name}",
            "--single-transaction",
            "--quick",
            "--default-character-set=utf8mb4",
            "--routines",
            "--triggers",
            db_name,
        ]

        print(f"Executing mysqldump for database '{db_name}'...")
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        with gzip.open(output_file, 'wb') as gz_out:
            shutil.copyfileobj(proc.stdout, gz_out)

        _, stderr = proc.communicate()
        if proc.returncode != 0:
            err_msg = stderr.decode('utf-8', errors='replace').strip()
            raise RuntimeError(f"mysqldump failed (code {proc.returncode}): {err_msg}")

    finally:
        if os.path.exists(temp_cnf.name):
            try:
                os.remove(temp_cnf.name)
            except OSError:
                pass


def backup_sqlite(db_config, output_file):
    """Dump SQLite database using online backup API without locking."""
    src_path = str(db_config.get('NAME'))
    if not os.path.exists(src_path):
        raise FileNotFoundError(f"SQLite database file not found: {src_path}")

    temp_dump = tempfile.NamedTemporaryFile(suffix='.sqlite3', delete=False)
    temp_dump.close()

    try:
        print(f"Creating consistent SQLite snapshot of '{src_path}'...")
        src_conn = sqlite3.connect(src_path)
        dst_conn = sqlite3.connect(temp_dump.name)
        with dst_conn:
            src_conn.backup(dst_conn)
        src_conn.close()
        dst_conn.close()

        print("Compressing SQLite snapshot...")
        with open(temp_dump.name, 'rb') as f_in:
            with gzip.open(output_file, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
    finally:
        if os.path.exists(temp_dump.name):
            try:
                os.remove(temp_dump.name)
            except OSError:
                pass


def cleanup_old_backups(backup_dir, retention_days=7):
    """Delete backup files older than retention_days."""
    if retention_days <= 0:
        return

    cutoff = datetime.now() - timedelta(days=retention_days)
    count = 0
    for p in Path(backup_dir).glob("examai_backup_*.gz"):
        try:
            mtime = datetime.fromtimestamp(p.stat().st_mtime)
            if mtime < cutoff:
                p.unlink()
                count += 1
        except OSError:
            pass

    if count > 0:
        print(f"Cleaned up {count} backup(s) older than {retention_days} days.")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="ExamAI Database Backup Utility")
    parser.add_argument("--retention-days", type=int, default=7, help="Retention period in days (default: 7)")
    parser.add_argument("--output-dir", type=str, default="backups", help="Destination folder (default: backups)")
    args = parser.parse_args()

    backup_dir = BASE_DIR / args.output_dir
    backup_dir.mkdir(parents=True, exist_ok=True)

    db_config = settings.DATABASES['default']
    engine = db_config.get('ENGINE', '')
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    if 'mysql' in engine:
        filename = f"examai_backup_mysql_{timestamp}.sql.gz"
        out_path = backup_dir / filename
        backup_mysql(db_config, out_path)
    elif 'sqlite' in engine:
        filename = f"examai_backup_sqlite_{timestamp}.db.gz"
        out_path = backup_dir / filename
        backup_sqlite(db_config, out_path)
    else:
        raise ValueError(f"Unsupported database engine for backup: {engine}")

    file_size_kb = out_path.stat().st_size / 1024
    print(f"SUCCESS: Backup saved to: {out_path} ({file_size_kb:.2f} KB)")

    cleanup_old_backups(backup_dir, retention_days=args.retention_days)
    return 0


if __name__ == '__main__':
    sys.exit(main())

# ExamAI - AI-Powered Examination & Assessment Platform

## Overview
ExamAI is a multi-tenant examination platform built with Django REST Framework and React + Vite. It provides automated paper generation, intelligent question bank management, live exam proctoring & dashboards, student attempt evaluations, and role-based multi-tenant isolation.

---

## Database Architecture

ExamAI natively supports both **MySQL 8.4 LTS** (production/staging) and **SQLite** (local development/fallback).

The active database engine is controlled seamlessly via the `DB_ENGINE` setting in your `.env` file.

### Supported Database Engines

| Parameter | MySQL (Default / Recommended) | SQLite (Development / Rollback) |
| :--- | :--- | :--- |
| **Engine** | MySQL 8.4 LTS / 8.0+ | SQLite 3 |
| **Driver** | `mysqlclient` (2.3.0) | Built-in Python `sqlite3` |
| **Charset** | `utf8mb4` | UTF-8 |
| **Collation** | `utf8mb4_0900_ai_ci` | Binary |
| **Isolation** | `READ COMMITTED` | WAL mode |
| **Connection Pooling** | `CONN_MAX_AGE = 60` | Persistent |

---

## Environment Configuration

Create a `.env` file in the project root (see `.env.example`):

### MySQL Configuration
```env
DB_ENGINE=mysql
DB_NAME=examai
DB_USER=examai_user
DB_PASSWORD=your_secure_password
DB_HOST=127.0.0.1
DB_PORT=3306
```

### Instant Rollback to SQLite
To instantly run against the SQLite database with zero downtime or reconfiguration:
```env
DB_ENGINE=sqlite
```

---

## Useful Database Management Scripts

All database maintenance scripts are located in `scripts/`:

1. **Database Health Check**
   Inspects connectivity, server version, character set, transaction isolation level, and row counts:
   ```bash
   python scripts/check_db_health.py
   ```

2. **Migration Data Verification**
   Compares SQLite (`db.sqlite3`) and MySQL row-by-row, tenant-by-tenant, and verifies numerical checksums, foreign key integrity, and sample records:
   ```bash
   python scripts/verify_mysql_migration.py
   ```

3. **Auto-Increment Sequence Reset**
   Syncs all table `AUTO_INCREMENT` values to `MAX(id) + 1`:
   ```bash
   python scripts/reset_auto_increment.py
   ```

4. **Query Performance Analyzer**
   Runs MySQL `EXPLAIN` query execution plans on dashboard hot paths and question bank indexes:
   ```bash
   python scripts/explain_queries.py
   ```

---

## Running the Automated Test Suite

Run all test suites against the active database:

```bash
# MySQL Compatibility & Deadlock Retry Tests
python manage.py test api.test_mysql_compatibility --keepdb

# Multi-Tenant Isolation Tests
python manage.py test api.test_multi_tenant_isolation --keepdb

# Admin Live Examination Dashboard Tests
python manage.py test api.test_admin_live_exams --keepdb

# Question Bank Management Tests
python manage.py test api.test_question_bank --keepdb

# Paper Engine & Generation Tests
python manage.py test api.test_paper_generation --keepdb

# Concurrency & Lock Handling Tests
python manage.py test api.test_save_concurrency --keepdb
```

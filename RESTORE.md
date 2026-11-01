# EXAM PLATFORM - COMPLETE RESTORE & RUNBOOK

This document describes step-by-step instructions to restore and verify the entire exam platform from this backup set (`Mini-Project_20261101_1850_FINAL`) onto a clean machine or fresh deployment environment.

---

## 1. System Prerequisites

| Component | Minimum Version | Recommended Version | Verification Command |
|---|---|---|---|
| **Operating System** | Windows 10/11 / Ubuntu 22.04+ / macOS | Windows 11 / Linux | `cmd /c ver` or `uname -a` |
| **Python** | 3.11+ | Python 3.13.x | `python --version` |
| **Node.js** | 18.x+ | Node 20.x LTS | `node --version` |
| **npm** | 9.x+ | npm 10.x+ | `npm --version` |
| **Database** | SQLite 3.35+ (or PostgreSQL 15+) | SQLite 3 (built-in) | `python -c "import sqlite3; print(sqlite3.sqlite_version)"` |
| **Ollama (Optional)** | 0.3+ | 0.5+ (for local AI generation) | `ollama --version` |

---

## 2. Directory Structure of This Backup Set

```text
Mini-Project_20261101_1850_FINAL/
├── database/
│   ├── db_final.sqlite3      # Clean snapshot of SQLite database (12.7 MB, 53 tables)
│   └── db_final.sql          # Standard ANSI SQL dump (9.28 MB)
├── media/                    # All uploads, syllabus docs, and avatars (29 files)
├── project_src/              # Clean source tree (backend + frontend)
├── seed_credentials.csv      # Complete credentials for 1,152 demo users
├── CHECKSUMS_SHA256.txt      # SHA-256 digests for all files in this backup
├── MANIFEST.txt              # Detailed manifest with exact byte counts and checksums
└── RESTORE.md                # This restoration guide
```

---

## 3. Step-by-Step Restoration Procedure

### Step 1: Copy Source Code to Target Destination
Copy the contents of `project_src/` to your target project folder (e.g., `C:\Projects\Mini-Project` or `/var/www/exam-platform`):
```powershell
# Windows PowerShell
Copy-Item -Path "project_src\*" -Destination "C:\Projects\Mini-Project" -Recurse -Force

# Linux / macOS
cp -r project_src/* /path/to/target/
```

### Step 2: Configure Environment Variables
Copy `.env.example` to `.env` and configure settings:
```powershell
cd C:\Projects\Mini-Project
Copy-Item .env.example .env
```
Ensure key environment values are present in `.env`:
```ini
DEBUG=True
SECRET_KEY=django-insecure-restore-seed-key-2026-exam-platform-production
ALLOWED_HOSTS=localhost,127.0.0.1,testserver
DATABASE_URL=sqlite:///db.sqlite3
```

### Step 3: Setup Python Virtual Environment & Backend Dependencies
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1   # On Linux: source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### Step 4: Setup Frontend Dependencies
```powershell
cd Front-End
npm install
cd ..
```

### Step 5: Restore Media Files
Copy all media assets into the `media/` directory:
```powershell
# In project root
New-Item -ItemType Directory -Path "media" -Force
Copy-Item -Path "E:\Backups\Mini-Project_20261101_1850_FINAL\media\*" -Destination "media" -Recurse -Force
```

### Step 6: Restore the Database
You can restore either from the direct SQLite binary or the ANSI SQL script:

**Option A (Fastest — Direct SQLite binary restore):**
```powershell
Copy-Item -Path "E:\Backups\Mini-Project_20261101_1850_FINAL\database\db_final.sqlite3" -Destination "db.sqlite3" -Force
```

**Option B (From SQL Dump):**
```powershell
python -c "import sqlite3; con = sqlite3.connect('db.sqlite3'); con.executescript(open(r'E:\Backups\Mini-Project_20261101_1850_FINAL\database\db_final.sql', encoding='utf-8').read()); con.close()"
```

### Step 7: Validate Database & Django Integrity
```powershell
python manage.py check
python manage.py makemigrations --check
```

Verify table counts and row statistics:
```powershell
python manage.py shell -c "from admins.models import AdminInstitution; from api.models import Exam, Question, StudentAttempt; print(f'Institutes: {AdminInstitution.objects.count()} | Exams: {Exam.objects.count()} | Questions: {Question.objects.count()} | Attempts: {StudentAttempt.objects.count()}')"
```
Expected output:
`Institutes: 10 | Exams: 431 | Questions: 5219 | Attempts: 829`

### Step 8: Copy Credentials File (Optional for Dev / Demo Login)
```powershell
Copy-Item -Path "E:\Backups\Mini-Project_20261101_1850_FINAL\seed_credentials.csv" -Destination "seed_credentials.csv" -Force
```

---

## 4. Default Credentials & Test Accounts

Shared password for all seeded accounts: `DevSeed@2026!`

| Institute | Role | Name | Username / Email | Password |
|---|---|---|---|---|
| **Global** | **Super Admin** | Harsh Poshiya | `harshposhiya92@gmail.com` | *(Protected user secret)* |
| **GLS University** | Admin | Admin GLS | `admin.gls@example.edu` | `DevSeed@2026!` |
| **GLS University** | Faculty | Harsh Poshiya | `harsh.poshiya21@gmail.com` | *(Protected user secret)* |
| **GLS University** | Student | Harsh Poshiya | `harshposhiya92@gmail.com` | *(Protected user secret)* |
| **Gujarat University** | Admin | Ishika Makwana | `ishikamakwana@gmail.com` | `DevSeed@2026!` |
| **Gujarat University** | Faculty | Pallavi Rathore | `pallavi.rathore.fac.gu.12.1@example.edu` | `DevSeed@2026!` |
| **Gujarat University** | Student | Aarav Sharma | `aarav.sharma.stu.gu.12.1@example.edu` | `DevSeed@2026!` |
| **L.D. College of Eng.**| Admin | Richa Jethva | `richajethva@gmail.com` | `DevSeed@2026!` |
| **L.D. College of Eng.**| Faculty | Nikhil Verma | `nikhil.verma.fac.ldce.20.1@example.edu` | `DevSeed@2026!` |
| **L.D. College of Eng.**| Student | Divya Patel | `divya.patel.stu.ldce.20.1@example.edu` | `DevSeed@2026!` |
| **Atmiya University** | Admin | Admin Atmiya | `admin.atmiya@example.edu` | `DevSeed@2026!` |
| **Atmiya University** | Faculty | Vivek Poshiya | `vivekposhiya@gmail.com` | *(Protected user secret)* |
| **Atmiya University** | Student | Hardik Patel | `hardikpatel@gmail.com` | *(Protected user secret)* |
| **Pragyan Inst.** | Admin | Admin PITS | `admin.pits@example.edu` | `DevSeed@2026!` |
| **Pragyan Inst.** | Faculty | Pallavi Rajput | `pallavi.rajput.fac.1@pits.example.edu` | `DevSeed@2026!` |
| **Pragyan Inst.** | Student | Tarun Rathore | `tarun.rathore.stu.1@pits.example.edu` | `DevSeed@2026!` |
| **Deccan Inst.** | Admin | Admin DIAE | `admin.diae@example.edu` | `DevSeed@2026!` |
| **Deccan Inst.** | Faculty | Aarav Verma | `aarav.verma.fac.1@diae.example.edu` | `DevSeed@2026!` |
| **Deccan Inst.** | Student | Rohit Roy | `rohit.roy.stu.1@diae.example.edu` | `DevSeed@2026!` |

*(Full roster of all 1,152 accounts across 10 institutes is documented in `seed_credentials.csv`)*

---

## 5. Running the Application

### Start Django Backend:
```powershell
python manage.py runserver 8000
```
Backend API will be accessible at: `http://localhost:8000`

### Start React/Vite Frontend:
```powershell
cd Front-End
npm run dev
```
Frontend Web UI will be accessible at: `http://localhost:5173`

import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

os.environ['DB_ENGINE'] = 'mysql'
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
import django
django.setup()

with open(BASE_DIR / 'counts_sqlite.txt', encoding='utf-8') as f:
    sqlite_counts = dict(line.strip().split(': ') for line in f if line.strip())
with open(BASE_DIR / 'counts_mysql.txt', encoding='utf-8') as f:
    mysql_counts = dict(line.strip().split(': ') for line in f if line.strip())

excluded = {'contenttypes.contenttype', 'auth.permission', 'admin.logentry', 'sessions.session'}

print(f"{'Model':<35} {'SQLite':<10} {'MySQL':<10} {'Status'}")
print('-' * 70)

all_match = True
for model in sorted(sqlite_counts.keys()):
    sq = int(sqlite_counts.get(model, 0))
    my = int(mysql_counts.get(model, 0))
    if model in excluded:
        status = 'EXCLUDED (Auto-managed)'
    elif sq == my:
        status = 'EXACT MATCH'
    else:
        status = 'MISMATCH'
        all_match = False
    print(f"{model:<35} {sq:<10} {my:<10} {status}")

print('-' * 70)
print('Data Integrity Verification:', 'PASSED (100% Match)' if all_match else 'FAILED')

# Spot check records from important models
print('\n' + '=' * 70)
print('SPOT CHECKS FROM IMPORTANT MODELS')
print('=' * 70)

from api.models import Question, Option, Exam, StudentAnswer
from admins.models import AdminInstitution, AdminDepartment
from faculty.models import FacultyProfile, Paper
from students.models import StudentProfile
from django.contrib.auth.models import User

# 1. AdminInstitution
print('\n[1] AdminInstitution sample:')
for inst in AdminInstitution.objects.all()[:3]:
    print(f"  ID: {inst.id} | Name: {inst.institution_name} | Code: {inst.institution_code} | Created: {inst.created_at}")

# 2. Questions & Options (Check Unicode/Special characters and decimals/dates)
print('\n[2] Question sample:')
for q in Question.objects.all()[:3]:
    text_preview = q.text[:80].replace('\n', ' ')
    print(f"  ID: {q.id} | Subject: {q.subject.name if q.subject else None} | Marks: {q.marks} | Text: {text_preview}")

print('\n[3] Option sample (Options with text & is_correct):')
for opt in Option.objects.all()[:3]:
    print(f"  ID: {opt.id} | Question ID: {opt.question_id} | Correct: {opt.is_correct} | Text: {opt.text}")

print('\n[4] Auth User sample:')
for u in User.objects.all()[:3]:
    print(f"  ID: {u.id} | Username: {u.username} | Email: {u.email} | Is Staff: {u.is_staff} | Date Joined: {u.date_joined}")

print('\n[5] Exam sample:')
for ex in Exam.objects.all()[:3]:
    print(f"  ID: {ex.id} | Title: {ex.title} | Total Marks: {ex.total_marks} | Status: {ex.status} | Created: {ex.created_at}")

# Spot check unicode questions (e.g. non-ascii text)
print('\n[6] Unicode & Special Character Check:')
unicode_questions = [q for q in Question.objects.all() if any(ord(c) > 127 for c in q.text)][:3]
if unicode_questions:
    for q in unicode_questions:
        print(f"  ID: {q.id} | Unicode Text: {q.text[:80]}")
else:
    print("  All questions are in ASCII/English; checked special math/punctuation characters:")
    special_q = [q for q in Question.objects.all() if any(c in q.text for c in "{}[]()+-*/=<>_&^%$#@!~`")][:3]
    for q in special_q:
        print(f"  ID: {q.id} | Special Text: {q.text[:80]}")

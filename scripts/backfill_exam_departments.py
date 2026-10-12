"""Backfill department field on existing Exam records from creating faculty."""

import os
import sys
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')

import django
django.setup()

from api.models import Exam
from api.utils.departments import get_faculty_department, normalize_department


def backfill_exam_departments(dry_run: bool = False):
    exams = Exam.objects.all().order_by('id')
    total = exams.count()
    print(f"Found {total} exam(s) in database to inspect.")

    updated_count = 0
    unresolved = []

    for exam in exams:
        current_dept = (exam.department or '').strip()
        faculty = exam.created_by
        creator_dept = get_faculty_department(faculty) if faculty else ''

        if not current_dept:
            if creator_dept:
                target_dept = normalize_department(creator_dept)
                print(f"Exam #{exam.id} ('{exam.title}'): created by {faculty.email} -> backfilling department to '{target_dept}'")
                if not dry_run:
                    exam.department = target_dept
                    exam.save(update_fields=['department'])
                updated_count += 1
            else:
                unresolved.append(exam)
                print(f"Exam #{exam.id} ('{exam.title}'): created by {getattr(faculty, 'email', 'None')} -> UNRESOLVED (no faculty department)")
        else:
            print(f"Exam #{exam.id} ('{exam.title}'): department already set to '{current_dept}'.")

    mode = "DRY-RUN" if dry_run else "APPLIED"
    print(f"\n{mode} COMPLETE: {updated_count} exam(s) updated, {len(unresolved)} unresolved.")
    return updated_count, unresolved


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Backfill Exam department from creating faculty.")
    parser.add_argument('--dry-run', action='store_true', help="Preview changes without saving to DB")
    args = parser.parse_args()
    backfill_exam_departments(dry_run=args.dry_run)

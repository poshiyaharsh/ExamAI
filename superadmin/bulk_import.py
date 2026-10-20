import csv
import io
import logging
import re
import secrets
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.db import transaction

from admins.models import AdminDepartment, AdminInstitution
from faculty.models import FacultyProfile
from students.models import StudentProfile
from superadmin.institute_service import get_or_create_institute_policy

User = get_user_model()
logger = logging.getLogger(__name__)


def get_bulk_import_template(role: str = 'student') -> str:
    """Generate sample CSV template content for student or faculty bulk onboarding."""
    if role == 'faculty':
        return (
            "email,first_name,last_name,department,designation\n"
            "john.doe@college.edu,John,Doe,Computer Science,Associate Professor\n"
            "jane.smith@college.edu,Jane,Smith,Information Technology,Assistant Professor\n"
        )
    return (
        "email,first_name,last_name,department,roll_number\n"
        "alice.kumar@college.edu,Alice,Kumar,Computer Science,CS2026001\n"
        "bob.patel@college.edu,Bob,Patel,Information Technology,IT2026002\n"
    )


def validate_and_process_bulk_import(
    institution: AdminInstitution,
    file_content: str,
    role: str = 'student',
    dry_run: bool = True,
) -> dict:
    """
    Validate and optionally execute atomic bulk onboarding of students or faculty.
    Validates:
    - Email formats & uniqueness (against CSV and DB)
    - Valid department in institute's allowed departments
    - Required fields (first_name, last_name, department)
    Generates random strong passwords and returns one-time credentials table.
    Enforces immutable department during profile initialization.
    """
    policy = get_or_create_institute_policy(institution)
    valid_departments = {
        d.strip().lower(): d.strip()
        for d in (
            policy.allowed_departments
            or list(AdminDepartment.objects.filter(institution=institution).values_list('department_name', flat=True))
        )
    }

    reader = csv.DictReader(io.StringIO(file_content.strip()))
    required_fields = ['email', 'first_name', 'last_name', 'department']

    seen_emails = set()
    valid_rows = []
    errors = []

    for idx, row in enumerate(reader, start=2):  # Line 1 is header
        row_errors = []
        clean_row = {k.strip(): (v.strip() if v else '') for k, v in row.items() if k}

        # Check required fields
        for field in required_fields:
            if not clean_row.get(field):
                row_errors.append(f"Missing required field: '{field}'")

        email = clean_row.get('email', '').lower()
        if email:
            try:
                validate_email(email)
            except ValidationError:
                row_errors.append(f"Invalid email format: '{email}'")

            if email in seen_emails:
                row_errors.append(f"Duplicate email within import file: '{email}'")
            seen_emails.add(email)

            if User.objects.filter(email__iexact=email).exists():
                row_errors.append(f"Email '{email}' is already registered in the system.")

        # Check department
        dept_raw = clean_row.get('department', '')
        if dept_raw:
            norm_dept = valid_departments.get(dept_raw.lower())
            if not norm_dept:
                allowed_list = list(valid_departments.values())[:5]
                row_errors.append(
                    f"Department '{dept_raw}' is not authorized for {institution.institution_name}. "
                    f"Allowed: {', '.join(allowed_list)}..."
                )
            else:
                clean_row['department'] = norm_dept

        if row_errors:
            errors.append({
                'row_number': idx,
                'email': email or 'N/A',
                'errors': row_errors,
            })
        else:
            valid_rows.append(clean_row)

    total_rows = len(valid_rows) + len(errors)
    summary = {
        'total_rows': total_rows,
        'valid_count': len(valid_rows),
        'error_count': len(errors),
        'errors': errors,
        'dry_run': dry_run,
    }

    if dry_run or errors or not valid_rows:
        return summary

    # Execute atomic import
    created_credentials = []
    with transaction.atomic():
        for r in valid_rows:
            temp_password = f"{secrets.token_urlsafe(8)}!2026"
            base_username = r['email'].split('@')[0]
            username = base_username
            suffix = 1
            while User.objects.filter(username=username).exists():
                username = f"{base_username}{suffix}"
                suffix += 1

            user = User.objects.create(
                username=username,
                email=r['email'],
                first_name=r['first_name'],
                last_name=r['last_name'],
                password=make_password(temp_password),
            )

            if role == 'faculty':
                emp_id = r.get('employee_id') or FacultyProfile.build_next_employee_id(institution)
                FacultyProfile.objects.create(
                    user=user,
                    institution=institution,
                    employee_id=emp_id,
                    department=r['department'],
                    designation=r.get('designation', 'Faculty'),
                )
            else:
                stu_id = r.get('roll_number') or StudentProfile.build_next_student_id(institution)
                StudentProfile.objects.create(
                    user=user,
                    institution=institution,
                    student_id=stu_id,
                    department=r['department'],
                )

            created_credentials.append({
                'username': username,
                'email': r['email'],
                'role': role,
                'department': r['department'],
                'temp_password': temp_password,
            })

    summary['imported_count'] = len(created_credentials)
    summary['credentials'] = created_credentials
    summary['message'] = f'Successfully imported {len(created_credentials)} {role}(s) atomically.'
    return summary

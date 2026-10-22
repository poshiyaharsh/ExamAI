import logging
import secrets
import string
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Avg, Count, Max, Q, QuerySet
from django.utils import timezone

from admins.models import AdminDepartment, AdminInstitution, AdminProfile, DepartmentChangeAuditLog
from api.models import AttemptEvent, Exam, Notification, StudentAttempt
from faculty.models import FacultyProfile
from students.models import StudentProfile

User = get_user_model()
logger = logging.getLogger(__name__)


def parse_iso_datetime(dt_str: Optional[str]) -> Optional[datetime]:
    if not dt_str:
        return None
    try:
        clean = dt_str.replace('Z', '+00:00')
        dt = datetime.fromisoformat(clean)
        if timezone.is_naive(dt):
            dt = timezone.make_aware(dt)
        return dt
    except (ValueError, TypeError):
        return None


def get_users_tab_counts(inst_id: Optional[int] = None) -> Dict[str, int]:
    """Calculate total counts for students, faculty, and admins across the platform."""
    base_qs = User.objects.exclude(super_admin_profile__isnull=False)
    if inst_id:
        base_qs = base_qs.filter(
            Q(student_profile__institution_id=inst_id)
            | Q(faculty_profile__institution_id=inst_id)
            | Q(admin_institution__id=inst_id)
        )

    students_count = base_qs.filter(student_profile__isnull=False).count()
    faculty_count = base_qs.filter(faculty_profile__isnull=False).count()
    admins_count = base_qs.filter(admin_profile__isnull=False).count()

    return {
        'students': students_count,
        'faculty': faculty_count,
        'admins': admins_count,
        'total': students_count + faculty_count + admins_count,
    }


def filter_users_queryset(params: Dict[str, Any]) -> Tuple[QuerySet, Dict[str, int]]:
    """
    Build server-side filtered and sorted queryset for user management tabs.
    Returns (filtered_queryset, tab_counts).
    """
    role = str(params.get('role', 'student')).strip().lower()
    search = str(params.get('search', '')).strip()
    status_filter = str(params.get('status', 'all')).strip().lower()
    inst_id = params.get('institution_id')
    department = str(params.get('department', 'all')).strip()
    sort_by = str(params.get('sort_by', 'joined')).strip().lower()
    sort_order = str(params.get('sort_order', 'desc')).strip().lower()

    # Base: strictly exclude any super admin account
    qs = User.objects.exclude(super_admin_profile__isnull=False).select_related(
        'student_profile', 'student_profile__institution',
        'faculty_profile', 'faculty_profile__institution',
        'admin_profile', 'admin_institution',
    )

    tab_counts = get_users_tab_counts(int(inst_id) if inst_id else None)

    # 1. Role filtering
    if role == 'faculty':
        qs = qs.filter(faculty_profile__isnull=False)
    elif role == 'admin':
        qs = qs.filter(admin_profile__isnull=False)
    else:  # default 'student'
        qs = qs.filter(student_profile__isnull=False)

    # 2. Common filters: Institution
    if inst_id:
        try:
            inst_int = int(inst_id)
            if role == 'faculty':
                qs = qs.filter(faculty_profile__institution_id=inst_int)
            elif role == 'admin':
                qs = qs.filter(admin_institution__id=inst_int)
            else:
                qs = qs.filter(student_profile__institution_id=inst_int)
        except (ValueError, TypeError):
            pass

    # 3. Common filters: Department
    if department and department != 'all':
        if role == 'faculty':
            qs = qs.filter(faculty_profile__department__iexact=department)
        elif role == 'student':
            qs = qs.filter(student_profile__department__iexact=department)

    # 4. Common filters: Status
    if status_filter == 'active':
        qs = qs.filter(is_active=True)
    elif status_filter == 'inactive':
        qs = qs.filter(is_active=False)

    # 5. Common filters: Joined Date Range
    joined_after = parse_iso_datetime(params.get('joined_after'))
    joined_before = parse_iso_datetime(params.get('joined_before'))
    if joined_after:
        qs = qs.filter(date_joined__gte=joined_after)
    if joined_before:
        qs = qs.filter(date_joined__lte=joined_before)

    # 6. Common filters: Last Login Range
    never_logged_in = str(params.get('never_logged_in', '')).lower() in ('true', '1')
    if never_logged_in:
        qs = qs.filter(last_login__isnull=True)
    else:
        last_login_after = parse_iso_datetime(params.get('last_login_after'))
        last_login_before = parse_iso_datetime(params.get('last_login_before'))
        if last_login_after:
            qs = qs.filter(last_login__gte=last_login_after)
        if last_login_before:
            qs = qs.filter(last_login__lte=last_login_before)

    # 7. Common filters: Search (name, email, username, identifier)
    if search:
        search_q = (
            Q(username__icontains=search)
            | Q(email__icontains=search)
            | Q(first_name__icontains=search)
            | Q(last_name__icontains=search)
        )
        if search.isdigit():
            search_q |= Q(id=int(search))
        if role == 'student':
            search_q |= Q(student_profile__student_id__icontains=search)
        elif role == 'faculty':
            search_q |= Q(faculty_profile__employee_id__icontains=search)
        elif role == 'admin':
            search_q |= Q(admin_institution__institution_code__icontains=search)
            search_q |= Q(admin_institution__institution_name__icontains=search)
        qs = qs.filter(search_q)

    # 8. Role-specific: Students
    if role == 'student':
        batch_year = str(params.get('batch_year', '')).strip()
        if batch_year:
            qs = qs.filter(student_profile__student_id__icontains=f'-{batch_year}-')

        enrollment_id = str(params.get('enrollment_id', '')).strip()
        if enrollment_id:
            qs = qs.filter(student_profile__student_id__icontains=enrollment_id)

        exam_activity = str(params.get('exam_activity', '')).strip().lower()
        if exam_activity == 'attempted':
            qs = qs.filter(exam_attempts__isnull=False).distinct()
        elif exam_activity == 'never_attempted':
            qs = qs.filter(exam_attempts__isnull=True)

        flagged_violations = str(params.get('flagged_violations', '')).strip().lower()
        if flagged_violations in ('true', '1'):
            qs = qs.filter(exam_attempts__violation_count__gt=0).distinct()
        elif flagged_violations in ('false', '0'):
            qs = qs.exclude(exam_attempts__violation_count__gt=0)

    # 9. Role-specific: Faculty
    elif role == 'faculty':
        designation = str(params.get('designation', '')).strip()
        if designation and designation != 'all':
            qs = qs.filter(faculty_profile__designation__icontains=designation)

        employee_id = str(params.get('employee_id', '')).strip()
        if employee_id:
            qs = qs.filter(faculty_profile__employee_id__icontains=employee_id)

        has_published = str(params.get('has_published_exams', '')).strip().lower()
        if has_published in ('true', '1'):
            qs = qs.filter(created_exams__status=Exam.Status.PUBLISHED).distinct()
        elif has_published in ('false', '0'):
            qs = qs.exclude(created_exams__status=Exam.Status.PUBLISHED)

        has_live = str(params.get('has_live_exams', '')).strip().lower()
        now = timezone.now()
        if has_live in ('true', '1'):
            qs = qs.filter(
                created_exams__status=Exam.Status.PUBLISHED,
                created_exams__starts_at__lte=now,
                created_exams__ends_at__gte=now,
            ).distinct()
        elif has_live in ('false', '0'):
            qs = qs.exclude(
                created_exams__status=Exam.Status.PUBLISHED,
                created_exams__starts_at__lte=now,
                created_exams__ends_at__gte=now,
            )

    # 10. Server-side Sorting
    prefix = '' if sort_order == 'asc' else '-'
    if sort_by == 'name':
        qs = qs.order_by(f'{prefix}first_name', f'{prefix}last_name', '-id')
    elif sort_by == 'last_login':
        # Nulls last for last_login
        if sort_order == 'asc':
            qs = qs.order_by('last_login', '-id')
        else:
            qs = qs.order_by('-last_login', '-id')
    elif sort_by == 'identifier':
        if role == 'student':
            qs = qs.order_by(f'{prefix}student_profile__student_id', '-id')
        elif role == 'faculty':
            qs = qs.order_by(f'{prefix}faculty_profile__employee_id', '-id')
        else:
            qs = qs.order_by(f'{prefix}id')
    else:  # default 'joined'
        qs = qs.order_by(f'{prefix}date_joined', '-id')

    return qs, tab_counts


def serialize_user_row(u: User, role: str) -> Dict[str, Any]:
    """Serialize user row data according to role specifications."""
    full_name = f'{u.first_name} {u.last_name}'.strip() or u.username
    row: Dict[str, Any] = {
        'id': u.id,
        'username': u.username,
        'email': u.email,
        'full_name': full_name,
        'role': role,
        'is_active': u.is_active,
        'date_joined': u.date_joined.isoformat() if u.date_joined else None,
        'last_login': u.last_login.isoformat() if u.last_login else None,
    }

    if role == 'student':
        sp = getattr(u, 'student_profile', None)
        inst = sp.institution if sp else None
        stu_id = sp.student_id if sp else ''
        batch = ''
        if stu_id and '-' in stu_id:
            parts = stu_id.split('-')
            if len(parts) >= 2 and parts[1].isdigit():
                batch = parts[1]
        elif sp and sp.created_at:
            batch = str(sp.created_at.year)

        row.update({
            'identifier': stu_id or f'STU-{u.id:04d}',
            'department': sp.department if (sp and sp.department) else 'Unassigned',
            'institution': {
                'id': inst.id if inst else None,
                'name': inst.institution_name if inst else 'Unassigned',
                'code': inst.institution_code if inst else '',
            },
            'batch_year': batch or 'N/A',
            'semester': getattr(sp, 'semester', None) or 'N/A',
        })

    elif role == 'faculty':
        fp = getattr(u, 'faculty_profile', None)
        inst = fp.institution if fp else None
        row.update({
            'identifier': fp.employee_id if (fp and fp.employee_id) else f'FAC-{u.id:03d}',
            'department': fp.department if (fp and fp.department) else 'Unassigned',
            'designation': fp.designation if (fp and fp.designation) else 'Faculty Member',
            'institution': {
                'id': inst.id if inst else None,
                'name': inst.institution_name if inst else 'Unassigned',
                'code': inst.institution_code if inst else '',
            },
        })

    elif role == 'admin':
        inst = getattr(u, 'admin_institution', None)
        row.update({
            'identifier': f'ADM-{u.id:03d}',
            'institution': {
                'id': inst.id if inst else None,
                'name': inst.institution_name if inst else 'Unassigned',
                'code': inst.institution_code if inst else '',
            },
            'department': 'Administration',
            'permissions_scope': inst.institution_name if inst else 'Unassigned',
        })

    return row


def get_user_drawer_details(user_id: int) -> Dict[str, Any]:
    """Compile comprehensive profile, history, activity and notifications for drawer view."""
    user = User.objects.filter(id=user_id).select_related(
        'student_profile', 'student_profile__institution',
        'faculty_profile', 'faculty_profile__institution',
        'admin_profile', 'admin_institution',
    ).first()

    if not user or hasattr(user, 'super_admin_profile'):
        raise ValidationError('User not found or access restricted.')

    role = 'student'
    inst_name = 'Unassigned'
    inst_code = ''
    inst_id = None
    dept = 'Unassigned'
    identifier = ''
    role_meta: Dict[str, Any] = {}

    if hasattr(user, 'faculty_profile'):
        role = 'faculty'
        fp = user.faculty_profile
        dept = fp.department or 'Unassigned'
        identifier = fp.employee_id or f'FAC-{user.id:03d}'
        if fp.institution:
            inst_name = fp.institution.institution_name
            inst_code = fp.institution.institution_code
            inst_id = fp.institution.id
        role_meta['designation'] = fp.designation or 'Faculty Member'

    elif hasattr(user, 'admin_profile'):
        role = 'admin'
        identifier = f'ADM-{user.id:03d}'
        inst = getattr(user, 'admin_institution', None)
        if inst:
            inst_name = inst.institution_name
            inst_code = inst.institution_code
            inst_id = inst.id
        dept = 'Administration'
        role_meta['scope'] = inst_name

    elif hasattr(user, 'student_profile'):
        role = 'student'
        sp = user.student_profile
        dept = sp.department or 'Unassigned'
        identifier = sp.student_id or f'STU-{user.id:04d}'
        if sp.institution:
            inst_name = sp.institution.institution_name
            inst_code = sp.institution.institution_code
            inst_id = sp.institution.id

    # Activity Summary
    activity_summary: Dict[str, Any] = {}
    if role == 'student':
        attempts = StudentAttempt.objects.filter(student=user)
        total_attempts = attempts.count()
        submitted = attempts.filter(status__in=[StudentAttempt.Status.SUBMITTED, StudentAttempt.Status.EVALUATED])
        avg_score = submitted.aggregate(avg=Avg('total_score'))['avg'] or 0.0
        violations_count = attempts.aggregate(v=Avg('violation_count'))['v'] or 0
        recent_attempts = [
            {
                'id': a.id,
                'exam_title': a.exam.title if a.exam else 'Exam',
                'score': a.total_score,
                'max_score': a.max_score,
                'status': a.status,
                'started_at': a.started_at.isoformat() if a.started_at else None,
                'violations': a.violation_count,
            }
            for a in attempts.order_by('-started_at')[:5]
        ]
        activity_summary = {
            'total_attempts': total_attempts,
            'completed_attempts': submitted.count(),
            'average_score': round(float(avg_score), 1),
            'total_violations': int(violations_count),
            'recent_attempts': recent_attempts,
        }

    elif role == 'faculty':
        exams = Exam.objects.filter(created_by=user)
        total_exams = exams.count()
        published_exams = exams.filter(status=Exam.Status.PUBLISHED).count()
        now = timezone.now()
        live_exams = exams.filter(
            status=Exam.Status.PUBLISHED,
            starts_at__lte=now,
            ends_at__gte=now,
        ).count()
        recent_exams = [
            {
                'id': e.id,
                'title': e.title,
                'status': e.status,
                'total_marks': e.total_marks,
                'created_at': e.created_at.isoformat() if e.created_at else None,
            }
            for e in exams.order_by('-created_at')[:5]
        ]
        activity_summary = {
            'total_exams_created': total_exams,
            'published_exams': published_exams,
            'live_exams': live_exams,
            'recent_exams': recent_exams,
        }

    elif role == 'admin':
        inst = getattr(user, 'admin_institution', None)
        if inst:
            total_students = StudentProfile.objects.filter(institution=inst).count()
            total_faculty = FacultyProfile.objects.filter(institution=inst).count()
            total_exams = Exam.objects.filter(institution=inst).count()
            departments_count = AdminDepartment.objects.filter(institution=inst).count()
            activity_summary = {
                'total_students': total_students,
                'total_faculty': total_faculty,
                'total_exams': total_exams,
                'departments_count': departments_count,
            }

    # Notifications Sent to this User
    user_notifications = [
        {
            'id': n.id,
            'title': n.title,
            'message': n.message,
            'type': n.type,
            'is_read': n.is_read,
            'created_at': n.created_at.isoformat(),
        }
        for n in Notification.objects.filter(user=user).order_by('-created_at')[:8]
    ]

    return {
        'profile': {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'role': role,
            'identifier': identifier,
            'is_active': user.is_active,
            'date_joined': user.date_joined.isoformat() if user.date_joined else None,
            'last_login': user.last_login.isoformat() if user.last_login else None,
            'department': dept,
            'institution': {
                'id': inst_id,
                'name': inst_name,
                'code': inst_code,
            },
            'role_meta': role_meta,
        },
        'activity_summary': activity_summary,
        'notifications': user_notifications,
    }


def create_user_record(data: Dict[str, Any], creator_user: User) -> Tuple[User, str]:
    """
    Validate and create a new Student, Faculty, or Admin user.
    Strictly forbids creating Super Admin accounts.
    Returns (created_user, generated_or_provided_password).
    """
    role = str(data.get('role', '')).strip().lower()
    if role not in ('student', 'faculty', 'admin'):
        raise ValidationError('Role must be "student", "faculty", or "admin". Super Admin creation is prohibited.')

    email = str(data.get('email', '')).strip().lower()
    username = str(data.get('username', '')).strip()
    first_name = str(data.get('first_name', '')).strip()
    last_name = str(data.get('last_name', '')).strip()
    password = str(data.get('password', '')).strip()
    inst_id = data.get('institution_id')
    department = str(data.get('department', '')).strip()

    if not email:
        raise ValidationError('Email address is mandatory.')

    if not username:
        username = email.split('@')[0]

    if User.objects.filter(username=username).exists():
        # Ensure uniqueness by appending 4 random digits
        username = f"{username}_{secrets.randbelow(8999) + 1000}"

    if User.objects.filter(email=email).exists():
        raise ValidationError(f'A user with email "{email}" already exists.')

    if not password:
        alphabet = string.ascii_letters + string.digits + '!@#$%'
        password = ''.join(secrets.choice(alphabet) for _ in range(12))

    institution = None
    if inst_id:
        institution = AdminInstitution.objects.filter(id=int(inst_id)).first()
        if not institution:
            raise ValidationError('Specified institution does not exist.')

    with transaction.atomic():
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            is_active=True,
            is_staff=False,
            is_superuser=False,
        )

        if role == 'student':
            sp = StudentProfile.objects.create(
                user=user,
                institution=institution,
                department=department or 'General',
            )
            sp.ensure_student_id()

        elif role == 'faculty':
            designation = str(data.get('designation', 'Assistant Professor')).strip()
            fp = FacultyProfile.objects.create(
                user=user,
                institution=institution,
                department=department or 'General',
                designation=designation,
            )
            fp.ensure_employee_id()

        elif role == 'admin':
            AdminProfile.objects.create(user=user)
            if institution and not hasattr(institution, 'admin'):
                institution.admin = user
                institution.save(update_fields=['admin'])

    return user, password


def toggle_user_active_status(user_id: int, request_user: User) -> Tuple[User, bool, Dict[str, Any]]:
    """
    Toggle is_active on user with impact preview.
    Prevents deactivating the last super admin.
    """
    target = User.objects.filter(id=user_id).first()
    if not target:
        raise ValidationError('Target user not found.')

    if hasattr(target, 'super_admin_profile'):
        raise ValidationError('Super Admin account state cannot be modified via this endpoint.')

    next_status = not target.is_active

    # Calculate operational impact
    impact = {
        'live_exams_count': 0,
        'in_progress_attempts_count': 0,
    }
    now = timezone.now()
    if hasattr(target, 'faculty_profile'):
        impact['live_exams_count'] = Exam.objects.filter(
            created_by=target,
            status=Exam.Status.PUBLISHED,
            starts_at__lte=now,
            ends_at__gte=now,
        ).count()
    elif hasattr(target, 'student_profile'):
        impact['in_progress_attempts_count'] = StudentAttempt.objects.filter(
            student=target,
            status=StudentAttempt.Status.IN_PROGRESS,
        ).count()

    target.is_active = next_status
    target.save(update_fields=['is_active'])

    return target, next_status, impact


def revoke_user_sessions(user_id: int) -> int:
    """Revoke all outstanding SimpleJWT tokens for target user."""
    target = User.objects.filter(id=user_id).first()
    if not target:
        raise ValidationError('Target user not found.')

    revoked_count = 0
    try:
        from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
        for token in OutstandingToken.objects.filter(user=target):
            _, created = BlacklistedToken.objects.get_or_create(token=token)
            if created:
                revoked_count += 1
    except Exception as exc:
        logger.warning('Could not blacklist tokens for user %s: %s', user_id, exc)

    return revoked_count


def execute_bulk_users_action(
    action: str,
    user_ids: List[int],
    payload: Dict[str, Any],
    request_user: User,
) -> Dict[str, Any]:
    """
    Execute bulk actions atomically with per-row result report.
    Guarantees no super admin account is altered.
    """
    if not user_ids:
        return {'status': 'error', 'message': 'No users selected for bulk action.'}

    # Filter out any super admin accounts
    targets = list(User.objects.filter(id__in=user_ids).exclude(super_admin_profile__isnull=False))
    succeeded = 0
    failed = 0
    errors: List[str] = []

    with transaction.atomic():
        if action == 'activate':
            for u in targets:
                u.is_active = True
                u.save(update_fields=['is_active'])
                succeeded += 1

        elif action == 'deactivate':
            for u in targets:
                u.is_active = False
                u.save(update_fields=['is_active'])
                succeeded += 1

        elif action == 'move_department':
            new_dept = str(payload.get('department', '')).strip()
            reason = str(payload.get('reason', 'Bulk administrative department reassignment')).strip()
            if not new_dept:
                raise ValidationError('Target department name is required for bulk move.')

            for u in targets:
                if hasattr(u, 'student_profile'):
                    stu = u.student_profile
                    stu.department = new_dept
                    stu.save()
                    succeeded += 1
                elif hasattr(u, 'faculty_profile'):
                    fac = u.faculty_profile
                    fac.department = new_dept
                    fac.save()
                    succeeded += 1
                else:
                    failed += 1
                    errors.append(f'User {u.username} (Admin) does not support department reassignment.')

        elif action == 'revoke_sessions':
            for u in targets:
                revoke_user_sessions(u.id)
                succeeded += 1

        else:
            raise ValidationError(f'Unsupported bulk action "{action}".')

    return {
        'status': 'success',
        'action': action,
        'total_selected': len(user_ids),
        'succeeded': succeeded,
        'failed': failed,
        'errors': errors,
    }

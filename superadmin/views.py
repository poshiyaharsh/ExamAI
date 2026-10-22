import csv
import datetime
import logging
import os
import secrets
import shutil
import string
import subprocess
import time
from datetime import timedelta
from django.conf import settings
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import connection, transaction
from django.db.models import Avg, Count, Max, Min, Q
from django.http import Http404, HttpResponse
from django.utils import timezone
import requests
from rest_framework import exceptions, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from admins.models import AdminDepartment, AdminInstitution, AdminProfile, DepartmentChangeAuditLog
from api.models import Exam, PaperGenerationJob, Question, StudentAttempt
from api.utils.departments import DEFAULT_DEPARTMENT_NAMES
from faculty.models import FacultyProfile
from students.models import StudentProfile
from superadmin.alerts import send_super_admin_security_alert
from superadmin.audit import get_client_ip, log_super_admin_action
from superadmin.authentication import SuperAdminAuthentication, generate_super_admin_token
from superadmin.backups import (
    create_database_backup,
    prune_backups,
    restore_backup_on_live_database,
    test_restore_backup,
)
from superadmin.announcements_service import create_and_dispatch_announcement
from superadmin.bulk_import import get_bulk_import_template, validate_and_process_bulk_import
from superadmin.impersonation import create_impersonation_session
from superadmin.institute_service import (
    calculate_institute_usage,
    get_or_create_institute_policy,
    validate_and_save_logo,
)
from superadmin.jobs_service import (
    cancel_paper_generation_job,
    detect_and_cleanup_stuck_jobs,
    get_jobs_summary,
    list_background_jobs,
    retry_paper_generation_job,
)
from superadmin.analytics_service import get_cross_institute_analytics
from superadmin.dpdp_service import (
    dry_run_anonymize_user,
    execute_anonymize_user,
    export_user_data,
    get_data_inventory,
)
from superadmin.ai_service import (
    get_ollama_status_and_sync,
    initiate_model_pull,
    remove_ollama_model,
    set_default_ai_model,
    test_ai_model_connectivity,
    toggle_ai_model_status,
)
from superadmin.notification_service import (
    cancel_scheduled_campaign,
    create_and_send_campaign,
    list_campaigns_paginated,
    preview_campaign_audience,
)
from superadmin.user_service import (
    create_user_record,
    execute_bulk_users_action,
    filter_users_queryset,
    get_user_drawer_details,
    revoke_user_sessions,
    serialize_user_row,
    toggle_user_active_status,
)
from superadmin.exports_service import export_entities_to_csv
from superadmin.logs_service import get_error_summary_grouped, get_system_logs
from superadmin.models import (
    DatabaseBackupRecord,
    DataSubjectRequest,
    InstitutePolicy,
    MaintenanceWindow,
    SuperAdminAuditLog,
    SuperAdminProfile,
    SystemAnnouncement,
    SystemSetting,
)
from superadmin.monitoring import check_system_health, send_deduplicated_alert
from superadmin.permissions_matrix import generate_permissions_matrix
from superadmin.permissions import IsEnrolledSuperAdmin, IsSuperAdmin, RequiresReauth
from superadmin.totp import (
    generate_recovery_codes,
    get_totp_uri,
    verify_and_consume_recovery_code,
    verify_totp,
)

User = get_user_model()
logger = logging.getLogger(__name__)


# ==============================================================================
# 1. SUPER ADMIN AUTHENTICATION VIEWS
# ==============================================================================

class SuperAdminLoginAPIView(APIView):
    """
    Secure login endpoint for the platform Super Admin.
    Enforces progressive lockouts, generic error messages, and 2FA verification.
    """
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        username = str(request.data.get('username', '')).strip()
        password = str(request.data.get('password', ''))
        totp_code = str(request.data.get('totp_code', '')).strip()
        recovery_code = str(request.data.get('recovery_code', '')).strip()

        client_ip = get_client_ip(request)

        # Uniform 404 check if non-superadmin probe or username does not exist
        profile = SuperAdminProfile.objects.filter(user__username=username).select_related('user').first()
        if not profile:
            # Constant-time dummy check to prevent timing attack enumeration
            authenticate(username=username, password=password)
            logger.warning('Failed super admin login attempt from %s for username %s', client_ip, username)
            return Response(
                {'status': 'error', 'message': 'Invalid credentials.'},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        user = profile.user

        # Check account lockout
        if profile.is_locked():
            logger.warning('SuperAdmin login attempted while locked from IP %s', client_ip)
            return Response(
                {
                    'status': 'locked',
                    'message': 'Account is temporarily locked due to multiple failed login attempts. Try again later.',
                    'locked_until': profile.locked_until.isoformat(),
                },
                status=status.HTTP_423_LOCKED,
            )

        # Authenticate password
        authenticated_user = authenticate(username=username, password=password)
        if not authenticated_user or authenticated_user.id != user.id:
            profile.failed_login_attempts += 1
            if profile.failed_login_attempts >= 5:
                profile.locked_until = timezone.now() + timedelta(minutes=15)
                send_super_admin_security_alert(
                    subject='Super Admin Account Locked',
                    message=(
                        f'Your Super Admin account has been temporarily locked for 15 minutes.\n'
                        f'Triggered after 5 consecutive failed login attempts.\n'
                        f'Originating IP: {client_ip}\n'
                        f'Timestamp: {timezone.now().isoformat()}'
                    ),
                )
                log_super_admin_action(
                    request,
                    action='super_admin_locked',
                    target_entity='SuperAdminProfile',
                    target_id=str(profile.id),
                    description=f'Account locked for 15 minutes after 5 failed attempts from {client_ip}',
                )
            profile.save(update_fields=['failed_login_attempts', 'locked_until'])

            log_super_admin_action(
                request,
                action='super_admin_login_failed',
                target_entity='SuperAdminProfile',
                target_id=str(profile.id),
                description=f'Failed password attempt ({profile.failed_login_attempts}/5) from {client_ip}',
            )

            return Response(
                {'status': 'error', 'message': 'Invalid credentials.'},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # If TOTP is not enrolled yet, enter enrollment mode
        if not profile.is_totp_enrolled:
            temp_token = generate_super_admin_token(user)
            totp_uri = get_totp_uri(profile.totp_secret, user.username)
            return Response(
                {
                    'status': 'enrollment_required',
                    'message': 'Two-factor authentication (2FA) enrollment is required.',
                    'totp_secret': profile.totp_secret,
                    'totp_uri': totp_uri,
                    'temp_token': temp_token,
                },
                status=status.HTTP_200_OK,
            )

        # Verify 2FA code or recovery code
        if not totp_code and not recovery_code:
            return Response(
                {'status': '2fa_required', 'message': 'Please provide your 6-digit authenticator code.'},
                status=status.HTTP_200_OK,
            )

        totp_success = False
        recovery_used = False
        matched_step = None

        if totp_code:
            totp_success, matched_step = verify_totp(
                profile.totp_secret, totp_code, window=1, last_used_step=profile.last_totp_step
            )

        if not totp_success and recovery_code:
            valid_rec, updated_hashes = verify_and_consume_recovery_code(
                recovery_code, profile.recovery_codes_hash
            )
            if valid_rec:
                totp_success = True
                recovery_used = True
                profile.recovery_codes_hash = updated_hashes
                profile.save(update_fields=['recovery_codes_hash'])
                send_super_admin_security_alert(
                    subject='One-Time Recovery Code Used',
                    message=(
                        f'A one-time recovery code was used to log into your Super Admin account.\n'
                        f'Remaining recovery codes: {len(updated_hashes)}\n'
                        f'Originating IP: {client_ip}\n'
                        f'Timestamp: {timezone.now().isoformat()}'
                    ),
                )
                log_super_admin_action(
                    request,
                    action='recovery_code_used',
                    target_entity='SuperAdminProfile',
                    target_id=str(profile.id),
                    description=f'Recovery code consumed. Remaining: {len(updated_hashes)}',
                )

        if not totp_success:
            profile.failed_login_attempts += 1
            profile.save(update_fields=['failed_login_attempts'])
            log_super_admin_action(
                request,
                action='2fa_verification_failed',
                target_entity='SuperAdminProfile',
                target_id=str(profile.id),
                description=f'Failed 2FA verification attempt from {client_ip}',
            )
            return Response(
                {'status': 'error', 'message': 'Invalid two-factor authentication code or code already used.'},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # Successful Login
        session_id = secrets.token_hex(16)
        profile.failed_login_attempts = 0
        profile.locked_until = None
        profile.last_login_at = timezone.now()
        profile.last_login_ip = client_ip
        profile.last_reauth_at = timezone.now()  # Fresh login counts as re-authenticated
        profile.last_activity_at = timezone.now()
        profile.active_session_id = session_id
        if matched_step:
            profile.last_totp_step = matched_step

        profile.save(update_fields=[
            'failed_login_attempts', 'locked_until', 'last_login_at', 'last_login_ip',
            'last_reauth_at', 'last_activity_at', 'active_session_id', 'last_totp_step',
        ])

        token = generate_super_admin_token(user, session_id=session_id)

        log_super_admin_action(
            request,
            action='super_admin_login_success',
            target_entity='SuperAdminProfile',
            target_id=str(profile.id),
            description=f'Successful super admin login from {client_ip}',
        )

        send_super_admin_security_alert(
            subject='Successful Super Admin Login',
            message=(
                f'Successful Super Admin login detected.\n'
                f'Username: {user.username}\n'
                f'IP Address: {client_ip}\n'
                f'User-Agent: {request.META.get("HTTP_USER_AGENT", "Unknown")}\n'
                f'Timestamp: {timezone.now().isoformat()}'
            ),
        )

        res = Response(
            {
                'status': 'success',
                'message': 'Authenticated successfully as Super Admin.',
                'token': token,
                'user': {
                    'username': user.username,
                    'email': user.email,
                    'is_totp_enrolled': profile.is_totp_enrolled,
                    'last_login_at': profile.last_login_at.isoformat() if profile.last_login_at else None,
                },
            },
            status=status.HTTP_200_OK,
        )

        cookie_name = '__Host-examai_sa_session' if not settings.DEBUG else 'examai_sa_session'
        res.set_cookie(
            key=cookie_name,
            value=token,
            max_age=getattr(settings, 'SUPER_ADMIN_SESSION_AGE', 900),
            httponly=True,
            secure=not settings.DEBUG,
            samesite='Strict',
            path='/',
        )

        return res


class SuperAdmin2FAEnrollAPIView(APIView):
    """
    Finalize 2FA enrollment by confirming the initial code.
    """
    authentication_classes = [SuperAdminAuthentication]
    permission_classes = [IsSuperAdmin]

    def post(self, request):
        code = str(request.data.get('totp_code', '')).strip()
        profile = request.user.super_admin_profile

        if profile.is_totp_enrolled:
            return Response(
                {'status': 'already_enrolled', 'message': '2FA is already enrolled.'},
                status=status.HTTP_200_OK,
            )

        valid_totp, matched_step = verify_totp(
            profile.totp_secret, code, window=1, last_used_step=profile.last_totp_step
        )
        if not valid_totp:
            return Response(
                {'status': 'error', 'message': 'Verification code does not match. Check your authenticator app time.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        profile.is_totp_enrolled = True
        profile.last_reauth_at = timezone.now()
        profile.last_activity_at = timezone.now()
        if matched_step:
            profile.last_totp_step = matched_step
        profile.save(update_fields=['is_totp_enrolled', 'last_reauth_at', 'last_activity_at', 'last_totp_step'])

        log_super_admin_action(
            request,
            action='2fa_enrollment_completed',
            target_entity='SuperAdminProfile',
            target_id=str(profile.id),
            description='Mandatory 2FA enrollment completed successfully.',
        )

        return Response(
            {'status': 'success', 'message': '2FA enrollment completed successfully. Your account is fully secured.'},
            status=status.HTTP_200_OK,
        )


class SuperAdminReauthAPIView(APIView):
    """
    Step-up re-authentication required before performing dangerous operations.
    Validates password + TOTP and extends the re-auth window for 5 minutes.
    """
    authentication_classes = [SuperAdminAuthentication]
    permission_classes = [IsSuperAdmin, IsEnrolledSuperAdmin]

    def post(self, request):
        password = str(request.data.get('password', ''))
        totp_code = str(request.data.get('totp_code', '')).strip()

        user = request.user
        profile = user.super_admin_profile

        if not user.check_password(password):
            log_super_admin_action(
                request,
                action='reauth_failed_password',
                target_entity='SuperAdminProfile',
                target_id=str(profile.id),
                description='Re-authentication rejected: wrong password.',
            )
            return Response({'status': 'error', 'message': 'Password verification failed.'}, status=status.HTTP_401_UNAUTHORIZED)

        valid_totp, matched_step = verify_totp(
            profile.totp_secret, totp_code, window=1, last_used_step=profile.last_totp_step
        )
        if not valid_totp:
            log_super_admin_action(
                request,
                action='reauth_failed_totp',
                target_entity='SuperAdminProfile',
                target_id=str(profile.id),
                description='Re-authentication rejected: invalid TOTP or code already used.',
            )
            return Response({'status': 'error', 'message': '2FA verification code invalid or already used.'}, status=status.HTTP_401_UNAUTHORIZED)

        profile.last_reauth_at = timezone.now()
        profile.last_activity_at = timezone.now()
        if matched_step:
            profile.last_totp_step = matched_step
        profile.save(update_fields=['last_reauth_at', 'last_activity_at', 'last_totp_step'])

        log_super_admin_action(
            request,
            action='reauth_success',
            target_entity='SuperAdminProfile',
            target_id=str(profile.id),
            description='Super Admin step-up re-authentication successful.',
        )

        return Response({'status': 'success', 'message': 'Re-authentication verified.'}, status=status.HTTP_200_OK)


class SuperAdminLogoutAPIView(APIView):
    """Log out super admin and invalidate session cookie and active JWT session."""
    authentication_classes = [SuperAdminAuthentication]
    permission_classes = [IsSuperAdmin]

    def post(self, request):
        profile = getattr(request.user, 'super_admin_profile', None)
        if profile:
            profile.active_session_id = ''
            profile.save(update_fields=['active_session_id'])
        log_super_admin_action(request, action='super_admin_logout', description='Super admin logged out.')
        res = Response({'status': 'success', 'message': 'Successfully logged out.'}, status=status.HTTP_200_OK)
        for cookie_name in ['__Host-examai_sa_session', 'examai_sa_session']:
            res.delete_cookie(cookie_name, path='/')
        return res


class SuperAdminMeAPIView(APIView):
    """Retrieve super admin status and active session metadata."""
    authentication_classes = [SuperAdminAuthentication]
    permission_classes = [IsSuperAdmin]

    def get(self, request):
        profile = request.user.super_admin_profile
        return Response(
            {
                'status': 'success',
                'user': {
                    'username': request.user.username,
                    'email': request.user.email,
                    'is_totp_enrolled': profile.is_totp_enrolled,
                    'last_login_at': profile.last_login_at.isoformat() if profile.last_login_at else None,
                    'last_login_ip': profile.last_login_ip,
                    'is_reauth_valid': profile.is_reauth_valid(),
                    'remaining_recovery_codes': len(profile.recovery_codes_hash),
                },
            },
            status=status.HTTP_200_OK,
        )


# ==============================================================================
# 2. DASHBOARD & SYSTEM HEALTH
# ==============================================================================

class SuperAdminDashboardAPIView(APIView):
    """
    Global aggregates across all institutes, platform health checks, and recent audit logs.
    """
    authentication_classes = [SuperAdminAuthentication]
    permission_classes = [IsSuperAdmin, IsEnrolledSuperAdmin]

    def get(self, request):
        now = timezone.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        # 1. Totals across institutes
        total_institutes = AdminInstitution.objects.count()
        active_institutes = AdminInstitution.objects.filter(status=AdminInstitution.STATUS_ACTIVE).count()
        suspended_institutes = total_institutes - active_institutes

        total_departments = AdminDepartment.objects.values('department_name').distinct().count()

        total_faculty = FacultyProfile.objects.count()
        active_faculty = FacultyProfile.objects.filter(user__is_active=True).count()

        total_students = StudentProfile.objects.count()
        active_students = StudentProfile.objects.filter(user__is_active=True).count()

        total_exams = Exam.objects.count()
        exams_by_status = dict(Exam.objects.values('status').annotate(cnt=Count('id')).values_list('status', 'cnt'))

        live_exams_now = Exam.objects.filter(
            status=Exam.Status.PUBLISHED,
            starts_at__lte=now,
            ends_at__gte=now,
        ).count()

        attempts_today = StudentAttempt.objects.filter(started_at__gte=today_start).count()
        shortfall_exams = Exam.objects.filter(marks_shortfall__gt=0).count()
        failed_generation_jobs = PaperGenerationJob.objects.filter(status='failed').count()
        violations_today = StudentAttempt.objects.filter(started_at__gte=today_start, violation_count__gt=0).count()

        # 2. System Health
        # Database ping & latency
        db_healthy = True
        db_latency_ms = 0
        try:
            t0 = time.time()
            with connection.cursor() as cursor:
                cursor.execute('SELECT 1')
                cursor.fetchone()
            db_latency_ms = round((time.time() - t0) * 1000, 2)
        except Exception as exc:
            db_healthy = False
            logger.error('DB ping failed: %s', exc)

        # Ollama check
        ollama_url = getattr(settings, 'OLLAMA_BASE_URL', 'http://127.0.0.1:11434').rstrip('/')
        ollama_reachable = False
        installed_models = []
        try:
            resp = requests.get(f'{ollama_url}/api/tags', timeout=2)
            if resp.status_code == 200:
                ollama_reachable = True
                installed_models = [m.get('name') for m in resp.json().get('models', []) if m.get('name')]
        except Exception:
            ollama_reachable = False

        # Disk space
        total_disk_gb = 0
        free_disk_gb = 0
        try:
            usage = shutil.disk_usage(str(settings.BASE_DIR))
            total_disk_gb = round(usage.total / (1024 ** 3), 1)
            free_disk_gb = round(usage.free / (1024 ** 3), 1)
        except Exception:
            pass

        # 3. Recent Audit Events
        recent_audits = list(
            SuperAdminAuditLog.objects.order_by('-created_at')[:10].values(
                'id', 'actor_username', 'action', 'target_entity', 'description', 'ip_address', 'created_at'
            )
        )

        return Response(
            {
                'status': 'success',
                'totals': {
                    'total_institutes': total_institutes,
                    'active_institutes': active_institutes,
                    'suspended_institutes': suspended_institutes,
                    'total_departments': total_departments,
                    'total_faculty': total_faculty,
                    'active_faculty': active_faculty,
                    'total_students': total_students,
                    'active_students': active_students,
                    'total_exams': total_exams,
                    'exams_by_status': exams_by_status,
                    'live_exams_now': live_exams_now,
                    'attempts_today': attempts_today,
                    'shortfall_exams': shortfall_exams,
                    'failed_generation_jobs': failed_generation_jobs,
                    'violations_today': violations_today,
                },
                'health': {
                    'database': {'status': 'healthy' if db_healthy else 'down', 'latency_ms': db_latency_ms},
                    'ollama': {
                        'reachable': ollama_reachable,
                        'base_url': ollama_url,
                        'installed_models': installed_models,
                        'default_model': getattr(settings, 'OLLAMA_MODEL', 'qwen2.5:3b-instruct'),
                    },
                    'disk': {'total_gb': total_disk_gb, 'free_gb': free_disk_gb},
                    'active_jobs': PaperGenerationJob.objects.filter(status__in=['pending', 'running']).count(),
                },
                'recent_audits': recent_audits,
            },
            status=status.HTTP_200_OK,
        )


# ==============================================================================
# 3. INSTITUTES MANAGEMENT
# ==============================================================================

class SuperAdminInstituteListCreateAPIView(APIView):
    authentication_classes = [SuperAdminAuthentication]
    permission_classes = [IsSuperAdmin, IsEnrolledSuperAdmin]

    def get(self, request):
        search = str(request.query_params.get('search', '')).strip()
        status_filter = str(request.query_params.get('status', 'all')).strip().lower()
        page_num = int(request.query_params.get('page', 1))
        page_size = int(request.query_params.get('page_size', 10))
        if page_size not in [10, 25, 50, 100]:
            page_size = 10

        qs = AdminInstitution.objects.all().select_related('admin').order_by('-created_at')

        if search:
            qs = qs.filter(
                Q(institution_name__icontains=search)
                | Q(institution_code__icontains=search)
                | Q(city__icontains=search)
            )

        if status_filter in ['active', 'suspended']:
            qs = qs.filter(status=status_filter)

        paginator = Paginator(qs, page_size)
        page_obj = paginator.get_page(page_num)

        items = []
        for inst in page_obj:
            items.append({
                'id': inst.id,
                'name': inst.institution_name,
                'code': inst.institution_code,
                'status': inst.status,
                'city': inst.city,
                'state': inst.state,
                'admin_email': inst.admin.email if inst.admin else 'Unassigned',
                'admin_name': f'{inst.admin.first_name} {inst.admin.last_name}'.strip() if inst.admin else 'Unassigned',
                'faculty_count': inst.faculty_profiles.count(),
                'students_count': inst.student_profiles.count(),
                'exams_count': inst.exams.count(),
                'departments_count': inst.departments.count(),
                'created_at': inst.created_at.isoformat() if inst.created_at else None,
            })

        return Response(
            {
                'status': 'success',
                'data': items,
                'pagination': {
                    'page': page_obj.number,
                    'page_size': page_size,
                    'total_count': paginator.count,
                    'total_pages': paginator.num_pages,
                    'has_next': page_obj.has_next(),
                    'has_prev': page_obj.has_previous(),
                },
            },
            status=status.HTTP_200_OK,
        )

    def post(self, request):
        profile = request.user.super_admin_profile
        if not profile.is_reauth_valid():
            raise exceptions.PermissionDenied({'status': 'reauth_required', 'message': 'Re-authentication required.'})

        name = str(request.data.get('institution_name', '')).strip()
        admin_email = str(request.data.get('admin_email', '')).strip().lower()
        admin_first_name = str(request.data.get('admin_first_name', '')).strip()
        admin_last_name = str(request.data.get('admin_last_name', '')).strip()
        admin_password = str(request.data.get('admin_password', ''))
        city = str(request.data.get('city', '')).strip()
        state = str(request.data.get('state', '')).strip()

        if not name or not admin_email or not admin_password:
            return Response({'status': 'error', 'message': 'Institution name, admin email, and password are required.'}, status=status.HTTP_400_BAD_REQUEST)

        if User.objects.filter(username=admin_email).exists():
            return Response({'status': 'error', 'message': f'A user with email "{admin_email}" already exists.'}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            admin_user = User.objects.create_user(
                username=admin_email,
                email=admin_email,
                first_name=admin_first_name,
                last_name=admin_last_name,
                password=admin_password,
            )
            AdminProfile.objects.create(user=admin_user)

            inst = AdminInstitution.objects.create(
                admin=admin_user,
                institution_name=name,
                city=city,
                state=state,
            )

            # Auto-seed standard departments
            AdminDepartment.objects.bulk_create([
                AdminDepartment(institution=inst, department_name=dname)
                for dname in DEFAULT_DEPARTMENT_NAMES
            ])

            log_super_admin_action(
                request,
                action='institution_created',
                target_entity='AdminInstitution',
                target_id=str(inst.id),
                description=f'Created institute "{name}" ({inst.institution_code}) with admin {admin_email}.',
                after_state={'id': inst.id, 'name': name, 'code': inst.institution_code, 'admin_email': admin_email},
            )

        return Response(
            {
                'status': 'success',
                'message': f'Institution "{name}" created successfully.',
                'data': {'id': inst.id, 'name': name, 'code': inst.institution_code},
            },
            status=status.HTTP_201_CREATED,
        )


class SuperAdminInstituteDetailAPIView(APIView):
    authentication_classes = [SuperAdminAuthentication]
    permission_classes = [IsSuperAdmin, IsEnrolledSuperAdmin]

    def get(self, request, institute_id):
        inst = AdminInstitution.objects.filter(id=institute_id).select_related('admin').first()
        if not inst:
            raise Http404()

        depts = list(inst.departments.values('id', 'department_name'))
        data = {
            'id': inst.id,
            'name': inst.institution_name,
            'code': inst.institution_code,
            'status': inst.status,
            'city': inst.city,
            'state': inst.state,
            'address': inst.address,
            'phone': inst.phone,
            'website': inst.website,
            'admin': {
                'id': inst.admin.id if inst.admin else None,
                'email': inst.admin.email if inst.admin else None,
                'name': f'{inst.admin.first_name} {inst.admin.last_name}'.strip() if inst.admin else 'Unassigned',
            },
            'departments': depts,
            'stats': {
                'faculty_count': inst.faculty_profiles.count(),
                'students_count': inst.student_profiles.count(),
                'exams_count': inst.exams.count(),
            },
            'created_at': inst.created_at.isoformat() if inst.created_at else None,
        }
        return Response({'status': 'success', 'data': data}, status=status.HTTP_200_OK)

    def put(self, request, institute_id):
        inst = AdminInstitution.objects.filter(id=institute_id).first()
        if not inst:
            raise Http404()

        before = {'name': inst.institution_name, 'city': inst.city, 'phone': inst.phone}
        inst.institution_name = request.data.get('name', inst.institution_name).strip()
        inst.city = request.data.get('city', inst.city).strip()
        inst.state = request.data.get('state', inst.state).strip()
        inst.address = request.data.get('address', inst.address).strip()
        inst.phone = request.data.get('phone', inst.phone).strip()
        inst.website = request.data.get('website', inst.website).strip()
        inst.save()

        log_super_admin_action(
            request,
            action='institution_updated',
            target_entity='AdminInstitution',
            target_id=str(inst.id),
            description=f'Updated details for institute {inst.institution_code}.',
            before_state=before,
            after_state={'name': inst.institution_name, 'city': inst.city, 'phone': inst.phone},
        )

        return Response({'status': 'success', 'message': 'Institution details updated.'}, status=status.HTTP_200_OK)


class SuperAdminInstituteToggleStatusAPIView(APIView):
    """
    Suspend or activate an entire institution. Requires step-up re-authentication.
    """
    authentication_classes = [SuperAdminAuthentication]
    permission_classes = [IsSuperAdmin, IsEnrolledSuperAdmin, RequiresReauth]

    def post(self, request, institute_id):
        inst = AdminInstitution.objects.filter(id=institute_id).first()
        if not inst:
            raise Http404()

        new_status = AdminInstitution.STATUS_SUSPENDED if inst.status == AdminInstitution.STATUS_ACTIVE else AdminInstitution.STATUS_ACTIVE
        reason = str(request.data.get('reason', '')).strip()

        before_status = inst.status
        inst.status = new_status
        inst.save(update_fields=['status'])

        # Invalidate cached tenant sessions
        try:
            from api.tenant import bump_tenant_cache_version
            bump_tenant_cache_version(inst.id)
        except Exception:
            pass

        action_name = 'institution_suspended' if new_status == AdminInstitution.STATUS_SUSPENDED else 'institution_activated'
        log_super_admin_action(
            request,
            action=action_name,
            target_entity='AdminInstitution',
            target_id=str(inst.id),
            description=f'{inst.institution_name} status toggled to {new_status}. Reason: {reason or "N/A"}',
            before_state={'status': before_status},
            after_state={'status': new_status, 'reason': reason},
        )

        return Response(
            {
                'status': 'success',
                'message': f'Institution "{inst.institution_name}" has been {new_status}.',
                'data': {'id': inst.id, 'status': new_status},
            },
            status=status.HTTP_200_OK,
        )


# ==============================================================================
# 4. GLOBAL USERS DIRECTORY
# ==============================================================================

class SuperAdminUserListAPIView(APIView):
    """
    Role-separated directory for students, faculty, and admins across all institutions.
    """
    authentication_classes = [SuperAdminAuthentication]
    permission_classes = [IsSuperAdmin, IsEnrolledSuperAdmin]

    def get(self, request):
        role_param = str(request.query_params.get('role', 'student')).strip().lower()
        if role_param not in ('student', 'faculty', 'admin'):
            role_param = 'student'

        qs, tab_counts = filter_users_queryset(request.query_params)

        page_num = int(request.query_params.get('page', 1))
        page_size = int(request.query_params.get('page_size', 10))
        if page_size not in [10, 25, 50, 100]:
            page_size = 10

        paginator = Paginator(qs, page_size)
        page_obj = paginator.get_page(page_num)

        items = [serialize_user_row(u, role_param) for u in page_obj]

        return Response(
            {
                'status': 'success',
                'data': items,
                'counts': tab_counts,
                'pagination': {
                    'page': page_obj.number,
                    'page_size': page_size,
                    'total_count': paginator.count,
                    'total_pages': paginator.num_pages,
                    'has_next': page_obj.has_next(),
                    'has_prev': page_obj.has_previous(),
                },
            },
            status=status.HTTP_200_OK,
        )


class SuperAdminUserDetailDrawerAPIView(APIView):
    """
    Returns comprehensive profile, login history, activity summary, and sent notifications.
    """
    authentication_classes = [SuperAdminAuthentication]
    permission_classes = [IsSuperAdmin, IsEnrolledSuperAdmin]

    def get(self, request, user_id):
        try:
            drawer_data = get_user_drawer_details(user_id)
            return Response({'status': 'success', 'data': drawer_data}, status=status.HTTP_200_OK)
        except ValidationError as e:
            msg = e.message if hasattr(e, 'message') else str(e)
            return Response({'status': 'error', 'message': msg}, status=status.HTTP_404_NOT_FOUND)


class SuperAdminUserCreateAPIView(APIView):
    """
    Create Student, Faculty, or Admin user. Super Admin creation is strictly prohibited.
    """
    authentication_classes = [SuperAdminAuthentication]
    permission_classes = [IsSuperAdmin, IsEnrolledSuperAdmin]

    def post(self, request):
        role = str(request.data.get('role', '')).strip().lower()
        if role == 'admin':
            profile = request.user.super_admin_profile
            if not profile.is_reauth_valid():
                raise exceptions.PermissionDenied({'status': 'reauth_required', 'message': 'Re-authentication required to create an Institute Admin.'})

        try:
            new_user, raw_password = create_user_record(request.data, request.user)
            log_super_admin_action(
                request,
                action='user_created',
                target_entity='User',
                target_id=str(new_user.id),
                description=f'Created new {role} user "{new_user.username}" ({new_user.email})',
                after_state={'username': new_user.username, 'email': new_user.email, 'role': role},
            )
            return Response(
                {
                    'status': 'success',
                    'message': f'User "{new_user.username}" created successfully.',
                    'user': {
                        'id': new_user.id,
                        'username': new_user.username,
                        'email': new_user.email,
                        'role': role,
                    },
                    'temporary_password': raw_password,
                },
                status=status.HTTP_201_CREATED,
            )
        except ValidationError as e:
            msg = e.message if hasattr(e, 'message') else str(e)
            return Response({'status': 'error', 'message': msg}, status=status.HTTP_400_BAD_REQUEST)


class SuperAdminUserUpdateProfileAPIView(APIView):
    """
    Update basic user profile (first_name, last_name, email).
    Department/institution is strictly immutable here (must use transfer endpoint).
    """
    authentication_classes = [SuperAdminAuthentication]
    permission_classes = [IsSuperAdmin, IsEnrolledSuperAdmin, RequiresReauth]

    def post(self, request, user_id):
        target_user = User.objects.filter(id=user_id).first()
        if not target_user or hasattr(target_user, 'super_admin_profile'):
            raise Http404()

        email = str(request.data.get('email', '')).strip().lower()
        first_name = str(request.data.get('first_name', '')).strip()
        last_name = str(request.data.get('last_name', '')).strip()

        if email and email != target_user.email:
            if User.objects.filter(email=email).exclude(id=target_user.id).exists():
                return Response({'status': 'error', 'message': f'Email "{email}" is already in use.'}, status=status.HTTP_400_BAD_REQUEST)
            target_user.email = email

        if first_name:
            target_user.first_name = first_name
        if last_name:
            target_user.last_name = last_name

        target_user.save()

        log_super_admin_action(
            request,
            action='user_profile_updated',
            target_entity='User',
            target_id=str(target_user.id),
            description=f'Updated profile details for {target_user.username}',
            after_state={'email': target_user.email, 'first_name': target_user.first_name, 'last_name': target_user.last_name},
        )

        return Response({'status': 'success', 'message': 'Profile updated successfully.'}, status=status.HTTP_200_OK)


class SuperAdminUserToggleActiveAPIView(APIView):
    """
    Activate or deactivate user account with impact assessment.
    """
    authentication_classes = [SuperAdminAuthentication]
    permission_classes = [IsSuperAdmin, IsEnrolledSuperAdmin]

    def post(self, request, user_id):
        try:
            target, next_status, impact = toggle_user_active_status(user_id, request.user)
            verb = 'activated' if next_status else 'deactivated'

            log_super_admin_action(
                request,
                action=f'user_{verb}',
                target_entity='User',
                target_id=str(target.id),
                description=f'Super Admin {verb} user {target.username} ({target.email}). Impact: {impact}',
                after_state={'is_active': next_status, 'impact': impact},
            )

            return Response(
                {
                    'status': 'success',
                    'message': f'User "{target.username}" has been {verb}.',
                    'is_active': next_status,
                    'impact': impact,
                },
                status=status.HTTP_200_OK,
            )
        except ValidationError as e:
            msg = e.message if hasattr(e, 'message') else str(e)
            return Response({'status': 'error', 'message': msg}, status=status.HTTP_400_BAD_REQUEST)


class SuperAdminUserRevokeSessionsAPIView(APIView):
    """
    Force logout / revoke all active sessions for a user.
    """
    authentication_classes = [SuperAdminAuthentication]
    permission_classes = [IsSuperAdmin, IsEnrolledSuperAdmin, RequiresReauth]

    def post(self, request, user_id):
        target = User.objects.filter(id=user_id).first()
        if not target or hasattr(target, 'super_admin_profile'):
            raise Http404()

        revoked_count = revoke_user_sessions(user_id)
        log_super_admin_action(
            request,
            action='user_sessions_revoked',
            target_entity='User',
            target_id=str(target.id),
            description=f'Revoked all active sessions for user {target.username} ({revoked_count} tokens blacklisted)',
        )

        return Response(
            {
                'status': 'success',
                'message': f'Revoked {revoked_count} active session(s) for user "{target.username}".',
            },
            status=status.HTTP_200_OK,
        )


class SuperAdminUserBulkActionAPIView(APIView):
    """
SuperAdminBulkActionAPIView = SuperAdminUserBulkActionAPIView
    Atomic bulk operations on selected users.
    Risky actions (deactivate, move_department) require fresh step-up re-authentication.
    """
    authentication_classes = [SuperAdminAuthentication]
    permission_classes = [IsSuperAdmin, IsEnrolledSuperAdmin]

    def post(self, request):
        action = str(request.data.get('action', '')).strip().lower()
        user_ids = request.data.get('user_ids', [])
        select_all = bool(request.data.get('select_all', False))
        filters = request.data.get('filters', {})
        payload = request.data.get('payload', {})

        if select_all:
            qs, _ = filter_users_queryset(filters)
            user_ids = list(qs.values_list('id', flat=True))

        if not user_ids:
            return Response({'status': 'error', 'message': 'No users selected.'}, status=status.HTTP_400_BAD_REQUEST)

        # Risky actions mandate reauth
        if action in ('deactivate', 'move_department'):
            profile = request.user.super_admin_profile
            if not profile.is_reauth_valid():
                raise exceptions.PermissionDenied({'status': 'reauth_required', 'message': f'Re-authentication required to bulk {action} users.'})

        try:
            result = execute_bulk_users_action(action, user_ids, payload, request.user)
            log_super_admin_action(
                request,
                action=f'bulk_users_{action}',
                target_entity='User',
                target_id=f'{len(user_ids)}_users',
                description=f'Bulk {action} executed on {len(user_ids)} users. Result: {result["succeeded"]} succeeded, {result["failed"]} failed.',
                after_state=result,
            )
            return Response(result, status=status.HTTP_200_OK)
        except ValidationError as e:
            msg = e.message if hasattr(e, 'message') else str(e)
            return Response({'status': 'error', 'message': msg}, status=status.HTTP_400_BAD_REQUEST)


class SuperAdminUserResetPasswordAPIView(APIView):
    """
    Administrative password reset. Requires step-up re-authentication.
    """
    authentication_classes = [SuperAdminAuthentication]
    permission_classes = [IsSuperAdmin, IsEnrolledSuperAdmin, RequiresReauth]

    def post(self, request, user_id):
        target_user = User.objects.filter(id=user_id).first()
        if not target_user:
            raise Http404()

        if hasattr(target_user, 'super_admin_profile'):
            raise exceptions.PermissionDenied('Cannot reset Super Admin password via this endpoint.')

        new_password = str(request.data.get('new_password', '')).strip()
        reason = str(request.data.get('reason', '')).strip()

        if not new_password:
            # Auto-generate secure 12-char password
            alphabet = string.ascii_letters + string.digits + '!@#$%'
            new_password = ''.join(secrets.choice(alphabet) for _ in range(12))

        target_user.set_password(new_password)
        target_user.save(update_fields=['password'])

        log_super_admin_action(
            request,
            action='user_password_reset',
            target_entity='User',
            target_id=str(target_user.id),
            description=f'Super Admin reset password for {target_user.email}. Reason: {reason or "Administrative request"}',
            after_state={'username': target_user.username, 'email': target_user.email, 'reason': reason},
        )

        return Response(
            {
                'status': 'success',
                'message': f'Password for {target_user.email} reset successfully.',
                'temporary_password': new_password,
            },
            status=status.HTTP_200_OK,
        )


class SuperAdminUserTransferAPIView(APIView):
    """
    Transfer student or faculty across institutions or departments.
    Requires step-up re-authentication and leaves a permanent audit trail.
    """
    authentication_classes = [SuperAdminAuthentication]
    permission_classes = [IsSuperAdmin, IsEnrolledSuperAdmin, RequiresReauth]

    def post(self, request, user_id):
        target_user = User.objects.filter(id=user_id).first()
        if not target_user:
            raise Http404()

        new_inst_id = request.data.get('institution_id')
        new_department = str(request.data.get('department', '')).strip()
        reason = str(request.data.get('reason', '')).strip()

        if not new_department or not reason:
            return Response({'status': 'error', 'message': 'New department and transfer justification reason are mandatory.'}, status=status.HTTP_400_BAD_REQUEST)

        new_inst = None
        if new_inst_id:
            new_inst = AdminInstitution.objects.filter(id=int(new_inst_id)).first()
            if not new_inst:
                return Response({'status': 'error', 'message': 'Target institution does not exist.'}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            before_dept = 'Unassigned'
            before_inst = 'Unassigned'

            if hasattr(target_user, 'faculty_profile'):
                fac = target_user.faculty_profile
                before_dept = fac.department
                before_inst = fac.institution.institution_code if fac.institution else 'None'
                fac.department = new_department
                if new_inst:
                    fac.institution = new_inst
                fac.save()

            elif hasattr(target_user, 'student_profile'):
                stu = target_user.student_profile
                before_dept = stu.department
                before_inst = stu.institution.institution_code if stu.institution else 'None'
                stu.department = new_department
                if new_inst:
                    stu.institution = new_inst
                stu.save()

            else:
                return Response({'status': 'error', 'message': 'Only faculty and student profiles support department transfers.'}, status=status.HTTP_400_BAD_REQUEST)

            # Record in existing DepartmentChangeAuditLog
            DepartmentChangeAuditLog.objects.create(
                user=target_user,
                changed_by=request.user,
                old_department=before_dept,
                new_department=new_department,
                reason=f'[SUPER ADMIN TRANSFER] {reason}',
            )

            # Record in SuperAdminAuditLog
            log_super_admin_action(
                request,
                action='user_transfer',
                target_entity='User',
                target_id=str(target_user.id),
                description=f'Transferred user {target_user.email} from {before_inst}:{before_dept} to {new_inst.institution_code if new_inst else before_inst}:{new_department}. Reason: {reason}',
                before_state={'department': before_dept, 'institution': before_inst},
                after_state={'department': new_department, 'institution': new_inst.institution_code if new_inst else before_inst, 'reason': reason},
            )

        return Response(
            {
                'status': 'success',
                'message': f'User {target_user.email} transferred successfully to {new_department}.',
            },
            status=status.HTTP_200_OK,
        )


# ==============================================================================
# 5. GLOBAL EXAMS OVERVIEW
# ==============================================================================

class SuperAdminExamListAPIView(APIView):
    authentication_classes = [SuperAdminAuthentication]
    permission_classes = [IsSuperAdmin, IsEnrolledSuperAdmin]

    def get(self, request):
        status_filter = str(request.query_params.get('status', 'all')).strip().lower()
        inst_id = request.query_params.get('institution_id')
        search = str(request.query_params.get('search', '')).strip()
        shortfall_only = str(request.query_params.get('shortfall_only', '')).lower() == 'true'

        page_num = int(request.query_params.get('page', 1))
        page_size = int(request.query_params.get('page_size', 10))
        if page_size not in [10, 25, 50, 100]:
            page_size = 10

        qs = Exam.objects.all().select_related('institution', 'created_by').order_by('-created_at')

        if status_filter != 'all':
            qs = qs.filter(status=status_filter)

        if shortfall_only:
            qs = qs.filter(marks_shortfall__gt=0)

        if inst_id:
            try:
                qs = qs.filter(institution_id=int(inst_id))
            except (ValueError, TypeError):
                pass

        if search:
            qs = qs.filter(
                Q(title__icontains=search)
                | Q(subject__icontains=search)
                | Q(department__icontains=search)
                | Q(institution__institution_name__icontains=search)
            )

        paginator = Paginator(qs, page_size)
        page_obj = paginator.get_page(page_num)

        items = []
        for e in page_obj:
            items.append({
                'id': e.id,
                'title': e.title,
                'subject': e.subject,
                'department': e.department,
                'institution': {
                    'id': e.institution.id if e.institution else None,
                    'name': e.institution.institution_name if e.institution else 'Unassigned',
                },
                'status': e.status,
                'duration_minutes': e.duration_minutes,
                'total_marks': e.total_marks,
                'target_total_marks': e.target_total_marks,
                'marks_shortfall': e.marks_shortfall,
                'starts_at': e.starts_at.isoformat() if e.starts_at else None,
                'ends_at': e.ends_at.isoformat() if e.ends_at else None,
                'is_immutable': e.is_immutable,
                'created_by': e.created_by.username if e.created_by else 'Unknown',
                'created_at': e.created_at.isoformat() if e.created_at else None,
            })

        return Response(
            {
                'status': 'success',
                'data': items,
                'pagination': {
                    'page': page_obj.number,
                    'page_size': page_size,
                    'total_count': paginator.count,
                    'total_pages': paginator.num_pages,
                    'has_next': page_obj.has_next(),
                    'has_prev': page_obj.has_previous(),
                },
            },
            status=status.HTTP_200_OK,
        )


class SuperAdminExamForceCloseAPIView(APIView):
    """
    Force-close a live exam. Requires step-up re-authentication and audit log.
    """
    authentication_classes = [SuperAdminAuthentication]
    permission_classes = [IsSuperAdmin, IsEnrolledSuperAdmin, RequiresReauth]

    def post(self, request, exam_id):
        exam = Exam.objects.filter(id=exam_id).first()
        if not exam:
            raise Http404()

        reason = str(request.data.get('reason', '')).strip()
        if not reason:
            return Response({'status': 'error', 'message': 'Justification reason is required to force-close an exam.'}, status=status.HTTP_400_BAD_REQUEST)

        before_status = exam.status
        exam.status = Exam.Status.CLOSED
        exam.save(update_fields=['status'])

        # Auto-submit all currently ongoing student attempts for this exam
        ongoing_attempts = StudentAttempt.objects.filter(exam=exam, status=StudentAttempt.Status.IN_PROGRESS)
        closed_count = ongoing_attempts.count()
        ongoing_attempts.update(status=StudentAttempt.Status.SUBMITTED, submitted_at=timezone.now())

        log_super_admin_action(
            request,
            action='exam_force_closed',
            target_entity='Exam',
            target_id=str(exam.id),
            description=f'Force-closed live exam "{exam.title}" (ID: {exam.id}). {closed_count} ongoing attempts submitted. Reason: {reason}',
            before_state={'status': before_status},
            after_state={'status': Exam.Status.CLOSED, 'closed_attempts': closed_count, 'reason': reason},
        )

        return Response(
            {
                'status': 'success',
                'message': f'Exam "{exam.title}" has been closed. {closed_count} ongoing attempt(s) submitted.',
            },
            status=status.HTTP_200_OK,
        )


# ==============================================================================
# 6. SYSTEM SETTINGS & AUDIT LOGS
# ==============================================================================

class SuperAdminSystemSettingsAPIView(APIView):
    authentication_classes = [SuperAdminAuthentication]
    permission_classes = [IsSuperAdmin, IsEnrolledSuperAdmin]

    def get(self, request):
        maintenance = SystemSetting.get_setting('maintenance_mode', {'enabled': False, 'message': ''})
        max_warnings = SystemSetting.get_setting('max_warnings', 3)
        rate_limits = SystemSetting.get_setting('rate_limits', {'anon': '120/min', 'user': '1200/min'})
        return Response(
            {
                'status': 'success',
                'settings': {
                    'maintenance_mode': maintenance,
                    'max_warnings': max_warnings,
                    'rate_limits': rate_limits,
                    'allowed_ips': getattr(settings, 'SUPER_ADMIN_ALLOWED_IPS', []),
                },
            },
            status=status.HTTP_200_OK,
        )

    def post(self, request):
        # Updating critical system settings requires reauth
        profile = request.user.super_admin_profile
        if not profile.is_reauth_valid():
            raise exceptions.PermissionDenied({'status': 'reauth_required', 'message': 'Re-authentication required.'})

        key = str(request.data.get('key', '')).strip()
        value = request.data.get('value')

        if not key:
            return Response({'status': 'error', 'message': 'Setting key is required.'}, status=status.HTTP_400_BAD_REQUEST)

        before = SystemSetting.get_setting(key, {})
        SystemSetting.set_setting(key, value, updated_by=request.user.username)

        log_super_admin_action(
            request,
            action='system_setting_updated',
            target_entity='SystemSetting',
            target_id=key,
            description=f'System setting "{key}" updated.',
            before_state={'value': before},
            after_state={'value': value},
        )

        return Response({'status': 'success', 'message': f'Setting "{key}" updated.'}, status=status.HTTP_200_OK)


class SuperAdminAuditLogAPIView(APIView):
    """
    Read-only, searchable, filterable, and exportable Super Admin Audit Log.
    """
    authentication_classes = [SuperAdminAuthentication]
    permission_classes = [IsSuperAdmin, IsEnrolledSuperAdmin]

    def get(self, request):
        action_filter = str(request.query_params.get('action', 'all')).strip()
        search = str(request.query_params.get('search', '')).strip()
        export = str(request.query_params.get('export', '')).lower() == 'csv'

        qs = SuperAdminAuditLog.objects.all().order_by('-created_at')

        if action_filter != 'all':
            qs = qs.filter(action__icontains=action_filter)

        if search:
            qs = qs.filter(
                Q(actor_username__icontains=search)
                | Q(description__icontains=search)
                | Q(target_entity__icontains=search)
                | Q(ip_address__icontains=search)
            )

        # Export as CSV with formula injection defense
        if export:
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = f'attachment; filename="superadmin_audit_{int(time.time())}.csv"'
            writer = csv.writer(response)
            writer.writerow(['ID', 'Timestamp (UTC)', 'Actor', 'Action', 'Target Entity', 'Target ID', 'IP Address', 'Prev Hash', 'Entry Hash', 'Description'])
            for log in qs[:5000]:
                def sanitize_cell(v):
                    s = str(v)
                    if s.startswith(('=', '+', '-', '@', '\t', '\r')):
                        return f"'{s}"
                    return s

                writer.writerow([
                    log.id,
                    log.created_at.isoformat(),
                    sanitize_cell(log.actor_username),
                    sanitize_cell(log.action),
                    sanitize_cell(log.target_entity),
                    sanitize_cell(log.target_id),
                    sanitize_cell(log.ip_address),
                    log.prev_hash,
                    log.entry_hash,
                    sanitize_cell(log.description),
                ])
            return response

        page_num = int(request.query_params.get('page', 1))
        page_size = int(request.query_params.get('page_size', 25))
        if page_size not in [10, 25, 50, 100]:
            page_size = 25

        paginator = Paginator(qs, page_size)
        page_obj = paginator.get_page(page_num)

        items = list(page_obj.object_list.values(
            'id', 'actor_username', 'action', 'target_entity', 'target_id',
            'description', 'before_state', 'after_state', 'ip_address', 'prev_hash', 'entry_hash', 'created_at'
        ))

        return Response(
            {
                'status': 'success',
                'data': items,
                'pagination': {
                    'page': page_obj.number,
                    'page_size': page_size,
                    'total_count': paginator.count,
                    'total_pages': paginator.num_pages,
                    'has_next': page_obj.has_next(),
                    'has_prev': page_obj.has_previous(),
                },
            },
            status=status.HTTP_200_OK,
        )


# ==============================================================================
# 7. DATA TOOLS & BACKUPS
# ==============================================================================

class SuperAdminBackupAPIView(APIView):
    """
    List backups and trigger fresh database backups outside the workspace.
    Includes SHA-256 checksums, retention policies, and scratch restore status.
    """
    authentication_classes = [SuperAdminAuthentication]
    permission_classes = [IsSuperAdmin, IsEnrolledSuperAdmin]

    def get(self, request):
        records = DatabaseBackupRecord.objects.all().order_by('-created_at')
        backups_data = []

        if records.exists():
            for rec in records:
                backups_data.append({
                    'id': rec.id,
                    'filename': rec.filename,
                    'file_path': rec.file_path,
                    'size_mb': round(rec.file_size_bytes / (1024 * 1024), 2),
                    'checksum_sha256': rec.checksum_sha256,
                    'backup_type': rec.backup_type,
                    'status': rec.status,
                    'restore_test_status': rec.restore_test_status,
                    'restore_test_details': rec.restore_test_details,
                    'restore_test_at': rec.restore_test_at.isoformat() if rec.restore_test_at else None,
                    'created_by': rec.created_by,
                    'created_at': rec.created_at.isoformat(),
                })
        else:
            # Fallback to disk scan if no DB records yet
            backup_dir = os.path.abspath(os.path.join(settings.BASE_DIR, '..', 'backups'))
            if os.path.exists(backup_dir):
                for fname in os.listdir(backup_dir):
                    if fname.endswith('.sql'):
                        fpath = os.path.join(backup_dir, fname)
                        st = os.stat(fpath)
                        backups_data.append({
                            'id': None,
                            'filename': fname,
                            'file_path': fpath,
                            'size_mb': round(st.st_size / (1024 * 1024), 2),
                            'checksum_sha256': '',
                            'backup_type': 'manual',
                            'status': 'completed',
                            'restore_test_status': 'not_tested',
                            'restore_test_details': '',
                            'restore_test_at': None,
                            'created_by': 'system',
                            'created_at': datetime.datetime.fromtimestamp(st.st_ctime).isoformat(),
                        })

        return Response({'status': 'success', 'backups': backups_data}, status=status.HTTP_200_OK)

    def post(self, request):
        profile = request.user.super_admin_profile
        if not profile.is_reauth_valid():
            raise exceptions.PermissionDenied({'status': 'reauth_required', 'message': 'Re-authentication required.'})

        backup_type = request.data.get('type', 'manual')
        if backup_type not in ['manual', 'daily', 'weekly']:
            backup_type = 'manual'

        try:
            record = create_database_backup(backup_type=backup_type, created_by=request.user.username)
        except Exception as exc:
            logger.error('Database backup failed: %s', exc)
            return Response(
                {'status': 'error', 'message': f'Backup failed: {str(exc)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        size_mb = round(record.file_size_bytes / (1024 * 1024), 2)
        log_super_admin_action(
            request,
            action='database_backup_created',
            target_entity='DatabaseBackupRecord',
            target_id=str(record.id),
            description=f'Created database backup "{record.filename}" ({size_mb} MB) [SHA256: {record.checksum_sha256[:16]}...].',
            after_state={'filename': record.filename, 'size_mb': size_mb, 'checksum': record.checksum_sha256},
        )

        return Response(
            {
                'status': 'success',
                'message': f'Backup "{record.filename}" created successfully.',
                'backup': {
                    'id': record.id,
                    'filename': record.filename,
                    'size_mb': size_mb,
                    'checksum_sha256': record.checksum_sha256,
                    'backup_type': record.backup_type,
                    'created_at': record.created_at.isoformat(),
                },
            },
            status=status.HTTP_201_CREATED,
        )


class SuperAdminBackupTestRestoreAPIView(APIView):
    """
    Test restoring a database backup into a temporary scratch schema.
    Verifies SQL file integrity, syntax, table structure, and reports result.
    """
    authentication_classes = [SuperAdminAuthentication]
    permission_classes = [IsSuperAdmin, IsEnrolledSuperAdmin]

    def post(self, request, backup_id):
        profile = request.user.super_admin_profile
        if not profile.is_reauth_valid():
            raise exceptions.PermissionDenied({'status': 'reauth_required', 'message': 'Re-authentication required.'})

        result = test_restore_backup(backup_id)

        log_super_admin_action(
            request,
            action='backup_restore_test',
            target_entity='DatabaseBackupRecord',
            target_id=str(backup_id),
            description=f'Tested restore for backup #{backup_id}: {result.get("message")}',
            after_state=result,
        )

        resp_status = status.HTTP_200_OK if result.get('success') else status.HTTP_400_BAD_REQUEST
        return Response(result, status=resp_status)


class SuperAdminBackupLiveRestoreAPIView(APIView):
    """
    Restore a backup onto the active primary database.
    Requires re-authentication, dry-run preview, and active Maintenance Mode.
    """
    authentication_classes = [SuperAdminAuthentication]
    permission_classes = [IsSuperAdmin, IsEnrolledSuperAdmin]

    def post(self, request, backup_id):
        profile = request.user.super_admin_profile
        if not profile.is_reauth_valid():
            raise exceptions.PermissionDenied({'status': 'reauth_required', 'message': 'Re-authentication required.'})

        dry_run = request.data.get('dry_run', True)
        confirm_maintenance = request.data.get('confirm_maintenance', False)

        result = restore_backup_on_live_database(
            backup_id=backup_id,
            dry_run=dry_run,
            confirm_maintenance=confirm_maintenance,
        )

        if not dry_run and result.get('success'):
            log_super_admin_action(
                request,
                action='database_live_restore_executed',
                target_entity='DatabaseBackupRecord',
                target_id=str(backup_id),
                description=f'LIVE database restore executed from backup #{backup_id}.',
                after_state=result,
            )

        resp_status = status.HTTP_200_OK if result.get('success') else status.HTTP_400_BAD_REQUEST
        return Response(result, status=resp_status)


class SuperAdminMonitoringHealthAPIView(APIView):
    """
    Retrieve aggregated platform health status:
    Database latency, Ollama engine status/models, disk space, background jobs, and latest backup status.
    """
    authentication_classes = [SuperAdminAuthentication]
    permission_classes = [IsSuperAdmin, IsEnrolledSuperAdmin]

    def get(self, request):
        health_data = check_system_health()
        return Response({'status': 'success', 'health': health_data}, status=status.HTTP_200_OK)


class SuperAdminLogsAPIView(APIView):
    """
    Read-only system log viewer.
    Filters by level, search keyword, and limits results.
    Strictly masks passwords, Bearer tokens, recovery codes, and secret slugs.
    """
    authentication_classes = [SuperAdminAuthentication]
    permission_classes = [IsSuperAdmin, IsEnrolledSuperAdmin]

    def get(self, request):
        level = request.GET.get('level')
        query = request.GET.get('q')
        limit = min(int(request.GET.get('limit', 150)), 500)

        logs = get_system_logs(level=level, query=query, limit=limit)
        return Response({'status': 'success', 'count': len(logs), 'logs': logs}, status=status.HTTP_200_OK)


class SuperAdminErrorSummaryAPIView(APIView):
    """
    Error summary grouped by cause and exception pattern.
    Reports occurrence count, first seen, last seen, and representative sample.
    """
    authentication_classes = [SuperAdminAuthentication]
    permission_classes = [IsSuperAdmin, IsEnrolledSuperAdmin]

    def get(self, request):
        days = min(int(request.GET.get('days', 7)), 30)
        summary = get_error_summary_grouped(days=days)
        return Response({'status': 'success', 'summary': summary}, status=status.HTTP_200_OK)


class SuperAdminJobCenterAPIView(APIView):
    """
    Central background job controller.
    Monitors generation jobs, durations, failure rates, and stuck tasks.
    """
    authentication_classes = [SuperAdminAuthentication]
    permission_classes = [IsSuperAdmin, IsEnrolledSuperAdmin]

    def get(self, request):
        status_filter = request.GET.get('status')
        limit = min(int(request.GET.get('limit', 50)), 100)

        summary = get_jobs_summary()
        jobs = list_background_jobs(status_filter=status_filter, limit=limit)

        return Response({'status': 'success', 'summary': summary, 'jobs': jobs}, status=status.HTTP_200_OK)


class SuperAdminJobActionAPIView(APIView):
    """
    Perform administrative actions on background jobs (retry, cancel).
    """
    authentication_classes = [SuperAdminAuthentication]
    permission_classes = [IsSuperAdmin, IsEnrolledSuperAdmin]

    def post(self, request, job_id, action):
        if action == 'retry':
            res = retry_paper_generation_job(job_id)
        elif action == 'cancel':
            res = cancel_paper_generation_job(job_id)
        else:
            return Response({'status': 'error', 'message': f'Unknown action "{action}".'}, status=status.HTTP_400_BAD_REQUEST)

        if res.get('success'):
            log_super_admin_action(
                request,
                action=f'job_{action}',
                target_entity='PaperGenerationJob',
                target_id=str(job_id),
                description=f'Super admin executed {action} on job #{job_id}.',
            )
            return Response(res, status=status.HTTP_200_OK)
        return Response(res, status=status.HTTP_400_BAD_REQUEST)


class SuperAdminStuckJobDetectorAPIView(APIView):
    """
    Scan for stuck jobs (>15 minutes in pending/running) with optional auto-cleanup.
    """
    authentication_classes = [SuperAdminAuthentication]
    permission_classes = [IsSuperAdmin, IsEnrolledSuperAdmin]

    def post(self, request):
        timeout = int(request.data.get('timeout', 15))
        auto_fail = bool(request.data.get('auto_fail', False))

        stuck_ids = detect_and_cleanup_stuck_jobs(threshold_minutes=timeout, auto_fail=auto_fail)

        if auto_fail and stuck_ids:
            log_super_admin_action(
                request,
                action='stuck_jobs_cleaned',
                target_entity='PaperGenerationJob',
                target_id=','.join(map(str, stuck_ids)),
                description=f'Cleaned up {len(stuck_ids)} stuck jobs: {stuck_ids}',
            )

        return Response(
            {
                'status': 'success',
                'stuck_count': len(stuck_ids),
                'stuck_ids': stuck_ids,
                'cleaned': auto_fail,
            },
            status=status.HTTP_200_OK,
        )


class SuperAdminMaintenanceWindowAPIView(APIView):
    """
    Schedule platform-wide maintenance windows with super-admin bypass.
    """
    authentication_classes = [SuperAdminAuthentication]
    permission_classes = [IsSuperAdmin, IsEnrolledSuperAdmin]

    def get(self, request):
        is_active, msg = MaintenanceWindow.is_currently_active()
        record = MaintenanceWindow.objects.first()
        return Response(
            {
                'status': 'success',
                'is_currently_active': is_active,
                'active_message': msg,
                'configuration': {
                    'is_enabled': record.is_enabled if record else False,
                    'start_time': record.start_time.isoformat() if (record and record.start_time) else None,
                    'end_time': record.end_time.isoformat() if (record and record.end_time) else None,
                    'custom_message': record.custom_message if record else 'System is temporarily undergoing scheduled maintenance.',
                    'bypass_superadmin': record.bypass_superadmin if record else True,
                    'updated_at': record.updated_at.isoformat() if record else None,
                    'updated_by': record.updated_by if record else '',
                },
            },
            status=status.HTTP_200_OK,
        )

    def post(self, request):
        profile = request.user.super_admin_profile
        if not profile.is_reauth_valid():
            raise exceptions.PermissionDenied({'status': 'reauth_required', 'message': 'Re-authentication required.'})

        is_enabled = bool(request.data.get('is_enabled', False))
        custom_message = request.data.get('custom_message', '').strip() or 'System is temporarily undergoing scheduled maintenance. Please check back shortly.'
        start_time = request.data.get('start_time')
        end_time = request.data.get('end_time')
        bypass_superadmin = bool(request.data.get('bypass_superadmin', True))

        record = MaintenanceWindow.objects.first()
        if not record:
            record = MaintenanceWindow()

        record.is_enabled = is_enabled
        record.custom_message = custom_message
        record.start_time = start_time if start_time else None
        record.end_time = end_time if end_time else None
        record.bypass_superadmin = bypass_superadmin
        record.updated_by = request.user.username
        record.save()

        log_super_admin_action(
            request,
            action='maintenance_window_configured',
            target_entity='MaintenanceWindow',
            target_id=str(record.id),
            description=f'Configured maintenance mode: enabled={is_enabled}, bypass={bypass_superadmin}.',
            after_state={
                'is_enabled': is_enabled,
                'start_time': str(start_time),
                'end_time': str(end_time),
                'custom_message': custom_message,
            },
        )

        return Response(
            {
                'status': 'success',
                'message': 'Maintenance window updated successfully.',
                'is_currently_active': MaintenanceWindow.is_currently_active()[0],
            },
            status=status.HTTP_200_OK,
        )


class SuperAdminCleanupReportAPIView(APIView):
    """
    List orphan files and old drafts.
    GET produces dry-run report; POST executes confirmed cleanup items with reauth.
    """
    authentication_classes = [SuperAdminAuthentication]
    permission_classes = [IsSuperAdmin, IsEnrolledSuperAdmin]

    def get(self, request):
        cutoff = timezone.now() - timedelta(days=30)
        stale_drafts_count = Exam.objects.filter(status=Exam.Status.DRAFT, updated_at__lt=cutoff).count()
        failed_jobs_count = PaperGenerationJob.objects.filter(status='failed').count()

        return Response(
            {
                'status': 'success',
                'report': {
                    'stale_drafts_count': stale_drafts_count,
                    'failed_jobs_count': failed_jobs_count,
                    'cutoff_days': 30,
                },
            },
            status=status.HTTP_200_OK,
        )

    def post(self, request):
        profile = request.user.super_admin_profile
        if not profile.is_reauth_valid():
            raise exceptions.PermissionDenied({'status': 'reauth_required', 'message': 'Re-authentication required.'})

        cleanup_type = str(request.data.get('type', '')).strip()
        deleted_count = 0

        if cleanup_type == 'stale_drafts':
            cutoff = timezone.now() - timedelta(days=30)
            stale_drafts = Exam.objects.filter(status=Exam.Status.DRAFT, updated_at__lt=cutoff)
            deleted_count = stale_drafts.count()
            stale_drafts.delete()
        elif cleanup_type == 'failed_jobs':
            failed_jobs = PaperGenerationJob.objects.filter(status='failed')
            deleted_count = failed_jobs.count()
            failed_jobs.delete()
        else:
            return Response({'status': 'error', 'message': 'Invalid cleanup type.'}, status=status.HTTP_400_BAD_REQUEST)

        log_super_admin_action(
            request,
            action=f'cleanup_{cleanup_type}',
            target_entity=cleanup_type,
            description=f'Super admin cleaned up {deleted_count} items of type {cleanup_type}.',
            after_state={'type': cleanup_type, 'deleted_count': deleted_count},
        )

        return Response({'status': 'success', 'message': f'Cleaned up {deleted_count} record(s).'}, status=status.HTTP_200_OK)


# ==============================================================================
# 8. INSTITUTE CONTROL, BULK ONBOARDING & IMPERSONATION
# ==============================================================================

class SuperAdminInstitutePolicyAPIView(APIView):
    """
    Manage institute-specific policies, quotas, operational overrides, and feature flags.
    """
    authentication_classes = [SuperAdminAuthentication]
    permission_classes = [IsSuperAdmin, IsEnrolledSuperAdmin]

    def get(self, request, institute_id):
        inst = AdminInstitution.objects.filter(pk=institute_id).first()
        if not inst:
            raise Http404()

        usage = calculate_institute_usage(inst)
        return Response({'status': 'success', 'usage_and_policy': usage}, status=status.HTTP_200_OK)

    def post(self, request, institute_id):
        profile = request.user.super_admin_profile
        if not profile.is_reauth_valid():
            raise exceptions.PermissionDenied({'status': 'reauth_required', 'message': 'Re-authentication required.'})

        inst = AdminInstitution.objects.filter(pk=institute_id).first()
        if not inst:
            raise Http404()

        policy = get_or_create_institute_policy(inst)
        data = request.data

        if 'timezone' in data:
            policy.timezone_name = str(data['timezone']).strip()
        if 'academic_year' in data:
            policy.academic_year = str(data['academic_year']).strip()
        if 'max_students' in data:
            policy.max_students = int(data['max_students'])
        if 'max_faculty' in data:
            policy.max_faculty = int(data['max_faculty'])
        if 'max_ai_generations_per_month' in data:
            policy.max_ai_generations_per_month = int(data['max_ai_generations_per_month'])
        if 'max_storage_mb' in data:
            policy.max_storage_mb = int(data['max_storage_mb'])
        if 'exam_window_buffer_minutes' in data:
            policy.exam_window_buffer_minutes = int(data['exam_window_buffer_minutes'])
        if 'violation_limit_override' in data:
            policy.violation_limit_override = int(data['violation_limit_override'])
        if 'faculty_can_publish_without_review' in data:
            policy.faculty_can_publish_without_review = bool(data['faculty_can_publish_without_review'])
        if 'allowed_departments' in data and isinstance(data['allowed_departments'], list):
            policy.allowed_departments = [str(d).strip() for d in data['allowed_departments'] if str(d).strip()]
        if 'feature_flags' in data and isinstance(data['feature_flags'], dict):
            policy.feature_flags = data['feature_flags']

        policy.updated_by = request.user.username
        policy.save()

        log_super_admin_action(
            request,
            action='institute_policy_updated',
            target_entity='InstitutePolicy',
            target_id=str(policy.id),
            description=f'Updated policy & quotas for institute "{inst.institution_name}".',
            after_state=data,
        )

        return Response(
            {
                'status': 'success',
                'message': 'Institute policy updated successfully.',
                'usage_and_policy': calculate_institute_usage(inst),
            },
            status=status.HTTP_200_OK,
        )


class SuperAdminInstituteLogoAPIView(APIView):
    """
    Safely upload and store institution logo with format/size validation.
    """
    authentication_classes = [SuperAdminAuthentication]
    permission_classes = [IsSuperAdmin, IsEnrolledSuperAdmin]

    def post(self, request, institute_id):
        profile = request.user.super_admin_profile
        if not profile.is_reauth_valid():
            raise exceptions.PermissionDenied({'status': 'reauth_required', 'message': 'Re-authentication required.'})

        inst = AdminInstitution.objects.filter(pk=institute_id).first()
        if not inst:
            raise Http404()

        logo_file = request.FILES.get('logo')
        if not logo_file:
            return Response({'status': 'error', 'message': 'No image file uploaded.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            rel_url = validate_and_save_logo(inst, logo_file)
        except ValueError as err:
            return Response({'status': 'error', 'message': str(err)}, status=status.HTTP_400_BAD_REQUEST)

        log_super_admin_action(
            request,
            action='institute_logo_updated',
            target_entity='AdminInstitution',
            target_id=str(inst.id),
            description=f'Uploaded new logo for "{inst.institution_name}".',
        )

        return Response(
            {'status': 'success', 'message': 'Logo uploaded successfully.', 'logo_url': rel_url},
            status=status.HTTP_200_OK,
        )


class SuperAdminBulkImportTemplateAPIView(APIView):
    """
    Download CSV templates for student or faculty bulk onboarding.
    """
    authentication_classes = [SuperAdminAuthentication]
    permission_classes = [IsSuperAdmin, IsEnrolledSuperAdmin]

    def get(self, request):
        role = request.GET.get('role', 'student').lower()
        if role not in ['student', 'faculty']:
            role = 'student'

        csv_content = get_bulk_import_template(role=role)
        resp = HttpResponse(csv_content, content_type='text/csv')
        resp['Content-Disposition'] = f'attachment; filename="bulk_{role}_template.csv"'
        return resp


class SuperAdminBulkImportAPIView(APIView):
    """
    Atomic bulk onboarding of students/faculty with dry-run preview and secure one-time credentials.
    """
    authentication_classes = [SuperAdminAuthentication]
    permission_classes = [IsSuperAdmin, IsEnrolledSuperAdmin]

    def post(self, request, institute_id):
        profile = request.user.super_admin_profile
        if not profile.is_reauth_valid():
            raise exceptions.PermissionDenied({'status': 'reauth_required', 'message': 'Re-authentication required.'})

        inst = AdminInstitution.objects.filter(pk=institute_id).first()
        if not inst:
            raise Http404()

        role = str(request.data.get('role', 'student')).lower()
        if role not in ['student', 'faculty']:
            role = 'student'

        dry_run = str(request.data.get('dry_run', 'true')).lower() == 'true'

        content = ''
        if 'file' in request.FILES:
            content = request.FILES['file'].read().decode('utf-8', errors='ignore')
        elif 'content' in request.data:
            content = str(request.data['content'])

        if not content.strip():
            return Response({'status': 'error', 'message': 'Empty file or content received.'}, status=status.HTTP_400_BAD_REQUEST)

        summary = validate_and_process_bulk_import(
            institution=inst,
            file_content=content,
            role=role,
            dry_run=dry_run,
        )

        if not dry_run and summary.get('imported_count'):
            log_super_admin_action(
                request,
                action=f'bulk_{role}_import_executed',
                target_entity='AdminInstitution',
                target_id=str(inst.id),
                description=f'Bulk imported {summary["imported_count"]} {role}(s) into "{inst.institution_name}".',
                after_state={'imported_count': summary['imported_count'], 'role': role},
            )

        resp_status = status.HTTP_200_OK if not summary.get('errors') else status.HTTP_400_BAD_REQUEST
        return Response(summary, status=resp_status)


class SuperAdminAnnouncementsAPIView(APIView):
    """
    Post targeted system announcements with XSS sanitization across institutes, departments, or roles.
    """
    authentication_classes = [SuperAdminAuthentication]
    permission_classes = [IsSuperAdmin, IsEnrolledSuperAdmin]

    def get(self, request):
        qs = SystemAnnouncement.objects.select_related('target_institute').order_by('-created_at')[:50]
        items = []
        for a in qs:
            items.append({
                'id': a.id,
                'title': a.title,
                'message': a.message,
                'target_type': a.target_type,
                'target_institute_name': a.target_institute.institution_name if a.target_institute else 'All',
                'target_department': a.target_department or 'All',
                'target_role': a.target_role or 'All',
                'is_active': a.is_active,
                'created_at': a.created_at.isoformat(),
            })
        return Response({'status': 'success', 'announcements': items}, status=status.HTTP_200_OK)

    def post(self, request):
        profile = request.user.super_admin_profile
        if not profile.is_reauth_valid():
            raise exceptions.PermissionDenied({'status': 'reauth_required', 'message': 'Re-authentication required.'})

        title = str(request.data.get('title', '')).strip()
        message = str(request.data.get('message', '')).strip()
        if not title or not message:
            return Response({'status': 'error', 'message': 'Title and message are required.'}, status=status.HTTP_400_BAD_REQUEST)

        target_type = request.data.get('target_type', 'all')
        target_institute_id = request.data.get('target_institute_id')
        target_department = str(request.data.get('target_department', '')).strip()
        target_role = str(request.data.get('target_role', '')).strip()

        announcement = create_and_dispatch_announcement(
            title=title,
            message=message,
            target_type=target_type,
            target_institute_id=target_institute_id,
            target_department=target_department,
            target_role=target_role,
            created_by=request.user.username,
        )

        log_super_admin_action(
            request,
            action='announcement_published',
            target_entity='SystemAnnouncement',
            target_id=str(announcement.id),
            description=f'Published announcement "{announcement.title}" ({target_type}).',
        )

        return Response(
            {
                'status': 'success',
                'message': 'Announcement published successfully.',
                'announcement_id': announcement.id,
            },
            status=status.HTTP_201_CREATED,
        )


class SuperAdminPermissionsMatrixAPIView(APIView):
    """
    Introspect real permission classes and return live capabilities matrix.
    """
    authentication_classes = [SuperAdminAuthentication]
    permission_classes = [IsSuperAdmin, IsEnrolledSuperAdmin]

    def get(self, request):
        matrix_data = generate_permissions_matrix()
        return Response({'status': 'success', 'permissions_matrix': matrix_data}, status=status.HTTP_200_OK)


class SuperAdminImpersonateAPIView(APIView):
    """
    Time-limited (15 minutes), audited impersonation of any user for operational support.
    """
    authentication_classes = [SuperAdminAuthentication]
    permission_classes = [IsSuperAdmin, IsEnrolledSuperAdmin]

    def post(self, request, user_id):
        profile = request.user.super_admin_profile
        if not profile.is_reauth_valid():
            raise exceptions.PermissionDenied({'status': 'reauth_required', 'message': 'Re-authentication required.'})

        reason = str(request.data.get('reason', '')).strip()
        if not reason or len(reason) < 5:
            return Response(
                {'status': 'error', 'message': 'A valid operational reason (at least 5 characters) is required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        client_ip = get_client_ip(request)
        try:
            impersonation = create_impersonation_session(
                super_admin_user=request.user,
                target_user_id=user_id,
                reason=reason,
                client_ip=client_ip,
            )
        except Exception as exc:
            return Response({'status': 'error', 'message': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        log_super_admin_action(
            request,
            action='user_impersonated',
            target_entity='User',
            target_id=str(user_id),
            description=f'Impersonated user #{user_id} ({impersonation["target_user"]["username"]}). Reason: {reason}',
            after_state={'reason': reason, 'expires_in_minutes': 15},
        )

        return Response(
            {
                'status': 'success',
                'message': f'Impersonation session established for {impersonation["target_user"]["username"]}.',
                'impersonation': impersonation,
            },
            status=status.HTTP_200_OK,
        )


# ==============================================================================
# 9. REPORTS, ANALYTICS & DATA PRIVACY (DPDP)
# ==============================================================================

class SuperAdminCrossInstituteAnalyticsAPIView(APIView):
    """
    Platform-wide aggregate analytics across all tenant institutions.
    """
    authentication_classes = [SuperAdminAuthentication]
    permission_classes = [IsSuperAdmin, IsEnrolledSuperAdmin]

    def get(self, request):
        force_refresh = str(request.GET.get('refresh', 'false')).lower() == 'true'
        analytics = get_cross_institute_analytics(force_refresh=force_refresh)
        return Response({'status': 'success', 'analytics': analytics}, status=status.HTTP_200_OK)


class SuperAdminExportsAPIView(APIView):
    """
    Download sanitized CSV reports for users, exams, attempts, or audit logs.
    Guards against Formula Injection (CWE-1236) and requires recent step-up re-authentication.
    """
    authentication_classes = [SuperAdminAuthentication]
    permission_classes = [IsSuperAdmin, IsEnrolledSuperAdmin]

    def get(self, request):
        profile = request.user.super_admin_profile
        if not profile.is_reauth_valid():
            raise exceptions.PermissionDenied({'status': 'reauth_required', 'message': 'Re-authentication required.'})

        entity = request.GET.get('entity', 'users').lower()
        inst_id = request.GET.get('institution_id')
        filters = {'institution_id': int(inst_id)} if inst_id and inst_id.isdigit() else {}

        try:
            csv_data, filename = export_entities_to_csv(entity_type=entity, filters=filters)
        except ValueError as err:
            return Response({'status': 'error', 'message': str(err)}, status=status.HTTP_400_BAD_REQUEST)

        log_super_admin_action(
            request,
            action=f'export_{entity}_downloaded',
            target_entity=entity,
            description=f'Exported {entity} CSV data with formula sanitization.',
        )

        resp = HttpResponse(csv_data, content_type='text/csv; charset=utf-8')
        resp['Content-Disposition'] = f'attachment; filename="{filename}"'
        return resp


class SuperAdminDPDPDataExportAPIView(APIView):
    """
    DPDP Right to Data Portability: export personal data for a specific user.
    """
    authentication_classes = [SuperAdminAuthentication]
    permission_classes = [IsSuperAdmin, IsEnrolledSuperAdmin]

    def get(self, request, user_id):
        profile = request.user.super_admin_profile
        if not profile.is_reauth_valid():
            raise exceptions.PermissionDenied({'status': 'reauth_required', 'message': 'Re-authentication required.'})

        try:
            data = export_user_data(user_id)
        except ValueError as err:
            return Response({'status': 'error', 'message': str(err)}, status=status.HTTP_404_NOT_FOUND)

        log_super_admin_action(
            request,
            action='dpdp_user_data_exported',
            target_entity='User',
            target_id=str(user_id),
            description=f'Exported DPDP personal data package for user #{user_id}.',
        )

        return Response({'status': 'success', 'data_package': data}, status=status.HTTP_200_OK)


class SuperAdminDPDPAnonymizeAPIView(APIView):
    """
    DPDP Right to Erasure / Anonymization with regulatory academic record preservation.
    POST with dry_run=true returns impact report.
    POST with dry_run=false executes irreversible personal data scrubbing.
    """
    authentication_classes = [SuperAdminAuthentication]
    permission_classes = [IsSuperAdmin, IsEnrolledSuperAdmin]

    def post(self, request, user_id):
        profile = request.user.super_admin_profile
        if not profile.is_reauth_valid():
            raise exceptions.PermissionDenied({'status': 'reauth_required', 'message': 'Re-authentication required.'})

        dry_run = str(request.data.get('dry_run', 'true')).lower() == 'true'
        reason = str(request.data.get('reason', '')).strip()

        try:
            if dry_run:
                summary = dry_run_anonymize_user(user_id)
                return Response({'status': 'success', 'dry_run_summary': summary}, status=status.HTTP_200_OK)
            else:
                if not reason or len(reason) < 5:
                    return Response(
                        {'status': 'error', 'message': 'A valid justification reason is required for permanent anonymization.'},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                result = execute_anonymize_user(user_id=user_id, executed_by=request.user.username, reason=reason)
                log_super_admin_action(
                    request,
                    action='dpdp_user_anonymized',
                    target_entity='User',
                    target_id=str(user_id),
                    description=f'Permanently anonymized personal data for user #{user_id}. Reason: {reason}',
                )
                return Response(result, status=status.HTTP_200_OK)
        except ValueError as err:
            return Response({'status': 'error', 'message': str(err)}, status=status.HTTP_400_BAD_REQUEST)


class SuperAdminDPDPDataInventoryAPIView(APIView):
    """
    Comprehensive personal data inventory mapping categories, storage entities, retention schedules, and legal bases.
    """
    authentication_classes = [SuperAdminAuthentication]
    permission_classes = [IsSuperAdmin, IsEnrolledSuperAdmin]

    def get(self, request):
        inventory = get_data_inventory()
        return Response({'status': 'success', 'data_inventory': inventory}, status=status.HTTP_200_OK)


# ==============================================================================
# MODULE B: AI MODEL MANAGEMENT (DYNAMIC OLLAMA REGISTRY)
# ==============================================================================

class SuperAdminAIModelsAPIView(APIView):
    """
    Get all registered Ollama models, sync with local Ollama runtime,
    view running instances, capacity warnings, and initiate downloads.
    """
    authentication_classes = [SuperAdminAuthentication]
    permission_classes = [IsSuperAdmin, IsEnrolledSuperAdmin]

    def get(self, request):
        data = get_ollama_status_and_sync()
        return Response({'status': 'success', **data}, status=status.HTTP_200_OK)

    def post(self, request):
        model_name = str(request.data.get('name', '')).strip()
        if not model_name:
            return Response({'status': 'error', 'message': 'Model tag name is required.'}, status=status.HTTP_400_BAD_REQUEST)

        success, msg, model_data = initiate_model_pull(model_name=model_name, actor_username=request.user.username)
        if not success:
            return Response({'status': 'error', 'message': msg}, status=status.HTTP_400_BAD_REQUEST)

        return Response({'status': 'success', 'message': msg, 'data': model_data}, status=status.HTTP_202_ACCEPTED)


class SuperAdminAIModelToggleAPIView(APIView):
    """
    Enable or disable an AI model. Disabled models are excluded from paper generation.
    """
    authentication_classes = [SuperAdminAuthentication]
    permission_classes = [IsSuperAdmin, IsEnrolledSuperAdmin]

    def post(self, request, model_id):
        is_enabled = bool(request.data.get('is_enabled', True))
        success, msg = toggle_ai_model_status(
            model_id=model_id,
            is_enabled=is_enabled,
            actor_username=request.user.username,
        )
        if not success:
            return Response({'status': 'error', 'message': msg}, status=status.HTTP_400_BAD_REQUEST)
        return Response({'status': 'success', 'message': msg}, status=status.HTTP_200_OK)


class SuperAdminAIModelSetDefaultAPIView(APIView):
    """
    Sets designated AI model as the platform primary default for paper generation.
    """
    authentication_classes = [SuperAdminAuthentication]
    permission_classes = [IsSuperAdmin, IsEnrolledSuperAdmin]

    def post(self, request, model_id):
        success, msg = set_default_ai_model(model_id=model_id, actor_username=request.user.username)
        if not success:
            return Response({'status': 'error', 'message': msg}, status=status.HTTP_400_BAD_REQUEST)
        return Response({'status': 'success', 'message': msg}, status=status.HTTP_200_OK)


class SuperAdminAIModelDeleteAPIView(APIView):
    """
    Permanently deletes model from disk via Ollama HTTP API and removes from platform registry.
    Requires step-up re-authentication.
    """
    authentication_classes = [SuperAdminAuthentication]
    permission_classes = [IsSuperAdmin, IsEnrolledSuperAdmin]

    def delete(self, request, model_id):
        return self._perform_delete(request, model_id)

    def post(self, request, model_id):
        return self._perform_delete(request, model_id)

    def _perform_delete(self, request, model_id):
        profile = getattr(request.user, 'super_admin_profile', None)
        if profile and not profile.is_reauth_valid():
            return Response(
                {'status': 'reauth_required', 'message': 'Deleting an AI model requires step-up re-authentication.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        success, msg = remove_ollama_model(model_id=model_id, actor_username=request.user.username)
        if not success:
            return Response({'status': 'error', 'message': msg}, status=status.HTTP_400_BAD_REQUEST)
        return Response({'status': 'success', 'message': msg}, status=status.HTTP_200_OK)


class SuperAdminAIModelTestAPIView(APIView):
    """
    Runs latency benchmark and operational health test for an Ollama model.
    """
    authentication_classes = [SuperAdminAuthentication]
    permission_classes = [IsSuperAdmin, IsEnrolledSuperAdmin]

    def post(self, request, model_id):
        success, msg, result = test_ai_model_connectivity(model_id=model_id, actor_username=request.user.username)
        return Response(
            {'status': 'success' if success else 'failed', 'message': msg, 'result': result},
            status=status.HTTP_200_OK,
        )


# ==============================================================================
# MODULE C: NOTIFICATIONS ENGINE
# ==============================================================================

class SuperAdminNotificationCampaignListCreateAPIView(APIView):
    """
    List campaigns with real-time delivery and read rates.
    Create and dispatch or schedule targeted notification campaigns.
    """
    authentication_classes = [SuperAdminAuthentication]
    permission_classes = [IsSuperAdmin, IsEnrolledSuperAdmin]

    def get(self, request):
        page = max(1, int(request.GET.get('page', 1)))
        page_size = min(int(request.GET.get('page_size', 10)), 100)
        search = str(request.GET.get('search', '')).strip()
        status_filter = str(request.GET.get('status', 'all')).strip()

        data = list_campaigns_paginated(
            page=page,
            page_size=page_size,
            search=search,
            status_filter=status_filter,
        )
        return Response({'status': 'success', **data}, status=status.HTTP_200_OK)

    def post(self, request):
        success, msg, campaign_data = create_and_send_campaign(
            data=request.data,
            actor_username=request.user.username,
        )
        if not success:
            return Response({'status': 'error', 'message': msg}, status=status.HTTP_400_BAD_REQUEST)
        return Response({'status': 'success', 'message': msg, 'data': campaign_data}, status=status.HTTP_201_CREATED)


class SuperAdminNotificationAudiencePreviewAPIView(APIView):
    """
    Live recipient count resolution and sample recipient preview for the audience builder.
    """
    authentication_classes = [SuperAdminAuthentication]
    permission_classes = [IsSuperAdmin, IsEnrolledSuperAdmin]

    def post(self, request):
        target_audience = request.data.get('target_audience', 'all')
        target_role = request.data.get('target_role', '')
        target_institute_id = request.data.get('target_institute_id')
        target_department = request.data.get('target_department', '')
        target_user_ids = request.data.get('target_user_ids', [])

        preview_data = preview_campaign_audience(
            target_audience=target_audience,
            target_role=target_role,
            target_institute_id=target_institute_id,
            target_department=target_department,
            target_user_ids=target_user_ids,
        )
        return Response({'status': 'success', **preview_data}, status=status.HTTP_200_OK)


class SuperAdminNotificationCampaignCancelAPIView(APIView):
    """
    Cancels a scheduled or draft notification campaign.
    """
    authentication_classes = [SuperAdminAuthentication]
    permission_classes = [IsSuperAdmin, IsEnrolledSuperAdmin]

    def post(self, request, campaign_id):
        success, msg = cancel_scheduled_campaign(
            campaign_id=campaign_id,
            actor_username=request.user.username,
        )
        if not success:
            return Response({'status': 'error', 'message': msg}, status=status.HTTP_400_BAD_REQUEST)
        return Response({'status': 'success', 'message': msg}, status=status.HTTP_200_OK)





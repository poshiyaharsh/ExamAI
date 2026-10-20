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
from faculty.models import FacultyProfile
from students.models import StudentProfile
from superadmin.alerts import send_super_admin_security_alert
from superadmin.audit import get_client_ip, log_super_admin_action
from superadmin.authentication import SuperAdminAuthentication, generate_super_admin_token
from superadmin.models import SuperAdminAuditLog, SuperAdminProfile, SystemSetting
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

        if totp_code:
            totp_success = verify_totp(profile.totp_secret, totp_code, window=1)

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
                {'status': 'error', 'message': 'Invalid two-factor authentication code.'},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # Successful Login
        profile.failed_login_attempts = 0
        profile.locked_until = None
        profile.last_login_at = timezone.now()
        profile.last_login_ip = client_ip
        profile.last_reauth_at = timezone.now()  # Fresh login counts as re-authenticated
        profile.save(update_fields=['failed_login_attempts', 'locked_until', 'last_login_at', 'last_login_ip', 'last_reauth_at'])

        token = generate_super_admin_token(user)

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

        if not verify_totp(profile.totp_secret, code, window=1):
            return Response(
                {'status': 'error', 'message': 'Verification code does not match. Check your authenticator app time.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        profile.is_totp_enrolled = True
        profile.last_reauth_at = timezone.now()
        profile.save(update_fields=['is_totp_enrolled', 'last_reauth_at'])

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

        if not verify_totp(profile.totp_secret, totp_code, window=1):
            log_super_admin_action(
                request,
                action='reauth_failed_totp',
                target_entity='SuperAdminProfile',
                target_id=str(profile.id),
                description='Re-authentication rejected: invalid TOTP.',
            )
            return Response({'status': 'error', 'message': '2FA verification code invalid.'}, status=status.HTTP_401_UNAUTHORIZED)

        profile.last_reauth_at = timezone.now()
        profile.save(update_fields=['last_reauth_at'])

        log_super_admin_action(
            request,
            action='reauth_success',
            target_entity='SuperAdminProfile',
            target_id=str(profile.id),
            description='Super Admin step-up re-authentication successful.',
        )

        return Response({'status': 'success', 'message': 'Re-authentication verified.'}, status=status.HTTP_200_OK)


class SuperAdminLogoutAPIView(APIView):
    """Log out super admin and invalidate session cookie."""
    authentication_classes = [SuperAdminAuthentication]
    permission_classes = [IsSuperAdmin]

    def post(self, request):
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
            from api.constants import DEFAULT_DEPARTMENT_NAMES
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
    Unified directory for students, faculty, and admins across all institutions.
    """
    authentication_classes = [SuperAdminAuthentication]
    permission_classes = [IsSuperAdmin, IsEnrolledSuperAdmin]

    def get(self, request):
        role_filter = str(request.query_params.get('role', 'all')).strip().lower()
        inst_id = request.query_params.get('institution_id')
        dept_filter = str(request.query_params.get('department', 'all')).strip()
        status_filter = str(request.query_params.get('status', 'all')).strip().lower()
        search = str(request.query_params.get('search', '')).strip()

        page_num = int(request.query_params.get('page', 1))
        page_size = int(request.query_params.get('page_size', 10))
        if page_size not in [10, 25, 50, 100]:
            page_size = 10

        qs = User.objects.exclude(super_admin_profile__isnull=False).select_related(
            'admin_profile', 'faculty_profile', 'student_profile', 'admin_institution'
        ).order_by('-date_joined')

        if search:
            qs = qs.filter(
                Q(username__icontains=search)
                | Q(email__icontains=search)
                | Q(first_name__icontains=search)
                | Q(last_name__icontains=search)
                | Q(student_profile__student_id__icontains=search)
                | Q(faculty_profile__employee_id__icontains=search)
            )

        if status_filter == 'active':
            qs = qs.filter(is_active=True)
        elif status_filter == 'inactive':
            qs = qs.filter(is_active=False)

        if role_filter == 'admin':
            qs = qs.filter(admin_profile__isnull=False)
        elif role_filter == 'faculty':
            qs = qs.filter(faculty_profile__isnull=False)
        elif role_filter == 'student':
            qs = qs.filter(student_profile__isnull=False)

        if inst_id:
            try:
                inst_int = int(inst_id)
                qs = qs.filter(
                    Q(admin_institution__id=inst_int)
                    | Q(faculty_profile__institution_id=inst_int)
                    | Q(student_profile__institution_id=inst_int)
                )
            except (ValueError, TypeError):
                pass

        if dept_filter and dept_filter != 'all':
            qs = qs.filter(
                Q(faculty_profile__department__iexact=dept_filter)
                | Q(student_profile__department__iexact=dept_filter)
            )

        paginator = Paginator(qs, page_size)
        page_obj = paginator.get_page(page_num)

        items = []
        for u in page_obj:
            user_role = 'student'
            inst_obj = None
            dept = ''
            code_id = ''

            if hasattr(u, 'admin_profile'):
                user_role = 'admin'
                inst_obj = getattr(u, 'admin_institution', None)
            elif hasattr(u, 'faculty_profile'):
                user_role = 'faculty'
                inst_obj = u.faculty_profile.institution
                dept = u.faculty_profile.department
                code_id = u.faculty_profile.employee_id
            elif hasattr(u, 'student_profile'):
                user_role = 'student'
                inst_obj = u.student_profile.institution
                dept = u.student_profile.department
                code_id = u.student_profile.student_id

            items.append({
                'id': u.id,
                'username': u.username,
                'email': u.email,
                'full_name': f'{u.first_name} {u.last_name}'.strip() or u.username,
                'role': user_role,
                'identifier': code_id,
                'department': dept or 'Unassigned',
                'is_active': u.is_active,
                'institution': {
                    'id': inst_obj.id if inst_obj else None,
                    'name': inst_obj.institution_name if inst_obj else 'Unassigned',
                    'code': inst_obj.institution_code if inst_obj else '',
                },
                'date_joined': u.date_joined.isoformat() if u.date_joined else None,
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

        # Export as CSV
        if export:
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = f'attachment; filename="superadmin_audit_{int(time.time())}.csv"'
            writer = csv.writer(response)
            writer.writerow(['ID', 'Timestamp (UTC)', 'Actor', 'Action', 'Target Entity', 'Target ID', 'IP Address', 'Description'])
            for log in qs[:5000]:
                writer.writerow([
                    log.id,
                    log.created_at.isoformat(),
                    log.actor_username,
                    log.action,
                    log.target_entity,
                    log.target_id,
                    log.ip_address,
                    log.description,
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
            'description', 'before_state', 'after_state', 'ip_address', 'created_at'
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
    """
    authentication_classes = [SuperAdminAuthentication]
    permission_classes = [IsSuperAdmin, IsEnrolledSuperAdmin]

    def get_backup_dir(self):
        backup_dir = os.path.abspath(os.path.join(settings.BASE_DIR, '..', 'backups'))
        os.makedirs(backup_dir, exist_ok=True)
        return backup_dir

    def get(self, request):
        backup_dir = self.get_backup_dir()
        files = []
        for fname in os.listdir(backup_dir):
            if fname.endswith('.sql'):
                fpath = os.path.join(backup_dir, fname)
                st = os.stat(fpath)
                files.append({
                    'filename': fname,
                    'size_mb': round(st.st_size / (1024 * 1024), 2),
                    'created_at': datetime.datetime.fromtimestamp(st.st_ctime).isoformat(),
                })
        files.sort(key=lambda x: x['created_at'], reverse=True)
        return Response({'status': 'success', 'backups': files}, status=status.HTTP_200_OK)

    def post(self, request):
        profile = request.user.super_admin_profile
        if not profile.is_reauth_valid():
            raise exceptions.PermissionDenied({'status': 'reauth_required', 'message': 'Re-authentication required.'})

        backup_dir = self.get_backup_dir()
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        dump_filename = f'examai_backup_{timestamp}.sql'
        dump_path = os.path.join(backup_dir, dump_filename)

        mysqldump_bin = r'C:\Program Files\MySQL\MySQL Server 8.4\bin\mysqldump.exe'
        if not os.path.exists(mysqldump_bin):
            mysqldump_bin = 'mysqldump'

        db = settings.DATABASES['default']
        env = os.environ.copy()
        env['MYSQL_PWD'] = db['PASSWORD']
        cmd = [
            mysqldump_bin,
            '-h', db['HOST'],
            '-P', str(db['PORT']),
            '-u', db['USER'],
            db['NAME'],
        ]

        try:
            with open(dump_path, 'wb') as outfile:
                res = subprocess.run(cmd, env=env, stdout=outfile, stderr=subprocess.PIPE, timeout=60)
            if res.returncode != 0:
                raise Exception(res.stderr.decode('utf-8', errors='ignore'))
        except Exception as exc:
            logger.error('Database backup failed: %s', exc)
            return Response({'status': 'error', 'message': f'Backup failed: {str(exc)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        size_mb = round(os.path.getsize(dump_path) / (1024 * 1024), 2)
        log_super_admin_action(
            request,
            action='database_backup_created',
            target_entity='Backup',
            target_id=dump_filename,
            description=f'Created database backup "{dump_filename}" ({size_mb} MB).',
            after_state={'filename': dump_filename, 'size_mb': size_mb},
        )

        return Response(
            {
                'status': 'success',
                'message': f'Backup "{dump_filename}" created successfully.',
                'backup': {'filename': dump_filename, 'size_mb': size_mb},
            },
            status=status.HTTP_201_CREATED,
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

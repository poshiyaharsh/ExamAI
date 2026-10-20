import datetime
import logging
import jwt
from django.conf import settings
from django.contrib.auth import get_user_model
from django.http import Http404
from django.utils import timezone
from rest_framework import authentication, exceptions

from superadmin.audit import get_client_ip
from superadmin.models import SuperAdminProfile

User = get_user_model()
logger = logging.getLogger(__name__)


def generate_super_admin_token(user: User, session_id: str | None = None) -> str:
    """Generate a signed JWT token strictly scoped to super_admin."""
    now = timezone.now()
    lifetime_seconds = getattr(settings, 'SUPER_ADMIN_SESSION_AGE', 900)  # 15 minutes default
    payload = {
        'user_id': user.id,
        'username': user.username,
        'role': 'super_admin',
        'session_id': session_id or datetime.datetime.now().strftime('%Y%m%d%H%M%S%f'),
        'iat': int(now.timestamp()),
        'exp': int((now + datetime.timedelta(seconds=lifetime_seconds)).timestamp()),
    }
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm='HS256')
    return token


class SuperAdminAuthentication(authentication.BaseAuthentication):
    """
    Dedicated, isolated authentication backend for Super Admin portal.
    Enforces IP allowlisting, active session validation, sliding idle timeout,
    and uniform 404 response on probing.
    """

    def authenticate(self, request):
        token = None
        is_cookie_auth = False

        # Check Authorization header
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        if auth_header.startswith('Bearer '):
            token = auth_header.split(' ', 1)[1].strip()

        # Check Cookie fallback
        if not token:
            token = request.COOKIES.get('__Host-examai_sa_session') or request.COOKIES.get('examai_sa_session')
            if token:
                is_cookie_auth = True

        if not token:
            return None

        # Cookie fallback CSRF defense: require custom header
        if is_cookie_auth:
            custom_header = request.META.get('HTTP_X_SUPER_ADMIN_REQUEST') or request.META.get('HTTP_X_CSRFTOKEN')
            if not custom_header:
                raise Http404()

        # Verify IP Allowlist if configured
        allowed_ips = getattr(settings, 'SUPER_ADMIN_ALLOWED_IPS', [])
        client_ip = get_client_ip(request)
        if allowed_ips and client_ip not in allowed_ips:
            logger.warning('SuperAdmin access blocked for non-allowlisted IP: %s', client_ip)
            raise Http404()

        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
        except jwt.ExpiredSignatureError:
            raise exceptions.AuthenticationFailed('Super Admin session has expired. Please log in again.')
        except jwt.InvalidTokenError:
            # Uniform 404 on malformed/tampered probes
            raise Http404()

        if payload.get('role') != 'super_admin':
            raise Http404()

        user_id = payload.get('user_id')
        user = User.objects.filter(id=user_id).select_related('super_admin_profile').first()
        if not user or not hasattr(user, 'super_admin_profile'):
            raise Http404()

        profile = user.super_admin_profile
        if profile.is_locked():
            raise exceptions.AuthenticationFailed('Account is temporarily locked. Try again later.')

        # Active Session ID check (server-side token revocation on logout)
        token_session_id = payload.get('session_id')
        if not profile.active_session_id or token_session_id != profile.active_session_id:
            raise exceptions.AuthenticationFailed('Super Admin session has ended or been revoked. Please log in again.')

        # Sliding idle timeout (15 minutes of inactivity)
        idle_timeout = getattr(settings, 'SUPER_ADMIN_IDLE_TIMEOUT', 900)
        if profile.last_activity_at:
            idle_seconds = (timezone.now() - profile.last_activity_at).total_seconds()
            if idle_seconds > idle_timeout:
                profile.active_session_id = ''
                profile.save(update_fields=['active_session_id'])
                raise exceptions.AuthenticationFailed('Session expired due to inactivity. Please log in again.')

        # Update last activity timestamp
        profile.last_activity_at = timezone.now()
        profile.save(update_fields=['last_activity_at'])

        request.is_super_admin = True
        request.super_admin_profile = profile

        return (user, payload)

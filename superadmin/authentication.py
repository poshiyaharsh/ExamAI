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
    Enforces IP allowlisting, token role verification, and uniform 404 response on probing.
    """

    def authenticate(self, request):
        token = None

        # Check Authorization header
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        if auth_header.startswith('Bearer '):
            token = auth_header.split(' ', 1)[1].strip()

        # Check Cookie fallback
        if not token:
            token = request.COOKIES.get('__Host-examai_sa_session') or request.COOKIES.get('examai_sa_session')

        if not token:
            return None

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

        request.is_super_admin = True
        request.super_admin_profile = profile

        return (user, payload)

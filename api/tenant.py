"""Centralized multi-institute tenant isolation layer for ExamAI."""

import logging
from django.core.exceptions import PermissionDenied
from django.http import Http404
from rest_framework import status
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication

from admins.models import AdminInstitution

logger = logging.getLogger(__name__)


def get_user_institution(user):
    """
    Resolve the active AdminInstitution record for any user role (Admin, Faculty, Student).
    """
    if not user or not user.is_authenticated:
        return None

    # 1. Admin
    admin_inst = getattr(user, 'admin_institution', None)
    if admin_inst:
        return admin_inst

    # 2. Faculty
    faculty_profile = getattr(user, 'faculty_profile', None)
    if faculty_profile and faculty_profile.institution:
        return faculty_profile.institution

    # 3. Student
    student_profile = getattr(user, 'student_profile', None)
    if student_profile and student_profile.institution:
        return student_profile.institution

    # Fallback lookup in case related names are not loaded
    inst = AdminInstitution.objects.filter(admin=user).first()
    if inst:
        return inst

    return None


def verify_institution_active(institution):
    """
    Raise AuthenticationFailed if the institution is suspended or inactive.
    """
    if not institution:
        raise AuthenticationFailed('Account is not associated with any active institution.')

    inst_status = getattr(institution, 'status', AdminInstitution.STATUS_ACTIVE)
    if inst_status == AdminInstitution.STATUS_SUSPENDED:
        raise AuthenticationFailed('Your institution has been suspended. Please contact your administrator.')


class TenantJWTAuthentication(JWTAuthentication):
    """
    JWT Authentication that strictly verifies institution identity from the token
    against the database user record and verifies institution active status.
    Sets request.tenant and request.tenant_id on every authenticated request.
    """

    def authenticate(self, request):
        auth_result = super().authenticate(request)
        if auth_result is None:
            return None

        user, validated_token = auth_result
        institution = get_user_institution(user)

        # Ensure institution is active (blocks suspended institutions immediately)
        if institution:
            verify_institution_active(institution)

        token_inst_id = validated_token.get('institution_id')
        if token_inst_id is not None and institution:
            if int(token_inst_id) != int(institution.id):
                logger.warning(
                    'Tenant spoofing attempt detected user=%s token_inst=%s db_inst=%s',
                    user.username, token_inst_id, institution.id
                )
                raise AuthenticationFailed('Security violation: token institution mismatch.')

        request.tenant = institution
        request.tenant_id = institution.id if institution else None
        return (user, validated_token)


class TenantScopedMixin:
    """
    Mixin for APIViews to ensure request.tenant is present and valid.
    Reject requests without valid tenant context.
    """

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if request.user and request.user.is_authenticated:
            institution = getattr(request, 'tenant', None)
            if not institution:
                institution = get_user_institution(request.user)
                request.tenant = institution
                request.tenant_id = institution.id if institution else None

            if not request.tenant:
                raise PermissionDenied('No active institution associated with this user.')
            verify_institution_active(request.tenant)


def get_tenant_object_or_404(klass, institution, **kwargs):
    """
    Fetch an object strictly scoped to the tenant.
    Returns the object if found and belongs to the tenant.
    Raises Http404 if object does not exist or belongs to another tenant.
    This guarantees zero IDOR leakage and identical 404 response.
    """
    if not institution:
        raise Http404('Resource not found in this institution.')

    inst_id = institution.id if hasattr(institution, 'id') else institution
    try:
        return klass.objects.get(institution_id=inst_id, **kwargs)
    except klass.DoesNotExist:
        raise Http404('Resource not found in this institution.')


def get_tenant_cache_version(institution_id):
    """
    Retrieve current cache version integer for an institution.
    """
    from django.core.cache import cache
    key = f"tenant:{institution_id}:cache_ver"
    v = cache.get(key)
    if v is None:
        v = 1
        cache.set(key, v, timeout=86400 * 30)
    return v


def bump_tenant_cache_version(institution_id):
    """
    Increment cache version for an institution, instantly invalidating all
    cached student exam lists, dashboards, and stats within this tenant.
    """
    from django.core.cache import cache
    key = f"tenant:{institution_id}:cache_ver"
    try:
        cache.incr(key)
    except Exception:
        current = cache.get(key) or 1
        cache.set(key, current + 1, timeout=86400 * 30)


def get_tenant_cache_key(institution_id, key, user_id=None, version=None):
    """
    Generate an institution-isolated cache key with user scope and live tenant version.
    Format: tenant:{inst_id}:ver_{v}[:u:{user_id}]:{key}
    """
    v = version if version is not None else get_tenant_cache_version(institution_id)
    u_part = f":u:{user_id}" if user_id else ""
    return f"tenant:{institution_id}:ver_{v}{u_part}:{key}"


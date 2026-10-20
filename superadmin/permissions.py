from django.http import Http404
from rest_framework import exceptions, permissions


class IsSuperAdmin(permissions.BasePermission):
    """
    Ensures the requesting user is the authenticated Super Admin.
    Unauthenticated users or unauthorized roles immediately receive a plain 404.
    """

    def has_permission(self, request, view):
        user = getattr(request, 'user', None)
        if not user or not user.is_authenticated or not hasattr(user, 'super_admin_profile'):
            raise Http404()

        profile = user.super_admin_profile
        if profile.is_locked():
            raise exceptions.AuthenticationFailed('Super Admin account is temporarily locked.')

        return True


class IsEnrolledSuperAdmin(permissions.BasePermission):
    """
    Mandates that TOTP 2FA enrollment has been completed before access is granted.
    """

    def has_permission(self, request, view):
        user = getattr(request, 'user', None)
        if not user or not user.is_authenticated or not hasattr(user, 'super_admin_profile'):
            raise Http404()

        profile = user.super_admin_profile
        if not profile.is_totp_enrolled:
            raise exceptions.PermissionDenied(
                'TOTP 2FA enrollment is required before accessing Super Admin features.'
            )

        return True


class RequiresReauth(permissions.BasePermission):
    """
    Requires recent password + 2FA re-authentication within the past 5 minutes (300 seconds)
    for high-risk operations (destructive actions, security settings, credential resets, backups).
    """
    message = 'Re-authentication required. Please verify your credentials to perform this action.'

    def has_permission(self, request, view):
        user = getattr(request, 'user', None)
        if not user or not user.is_authenticated or not hasattr(user, 'super_admin_profile'):
            raise Http404()

        profile = user.super_admin_profile
        if not profile.is_reauth_valid(max_age_seconds=300):
            raise exceptions.PermissionDenied({
                'status': 'reauth_required',
                'message': self.message,
            })

        return True

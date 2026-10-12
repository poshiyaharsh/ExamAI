"""Permissions for the Question Bank API."""

from rest_framework.permissions import BasePermission
from admins.models import AdminProfile
from faculty.models import FacultyProfile
from api.utils.departments import get_faculty_department


class IsAdminQuestionBank(BasePermission):
    """
    Strict Admin-only permission for Question Bank write/mutation endpoints.
    """
    message = 'Administrator access for this institution is required.'

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        return AdminProfile.objects.filter(user=user).exists()


class IsAdminOrFacultyDepartmentReadOnly(BasePermission):
    """
    Allows Admin full access.
    Allows Faculty READ-ONLY access restricted to their own department questions.
    Students are strictly forbidden (returns False -> 403).
    """
    message = 'Question Bank access denied. Valid Admin or Faculty credentials required.'

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False

        # Admin has full access
        if AdminProfile.objects.filter(user=user).exists():
            return True

        # Faculty only gets safe methods (GET, HEAD, OPTIONS)
        if request.method in ('GET', 'HEAD', 'OPTIONS'):
            if FacultyProfile.objects.filter(user=user).exists():
                return True

        return False

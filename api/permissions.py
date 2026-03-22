from rest_framework.permissions import BasePermission

from admins.models import AdminProfile
from faculty.models import FacultyProfile
from students.models import StudentProfile


class IsAdminUser(BasePermission):
    message = 'Admin access required.'

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and AdminProfile.objects.filter(user=user).exists())


class IsFacultyUser(BasePermission):
    message = 'Faculty access required.'

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and FacultyProfile.objects.filter(user=user).exists())


class IsStudentUser(BasePermission):
    message = 'Student access required.'

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and StudentProfile.objects.filter(user=user).exists())

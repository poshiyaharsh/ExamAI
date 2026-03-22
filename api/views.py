from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
import secrets

from .models import PasswordResetOTP
from .serializers import (
    ChangePasswordSerializer,
    DepartmentSerializer,
    ForgotPasswordSerializer,
    InstitutionSerializer,
    ResetPasswordSerializer,
    TestMessageSerializer,
    VerifyOTPSerializer,
)
from admins.models import AdminDepartment, AdminInstitution
from admins.models import AdminProfile
from faculty.models import FacultyProfile
from students.models import StudentProfile
from .permissions import IsAdminUser


DEFAULT_DEPARTMENT_NAMES = [
    'Computer Science',
    'Information Technology',
    'Electronics and Communication',
    'Mechanical Engineering',
    'Civil Engineering',
    'Electrical Engineering',
    'Business Administration',
    'Commerce',
    'Mathematics',
    'Physics',
    'Chemistry',
]


class TestAPIView(APIView):
    def get(self, request):
        return Response(
            {
                'status': 'success',
                'message': 'Django API is connected successfully.',
                'data': {
                    'course': 'Mini Project Integration',
                    'backend': 'Django REST Framework',
                },
            },
            status=status.HTTP_200_OK,
        )

    def post(self, request):
        serializer = TestMessageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        validated_data = serializer.validated_data

        return Response(
            {
                'status': 'success',
                'message': f"Hello {validated_data['name']}, your message was received.",
                'submitted': validated_data,
            },
            status=status.HTTP_201_CREATED,
        )


def _resolve_user_role(user, token_role=None):
    roles = []
    if AdminProfile.objects.filter(user=user).exists():
        roles.append('admin')
    if FacultyProfile.objects.filter(user=user).exists():
        roles.append('faculty')
    if StudentProfile.objects.filter(user=user).exists():
        roles.append('student')

    if not roles:
        return None

    if token_role in roles:
        return token_role

    if 'admin' in roles:
        return 'admin'
    if 'faculty' in roles:
        return 'faculty'
    return 'student'


class AuthMeAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        token_role = None
        if request.auth and hasattr(request.auth, 'get'):
            token_role = request.auth.get('role')

        role = _resolve_user_role(request.user, token_role=token_role)
        if not role:
            return Response(
                {
                    'status': 'error',
                    'message': 'No role profile is associated with this account.',
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        return Response(
            {
                'status': 'success',
                'message': 'Authenticated user fetched successfully.',
                'user': {
                    'id': request.user.id,
                    'first_name': request.user.first_name,
                    'last_name': request.user.last_name,
                    'email': request.user.email,
                },
                'role': role,
            },
            status=status.HTTP_200_OK,
        )


class ChangePasswordAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)

        request.user.set_password(serializer.validated_data['new_password'])
        request.user.save(update_fields=['password'])

        return Response(
            {
                'status': 'success',
                'message': 'Password updated successfully.',
            },
            status=status.HTTP_200_OK,
        )


class ForgotPasswordAPIView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email']

        user = User.objects.filter(username=email).first()
        if not user:
            return Response(
                {
                    'status': 'error',
                    'message': 'Email is not registered.',
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        PasswordResetOTP.objects.filter(user=user, is_used=False).update(is_used=True)

        otp_code = f"{secrets.randbelow(1000000):06d}"
        otp_record = PasswordResetOTP(
            user=user,
            expires_at=timezone.now() + timedelta(minutes=10),
        )
        otp_record.set_otp(otp_code)
        otp_record.save()

        send_mail(
            subject='ExamAI Password Reset OTP',
            message=(
                f'Your ExamAI password reset OTP is: {otp_code}\n\n'
                'It will expire in 10 minutes. If you did not request this, ignore this email.'
            ),
            from_email=None,
            recipient_list=[email],
            fail_silently=False,
        )

        response_payload = {
            'status': 'success',
            'message': 'Reset instructions have been sent to your email.',
        }
        if settings.DEBUG and settings.EMAIL_BACKEND == 'django.core.mail.backends.console.EmailBackend':
            response_payload['debug_otp'] = otp_code

        return Response(
            response_payload,
            status=status.HTTP_200_OK,
        )


class VerifyOTPAPIView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = VerifyOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data['email']
        otp = serializer.validated_data['otp']

        user = User.objects.filter(username=email).first()
        if not user:
            return Response(
                {
                    'status': 'error',
                    'message': 'Email is not registered.',
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        otp_record = PasswordResetOTP.objects.filter(user=user, is_used=False).order_by('-created_at').first()
        if not otp_record:
            return Response(
                {
                    'status': 'error',
                    'message': 'OTP not found. Request a new one.',
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if otp_record.is_otp_expired:
            otp_record.is_used = True
            otp_record.save(update_fields=['is_used'])
            return Response(
                {
                    'status': 'error',
                    'message': 'OTP has expired. Request a new one.',
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not otp_record.check_otp(otp):
            return Response(
                {
                    'status': 'error',
                    'message': 'Invalid OTP.',
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        reset_token = secrets.token_urlsafe(32)
        otp_record.is_verified = True
        otp_record.set_reset_token(reset_token)
        otp_record.reset_token_expires_at = timezone.now() + timedelta(minutes=10)
        otp_record.save(update_fields=['is_verified', 'reset_token_hash', 'reset_token_expires_at'])

        return Response(
            {
                'status': 'success',
                'message': 'OTP verified successfully.',
                'reset_token': reset_token,
            },
            status=status.HTTP_200_OK,
        )


class ResetPasswordAPIView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data['email']
        reset_token = serializer.validated_data['reset_token']
        new_password = serializer.validated_data['new_password']

        user = User.objects.filter(username=email).first()
        if not user:
            return Response(
                {
                    'status': 'error',
                    'message': 'Email is not registered.',
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        otp_record = (
            PasswordResetOTP.objects.filter(user=user, is_used=False, is_verified=True)
            .order_by('-created_at')
            .first()
        )

        if not otp_record:
            return Response(
                {
                    'status': 'error',
                    'message': 'Verification not found. Verify OTP first.',
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if otp_record.is_reset_token_expired:
            otp_record.is_used = True
            otp_record.save(update_fields=['is_used'])
            return Response(
                {
                    'status': 'error',
                    'message': 'Reset session has expired. Start again.',
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not otp_record.check_reset_token(reset_token):
            return Response(
                {
                    'status': 'error',
                    'message': 'Invalid reset session.',
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.set_password(new_password)
        user.save(update_fields=['password'])

        otp_record.is_used = True
        otp_record.save(update_fields=['is_used'])

        return Response(
            {
                'status': 'success',
                'message': 'Password has been reset successfully.',
            },
            status=status.HTTP_200_OK,
        )


class InstitutionListAPIView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        institutions = AdminInstitution.objects.order_by('institution_name')
        serializer = InstitutionSerializer(institutions, many=True)
        return Response(
            {
                'status': 'success',
                'message': 'Institutions fetched successfully.',
                'data': serializer.data,
            },
            status=status.HTTP_200_OK,
        )


class DepartmentListAPIView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        institution = AdminInstitution.objects.filter(admin=request.user).first()
        if not institution:
            return Response(
                {
                    'status': 'success',
                    'message': 'Institution information not created yet.',
                    'data': [],
                },
                status=status.HTTP_200_OK,
            )

        existing_departments = set(
            AdminDepartment.objects.filter(institution=institution).values_list('department_name', flat=True)
        )

        # Ensure the standard department catalog exists for each institution.
        missing_defaults = [
            name for name in DEFAULT_DEPARTMENT_NAMES if name not in existing_departments
        ]
        if missing_defaults:
            AdminDepartment.objects.bulk_create(
                [
                    AdminDepartment(institution=institution, department_name=department_name)
                    for department_name in missing_defaults
                ],
                ignore_conflicts=True,
            )

        # Keep department table synced with existing student records for this institution.
        student_departments = (
            StudentProfile.objects.filter(institution=institution)
            .exclude(department='')
            .values_list('department', flat=True)
            .distinct()
        )
        existing_departments = set(
            AdminDepartment.objects.filter(institution=institution).values_list('department_name', flat=True)
        )
        missing_departments = [
            department_name.strip()
            for department_name in student_departments
            if department_name and department_name.strip() and department_name.strip() not in existing_departments
        ]
        if missing_departments:
            AdminDepartment.objects.bulk_create(
                [
                    AdminDepartment(institution=institution, department_name=department_name)
                    for department_name in missing_departments
                ],
                ignore_conflicts=True,
            )

        departments = AdminDepartment.objects.filter(institution=institution).order_by('department_name')
        serializer = DepartmentSerializer(departments, many=True)
        return Response(
            {
                'status': 'success',
                'message': 'Departments fetched successfully.',
                'data': serializer.data,
            },
            status=status.HTTP_200_OK,
        )

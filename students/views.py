import logging

from django.conf import settings
from django.db import OperationalError, ProgrammingError
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from api.permissions import IsStudentUser

from admins.models import AdminInstitution
from .models import StudentProfile
from .serializers import (
    StudentLoginSerializer,
    StudentProfileDepartmentUpdateSerializer,
    StudentProfileSerializer,
    StudentSignupSerializer,
)


logger = logging.getLogger(__name__)


def _error_response(exc, log_message, fallback_message):
    logger.exception(log_message)
    message = str(exc).strip()
    if settings.DEBUG and message:
        response_message = message
    else:
        response_message = fallback_message

    return Response(
        {
            'status': 'error',
            'message': response_message,
        },
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )


def _build_token_payload(user):
    refresh = RefreshToken.for_user(user)
    refresh['role'] = 'student'
    access = refresh.access_token
    access['role'] = 'student'
    return {
        'refresh': str(refresh),
        'access': str(access),
    }


def _get_or_create_student_profile(user):
    profile, _ = StudentProfile.objects.get_or_create(user=user)
    if not profile.institution:
        default_institution = AdminInstitution.objects.order_by('id').first()
        if default_institution:
            profile.institution = default_institution
            profile.save(update_fields=['institution'])
    profile.ensure_student_id()
    return profile


class StudentSignupAPIView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = StudentSignupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        return Response(
            {
                'status': 'success',
                'message': 'Student account created successfully.',
                'tokens': _build_token_payload(user),
                'user': {
                    'id': user.id,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'email': user.email,
                    'role': 'student',
                },
            },
            status=status.HTTP_201_CREATED,
        )


class StudentLoginAPIView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = StudentLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']

        return Response(
            {
                'status': 'success',
                'message': 'Student login successful.',
                'tokens': _build_token_payload(user),
                'user': {
                    'id': user.id,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'email': user.email,
                    'role': 'student',
                },
            },
            status=status.HTTP_200_OK,
        )


class StudentProfileAPIView(APIView):
    permission_classes = [IsAuthenticated, IsStudentUser]

    def get(self, request):
        try:
            profile = _get_or_create_student_profile(request.user)
        except (OperationalError, ProgrammingError) as exc:
            return _error_response(
                exc,
                f'Student profile fetch database error for user_id={request.user.id}',
                'Database schema issue detected. Please run migrations.',
            )
        except Exception as exc:
            return _error_response(
                exc,
                f'Unexpected student profile fetch error for user_id={request.user.id}',
                'Unable to fetch student profile.',
            )
        serializer = StudentProfileSerializer(profile)
        return Response(
            {
                'status': 'success',
                'message': 'Student profile fetched successfully.',
                'data': serializer.data,
            },
            status=status.HTTP_200_OK,
        )

    def put(self, request):
        try:
            profile = _get_or_create_student_profile(request.user)
        except (OperationalError, ProgrammingError) as exc:
            return _error_response(
                exc,
                f'Student profile update database error for user_id={request.user.id}',
                'Database schema issue detected. Please run migrations.',
            )
        except Exception as exc:
            return _error_response(
                exc,
                f'Unexpected student profile update error for user_id={request.user.id}',
                'Unable to update student profile.',
            )
        serializer = StudentProfileDepartmentUpdateSerializer(profile, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        response_serializer = StudentProfileSerializer(profile)
        return Response(
            {
                'status': 'success',
                'message': 'Department updated successfully.',
                'data': response_serializer.data,
            },
            status=status.HTTP_200_OK,
        )

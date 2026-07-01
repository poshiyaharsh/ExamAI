import logging

from django.conf import settings
from django.db import OperationalError, ProgrammingError
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from api.permissions import IsFacultyUser

from admins.models import AdminInstitution
from .models import FacultyProfile
from .serializers import (
    FacultyLoginSerializer,
    FacultyProfileDepartmentUpdateSerializer,
    FacultyProfileSerializer,
    FacultySignupSerializer,
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
    refresh['role'] = 'faculty'
    access = refresh.access_token
    access['role'] = 'faculty'
    return {
        'refresh': str(refresh),
        'access': str(access),
    }


def _get_or_create_faculty_profile(user):
    profile, _ = FacultyProfile.objects.get_or_create(user=user)
    if not profile.institution:
        default_institution = AdminInstitution.objects.order_by('id').first()
        if default_institution:
            profile.institution = default_institution
            profile.save(update_fields=['institution'])
    profile.ensure_employee_id()
    return profile


class FacultySignupAPIView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = FacultySignupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        return Response(
            {
                'status': 'success',
                'message': 'Faculty account created successfully.',
                'tokens': _build_token_payload(user),
                'user': {
                    'id': user.id,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'email': user.email,
                    'role': 'faculty',
                },
            },
            status=status.HTTP_201_CREATED,
        )


class FacultyLoginAPIView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = FacultyLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']

        return Response(
            {
                'status': 'success',
                'message': 'Faculty login successful.',
                'tokens': _build_token_payload(user),
                'user': {
                    'id': user.id,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'email': user.email,
                    'role': 'faculty',
                },
            },
            status=status.HTTP_200_OK,
        )


class FacultyProfileAPIView(APIView):
    permission_classes = [IsAuthenticated, IsFacultyUser]

    def get(self, request):
        try:
            profile = _get_or_create_faculty_profile(request.user)
        except (OperationalError, ProgrammingError) as exc:
            return _error_response(
                exc,
                f'Faculty profile fetch database error for user_id={request.user.id}',
                'Database schema issue detected. Please run migrations.',
            )
        except Exception as exc:
            return _error_response(
                exc,
                f'Unexpected faculty profile fetch error for user_id={request.user.id}',
                'Unable to fetch faculty profile.',
            )
        serializer = FacultyProfileSerializer(profile)
        return Response(
            {
                'status': 'success',
                'message': 'Faculty profile fetched successfully.',
                'data': serializer.data,
            },
            status=status.HTTP_200_OK,
        )

    def put(self, request):
        try:
            profile = _get_or_create_faculty_profile(request.user)
        except (OperationalError, ProgrammingError) as exc:
            return _error_response(
                exc,
                f'Faculty profile update database error for user_id={request.user.id}',
                'Database schema issue detected. Please run migrations.',
            )
        except Exception as exc:
            return _error_response(
                exc,
                f'Unexpected faculty profile update error for user_id={request.user.id}',
                'Unable to update faculty profile.',
            )

        serializer = FacultyProfileDepartmentUpdateSerializer(profile, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        response_serializer = FacultyProfileSerializer(profile)
        return Response(
            {
                'status': 'success',
                'message': 'Department updated successfully.',
                'data': response_serializer.data,
            },
            status=status.HTTP_200_OK,
        )

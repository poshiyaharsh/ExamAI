from rest_framework import status
from django.db import OperationalError
from rest_framework.permissions import AllowAny
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from admins.models import AdminInstitution
from .models import StudentProfile
from .serializers import (
    StudentLoginSerializer,
    StudentProfileDepartmentUpdateSerializer,
    StudentProfileSerializer,
    StudentSignupSerializer,
)


def _build_token_payload(user):
    refresh = RefreshToken.for_user(user)
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
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
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            profile = _get_or_create_student_profile(request.user)
        except OperationalError:
            return Response(
                {
                    'status': 'error',
                    'message': 'Database setup is incomplete. Run migrations using: python manage.py migrate',
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
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
        except OperationalError:
            return Response(
                {
                    'status': 'error',
                    'message': 'Database setup is incomplete. Run migrations using: python manage.py migrate',
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
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

from rest_framework import status
from django.db import OperationalError
from rest_framework.permissions import AllowAny
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .models import AdminInstitution
from .serializers import (
    AdminInstitutionCreateSerializer,
    AdminInstitutionSerializer,
    AdminInstitutionUpdateSerializer,
    AdminLoginSerializer,
    AdminSignupSerializer,
)


def _build_token_payload(user):
    refresh = RefreshToken.for_user(user)
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
    }


class AdminSignupAPIView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = AdminSignupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        return Response(
            {
                'status': 'success',
                'message': 'Admin account created successfully.',
                'tokens': _build_token_payload(user),
                'user': {
                    'id': user.id,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'email': user.email,
                    'role': 'admin',
                },
            },
            status=status.HTTP_201_CREATED,
        )


class AdminLoginAPIView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = AdminLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']

        return Response(
            {
                'status': 'success',
                'message': 'Admin login successful.',
                'tokens': _build_token_payload(user),
                'user': {
                    'id': user.id,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'email': user.email,
                    'role': 'admin',
                },
            },
            status=status.HTTP_200_OK,
        )


class AdminInstitutionAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            institution = AdminInstitution.objects.filter(admin=request.user).first()
        except OperationalError:
            return Response(
                {
                    'status': 'error',
                    'message': 'Database setup is incomplete. Run migrations using: python manage.py migrate',
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        if not institution:
            return Response(
                {
                    'status': 'success',
                    'message': 'Institution information not created yet.',
                    'data': {
                        'institution_name': '',
                        'institution_code': '',
                        'address': '',
                        'phone': '',
                        'email': request.user.email,
                    },
                    'exists': False,
                },
                status=status.HTTP_200_OK,
            )

        serializer = AdminInstitutionSerializer(institution)
        return Response(
            {
                'status': 'success',
                'message': 'Institution information fetched successfully.',
                'data': serializer.data,
                'exists': True,
            },
            status=status.HTTP_200_OK,
        )

    def post(self, request):
        if AdminInstitution.objects.filter(admin=request.user).exists():
            return Response(
                {
                    'status': 'error',
                    'message': 'Institution information already exists. Use update instead.',
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = AdminInstitutionCreateSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        institution = serializer.save()
        response_serializer = AdminInstitutionSerializer(institution)

        return Response(
            {
                'status': 'success',
                'message': 'Institution information created successfully.',
                'data': response_serializer.data,
                'exists': True,
            },
            status=status.HTTP_201_CREATED,
        )

    def put(self, request):
        institution = AdminInstitution.objects.filter(admin=request.user).first()
        if not institution:
            return Response(
                {
                    'status': 'error',
                    'message': 'Institution information does not exist. Create it first.',
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = AdminInstitutionUpdateSerializer(institution, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        response_serializer = AdminInstitutionSerializer(institution)

        return Response(
            {
                'status': 'success',
                'message': 'Institution information updated successfully.',
                'data': response_serializer.data,
                'exists': True,
            },
            status=status.HTTP_200_OK,
        )

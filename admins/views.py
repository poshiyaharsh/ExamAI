from rest_framework import status
from django.db import OperationalError
from django.db import transaction
from django.db.models import Q
from rest_framework.permissions import AllowAny
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from api.permissions import IsAdminUser

from students.models import StudentProfile
from .models import AdminInstitution, AdminProfile
from .serializers import (
    AdminInstitutionCreateSerializer,
    AdminInstitutionSerializer,
    AdminStudentCreateSerializer,
    AdminStudentDetailSerializer,
    AdminStudentListSerializer,
    AdminStudentUpdateSerializer,
    AdminInstitutionUpdateSerializer,
    AdminLoginSerializer,
    AdminSignupSerializer,
)


def _build_token_payload(user):
    refresh = RefreshToken.for_user(user)
    refresh['role'] = 'admin'
    access = refresh.access_token
    access['role'] = 'admin'
    return {
        'refresh': str(refresh),
        'access': str(access),
    }


def _ensure_admin_user(user):
    return AdminProfile.objects.filter(user=user).exists()


def _get_admin_institution(user):
    return AdminInstitution.objects.filter(admin=user).first()


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
    permission_classes = [IsAuthenticated, IsAdminUser]

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


class AdminStudentsAPIView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        if not _ensure_admin_user(request.user):
            return Response(
                {'status': 'error', 'message': 'Only admin users can access this resource.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            institution = _get_admin_institution(request.user)
            if not institution:
                return Response(
                    {
                        'status': 'success',
                        'message': 'Institution information not created yet.',
                        'data': [],
                    },
                    status=status.HTTP_200_OK,
                )

            queryset = StudentProfile.objects.select_related('user').filter(institution=institution)

            search_query = request.query_params.get('search', '').strip()
            if search_query:
                queryset = queryset.filter(
                    Q(user__first_name__icontains=search_query)
                    | Q(user__last_name__icontains=search_query)
                    | Q(user__email__icontains=search_query)
                    | Q(student_id__icontains=search_query)
                )

            department = request.query_params.get('department', '').strip()
            if department:
                queryset = queryset.filter(department__iexact=department)

            students = queryset.order_by('user__first_name', 'user__last_name', 'id')
            serializer = AdminStudentListSerializer(students, many=True)

            return Response(
                {
                    'status': 'success',
                    'message': 'Students fetched successfully.',
                    'data': serializer.data,
                },
                status=status.HTTP_200_OK,
            )
        except OperationalError:
            return Response(
                {
                    'status': 'error',
                    'message': 'Database setup is incomplete. Run migrations using: python manage.py migrate',
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def post(self, request):
        if not _ensure_admin_user(request.user):
            return Response(
                {'status': 'error', 'message': 'Only admin users can access this resource.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            institution = _get_admin_institution(request.user)
            if not institution:
                return Response(
                    {
                        'status': 'error',
                        'message': 'Institution information does not exist. Create it first.',
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            serializer = AdminStudentCreateSerializer(
                data=request.data,
                context={'institution': institution},
            )
            serializer.is_valid(raise_exception=True)
            student_profile = serializer.save()

            response_serializer = AdminStudentDetailSerializer(student_profile)
            return Response(
                {
                    'status': 'success',
                    'message': 'Student Created Successfully',
                    'data': {
                        **response_serializer.data,
                        'institution_id': institution.id,
                        'role': 'student',
                    },
                },
                status=status.HTTP_201_CREATED,
            )
        except OperationalError:
            return Response(
                {
                    'status': 'error',
                    'message': 'Database setup is incomplete. Run migrations using: python manage.py migrate',
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class AdminStudentDetailAPIView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def _get_student_for_admin(self, request, student_id):
        if not _ensure_admin_user(request.user):
            return None, Response(
                {'status': 'error', 'message': 'Only admin users can access this resource.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        institution = _get_admin_institution(request.user)
        if not institution:
            return None, Response(
                {'status': 'error', 'message': 'Admin institution not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        student = (
            StudentProfile.objects.select_related('user', 'institution')
            .filter(id=student_id, institution=institution)
            .first()
        )
        if not student:
            return None, Response(
                {'status': 'error', 'message': 'Student not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        return student, None

    def get(self, request, student_id):
        try:
            student, error_response = self._get_student_for_admin(request, student_id)
            if error_response:
                return error_response

            serializer = AdminStudentDetailSerializer(student)
            return Response(
                {
                    'status': 'success',
                    'message': 'Student details fetched successfully.',
                    'data': serializer.data,
                },
                status=status.HTTP_200_OK,
            )
        except OperationalError:
            return Response(
                {
                    'status': 'error',
                    'message': 'Database setup is incomplete. Run migrations using: python manage.py migrate',
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def put(self, request, student_id):
        try:
            student, error_response = self._get_student_for_admin(request, student_id)
            if error_response:
                return error_response

            serializer = AdminStudentUpdateSerializer(
                student,
                data=request.data,
                context={'student_profile': student},
            )
            serializer.is_valid(raise_exception=True)
            serializer.save()

            response_serializer = AdminStudentDetailSerializer(student)
            return Response(
                {
                    'status': 'success',
                    'message': 'Student information updated successfully.',
                    'data': response_serializer.data,
                },
                status=status.HTTP_200_OK,
            )
        except OperationalError:
            return Response(
                {
                    'status': 'error',
                    'message': 'Database setup is incomplete. Run migrations using: python manage.py migrate',
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def delete(self, request, student_id):
        try:
            student, error_response = self._get_student_for_admin(request, student_id)
            if error_response:
                return error_response

            with transaction.atomic():
                student.user.delete()

            return Response(
                {
                    'status': 'success',
                    'message': 'Student deleted successfully.',
                },
                status=status.HTTP_200_OK,
            )
        except OperationalError:
            return Response(
                {
                    'status': 'error',
                    'message': 'Database setup is incomplete. Run migrations using: python manage.py migrate',
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

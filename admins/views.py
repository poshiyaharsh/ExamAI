from rest_framework import status
from django.conf import settings
from django.db import OperationalError, ProgrammingError
from django.db import transaction
from django.db.models import Q
import logging
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
    AdminFacultyListSerializer,
    AdminFacultyDetailSerializer,
    AdminFacultyUpdateSerializer,
)
from faculty.models import FacultyProfile


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
        except (OperationalError, ProgrammingError) as exc:
            return _error_response(
                exc,
                f'Admin institution database error for user_id={request.user.id}',
                'Database schema issue detected. Please run migrations.',
            )
        except Exception as exc:
            return _error_response(
                exc,
                f'Unexpected admin institution error for user_id={request.user.id}',
                'Unable to fetch institution information.',
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
        except (OperationalError, ProgrammingError) as exc:
            return _error_response(
                exc,
                f'Admin students list database error for user_id={request.user.id}',
                'Database schema issue detected. Please run migrations.',
            )
        except Exception as exc:
            return _error_response(
                exc,
                f'Unexpected admin students list error for user_id={request.user.id}',
                'Unable to fetch students.',
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
        except (OperationalError, ProgrammingError) as exc:
            return _error_response(
                exc,
                f'Admin student create database error for user_id={request.user.id}',
                'Database schema issue detected. Please run migrations.',
            )
        except Exception as exc:
            return _error_response(
                exc,
                f'Unexpected admin student create error for user_id={request.user.id}',
                'Unable to create student.',
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
        except (OperationalError, ProgrammingError) as exc:
            return _error_response(
                exc,
                f'Admin student detail database error for user_id={request.user.id} student_id={student_id}',
                'Database schema issue detected. Please run migrations.',
            )
        except Exception as exc:
            return _error_response(
                exc,
                f'Unexpected admin student detail error for user_id={request.user.id} student_id={student_id}',
                'Unable to fetch student details.',
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
        except (OperationalError, ProgrammingError) as exc:
            return _error_response(
                exc,
                f'Admin student update database error for user_id={request.user.id} student_id={student_id}',
                'Database schema issue detected. Please run migrations.',
            )
        except Exception as exc:
            return _error_response(
                exc,
                f'Unexpected admin student update error for user_id={request.user.id} student_id={student_id}',
                'Unable to update student information.',
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
        except (OperationalError, ProgrammingError) as exc:
            return _error_response(
                exc,
                f'Admin student delete database error for user_id={request.user.id} student_id={student_id}',
                'Database schema issue detected. Please run migrations.',
            )
        except Exception as exc:
            return _error_response(
                exc,
                f'Unexpected admin student delete error for user_id={request.user.id} student_id={student_id}',
                'Unable to delete student.',
            )


class AdminFacultyAPIView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        if not _ensure_admin_user(request.user):
            return Response(
                {'status': 'error', 'message': 'Only admin users can access this resource.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            institution = _get_admin_institution(request.user)
            logger.debug(
                "Admin faculty list request user_id=%s username=%s institution_id=%s",
                request.user.id,
                request.user.username,
                getattr(institution, 'id', None),
            )
            if not institution:
                logger.debug("Admin faculty list missing institution for user_id=%s", request.user.id)
                return Response(
                    {
                        'status': 'success',
                        'message': 'Institution information not created yet.',
                        'data': [],
                        'total_faculty': 0,
                        'active_faculty': 0,
                        'total_departments': 0,
                    },
                    status=status.HTTP_200_OK,
                )

            queryset = FacultyProfile.objects.select_related('user', 'institution').filter(institution=institution)

            search_query = request.query_params.get('search', '').strip()
            if search_query:
                queryset = queryset.filter(
                    Q(user__first_name__icontains=search_query)
                    | Q(user__last_name__icontains=search_query)
                    | Q(user__email__icontains=search_query)
                    | Q(employee_id__icontains=search_query)
                )

            department = request.query_params.get('department', '').strip()
            if department:
                queryset = queryset.filter(department__iexact=department)

            status_filter = request.query_params.get('status', '').strip().lower()
            if status_filter == 'active':
                queryset = queryset.filter(user__is_active=True)
            elif status_filter == 'inactive':
                queryset = queryset.filter(user__is_active=False)

            faculty = queryset.order_by('user__first_name', 'user__last_name', 'id')
            serializer = AdminFacultyListSerializer(faculty, many=True)
            total_faculty = faculty.count()
            active_faculty = faculty.filter(user__is_active=True).count()
            total_departments = faculty.exclude(department__exact='').values('department').distinct().count()
            logger.debug(
                "Admin faculty list queryset_count=%s active_count=%s serializer_data=%s",
                total_faculty,
                active_faculty,
                serializer.data,
            )

            return Response(
                {
                    'status': 'success',
                    'message': 'Faculty fetched successfully.',
                    'data': serializer.data,
                    'total_faculty': total_faculty,
                    'active_faculty': active_faculty,
                    'inactive_faculty': max(total_faculty - active_faculty, 0),
                    'total_departments': total_departments,
                    'statistics': {
                        'total_faculty': total_faculty,
                        'active_faculty': active_faculty,
                        'inactive_faculty': max(total_faculty - active_faculty, 0),
                        'total_departments': total_departments,
                    },
                    'success': True,
                },
                status=status.HTTP_200_OK,
            )
        except (OperationalError, ProgrammingError) as exc:
            return _error_response(
                exc,
                f'Admin faculty list database error for user_id={request.user.id}',
                'Database schema issue detected. Please run migrations.',
            )
        except Exception as exc:
            return _error_response(
                exc,
                f'Unexpected admin faculty list error for user_id={request.user.id}',
                'Unable to fetch faculty.',
            )


class AdminFacultyDetailAPIView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def _get_faculty_for_admin(self, request, faculty_id):
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

        faculty = (
            FacultyProfile.objects.select_related('user', 'institution')
            .filter(id=faculty_id, institution=institution)
            .first()
        )
        if not faculty:
            return None, Response(
                {'status': 'error', 'message': 'Faculty not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        return faculty, None

    def get(self, request, faculty_id):
        try:
            faculty, error_response = self._get_faculty_for_admin(request, faculty_id)
            if error_response:
                return error_response

            serializer = AdminFacultyDetailSerializer(faculty)
            logger.debug(
                "Admin faculty detail request user_id=%s faculty_id=%s serializer_data=%s",
                request.user.id,
                faculty_id,
                serializer.data,
            )
            return Response(
                {
                    'status': 'success',
                    'message': 'Faculty details fetched successfully.',
                    'data': serializer.data,
                },
                status=status.HTTP_200_OK,
            )
        except (OperationalError, ProgrammingError) as exc:
            return _error_response(
                exc,
                f'Admin faculty detail database error for user_id={request.user.id} faculty_id={faculty_id}',
                'Database schema issue detected. Please run migrations.',
            )
        except Exception as exc:
            return _error_response(
                exc,
                f'Unexpected admin faculty detail error for user_id={request.user.id} faculty_id={faculty_id}',
                'Unable to fetch faculty details.',
            )

    def put(self, request, faculty_id):
        try:
            faculty, error_response = self._get_faculty_for_admin(request, faculty_id)
            if error_response:
                return error_response

            serializer = AdminFacultyUpdateSerializer(
                faculty,
                data=request.data,
                context={'faculty': faculty},
            )
            serializer.is_valid(raise_exception=True)
            serializer.save()

            response_serializer = AdminFacultyDetailSerializer(faculty)
            logger.debug(
                "Admin faculty update request user_id=%s faculty_id=%s serializer_data=%s",
                request.user.id,
                faculty_id,
                response_serializer.data,
            )
            return Response(
                {
                    'status': 'success',
                    'message': 'Faculty information updated successfully.',
                    'data': response_serializer.data,
                },
                status=status.HTTP_200_OK,
            )
        except (OperationalError, ProgrammingError) as exc:
            return _error_response(
                exc,
                f'Admin faculty update database error for user_id={request.user.id} faculty_id={faculty_id}',
                'Database schema issue detected. Please run migrations.',
            )
        except Exception as exc:
            return _error_response(
                exc,
                f'Unexpected admin faculty update error for user_id={request.user.id} faculty_id={faculty_id}',
                'Unable to update faculty information.',
            )

    def delete(self, request, faculty_id):
        try:
            faculty, error_response = self._get_faculty_for_admin(request, faculty_id)
            if error_response:
                return error_response

            with transaction.atomic():
                faculty.user.delete()

            return Response(
                {
                    'status': 'success',
                    'message': 'Faculty deleted successfully.',
                },
                status=status.HTTP_200_OK,
            )
        except (OperationalError, ProgrammingError) as exc:
            return _error_response(
                exc,
                f'Admin faculty delete database error for user_id={request.user.id} faculty_id={faculty_id}',
                'Database schema issue detected. Please run migrations.',
            )
        except Exception as exc:
            return _error_response(
                exc,
                f'Unexpected admin faculty delete error for user_id={request.user.id} faculty_id={faculty_id}',
                'Unable to delete faculty.',
            )

from rest_framework import status
from django.conf import settings
from django.db import OperationalError, ProgrammingError
from django.db import transaction
import datetime
from django.utils import timezone
from django.db.models import Count, Q
import logging
from rest_framework.permissions import AllowAny
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from api.permissions import IsAdminUser
from api.models import Exam, Question, StudentAttempt

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
    AdminFacultyCreateSerializer,
    AdminFacultyListSerializer,
    AdminFacultyDetailSerializer,
    AdminFacultyUpdateSerializer,
    AdminExamListSerializer,
    AdminExamDetailSerializer,
    AdminExamStatusUpdateSerializer,
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

            serializer = AdminFacultyCreateSerializer(
                data=request.data,
                context={'institution': institution},
            )
            serializer.is_valid(raise_exception=True)
            faculty_profile = serializer.save()

            response_serializer = AdminFacultyDetailSerializer(faculty_profile)
            return Response(
                {
                    'status': 'success',
                    'message': 'Faculty Created Successfully',
                    'data': response_serializer.data,
                },
                status=status.HTTP_201_CREATED,
            )
        except (OperationalError, ProgrammingError) as exc:
            return _error_response(
                exc,
                f'Admin faculty create database error for user_id={request.user.id}',
                'Database schema issue detected. Please run migrations.',
            )
        except Exception as exc:
            return _error_response(
                exc,
                f'Unexpected admin faculty create error for user_id={request.user.id}',
                'Unable to create faculty.',
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


class AdminExamsAPIView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        if not _ensure_admin_user(request.user):
            return Response(
                {'status': 'error', 'message': 'Only admin users can access this resource.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            institution = _get_admin_institution(request.user)
            base_queryset = (
                Exam.objects.select_related('created_by', 'created_by__faculty_profile')
                .annotate(
                    question_count=Count('questions', distinct=True),
                    attempts_count=Count('attempts', distinct=True),
                )
            )

            if institution:
                base_queryset = base_queryset.filter(
                    Q(created_by__faculty_profile__institution=institution)
                    | Q(created_by__faculty_profile__institution__isnull=True)
                )

            now = timezone.now()
            week_ago = now - datetime.timedelta(days=7)
            total_exams = base_queryset.count()
            published_exams = base_queryset.filter(status=Exam.Status.PUBLISHED).count()
            draft_exams = base_queryset.filter(status=Exam.Status.DRAFT).count()
            created_this_week = base_queryset.filter(created_at__gte=week_ago).count()

            faculty_list = []
            seen_faculty_ids = set()
            departments_set = set()
            subjects_set = set()

            for exam in base_queryset.iterator():
                f_user = exam.created_by
                if f_user and f_user.id not in seen_faculty_ids:
                    seen_faculty_ids.add(f_user.id)
                    f_name = f"{f_user.first_name} {f_user.last_name}".strip() or f_user.username or f_user.email
                    faculty_list.append({'id': f_user.id, 'name': f_name, 'email': f_user.email})

                f_profile = getattr(f_user, 'faculty_profile', None)
                if f_profile and f_profile.department:
                    departments_set.add(f_profile.department.strip())

                if isinstance(exam.topics, list):
                    for t in exam.topics:
                        if t and isinstance(t, str) and t.strip():
                            subjects_set.add(t.strip())

            faculty_list.sort(key=lambda x: x['name'].lower())
            distinct_departments = sorted(list(departments_set))
            distinct_subjects = sorted(list(subjects_set))

            queryset = base_queryset

            search = request.query_params.get('search', '').strip()
            if search:
                queryset = queryset.filter(
                    Q(title__icontains=search)
                    | Q(topics__icontains=search)
                    | Q(created_by__first_name__icontains=search)
                    | Q(created_by__last_name__icontains=search)
                    | Q(created_by__email__icontains=search)
                )

            faculty_filter = request.query_params.get('faculty', '').strip()
            if faculty_filter:
                if faculty_filter.isdigit():
                    queryset = queryset.filter(created_by_id=int(faculty_filter))
                else:
                    queryset = queryset.filter(
                        Q(created_by__first_name__icontains=faculty_filter)
                        | Q(created_by__last_name__icontains=faculty_filter)
                        | Q(created_by__email__icontains=faculty_filter)
                    )

            subject_filter = request.query_params.get('subject', '').strip()
            if subject_filter:
                queryset = queryset.filter(topics__icontains=subject_filter)

            department_filter = request.query_params.get('department', '').strip()
            if department_filter:
                queryset = queryset.filter(created_by__faculty_profile__department__iexact=department_filter)

            status_filter = request.query_params.get('status', '').strip().lower()
            if status_filter and status_filter != 'all':
                if status_filter == 'completed':
                    queryset = queryset.filter(status=Exam.Status.CLOSED)
                else:
                    queryset = queryset.filter(status__iexact=status_filter)

            start_date = request.query_params.get('start_date', '').strip()
            if start_date:
                try:
                    queryset = queryset.filter(created_at__date__gte=start_date)
                except Exception:
                    pass

            end_date = request.query_params.get('end_date', '').strip()
            if end_date:
                try:
                    queryset = queryset.filter(created_at__date__lte=end_date)
                except Exception:
                    pass

            sort = request.query_params.get('sort', '-created_at').strip()
            valid_sort_fields = {
                '-created_at', 'created_at',
                '-title', 'title',
                '-total_marks', 'total_marks',
                '-duration_minutes', 'duration_minutes',
                '-status', 'status',
            }
            if sort not in valid_sort_fields:
                sort = '-created_at'
            queryset = queryset.order_by(sort, '-id')

            filtered_count = queryset.count()
            try:
                page = max(1, int(request.query_params.get('page', 1)))
            except (ValueError, TypeError):
                page = 1
            try:
                page_size = max(1, min(100, int(request.query_params.get('page_size', 10))))
            except (ValueError, TypeError):
                page_size = 10

            offset = (page - 1) * page_size
            total_pages = max(1, (filtered_count + page_size - 1) // page_size) if filtered_count else 1
            exams_page = queryset[offset:offset + page_size]

            serializer = AdminExamListSerializer(exams_page, many=True)

            return Response(
                {
                    'status': 'success',
                    'data': serializer.data,
                    'pagination': {
                        'page': page,
                        'page_size': page_size,
                        'total_count': filtered_count,
                        'total_pages': total_pages,
                        'has_next': page < total_pages,
                        'has_prev': page > 1,
                    },
                    'stats': {
                        'total_exams': total_exams,
                        'published_exams': published_exams,
                        'draft_exams': draft_exams,
                        'created_this_week': created_this_week,
                    },
                    'filter_options': {
                        'faculties': faculty_list,
                        'departments': distinct_departments,
                        'subjects': distinct_subjects,
                        'statuses': [
                            {'value': 'all', 'label': 'All Statuses'},
                            {'value': 'published', 'label': 'Published'},
                            {'value': 'draft', 'label': 'Draft'},
                            {'value': 'closed', 'label': 'Closed / Completed'},
                            {'value': 'generating', 'label': 'Generating'},
                            {'value': 'failed', 'label': 'Failed'},
                        ],
                    },
                },
                status=status.HTTP_200_OK,
            )
        except Exception as exc:
            return _error_response(
                exc,
                f'Admin exams list error for user_id={request.user.id}',
                'Unable to fetch exams.',
            )


class AdminExamDetailAPIView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def _get_exam(self, request, exam_id):
        institution = _get_admin_institution(request.user)
        queryset = Exam.objects.select_related('created_by', 'created_by__faculty_profile').prefetch_related('questions', 'attempts')
        if institution:
            queryset = queryset.filter(
                Q(created_by__faculty_profile__institution=institution)
                | Q(created_by__faculty_profile__institution__isnull=True)
            )
        return queryset.filter(id=exam_id).first()

    def get(self, request, exam_id):
        if not _ensure_admin_user(request.user):
            return Response(
                {'status': 'error', 'message': 'Only admin users can access this resource.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            exam = self._get_exam(request, exam_id)
            if not exam:
                return Response(
                    {'status': 'error', 'message': 'Exam not found.'},
                    status=status.HTTP_404_NOT_FOUND,
                )
            serializer = AdminExamDetailSerializer(exam)
            return Response(
                {
                    'status': 'success',
                    'data': serializer.data,
                },
                status=status.HTTP_200_OK,
            )
        except Exception as exc:
            return _error_response(
                exc,
                f'Admin exam detail error for exam_id={exam_id}',
                'Unable to fetch exam details.',
            )

    def patch(self, request, exam_id):
        if not _ensure_admin_user(request.user):
            return Response(
                {'status': 'error', 'message': 'Only admin users can access this resource.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            exam = self._get_exam(request, exam_id)
            if not exam:
                return Response(
                    {'status': 'error', 'message': 'Exam not found.'},
                    status=status.HTTP_404_NOT_FOUND,
                )

            serializer = AdminExamStatusUpdateSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            new_status = serializer.validated_data['status']

            if new_status == Exam.Status.PUBLISHED:
                questions = list(exam.questions.all())
                if not questions:
                    return Response(
                        {'status': 'error', 'message': 'Cannot publish an exam with no questions.'},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

            exam.status = new_status
            exam.save(update_fields=['status', 'updated_at'])

            detail_serializer = AdminExamDetailSerializer(exam)
            return Response(
                {
                    'status': 'success',
                    'message': f'Exam status updated to {new_status}.',
                    'data': detail_serializer.data,
                },
                status=status.HTTP_200_OK,
            )
        except Exception as exc:
            return _error_response(
                exc,
                f'Admin exam status update error for exam_id={exam_id}',
                'Unable to update exam status.',
            )

    def delete(self, request, exam_id):
        if not _ensure_admin_user(request.user):
            return Response(
                {'status': 'error', 'message': 'Only admin users can access this resource.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            exam = self._get_exam(request, exam_id)
            if not exam:
                return Response(
                    {'status': 'error', 'message': 'Exam not found.'},
                    status=status.HTTP_404_NOT_FOUND,
                )

            with transaction.atomic():
                exam.delete()

            return Response(
                {
                    'status': 'success',
                    'message': 'Exam deleted successfully.',
                },
                status=status.HTTP_200_OK,
            )
        except Exception as exc:
            return _error_response(
                exc,
                f'Admin exam delete error for exam_id={exam_id}',
                'Unable to delete exam.',
            )

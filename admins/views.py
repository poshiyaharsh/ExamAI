from rest_framework import status
from django.conf import settings
from django.contrib.auth.models import User
from django.db import OperationalError, ProgrammingError
from django.db import transaction
import datetime
from django.utils import timezone
from django.db.models import Avg, Count, ExpressionWrapper, F, FloatField, Max, Min, Q
import logging
from rest_framework.permissions import AllowAny
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from api.permissions import IsAdminUser
from api.models import Exam, Question, StudentAttempt
from api.throttling import AuthRateThrottle

from students.models import StudentProfile
from .models import AdminInstitution, AdminProfile
from .serializers import (
    AdminInstitutionCreateSerializer,
    AdminInstitutionSerializer,
    AdminStudentCreateSerializer,
    AdminStudentDetailSerializer,
    AdminStudentListSerializer,
    AdminStudentUpdateSerializer,
    AdminStudentResultItemSerializer,
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
    from api.tenant import get_user_institution
    institution = get_user_institution(user)
    inst_id = institution.id if institution else None
    refresh = RefreshToken.for_user(user)
    refresh['role'] = 'admin'
    refresh['institution_id'] = inst_id
    access = refresh.access_token
    access['role'] = 'admin'
    access['institution_id'] = inst_id
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
    throttle_classes = [AuthRateThrottle]

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
    throttle_classes = [AuthRateThrottle]

    def post(self, request):
        serializer = AdminLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']

        institution = _get_admin_institution(user)
        if institution and getattr(institution, 'status', 'active') == 'suspended':
            return Response(
                {
                    'status': 'error',
                    'message': 'Your institution has been suspended. Please contact your administrator.',
                },
                status=status.HTTP_403_FORBIDDEN,
            )

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
                    'institution': {
                        'id': institution.id,
                        'name': institution.institution_name,
                        'code': institution.institution_code,
                    } if institution else None,
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
                        'stats': {
                            'total_students': 0,
                            'overall_average_score': None,
                            'top_performer': None,
                            'students_below_pass': 0,
                        },
                        'departments': [],
                    },
                    status=status.HTTP_200_OK,
                )

            completed_filter = Q(user__exam_attempts__status__in=[
                StudentAttempt.Status.SUBMITTED,
                StudentAttempt.Status.AUTO_SUBMITTED,
                StudentAttempt.Status.EVALUATED,
            ])

            base_queryset = (
                StudentProfile.objects.select_related('user', 'institution')
                .filter(institution=institution)
                .annotate(
                    attempt_count=Count('user__exam_attempts', filter=completed_filter, distinct=True),
                    last_exam_date=Max('user__exam_attempts__submitted_at', filter=completed_filter),
                    avg_percentage=Avg(
                        ExpressionWrapper(
                            F('user__exam_attempts__total_score') * 100.0 / F('user__exam_attempts__exam__total_marks'),
                            output_field=FloatField()
                        ),
                        filter=completed_filter
                    ),
                    max_percentage=Max(
                        ExpressionWrapper(
                            F('user__exam_attempts__total_score') * 100.0 / F('user__exam_attempts__exam__total_marks'),
                            output_field=FloatField()
                        ),
                        filter=completed_filter
                    ),
                    min_percentage=Min(
                        ExpressionWrapper(
                            F('user__exam_attempts__total_score') * 100.0 / F('user__exam_attempts__exam__total_marks'),
                            output_field=FloatField()
                        ),
                        filter=completed_filter
                    ),
                )
            )

            # Pre-filter stats
            all_students = list(base_queryset)
            total_students = len(all_students)
            students_with_exams = [s for s in all_students if (s.attempt_count or 0) > 0 and s.avg_percentage is not None]
            
            if students_with_exams:
                overall_avg = round(sum(s.avg_percentage for s in students_with_exams) / len(students_with_exams), 1)
                best_student = max(students_with_exams, key=lambda s: s.avg_percentage)
                b_name = f"{best_student.user.first_name} {best_student.user.last_name}".strip() or best_student.user.username
                top_performer = {
                    'id': best_student.id,
                    'name': b_name,
                    'email': best_student.user.email,
                    'roll_number': best_student.student_id,
                    'percentage': round(best_student.avg_percentage, 1),
                }
                students_below_pass = len([s for s in students_with_exams if s.avg_percentage < 40.0])
            else:
                overall_avg = None
                top_performer = None
                students_below_pass = 0

            departments = sorted(list({s.department for s in all_students if s.department}))

            # Applying search & filters
            queryset = base_queryset

            search_query = request.query_params.get('search', '').strip()
            if search_query:
                queryset = queryset.filter(
                    Q(user__first_name__icontains=search_query)
                    | Q(user__last_name__icontains=search_query)
                    | Q(user__email__icontains=search_query)
                    | Q(student_id__icontains=search_query)
                )

            department = request.query_params.get('department', '').strip()
            if department and department != 'all':
                queryset = queryset.filter(department__iexact=department)

            score_range = request.query_params.get('score_range', '').strip().lower()
            if score_range and score_range != 'all':
                if score_range == 'excellent':
                    queryset = queryset.filter(avg_percentage__gte=80.0)
                elif score_range == 'good':
                    queryset = queryset.filter(avg_percentage__gte=65.0, avg_percentage__lt=80.0)
                elif score_range == 'average':
                    queryset = queryset.filter(avg_percentage__gte=50.0, avg_percentage__lt=65.0)
                elif score_range == 'needs_improvement':
                    queryset = queryset.filter(avg_percentage__lt=50.0, attempt_count__gt=0)
                elif score_range == 'no_exams':
                    queryset = queryset.filter(Q(attempt_count=0) | Q(avg_percentage__isnull=True))

            # Sorting
            sort_by = request.query_params.get('sort', '').strip()
            if sort_by == 'average_desc':
                queryset = queryset.order_by(F('avg_percentage').desc(nulls_last=True), 'user__first_name')
            elif sort_by == 'average_asc':
                queryset = queryset.order_by(F('avg_percentage').asc(nulls_last=True), 'user__first_name')
            elif sort_by == 'name_asc':
                queryset = queryset.order_by('user__first_name', 'user__last_name')
            elif sort_by == 'name_desc':
                queryset = queryset.order_by('-user__first_name', '-user__last_name')
            elif sort_by == 'exams_desc':
                queryset = queryset.order_by('-attempt_count', '-avg_percentage')
            elif sort_by == 'last_exam_desc':
                queryset = queryset.order_by(F('last_exam_date').desc(nulls_last=True))
            else:
                queryset = queryset.order_by('user__first_name', 'user__last_name', 'id')

            filtered_count = queryset.count()
            page = request.query_params.get('page')
            page_size = request.query_params.get('page_size')

            if page:
                try:
                    p = max(1, int(page))
                    ps = max(1, min(100, int(page_size or 10)))
                except (ValueError, TypeError):
                    p, ps = 1, 10
                offset = (p - 1) * ps
                total_pages = max(1, (filtered_count + ps - 1) // ps) if filtered_count else 1
                students_page = queryset[offset:offset + ps]
                pagination_data = {
                    'page': p,
                    'page_size': ps,
                    'total_count': filtered_count,
                    'total_pages': total_pages,
                    'has_next': p < total_pages,
                    'has_prev': p > 1,
                }
            else:
                students_page = queryset
                pagination_data = None

            serializer = AdminStudentListSerializer(students_page, many=True)

            return Response(
                {
                    'status': 'success',
                    'message': 'Students fetched successfully.',
                    'data': serializer.data,
                    'pagination': pagination_data,
                    'stats': {
                        'total_students': total_students,
                        'overall_average_score': overall_avg,
                        'top_performer': top_performer,
                        'students_below_pass': students_below_pass,
                    },
                    'departments': departments,
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
                'Unable to fetch students list.',
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
                        'results': [],
                        'count': 0,
                        'total_count': 0,
                        'total_pages': 1,
                        'page': 1,
                        'page_size': 10,
                        'has_next': False,
                        'has_prev': False,
                        'next': None,
                        'previous': None,
                        'pagination': {
                            'page': 1,
                            'page_size': 10,
                            'total_count': 0,
                            'total_pages': 1,
                            'has_next': False,
                            'has_prev': False,
                        },
                        'total_faculty': 0,
                        'active_faculty': 0,
                        'inactive_faculty': 0,
                        'total_departments': 0,
                        'statistics': {
                            'total_faculty': 0,
                            'active_faculty': 0,
                            'inactive_faculty': 0,
                            'total_departments': 0,
                        },
                        'success': True,
                    },
                    status=status.HTTP_200_OK,
                )

            base_queryset = FacultyProfile.objects.select_related('user', 'institution').filter(institution=institution)

            # Pre-filter stats
            total_faculty_stats = base_queryset.count()
            active_faculty_stats = base_queryset.filter(user__is_active=True).count()
            inactive_faculty_stats = max(total_faculty_stats - active_faculty_stats, 0)
            total_departments_stats = base_queryset.exclude(department__exact='').values('department').distinct().count()

            # Applying search & filters
            queryset = base_queryset

            search_query = request.query_params.get('search', '').strip()
            if search_query:
                queryset = queryset.filter(
                    Q(user__first_name__icontains=search_query)
                    | Q(user__last_name__icontains=search_query)
                    | Q(user__email__icontains=search_query)
                    | Q(employee_id__icontains=search_query)
                )

            department = request.query_params.get('department', '').strip()
            if department and department.lower() != 'all':
                queryset = queryset.filter(department__iexact=department)

            status_filter = request.query_params.get('status', '').strip().lower()
            if status_filter == 'active':
                queryset = queryset.filter(user__is_active=True)
            elif status_filter == 'inactive':
                queryset = queryset.filter(user__is_active=False)

            # Stable sorting
            sort_by = request.query_params.get('sort', '').strip()
            if sort_by == 'name_desc':
                queryset = queryset.order_by('-user__first_name', '-user__last_name', '-id')
            elif sort_by == 'department_asc':
                queryset = queryset.order_by('department', 'user__first_name', 'id')
            elif sort_by == 'department_desc':
                queryset = queryset.order_by('-department', 'user__first_name', 'id')
            elif sort_by == 'created_desc':
                queryset = queryset.order_by('-created_at', '-id')
            else:
                queryset = queryset.order_by('user__first_name', 'user__last_name', 'id')

            filtered_count = queryset.count()

            # Pagination parameters (allowed: 10, 25, 50, 100)
            ALLOWED_PAGE_SIZES = (10, 25, 50, 100)
            raw_page_size = request.query_params.get('page_size')
            try:
                parsed_page_size = int(raw_page_size) if raw_page_size else 10
                page_size = parsed_page_size if parsed_page_size in ALLOWED_PAGE_SIZES else 10
            except (ValueError, TypeError):
                page_size = 10

            total_pages = max(1, (filtered_count + page_size - 1) // page_size) if filtered_count else 1

            raw_page = request.query_params.get('page')
            try:
                parsed_page = int(raw_page) if raw_page else 1
                page = max(1, min(total_pages, parsed_page))
            except (ValueError, TypeError):
                page = 1

            offset = (page - 1) * page_size
            faculty_page = queryset[offset:offset + page_size]

            serializer = AdminFacultyListSerializer(faculty_page, many=True)

            has_next = page < total_pages
            has_prev = page > 1

            base_url = request.build_absolute_uri(request.path)

            def make_page_url(target_page):
                qp = request.GET.copy()
                qp['page'] = str(target_page)
                qp['page_size'] = str(page_size)
                return f"{base_url}?{qp.urlencode()}"

            next_url = make_page_url(page + 1) if has_next else None
            prev_url = make_page_url(page - 1) if has_prev else None

            pagination_data = {
                'page': page,
                'page_size': page_size,
                'total_count': filtered_count,
                'total_pages': total_pages,
                'has_next': has_next,
                'has_prev': has_prev,
            }

            return Response(
                {
                    'status': 'success',
                    'message': 'Faculty fetched successfully.',
                    'data': serializer.data,
                    'results': serializer.data,
                    'count': filtered_count,
                    'total_count': filtered_count,
                    'total_pages': total_pages,
                    'page': page,
                    'page_size': page_size,
                    'has_next': has_next,
                    'has_prev': has_prev,
                    'next': next_url,
                    'previous': prev_url,
                    'pagination': pagination_data,
                    'total_faculty': total_faculty_stats,
                    'active_faculty': active_faculty_stats,
                    'inactive_faculty': inactive_faculty_stats,
                    'total_departments': total_departments_stats,
                    'statistics': {
                        'total_faculty': total_faculty_stats,
                        'active_faculty': active_faculty_stats,
                        'inactive_faculty': inactive_faculty_stats,
                        'total_departments': total_departments_stats,
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
            if not institution:
                return Response(
                    {
                        'status': 'success',
                        'message': 'Institution information not created yet.',
                        'data': [],
                        'pagination': None,
                        'stats': {
                            'total_exams': 0,
                            'published_exams': 0,
                            'draft_exams': 0,
                            'created_this_week': 0,
                        },
                        'filter_options': {
                            'faculties': [],
                            'departments': [],
                            'subjects': [],
                            'statuses': [],
                        },
                    },
                    status=status.HTTP_200_OK,
                )

            base_queryset = (
                Exam.objects.select_related('created_by', 'created_by__faculty_profile')
                .filter(institution=institution)
                .annotate(
                    question_count=Count('questions', distinct=True),
                    attempts_count=Count('attempts', distinct=True),
                )
            )

            from api.exams.eligibility import live_exams_queryset

            now = timezone.now()
            week_ago = now - datetime.timedelta(days=7)
            total_exams = base_queryset.count()
            published_exams = base_queryset.filter(status=Exam.Status.PUBLISHED).count()
            draft_exams = base_queryset.filter(status=Exam.Status.DRAFT).count()
            created_this_week = base_queryset.filter(created_at__gte=week_ago).count()
            live_exams_count = live_exams_queryset(institution, now).count()

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
                queryset = queryset.filter(
                    Q(department__iexact=department_filter) |
                    Q(created_by__faculty_profile__department__iexact=department_filter)
                )

            status_filter = request.query_params.get('status', '').strip().lower()
            if status_filter and status_filter != 'all':
                if status_filter == 'live':
                    live_ids = live_exams_queryset(institution, now).values_list('id', flat=True)
                    queryset = queryset.filter(id__in=live_ids)
                elif status_filter == 'completed':
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

            sort = request.query_params.get('sort', '').strip()
            if not sort:
                sort = '-starts_at' if status_filter == 'live' else '-created_at'

            valid_sort_fields = {
                '-created_at', 'created_at',
                '-starts_at', 'starts_at',
                '-title', 'title',
                '-total_marks', 'total_marks',
                '-duration_minutes', 'duration_minutes',
                '-status', 'status',
            }
            if sort not in valid_sort_fields:
                sort = '-starts_at' if status_filter == 'live' else '-created_at'

            if sort == '-starts_at':
                queryset = queryset.order_by(F('starts_at').desc(nulls_last=True), '-id')
            elif sort == 'starts_at':
                queryset = queryset.order_by(F('starts_at').asc(nulls_first=True), '-id')
            else:
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
                        'live_exams': live_exams_count,
                    },
                    'filter_options': {
                        'faculties': faculty_list,
                        'departments': distinct_departments,
                        'subjects': distinct_subjects,
                        'statuses': [
                            {'value': 'all', 'label': 'All Statuses'},
                            {'value': 'live', 'label': 'Live / Active Now'},
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
        if not institution:
            return None
        return (
            Exam.objects.select_related('created_by', 'created_by__faculty_profile')
            .prefetch_related('questions', 'attempts')
            .filter(id=exam_id, institution=institution)
            .first()
        )

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
            from api.utils.departments import get_exam_visibility_status_for_faculty
            serializer = AdminExamDetailSerializer(exam)
            data = dict(serializer.data)
            data['visibility'] = get_exam_visibility_status_for_faculty(exam)
            return Response(
                {
                    'status': 'success',
                    'data': data,
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


class AdminStudentResultsAPIView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request, student_id):
        if not _ensure_admin_user(request.user):
            return Response(
                {'status': 'error', 'message': 'Only admin users can access this resource.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            institution = _get_admin_institution(request.user)
            if not institution:
                return Response({'status': 'error', 'message': 'Student not found.'}, status=status.HTTP_404_NOT_FOUND)

            student = StudentProfile.objects.select_related('user', 'institution').filter(id=student_id, institution=institution).first()
            if not student:
                return Response({'status': 'error', 'message': 'Student not found.'}, status=status.HTTP_404_NOT_FOUND)

            attempts = (
                StudentAttempt.objects.filter(student=student.user, institution=institution)
                .select_related('exam', 'exam__created_by')
                .order_by('-submitted_at', '-started_at')
            )

            completed_attempts = [
                a for a in attempts
                if a.status in [StudentAttempt.Status.SUBMITTED, StudentAttempt.Status.AUTO_SUBMITTED, StudentAttempt.Status.EVALUATED]
            ]

            results_serializer = AdminStudentResultItemSerializer(attempts, many=True)
            percentages = [
                (float(a.total_score or 0) / (a.exam.total_marks or 1)) * 100.0
                for a in completed_attempts
            ]

            overall_avg = round(sum(percentages) / len(percentages), 1) if percentages else None
            highest_pct = round(max(percentages), 1) if percentages else None
            lowest_pct = round(min(percentages), 1) if percentages else None

            # Build chronological trend (oldest to newest)
            trend = []
            for a in reversed(completed_attempts):
                pct = round((float(a.total_score or 0) / (a.exam.total_marks or 1)) * 100.0, 1)
                d = a.submitted_at or a.started_at
                trend.append({
                    'date': d.strftime('%b %d, %Y') if d else '-',
                    'percentage': pct,
                    'exam_title': a.exam.title,
                    'status': a.status,
                })

            full_name = f"{student.user.first_name} {student.user.last_name}".strip() or student.user.username

            return Response({
                'status': 'success',
                'data': {
                    'student': {
                        'id': student.id,
                        'full_name': full_name,
                        'first_name': student.user.first_name,
                        'last_name': student.user.last_name,
                        'email': student.user.email,
                        'roll_number': student.student_id,
                        'department': student.department,
                    },
                    'summary': {
                        'total_attempts': len(completed_attempts),
                        'overall_average': overall_avg,
                        'highest_score': highest_pct,
                        'lowest_score': lowest_pct,
                        'performance_status': (
                            'N/A' if overall_avg is None else
                            'Excellent' if overall_avg >= 80 else
                            'Good' if overall_avg >= 65 else
                            'Average' if overall_avg >= 50 else 'Needs Improvement'
                        ),
                    },
                    'results': results_serializer.data,
                    'trend': trend,
                }
            }, status=status.HTTP_200_OK)
        except Exception as exc:
            return _error_response(
                exc,
                f'Unexpected admin student results error for student_id={student_id}',
                'Unable to fetch student results.',
            )


class AdminExamAuditAPIView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        if not _ensure_admin_user(request.user):
            return Response(
                {'status': 'error', 'message': 'Only admin users can access this resource.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        institution = _get_admin_institution(request.user)
        if not institution:
            return Response({'status': 'error', 'message': 'No institution found.'}, status=status.HTTP_400_BAD_REQUEST)

        from api.utils.departments import get_exam_visibility_status_for_faculty, get_faculty_department

        exams = Exam.objects.filter(institution=institution).select_related('created_by', 'institution')
        issues = []
        clean_count = 0

        for exam in exams:
            visibility = get_exam_visibility_status_for_faculty(exam)
            exam_dept = (exam.department or '').strip()
            faculty_dept = get_faculty_department(exam.created_by)
            has_issue = False
            item_issues = []

            if not exam_dept:
                has_issue = True
                item_issues.append('Exam department is missing')

            if faculty_dept and exam_dept and faculty_dept.lower() != exam_dept.lower():
                has_issue = True
                item_issues.append(f'Department mismatch with creating faculty ({exam_dept} vs {faculty_dept})')

            if exam.questions.count() == 0:
                has_issue = True
                item_issues.append('Exam has zero questions')

            if exam.starts_at and exam.ends_at and exam.starts_at > exam.ends_at:
                has_issue = True
                item_issues.append('Start date is after end date')

            if has_issue:
                issues.append({
                    'exam_id': exam.id,
                    'title': exam.title,
                    'status': exam.status,
                    'department': exam.department,
                    'faculty_email': exam.created_by.email,
                    'faculty_department': faculty_dept,
                    'issues': item_issues,
                    'visibility': visibility,
                })
            else:
                clean_count += 1

        return Response({
            'status': 'success',
            'data': {
                'total_exams': exams.count(),
                'healthy_exams_count': clean_count,
                'issue_exams_count': len(issues),
                'issues': issues,
            }
        }, status=status.HTTP_200_OK)


class AdminUserDepartmentChangeAPIView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def post(self, request, user_id):
        institution = _get_admin_institution(request.user)
        if not institution:
            return Response({'status': 'error', 'message': 'Admin institution not found.'}, status=status.HTTP_404_NOT_FOUND)

        target_user = User.objects.filter(id=user_id).first()
        if not target_user:
            return Response({'status': 'error', 'message': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)

        profile = getattr(target_user, 'student_profile', None) or getattr(target_user, 'faculty_profile', None)
        if not profile or profile.institution_id != institution.id:
            return Response({'status': 'error', 'message': 'User does not belong to your institution.'}, status=status.HTTP_404_NOT_FOUND)

        new_dept = request.data.get('department', '').strip()
        reason = request.data.get('reason', '').strip()
        if not new_dept:
            return Response({'status': 'error', 'message': 'New department is required.'}, status=status.HTTP_400_BAD_REQUEST)
        if not reason:
            return Response({'status': 'error', 'message': 'A reason is required for administrative department changes.'}, status=status.HTTP_400_BAD_REQUEST)

        from api.utils.departments import validate_department_name
        is_valid, norm_dept = validate_department_name(new_dept, institution=institution)
        if not is_valid:
            return Response({'status': 'error', 'message': f'Invalid department "{new_dept}". Must be an allowed department.'}, status=status.HTTP_400_BAD_REQUEST)

        old_dept = profile.department or 'Unassigned'
        profile.department = norm_dept
        profile._allow_department_change = True
        profile.save(update_fields=['department'])

        from admins.models import DepartmentChangeAuditLog
        log = DepartmentChangeAuditLog.objects.create(
            user=target_user,
            institution=institution,
            changed_by=request.user,
            previous_department=old_dept,
            new_department=norm_dept,
            reason=reason,
        )

        return Response({
            'status': 'success',
            'message': f'Department successfully changed from {old_dept} to {norm_dept}.',
            'data': {
                'user_id': target_user.id,
                'email': target_user.email,
                'department': norm_dept,
                'audit_id': log.id,
                'timestamp': log.timestamp.isoformat(),
            }
        }, status=status.HTTP_200_OK)


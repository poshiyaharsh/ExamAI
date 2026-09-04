import logging

from django.conf import settings
from django.db import OperationalError, ProgrammingError
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from api.permissions import IsStudentUser

from admins.models import AdminInstitution
from faculty.models import Paper
from .models import ExamAttempt, StudentProfile
from .serializers import (
    ExamAttemptSerializer,
    StudentExamDetailSerializer,
    StudentExamSummarySerializer,
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


def _student_or_error(request):
    profile = _get_or_create_student_profile(request.user)
    if not profile.institution:
        return None, Response({'status': 'error', 'message': 'Student institution not found.'}, status=status.HTTP_400_BAD_REQUEST)
    return profile, None


def _student_paper_queryset(student):
    return Paper.objects.select_related('faculty__user', 'institution').prefetch_related('questions').filter(
        institution=student.institution,
        is_published=True,
    )


def _normalize_answer(value):
    return ' '.join(str(value or '').split()).casefold()


def _calculate_score(paper, answers):
    score = 0
    for question in paper.questions.all():
        submitted = answers.get(str(question.question_number), answers.get(question.question_number))
        if submitted is not None and _normalize_answer(submitted) == _normalize_answer(question.answer):
            if question.question_type in {'MCQ', 'True/False', 'Fill in the Blanks'}:
                score += question.marks
    return score


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


class StudentExamListAPIView(APIView):
    permission_classes = [IsAuthenticated, IsStudentUser]

    def get(self, request):
        student, error_response = _student_or_error(request)
        if error_response:
            return error_response
        return Response({'status': 'success', 'message': 'Student exams fetched successfully.', 'data': StudentExamSummarySerializer(_student_paper_queryset(student), many=True).data})


class StudentExamDetailAPIView(APIView):
    permission_classes = [IsAuthenticated, IsStudentUser]

    def get(self, request, paper_id):
        student, error_response = _student_or_error(request)
        if error_response:
            return error_response
        paper = _student_paper_queryset(student).filter(id=paper_id).first()
        if not paper:
            return Response({'status': 'error', 'message': 'Exam not found.'}, status=status.HTTP_404_NOT_FOUND)
        return Response({'status': 'success', 'message': 'Exam fetched successfully.', 'data': StudentExamDetailSerializer(paper).data})


class StudentExamStartAPIView(APIView):
    permission_classes = [IsAuthenticated, IsStudentUser]

    def post(self, request, paper_id):
        student, error_response = _student_or_error(request)
        if error_response:
            return error_response
        paper = _student_paper_queryset(student).filter(id=paper_id).first()
        if not paper:
            return Response({'status': 'error', 'message': 'Exam not found.'}, status=status.HTTP_404_NOT_FOUND)
        attempt, _ = ExamAttempt.objects.get_or_create(student=student, paper=paper, status=ExamAttempt.STATUS_STARTED, defaults={'max_score': paper.total_marks})
        return Response({'status': 'success', 'message': 'Exam started successfully.', 'data': {'attempt': ExamAttemptSerializer(attempt).data, 'exam': StudentExamDetailSerializer(paper).data}})


class StudentExamSubmitAPIView(APIView):
    permission_classes = [IsAuthenticated, IsStudentUser]

    def post(self, request, paper_id):
        student, error_response = _student_or_error(request)
        if error_response:
            return error_response
        paper = _student_paper_queryset(student).filter(id=paper_id).first()
        if not paper:
            return Response({'status': 'error', 'message': 'Exam not found.'}, status=status.HTTP_404_NOT_FOUND)
        answers = request.data.get('answers')
        if not isinstance(answers, dict):
            return Response({'status': 'error', 'message': 'Answers must be an object.'}, status=status.HTTP_400_BAD_REQUEST)
        attempt = ExamAttempt.objects.filter(student=student, paper=paper, status=ExamAttempt.STATUS_STARTED).order_by('-started_at').first()
        if not attempt:
            return Response({'status': 'error', 'message': 'No active exam attempt found.'}, status=status.HTTP_400_BAD_REQUEST)
        attempt.answers = answers
        attempt.score = _calculate_score(paper, answers)
        attempt.max_score = paper.total_marks
        attempt.status = ExamAttempt.STATUS_SUBMITTED
        attempt.submitted_at = timezone.now()
        attempt.save(update_fields=['answers', 'score', 'max_score', 'status', 'submitted_at'])
        return Response({'status': 'success', 'message': 'Exam submitted successfully.', 'data': ExamAttemptSerializer(attempt).data})

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

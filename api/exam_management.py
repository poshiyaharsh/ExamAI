from django.db.models import Count
import logging
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Exam, Question
from .permissions import IsFacultyUser
from .serializers import (
    ExamDetailSerializer,
    ExamListSerializer,
    ExamUpdateSerializer,
    FacultyQuestionSerializer,
    QuestionSerializer,
    QuestionUpdateSerializer,
)

logger = logging.getLogger(__name__)


class FacultyExamViewMixin:
    permission_classes = [IsAuthenticated, IsFacultyUser]

    def get_exam(self, request, exam_id):
        from api.tenant import get_user_institution
        tenant = getattr(request, 'tenant', None) or get_user_institution(request.user)
        if not tenant:
            return None
        return Exam.objects.filter(created_by=request.user, institution=tenant, id=exam_id).first()


class ExamListView(APIView):
    permission_classes = [IsAuthenticated, IsFacultyUser]
    pagination_class = None

    def get(self, request):
        from api.tenant import get_user_institution
        tenant = getattr(request, 'tenant', None) or get_user_institution(request.user)
        if not tenant:
            return Response([])

        exams = (
            Exam.objects.filter(created_by=request.user, institution=tenant)
            .annotate(question_count=Count('questions', distinct=True), attempts_count=Count('attempts', distinct=True))
            .order_by('-created_at')
        )
        logger.debug('Faculty exam list user=%s user_id=%s count=%s', request.user, request.user.id, exams.count())
        return Response(ExamListSerializer(exams, many=True).data)


class ExamDetailView(FacultyExamViewMixin, APIView):
    def get(self, request, exam_id):
        exam = self.get_exam(request, exam_id)
        if not exam:
            return Response({'detail': 'Exam not found.'}, status=status.HTTP_404_NOT_FOUND)
        from api.utils.departments import get_exam_visibility_status_for_faculty
        data = ExamDetailSerializer(exam).data
        data['visibility'] = get_exam_visibility_status_for_faculty(exam)
        return Response(data)

    def patch(self, request, exam_id):
        exam = self.get_exam(request, exam_id)
        if not exam:
            return Response({'detail': 'Exam not found.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = ExamUpdateSerializer(exam, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        from api.tenant import bump_tenant_cache_version
        from api.utils.departments import get_exam_visibility_status_for_faculty
        bump_tenant_cache_version(exam.institution_id)

        data = ExamDetailSerializer(exam).data
        data['visibility'] = get_exam_visibility_status_for_faculty(exam)
        return Response(data)


class QuestionUpdateView(FacultyExamViewMixin, APIView):
    def put(self, request, exam_id, question_id):
        exam = self.get_exam(request, exam_id)
        if not exam:
            return Response({'detail': 'Exam not found.'}, status=status.HTTP_404_NOT_FOUND)
        question = Question.objects.filter(exam=exam, institution=exam.institution, id=question_id).first()
        if not question:
            return Response({'detail': 'Question not found.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = QuestionUpdateSerializer(question, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        from api.tenant import bump_tenant_cache_version
        bump_tenant_cache_version(exam.institution_id)
        return Response(FacultyQuestionSerializer(question).data)


class PublishExamView(FacultyExamViewMixin, APIView):
    def post(self, request, exam_id):
        exam = self.get_exam(request, exam_id)
        if not exam:
            return Response({'detail': 'Exam not found.'}, status=status.HTTP_404_NOT_FOUND)

        from api.utils.departments import get_exam_visibility_status_for_faculty, get_faculty_department

        # Validate department
        if not (exam.department or '').strip():
            faculty_dept = get_faculty_department(exam.created_by)
            if faculty_dept:
                exam.department = faculty_dept
                exam.save(update_fields=['department'])
            else:
                return Response(
                    {'detail': 'A valid department must be assigned to the exam before it can be published.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        questions = list(exam.questions.all())
        if not questions:
            return Response({'detail': 'An exam must contain at least one question.'}, status=status.HTTP_400_BAD_REQUEST)
        if sum(question.marks for question in questions) != exam.total_marks:
            return Response(
                {'detail': 'Question marks must sum exactly to the exam total marks before publishing.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        exam.status = Exam.Status.PUBLISHED
        exam.save(update_fields=['status', 'updated_at'])

        from api.tenant import bump_tenant_cache_version
        bump_tenant_cache_version(exam.institution_id)

        visibility = get_exam_visibility_status_for_faculty(exam)
        data = ExamDetailSerializer(exam).data
        data['visibility'] = visibility
        data['message'] = f"Exam published successfully! {visibility['status_summary']}"
        return Response(data)

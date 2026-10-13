from django.db import models
from django.db.models import Count
from django.utils import timezone
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
        return Exam.objects.filter(
            created_by=request.user, institution=tenant, id=exam_id
        ).prefetch_related(
            'questions__option_items',
            'questions__topic',
            'questions__subject',
        ).first()


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

        if exam.status == Exam.Status.PUBLISHED or exam.is_immutable:
            return Response(
                {'detail': 'Published exams are immutable and cannot be modified.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = ExamUpdateSerializer(exam, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        from api.paper_engine.cache import PaperCacheService
        PaperCacheService.invalidate_exam(exam.institution_id, exam.id)

        from api.utils.departments import get_exam_visibility_status_for_faculty
        data = ExamDetailSerializer(exam).data
        data['visibility'] = get_exam_visibility_status_for_faculty(exam)
        return Response(data)


class QuestionUpdateView(FacultyExamViewMixin, APIView):
    def put(self, request, exam_id, question_id):
        exam = self.get_exam(request, exam_id)
        if not exam:
            return Response({'detail': 'Exam not found.'}, status=status.HTTP_404_NOT_FOUND)

        if exam.status == Exam.Status.PUBLISHED or exam.is_immutable:
            return Response(
                {'detail': 'Published exams are immutable and cannot be modified.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        question = Question.objects.filter(exam=exam, institution=exam.institution, id=question_id).first()
        if not question:
            return Response({'detail': 'Question not found.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = QuestionUpdateSerializer(question, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        from api.paper_engine.cache import PaperCacheService
        PaperCacheService.invalidate_exam(exam.institution_id, exam.id)
        return Response(FacultyQuestionSerializer(question).data)


class ShuffleExamView(FacultyExamViewMixin, APIView):
    def post(self, request, exam_id):
        exam = self.get_exam(request, exam_id)
        if not exam:
            return Response({'detail': 'Exam not found.'}, status=status.HTTP_404_NOT_FOUND)

        from api.paper_engine.generator import shuffle_exam_questions
        try:
            tenant = getattr(request, 'tenant', None) or exam.institution
            data = shuffle_exam_questions(exam, request.user, tenant)
            return Response(data)
        except ValueError as err:
            return Response({'detail': str(err)}, status=status.HTTP_400_BAD_REQUEST)


class SwapQuestionView(FacultyExamViewMixin, APIView):
    def post(self, request, exam_id, question_id):
        exam = self.get_exam(request, exam_id)
        if not exam:
            return Response({'detail': 'Exam not found.'}, status=status.HTTP_404_NOT_FOUND)

        from api.paper_engine.generator import swap_single_question
        from api.paper_engine.pool import PoolExhaustedError
        try:
            tenant = getattr(request, 'tenant', None) or exam.institution
            q_data, report = swap_single_question(exam, question_id, request.user, tenant)
            return Response({
                'question': q_data,
                'validation_report': report.to_dict(),
            })
        except PoolExhaustedError as p_err:
            return Response({'detail': p_err.message}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
        except ValueError as v_err:
            return Response({'detail': str(v_err)}, status=status.HTTP_400_BAD_REQUEST)


class ClearFacultyPaperCacheView(FacultyExamViewMixin, APIView):
    def delete(self, request):
        from api.tenant import get_user_institution
        tenant = getattr(request, 'tenant', None) or get_user_institution(request.user)
        if not tenant:
            return Response({'detail': 'No active institution found.'}, status=status.HTTP_400_BAD_REQUEST)

        from api.paper_engine.cache import PaperCacheService
        PaperCacheService.clear_faculty_papers(tenant.id, request.user.id)
        return Response({'status': 'success', 'message': 'Cached papers cleared successfully.'})


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
        exam.is_immutable = True
        exam.save(update_fields=['status', 'is_immutable', 'updated_at'])

        # Update times_used and last_used_at on exam questions and repository bank questions
        now = timezone.now()
        exam.questions.all().update(
            times_used=models.F('times_used') + 1,
            last_used_at=now,
        )
        q_hashes = [q.text_hash for q in questions if q.text_hash]
        if q_hashes:
            Question.objects.filter(
                institution=exam.institution,
                text_hash__in=q_hashes,
                exam__isnull=True,
            ).update(
                times_used=models.F('times_used') + 1,
                last_used_at=now,
            )

        from api.paper_engine.cache import PaperCacheService
        PaperCacheService.invalidate_exam(exam.institution_id, exam.id)

        visibility = get_exam_visibility_status_for_faculty(exam)
        data = ExamDetailSerializer(exam).data
        data['visibility'] = visibility
        data['message'] = f"Exam published successfully! {visibility['status_summary']}"
        return Response(data)

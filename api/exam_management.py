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
        from api.utils.departments import get_faculty_department
        tenant = getattr(request, 'tenant', None) or get_user_institution(request.user)
        if not tenant:
            return None
        faculty_dept = get_faculty_department(request.user)
        qs = Exam.objects.filter(
            created_by=request.user, institution=tenant, id=exam_id
        )
        if faculty_dept and faculty_dept.lower() not in ('', 'unassigned'):
            qs = qs.filter(department__iexact=faculty_dept)
        return qs.prefetch_related(
            'questions__option_items',
            'questions__topic',
            'questions__subject',
        ).first()


class ExamListView(APIView):
    permission_classes = [IsAuthenticated, IsFacultyUser]
    pagination_class = None

    def get(self, request):
        from api.tenant import get_user_institution
        from api.utils.departments import get_faculty_department
        tenant = getattr(request, 'tenant', None) or get_user_institution(request.user)
        if not tenant:
            return Response([])

        faculty_dept = get_faculty_department(request.user)
        qs = Exam.objects.filter(created_by=request.user, institution=tenant)
        if faculty_dept and faculty_dept.lower() not in ('', 'unassigned'):
            qs = qs.filter(department__iexact=faculty_dept)

        exams = (
            qs.annotate(question_count=Count('questions', distinct=True), attempts_count=Count('attempts', distinct=True))
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

    def delete(self, request, exam_id):
        exam = self.get_exam(request, exam_id)
        if not exam:
            return Response({'detail': 'Exam not found.'}, status=status.HTTP_404_NOT_FOUND)
        if exam.status == Exam.Status.PUBLISHED:
            if hasattr(exam, 'attempts') and exam.attempts.exists():
                return Response(
                    {'detail': 'Cannot delete an exam with student attempts. You can close it instead.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        exam.delete()
        return Response({'detail': 'Exam deleted successfully.'}, status=status.HTTP_200_OK)


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

    def delete(self, request, exam_id, question_id):
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

        question.delete()
        from api.paper_engine.cache import PaperCacheService
        PaperCacheService.invalidate_exam(exam.institution_id, exam.id)
        return Response({'deleted': True, 'id': question_id}, status=status.HTTP_200_OK)


class ExamQuestionCreateView(FacultyExamViewMixin, APIView):
    def post(self, request, exam_id):
        exam = self.get_exam(request, exam_id)
        if not exam:
            return Response({'detail': 'Exam not found.'}, status=status.HTTP_404_NOT_FOUND)

        if exam.status == Exam.Status.PUBLISHED or exam.is_immutable:
            return Response(
                {'detail': 'Published exams are immutable and cannot be modified.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        bank_q_id = request.data.get('bank_question_id')
        next_order = exam.questions.count() + 1

        if bank_q_id:
            bank_q = Question.objects.filter(id=bank_q_id, institution=exam.institution).first()
            if not bank_q:
                return Response({'detail': 'Question bank item not found.'}, status=status.HTTP_404_NOT_FOUND)
            new_q = Question.objects.create(
                institution=exam.institution,
                exam=exam,
                order=next_order,
                department=exam.department,
                subject=bank_q.subject,
                topic=bank_q.topic,
                topic_text=bank_q.topic_text,
                question_type=bank_q.question_type,
                difficulty=bank_q.difficulty,
                text=bank_q.text,
                options=bank_q.options,
                correct_answer=bank_q.correct_answer,
                model_answer=bank_q.model_answer,
                explanation=bank_q.explanation,
                marks=bank_q.marks,
                created_by=request.user,
            )
        else:
            q_text = str(request.data.get('text', '')).strip()
            if not q_text:
                return Response({'detail': 'Question text is required.'}, status=status.HTTP_400_BAD_REQUEST)
            q_type = request.data.get('question_type', 'mcq')
            q_diff = request.data.get('difficulty', 'medium')
            q_marks = float(request.data.get('marks', 1.0))
            q_opts = request.data.get('options') or []
            q_ans = request.data.get('correct_answer')
            q_topic = request.data.get('topic', '')

            new_q = Question.objects.create(
                institution=exam.institution,
                exam=exam,
                order=next_order,
                department=exam.department,
                topic_text=q_topic,
                question_type=q_type,
                difficulty=q_diff,
                text=q_text,
                options=q_opts,
                correct_answer=q_ans,
                marks=q_marks,
                created_by=request.user,
            )

        from api.paper_engine.cache import PaperCacheService
        PaperCacheService.invalidate_exam(exam.institution_id, exam.id)
        return Response(FacultyQuestionSerializer(new_q).data, status=status.HTTP_201_CREATED)


class ReorderQuestionsView(FacultyExamViewMixin, APIView):
    def post(self, request, exam_id):
        exam = self.get_exam(request, exam_id)
        if not exam:
            return Response({'detail': 'Exam not found.'}, status=status.HTTP_404_NOT_FOUND)

        if exam.status == Exam.Status.PUBLISHED or exam.is_immutable:
            return Response(
                {'detail': 'Published exams are immutable and cannot be modified.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        question_ids = request.data.get('question_ids', [])
        if not isinstance(question_ids, list):
            return Response({'detail': 'question_ids must be a list.'}, status=status.HTTP_400_BAD_REQUEST)

        for idx, qid in enumerate(question_ids, start=1):
            Question.objects.filter(id=qid, exam=exam, institution=exam.institution).update(order=idx)

        from api.paper_engine.cache import PaperCacheService
        PaperCacheService.invalidate_exam(exam.institution_id, exam.id)

        exam.refresh_from_db()
        return Response(ExamDetailSerializer(exam).data, status=status.HTTP_200_OK)


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

        if not exam.is_reviewed:
            return Response(
                {'detail': 'This generated draft must be reviewed and confirmed before it can be published.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        questions = list(exam.questions.all())
        if not questions:
            return Response({'detail': 'An exam must contain at least one question.'}, status=status.HTTP_400_BAD_REQUEST)
        if exam.random_subset_size:
            if len(questions) < exam.random_subset_size:
                return Response(
                    {'detail': f'The exam question bank has {len(questions)} questions, which is less than the requested subset size of {exam.random_subset_size}.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        elif sum(question.marks for question in questions) != exam.total_marks:
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


class ConfirmExamReviewView(FacultyExamViewMixin, APIView):
    def post(self, request, exam_id):
        exam = self.get_exam(request, exam_id)
        if not exam:
            return Response({'detail': 'Exam not found.'}, status=status.HTTP_404_NOT_FOUND)

        exam.is_reviewed = True
        exam.save(update_fields=['is_reviewed', 'updated_at'])
        return Response({
            'detail': 'Exam review confirmed.',
            'exam': ExamDetailSerializer(exam).data,
        }, status=status.HTTP_200_OK)

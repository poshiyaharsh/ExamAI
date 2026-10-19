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

        from api.utils.schedule import normalize_to_utc, validate_exam_schedule, compute_attempt_expiry
        display_tz = str(request.data.get('display_timezone') or getattr(exam, 'display_timezone', 'Asia/Kolkata')).strip()

        # Handle published exam: only allow deadline (ends_at) extension
        if exam.status == Exam.Status.PUBLISHED or exam.is_immutable:
            disallowed_keys = set(request.data.keys()) - {'ends_at', 'display_timezone'}
            if disallowed_keys:
                return Response(
                    {'detail': 'Published exams are immutable. Only the deadline (ends_at) may be extended.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if 'ends_at' in request.data:
                raw_new_ends = request.data.get('ends_at')
                if not raw_new_ends:
                    return Response({'detail': 'Published exams must have a valid deadline (ends_at).'}, status=status.HTTP_400_BAD_REQUEST)
                new_ends_at = normalize_to_utc(raw_new_ends, display_tz)
                now = timezone.now()

                if new_ends_at < now:
                    return Response({'detail': 'New deadline cannot be in the past.'}, status=status.HTTP_400_BAD_REQUEST)

                if exam.ends_at and new_ends_at < exam.ends_at and exam.attempts.exists():
                    return Response(
                        {'detail': 'Cannot shorten deadline on an active exam with student attempts. You can only extend it.'},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                exam.ends_at = new_ends_at
                update_fields = ['ends_at', 'updated_at']
                if 'display_timezone' in request.data:
                    exam.display_timezone = display_tz
                    update_fields.append('display_timezone')
                exam.save(update_fields=update_fields)

                # Recompute expires_at for any in-progress attempts
                in_progress_attempts = exam.attempts.filter(status=StudentAttempt.Status.IN_PROGRESS)
                for att in in_progress_attempts:
                    att.expires_at = compute_attempt_expiry(exam, att.started_at, now)
                    att.save(update_fields=['expires_at'])

                from api.paper_engine.cache import PaperCacheService
                PaperCacheService.invalidate_exam(exam.institution_id, exam.id)

                from api.utils.departments import get_exam_visibility_status_for_faculty
                data = ExamDetailSerializer(exam).data
                data['visibility'] = get_exam_visibility_status_for_faculty(exam)
                return Response(data)

            if 'display_timezone' in request.data:
                exam.display_timezone = display_tz
                exam.save(update_fields=['display_timezone', 'updated_at'])
                from api.utils.departments import get_exam_visibility_status_for_faculty
                data = ExamDetailSerializer(exam).data
                data['visibility'] = get_exam_visibility_status_for_faculty(exam)
                return Response(data)

            return Response(
                {'detail': 'No updates provided.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Draft exam update
        data = request.data.copy()
        if 'starts_at' in data and data['starts_at']:
            data['starts_at'] = normalize_to_utc(data['starts_at'], display_tz)
        if 'ends_at' in data and data['ends_at']:
            data['ends_at'] = normalize_to_utc(data['ends_at'], display_tz)

        # Validate schedule if provided
        test_starts = data.get('starts_at', exam.starts_at)
        test_ends = data.get('ends_at', exam.ends_at)
        test_dur = data.get('duration_minutes', exam.duration_minutes)
        if test_starts or test_ends:
            is_valid, err_msg = validate_exam_schedule(test_starts, test_ends, test_dur, is_publishing=False)
            if not is_valid:
                return Response({'detail': err_msg}, status=status.HTTP_400_BAD_REQUEST)

        serializer = ExamUpdateSerializer(exam, data=data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        if 'display_timezone' in request.data:
            exam.display_timezone = display_tz
            exam.save(update_fields=['display_timezone'])

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

    def patch(self, request, exam_id, question_id):
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
        serializer = QuestionUpdateSerializer(question, data=request.data, partial=True)
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
        # Recalculate exam total marks and shortfall
        active_qs = exam.questions.filter(is_deleted=False)
        actual_sum = sum(q.marks for q in active_qs)
        exam.total_marks = int(round(float(actual_sum)))
        if exam.target_total_marks:
            exam.marks_shortfall = max(0, exam.target_total_marks - exam.total_marks)
        exam.save(update_fields=['total_marks', 'marks_shortfall'])

        from api.paper_engine.cache import PaperCacheService
        PaperCacheService.invalidate_exam(exam.institution_id, exam.id)
        return Response({'deleted': True, 'id': question_id, 'actual_total_marks': exam.total_marks, 'marks_shortfall': exam.marks_shortfall}, status=status.HTTP_200_OK)


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
                source='manual',
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
                model_answer=str(request.data.get('model_answer', '')),
                accepted_answers=request.data.get('accepted_answers') or [],
                rubric=request.data.get('rubric') or [],
                word_limit=request.data.get('word_limit'),
                source='manual',
                marks=q_marks,
                created_by=request.user,
            )

            if q_opts and isinstance(q_opts, list) and q_type in {'mcq', 'true_false', 'truefalse'}:
                from api.models import Option
                opts_to_create = []
                correct_str = str(q_ans).strip().lower() if q_ans is not None else ''
                for opt_idx, opt_txt in enumerate(q_opts, start=1):
                    clean_opt_str = str(opt_txt).strip().lower()
                    is_corr = (clean_opt_str == correct_str) or (str(opt_idx - 1) == correct_str) or (
                        correct_str in {'a': 0, 'b': 1, 'c': 2, 'd': 3} and opt_idx - 1 == {'a': 0, 'b': 1, 'c': 2, 'd': 3}[correct_str]
                    ) or (clean_opt_str == 'true' and correct_str in {'true', 't', '1'}) or (clean_opt_str == 'false' and correct_str in {'false', 'f', '0'})
                    opts_to_create.append(Option(
                        question=new_q,
                        text=str(opt_txt),
                        is_correct=is_corr,
                        order=opt_idx,
                    ))
                if opts_to_create:
                    Option.objects.bulk_create(opts_to_create)

        # Recalculate exam total marks and shortfall
        active_qs = exam.questions.filter(is_deleted=False)
        actual_sum = sum(q.marks for q in active_qs)
        exam.total_marks = int(round(float(actual_sum)))
        if exam.target_total_marks:
            exam.marks_shortfall = max(0, exam.target_total_marks - exam.total_marks)
        exam.save(update_fields=['total_marks', 'marks_shortfall'])

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

        # Enforce strict schedule window on publish
        from api.utils.schedule import validate_exam_schedule
        sched_ok, sched_err = validate_exam_schedule(
            exam.starts_at, exam.ends_at, exam.duration_minutes, is_publishing=True
        )
        if not sched_ok:
            return Response({'detail': sched_err}, status=status.HTTP_400_BAD_REQUEST)

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
            actual_sum = sum(question.marks for question in questions)
            return Response(
                {'detail': f'Question marks ({actual_sum}) must equal exam total marks ({exam.total_marks}).'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Shortfall check: block publish if marks_shortfall > 0 unless confirm_shortfall is explicitly sent
        if exam.marks_shortfall > 0:
            if not request.data.get('confirm_shortfall'):
                return Response(
                    {
                        'detail': f'This paper has an unresolved shortfall of {exam.marks_shortfall} marks ({exam.total_marks} of {exam.target_total_marks} marks generated). Resolve the shortfall before publishing, or confirm "Publish with {exam.marks_shortfall} fewer marks".',
                        'marks_shortfall': exam.marks_shortfall,
                        'target_total_marks': exam.target_total_marks,
                        'actual_total_marks': exam.total_marks,
                        'requires_shortfall_confirmation': True,
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            else:
                report = exam.validation_report or {}
                report['shortfall_publish_confirmed'] = {
                    'confirmed_by': request.user.username,
                    'confirmed_at': timezone.now().isoformat(),
                    'original_target': exam.target_total_marks,
                    'published_marks': exam.total_marks,
                    'shortfall': exam.marks_shortfall,
                }
                exam.validation_report = report
                exam.target_total_marks = exam.total_marks
                exam.marks_shortfall = 0
                exam.save(update_fields=['validation_report', 'target_total_marks', 'marks_shortfall'])

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


class AdjustMarksView(FacultyExamViewMixin, APIView):
    """
    Handles marks adjustments for exams with shortfalls:
    - action 'set_actual': sets target_total_marks to total_marks (shortfall = 0).
    - action 'preview_scale': calculates scaled marks per question to hit target_total_marks.
    - action 'scale_target': applies the integer-rounded scaled marks to all questions.
    """
    def post(self, request, exam_id):
        exam = self.get_exam(request, exam_id)
        if not exam:
            return Response({'detail': 'Exam not found.'}, status=status.HTTP_404_NOT_FOUND)

        if exam.status == Exam.Status.PUBLISHED or exam.is_immutable:
            return Response({'detail': 'Cannot modify published exams.'}, status=status.HTTP_400_BAD_REQUEST)

        action = request.data.get('action')
        target_raw = request.data.get('target_marks')
        target = int(target_raw) if target_raw is not None else int(exam.target_total_marks or exam.total_marks or 0)
        active_questions = list(exam.questions.filter(is_deleted=False).order_by('order'))
        if not active_questions:
            return Response({'detail': 'Exam has no active questions.'}, status=status.HTTP_400_BAD_REQUEST)

        current_total = float(sum(q.marks for q in active_questions))

        if action == 'set_actual':
            exam.target_total_marks = int(round(current_total))
            exam.total_marks = exam.target_total_marks
            exam.marks_shortfall = 0
            exam.save(update_fields=['target_total_marks', 'total_marks', 'marks_shortfall', 'updated_at'])
            return Response({
                'detail': f'Paper total marks updated to {exam.total_marks}. Shortfall resolved.',
                'target_total_marks': exam.target_total_marks,
                'total_marks': exam.total_marks,
                'marks_shortfall': 0,
                'exam': ExamDetailSerializer(exam).data,
            })

        elif action in {'preview_scale', 'scale_target'}:
            scale_ratio = (float(target) / current_total) if current_total > 0 else 1.0
            previews = []
            running_marks = 0

            for idx, q in enumerate(active_questions):
                if idx == len(active_questions) - 1:
                    new_m = max(1, target - running_marks)
                else:
                    new_m = max(1, int(round(float(q.marks) * scale_ratio)))
                    running_marks += new_m

                previews.append({
                    'id': q.id,
                    'order': q.order,
                    'text': q.text[:80] + '...',
                    'old_marks': float(q.marks),
                    'new_marks': new_m,
                })

            if action == 'preview_scale':
                preview_data = {
                    'target_marks': target,
                    'current_marks': int(round(current_total)),
                    'current_total': float(current_total),
                    'scaled_total': sum(p['new_marks'] for p in previews),
                    'scaling_factor': round(scale_ratio, 2),
                    'question_previews': previews,
                }
                return Response({
                    **preview_data,
                    'preview': preview_data,
                })

            for p in previews:
                Question.objects.filter(id=p['id']).update(marks=p['new_marks'])

            exam.total_marks = target
            exam.marks_shortfall = 0
            exam.save(update_fields=['total_marks', 'marks_shortfall', 'updated_at'])

            from api.paper_engine.cache import PaperCacheService
            PaperCacheService.invalidate_exam(exam.institution_id, exam.id)

            return Response({
                'detail': f'Questions scaled successfully to reach target of {target} marks.',
                'target_total_marks': exam.target_total_marks,
                'total_marks': exam.total_marks,
                'marks_shortfall': 0,
                'exam': ExamDetailSerializer(exam).data,
            })

        return Response({'detail': "Invalid action. Supported actions: 'set_actual', 'preview_scale', 'scale_target'."}, status=status.HTTP_400_BAD_REQUEST)

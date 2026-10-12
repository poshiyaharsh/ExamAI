"""REST API views for Question Bank management."""

import csv
import io
import json
import logging
from decimal import Decimal
from typing import Any, Dict, List

from django.core.cache import cache
from django.db import models, transaction
from django.db.models import Count, Q
from django.http import HttpResponse
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from api.models import (
    Option,
    Question,
    QuestionAuditLog,
    QuestionImportLog,
    Subject,
    Topic,
)
from api.permissions_question_bank import (
    IsAdminOrFacultyDepartmentReadOnly,
    IsAdminQuestionBank,
)
from api.serializers_question_bank import (
    BulkActionSerializer,
    OptionSerializer,
    QuestionCreateUpdateSerializer,
    QuestionDetailSerializer,
    QuestionImportLogSerializer,
    QuestionListSerializer,
    SubjectSerializer,
    TopicSerializer,
)
from api.tenant import (
    bump_tenant_cache_version,
    get_tenant_object_or_404,
    get_user_institution,
)
from api.utils.departments import get_faculty_department, normalize_department
from api.validators.question_bank import (
    compute_text_hash,
    is_question_used_in_exam,
    sanitize_formula_injection,
    sanitize_text,
    validate_question_payload,
)

logger = logging.getLogger(__name__)


class QuestionBankPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100

    def get_paginated_response(self, data):
        return Response({
            'count': self.page.paginator.count,
            'total_pages': self.page.paginator.num_pages,
            'current_page': self.page.number,
            'next': self.get_next_link(),
            'previous': self.get_previous_link(),
            'results': data,
        })


def _get_active_tenant(request):
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        tenant = get_user_institution(request.user)
        request.tenant = tenant
    if not tenant:
        raise PermissionDenied('No active institution context associated with this request.')
    return tenant


class QuestionListCreateAPIView(APIView):
    permission_classes = [IsAdminOrFacultyDepartmentReadOnly]
    pagination_class = QuestionBankPagination

    def get_queryset(self, request, tenant):
        qs = Question.objects.filter(
            institution=tenant,
            is_deleted=False,
        ).select_related('subject', 'topic', 'created_by').annotate(
            options_count_annotated=Count('option_items', distinct=True)
        )

        # Faculty department restriction
        is_admin = getattr(request.user, 'admin_profile', None) is not None
        if not is_admin:
            faculty_dept = get_faculty_department(request.user)
            if faculty_dept:
                qs = qs.filter(department=faculty_dept, status='ACTIVE')
            else:
                qs = qs.none()

        params = request.query_params

        # Subject
        sub = params.get('subject') or params.get('subject_id')
        if sub:
            qs = qs.filter(subject_id=sub)

        # Topic
        top = params.get('topic') or params.get('topic_id')
        if top:
            qs = qs.filter(topic_id=top)

        # Department
        dept = params.get('department')
        if dept and is_admin:
            norm_dept = normalize_department(dept)
            if norm_dept:
                qs = qs.filter(department=norm_dept)

        # Question type
        q_type = params.get('type') or params.get('question_type')
        if q_type:
            qs = qs.filter(question_type__iexact=q_type)

        # Difficulty
        diff = params.get('difficulty')
        if diff and diff.lower() != 'all':
            qs = qs.filter(difficulty__iexact=diff)

        # Status
        st = params.get('status')
        if st and st.lower() != 'all':
            qs = qs.filter(status__iexact=st)

        # Marks Range
        marks_min = params.get('marks_min')
        if marks_min:
            try:
                qs = qs.filter(marks__gte=Decimal(str(marks_min)))
            except Exception:
                pass
        marks_max = params.get('marks_max')
        if marks_max:
            try:
                qs = qs.filter(marks__lte=Decimal(str(marks_max)))
            except Exception:
                pass

        # Tag
        tag = params.get('tag')
        if tag:
            qs = qs.filter(tags__icontains=tag.strip())

        # Created By
        created_by_id = params.get('created_by')
        if created_by_id:
            qs = qs.filter(created_by_id=created_by_id)

        # Date Range
        date_from = params.get('date_from')
        if date_from:
            d_from = parse_date(date_from)
            if d_from:
                qs = qs.filter(created_at__date__gte=d_from)
        date_to = params.get('date_to')
        if date_to:
            d_to = parse_date(date_to)
            if d_to:
                qs = qs.filter(created_at__date__lte=d_to)

        # Used / Unused filter
        used = params.get('used')
        if used is not None:
            if used.lower() in ('true', '1', 'yes'):
                qs = qs.filter(times_used__gt=0)
            elif used.lower() in ('false', '0', 'no'):
                qs = qs.filter(times_used=0)

        # Search across text and tags
        search = params.get('search')
        if search and search.strip():
            s = search.strip()
            qs = qs.filter(
                Q(text__icontains=s) |
                Q(tags__icontains=s) |
                Q(subject__name__icontains=s) |
                Q(topic__name__icontains=s)
            )

        # Sorting
        ordering = params.get('ordering', '-created_at')
        allowed_ordering = {
            'newest': '-created_at',
            'oldest': 'created_at',
            'most_used': '-times_used',
            'least_used': 'times_used',
            'marks_high': '-marks',
            'marks_low': 'marks',
            'difficulty': 'difficulty',
            '-created_at': '-created_at',
            'created_at': 'created_at',
        }
        qs = qs.order_by(allowed_ordering.get(ordering, '-created_at'))

        return qs

    def get(self, request):
        tenant = _get_active_tenant(request)
        qs = self.get_queryset(request, tenant)

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(qs, request)
        serializer = QuestionListSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    def post(self, request):
        # Strict Admin only for creation
        tenant = _get_active_tenant(request)
        if not getattr(request.user, 'admin_profile', None):
            return Response({'detail': 'Only institution administrators can create questions.'}, status=status.HTTP_403_FORBIDDEN)

        serializer = QuestionCreateUpdateSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        question = serializer.save()

        try:
            bump_tenant_cache_version(tenant.id)
        except Exception:
            pass

        data = QuestionDetailSerializer(question).data
        data['warnings'] = serializer.context.get('warnings', [])
        return Response(data, status=status.HTTP_201_CREATED)


class QuestionDetailAPIView(APIView):
    permission_classes = [IsAdminOrFacultyDepartmentReadOnly]

    def get_object(self, request, pk):
        tenant = _get_active_tenant(request)
        question = get_tenant_object_or_404(
            Question.objects.select_related('subject', 'topic', 'exam', 'created_by').prefetch_related('option_items', 'audit_logs'),
            tenant,
            id=pk,
            is_deleted=False,
        )

        # Faculty restriction: must match department
        is_admin = getattr(request.user, 'admin_profile', None) is not None
        if not is_admin:
            faculty_dept = get_faculty_department(request.user)
            if not faculty_dept or question.department != faculty_dept:
                raise PermissionDenied('Access denied to questions outside your department.')

        return question

    def get(self, request, pk):
        question = self.get_object(request, pk)
        serializer = QuestionDetailSerializer(question)
        return Response(serializer.data)

    def put(self, request, pk):
        return self.patch(request, pk)

    def patch(self, request, pk):
        tenant = _get_active_tenant(request)
        if not getattr(request.user, 'admin_profile', None):
            return Response({'detail': 'Only institution administrators can modify questions.'}, status=status.HTTP_403_FORBIDDEN)

        question = get_tenant_object_or_404(Question, tenant, id=pk, is_deleted=False)

        serializer = QuestionCreateUpdateSerializer(
            question,
            data=request.data,
            partial=True,
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        updated_q = serializer.save()

        try:
            bump_tenant_cache_version(tenant.id)
        except Exception:
            pass

        data = QuestionDetailSerializer(updated_q).data
        data['warnings'] = serializer.context.get('warnings', [])
        return Response(data)

    def delete(self, request, pk):
        tenant = _get_active_tenant(request)
        if not getattr(request.user, 'admin_profile', None):
            return Response({'detail': 'Only institution administrators can delete questions.'}, status=status.HTTP_403_FORBIDDEN)

        question = get_tenant_object_or_404(Question, tenant, id=pk, is_deleted=False)

        # Rule 9: Prevent deletion if used in published/ongoing exam
        is_used, reason = is_question_used_in_exam(question)
        if is_used:
            return Response({
                'detail': f'Cannot delete this question: {reason}. You can archive it instead.'
            }, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            question.is_deleted = True
            question.deleted_at = timezone.now()
            question.save(update_fields=['is_deleted', 'deleted_at'])

            QuestionAuditLog.objects.create(
                institution=tenant,
                question=question,
                user=request.user,
                action='DELETE',
                changes={'deleted_at': str(question.deleted_at)},
            )

        try:
            bump_tenant_cache_version(tenant.id)
        except Exception:
            pass

        return Response({'message': 'Question successfully soft-deleted.'}, status=status.HTTP_200_OK)


class QuestionRestoreAPIView(APIView):
    permission_classes = [IsAdminQuestionBank]

    def post(self, request, pk):
        tenant = _get_active_tenant(request)
        question = get_tenant_object_or_404(Question, tenant, id=pk, is_deleted=True)

        with transaction.atomic():
            question.is_deleted = False
            question.deleted_at = None
            question.save(update_fields=['is_deleted', 'deleted_at'])

            QuestionAuditLog.objects.create(
                institution=tenant,
                question=question,
                user=request.user,
                action='RESTORE',
                changes={'restored_at': str(timezone.now())},
            )

        try:
            bump_tenant_cache_version(tenant.id)
        except Exception:
            pass

        return Response(QuestionDetailSerializer(question).data)


class QuestionDuplicateAPIView(APIView):
    permission_classes = [IsAdminQuestionBank]

    @transaction.atomic
    def post(self, request, pk):
        tenant = _get_active_tenant(request)
        original = get_tenant_object_or_404(
            Question.objects.prefetch_related('option_items'),
            tenant,
            id=pk,
            is_deleted=False,
        )

        copy_text = f"{original.text} (Copy)"
        new_hash = compute_text_hash(copy_text)

        clone = Question.objects.create(
            institution=tenant,
            department=original.department,
            subject=original.subject,
            topic=original.topic,
            topic_name=original.topic_name,
            exam=None,  # Reset exam attachment
            question_type=original.question_type,
            difficulty=original.difficulty,
            text=copy_text,
            explanation=original.explanation,
            marks=original.marks,
            negative_marks=original.negative_marks,
            status=Question.Status.DRAFT,  # Always cloned as Draft
            is_deleted=False,
            text_hash=new_hash,
            version=1,
            times_used=0,
            last_used_at=None,
            tags=original.tags,
            created_by=request.user,
            model_answer=original.model_answer,
            options=original.options,
            correct_answer=original.correct_answer,
        )

        # Clone options
        new_opts = [
            Option(
                question=clone,
                text=opt.text,
                is_correct=opt.is_correct,
                order=opt.order,
            )
            for opt in original.option_items.all()
        ]
        if new_opts:
            Option.objects.bulk_create(new_opts)

        QuestionAuditLog.objects.create(
            institution=tenant,
            question=clone,
            user=request.user,
            action='DUPLICATE',
            changes={'cloned_from_id': original.id},
        )

        try:
            bump_tenant_cache_version(tenant.id)
        except Exception:
            pass

        return Response(QuestionDetailSerializer(clone).data, status=status.HTTP_201_CREATED)


class QuestionBulkActionAPIView(APIView):
    permission_classes = [IsAdminQuestionBank]

    def post(self, request):
        tenant = _get_active_tenant(request)
        serializer = BulkActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        action = serializer.validated_data['action']
        ids = serializer.validated_data['ids']
        target_val = serializer.validated_data['target_value']

        # Verify all IDs belong to this institution
        qs = Question.objects.filter(institution=tenant, id__in=ids, is_deleted=False)
        found_ids = set(qs.values_list('id', flat=True))
        missing_ids = [item_id for item_id in ids if item_id not in found_ids]
        if missing_ids:
            return Response({
                'detail': f'Some question IDs do not exist in your institution: {missing_ids[:5]}'
            }, status=status.HTTP_404_NOT_FOUND)

        with transaction.atomic():
            if action == 'activate':
                updated_count = qs.update(status=Question.Status.ACTIVE, updated_at=timezone.now())

            elif action == 'archive':
                updated_count = qs.update(status=Question.Status.ARCHIVED, updated_at=timezone.now())

            elif action == 'delete':
                # Check Rule 9
                locked_qs = []
                for q in qs:
                    used, reason = is_question_used_in_exam(q)
                    if used:
                        locked_qs.append(q.id)

                if locked_qs:
                    return Response({
                        'detail': f'Cannot bulk delete questions used in exams: {locked_qs[:5]}. Please archive them instead.'
                    }, status=status.HTTP_400_BAD_REQUEST)

                now = timezone.now()
                updated_count = qs.update(is_deleted=True, deleted_at=now, updated_at=now)

            elif action == 'change_difficulty':
                diff = target_val.upper()
                if diff not in ('EASY', 'MEDIUM', 'HARD'):
                    return Response({'detail': 'Invalid difficulty level.'}, status=status.HTTP_400_BAD_REQUEST)
                updated_count = qs.update(difficulty=diff, updated_at=timezone.now())

            elif action == 'change_topic':
                try:
                    topic_obj = Topic.objects.get(id=int(target_val), institution=tenant)
                    updated_count = qs.update(topic=topic_obj, topic_name=topic_obj.name, updated_at=timezone.now())
                except Exception:
                    return Response({'detail': 'Invalid topic ID for your institution.'}, status=status.HTTP_400_BAD_REQUEST)

            elif action == 'change_subject':
                try:
                    subject_obj = Subject.objects.get(id=int(target_val), institution=tenant)
                    updated_count = qs.update(subject=subject_obj, department=subject_obj.department, updated_at=timezone.now())
                except Exception:
                    return Response({'detail': 'Invalid subject ID for your institution.'}, status=status.HTTP_400_BAD_REQUEST)

            # Audit logs
            audit_records = [
                QuestionAuditLog(
                    institution=tenant,
                    question=q,
                    user=request.user,
                    action=f'BULK_{action.upper()}',
                    changes={'action': action, 'target_value': target_val},
                )
                for q in qs
            ]
            QuestionAuditLog.objects.bulk_create(audit_records)

        try:
            bump_tenant_cache_version(tenant.id)
        except Exception:
            pass

        return Response({
            'message': f'Bulk action {action} applied successfully to {len(ids)} questions.',
            'affected_count': len(ids),
        })


class QuestionStatsAPIView(APIView):
    permission_classes = [IsAdminOrFacultyDepartmentReadOnly]

    def get(self, request):
        tenant = _get_active_tenant(request)

        qs = Question.objects.filter(institution=tenant, is_deleted=False)

        # Faculty restriction
        is_admin = getattr(request.user, 'admin_profile', None) is not None
        if not is_admin:
            faculty_dept = get_faculty_department(request.user)
            if faculty_dept:
                qs = qs.filter(department=faculty_dept)
            else:
                qs = qs.none()

        total = qs.count()
        unused = qs.filter(times_used=0).count()

        # By difficulty
        diff_counts = dict(qs.values('difficulty').annotate(c=Count('id')).values_list('difficulty', 'c'))

        # By status
        status_counts = dict(qs.values('status').annotate(c=Count('id')).values_list('status', 'c'))

        # By question type
        type_counts = dict(qs.values('question_type').annotate(c=Count('id')).values_list('question_type', 'c'))

        # By department
        dept_counts = dict(qs.values('department').annotate(c=Count('id')).values_list('department', 'c'))

        # Top 5 most used questions
        most_used = list(
            qs.filter(times_used__gt=0).order_by('-times_used').values(
                'id', 'text', 'times_used', 'last_used_at', 'marks', 'difficulty'
            )[:5]
        )

        return Response({
            'total_questions': total,
            'unused_count': unused,
            'by_difficulty': {
                'Easy': diff_counts.get('EASY', 0) + diff_counts.get('easy', 0),
                'Medium': diff_counts.get('MEDIUM', 0) + diff_counts.get('medium', 0),
                'Hard': diff_counts.get('HARD', 0) + diff_counts.get('hard', 0),
            },
            'by_status': {
                'Active': status_counts.get('ACTIVE', 0),
                'Draft': status_counts.get('DRAFT', 0),
                'Archived': status_counts.get('ARCHIVED', 0),
            },
            'by_type': type_counts,
            'by_department': dept_counts,
            'most_used_questions': most_used,
        })


class SubjectListCreateAPIView(APIView):
    permission_classes = [IsAdminOrFacultyDepartmentReadOnly]

    def get(self, request):
        tenant = _get_active_tenant(request)
        qs = Subject.objects.filter(institution=tenant).annotate(
            question_count=Count('questions', filter=Q(questions__is_deleted=False))
        ).order_by('name')

        dept = request.query_params.get('department')
        if dept:
            qs = qs.filter(department=normalize_department(dept))

        serializer = SubjectSerializer(qs, many=True)
        return Response(serializer.data)

    def post(self, request):
        tenant = _get_active_tenant(request)
        if not getattr(request.user, 'admin_profile', None):
            return Response({'detail': 'Admin access required to create subjects.'}, status=status.HTTP_403_FORBIDDEN)

        serializer = SubjectSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        subject = serializer.save(institution=tenant, created_by=request.user)
        return Response(SubjectSerializer(subject).data, status=status.HTTP_201_CREATED)


class SubjectDetailAPIView(APIView):
    permission_classes = [IsAdminQuestionBank]

    def get_object(self, request, pk):
        tenant = _get_active_tenant(request)
        return get_tenant_object_or_404(Subject, tenant, id=pk)

    def put(self, request, pk):
        subject = self.get_object(request, pk)
        serializer = SubjectSerializer(subject, data=request.data, partial=True, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def delete(self, request, pk):
        subject = self.get_object(request, pk)
        # Block deleting subject with questions
        active_q_count = Question.objects.filter(subject=subject, is_deleted=False).count()
        if active_q_count > 0:
            return Response({
                'detail': f"Cannot delete subject '{subject.name}': it currently contains {active_q_count} active questions."
            }, status=status.HTTP_400_BAD_REQUEST)

        subject.delete()
        return Response({'message': f"Subject '{subject.name}' deleted successfully."})


class TopicListCreateAPIView(APIView):
    permission_classes = [IsAdminOrFacultyDepartmentReadOnly]

    def get(self, request):
        tenant = _get_active_tenant(request)
        qs = Topic.objects.filter(institution=tenant).select_related('subject').annotate(
            question_count=Count('questions', filter=Q(questions__is_deleted=False))
        ).order_by('name')

        sub = request.query_params.get('subject') or request.query_params.get('subject_id')
        if sub:
            qs = qs.filter(subject_id=sub)

        serializer = TopicSerializer(qs, many=True)
        return Response(serializer.data)

    def post(self, request):
        tenant = _get_active_tenant(request)
        if not getattr(request.user, 'admin_profile', None):
            return Response({'detail': 'Admin access required to create topics.'}, status=status.HTTP_403_FORBIDDEN)

        serializer = TopicSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        topic = serializer.save(institution=tenant, created_by=request.user)
        return Response(TopicSerializer(topic).data, status=status.HTTP_201_CREATED)


class TopicDetailAPIView(APIView):
    permission_classes = [IsAdminQuestionBank]

    def get_object(self, request, pk):
        tenant = _get_active_tenant(request)
        return get_tenant_object_or_404(Topic, tenant, id=pk)

    def put(self, request, pk):
        topic = self.get_object(request, pk)
        serializer = TopicSerializer(topic, data=request.data, partial=True, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def delete(self, request, pk):
        topic = self.get_object(request, pk)
        active_q_count = Question.objects.filter(topic=topic, is_deleted=False).count()
        if active_q_count > 0:
            return Response({
                'detail': f"Cannot delete topic '{topic.name}': it currently contains {active_q_count} active questions."
            }, status=status.HTTP_400_BAD_REQUEST)

        topic.delete()
        return Response({'message': f"Topic '{topic.name}' deleted successfully."})


class QuestionExportAPIView(APIView):
    permission_classes = [IsAdminOrFacultyDepartmentReadOnly]

    def get(self, request):
        tenant = _get_active_tenant(request)
        list_view = QuestionListCreateAPIView()
        qs = list_view.get_queryset(request, tenant).prefetch_related('option_items')

        export_format = request.query_params.get('format', 'csv').lower()

        headers = [
            'ID', 'Department', 'Subject', 'Topic', 'Question Type', 'Difficulty',
            'Marks', 'Negative Marks', 'Question Text', 'Explanation', 'Status',
            'Option 1', 'Option 2', 'Option 3', 'Option 4', 'Correct Option(s)',
            'Model Answer', 'Times Used', 'Tags',
        ]

        rows = []
        for q in qs:
            opts = list(q.option_items.all())
            opt_texts = [o.text for o in opts]
            while len(opt_texts) < 4:
                opt_texts.append('')
            correct_opts = [str(idx) for idx, o in enumerate(opts, start=1) if o.is_correct]

            rows.append([
                sanitize_formula_injection(str(q.id)),
                sanitize_formula_injection(q.department),
                sanitize_formula_injection(q.subject.name if q.subject else ''),
                sanitize_formula_injection(q.topic.name if q.topic else q.topic_name),
                sanitize_formula_injection(q.question_type),
                sanitize_formula_injection(q.difficulty),
                sanitize_formula_injection(str(q.marks)),
                sanitize_formula_injection(str(q.negative_marks)),
                sanitize_formula_injection(q.text),
                sanitize_formula_injection(q.explanation),
                sanitize_formula_injection(q.status),
                sanitize_formula_injection(opt_texts[0]),
                sanitize_formula_injection(opt_texts[1]),
                sanitize_formula_injection(opt_texts[2]),
                sanitize_formula_injection(opt_texts[3]),
                sanitize_formula_injection(', '.join(correct_opts)),
                sanitize_formula_injection(q.model_answer),
                sanitize_formula_injection(str(q.times_used)),
                sanitize_formula_injection(', '.join(q.tags or [])),
            ])

        if export_format == 'xlsx':
            try:
                import openpyxl
                from openpyxl.styles import Font, PatternFill
                wb = openpyxl.Workbook()
                ws = wb.active
                ws.title = 'Question Bank'

                # Header row
                ws.append(headers)
                header_fill = PatternFill(start_color='1F4E79', end_color='1F4E79', fill_type='solid')
                header_font = Font(color='FFFFFF', bold=True)
                for col_num in range(1, len(headers) + 1):
                    cell = ws.cell(row=1, column=col_num)
                    cell.fill = header_fill
                    cell.font = header_font

                for r in rows:
                    ws.append(r)

                out = io.BytesIO()
                wb.save(out)
                out.seek(0)
                response = HttpResponse(
                    out.getvalue(),
                    content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                )
                response['Content-Disposition'] = f'attachment; filename="question_bank_{tenant.id}_{timezone.now().strftime("%Y%m%d")}.xlsx"'
                return response
            except ImportError:
                pass  # Fallback to CSV

        # CSV format
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(headers)
        writer.writerows(rows)

        response = HttpResponse(output.getvalue(), content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="question_bank_{tenant.id}_{timezone.now().strftime("%Y%m%d")}.csv"'
        return response


class QuestionImportTemplateAPIView(APIView):
    permission_classes = [IsAdminOrFacultyDepartmentReadOnly]

    def get(self, request):
        fmt = request.query_params.get('format', 'csv').lower()

        headers = [
            'department', 'subject', 'topic', 'question_type', 'difficulty',
            'marks', 'negative_marks', 'question_text', 'explanation',
            'option_1', 'option_2', 'option_3', 'option_4', 'correct_options',
            'model_answer', 'tags',
        ]
        sample_row = [
            'Computer Science', 'Data Structures', 'Binary Trees', 'MCQ_SINGLE', 'MEDIUM',
            '2.0', '0.5', 'What is the maximum number of nodes in a binary tree of depth k?',
            'The maximum number of nodes at depth k is 2^(k+1) - 1.',
            '2^k - 1', '2^(k+1) - 1', '2^(k-1) + 1', '2^k + 1', '2',
            '', 'binary tree, trees, dsa',
        ]

        if fmt == 'xlsx':
            try:
                import openpyxl
                from openpyxl.styles import Font, PatternFill
                wb = openpyxl.Workbook()
                ws = wb.active
                ws.title = 'Template'
                ws.append(headers)
                ws.append(sample_row)

                header_fill = PatternFill(start_color='1F4E79', end_color='1F4E79', fill_type='solid')
                header_font = Font(color='FFFFFF', bold=True)
                for col_num in range(1, len(headers) + 1):
                    cell = ws.cell(row=1, column=col_num)
                    cell.fill = header_fill
                    cell.font = header_font

                out = io.BytesIO()
                wb.save(out)
                out.seek(0)
                resp = HttpResponse(out.getvalue(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
                resp['Content-Disposition'] = 'attachment; filename="question_import_template.xlsx"'
                return resp
            except ImportError:
                pass

        out = io.StringIO()
        writer = csv.writer(out)
        writer.writerow(headers)
        writer.writerow(sample_row)
        resp = HttpResponse(out.getvalue(), content_type='text/csv')
        resp['Content-Disposition'] = 'attachment; filename="question_import_template.csv"'
        return resp


class QuestionBulkImportAPIView(APIView):
    permission_classes = [IsAdminQuestionBank]
    parser_classes = [MultiPartParser, FormParser]

    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB limit
    MAX_ROWS = 2000

    def parse_file(self, uploaded_file) -> List[Dict[str, Any]]:
        filename = uploaded_file.name or ''
        ext = filename.split('.')[-1].lower() if '.' in filename else ''
        if ext not in ('csv', 'xlsx'):
            raise ValidationError({'file': 'Only CSV and XLSX files are accepted.'})

        rows = []
        if ext == 'csv':
            content = uploaded_file.read().decode('utf-8-sig', errors='replace')
            reader = csv.DictReader(io.StringIO(content))
            for row in reader:
                rows.append({k.strip().lower() if k else '': v for k, v in row.items()})
        elif ext == 'xlsx':
            import openpyxl
            wb = openpyxl.load_workbook(uploaded_file, data_only=True)
            ws = wb.active
            headers = []
            for row_idx, row in enumerate(ws.iter_rows(values_only=True), start=1):
                if row_idx == 1:
                    headers = [str(cell).strip().lower() if cell is not None else '' for cell in row]
                    continue
                if not any(row):
                    continue
                row_dict = {}
                for col_idx, val in enumerate(row):
                    if col_idx < len(headers) and headers[col_idx]:
                        row_dict[headers[col_idx]] = str(val).strip() if val is not None else ''
                rows.append(row_dict)

        if len(rows) > self.MAX_ROWS:
            raise ValidationError({'file': f'Maximum allowed rows per import is {self.MAX_ROWS}. Found {len(rows)}.'})

        return rows

    def post(self, request):
        tenant = _get_active_tenant(request)

        uploaded_file = request.FILES.get('file')
        if not uploaded_file:
            return Response({'file': 'A CSV or XLSX file is required.'}, status=status.HTTP_400_BAD_REQUEST)

        if uploaded_file.size > self.MAX_FILE_SIZE:
            return Response({'file': 'File size exceeds 10MB limit.'}, status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE)

        is_dry_run = request.query_params.get('dry_run', 'false').lower() == 'true'
        mode = request.data.get('mode', 'all_or_nothing').lower()

        try:
            raw_rows = self.parse_file(uploaded_file)
        except Exception as exc:
            return Response({'file': f'Failed to parse file: {str(exc)}'}, status=status.HTTP_400_BAD_REQUEST)

        if not raw_rows:
            return Response({'file': 'Uploaded file contains no rows.'}, status=status.HTTP_400_BAD_REQUEST)

        # Subject & Topic cache
        subject_cache = {s.name.lower(): s for s in Subject.objects.filter(institution=tenant)}
        topic_cache = {(t.subject_id, t.name.lower()): t for t in Topic.objects.filter(institution=tenant)}

        row_results = []
        valid_items = []
        existing_hashes = set(
            Question.objects.filter(institution=tenant, is_deleted=False).values_list('subject_id', 'text_hash')
        )
        batch_hashes = set()

        for idx, row in enumerate(raw_rows, start=2):  # Row 2 is first data row
            row_errors = []
            row_warnings = []

            dept_raw = row.get('department', '')
            dept = normalize_department(dept_raw)

            # Subject lookup/create
            sub_name = (row.get('subject') or '').strip()
            subject_obj = None
            if not sub_name:
                row_errors.append('Subject is required.')
            else:
                sub_key = sub_name.lower()
                if sub_key in subject_cache:
                    subject_obj = subject_cache[sub_key]
                else:
                    if not is_dry_run:
                        subject_obj = Subject.objects.create(
                            institution=tenant,
                            department=dept or 'Computer Science',
                            name=sub_name,
                            code=sub_name[:10].upper().replace(' ', '_'),
                            created_by=request.user,
                        )
                        subject_cache[sub_key] = subject_obj
                    else:
                        subject_obj = Subject(id=999999, institution=tenant, department=dept or 'Computer Science', name=sub_name)

            # Topic lookup
            top_name = (row.get('topic') or '').strip()
            topic_obj = None
            if top_name and subject_obj and subject_obj.id != 999999:
                top_key = (subject_obj.id, top_name.lower())
                if top_key in topic_cache:
                    topic_obj = topic_cache[top_key]
                elif not is_dry_run:
                    topic_obj = Topic.objects.create(
                        institution=tenant,
                        subject=subject_obj,
                        name=top_name,
                        created_by=request.user,
                    )
                    topic_cache[top_key] = topic_obj

            # Question payload
            q_text = row.get('question_text') or row.get('text') or ''
            q_type = (row.get('question_type') or 'MCQ_SINGLE').strip().upper()
            diff = (row.get('difficulty') or 'MEDIUM').strip().upper()
            marks_val = row.get('marks') or '1.0'
            neg_marks_val = row.get('negative_marks') or '0.0'
            explanation = row.get('explanation') or ''
            model_answer = row.get('model_answer') or ''
            tags = [t.strip() for t in (row.get('tags') or '').split(',') if t.strip()]

            # Options
            options_list = []
            correct_raw = row.get('correct_options') or row.get('correct_option') or row.get('correct_answer') or ''
            correct_splits = [c.strip().lower() for c in str(correct_raw).split(',') if c.strip()]

            for opt_idx in range(1, 7):
                opt_key = f'option_{opt_idx}'
                if opt_key in row and row[opt_key]:
                    opt_val = str(row[opt_key]).strip()
                    if opt_val:
                        # Check if correct by index (1-based) or by text match
                        is_correct = (str(opt_idx) in correct_splits) or (opt_val.lower() in correct_splits)
                        options_list.append({'text': opt_val, 'is_correct': is_correct, 'order': opt_idx})

            payload = {
                'text': q_text,
                'department': dept or (subject_obj.department if subject_obj else ''),
                'subject': subject_obj.id if subject_obj else None,
                'topic': topic_obj.id if topic_obj else None,
                'topic_name': top_name,
                'question_type': q_type,
                'difficulty': diff,
                'marks': marks_val,
                'negative_marks': neg_marks_val,
                'explanation': explanation,
                'model_answer': model_answer,
                'tags': tags,
                'options': options_list,
            }

            try:
                cleaned_payload, warnings = validate_question_payload(
                    payload,
                    institution=tenant,
                    allow_warnings=True,
                )
                row_warnings.extend(warnings)

                # Batch duplicate check
                thash = cleaned_payload['text_hash']
                sub_id = subject_obj.id if subject_obj else None
                if (sub_id, thash) in existing_hashes or (sub_id, thash) in batch_hashes:
                    row_errors.append(f"Duplicate question text within subject '{sub_name}'.")
                else:
                    batch_hashes.add((sub_id, thash))
                    valid_items.append((cleaned_payload, subject_obj, topic_obj))

            except ValidationError as v_err:
                for k, v in v_err.detail.items():
                    msg = v[0] if isinstance(v, list) else str(v)
                    row_errors.append(f"{k}: {msg}")

            row_results.append({
                'row_number': idx,
                'question_text': q_text[:60] if q_text else '',
                'is_valid': len(row_errors) == 0,
                'errors': row_errors,
                'warnings': row_warnings,
            })

        total_rows = len(raw_rows)
        valid_count = len(valid_items)
        failed_count = total_rows - valid_count

        if is_dry_run:
            return Response({
                'dry_run': True,
                'total_rows': total_rows,
                'valid_count': valid_count,
                'failed_count': failed_count,
                'row_results': row_results,
            })

        # Real import mode check
        if mode == 'all_or_nothing' and failed_count > 0:
            return Response({
                'detail': f'Import failed: {failed_count} row(s) contained errors. No records were saved in all-or-nothing mode.',
                'total_rows': total_rows,
                'valid_count': valid_count,
                'failed_count': failed_count,
                'row_results': row_results,
            }, status=status.HTTP_400_BAD_REQUEST)

        # Commit import inside transaction
        created_questions = []
        created_options = []

        with transaction.atomic():
            for cleaned_payload, subject_obj, topic_obj in valid_items:
                opts_data = cleaned_payload.pop('options', [])
                top_name = cleaned_payload.pop('topic_name', '')
                if top_name and not cleaned_payload.get('topic_text'):
                    cleaned_payload['topic_text'] = top_name
                cleaned_payload['institution'] = tenant
                cleaned_payload['created_by'] = request.user
                cleaned_payload['subject'] = subject_obj
                cleaned_payload['topic'] = topic_obj

                if opts_data:
                    cleaned_payload['options'] = [o['text'] for o in opts_data]
                    correct_opts = [o['text'] for o in opts_data if o.get('is_correct')]
                    cleaned_payload['correct_answer'] = correct_opts[0] if len(correct_opts) == 1 else correct_opts

                q_inst = Question(**cleaned_payload)
                created_questions.append((q_inst, opts_data))

            # Batch create Questions in chunks of 100
            saved_questions = []
            for i in range(0, len(created_questions), 100):
                chunk = [item[0] for item in created_questions[i:i + 100]]
                saved_chunk = Question.objects.bulk_create(chunk)
                saved_questions.extend(saved_chunk)

            # Create Option objects
            for (q_inst, opts_data), saved_q in zip(created_questions, saved_questions):
                for opt in opts_data:
                    created_options.append(Option(
                        question=saved_q,
                        text=opt['text'],
                        is_correct=opt['is_correct'],
                        order=opt['order'],
                    ))

            for i in range(0, len(created_options), 200):
                Option.objects.bulk_create(created_options[i:i + 200])

            # Import Log
            QuestionImportLog.objects.create(
                institution=tenant,
                created_by=request.user,
                filename=uploaded_file.name or 'upload',
                file_format=uploaded_file.name.split('.')[-1].lower() if '.' in uploaded_file.name else 'csv',
                total_rows=total_rows,
                imported_count=len(saved_questions),
                duplicate_count=0,
                failed_count=failed_count,
                error_details=[r for r in row_results if not r['is_valid']][:100],
            )

        try:
            bump_tenant_cache_version(tenant.id)
        except Exception:
            pass

        return Response({
            'dry_run': False,
            'message': f'Successfully imported {len(saved_questions)} question(s).',
            'total_rows': total_rows,
            'imported_count': len(saved_questions),
            'valid_count': len(saved_questions),
            'failed_count': failed_count,
            'row_results': row_results,
        }, status=status.HTTP_201_CREATED)

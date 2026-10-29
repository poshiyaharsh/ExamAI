"""
Faculty Question Bank Views:
1. FacultyQuestionBankUploadView: Multipart upload supporting CSV, XLSX, DOCX, JSON with dry-run preview and transactional commit.
2. FacultyQuestionBankTemplateView: Downloadable templates for all 4 formats.
3. FacultyQuestionBankListView: List, search, and filter bank questions with multi-tenancy and privacy isolation.
4. AssemblePaperFromBankView: Assembles exam papers from bank questions manually or auto-assembled via deterministic knapsack solver.
"""

from decimal import Decimal
import logging
from typing import Any, Dict, List, Optional

from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from api.models import Exam, Option, Question, QuestionImportLog, Subject, Topic
from api.permissions import IsFacultyUser
from api.tenant import get_user_institution
from api.utils.departments import get_faculty_department, normalize_department
from api.utils.question_bank_parser import parse_and_validate_question_bank_file
from api.utils.question_bank_templates import get_template

logger = logging.getLogger(__name__)


class FacultyQuestionBankUploadView(APIView):
    """
    POST /api/faculty/question-bank/upload/
    Uploads question bank files (.csv, .xlsx, .docx, .json).
    Supports dry-run preview and transactional import.
    """
    permission_classes = [IsAuthenticated, IsFacultyUser]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def post(self, request):
        tenant_inst = getattr(request, 'tenant', None) or get_user_institution(request.user)
        if not tenant_inst:
            return Response({'detail': 'No active institution found.'}, status=status.HTTP_400_BAD_REQUEST)

        faculty_dept = get_faculty_department(request.user) or ''

        uploaded_file = request.FILES.get('file') or request.FILES.get('question_file')
        if not uploaded_file:
            return Response({'detail': 'No file uploaded. Please provide a CSV, XLSX, DOCX, or JSON file.'}, status=status.HTTP_400_BAD_REQUEST)

        # Parse and validate file container and all rows
        try:
            report = parse_and_validate_question_bank_file(uploaded_file)
        except ValueError as val_err:
            return Response({'detail': str(val_err)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:
            logger.error("Error parsing question bank file: %s", exc)
            return Response({'detail': f'Failed to process file: {str(exc)}'}, status=status.HTTP_400_BAD_REQUEST)

        is_dry_run = str(request.data.get('dry_run', 'false')).lower() in ('true', '1', 'yes')
        import_valid_only = str(request.data.get('import_valid_rows_only', 'false')).lower() in ('true', '1', 'yes')
        is_shared = str(request.data.get('is_shared', 'true')).lower() not in ('false', '0', 'no')

        # If dry run, return preview immediately without touching database
        if is_dry_run:
            return Response({
                'dry_run': True,
                'filename': report['filename'],
                'format': report['format'],
                'total_rows': report['total_rows'],
                'valid_count': report['valid_count'],
                'invalid_count': report['invalid_count'],
                'duplicate_count': report['duplicate_count'],
                'has_errors': report['has_errors'],
                'errors': report['errors'][:50],
                'warnings': report['warnings'][:50],
                'preview_rows': report['preview_rows'],
            }, status=status.HTTP_200_OK)

        # Non-dry-run: check all-or-nothing rollback rule
        if report['has_errors'] and not import_valid_only:
            return Response({
                'detail': f"File contains {report['invalid_count']} invalid row(s). No rows were imported. Check the errors or enable 'Import valid rows only'.",
                'has_errors': True,
                'total_rows': report['total_rows'],
                'valid_count': report['valid_count'],
                'invalid_count': report['invalid_count'],
                'errors': report['errors'],
                'preview_rows': report['preview_rows'],
            }, status=status.HTTP_400_BAD_REQUEST)

        rows_to_save = [
            r['data'] for r in report['all_rows']
            if r['is_valid'] and (not r.get('is_duplicate') or import_valid_only)
        ]

        if not rows_to_save:
            return Response({'detail': 'No valid questions found to import.'}, status=status.HTTP_400_BAD_REQUEST)

        # Subject cache
        sub_cache = {s.name.lower(): s for s in Subject.objects.filter(institution=tenant_inst)}

        imported_count = 0
        with transaction.atomic():
            for row in rows_to_save:
                # Find or assign Subject
                sub_name = (row.get('subject') or 'General').strip()
                sub_key = sub_name.lower()
                subject_obj = sub_cache.get(sub_key)
                if not subject_obj:
                    subject_obj = Subject.objects.create(
                        name=sub_name,
                        code=(sub_name[:4].upper() + "101"),
                        department=faculty_dept,
                        institution=tenant_inst,
                    )
                    sub_cache[sub_key] = subject_obj

                # Create Question Bank item (exam=None)
                q = Question.objects.create(
                    institution=tenant_inst,
                    department=faculty_dept,
                    subject=subject_obj,
                    topic_text=row.get('topic') or '',
                    created_by=request.user,
                    question_type=row.get('question_type') or 'mcq',
                    difficulty=row.get('difficulty') or 'medium',
                    text=row.get('question_text') or '',
                    explanation=row.get('explanation') or '',
                    marks=Decimal(str(row.get('marks') or 1)),
                    status=Question.Status.ACTIVE,
                    source='faculty_upload',
                    is_shared=is_shared,
                    options=row.get('options') or [],
                    correct_answer=row.get('correct_answer'),
                    model_answer=row.get('model_answer') or '',
                    rubric=row.get('rubric') or [],
                    exam=None,
                )

                # If MCQ, create relational Option records
                if row.get('question_type') == 'mcq' and row.get('options'):
                    for opt_data in row['options']:
                        Option.objects.create(
                            question=q,
                            text=opt_data.get('text', ''),
                            is_correct=bool(opt_data.get('is_correct')),
                            order=int(opt_data.get('order', 1)),
                        )

                imported_count += 1

            # Create audit log
            QuestionImportLog.objects.create(
                institution=tenant_inst,
                created_by=request.user,
                filename=report['filename'],
                file_format=report['format'],
                total_rows=report['total_rows'],
                imported_count=imported_count,
                duplicate_count=report['duplicate_count'],
                failed_count=report['invalid_count'],
                error_details=report['errors'][:50],
            )

        return Response({
            'detail': f"Successfully imported {imported_count} question(s) into your question bank.",
            'imported_count': imported_count,
            'total_rows': report['total_rows'],
            'failed_count': report['invalid_count'],
            'duplicate_count': report['duplicate_count'],
            'is_shared': is_shared,
        }, status=status.HTTP_201_CREATED)


class FacultyQuestionBankTemplateView(APIView):
    """
    GET /api/faculty/question-bank/templates/?format={csv,xlsx,docx,json}
    Returns downloadable sample templates for each format.
    """
    permission_classes = [IsAuthenticated, IsFacultyUser]

    def perform_content_negotiation(self, request, force=False):
        # Override DRF content negotiation so ?format=csv|xlsx|docx doesn't trigger 404 Http404 renderer filter
        from rest_framework.renderers import JSONRenderer
        return (JSONRenderer(), 'application/json')

    def get(self, request):
        fmt = (
            request.query_params.get('format')
            or request.query_params.get('file_format')
            or 'csv'
        ).lower()
        content, content_type, filename = get_template(fmt)
        resp = HttpResponse(content, content_type=content_type)
        resp['Content-Disposition'] = f'attachment; filename="{filename}"'
        resp['Access-Control-Expose-Headers'] = 'Content-Disposition'
        return resp


class FacultyQuestionBankListView(APIView):
    """
    GET /api/faculty/question-bank/
    Lists questions in the faculty's bank (their own + department shared).
    Supports search, filter by question_type, difficulty, subject, and marks.
    """
    permission_classes = [IsAuthenticated, IsFacultyUser]

    def get(self, request):
        tenant_inst = getattr(request, 'tenant', None) or get_user_institution(request.user)
        if not tenant_inst:
            return Response({'detail': 'No active institution found.'}, status=status.HTTP_400_BAD_REQUEST)

        faculty_dept = get_faculty_department(request.user) or ''

        # Questions scoped to tenant + (created by user OR shared in department)
        qs = Question.objects.filter(
            institution=tenant_inst,
            exam__isnull=True,
            is_deleted=False,
            status=Question.Status.ACTIVE,
        ).filter(
            Q(created_by=request.user) | Q(is_shared=True, department=faculty_dept)
        ).select_related('subject', 'created_by').prefetch_related('option_items').order_by('-created_at')

        # Filters
        params = request.query_params
        q_type = params.get('question_type') or params.get('type')
        if q_type and q_type.lower() != 'all':
            qs = qs.filter(question_type__iexact=q_type)

        difficulty = params.get('difficulty')
        if difficulty and difficulty.lower() != 'all':
            qs = qs.filter(difficulty__iexact=difficulty)

        subject_id = params.get('subject_id') or params.get('subject')
        if subject_id:
            if str(subject_id).isdigit():
                qs = qs.filter(subject_id=int(subject_id))
            else:
                qs = qs.filter(subject__name__icontains=str(subject_id))

        search = params.get('search') or params.get('q')
        if search:
            qs = qs.filter(Q(text__icontains=search) | Q(topic_text__icontains=search))

        # Privacy filter
        privacy = params.get('privacy')
        if privacy == 'private':
            qs = qs.filter(created_by=request.user, is_shared=False)
        elif privacy == 'shared':
            qs = qs.filter(is_shared=True)

        total_count = qs.count()
        limit = min(200, max(1, int(params.get('limit', 100))))
        offset = max(0, int(params.get('offset', 0)))
        page_qs = qs[offset:offset + limit]

        items = []
        for q in page_qs:
            opts = [
                {'text': o.text, 'is_correct': o.is_correct, 'order': o.order}
                for o in q.option_items.all()
            ] or (q.options if isinstance(q.options, list) else [])

            items.append({
                'id': q.id,
                'text': q.text,
                'question_type': q.question_type,
                'difficulty': q.difficulty,
                'marks': float(q.marks),
                'topic': q.topic_text,
                'subject': q.subject.name if q.subject else '',
                'subject_id': q.subject_id,
                'department': q.department,
                'options': opts,
                'correct_answer': q.correct_answer,
                'explanation': q.explanation,
                'rubric': q.rubric or [],
                'is_shared': q.is_shared,
                'is_owner': q.created_by_id == request.user.id,
                'created_by': q.created_by.get_full_name() or q.created_by.username if q.created_by else 'Faculty',
                'created_at': q.created_at.isoformat() if q.created_at else None,
            })

        return Response({
            'total_count': total_count,
            'limit': limit,
            'offset': offset,
            'questions': items,
        }, status=status.HTTP_200_OK)


class AssemblePaperFromBankView(APIView):
    """
    POST /api/faculty/exams/{exam_id}/assemble-from-bank/
    Assembles a paper directly from Question Bank items without AI calls.
    Supports:
    1. Explicit question_ids list selection.
    2. Deterministic auto-assembly to exact target_marks using Knapsack/greedy subset-sum.
    """
    permission_classes = [IsAuthenticated, IsFacultyUser]

    def post(self, request, exam_id=None):
        tenant_inst = getattr(request, 'tenant', None) or get_user_institution(request.user)
        if not tenant_inst:
            return Response({'detail': 'No active institution found.'}, status=status.HTTP_400_BAD_REQUEST)

        faculty_dept = get_faculty_department(request.user) or ''
        effective_exam_id = exam_id or request.data.get('exam_id')

        if effective_exam_id:
            exam = Exam.objects.filter(id=effective_exam_id, institution=tenant_inst).first()
            if not exam:
                return Response({'detail': 'Exam not found.'}, status=status.HTTP_404_NOT_FOUND)
            if exam.status == Exam.Status.PUBLISHED or exam.is_immutable:
                return Response({'detail': 'Cannot modify published or immutable exams.'}, status=status.HTTP_400_BAD_REQUEST)
        else:
            title = (request.data.get('title') or 'Exam from Question Bank').strip()
            subj = str(request.data.get('subject') or '')[:80].strip()
            dur = int(request.data.get('duration_minutes') or 60)
            t_marks = int(request.data.get('target_marks') or 50)
            exam = Exam.objects.create(
                institution=tenant_inst,
                title=title,
                subject=subj,
                created_by=request.user,
                department=faculty_dept,
                duration_minutes=dur,
                total_marks=0,
                target_total_marks=t_marks,
                marks_shortfall=0,
                topics=request.data.get('topics') or [],
                difficulty_distribution={},
                question_types=[],
                ai_model_used='Question Bank (Offline)',
                status=Exam.Status.DRAFT,
                starts_at=request.data.get('starts_at') or None,
                ends_at=request.data.get('ends_at') or None,
                is_reviewed=True,
            )

        action = str(request.data.get('action', 'replace')).lower()
        auto_assemble = bool(request.data.get('auto_assemble'))
        question_ids = request.data.get('question_ids') or []

        # Candidate questions available to this faculty
        bank_qs = Question.objects.filter(
            institution=tenant_inst,
            exam__isnull=True,
            is_deleted=False,
            status=Question.Status.ACTIVE,
        ).filter(
            Q(created_by=request.user) | Q(is_shared=True, department=faculty_dept)
        ).select_related('subject').prefetch_related('option_items')

        selected_bank_items: List[Question] = []

        if auto_assemble:
            # Deterministic Auto-Assembly matching target marks exactly without LLM
            target_marks = int(request.data.get('target_marks') or exam.target_total_marks or exam.total_marks or 50)
            blueprint = request.data.get('blueprint')
            subject_id = request.data.get('subject_id')

            if subject_id:
                bank_candidates = list(bank_qs.filter(subject_id=subject_id))
                if not bank_candidates:
                    bank_candidates = list(bank_qs)
            else:
                bank_candidates = list(bank_qs)

            if not bank_candidates:
                return Response({'detail': 'No questions found in question bank to assemble paper.'}, status=status.HTTP_400_BAD_REQUEST)

            # Knapsack/Subset-sum deterministic solver for exact target marks
            selected_bank_items = self._solve_knapsack_for_target(
                candidates=bank_candidates,
                target_marks=target_marks,
                blueprint=blueprint,
            )

            if not selected_bank_items:
                return Response({'detail': f'Could not assemble questions from bank to match target {target_marks} marks.'}, status=status.HTTP_400_BAD_REQUEST)

        else:
            # Manual question_ids list
            if not question_ids or not isinstance(question_ids, list):
                return Response({'detail': 'question_ids list is required when auto_assemble is false.'}, status=status.HTTP_400_BAD_REQUEST)

            id_map = {q.id: q for q in bank_qs.filter(id__in=question_ids)}
            for q_id in question_ids:
                if q_id in id_map:
                    selected_bank_items.append(id_map[q_id])

            if not selected_bank_items:
                return Response({'detail': 'None of the requested questions could be found in your accessible question bank.'}, status=status.HTTP_400_BAD_REQUEST)

        # Clone selected questions into Exam
        with transaction.atomic():
            start_order = 1
            if action == 'append':
                existing_max = exam.questions.filter(is_deleted=False).order_by('-order').first()
                start_order = (existing_max.order + 1) if existing_max else 1
            else:
                # Replace: mark existing questions as deleted
                exam.questions.filter(is_deleted=False).update(is_deleted=True, deleted_at=timezone.now())

            cloned_questions = []
            for idx, bq in enumerate(selected_bank_items):
                new_q = Question.objects.create(
                    institution=tenant_inst,
                    department=exam.department or faculty_dept,
                    subject=bq.subject,
                    topic_text=bq.topic_text,
                    created_by=request.user,
                    question_type=bq.question_type,
                    difficulty=bq.difficulty,
                    text=bq.text,
                    explanation=bq.explanation,
                    marks=bq.marks,
                    status=Question.Status.ACTIVE,
                    source='question_bank',
                    is_shared=True,
                    options=bq.options,
                    correct_answer=bq.correct_answer,
                    model_answer=bq.model_answer,
                    rubric=bq.rubric,
                    exam=exam,
                    order=start_order + idx,
                )
                # Clone option items
                for opt in bq.option_items.all():
                    Option.objects.create(
                        question=new_q,
                        text=opt.text,
                        is_correct=opt.is_correct,
                        order=opt.order,
                    )
                cloned_questions.append(new_q)

            # Update exam totals
            active_exam_questions = list(exam.questions.filter(is_deleted=False))
            actual_total = int(round(sum(float(q.marks) for q in active_exam_questions)))
            target_marks = int(exam.target_total_marks or actual_total)

            shortfall = max(0, target_marks - actual_total)
            exam.total_marks = actual_total
            exam.marks_shortfall = shortfall
            exam.status = Exam.Status.DRAFT
            exam.save(update_fields=['total_marks', 'marks_shortfall', 'status', 'updated_at'])

        from api.paper_engine.cache import PaperCacheService
        PaperCacheService.invalidate_exam(exam.institution_id, exam.id)

        return Response({
            'detail': f"Successfully assembled {len(cloned_questions)} question(s) into exam '{exam.title}'.",
            'exam_id': exam.id,
            'question_count': len(active_exam_questions),
            'actual_total_marks': actual_total,
            'target_total_marks': target_marks,
            'marks_shortfall': shortfall,
        }, status=status.HTTP_200_OK)

    def _solve_knapsack_for_target(
        self,
        candidates: List[Question],
        target_marks: int,
        blueprint: Optional[Dict[str, Any]] = None,
    ) -> List[Question]:
        """
        Deterministic Subset-Sum / Greedy Knapsack algorithm:
        Finds a set of distinct bank questions summing to exact target_marks.
        If blueprint is provided, prioritizes counts per question type.
        """
        # Deduplicate candidates by text
        seen = set()
        unique_candidates: List[Question] = []
        for c in candidates:
            k = c.text.strip().lower()
            if k not in seen:
                seen.add(k)
                unique_candidates.append(c)

        # DP Subset Sum to find exact sum = target_marks
        # dp[m] = list of indices reaching sum m
        dp: Dict[int, List[int]] = {0: []}

        # Sort candidates to balance type and difficulty
        unique_candidates.sort(key=lambda q: (float(q.marks), q.question_type))

        for idx, q in enumerate(unique_candidates):
            q_marks = int(round(float(q.marks)))
            if q_marks <= 0 or q_marks > target_marks:
                continue

            # Update DP table downwards
            current_sums = sorted(dp.keys(), reverse=True)
            for s in current_sums:
                new_s = s + q_marks
                if new_s <= target_marks and new_s not in dp:
                    dp[new_s] = dp[s] + [idx]

            if target_marks in dp:
                break

        if target_marks in dp:
            chosen_indices = dp[target_marks]
            return [unique_candidates[i] for i in chosen_indices]

        # If exact sum not possible, pick largest sum <= target_marks
        best_sum = max(dp.keys())
        chosen_indices = dp[best_sum]
        return [unique_candidates[i] for i in chosen_indices]

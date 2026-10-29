"""
Faculty Question Bank Views:
1. FacultyQuestionBankUploadView: Multipart upload supporting CSV, XLSX, DOCX, JSON with dry-run preview and transactional commit.
2. FacultyQuestionBankTemplateView: Downloadable templates for all 4 formats.
3. FacultyQuestionBankListView: List, search, and filter bank questions with multi-tenancy and privacy isolation.
4. AssemblePaperFromBankView: Assembles exam papers from bank questions manually or auto-assembled via deterministic knapsack solver.
"""

import csv
from decimal import Decimal
import io
import json
import logging
from typing import Any, Dict, List, Optional

from django.db import transaction
from django.db.models import Q, Count
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
from api.utils.options import clean_options_list
from api.utils.question_bank_templates import get_template
from api.utils.validate_paper import canonicalize_type, canonicalize_difficulty

logger = logging.getLogger(__name__)


class FacultyQuestionBankUploadView(APIView):
    """
    POST /api/faculty/question-bank/upload/
    Uploads and processes question bank files (.csv, .xlsx, .docx, .json, .pdf, .txt).
    Supports:
    1. Intelligent sniffing, header detection, column mapping, and dry-run preview.
    2. Interactive preview and inline row curation.
    3. Transactional atomic commit with selectable import modes:
       - 'ready_only': imports only 100% verified rows.
       - 'ready_and_reviewed': imports ready and faculty-reviewed rows.
       - 'all': imports all valid rows, skipping fatal errors.
    """
    permission_classes = [IsAuthenticated, IsFacultyUser]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def post(self, request):
        tenant_inst = getattr(request, 'tenant', None) or get_user_institution(request.user)
        if not tenant_inst:
            return Response({'detail': 'No active institution found.'}, status=status.HTTP_400_BAD_REQUEST)

        faculty_dept = get_faculty_department(request.user) or ''
        is_shared = str(request.data.get('is_shared', 'true')).lower() not in ('false', '0', 'no')
        import_valid_only = str(request.data.get('import_valid_rows_only', 'false')).lower() in ('true', '1', 'yes')
        has_explicit_import_mode = 'import_mode' in request.data
        import_mode = str(request.data.get('import_mode') or 'all').lower()
        mode = str(request.data.get('mode') or ('analyze' if str(request.data.get('dry_run', 'false')).lower() in ('true', '1', 'yes') else 'commit')).lower()

        # Resolve and validate target subject (required for question bank association)
        target_subject = None
        target_subject_id = request.data.get('subject_id')
        target_subject_name = request.data.get('subject_name') or request.data.get('subject')

        if target_subject_id:
            try:
                target_subject = Subject.objects.filter(
                    id=int(target_subject_id),
                    institution=tenant_inst,
                ).first()
                if not target_subject:
                    return Response({'detail': 'Selected subject not found in your institution.'}, status=status.HTTP_400_BAD_REQUEST)
                if faculty_dept and target_subject.department and target_subject.department.strip().lower() != faculty_dept.strip().lower():
                    return Response({'detail': f'Selected subject belongs to {target_subject.department}, not your department ({faculty_dept}).'}, status=status.HTTP_403_FORBIDDEN)
            except (ValueError, TypeError):
                return Response({'detail': 'Invalid subject ID.'}, status=status.HTTP_400_BAD_REQUEST)
        elif target_subject_name and str(target_subject_name).strip():
            s_name = str(target_subject_name).strip()
            target_subject = Subject.objects.filter(
                institution=tenant_inst,
                name__iexact=s_name,
            ).filter(Q(department=faculty_dept) | Q(department='')).first()
            if not target_subject:
                words = s_name.split()
                code_prefix = ''.join(w[0] for w in words)[:4].upper() if len(words) >= 2 else s_name[:4].upper()
                target_subject = Subject.objects.create(
                    institution=tenant_inst,
                    department=faculty_dept,
                    name=s_name,
                    code=f"{code_prefix}101" if code_prefix else "SUB101",
                    created_by=request.user,
                )

        # Check for direct curated questions list payload (e.g. from frontend preview editor)
        direct_questions = request.data.get('questions')
        if direct_questions and isinstance(direct_questions, list):
            if not target_subject:
                has_row_sub = any(
                    isinstance(q, dict) and (q.get('subject') or (isinstance(q.get('data'), dict) and q['data'].get('subject')))
                    for q in direct_questions
                )
                if not has_row_sub:
                    return Response({'detail': 'Subject is required. Please select or specify a subject before importing questions.'}, status=status.HTTP_400_BAD_REQUEST)

            return self._commit_direct_questions(
                request=request,
                tenant_inst=tenant_inst,
                faculty_dept=faculty_dept,
                questions=direct_questions,
                is_shared=is_shared,
                target_subject=target_subject,
            )

        uploaded_file = request.FILES.get('file') or request.FILES.get('question_file')
        if not uploaded_file:
            return Response({'detail': 'No file uploaded. Please provide a CSV, XLSX, DOCX, JSON, PDF, or TXT file.'}, status=status.HTTP_400_BAD_REQUEST)

        # Parse mapping and defaults if passed
        raw_mapping = request.data.get('custom_mapping')
        custom_mapping = None
        if raw_mapping:
            if isinstance(raw_mapping, dict):
                custom_mapping = raw_mapping
            elif isinstance(raw_mapping, str):
                try:
                    custom_mapping = json.loads(raw_mapping)
                except Exception:
                    custom_mapping = None

        sheet_name = request.data.get('sheet_name') or None
        default_marks = float(request.data.get('default_marks') or 1.0)
        default_difficulty = str(request.data.get('default_difficulty') or 'medium').lower()
        default_type = request.data.get('default_type') or None
        use_smart = str(request.data.get('smart_import', 'true')).lower() in ('true', '1', 'yes')

        # Parse and validate file container and all rows
        try:
            report = parse_and_validate_question_bank_file(
                uploaded_file=uploaded_file,
                use_smart_import=use_smart,
                custom_mapping=custom_mapping,
                default_marks=default_marks,
                default_difficulty=default_difficulty,
                default_type=default_type,
                sheet_name=sheet_name,
            )
        except ValueError as val_err:
            return Response({'detail': str(val_err)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:
            logger.error("Error parsing question bank file: %s", exc)
            return Response({'detail': f'Failed to process file: {str(exc)}'}, status=status.HTTP_400_BAD_REQUEST)

        is_dry_run = mode == 'analyze' or str(request.data.get('dry_run', 'false')).lower() in ('true', '1', 'yes')

        # If analyze / dry run, return preview immediately without touching database
        if is_dry_run:
            return Response({
                'dry_run': True,
                'filename': report['filename'],
                'format': report['format'],
                'total_rows': report['total_rows'],
                'valid_count': report['valid_count'],
                'ready_count': report.get('ready_count', report['valid_count']),
                'needs_review_count': report.get('needs_review_count', 0),
                'invalid_count': report['invalid_count'],
                'duplicate_count': report['duplicate_count'],
                'has_errors': report['has_errors'],
                'sheet_names': report.get('sheet_names', []),
                'selected_sheet': report.get('selected_sheet'),
                'columns': report.get('columns', []),
                'header_row_index': report.get('header_row_index'),
                'errors': report['errors'][:50],
                'warnings': report['warnings'][:50],
                'preview_rows': report['preview_rows'],
                'all_rows': report.get('all_rows', []),
            }, status=status.HTTP_200_OK)

        # Non-dry-run: check all-or-nothing rollback rule if strict mode
        if report['has_errors'] and not import_valid_only and (not has_explicit_import_mode or import_mode == 'all'):
            return Response({
                'detail': f"File contains {report['invalid_count']} invalid row(s). No rows were imported. Check the errors or enable 'Import valid rows only'.",
                'has_errors': True,
                'total_rows': report['total_rows'],
                'valid_count': report['valid_count'],
                'ready_count': report.get('ready_count', report['valid_count']),
                'needs_review_count': report.get('needs_review_count', 0),
                'invalid_count': report['invalid_count'],
                'errors': report['errors'],
                'preview_rows': report['preview_rows'],
            }, status=status.HTTP_400_BAD_REQUEST)

        if import_mode == 'ready_only':
            rows_to_save = [
                r['data'] for r in report['all_rows']
                if (r.get('status') == 'ready' or (r.get('is_valid') and not r.get('status')))
                and (not r.get('is_duplicate') or import_valid_only)
            ]
        elif import_mode in ('ready_and_reviewed', 'all'):
            rows_to_save = [
                r['data'] for r in report['all_rows']
                if r['is_valid'] and (not r.get('is_duplicate') or import_valid_only)
            ]
        else:
            rows_to_save = [
                r['data'] for r in report['all_rows']
                if r['is_valid'] and (not r.get('is_duplicate') or import_valid_only)
            ]

        if not rows_to_save:
            return Response({'detail': 'No eligible questions found to import with current mode.'}, status=status.HTTP_400_BAD_REQUEST)

        if not is_dry_run and not target_subject:
            has_row_sub = any(
                isinstance(r, dict) and (
                    r.get('subject') or (isinstance(r.get('data'), dict) and r['data'].get('subject'))
                )
                for r in report.get('all_rows', [])
            )
            if not has_row_sub:
                return Response({'detail': 'Subject is required. Please select a subject before importing questions.'}, status=status.HTTP_400_BAD_REQUEST)

        return self._insert_questions(
            tenant_inst=tenant_inst,
            faculty_dept=faculty_dept,
            user=request.user,
            rows_to_save=rows_to_save,
            filename=report['filename'],
            file_format=report['format'],
            total_rows=report['total_rows'],
            invalid_count=report['invalid_count'],
            duplicate_count=report['duplicate_count'],
            errors=report['errors'],
            is_shared=is_shared,
            target_subject=target_subject,
        )

    def _commit_direct_questions(self, request, tenant_inst, faculty_dept, questions: List[Any], is_shared: bool, target_subject=None):
        filename = request.data.get('filename') or 'curated_question_bank.json'
        file_format = request.data.get('format') or 'json'

        rows_to_save = []
        for q in questions:
            item = q.get('data') if isinstance(q, dict) and 'data' in q else q
            if isinstance(item, dict) and (item.get('question_text') or item.get('text')):
                rows_to_save.append(item)

        if not rows_to_save:
            return Response({'detail': 'No valid questions found in payload.'}, status=status.HTTP_400_BAD_REQUEST)

        return self._insert_questions(
            tenant_inst=tenant_inst,
            faculty_dept=faculty_dept,
            user=request.user,
            rows_to_save=rows_to_save,
            filename=filename,
            file_format=file_format,
            total_rows=len(questions),
            invalid_count=len(questions) - len(rows_to_save),
            duplicate_count=0,
            errors=[],
            is_shared=is_shared,
            target_subject=target_subject,
        )

    def _insert_questions(self, tenant_inst, faculty_dept, user, rows_to_save, filename, file_format, total_rows, invalid_count, duplicate_count, errors, is_shared, target_subject=None):
        sub_cache = {s.name.lower(): s for s in Subject.objects.filter(institution=tenant_inst)}
        imported_count = 0

        with transaction.atomic():
            for row in rows_to_save:
                if target_subject:
                    subject_obj = target_subject
                else:
                    sub_name = (row.get('subject') or '').strip()
                    if not sub_name:
                        dept_sub = Subject.objects.filter(institution=tenant_inst, department=faculty_dept).first()
                        if dept_sub:
                            subject_obj = dept_sub
                            sub_name = dept_sub.name
                        else:
                            sub_name = 'General'
                    sub_key = sub_name.lower()
                    subject_obj = sub_cache.get(sub_key)
                    if not subject_obj:
                        words = sub_name.split()
                        code_prefix = ''.join(w[0] for w in words)[:4].upper() if len(words) >= 2 else sub_name[:4].upper()
                        subject_obj = Subject.objects.create(
                            name=sub_name,
                            code=f"{code_prefix}101" if code_prefix else "SUB101",
                            department=faculty_dept,
                            institution=tenant_inst,
                            created_by=user,
                        )
                        sub_cache[sub_key] = subject_obj

                raw_options = row.get('options') or []
                cleaned_opts = clean_options_list(raw_options) if raw_options else []

                q = Question.objects.create(
                    institution=tenant_inst,
                    department=faculty_dept,
                    subject=subject_obj,
                    topic_text=row.get('topic') or '',
                    created_by=user,
                    question_type=row.get('question_type') or 'mcq',
                    difficulty=row.get('difficulty') or 'medium',
                    text=row.get('question_text') or row.get('text') or '',
                    explanation=row.get('explanation') or '',
                    marks=Decimal(str(row.get('marks') or 1)),
                    status=Question.Status.ACTIVE,
                    source='faculty_upload',
                    is_shared=is_shared,
                    options=cleaned_opts,
                    correct_answer=row.get('correct_answer'),
                    model_answer=row.get('model_answer') or '',
                    rubric=row.get('rubric') or [],
                    exam=None,
                )

                if row.get('question_type') == 'mcq' and raw_options:
                    for idx_opt, opt_data in enumerate(raw_options, start=1):
                        if isinstance(opt_data, dict):
                            opt_text = opt_data.get('text', '')
                            opt_is_correct = bool(opt_data.get('is_correct'))
                            opt_order = int(opt_data.get('order', idx_opt))
                        else:
                            opt_text = str(opt_data)
                            corr = str(row.get('correct_answer', '')).strip().lower()
                            letter = chr(64 + idx_opt).lower()
                            opt_is_correct = (corr == opt_text.strip().lower() or corr == letter)
                            opt_order = idx_opt
                        if opt_text:
                            Option.objects.create(
                                question=q,
                                text=opt_text,
                                is_correct=opt_is_correct,
                                order=opt_order,
                            )

                imported_count += 1

            QuestionImportLog.objects.create(
                institution=tenant_inst,
                created_by=user,
                filename=filename,
                file_format=file_format,
                total_rows=total_rows,
                imported_count=imported_count,
                duplicate_count=duplicate_count,
                failed_count=invalid_count,
                error_details=errors[:50],
            )

        subj_info = None
        if target_subject:
            subj_info = {
                'id': target_subject.id,
                'name': target_subject.name,
                'code': target_subject.code,
                'department': target_subject.department,
            }

        return Response({
            'detail': f"Successfully imported {imported_count} question(s) into your question bank.",
            'imported_count': imported_count,
            'total_rows': total_rows,
            'failed_count': invalid_count,
            'duplicate_count': duplicate_count,
            'is_shared': is_shared,
            'subject': subj_info,
        }, status=status.HTTP_201_CREATED)


class FacultyQuestionBankAiAssistView(APIView):
    """
    POST /api/faculty/question-bank/ai-assist/
    Runs local Ollama LLM with strict XML isolation and JSON schema
    to parse complex, unstructured question text blocks.
    """
    permission_classes = [IsAuthenticated, IsFacultyUser]

    def post(self, request):
        tenant_inst = getattr(request, 'tenant', None) or get_user_institution(request.user)
        if not tenant_inst:
            return Response({'detail': 'No active institution found.'}, status=status.HTTP_400_BAD_REQUEST)

        unstructured_text = request.data.get('text') or ''
        if not unstructured_text and 'items' in request.data:
            unstructured_text = "\n\n".join([str(item.get('question_text') or item) for item in request.data['items']])

        if not unstructured_text.strip():
            return Response({'detail': 'Please provide text or items to assist with.'}, status=status.HTTP_400_BAD_REQUEST)

        from api.utils.smart_importer.ai_extractor import extract_questions_with_ai
        extracted = extract_questions_with_ai(unstructured_text)

        return Response({
            'success': True,
            'extracted_count': len(extracted),
            'questions': extracted,
        }, status=status.HTTP_200_OK)


class FacultyQuestionBankExportReportView(APIView):
    """
    POST /api/faculty/question-bank/export-report/
    Exports a CSV report of skipped, invalid, or needs_review rows.
    """
    permission_classes = [IsAuthenticated, IsFacultyUser]

    def post(self, request):
        rows = request.data.get('rows') or []
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['Row Number', 'Status', 'Question Text', 'Question Type', 'Errors', 'Review Notes / Warnings'])

        for r in rows:
            data = r.get('data') or r
            row_num = r.get('row_number') or data.get('row_number', '')
            st = r.get('status', 'invalid')
            q_text = data.get('question_text', '')
            q_type = data.get('question_type', '')
            errs = "; ".join(r.get('errors') or [])
            warns = "; ".join(r.get('warnings') or r.get('review_notes') or [])
            writer.writerow([row_num, st, q_text, q_type, errs, warns])

        resp = HttpResponse(output.getvalue(), content_type='text/csv')
        resp['Content-Disposition'] = 'attachment; filename="question_import_error_report.csv"'
        resp['Access-Control-Expose-Headers'] = 'Content-Disposition'
        return resp


class FacultyQuestionBankExportCleanedView(APIView):
    """
    POST /api/faculty/question-bank/export-cleaned/
    Exports parsed / edited question bank items into a standard, clean XLSX workbook.
    """
    permission_classes = [IsAuthenticated, IsFacultyUser]

    def post(self, request):
        import openpyxl
        from openpyxl.styles import Alignment, Font, PatternFill

        rows = request.data.get('questions') or request.data.get('rows') or []
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Question Bank"

        headers = [
            "Question Text", "Question Type", "Marks", "Difficulty",
            "Topic", "Subject", "Option A", "Option B", "Option C", "Option D",
            "Correct Answer", "Explanation"
        ]
        ws.append(headers)

        header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
        header_fill = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
        for col_num in range(1, len(headers) + 1):
            cell = ws.cell(row=1, column=col_num)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center", vertical="center")

        for r in rows:
            data = r.get('data') or r
            opts = data.get('options_raw') or []
            if not opts and data.get('options'):
                raw_o = data.get('options')
                if isinstance(raw_o, list):
                    opts = [o.get('text', '') if isinstance(o, dict) else str(o) for o in raw_o]

            opt_a = opts[0] if len(opts) > 0 else ""
            opt_b = opts[1] if len(opts) > 1 else ""
            opt_c = opts[2] if len(opts) > 2 else ""
            opt_d = opts[3] if len(opts) > 3 else ""

            ws.append([
                data.get('question_text', ''),
                data.get('question_type', 'mcq'),
                float(data.get('marks') or 1.0),
                data.get('difficulty', 'medium'),
                data.get('topic', ''),
                data.get('subject', ''),
                opt_a,
                opt_b,
                opt_c,
                opt_d,
                data.get('correct_answer', ''),
                data.get('explanation', ''),
            ])

        for col in ws.columns:
            max_len = max(len(str(cell.value or '')) for cell in col)
            col_letter = openpyxl.utils.get_column_letter(col[0].column)
            ws.column_dimensions[col_letter].width = min(50, max(max_len + 3, 12))

        output = io.BytesIO()
        wb.save(output)
        output.seek(0)

        resp = HttpResponse(output.getvalue(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        resp['Content-Disposition'] = 'attachment; filename="cleaned_question_bank.xlsx"'
        resp['Access-Control-Expose-Headers'] = 'Content-Disposition'
        return resp


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
            if str(subject_id).lower() in ('general', 'uncategorized', 'none', 'null'):
                qs = qs.filter(subject__isnull=True)
            elif str(subject_id).isdigit():
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
                'question_text': q.text,
                'question_type': q.question_type,
                'difficulty': q.difficulty,
                'marks': float(q.marks),
                'topic': q.topic_text,
                'subject': q.subject.name if q.subject else '',
                'subject_name': q.subject.name if q.subject else '',
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


class FacultyQuestionBankBanksView(APIView):
    """
    GET /api/faculty/question-bank/banks/
    Returns accessible question banks / subjects with active question counts.
    """
    permission_classes = [IsAuthenticated, IsFacultyUser]

    def get(self, request):
        tenant_inst = getattr(request, 'tenant', None) or get_user_institution(request.user)
        if not tenant_inst:
            return Response({'detail': 'No active institution found.'}, status=status.HTTP_400_BAD_REQUEST)

        faculty_dept = get_faculty_department(request.user) or ''

        base_qs = Question.objects.filter(
            institution=tenant_inst,
            exam__isnull=True,
            is_deleted=False,
            status=Question.Status.ACTIVE,
        ).filter(
            Q(created_by=request.user) | Q(is_shared=True, department=faculty_dept)
        )

        subj_filter = request.query_params.get('subject_id') or request.query_params.get('subject')
        if subj_filter:
            if str(subj_filter).isdigit():
                base_qs = base_qs.filter(subject_id=int(subj_filter))
            else:
                base_qs = base_qs.filter(subject__name__iexact=str(subj_filter).strip())

        subject_counts = base_qs.exclude(subject__isnull=True).values(
            'subject_id', 'subject__name', 'subject__code', 'subject__department'
        ).annotate(count=Count('id')).order_by('subject__name')

        banks = []
        for item in subject_counts:
            banks.append({
                'id': item['subject_id'],
                'name': item['subject__name'],
                'code': item['subject__code'] or '',
                'department': item['subject__department'] or faculty_dept,
                'question_count': item['count'],
            })

        uncategorized_count = base_qs.filter(subject__isnull=True).count()
        if uncategorized_count > 0:
            banks.append({
                'id': 'general',
                'name': 'General / Unassigned Bank',
                'code': 'GEN',
                'department': faculty_dept,
                'question_count': uncategorized_count,
            })

        return Response({'banks': banks, 'total_banks': len(banks)}, status=status.HTTP_200_OK)


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
            update_fields = []
            if 'title' in request.data:
                raw_title = request.data.get('title')
                if not raw_title or not str(raw_title).strip():
                    return Response({'detail': 'Exam title is required and cannot be empty or whitespace.'}, status=status.HTTP_400_BAD_REQUEST)
                title = str(raw_title).strip()
                if len(title) > 255:
                    return Response({'detail': 'Exam title cannot exceed 255 characters.'}, status=status.HTTP_400_BAD_REQUEST)
                exam.title = title
                update_fields.append('title')

            if 'duration_minutes' in request.data:
                try:
                    dur_val = int(request.data.get('duration_minutes'))
                    if dur_val < 1 or dur_val > 600:
                        return Response({'detail': 'Duration must be between 1 and 600 minutes.'}, status=status.HTTP_400_BAD_REQUEST)
                    exam.duration_minutes = dur_val
                    update_fields.append('duration_minutes')
                except (ValueError, TypeError):
                    return Response({'detail': 'Invalid duration minutes value.'}, status=status.HTTP_400_BAD_REQUEST)

            if 'subject' in request.data:
                subj_val = str(request.data.get('subject') or '')[:80].strip()
                if subj_val:
                    exam.subject = subj_val
                    update_fields.append('subject')

            if update_fields:
                exam.save(update_fields=update_fields)
        else:
            raw_title = request.data.get('title')
            if not raw_title or not str(raw_title).strip():
                return Response({'detail': 'Exam title is required and cannot be empty or whitespace.'}, status=status.HTTP_400_BAD_REQUEST)
            title = str(raw_title).strip()
            if len(title) > 255:
                return Response({'detail': 'Exam title cannot exceed 255 characters.'}, status=status.HTTP_400_BAD_REQUEST)

            subj = str(request.data.get('subject') or '')[:80].strip()
            try:
                dur = int(request.data.get('duration_minutes') or 60)
                if dur < 1 or dur > 600:
                    return Response({'detail': 'Duration must be between 1 and 600 minutes.'}, status=status.HTTP_400_BAD_REQUEST)
            except (ValueError, TypeError):
                return Response({'detail': 'Invalid duration minutes value.'}, status=status.HTTP_400_BAD_REQUEST)
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

        # Filter candidates by subject_id if specified in payload or query params
        cand_subject_id = request.data.get('subject_id') or request.query_params.get('subject_id')
        if cand_subject_id:
            if str(cand_subject_id).lower() in ('general', 'uncategorized', 'none', 'null'):
                bank_qs = bank_qs.filter(subject__isnull=True)
            elif str(cand_subject_id).isdigit():
                bank_qs = bank_qs.filter(subject_id=int(cand_subject_id))
            else:
                bank_qs = bank_qs.filter(subject__name__icontains=str(cand_subject_id))

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
                    options=clean_options_list(bq.options) if bq.options else [],
                    correct_answer=bq.correct_answer,
                    model_answer=bq.model_answer,
                    rubric=bq.rubric,
                    exam=exam,
                    order=start_order + idx,
                )
                # Clone option items
                if bq.option_items.exists():
                    for opt in bq.option_items.all():
                        Option.objects.create(
                            question=new_q,
                            text=opt.text,
                            is_correct=opt.is_correct,
                            order=opt.order,
                        )
                elif new_q.options and isinstance(new_q.options, list):
                    for o_idx, opt_str in enumerate(new_q.options):
                        is_corr = False
                        if bq.correct_answer:
                            if str(bq.correct_answer).strip().lower() == str(opt_str).strip().lower():
                                is_corr = True
                            elif str(bq.correct_answer).strip().upper() == chr(65 + o_idx):
                                is_corr = True
                        Option.objects.create(
                            question=new_q,
                            text=str(opt_str),
                            is_correct=is_corr,
                            order=o_idx + 1,
                        )
                cloned_questions.append(new_q)

            # Update exam totals and metadata
            active_exam_questions = list(exam.questions.filter(is_deleted=False))
            actual_total = int(round(sum(float(q.marks) for q in active_exam_questions)))
            target_marks = int(exam.target_total_marks or actual_total)

            shortfall = max(0, target_marks - actual_total)
            exam.total_marks = actual_total
            exam.marks_shortfall = shortfall

            types_set = sorted(list({canonicalize_type(q.question_type) for q in active_exam_questions if q.question_type}))
            topics_set = sorted(list({q.topic_text for q in active_exam_questions if q.topic_text}))
            diff_counts = {}
            for q in active_exam_questions:
                d = canonicalize_difficulty(q.difficulty)
                diff_counts[d] = diff_counts.get(d, 0) + 1
            total_q = len(active_exam_questions) or 1
            diff_dist = {d: round((count / total_q) * 100) for d, count in diff_counts.items()}

            exam.question_types = types_set
            exam.topics = topics_set
            exam.difficulty_distribution = diff_dist
            exam.status = Exam.Status.DRAFT
            exam.save(update_fields=['total_marks', 'marks_shortfall', 'status', 'question_types', 'topics', 'difficulty_distribution', 'updated_at'])

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

        # Handle blueprint type counts if provided
        chosen_by_blueprint: List[Question] = []
        remaining_candidates = unique_candidates

        if blueprint and isinstance(blueprint, dict):
            # Parse requested counts per type
            desired_counts: Dict[str, int] = {}
            for raw_type, spec in blueprint.items():
                c_type = canonicalize_type(raw_type)
                cnt = 0
                if isinstance(spec, int):
                    cnt = spec
                elif isinstance(spec, dict):
                    cnt = int(spec.get('count') or 0)
                elif isinstance(spec, str) and spec.isdigit():
                    cnt = int(spec)
                if cnt > 0:
                    desired_counts[c_type] = cnt

            if desired_counts:
                # Group candidates by canonical type
                by_type: Dict[str, List[Question]] = {}
                for c in unique_candidates:
                    ct = canonicalize_type(c.question_type)
                    by_type.setdefault(ct, []).append(c)

                blueprint_chosen_ids = set()
                for c_type, count in desired_counts.items():
                    type_pool = by_type.get(c_type, [])
                    picked = type_pool[:count]
                    for p in picked:
                        chosen_by_blueprint.append(p)
                        blueprint_chosen_ids.add(p.id)

                remaining_candidates = [c for c in unique_candidates if c.id not in blueprint_chosen_ids]

        blueprint_sum = int(round(sum(float(q.marks) for q in chosen_by_blueprint)))

        # If blueprint alone was requested and reached or exceeded target_marks, or target_marks was reached:
        if chosen_by_blueprint and (blueprint_sum >= target_marks or target_marks <= 0):
            return chosen_by_blueprint

        # Otherwise, need to fill shortfall with knapsack on remaining candidates
        remaining_target = max(0, target_marks - blueprint_sum)
        if remaining_target == 0:
            return chosen_by_blueprint

        # DP Subset Sum to find exact sum = remaining_target
        dp: Dict[int, List[int]] = {0: []}
        remaining_candidates.sort(key=lambda q: (float(q.marks), q.question_type))

        for idx, q in enumerate(remaining_candidates):
            q_marks = int(round(float(q.marks)))
            if q_marks <= 0 or q_marks > remaining_target:
                continue

            current_sums = sorted(dp.keys(), reverse=True)
            for s in current_sums:
                new_s = s + q_marks
                if new_s <= remaining_target and new_s not in dp:
                    dp[new_s] = dp[s] + [idx]

            if remaining_target in dp:
                break

        if remaining_target in dp:
            chosen_indices = dp[remaining_target]
            return chosen_by_blueprint + [remaining_candidates[i] for i in chosen_indices]

        # If exact sum not possible, pick largest sum <= remaining_target
        if dp:
            best_sum = max(dp.keys())
            chosen_indices = dp[best_sum]
            return chosen_by_blueprint + [remaining_candidates[i] for i in chosen_indices]

        return chosen_by_blueprint

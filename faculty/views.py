import logging
import json
import os
import tempfile
import urllib.error
import urllib.request
from io import BytesIO

from django.conf import settings
from django.core.files.base import ContentFile
from django.db import OperationalError, ProgrammingError
from django.db import transaction
from django.http import HttpResponse
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import AllowAny
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from api.permissions import IsFacultyUser

from admins.models import AdminInstitution
from .models import FacultyProfile, Paper, PaperQuestion, SyllabusUpload
from .serializers import (
    GeneratePaperSerializer,
    FacultyLoginSerializer,
    PaperHistorySerializer,
    PaperSerializer,
    FacultyProfileDepartmentUpdateSerializer,
    FacultyProfileSerializer,
    FacultySignupSerializer,
    SyllabusUploadSerializer,
)


from backend.ai_config import ProviderError, get_ai_provider_manager

logger = logging.getLogger(__name__)

QUESTION_TYPE_LABELS = {
    'MCQ': 'MCQ',
    'Subjective': 'Subjective',
    'True/False': 'True/False',
    'Fill in the Blanks': 'Fill in the Blanks',
}


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
    refresh['role'] = 'faculty'
    access = refresh.access_token
    access['role'] = 'faculty'
    return {
        'refresh': str(refresh),
        'access': str(access),
    }


def _get_or_create_faculty_profile(user):
    profile, _ = FacultyProfile.objects.get_or_create(user=user)
    if not profile.institution:
        default_institution = AdminInstitution.objects.order_by('id').first()
        if default_institution:
            profile.institution = default_institution
            profile.save(update_fields=['institution'])
    profile.ensure_employee_id()
    return profile


def _faculty_or_error(request):
    profile = _get_or_create_faculty_profile(request.user)
    if not profile.institution:
        return None, Response(
            {'status': 'error', 'message': 'Faculty institution not found.'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    return profile, None


def _validate_syllabus_file(uploaded_file):
    filename = uploaded_file.name or ''
    extension = os.path.splitext(filename)[1].lower()
    if extension not in ('.pdf', '.docx'):
        return 'Only PDF and DOCX syllabus files are supported.'
    if uploaded_file.size > 10 * 1024 * 1024:
        return 'Syllabus file must be 10MB or smaller.'
    return None


def _extract_pdf_text(path):
    try:
        import pdfplumber
        with pdfplumber.open(path) as pdf:
            return '\n'.join(page.extract_text() or '' for page in pdf.pages).strip()
    except ImportError:
        try:
            import fitz
            document = fitz.open(path)
            return '\n'.join(page.get_text() for page in document).strip()
        except ImportError as exc:
            raise ValueError('PDF extraction requires pdfplumber or PyMuPDF to be installed.') from exc


def _extract_docx_text(path):
    try:
        from docx import Document
    except ImportError as exc:
        raise ValueError('DOCX extraction requires python-docx to be installed.') from exc
    document = Document(path)
    return '\n'.join(paragraph.text for paragraph in document.paragraphs).strip()


def _extract_syllabus_text(uploaded_file):
    extension = os.path.splitext(uploaded_file.name or '')[1].lower()
    suffix = extension if extension in ('.pdf', '.docx') else ''
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
        for chunk in uploaded_file.chunks():
            temp_file.write(chunk)
        temp_path = temp_file.name

    try:
        if extension == '.pdf':
            text = _extract_pdf_text(temp_path)
        elif extension == '.docx':
            text = _extract_docx_text(temp_path)
        else:
            raise ValueError('Only PDF and DOCX syllabus files are supported.')
    finally:
        try:
            os.unlink(temp_path)
        except OSError:
            pass

    if not text:
        raise ValueError('No readable text was found in the syllabus file.')
    return text


def _json_request(url, payload, headers, timeout=60):
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode('utf-8'),
        headers={**headers, 'Content-Type': 'application/json'},
        method='POST',
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode('utf-8', errors='ignore')
        raise RuntimeError(detail or f'Provider returned HTTP {exc.code}.') from exc
    except urllib.error.URLError as exc:
        raise TimeoutError('AI provider request timed out or could not be reached.') from exc


def _paper_prompt(validated_data):
    return (
        'Generate an exam paper using ONLY the syllabus text below. '
        'Return JSON only with keys: title, duration, total_marks, model, questions. '
        'Each question must include type, difficulty, marks, question, options, answer. '
        'MCQ questions must include options. Do not include markdown.\n\n'
        f"Title: {validated_data['title']}\n"
        f"Duration: {validated_data['duration']}\n"
        f"Total marks: {validated_data['total_marks']}\n"
        f"Model: {validated_data['model']}\n"
        f"Topics: {', '.join(validated_data['topics'])}\n"
        f"Question types: {', '.join(validated_data['question_types'])}\n"
        f"Difficulty distribution: {validated_data['difficulty_distribution']}\n\n"
        f"Syllabus:\n{validated_data['syllabus_upload'].extracted_text[:18000]}"
    )


def _generate_with_provider(validated_data):
    manager = get_ai_provider_manager()
    return manager.generate(validated_data['model'], _paper_prompt(validated_data))


def _validate_generated_paper(generated, validated_data):
    questions = generated.get('questions')
    if not isinstance(questions, list) or not questions:
        raise ValueError('AI provider did not return any questions.')

    allowed_types = set(validated_data['question_types'])
    allowed_difficulties = {'Easy', 'Medium', 'Hard'}
    total_marks = 0
    marks_by_difficulty = {'Easy': 0, 'Medium': 0, 'Hard': 0}
    normalized_questions = []
    for index, question in enumerate(questions, start=1):
        question_type = question.get('type')
        difficulty = question.get('difficulty')
        marks = int(question.get('marks') or 0)
        text = str(question.get('question') or '').strip()
        if question_type not in allowed_types:
            raise ValueError('AI generated a question type that was not selected.')
        if difficulty not in allowed_difficulties:
            raise ValueError('AI generated an invalid difficulty level.')
        if marks <= 0 or not text:
            raise ValueError('AI generated an invalid question.')
        total_marks += marks
        marks_by_difficulty[difficulty] += marks
        normalized_questions.append({
            'question_number': index,
            'type': question_type,
            'difficulty': difficulty,
            'marks': marks,
            'question': text,
            'options': question.get('options') if isinstance(question.get('options'), list) else [],
            'answer': str(question.get('answer') or '').strip(),
        })

    if total_marks != validated_data['total_marks']:
        raise ValueError('Generated question marks do not equal Total Marks.')

    expected_marks = {}
    allocated_marks = 0
    difficulties = ['Easy', 'Medium', 'Hard']
    for difficulty in difficulties[:-1]:
        marks = round(validated_data['total_marks'] * validated_data['difficulty_distribution'][difficulty] / 100)
        expected_marks[difficulty] = marks
        allocated_marks += marks
    expected_marks[difficulties[-1]] = validated_data['total_marks'] - allocated_marks

    if marks_by_difficulty != expected_marks:
        raise ValueError('Generated question difficulty marks do not match the requested distribution.')

    generated['questions'] = normalized_questions
    generated['title'] = validated_data['title']
    generated['duration'] = validated_data['duration']
    generated['total_marks'] = validated_data['total_marks']
    generated['model'] = validated_data['model']
    return generated


def _save_generated_paper(faculty, validated_data, generated):
    upload = validated_data['syllabus_upload']
    with transaction.atomic():
        upload.original_file.open('rb')
        paper = Paper.objects.create(
            faculty=faculty,
            institution=faculty.institution,
            title=validated_data['title'],
            syllabus_filename=upload.original_filename,
            extracted_syllabus_text=upload.extracted_text,
            ai_model=validated_data['model'],
            topics=validated_data['topics'],
            question_types=validated_data['question_types'],
            difficulty_distribution=validated_data['difficulty_distribution'],
            duration=validated_data['duration'],
            total_marks=validated_data['total_marks'],
            generated_questions=generated['questions'],
        )
        paper.syllabus_file.save(upload.original_filename, ContentFile(upload.original_file.read()), save=True)

        PaperQuestion.objects.bulk_create([
            PaperQuestion(
                paper=paper,
                question_number=question['question_number'],
                question_type=question['type'],
                difficulty=question['difficulty'],
                marks=question['marks'],
                question=question['question'],
                options=question['options'],
                answer=question['answer'],
            )
            for question in generated['questions']
        ])
    return paper


def _paper_for_faculty(faculty, paper_id):
    return (
        Paper.objects.select_related('institution', 'faculty')
        .prefetch_related('questions')
        .filter(id=paper_id, institution=faculty.institution)
        .first()
    )


def _render_paper_text(paper):
    sections = {'MCQ': [], 'Subjective': [], 'True/False': [], 'Fill in the Blanks': []}
    for question in paper.questions.all():
        sections.setdefault(question.question_type, []).append(question)
    lines = [
        paper.institution.institution_name,
        paper.title,
        f'Duration: {paper.duration} minutes',
        f'Total Marks: {paper.total_marks}',
        '',
        'Instructions: Answer all questions. Marks are shown beside each question.',
        '',
    ]
    section_name = 'A'
    question_number = 1
    for question_type, questions in sections.items():
        if not questions:
            continue
        lines.append(f'Section {section_name} - {question_type}')
        for question in questions:
            lines.append(f'{question_number}. {question.question} [{question.marks} marks]')
            for option in question.options:
                lines.append(f'   - {option}')
            question_number += 1
        lines.append('')
        section_name = chr(ord(section_name) + 1)
    return '\n'.join(lines)


def _export_pdf(paper):
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
    except ImportError as exc:
        raise ValueError('PDF export requires reportlab to be installed.') from exc

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    y = height - 50
    for line in _render_paper_text(paper).splitlines():
        if y < 50:
            pdf.showPage()
            y = height - 50
        pdf.drawString(50, y, line[:110])
        y -= 18
    pdf.save()
    buffer.seek(0)
    return buffer.getvalue(), 'application/pdf', f'{paper.title}.pdf'


def _export_docx(paper):
    try:
        from docx import Document
    except ImportError as exc:
        raise ValueError('DOCX export requires python-docx to be installed.') from exc
    document = Document()
    document.add_heading(paper.institution.institution_name, level=1)
    document.add_heading(paper.title, level=2)
    document.add_paragraph(f'Duration: {paper.duration} minutes')
    document.add_paragraph(f'Total Marks: {paper.total_marks}')
    document.add_heading('Instructions', level=2)
    document.add_paragraph('Answer all questions. Marks are shown beside each question.')
    for line in _render_paper_text(paper).splitlines()[7:]:
        if line.startswith('Section '):
            document.add_heading(line, level=2)
        elif line:
            document.add_paragraph(line)
    buffer = BytesIO()
    document.save(buffer)
    buffer.seek(0)
    return (
        buffer.getvalue(),
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        f'{paper.title}.docx',
    )


class FacultySignupAPIView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = FacultySignupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        return Response(
            {
                'status': 'success',
                'message': 'Faculty account created successfully.',
                'tokens': _build_token_payload(user),
                'user': {
                    'id': user.id,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'email': user.email,
                    'role': 'faculty',
                },
            },
            status=status.HTTP_201_CREATED,
        )


class FacultyLoginAPIView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = FacultyLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']

        return Response(
            {
                'status': 'success',
                'message': 'Faculty login successful.',
                'tokens': _build_token_payload(user),
                'user': {
                    'id': user.id,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'email': user.email,
                    'role': 'faculty',
                },
            },
            status=status.HTTP_200_OK,
        )


class FacultyProfileAPIView(APIView):
    permission_classes = [IsAuthenticated, IsFacultyUser]

    def get(self, request):
        try:
            profile = _get_or_create_faculty_profile(request.user)
        except (OperationalError, ProgrammingError) as exc:
            return _error_response(
                exc,
                f'Faculty profile fetch database error for user_id={request.user.id}',
                'Database schema issue detected. Please run migrations.',
            )
        except Exception as exc:
            return _error_response(
                exc,
                f'Unexpected faculty profile fetch error for user_id={request.user.id}',
                'Unable to fetch faculty profile.',
            )
        serializer = FacultyProfileSerializer(profile)
        return Response(
            {
                'status': 'success',
                'message': 'Faculty profile fetched successfully.',
                'data': serializer.data,
            },
            status=status.HTTP_200_OK,
        )

    def put(self, request):
        try:
            profile = _get_or_create_faculty_profile(request.user)
        except (OperationalError, ProgrammingError) as exc:
            return _error_response(
                exc,
                f'Faculty profile update database error for user_id={request.user.id}',
                'Database schema issue detected. Please run migrations.',
            )
        except Exception as exc:
            return _error_response(
                exc,
                f'Unexpected faculty profile update error for user_id={request.user.id}',
                'Unable to update faculty profile.',
            )

        serializer = FacultyProfileDepartmentUpdateSerializer(profile, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        response_serializer = FacultyProfileSerializer(profile)
        return Response(
            {
                'status': 'success',
                'message': 'Department updated successfully.',
                'data': response_serializer.data,
            },
            status=status.HTTP_200_OK,
        )


class SyllabusUploadAPIView(APIView):
    permission_classes = [IsAuthenticated, IsFacultyUser]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        faculty, error_response = _faculty_or_error(request)
        if error_response:
            return error_response

        uploaded_file = request.FILES.get('file')
        if not uploaded_file:
            return Response(
                {'status': 'error', 'message': 'Syllabus file is required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        validation_error = _validate_syllabus_file(uploaded_file)
        if validation_error:
            return Response({'status': 'error', 'message': validation_error}, status=status.HTTP_400_BAD_REQUEST)

        try:
            extracted_text = _extract_syllabus_text(uploaded_file)
            uploaded_file.seek(0)
            syllabus = SyllabusUpload.objects.create(
                faculty=faculty,
                institution=faculty.institution,
                original_file=uploaded_file,
                original_filename=uploaded_file.name,
                content_type=getattr(uploaded_file, 'content_type', '') or '',
                extracted_text=extracted_text,
            )
        except ValueError as exc:
            return Response({'status': 'error', 'message': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:
            return _error_response(exc, 'Unexpected syllabus upload error', 'Unable to upload syllabus.')

        return Response(
            {
                'status': 'success',
                'message': 'Syllabus uploaded successfully.',
                'data': SyllabusUploadSerializer(syllabus).data,
            },
            status=status.HTTP_201_CREATED,
        )


class GeneratePaperAPIView(APIView):
    permission_classes = [IsAuthenticated, IsFacultyUser]

    def post(self, request):
        faculty, error_response = _faculty_or_error(request)
        if error_response:
            return error_response

        serializer = GeneratePaperSerializer(data=request.data, context={'faculty': faculty})
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        upload = validated_data['syllabus_upload']
        if not upload.original_file or not upload.original_file.name or not upload.original_file.storage.exists(upload.original_file.name):
            return Response(
                {
                    'success': False,
                    'provider': None,
                    'error_code': 'syllabus_not_found',
                    'message': 'The uploaded syllabus file is no longer available. Please upload it again.',
                    'fallback_attempted': False,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            generated, provider, provider_model, failures = _generate_with_provider(validated_data)
            generated = _validate_generated_paper(generated, validated_data)
            paper = _save_generated_paper(faculty, validated_data, generated)
        except ProviderError as exc:
            if exc.provider == 'all':
                try:
                    failures = json.loads(exc.reason)
                except json.JSONDecodeError:
                    failures = []
                final_failure = failures[-1] if failures else {}
                return Response(
                    {
                        'success': False,
                        'status': 'error',
                        'provider': final_failure.get('provider'),
                        'error_code': 'all_providers_failed',
                        'message': 'No configured AI provider could generate the paper. Review the provider report below.',
                        'fallback_attempted': len(failures) > 1,
                        'failures': failures,
                    },
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )
            return Response(
                {
                    'success': False,
                    'status': 'error',
                    'provider': exc.provider,
                    'error_code': exc.code,
                    'message': exc.reason,
                    'fallback_attempted': False,
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except ValueError as exc:
            return Response({'success': False, 'status': 'error', 'message': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except (BrokenPipeError, ConnectionAbortedError):
            logger.info('Client disconnected while generating a paper; generation response was discarded.')
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Exception as exc:
            return _error_response(exc, 'Unexpected paper generation error', 'Unable to generate paper.')

        response_data = {
            'success': True,
            'status': 'success',
            'message': 'Paper generated successfully.',
            'provider': provider,
            'model': provider_model,
            'paper': PaperSerializer(paper).data,
            'data': PaperSerializer(paper).data,
        }
        if failures:
            response_data['warning'] = 'The selected provider was unavailable; a fallback provider generated this paper.'

        return Response(
            response_data,
            status=status.HTTP_201_CREATED,
        )


class PaperHistoryAPIView(APIView):
    permission_classes = [IsAuthenticated, IsFacultyUser]

    def get(self, request):
        faculty, error_response = _faculty_or_error(request)
        if error_response:
            return error_response

        papers = Paper.objects.filter(institution=faculty.institution, faculty=faculty).prefetch_related('questions')
        return Response(
            {
                'status': 'success',
                'message': 'Paper history fetched successfully.',
                'data': PaperHistorySerializer(papers, many=True).data,
            },
            status=status.HTTP_200_OK,
        )


class PaperDetailAPIView(APIView):
    permission_classes = [IsAuthenticated, IsFacultyUser]

    def get(self, request, paper_id):
        faculty, error_response = _faculty_or_error(request)
        if error_response:
            return error_response

        paper = _paper_for_faculty(faculty, paper_id)
        if not paper:
            return Response({'status': 'error', 'message': 'Paper not found.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(
            {
                'status': 'success',
                'message': 'Paper fetched successfully.',
                'data': PaperSerializer(paper).data,
            },
            status=status.HTTP_200_OK,
        )

    def delete(self, request, paper_id):
        faculty, error_response = _faculty_or_error(request)
        if error_response:
            return error_response

        paper = _paper_for_faculty(faculty, paper_id)
        if not paper:
            return Response({'status': 'error', 'message': 'Paper not found.'}, status=status.HTTP_404_NOT_FOUND)
        paper.delete()
        return Response(
            {'status': 'success', 'message': 'Paper deleted successfully.'},
            status=status.HTTP_200_OK,
        )


class PaperExportAPIView(APIView):
    permission_classes = [IsAuthenticated, IsFacultyUser]

    def get(self, request, paper_id):
        faculty, error_response = _faculty_or_error(request)
        if error_response:
            return error_response

        paper = _paper_for_faculty(faculty, paper_id)
        if not paper:
            return Response({'status': 'error', 'message': 'Paper not found.'}, status=status.HTTP_404_NOT_FOUND)

        export_format = (request.query_params.get('format') or 'pdf').lower()
        try:
            if export_format == 'docx':
                content, content_type, filename = _export_docx(paper)
            elif export_format == 'pdf':
                content, content_type, filename = _export_pdf(paper)
            else:
                return Response({'status': 'error', 'message': 'Export format must be pdf or docx.'}, status=status.HTTP_400_BAD_REQUEST)
        except ValueError as exc:
            return Response({'status': 'error', 'message': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:
            return _error_response(exc, 'Unexpected paper export error', 'Unable to export paper.')

        response = HttpResponse(content, content_type=content_type)
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response

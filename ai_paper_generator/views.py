"""

API and Template Views for AI Paper Generator Module.

"""

import io

import os

import tempfile

import json

import logging

import hashlib

import re

import threading

import time

from typing import Dict, Any, List, Optional



from django.http import HttpResponse, JsonResponse

from django.shortcuts import get_object_or_404, render

from django.views import View

import datetime

from django.utils import timezone

from rest_framework import status

from rest_framework.parsers import MultiPartParser, FormParser, JSONParser

from rest_framework.permissions import IsAuthenticated

from rest_framework.response import Response

from rest_framework.views import APIView

from rest_framework.authentication import SessionAuthentication

from api.tenant import TenantJWTAuthentication



from api.permissions import IsFacultyUser

from faculty.models import FacultyProfile

from .model_manager import ModelManager

from .ollama_client import OllamaClient

from .models import GenerationJob, GenerationLog, PaperDraft

from .serializers import (

    StartGenerationSerializer,

    GenerationJobSerializer,

    GenerationLogSerializer,

    EditQuestionSerializer,

)

from .generators.blueprint import (

    build_blueprint,

    auto_distribute_blueprint,

    calculate_allocated_marks,

)

from .generators.pipeline import launch_generation_job

from .generators.repair import generate_and_validate_slot_with_repair
from .generators.rubric_builder import build_rubric

from .generators.deduplicator import QuestionDeduplicator

from .generators.paper_builder import assemble_and_order_paper

from .rag.loader import load_document

from .rag.chunker import chunk_document_pages

from .rag.vector_store import LocalVectorStore

from .rag.retriever import RAGRetriever

from .logging_setup import log_event



logger = logging.getLogger(__name__)





def _get_faculty(request):

    """Resolves faculty profile from request user with fallback for dev/demo."""

    user = getattr(request, 'user', None)

    if user and user.is_authenticated:

        if hasattr(user, 'faculty_profile'):

            return user.faculty_profile

        fp = FacultyProfile.objects.filter(user=user).first()

        if fp:

            return fp

        if getattr(user, 'is_superuser', False):

            return FacultyProfile.objects.first()

    # Development / standalone UI fallback

    from django.conf import settings

    if settings.DEBUG or getattr(settings, 'TESTING', False):

        demo = FacultyProfile.objects.filter(user__username='faculty_demo').first()

        if demo:

            return demo

        return FacultyProfile.objects.first()

    return None







# ---------------------------------------------------------

# AI Model Registry & Caching (10s TTL)

# ---------------------------------------------------------

_MODELS_CACHE_LOCK = threading.Lock()

_MODELS_CACHE: Dict[str, Any] = {}

_MODELS_CACHE_TTL: float = 10.0





class AIPaperGeneratorBaseAPIView(APIView):

    authentication_classes = [TenantJWTAuthentication, SessionAuthentication]



class FacultyAiModelsAPIView(AIPaperGeneratorBaseAPIView):

    """

    Returns dynamically installed Ollama models with metadata (labels, sizes, roles, recommended flag)

    scoped for faculty exams and paper generation.

    Cached for 10 seconds to eliminate frontend request spam.

    Returns HTTP 200 with ollama_online=False if Ollama is not running.

    """

    permission_classes = [IsAuthenticated]



    def get(self, request):

        now = time.time()

        force_refresh = request.query_params.get('refresh', '').lower() in ('true', '1')



        with _MODELS_CACHE_LOCK:

            if not force_refresh and 'data' in _MODELS_CACHE:

                cached_time = _MODELS_CACHE.get('time', 0)

                if now - cached_time < _MODELS_CACHE_TTL:

                    return Response(_MODELS_CACHE['data'], status=status.HTTP_200_OK)



        mgr = ModelManager()

        data = mgr.get_available_models_metadata()



        if not data.get('ollama_online'):

            log_event(

                'MODEL_ERROR',

                'GET /api/faculty/ai-models/ - Ollama is offline or unreachable.',

                level=logging.WARNING

            )



        with _MODELS_CACHE_LOCK:

            _MODELS_CACHE['data'] = data

            _MODELS_CACHE['time'] = now



        return Response(data, status=status.HTTP_200_OK)





# ---------------------------------------------------------

# Deterministic Syllabus Hierarchy & Capacity Extraction

# ---------------------------------------------------------

UNIT_PATTERNS = [

    re.compile(r'(?i)^(?:unit|chapter|module|section|part)\s*[-:]?\s*([0-9ivxlcdm]+)[\s\-:.]*([^\n\r]+)'),

    re.compile(r'(?i)^([0-9ivxlcdm]+)\.\s+([A-Z][^\n\r]+)'),

]

DOMAIN_KEYWORDS = {

    'Computer Science': {'algorithm', 'database', 'sql', 'python', 'java', 'compiler', 'network', 'operating system', 'data structure', 'software', 'programming', 'binary', 'tree', 'graph', 'hash'},

    'Electronics': {'circuit', 'transistor', 'semiconductor', 'diode', 'amplifier', 'signal', 'modulation', 'analog', 'digital', 'microcontroller', 'vlsi', 'frequency'},

    'Mechanical': {'thermodynamics', 'fluid', 'mechanics', 'kinematics', 'heat transfer', 'combustion', 'gear', 'turbine', 'stress', 'strain', 'material science'},

    'Civil': {'concrete', 'surveying', 'geotechnical', 'soil', 'structural', 'hydrology', 'beam', 'foundation', 'pavement'},

    'Mathematics': {'calculus', 'differential', 'integral', 'linear algebra', 'probability', 'matrix', 'eigenvalue', 'vector space', 'fourier'},

    'Management': {'marketing', 'accounting', 'finance', 'organizational behavior', 'human resource', 'supply chain', 'strategy'},

}





def parse_syllabus_units_and_topics(full_text: str, pages_data: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:

    """

    Extracts units and topics deterministically without LLM.

    Identifies Unit / Chapter / Module headings or page-level sections.

    """

    lines = [line.strip() for line in full_text.splitlines() if line.strip()]

    raw_units = []

    current_unit = None



    for line in lines:

        matched = False

        for pat in UNIT_PATTERNS:

            m = pat.match(line)

            if m:

                heading_title = line[:120].strip()

                if current_unit:

                    raw_units.append(current_unit)

                current_unit = {

                    'title': heading_title,

                    'lines': [],

                }

                matched = True

                break



        if not matched:

            if current_unit is not None:

                current_unit['lines'].append(line)



    if current_unit:

        raw_units.append(current_unit)



    # If no explicit headings found, use pages or paragraph chunks

    if not raw_units:

        if pages_data and len(pages_data) > 1:

            for idx, p in enumerate(pages_data, start=1):

                raw_units.append({

                    'title': f'Section {idx}',

                    'lines': [p.get('text', '')],

                })

        else:

            paragraphs = [p.strip() for p in full_text.split('\n\n') if len(p.strip()) > 30]

            if len(paragraphs) > 1:

                for idx, para in enumerate(paragraphs[:15], start=1):

                    first_line = para.splitlines()[0][:80].strip()

                    raw_units.append({

                        'title': first_line or f'Topic {idx}',

                        'lines': [para],

                    })

            else:

                raw_units.append({

                    'title': 'Core Syllabus',

                    'lines': [full_text],

                })



    structured_units = []

    for idx, u in enumerate(raw_units[:15], start=1):

        unit_text = '\n'.join(u['lines'])

        subtopics = []

        for l in u['lines']:

            cleaned = l.lstrip('-*•123456789. ').strip()

            if 3 < len(cleaned) < 100 and not any(pat.match(l) for pat in UNIT_PATTERNS):

                subtopics.append(cleaned)



        structured_units.append({

            'index': idx,

            'title': u['title'],

            'topics': subtopics[:10] if subtopics else [u['title']],

            'char_count': len(unit_text),

            'summary': unit_text[:150] + ('...' if len(unit_text) > 150 else ''),

        })



    return structured_units





def estimate_syllabus_capacity(char_count: int, num_units: int, text: str = '') -> Dict[str, Any]:

    safe_chars = max(0, char_count)

    word_count = len(text.split()) if text else (safe_chars // 6)

    estimated_q = max(5, min(80, safe_chars // 250))

    estimated_marks = max(10, min(100, int(estimated_q * 2.5)))

    is_limited = safe_chars < 2000 or word_count < 300

    return {

        'char_count': safe_chars,

        'unit_count': max(1, num_units),

        'recommended_max_questions': estimated_q,

        'recommended_max_marks': estimated_marks,

        'is_limited': is_limited,

    }





def detect_domains(text: str):

    low = text.lower()

    words = set(re.findall(r'\b[a-z]{3,}\b', low))

    detected = []

    for domain, kws in DOMAIN_KEYWORDS.items():

        if len(words & kws) >= 3:

            detected.append(domain)

    has_multiple = len(detected) >= 2

    return has_multiple, detected





class FacultySyllabusParseAPIView(APIView):

    """

    Parses uploaded syllabus file (PDF, DOCX, TXT, PPTX) or text snippet.

    Extracts units, topics, character count, domain detection, and paper capacity.

    """

    permission_classes = [IsAuthenticated]

    parser_classes = [MultiPartParser, FormParser, JSONParser]



    def post(self, request):

        syllabus_file = request.FILES.get('syllabus') or request.FILES.get('file')

        raw_text = request.data.get('syllabus_text') or (

            request.data.get('syllabus') if isinstance(request.data.get('syllabus'), str) else None

        )



        if not syllabus_file and not (raw_text and str(raw_text).strip()):

            return Response(

                {'error': 'No syllabus file or text provided.', 'detail': 'No syllabus file or text provided.'},

                status=status.HTTP_400_BAD_REQUEST

            )



        fn = getattr(syllabus_file, 'name', 'direct_input')

        full_text = ''

        pages_data = []



        if syllabus_file:

            suffix = os.path.splitext(fn)[1].lower()

            tmp_path = None

            try:

                with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:

                    for chunk in syllabus_file.chunks():

                        tmp.write(chunk)

                    tmp_path = tmp.name



                pages_data = load_document(tmp_path)

                full_text = '\n\n'.join(p.get('text', '') for p in pages_data).strip()

            except Exception as exc:

                log_event('RAG', f"Failed to load syllabus document '{fn}': {str(exc)}", level=logging.ERROR)

                return Response(

                    {'error': f"Failed to parse syllabus file '{fn}': {str(exc)}", 'detail': str(exc)},

                    status=status.HTTP_400_BAD_REQUEST

                )

            finally:

                if tmp_path and os.path.exists(tmp_path):

                    try:

                        os.unlink(tmp_path)

                    except Exception:

                        pass

        else:

            full_text = str(raw_text).strip()



        if not full_text:

            return Response(

                {'error': 'The uploaded syllabus contains no readable text.', 'detail': 'The uploaded syllabus contains no readable text.'},

                status=status.HTTP_400_BAD_REQUEST

            )



        try:

            units = parse_syllabus_units_and_topics(full_text, pages_data=pages_data)

            has_multiple, detected_domains = detect_domains(full_text)

            capacity = estimate_syllabus_capacity(len(full_text), len(units), text=full_text)

            topics = [u['title'] for u in units] if units else [line.strip() for line in full_text.splitlines() if line.strip()][:15]

            file_hash = hashlib.sha256(full_text.encode('utf-8')).hexdigest()



            log_event('RAG', f"Successfully parsed syllabus '{fn}': {len(full_text)} chars, {len(units)} units detected.")



            return Response({

                'filename': fn,

                'file_hash': file_hash,

                'char_count': len(full_text),

                'units': units,

                'has_multiple_subjects': has_multiple,

                'detected_domains': detected_domains,

                'topics': topics,

                'detected_topics_count': len(topics),

                'capacity': capacity,

                'preview': full_text[:600] + ('...' if len(full_text) > 600 else ''),

            }, status=status.HTTP_200_OK)

        except Exception as exc:

            log_event('RAG', f"Syllabus analysis failed: {str(exc)}", level=logging.ERROR)

            return Response(

                {'error': f"Failed to process syllabus: {str(exc)}", 'detail': str(exc)},

                status=status.HTTP_500_INTERNAL_SERVER_ERROR

            )





class ActiveJobView(AIPaperGeneratorBaseAPIView):

    """

    Returns active running job for current user.

    Compatible with /api/papers/generations/active/ and /api/ai-generator/jobs/active/.

    Automatically marks stale jobs (>15 minutes old) as failed.

    """

    permission_classes = [IsAuthenticated]



    def get(self, request):

        faculty = _get_faculty(request)



        # Auto-fail stale jobs left hanging for more than 15 minutes

        cutoff = timezone.now() - datetime.timedelta(minutes=15)

        stale_filter = {

            'created_at__lt': cutoff,

            'status__in': ['pending', 'running', 'in_progress', 'generating']

        }

        if faculty:

            stale_qs = GenerationJob.objects.filter(faculty=faculty, **stale_filter)

        elif request.user.is_authenticated:

            stale_qs = GenerationJob.objects.filter(faculty__user=request.user, **stale_filter)

        else:

            stale_qs = GenerationJob.objects.none()



        stale_qs.update(

            status=GenerationJob.Status.FAILED,

            error_message="Generation job timed out (exceeded 15 minutes limit).",

            completed_at=timezone.now()

        )



        job = None

        if faculty:

            job = GenerationJob.objects.filter(

                faculty=faculty,

                status__in=['pending', 'running', 'in_progress', 'generating']

            ).order_by('-created_at').first()

        elif request.user.is_authenticated:

            job = GenerationJob.objects.filter(

                faculty__user=request.user,

                status__in=['pending', 'running', 'in_progress', 'generating']

            ).order_by('-created_at').first()



        return Response({

            'active_job': GenerationJobSerializer(job).data if job else None

        }, status=status.HTTP_200_OK)





class JobsListView(AIPaperGeneratorBaseAPIView):

    """

    Returns recent generation jobs for current user.

    Compatible with /api/papers/generations/ and /api/ai-generator/jobs/.

    """

    permission_classes = [IsAuthenticated]



    def get(self, request):

        faculty = _get_faculty(request)

        qs = GenerationJob.objects.none()

        if faculty:

            qs = GenerationJob.objects.filter(faculty=faculty).order_by('-created_at')[:20]

        elif request.user.is_authenticated:

            qs = GenerationJob.objects.filter(faculty__user=request.user).order_by('-created_at')[:20]



        return Response({

            'results': GenerationJobSerializer(qs, many=True).data,

            'count': qs.count()

        }, status=status.HTTP_200_OK)





class CancelJobView(AIPaperGeneratorBaseAPIView):

    """

    Cancels a running generation job.

    """

    permission_classes = [IsAuthenticated]



    def post(self, request, job_id):

        job = get_object_or_404(GenerationJob, id=job_id)

        if job.status in ['pending', 'running', 'in_progress', 'generating']:

            job.status = GenerationJob.Status.CANCELLED

            job.error_message = 'Cancelled by user.'

            job.completed_at = timezone.now()

            job.save(update_fields=['status', 'error_message', 'completed_at'])

            log_event('GENERATION', f"Job {job_id} cancelled by user.", job_id=job.id)

        return Response({

            'detail': 'Job cancelled.',

            'job': GenerationJobSerializer(job).data

        }, status=status.HTTP_200_OK)



class CheckModelsView(AIPaperGeneratorBaseAPIView):

    """

    Checks active Ollama server and lists installed models with dynamic role assignments.

    """

    permission_classes = [IsAuthenticated]



    def get(self, request):

        mgr = ModelManager()

        roles = mgr.detect_and_assign_roles()

        return Response(roles, status=status.HTTP_200_OK)





class UploadMaterialsView(AIPaperGeneratorBaseAPIView):

    """

    Uploads syllabus, notes, textbook or question bank files (.pdf, .docx, .txt, .pptx).

    Extracts text and preview information.

    """

    permission_classes = [IsAuthenticated, IsFacultyUser]

    parser_classes = [MultiPartParser, FormParser]



    def post(self, request):

        faculty = _get_faculty(request)

        if not faculty:

            return Response({'error': 'Faculty profile required.'}, status=status.HTTP_403_FORBIDDEN)



        uploaded_files = request.FILES.getlist('files')

        if not uploaded_files and 'file' in request.FILES:

            uploaded_files = [request.FILES['file']]



        if not uploaded_files:

            return Response({'error': 'No file uploaded.'}, status=status.HTTP_400_BAD_REQUEST)



        materials_summary = []

        raw_texts = []





        for f in uploaded_files:

            # Save temporarily to extract text

            suffix = os.path.splitext(f.name)[1].lower()

            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:

                for chunk in f.chunks():

                    tmp.write(chunk)

                tmp_path = tmp.name



            try:

                pages = load_document(tmp_path)

                chunks = chunk_document_pages(pages, default_topic='General Syllabus')

                full_text = " ".join(p['text'] for p in pages)

                raw_texts.append(full_text)

                materials_summary.append({

                    'filename': f.name,

                    'pages_count': len(pages),

                    'chunks_count': len(chunks),

                    'char_count': len(full_text),

                    'tmp_path': tmp_path,

                })

            except Exception as exc:

                if os.path.exists(tmp_path):

                    os.unlink(tmp_path)

                return Response(

                    {'error': f"Failed to parse '{f.name}': {str(exc)}"},

                    status=status.HTTP_400_BAD_REQUEST

                )



        return Response({

            'status': 'success',

            'materials': materials_summary,

            'total_files': len(materials_summary),

            'message': f"Successfully parsed {len(materials_summary)} document(s)."

        }, status=status.HTTP_200_OK)





class SuggestBlueprintView(APIView):

    """

    Auto-distribute calculator.

    Suggests an exact valid blueprint where sum(count * marks) == total_marks.

    """

    permission_classes = [IsAuthenticated]



    def post(self, request):

        total_marks = int(request.data.get('total_marks', 50))

        enabled_types = request.data.get('enabled_types')

        if total_marks <= 0:

            return Response({'error': 'Total marks must be > 0'}, status=status.HTTP_400_BAD_REQUEST)



        sections = auto_distribute_blueprint(total_marks, enabled_types=enabled_types)

        allocated = sum(s['count'] * s['marks_per_question'] for s in sections)



        return Response({

            'total_marks': total_marks,

            'allocated_marks': allocated,

            'matches_exactly': (allocated == total_marks),

            'sections': sections,

        }, status=status.HTTP_200_OK)





class StartGenerationView(AIPaperGeneratorBaseAPIView):

    """

    Validates the faculty form and starts background AI paper generation.

    """

    permission_classes = [IsAuthenticated, IsFacultyUser]

    parser_classes = [JSONParser, MultiPartParser, FormParser]



    def post(self, request):

        faculty = _get_faculty(request)

        if not faculty:

            return Response({'error': 'Faculty profile not found.'}, status=status.HTTP_403_FORBIDDEN)



        # 1. Deserialize and validate form data

        serializer = StartGenerationSerializer(data=request.data)

        if not serializer.is_valid():

            errors = serializer.errors

            print("[AI_GENERATOR_VALIDATION_ERROR]", errors)



            # Build safe representation of payload for logs

            safe_payload = {}

            try:

                raw_dict = request.data.dict() if hasattr(request.data, 'dict') else dict(request.data)

                for k, v in raw_dict.items():

                    safe_payload[k] = str(v)[:400]

            except Exception:

                safe_payload = {'raw': 'Unable to serialize request payload'}



            # Safe summary of validation errors (field names and error messages, no file contents)

            safe_error_summary = {

                field: [str(e) for e in errs] if isinstance(errs, list) else str(errs)

                for field, errs in errors.items()

            }

            log_event(

                job_id=None,

                level='ERROR',

                category='GENERATION',

                message=f"Validation failed for AI paper generation: {safe_error_summary}",

                details={'fields': safe_error_summary}

            )

            log_event(

                job_id=None,

                level='ERROR',

                category='VALIDATION',

                message=f"Validation failed for AI paper generation: {list(errors.keys())}",

                details={'errors': safe_error_summary}

            )



            # Format user-friendly primary error message

            first_msg = "Form validation failed. Please check the entered fields."

            for field, field_errs in errors.items():

                if isinstance(field_errs, list) and len(field_errs) > 0:

                    first_msg = f"{field}: {field_errs[0]}"

                    break

                elif isinstance(field_errs, dict):

                    nested_msg = next((f"{k}: {v[0] if isinstance(v, list) else v}" for k, v in field_errs.items()), str(field_errs))

                    first_msg = f"{field}: {nested_msg}"

                    break



            return Response({

                'error': first_msg,

                'fields': errors

            }, status=status.HTTP_400_BAD_REQUEST)



        vdata = serializer.validated_data

        total_marks = vdata['total_marks']

        sections = vdata['sections']

        topics = vdata['topics']

        diff_dist = vdata.get('difficulty_distribution') or {'Easy': 30, 'Medium': 50, 'Hard': 20}



        # 2. Build blueprint and assert exact equality

        try:

            blueprint = build_blueprint(

                total_marks=total_marks,

                sections=sections,

                topics=topics,

                difficulty_distribution=diff_dist

            )

        except ValueError as exc:

            err_msg = str(exc)

            log_event(

                job_id=None,

                level='ERROR',

                category='VALIDATION',

                message=f"Blueprint calculation error: {err_msg}",

                details={'total_marks': total_marks, 'sections': sections}

            )

            return Response({

                'error': err_msg,

                'fields': {'total_marks': [err_msg]}

            }, status=status.HTTP_400_BAD_REQUEST)



        allocated_marks = calculate_allocated_marks(blueprint)

        if allocated_marks != total_marks:

            err_msg = f"Allocated marks ({allocated_marks}) do not match total marks ({total_marks})."

            log_event(

                job_id=None,

                level='ERROR',

                category='VALIDATION',

                message=err_msg,

                details={'allocated_marks': allocated_marks, 'total_marks': total_marks}

            )

            return Response({

                'error': err_msg,

                'fields': {'total_marks': [err_msg]}

            }, status=status.HTTP_400_BAD_REQUEST)



        # 3. Validate uploaded document files

        uploaded_files = request.FILES.getlist('files')

        if not uploaded_files and 'file' in request.FILES:

            uploaded_files = [request.FILES['file']]



        allowed_exts = {'.pdf', '.docx', '.txt', '.pptx'}

        for f in uploaded_files:

            ext = os.path.splitext(f.name)[1].lower()

            if ext not in allowed_exts:

                err_msg = f"Unsupported file type '{ext}' for file '{f.name}'. Allowed formats: PDF, DOCX, TXT, PPTX."

                log_event(

                    job_id=None,

                    level='ERROR',

                    category='VALIDATION',

                    message=err_msg,

                    details={'file': f.name, 'extension': ext}

                )

                return Response({

                    'error': err_msg,

                    'fields': {'files': [err_msg]}

                }, status=status.HTTP_400_BAD_REQUEST)

            if f.size == 0:

                err_msg = f"Uploaded file '{f.name}' is empty (0 bytes)."

                return Response({

                    'error': err_msg,

                    'fields': {'files': [err_msg]}

                }, status=status.HTTP_400_BAD_REQUEST)



        # 4. Model assignments
        mgr = ModelManager()
        role_info = mgr.detect_and_assign_roles()
        model_roles_input = vdata.get('model_roles') or {}
        if isinstance(model_roles_input, dict):
            assigned_roles = {**role_info, **model_roles_input}
        else:
            assigned_roles = role_info

        gen_model = vdata.get('model_generator') or assigned_roles.get('mcq_generator') or assigned_roles.get('generator')
        val_model = vdata.get('model_validator') or assigned_roles.get('validator')
        fb_model = vdata.get('model_fallback') or assigned_roles.get('fallback')
        assigned_roles['generator'] = gen_model
        assigned_roles['validator'] = val_model
        assigned_roles['fallback'] = fb_model

        # 5. Create GenerationJob record
        job = GenerationJob.objects.create(
            faculty=faculty,
            institution=faculty.institution,
            title=vdata['title'],
            subject=vdata['subject'],
            class_semester=vdata.get('class_semester', ''),
            exam_type=vdata.get('exam_type', 'Final Examination'),
            total_marks=total_marks,
            allocated_marks=allocated_marks,
            duration=vdata.get('duration', 60),
            blueprint=blueprint,
            status=GenerationJob.Status.PENDING,
            progress_percent=2,
            progress_message="Job queued for processing",
            model_assignments=assigned_roles,
        )

        # Handle uploaded document files for RAG index

        uploaded_files = request.FILES.getlist('files')

        if not uploaded_files and 'file' in request.FILES:

            uploaded_files = [request.FILES['file']]





        vector_store = LocalVectorStore(job.id)

        all_chunks = []



        if uploaded_files:

            for f in uploaded_files:

                suffix = os.path.splitext(f.name)[1].lower()

                with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:

                    for chunk in f.chunks():

                        tmp.write(chunk)

                    tmp_path = tmp.name



                try:

                    pages = load_document(tmp_path)

                    chunks = chunk_document_pages(pages, default_topic=topics[0] if topics else 'Syllabus')

                    all_chunks.extend(chunks)

                finally:

                    if os.path.exists(tmp_path):

                        os.unlink(tmp_path)

        else:

            # If no files uploaded, create synthetic topic chunks so RAG still operates

            for t in topics:

                all_chunks.append({

                    'chunk_id': f"topic_{t}",

                    'text': f"Curriculum Unit: {t}. Core principles, fundamental concepts, and applied analytical methodologies of {vdata['subject']}.",

                    'source': 'curriculum_topics',

                    'page': 1,

                    'topic': t,

                    'token_count': 50,

                })



        vector_store.add_chunks(all_chunks)

        job.rag_sources = [{'count': len(all_chunks), 'files': [f.name for f in uploaded_files]}]

        job.save(update_fields=['rag_sources'])



        # Launch background worker

        launch_generation_job(job.id)



        return Response({

            'status': 'started',

            'job_id': job.id,

            'message': f"Generation job #{job.id} started successfully in background.",

            'total_slots': len(blueprint),

            'total_marks': total_marks,

        }, status=status.HTTP_202_ACCEPTED)





class JobStatusView(AIPaperGeneratorBaseAPIView):

    """

    Polling endpoint returning live generation progress.

    """

    permission_classes = [IsAuthenticated, IsFacultyUser]



    def get(self, request, job_id):

        faculty = _get_faculty(request)

        job = get_object_or_404(GenerationJob, id=job_id, institution=faculty.institution)

        return Response({

            'id': job.id,

            'status': job.status,

            'progress_percent': job.progress_percent,

            'progress_message': job.progress_message,

            'current_slot_index': job.current_slot_index,

            'total_slots': len(job.blueprint),

            'total_marks': job.total_marks,

            'questions_generated_count': len(job.generated_questions or []),

            'error_message': job.error_message,

            'saved_paper_id': job.saved_paper_id,

            'saved_exam_id': job.saved_exam_id,

        }, status=status.HTTP_200_OK)





class JobDetailView(AIPaperGeneratorBaseAPIView):

    """

    Returns full details of a completed job for the Review Screen.

    """

    permission_classes = [IsAuthenticated, IsFacultyUser]



    def get(self, request, job_id):

        faculty = _get_faculty(request)

        job = get_object_or_404(GenerationJob, id=job_id, institution=faculty.institution)

        return Response(GenerationJobSerializer(job).data, status=status.HTTP_200_OK)





class EditQuestionView(AIPaperGeneratorBaseAPIView):

    """

    Updates a single question during review.

    """

    permission_classes = [IsAuthenticated, IsFacultyUser]



    def put(self, request, job_id, question_number):

        faculty = _get_faculty(request)

        job = get_object_or_404(GenerationJob, id=job_id, institution=faculty.institution)



        serializer = EditQuestionSerializer(data=request.data)

        serializer.is_valid(raise_exception=True)

        vdata = serializer.validated_data



        questions = list(job.generated_questions or [])

        idx = next((i for i, q in enumerate(questions) if q.get('question_number') == question_number), None)

        if idx is None:

            return Response({'error': 'Question not found.'}, status=status.HTTP_404_NOT_FOUND)



        questions[idx]['question'] = vdata['question']

        questions[idx]['answer'] = vdata['answer']

        questions[idx]['marks'] = vdata['marks']

        if vdata.get('options'):

            questions[idx]['options'] = vdata['options']

        if questions[idx].get('type') in ('Short Answer', 'Long Answer'):
            rub = build_rubric(
                questions[idx]['type'],
                vdata['marks'],
                vdata['answer'],
                question_text=vdata['question'],
                model_answer=vdata['answer']
            )
            questions[idx]['rubric'] = rub
            questions[idx]['key_points'] = rub[0]['key_points']



        # Re-verify total marks

        new_total = sum(q['marks'] for q in questions)

        job.generated_questions = questions

        job.allocated_marks = new_total

        job.save(update_fields=['generated_questions', 'allocated_marks'])



        return Response({

            'status': 'updated',

            'question': questions[idx],

            'new_total_marks': new_total,

        }, status=status.HTTP_200_OK)



    def delete(self, request, job_id, question_number):

        faculty = _get_faculty(request)

        job = get_object_or_404(GenerationJob, id=job_id, institution=faculty.institution)



        questions = list(job.generated_questions or [])

        questions = [q for q in questions if q.get('question_number') != question_number]



        # Re-number

        for i, q in enumerate(questions, start=1):

            q['question_number'] = i



        new_total = sum(q['marks'] for q in questions)

        job.generated_questions = questions

        job.allocated_marks = new_total

        job.save(update_fields=['generated_questions', 'allocated_marks'])



        return Response({

            'status': 'deleted',

            'remaining_count': len(questions),

            'new_total_marks': new_total,

        }, status=status.HTTP_200_OK)





class RegenerateSingleSlotView(AIPaperGeneratorBaseAPIView):

    """

    Regenerates a single question with 1-click replacement.

    """

    permission_classes = [IsAuthenticated, IsFacultyUser]



    def post(self, request, job_id, question_number):

        faculty = _get_faculty(request)

        job = get_object_or_404(GenerationJob, id=job_id, institution=faculty.institution)



        questions = list(job.generated_questions or [])

        target_q = next((q for q in questions if q.get('question_number') == question_number), None)

        if not target_q:

            return Response({'error': 'Question not found.'}, status=status.HTTP_404_NOT_FOUND)



        # Slot config

        slot = {

            'slot_index': question_number,

            'type': target_q['type'],

            'marks': target_q['marks'],

            'difficulty': target_q.get('difficulty', 'Medium'),

            'topic': target_q.get('topic', 'General'),

        }



        client = OllamaClient()

        vector_store = LocalVectorStore(job.id)

        retriever = RAGRetriever(vector_store, job.id)

        deduplicator = QuestionDeduplicator()



        # Seed deduplicator with other questions

        for q in questions:

            if q.get('question_number') != question_number:

                deduplicator.add(q)



        model_gen = job.model_assignments.get('generator') or 'qwen2.5:3b-instruct'

        model_val = job.model_assignments.get('validator') or 'llama3.2:3b'

        model_fb = job.model_assignments.get('fallback') or 'phi3:mini'



        new_q = generate_and_validate_slot_with_repair(

            slot=slot,

            subject=job.subject,

            client=client,

            retriever=retriever,

            deduplicator=deduplicator,

            model_generator=model_gen,

            model_validator=model_val,

            model_fallback=model_fb,

            job_id=job.id,

        )

        new_q['question_number'] = question_number

        if new_q.get('type') in ('Short Answer', 'Long Answer'):
            rub = new_q.get('rubric')
            if not rub or not isinstance(rub, list) or not rub[0].get('key_points'):
                rub = build_rubric(new_q['type'], new_q['marks'], new_q.get('key_points') or new_q.get('answer'), question_text=new_q.get('question', ''), model_answer=new_q.get('answer', ''))
            new_q['rubric'] = rub
            new_q['key_points'] = rub[0]['key_points']



        # Replace in list

        for i, q in enumerate(questions):

            if q.get('question_number') == question_number:

                questions[i] = new_q

                break



        job.generated_questions = questions

        job.save(update_fields=['generated_questions'])



        return Response({

            'status': 'regenerated',

            'question': new_q,

        }, status=status.HTTP_200_OK)





class GenerationLogsView(AIPaperGeneratorBaseAPIView):

    """

    Returns audit logs.

    Scoped: Faculty sees own logs; Admin/SuperAdmin sees all logs.

    Supports download=true query param.

    """

    permission_classes = [IsAuthenticated]



    def get(self, request):

        user = request.user

        qs = GenerationLog.objects.all()



        # Faculty isolation

        faculty = getattr(user, 'faculty_profile', None)

        if faculty:

            qs = qs.filter(faculty=faculty)



        # Filter by job_id

        job_id = request.query_params.get('job_id')

        if job_id:

            qs = qs.filter(job_id=job_id)



        # Filter by level

        level = request.query_params.get('level')

        if level:

            qs = qs.filter(level=level.upper())



        # Filter by date

        date_str = request.query_params.get('date')

        if date_str:

            qs = qs.filter(created_at__date=date_str)



        if request.query_params.get('download') == 'true':

            # Export as JSON file

            logs_data = GenerationLogSerializer(qs[:1000], many=True).data

            response = HttpResponse(

                json.dumps(logs_data, indent=2),

                content_type='application/json'

            )

            response['Content-Disposition'] = 'attachment; filename="generation_logs.json"'

            return response



        logs_data = GenerationLogSerializer(qs[:200], many=True).data

        return Response({

            'count': qs.count(),

            'logs': logs_data,

        }, status=status.HTTP_200_OK)





class ExportPaperView(AIPaperGeneratorBaseAPIView):

    """

    Exports generated paper to PDF or DOCX.

    """

    permission_classes = [IsAuthenticated, IsFacultyUser]



    def get(self, request, job_id):

        faculty = _get_faculty(request)

        job = get_object_or_404(GenerationJob, id=job_id, institution=faculty.institution)

        path = request.path.lower()

        if 'pdf' in path:

            export_format = 'pdf'

        elif 'docx' in path:

            export_format = 'docx'

        else:

            export_format = request.query_params.get('format', 'pdf').lower()



        questions = job.generated_questions or []

        include_answers = request.query_params.get('include_answers', 'true').lower() in ('true', '1')



        paper_payload = {

            'title': job.title,

            'subject': job.subject,

            'duration': job.duration,

            'total_marks': job.total_marks,

            'questions': questions,

        }



        if export_format == 'pdf':

            from .exporters.pdf import export_paper_to_pdf

            pdf_bytes = export_paper_to_pdf(paper_payload, include_answers=include_answers)

            response = HttpResponse(pdf_bytes, content_type='application/pdf')

            response['Content-Disposition'] = f'attachment; filename="{job.title}.pdf"'

            return response

        else:

            from .exporters.docx import export_paper_to_docx

            docx_bytes = export_paper_to_docx(paper_payload, include_answers=include_answers)

            response = HttpResponse(

                docx_bytes,

                content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document'

            )

            response['Content-Disposition'] = f'attachment; filename="{job.title}.docx"'

            return response



        if export_format == 'old_legacy':

            from reportlab.lib.pagesizes import letter

            from reportlab.pdfgen import canvas



            buffer = io.BytesIO()

            p = canvas.Canvas(buffer, pagesize=letter)

            y = 750



            p.setFont("Helvetica-Bold", 16)

            p.drawString(50, y, f"{job.title} - {job.subject}")

            y -= 25

            p.setFont("Helvetica", 11)

            p.drawString(50, y, f"Total Marks: {job.total_marks} | Duration: {job.duration} mins")

            y -= 30



            for q in questions:

                if y < 80:

                    p.showPage()

                    y = 750

                p.setFont("Helvetica-Bold", 11)

                p.drawString(50, y, f"Q{q.get('question_number')}. [{q.get('type')}] ({q.get('marks')} Marks)")

                y -= 18

                p.setFont("Helvetica", 10)

                # Word wrap question text roughly

                q_text = q.get('question', '')

                p.drawString(60, y, q_text[:85])

                y -= 16

                if len(q_text) > 85:

                    p.drawString(60, y, q_text[85:170])

                    y -= 16



                if q.get('options'):

                    for opt in q['options']:

                        p.drawString(70, y, f"- {opt}")

                        y -= 14



                if include_answers and q.get('answer'):

                    p.setFont("Helvetica-Oblique", 9)

                    p.drawString(60, y, f"Answer: {q.get('answer')[:85]}")

                    y -= 16



                y -= 10



            p.save()

            buffer.seek(0)

            response = HttpResponse(buffer.getvalue(), content_type='application/pdf')

            response['Content-Disposition'] = f'attachment; filename="{job.title}.pdf"'

            return response



        else:  # DOCX export

            import docx

            doc = docx.Document()

            doc.add_heading(job.title, 0)

            p_sub = doc.add_paragraph()

            p_sub.add_run(f"Subject: {job.subject} | Duration: {job.duration} mins | Total Marks: {job.total_marks}").bold = True

            doc.add_paragraph("Instructions: Answer all questions carefully.")

            doc.add_paragraph("-" * 60)



            for q in questions:

                p = doc.add_paragraph()

                p.add_run(f"Q{q.get('question_number')}. ").bold = True

                p.add_run(f"({q.get('marks')} Marks) [{q.get('type')}] - {q.get('question')}")



                if q.get('options'):

                    for opt in q['options']:

                        doc.add_paragraph(f"  • {opt}")



                if include_answers and q.get('answer'):

                    ans_p = doc.add_paragraph()

                    ans_p.add_run("Model Answer / Key: ").italic = True

                    ans_p.add_run(str(q.get('answer')))



                doc.add_paragraph()



            buffer = io.BytesIO()

            doc.save(buffer)

            buffer.seek(0)

            response = HttpResponse(

                buffer.getvalue(),

                content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document'

            )

            response['Content-Disposition'] = f'attachment; filename="{job.title}.docx"'

            return response





class AIPaperGeneratorTemplateView(View):

    """

    Server-rendered fallback template view with JWT and session bootstrap.

    """

    def get(self, request):

        faculty = _get_faculty(request)

        auth_token = ""

        user_json = "{}"

        if faculty and faculty.user:

            try:

                from rest_framework_simplejwt.tokens import RefreshToken

                refresh = RefreshToken.for_user(faculty.user)

                if faculty.institution:

                    refresh['institution_id'] = faculty.institution.id

                refresh['role'] = 'faculty'

                auth_token = str(refresh.access_token)

                user_json = json.dumps({

                    'id': faculty.user.id,

                    'username': faculty.user.username,

                    'email': faculty.user.email,

                    'name': faculty.user.get_full_name() or faculty.user.username,

                    'institution': faculty.institution.institution_name if faculty.institution else ""

                })

            except Exception as e:

                logger.warning(f"Could not mint JWT for template: {e}")



        from django.middleware.csrf import get_token

        csrf_token = get_token(request)



        return render(request, 'ai_paper_generator/index.html', {

            'title': 'AI Paper Generator',

            'auth_token': auth_token,

            'csrf_token': csrf_token,

            'user_json': user_json,

            'timestamp': int(time.time()),

        })





class PaperDraftView(AIPaperGeneratorBaseAPIView):

    """

    Manages autosaved faculty wizard drafts across devices and sessions.

    GET: Returns saved draft data or None.

    POST: Upserts the saved draft data.

    DELETE: Clears the saved draft.

    """

    permission_classes = [IsAuthenticated]



    def get(self, request):

        faculty = _get_faculty(request)

        if not faculty:

            return Response({'draft': None}, status=status.HTTP_200_OK)

        draft = PaperDraft.objects.filter(faculty=faculty).first()

        if not draft or not draft.draft_data:

            return Response({'draft': None}, status=status.HTTP_200_OK)

        return Response({

            'draft': draft.draft_data,

            'version': draft.version,

            'updated_at': draft.updated_at.isoformat()

        }, status=status.HTTP_200_OK)



    def post(self, request):

        faculty = _get_faculty(request)

        if not faculty:

            return Response({'error': 'Faculty profile not found.'}, status=status.HTTP_403_FORBIDDEN)

        draft_data = request.data.get('draft') if 'draft' in request.data else request.data

        if not isinstance(draft_data, dict):

            return Response({'error': 'Draft data must be a JSON object.'}, status=status.HTTP_400_BAD_REQUEST)

        draft, _ = PaperDraft.objects.get_or_create(faculty=faculty)

        draft.draft_data = draft_data

        draft.version = int(request.data.get('version', 1))

        draft.save()

        return Response({

            'status': 'saved',

            'version': draft.version,

            'updated_at': draft.updated_at.isoformat()

        }, status=status.HTTP_200_OK)



    def delete(self, request):

        faculty = _get_faculty(request)

        if faculty:

            PaperDraft.objects.filter(faculty=faculty).delete()

        return Response({'status': 'cleared'}, status=status.HTTP_200_OK)


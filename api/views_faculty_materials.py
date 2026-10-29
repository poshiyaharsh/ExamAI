"""
Views for faculty subject management and subject-specific study materials.
Enforces strict multi-tenancy, department scoping, and cross-subject isolation.
"""

import logging
from typing import List

from django.db import transaction
from django.db.models import Count, Q
from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from api.models import Subject
from api.permissions import IsFacultyUser
from api.tenant import get_user_institution
from api.utils.departments import get_faculty_department, normalize_department
from api.utils.extract_text import get_cached_syllabus_data, extract_syllabus_text, detect_syllabus_topics
from faculty.models import FacultyProfile, SyllabusUpload

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = ('.pdf', '.docx', '.txt', '.doc')
MAX_MATERIAL_SIZE_BYTES = 25 * 1024 * 1024  # 25 MB


class FacultySubjectsListView(APIView):
    """
    GET /api/faculty/subjects/
    Returns subjects in the faculty's institution and department,
    annotated with available material counts and question bank item counts.

    POST /api/faculty/subjects/
    Creates a new subject for the faculty's department.
    """
    permission_classes = [IsAuthenticated, IsFacultyUser]
    parser_classes = [JSONParser, FormParser]

    def get(self, request):
        tenant_inst = getattr(request, 'tenant', None) or get_user_institution(request.user)
        if not tenant_inst:
            return Response({'detail': 'No active institution found.'}, status=status.HTTP_400_BAD_REQUEST)

        faculty_dept = get_faculty_department(request.user) or ''

        qs = Subject.objects.filter(institution=tenant_inst)
        if faculty_dept:
            qs = qs.filter(Q(department=faculty_dept) | Q(department=''))

        qs = qs.annotate(
            material_count=Count('study_materials', distinct=True),
            question_count=Count('questions', filter=Q(questions__is_deleted=False, questions__exam__isnull=True), distinct=True),
        ).order_by('name')

        subjects = []
        for s in qs:
            subjects.append({
                'id': s.id,
                'name': s.name,
                'code': s.code or '',
                'department': s.department or faculty_dept,
                'material_count': s.material_count,
                'question_count': s.question_count,
            })

        return Response({'subjects': subjects, 'total_count': len(subjects)}, status=status.HTTP_200_OK)

    def post(self, request):
        tenant_inst = getattr(request, 'tenant', None) or get_user_institution(request.user)
        if not tenant_inst:
            return Response({'detail': 'No active institution found.'}, status=status.HTTP_400_BAD_REQUEST)

        name = str(request.data.get('name') or '').strip()
        if not name:
            return Response({'detail': 'Subject name is required.'}, status=status.HTTP_400_BAD_REQUEST)

        faculty_dept = get_faculty_department(request.user) or ''
        code = str(request.data.get('code') or '').strip()
        desc = str(request.data.get('description') or '').strip()

        # Check existing
        existing = Subject.objects.filter(institution=tenant_inst, name__iexact=name, department=faculty_dept).first()
        if existing:
            return Response({
                'id': existing.id,
                'name': existing.name,
                'code': existing.code,
                'department': existing.department,
                                'created': False,
            }, status=status.HTTP_200_OK)

        subject = Subject.objects.create(
            institution=tenant_inst,
            name=name,
            code=code,
            department=faculty_dept,
            created_by=request.user,
        )

        return Response({
            'id': subject.id,
            'name': subject.name,
            'code': subject.code,
            'department': subject.department,
            'created': True,
        }, status=status.HTTP_201_CREATED)


class FacultyStudyMaterialsView(APIView):
    """
    GET /api/faculty/materials/?subject_id=<id>
    Lists uploaded study materials strictly belonging to the specified subject
    and within the faculty's institution and department.

    POST /api/faculty/materials/upload/
    Uploads a study material file (PDF, DOCX, TXT) and saves it associated
    with the target subject.
    """
    permission_classes = [IsAuthenticated, IsFacultyUser]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get(self, request):
        tenant_inst = getattr(request, 'tenant', None) or get_user_institution(request.user)
        if not tenant_inst:
            return Response({'detail': 'No active institution found.'}, status=status.HTTP_400_BAD_REQUEST)

        subject_id = request.query_params.get('subject_id')
        qs = SyllabusUpload.objects.filter(institution=tenant_inst).select_related('subject', 'faculty')

        if subject_id:
            if not str(subject_id).isdigit():
                return Response({'detail': 'Invalid subject_id.'}, status=status.HTTP_400_BAD_REQUEST)
            qs = qs.filter(subject_id=int(subject_id))

        materials = []
        for m in qs.order_by('-created_at'):
            text = m.extracted_text or ''
            topics = m.detected_topics if isinstance(m.detected_topics, list) else []
            preview = text[:300] + ('...' if len(text) > 300 else '')
            materials.append({
                'id': m.id,
                'subject_id': m.subject_id,
                'subject_name': m.subject.name if m.subject else '',
                'original_filename': m.original_filename,
                'content_type': m.content_type,
                'char_count': len(text),
                'detected_topics': topics,
                'preview': preview,
                'created_at': m.created_at.isoformat() if m.created_at else None,
            })

        return Response({'materials': materials, 'total_count': len(materials)}, status=status.HTTP_200_OK)

    def post(self, request):
        tenant_inst = getattr(request, 'tenant', None) or get_user_institution(request.user)
        if not tenant_inst:
            return Response({'detail': 'No active institution found.'}, status=status.HTTP_400_BAD_REQUEST)

        faculty_profile = getattr(request.user, 'faculty_profile', None)
        if not faculty_profile:
            return Response({'detail': 'Faculty profile not found.'}, status=status.HTTP_403_FORBIDDEN)

        subject_id = request.data.get('subject_id')
        subject_name = str(request.data.get('subject_name') or request.data.get('subject') or '').strip()

        subject = None
        if subject_id and str(subject_id).isdigit():
            subject = Subject.objects.filter(id=int(subject_id), institution=tenant_inst).first()
            if not subject:
                return Response({'detail': 'Selected subject was not found or is unauthorized.'}, status=status.HTTP_404_NOT_FOUND)
        elif subject_name:
            faculty_dept = get_faculty_department(request.user) or ''
            subject, _ = Subject.objects.get_or_create(
                institution=tenant_inst,
                name=subject_name,
                department=faculty_dept,
                defaults={'created_by': request.user},
            )
        else:
            return Response({'detail': 'A valid subject_id or subject_name is required.'}, status=status.HTTP_400_BAD_REQUEST)

        uploaded_file = request.FILES.get('file') or request.FILES.get('material') or request.FILES.get('syllabus')
        if not uploaded_file:
            return Response({'detail': 'No file uploaded. Please upload a PDF, DOCX, or TXT file.'}, status=status.HTTP_400_BAD_REQUEST)

        # Validate file size
        if uploaded_file.size > MAX_MATERIAL_SIZE_BYTES:
            return Response({'detail': 'File size exceeds maximum limit of 25MB.'}, status=status.HTTP_400_BAD_REQUEST)

        # Validate file extension
        fname = uploaded_file.name.lower()
        if not any(fname.endswith(ext) for ext in ALLOWED_EXTENSIONS):
            return Response(
                {'detail': f"Unsupported file type. Please upload a {', '.join(ALLOWED_EXTENSIONS)} document."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Extract text and detect topics
        try:
            cached_data = get_cached_syllabus_data(
                uploaded_file,
                uploaded_file.name,
                institution_id=tenant_inst.id
            )
            extracted_text = cached_data.get('text', '')
            detected_topics = cached_data.get('topics', [])
            if not detected_topics:
                detected_topics = detect_syllabus_topics(extracted_text)
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:
            logger.exception('Failed to process study material file %s', uploaded_file.name)
            return Response({'detail': f'Failed to process file: {str(exc)}'}, status=status.HTTP_400_BAD_REQUEST)

        if not extracted_text.strip():
            return Response({'detail': 'The uploaded document contains no extractable text.'}, status=status.HTTP_400_BAD_REQUEST)

        uploaded_file.seek(0)
        material = SyllabusUpload.objects.create(
            faculty=faculty_profile,
            institution=tenant_inst,
            subject=subject,
            original_file=uploaded_file,
            original_filename=uploaded_file.name,
            content_type=getattr(uploaded_file, 'content_type', '') or '',
            extracted_text=extracted_text,
            detected_topics=detected_topics,
        )

        return Response({
            'detail': f"Successfully uploaded and processed '{material.original_filename}' for {subject.name}!",
            'material': {
                'id': material.id,
                'subject_id': subject.id,
                'subject_name': subject.name,
                'original_filename': material.original_filename,
                'content_type': material.content_type,
                'char_count': len(extracted_text),
                'detected_topics': detected_topics,
                'preview': extracted_text[:300] + ('...' if len(extracted_text) > 300 else ''),
                'created_at': material.created_at.isoformat(),
            }
        }, status=status.HTTP_201_CREATED)


class FacultyStudyMaterialDetailView(APIView):
    """
    DELETE /api/faculty/materials/<int:pk>/
    Deletes a study material record owned by the requesting faculty.
    """
    permission_classes = [IsAuthenticated, IsFacultyUser]

    def delete(self, request, pk):
        tenant_inst = getattr(request, 'tenant', None) or get_user_institution(request.user)
        if not tenant_inst:
            return Response({'detail': 'No active institution found.'}, status=status.HTTP_400_BAD_REQUEST)

        faculty_profile = getattr(request.user, 'faculty_profile', None)
        material = SyllabusUpload.objects.filter(
            id=pk,
            institution=tenant_inst,
            faculty=faculty_profile,
        ).first()

        if not material:
            return Response({'detail': 'Study material not found or not owned by you.'}, status=status.HTTP_404_NOT_FOUND)

        filename = material.original_filename
        # Delete file from storage if present
        if material.original_file:
            try:
                material.original_file.delete(save=False)
            except Exception:
                pass

        material.delete()
        return Response({'detail': f"Study material '{filename}' deleted successfully."}, status=status.HTTP_200_OK)

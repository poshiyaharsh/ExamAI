import logging
import os
import uuid
from django.conf import settings
from django.db.models import Sum
from django.utils import timezone

from admins.models import AdminDepartment, AdminInstitution
from api.models import Exam, PaperGenerationJob, Question
from faculty.models import FacultyProfile
from students.models import StudentProfile
from superadmin.models import InstitutePolicy

logger = logging.getLogger(__name__)

ALLOWED_IMAGE_TYPES = {'image/jpeg', 'image/png', 'image/webp'}
MAX_LOGO_SIZE_BYTES = 2 * 1024 * 1024  # 2 MB


def get_or_create_institute_policy(institution: AdminInstitution) -> InstitutePolicy:
    """Retrieve or initialize default operational policy and quotas for an institution."""
    policy, created = InstitutePolicy.objects.get_or_create(
        institution=institution,
        defaults={
            'timezone_name': 'Asia/Kolkata',
            'academic_year': f'{timezone.now().year}-{timezone.now().year + 1}',
            'max_students': 5000,
            'max_faculty': 200,
            'max_ai_generations_per_month': 500,
            'max_storage_mb': 10240,
            'exam_window_buffer_minutes': 15,
            'violation_limit_override': 3,
            'faculty_can_publish_without_review': True,
            'allowed_departments': list(
                AdminDepartment.objects.filter(institution=institution).values_list('department_name', flat=True)
            ),
            'feature_flags': {
                'ai_paper_generation': True,
                'live_proctoring': True,
                'camera_required': True,
                'audio_monitoring': False,
                'fullscreen_enforcement': True,
            },
        },
    )
    return policy


def calculate_institute_usage(institution: AdminInstitution) -> dict:
    """Compute real-time resource utilization against assigned quotas."""
    policy = get_or_create_institute_policy(institution)

    student_count = StudentProfile.objects.filter(institution=institution).count()
    faculty_count = FacultyProfile.objects.filter(institution=institution).count()

    now = timezone.now()
    first_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    ai_generations_used = PaperGenerationJob.objects.filter(
        institution=institution,
        created_at__gte=first_of_month,
    ).count()

    # Estimate database and uploaded media footprint in MB
    exam_count = Exam.objects.filter(institution=institution).count()
    est_storage_mb = round((student_count * 0.1) + (exam_count * 0.5), 2)

    return {
        'institution_id': institution.id,
        'institution_name': institution.institution_name,
        'institution_code': institution.institution_code,
        'students': {
            'used': student_count,
            'quota': policy.max_students,
            'percent': round((student_count / policy.max_students * 100), 1) if policy.max_students else 0,
        },
        'faculty': {
            'used': faculty_count,
            'quota': policy.max_faculty,
            'percent': round((faculty_count / policy.max_faculty * 100), 1) if policy.max_faculty else 0,
        },
        'ai_generations_monthly': {
            'used': ai_generations_used,
            'quota': policy.max_ai_generations_per_month,
            'percent': round((ai_generations_used / policy.max_ai_generations_per_month * 100), 1) if policy.max_ai_generations_per_month else 0,
        },
        'storage_mb': {
            'used': est_storage_mb,
            'quota': policy.max_storage_mb,
            'percent': round((est_storage_mb / policy.max_storage_mb * 100), 1) if policy.max_storage_mb else 0,
        },
        'policy': {
            'timezone': policy.timezone_name,
            'academic_year': policy.academic_year,
            'exam_window_buffer_minutes': policy.exam_window_buffer_minutes,
            'violation_limit_override': policy.violation_limit_override,
            'faculty_can_publish_without_review': policy.faculty_can_publish_without_review,
            'allowed_departments': policy.allowed_departments,
            'feature_flags': policy.feature_flags,
            'logo_url': policy.logo_path if policy.logo_path else None,
        },
    }


def validate_and_save_logo(institution: AdminInstitution, uploaded_file) -> str:
    """
    Validate uploaded image type, size, and store safely in media storage.
    Returns relative public URL path.
    """
    if uploaded_file.size > MAX_LOGO_SIZE_BYTES:
        raise ValueError('Logo file size exceeds the 2 MB limit.')

    content_type = getattr(uploaded_file, 'content_type', '')
    if content_type not in ALLOWED_IMAGE_TYPES:
        raise ValueError(f'Invalid image type "{content_type}". Allowed formats: JPEG, PNG, WEBP.')

    ext = os.path.splitext(uploaded_file.name)[1].lower()
    if ext not in ['.jpg', '.jpeg', '.png', '.webp']:
        raise ValueError('Invalid image file extension.')

    # Secure unique destination filename
    safe_filename = f'logo_{institution.institution_code}_{uuid.uuid4().hex[:12]}{ext}'
    logos_dir = os.path.join(settings.BASE_DIR, 'media', 'logos')
    os.makedirs(logos_dir, exist_ok=True)
    destination_path = os.path.join(logos_dir, safe_filename)

    with open(destination_path, 'wb+') as dest:
        for chunk in uploaded_file.chunks():
            dest.write(chunk)

    rel_url = f'/media/logos/{safe_filename}'
    policy = get_or_create_institute_policy(institution)
    policy.logo_path = rel_url
    policy.save(update_fields=['logo_path', 'updated_at'])

    return rel_url

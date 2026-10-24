from datetime import timedelta
import logging
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Exam, PaperGenerationJob, Question
from .permissions import IsFacultyUser
from .utils.departments import get_faculty_department
from .utils.evaluation_config import PAPER_JOB_MAX_SECONDS

logger = logging.getLogger(__name__)


def serialize_job(job):
    now = timezone.now()
    start = job.started_at or job.created_at
    if job.completed_at and start:
        elapsed = int((job.completed_at - start).total_seconds())
    elif start:
        elapsed = int((now - start).total_seconds())
    else:
        elapsed = 0

    return {
        'id': job.id,
        'exam_id': job.exam_id,
        'exam_title': job.exam.title if job.exam else '',
        'department': job.department,
        'model': job.model,
        'status': job.status,
        'progress': job.progress,
        'current_step': job.current_step,
        'error_message': job.error_message,
        'warnings': job.warnings or [],
        'question_count_requested': job.question_count_requested,
        'question_count_generated': job.question_count_generated,
        'target_marks': job.target_marks,
        'actual_marks': job.actual_marks,
        'marks_shortfall': job.marks_shortfall,
        'off_scope_rejected_count': job.off_scope_rejected_count,
        'retry_count': getattr(job, 'retry_count', 0),
        'is_cancelled': job.is_cancelled,
        'created_at': job.created_at.isoformat() if job.created_at else None,
        'started_at': job.started_at.isoformat() if job.started_at else None,
        'completed_at': job.completed_at.isoformat() if job.completed_at else None,
        'elapsed_seconds': max(0, elapsed),
    }


def check_and_handle_timeout(job):
    if job.status in [PaperGenerationJob.Status.QUEUED, PaperGenerationJob.Status.RUNNING]:
        req_count = job.question_count_requested or 10
        scaled_timeout = min(PAPER_JOB_MAX_SECONDS, max(300, req_count * 90))
        ref_time = job.started_at or job.created_at
        if ref_time and (timezone.now() - ref_time).total_seconds() > scaled_timeout:
            now = timezone.now()
            exam = job.exam
            q_count = exam.questions.filter(is_deleted=False).count() if exam else 0
            if q_count > 0:
                questions = exam.questions.filter(is_deleted=False)
                actual_marks = sum(float(q.marks) for q in questions)
                target = job.target_marks or (exam.target_total_marks if exam else actual_marks)
                shortfall = max(0, int(target - actual_marks))
                job.status = PaperGenerationJob.Status.COMPLETED_WITH_WARNINGS
                job.current_step = 'Completed with partial questions due to timeout'
                job.warnings = (job.warnings or []) + [
                    f'Generation timed out after {int(scaled_timeout // 60)} minutes. {q_count} questions ({int(actual_marks)}/{int(target)} marks) were preserved.'
                ]
                job.actual_marks = int(actual_marks)
                job.marks_shortfall = shortfall
                job.question_count_generated = q_count
                job.completed_at = now
                job.save(update_fields=[
                    'status', 'current_step', 'warnings', 'actual_marks',
                    'marks_shortfall', 'question_count_generated', 'completed_at'
                ])
                if exam:
                    exam.status = Exam.Status.DRAFT
                    exam.total_marks = int(actual_marks)
                    exam.marks_shortfall = shortfall
                    exam.save(update_fields=['status', 'total_marks', 'marks_shortfall'])
            else:
                job.status = PaperGenerationJob.Status.FAILED
                job.error_message = f'Generation timed out after {int(scaled_timeout // 60)} minutes.'
                job.completed_at = now
                job.save(update_fields=['status', 'error_message', 'completed_at'])
                if exam and exam.status == Exam.Status.GENERATING:
                    exam.status = Exam.Status.FAILED
                    exam.error_message = job.error_message
                    exam.save(update_fields=['status', 'error_message'])
    return job


class PaperGenerationJobDetailView(APIView):
    permission_classes = [IsAuthenticated, IsFacultyUser]

    def get(self, request, job_id):
        tenant_inst = getattr(request, 'tenant', None)
        try:
            job = PaperGenerationJob.objects.select_related('exam').get(id=job_id)
        except PaperGenerationJob.DoesNotExist:
            return Response({'detail': 'Generation job not found.'}, status=status.HTTP_404_NOT_FOUND)

        # IDOR Protection: only the faculty who created the job can view it
        if job.faculty_id != request.user.id:
            return Response({'detail': 'You do not have permission to access this generation job.'}, status=status.HTTP_403_FORBIDDEN)

        # Tenant isolation
        if tenant_inst and job.institution_id != tenant_inst.id:
            return Response({'detail': 'Tenant mismatch.'}, status=status.HTTP_403_FORBIDDEN)

        # Department isolation
        faculty_dept = get_faculty_department(request.user)
        if faculty_dept and job.department and faculty_dept != job.department:
            return Response({'detail': 'Department mismatch.'}, status=status.HTTP_403_FORBIDDEN)

        job = check_and_handle_timeout(job)
        return Response(serialize_job(job), status=status.HTTP_200_OK)


class PaperGenerationJobActiveView(APIView):
    permission_classes = [IsAuthenticated, IsFacultyUser]

    def get(self, request):
        tenant_inst = getattr(request, 'tenant', None)
        qs = PaperGenerationJob.objects.filter(
            faculty=request.user,
            status__in=[PaperGenerationJob.Status.QUEUED, PaperGenerationJob.Status.RUNNING],
        ).select_related('exam').order_by('-created_at')

        if tenant_inst:
            qs = qs.filter(institution=tenant_inst)

        active_job = qs.first()
        if not active_job:
            return Response({'active_job': None}, status=status.HTTP_200_OK)

        active_job = check_and_handle_timeout(active_job)
        if active_job.status in [PaperGenerationJob.Status.QUEUED, PaperGenerationJob.Status.RUNNING]:
            return Response({'active_job': serialize_job(active_job)}, status=status.HTTP_200_OK)

        return Response({'active_job': None}, status=status.HTTP_200_OK)


class PaperGenerationJobListView(APIView):
    permission_classes = [IsAuthenticated, IsFacultyUser]

    def get(self, request):
        tenant_inst = getattr(request, 'tenant', None)
        qs = PaperGenerationJob.objects.filter(
            faculty=request.user,
        ).select_related('exam').order_by('-created_at')

        if tenant_inst:
            qs = qs.filter(institution=tenant_inst)

        jobs = list(qs[:25])
        for j in jobs:
            check_and_handle_timeout(j)

        return Response({
            'results': [serialize_job(j) for j in jobs],
            'count': len(jobs),
        }, status=status.HTTP_200_OK)


class PaperGenerationJobCancelView(APIView):
    permission_classes = [IsAuthenticated, IsFacultyUser]

    def post(self, request, job_id):
        tenant_inst = getattr(request, 'tenant', None)
        try:
            job = PaperGenerationJob.objects.select_related('exam').get(id=job_id)
        except PaperGenerationJob.DoesNotExist:
            return Response({'detail': 'Generation job not found.'}, status=status.HTTP_404_NOT_FOUND)

        if job.faculty_id != request.user.id:
            return Response({'detail': 'You do not have permission to cancel this generation job.'}, status=status.HTTP_403_FORBIDDEN)

        if tenant_inst and job.institution_id != tenant_inst.id:
            return Response({'detail': 'Tenant mismatch.'}, status=status.HTTP_403_FORBIDDEN)

        if job.status in [PaperGenerationJob.Status.COMPLETED, PaperGenerationJob.Status.COMPLETED_WITH_WARNINGS]:
            return Response({'detail': 'Job has already completed and cannot be cancelled.'}, status=status.HTTP_400_BAD_REQUEST)

        if job.status in [PaperGenerationJob.Status.FAILED, PaperGenerationJob.Status.CANCELLED]:
            return Response({'detail': f'Job is already in {job.status} state.'}, status=status.HTTP_400_BAD_REQUEST)

        # Mark cancelled
        job.is_cancelled = True
        job.status = PaperGenerationJob.Status.CANCELLED
        job.current_step = 'Cancelled by user'
        job.completed_at = timezone.now()
        job.save(update_fields=['is_cancelled', 'status', 'current_step', 'completed_at'])

        # Clean up any partial questions and exam state
        if job.exam:
            if job.exam.status == Exam.Status.GENERATING:
                Question.objects.filter(exam=job.exam).delete()
                job.exam.status = Exam.Status.FAILED
                job.exam.error_message = 'Generation cancelled by user.'
                job.exam.save(update_fields=['status', 'error_message'])

        return Response({
            'detail': 'Generation job cancelled successfully.',
            'job': serialize_job(job),
        }, status=status.HTTP_200_OK)

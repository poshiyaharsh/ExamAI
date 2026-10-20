import logging
from datetime import timedelta
from django.core.cache import cache
from django.db.models import Avg, Count, F, Q
from django.utils import timezone

from admins.models import AdminInstitution
from api.models import Exam, PaperGenerationJob, StudentAttempt
from faculty.models import FacultyProfile
from students.models import StudentProfile

logger = logging.getLogger(__name__)
CACHE_KEY = 'superadmin_cross_institute_analytics'
CACHE_TTL = 60  # 60 seconds


def get_cross_institute_analytics(force_refresh: bool = False) -> dict:
    """
    Compute platform-wide aggregate metrics across all tenant institutions.
    Aggregations performed directly in the database without exposing personal data.
    Cached briefly (60s) for performance under load.
    """
    if not force_refresh:
        cached = cache.get(CACHE_KEY)
        if cached:
            return cached

    now = timezone.now()
    thirty_days_ago = now - timedelta(days=30)

    # 1. Institutions Overview
    total_inst = AdminInstitution.objects.count()
    active_inst = AdminInstitution.objects.filter(status=AdminInstitution.STATUS_ACTIVE).count()
    suspended_inst = AdminInstitution.objects.filter(status=AdminInstitution.STATUS_SUSPENDED).count()

    total_students = StudentProfile.objects.count()
    total_faculty = FacultyProfile.objects.count()

    # 2. Exams & Attempts Aggregates
    total_exams = Exam.objects.count()
    published_exams = Exam.objects.filter(status=Exam.Status.PUBLISHED).count()

    attempts_qs = StudentAttempt.objects.filter(
        status__in=[StudentAttempt.Status.SUBMITTED, StudentAttempt.Status.AUTO_SUBMITTED, StudentAttempt.Status.EVALUATED]
    )
    total_completed_attempts = attempts_qs.count()

    # Avoid 0% division and calculate pass rate & avg percentage
    if total_completed_attempts > 0:
        passed_attempts = attempts_qs.filter(total_score__gte=F('max_score') * 0.4).count()
        pass_rate_percent = round((passed_attempts / total_completed_attempts * 100), 1)
        avg_score_data = attempts_qs.aggregate(
            avg_score=Avg('total_score'),
            avg_violations=Avg('violation_count'),
        )
        avg_score = round(avg_score_data['avg_score'] or 0, 1)
        avg_violations = round(avg_score_data['avg_violations'] or 0, 2)
    else:
        pass_rate_percent = None
        avg_score = None
        avg_violations = 0.0

    # 3. AI Paper Generation Metrics
    gen_qs = PaperGenerationJob.objects.filter(created_at__gte=thirty_days_ago)
    total_gen = gen_qs.count()
    if total_gen > 0:
        successful_gen = gen_qs.filter(
            status__in=[PaperGenerationJob.Status.COMPLETED, PaperGenerationJob.Status.COMPLETED_WITH_WARNINGS]
        ).count()
        gen_success_rate = round((successful_gen / total_gen * 100), 1)
        shortfall_jobs = gen_qs.filter(marks_shortfall__gt=0).count()
        shortfall_rate = round((shortfall_jobs / total_gen * 100), 1)
    else:
        gen_success_rate = 100.0
        shortfall_rate = 0.0

    # 4. 30-Day Growth Trend (grouped by day)
    growth_trend = []
    for day_offset in range(29, -1, -1):
        day_start = (now - timedelta(days=day_offset)).replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        attempts_count = StudentAttempt.objects.filter(started_at__gte=day_start, started_at__lt=day_end).count()
        exams_count = Exam.objects.filter(created_at__gte=day_start, created_at__lt=day_end).count()
        growth_trend.append({
            'date': day_start.strftime('%Y-%m-%d'),
            'attempts': attempts_count,
            'exams_created': exams_count,
        })

    # 5. Department Breakdown across platform
    dept_distribution = list(
        Exam.objects.values('department')
        .annotate(exam_count=Count('id'))
        .filter(exam_count__gt=0)
        .order_by('-exam_count')[:10]
    )

    result = {
        'timestamp': now.isoformat(),
        'institutions': {
            'total': total_inst,
            'active': active_inst,
            'suspended': suspended_inst,
        },
        'users': {
            'total_students': total_students,
            'total_faculty': total_faculty,
        },
        'exams_and_results': {
            'total_exams': total_exams,
            'published_exams': published_exams,
            'completed_attempts': total_completed_attempts,
            'pass_rate_percent': pass_rate_percent,
            'average_score': avg_score,
            'average_violations_per_attempt': avg_violations,
        },
        'ai_generation': {
            'total_30d': total_gen,
            'success_rate_percent': gen_success_rate,
            'marks_shortfall_rate_percent': shortfall_rate,
        },
        'growth_trend_30d': growth_trend,
        'department_distribution': dept_distribution,
    }

    cache.set(CACHE_KEY, result, CACHE_TTL)
    return result

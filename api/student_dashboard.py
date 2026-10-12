import logging
from django.db.models import Avg, Count, ExpressionWrapper, F, FloatField, Max, Min, Q
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Exam, StudentAttempt
from .permissions import IsStudentUser
from .utils.departments import get_student_department
from .utils.scoring import PASSING_PERCENTAGE

logger = logging.getLogger(__name__)

COMPLETED_STATUSES = [
    StudentAttempt.Status.SUBMITTED,
    StudentAttempt.Status.AUTO_SUBMITTED,
    StudentAttempt.Status.EVALUATED,
]


def _format_time_taken(started_at, submitted_at):
    if not (started_at and submitted_at):
        return "-"
    diff_sec = int((submitted_at - started_at).total_seconds())
    if diff_sec < 0:
        return "0s"
    mins = diff_sec // 60
    secs = diff_sec % 60
    if mins > 0:
        return f"{mins}m {secs}s"
    return f"{secs}s"


class StudentDashboardView(APIView):
    permission_classes = [IsAuthenticated, IsStudentUser]

    def get(self, request):
        user = request.user
        now = timezone.now()
        student_profile = getattr(user, 'student_profile', None)
        student_dept = get_student_department(user)

        # 1. Profile information
        full_name = f"{user.first_name} {user.last_name}".strip() or user.username
        roll_number = student_profile.student_id if student_profile and student_profile.student_id else ""
        year_semester = ""
        if roll_number:
            parts = roll_number.split('-')
            if len(parts) >= 2 and parts[1].isdigit():
                year_semester = f"Class of {parts[1]}"

        profile_data = {
            'name': full_name,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'email': user.email,
            'roll_number': roll_number,
            'department': student_dept or 'Unassigned',
            'year_semester': year_semester,
            'profile_photo': None,
        }

        # 2. Department-scoped published exams
        if student_dept:
            dept_exams = Exam.objects.filter(
                status=Exam.Status.PUBLISHED,
                department__iexact=student_dept,
            ).select_related('created_by')
        else:
            dept_exams = Exam.objects.none()

        total_available = dept_exams.count()

        # 3. Student's completed attempts in department
        pct_expr = ExpressionWrapper(
            F('total_score') * 100.0 / F('exam__total_marks'),
            output_field=FloatField()
        )

        completed_attempts_qs = (
            StudentAttempt.objects.filter(
                student=user,
                status__in=COMPLETED_STATUSES,
            )
            .select_related('exam', 'exam__created_by')
            .annotate(percentage=pct_expr)
        )
        if student_dept:
            completed_attempts_qs = completed_attempts_qs.filter(exam__department__iexact=student_dept)

        stats_agg = completed_attempts_qs.aggregate(
            attempt_count=Count('id'),
            avg_score=Avg('percentage'),
            highest_score=Max('percentage'),
            lowest_score=Min('percentage'),
            pass_count=Count('id', filter=Q(percentage__gte=PASSING_PERCENTAGE)),
            fail_count=Count('id', filter=Q(percentage__lt=PASSING_PERCENTAGE)),
        )

        exams_attempted = stats_agg.get('attempt_count') or 0
        exams_pending = max(0, total_available - exams_attempted)
        avg_score = round(stats_agg['avg_score'], 1) if stats_agg.get('avg_score') is not None else None
        highest_score = round(stats_agg['highest_score'], 1) if stats_agg.get('highest_score') is not None else None
        pass_count = stats_agg.get('pass_count') or 0
        pass_rate = round((pass_count / exams_attempted) * 100.0, 1) if exams_attempted > 0 else None

        if avg_score is None:
            perf_status = 'N/A'
        elif avg_score >= 80.0:
            perf_status = 'Excellent'
        elif avg_score >= 65.0:
            perf_status = 'Good'
        elif avg_score >= 50.0:
            perf_status = 'Average'
        else:
            perf_status = 'Needs Improvement'

        stats_data = {
            'total_available': total_available,
            'exams_attempted': exams_attempted,
            'exams_pending': exams_pending,
            'average_score': avg_score,
            'highest_score': highest_score,
            'pass_count': pass_count,
            'fail_count': stats_agg.get('fail_count') or 0,
            'pass_rate': pass_rate,
            'performance_status': perf_status,
        }

        # 4. Ongoing & Upcoming exams (unattempted by student)
        completed_exam_ids = set(completed_attempts_qs.values_list('exam_id', flat=True))
        unattempted_exams = dept_exams.exclude(id__in=completed_exam_ids)

        def _serialize_exam(e):
            topics = e.topics
            subject = ', '.join(str(t) for t in topics) if isinstance(topics, list) and topics else 'General'
            faculty = e.created_by
            faculty_name = f"{faculty.first_name} {faculty.last_name}".strip() or faculty.username
            is_open = (e.starts_at is None or e.starts_at <= now) and (e.ends_at is None or e.ends_at >= now)
            return {
                'id': e.id,
                'title': e.title,
                'subject': subject,
                'department': e.department,
                'faculty_name': faculty_name,
                'duration_minutes': e.duration_minutes,
                'total_marks': e.total_marks,
                'starts_at': e.starts_at.isoformat() if e.starts_at else None,
                'ends_at': e.ends_at.isoformat() if e.ends_at else None,
                'is_open': is_open,
            }

        # Ongoing exams: currently within open window
        ongoing_exams = [
            _serialize_exam(e)
            for e in unattempted_exams.filter(
                Q(starts_at__isnull=True) | Q(starts_at__lte=now),
                Q(ends_at__isnull=True) | Q(ends_at__gte=now),
            ).order_by('ends_at', 'id')[:5]
        ]

        # Upcoming exams: scheduled with starts_at in the future, or other unattempted
        future_exams = unattempted_exams.filter(starts_at__gt=now).order_by('starts_at', 'id')[:5]
        if not future_exams.exists():
            # If no strict future starts_at, show upcoming unattempted exams
            future_exams = unattempted_exams.order_by('starts_at', '-created_at')[:5]

        upcoming_exams = [_serialize_exam(e) for e in future_exams]

        # 5. Recent results (last 5 completed attempts)
        recent_results_qs = completed_attempts_qs.order_by('-submitted_at', '-started_at', '-id')[:5]
        recent_results = []
        for a in recent_results_qs:
            topics = a.exam.topics
            subject = ', '.join(str(t) for t in topics) if isinstance(topics, list) and topics else 'General'
            faculty = a.exam.created_by
            faculty_name = f"{faculty.first_name} {faculty.last_name}".strip() or faculty.username
            pct = round(a.percentage, 1)

            recent_results.append({
                'attempt_id': a.id,
                'exam_id': a.exam.id,
                'exam_title': a.exam.title,
                'subject': subject,
                'department': a.exam.department,
                'faculty_name': faculty_name,
                'date': a.submitted_at.isoformat() if a.submitted_at else a.started_at.isoformat(),
                'marks_obtained': round(float(a.total_score or 0.0), 1),
                'total_marks': a.exam.total_marks,
                'percentage': pct,
                'is_passed': pct >= PASSING_PERCENTAGE,
                'time_taken': _format_time_taken(a.started_at, a.submitted_at),
                'status': a.status,
            })

        # 6. Performance trend (last 6-8 scores chronologically)
        latest_for_trend = list(completed_attempts_qs.order_by('-submitted_at', '-started_at', '-id')[:8])
        latest_for_trend.reverse()
        performance_trend = [
            {
                'attempt_id': a.id,
                'date': (a.submitted_at or a.started_at).strftime('%b %d') if (a.submitted_at or a.started_at) else '-',
                'percentage': round(a.percentage, 1),
                'exam_title': a.exam.title,
            }
            for a in latest_for_trend
        ]

        # 7. Subject strengths (aggregation)
        grouped_topics = (
            completed_attempts_qs.values('exam__topics')
            .annotate(avg_score=Avg(pct_expr), count=Count('id'))
            .order_by('-avg_score')
        )
        subject_list = []
        for item in grouped_topics:
            raw = item.get('exam__topics')
            s_name = ', '.join(str(t) for t in raw) if isinstance(raw, list) and raw else 'General'
            subject_list.append({
                'subject': s_name,
                'average_score': round(item['avg_score'], 1) if item.get('avg_score') is not None else 0.0,
                'count': item['count'],
            })

        strongest_subject = subject_list[0] if subject_list else None
        weakest_subject = (
            subject_list[-1]
            if len(subject_list) > 1 and subject_list[-1]['average_score'] != subject_list[0]['average_score']
            else None
        )

        return Response({
            'status': 'success',
            'data': {
                'profile': profile_data,
                'stats': stats_data,
                'ongoing_exams': ongoing_exams,
                'upcoming_exams': upcoming_exams,
                'recent_results': recent_results,
                'performance_trend': performance_trend,
                'subject_strengths': {
                    'strongest': strongest_subject,
                    'weakest': weakest_subject,
                    'all': subject_list,
                },
                'announcements': [],
            }
        })

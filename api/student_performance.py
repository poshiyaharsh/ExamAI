import logging
from datetime import datetime
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


class StudentPerformancePermissionMixin:
    permission_classes = [IsAuthenticated, IsStudentUser]


def _get_student_completed_attempts(user, tenant=None):
    """
    Returns queryset of completed attempts for the authenticated student,
    strictly scoped to their assigned department and tenant institution.
    """
    if not tenant:
        from api.tenant import get_user_institution
        tenant = get_user_institution(user)

    pct_expr = ExpressionWrapper(
        F('total_score') * 100.0 / F('exam__total_marks'),
        output_field=FloatField()
    )

    qs = (
        StudentAttempt.objects.filter(
            student=user,
            institution=tenant,
            status__in=COMPLETED_STATUSES,
        )
        .select_related('exam', 'exam__created_by')
        .annotate(percentage=pct_expr)
    )

    student_dept = get_student_department(user)
    if student_dept:
        qs = qs.filter(exam__department__iexact=student_dept)

    return qs, student_dept, pct_expr


def _format_time_taken(started_at, submitted_at):
    if not (started_at and submitted_at):
        return None, "-"
    diff_sec = int((submitted_at - started_at).total_seconds())
    if diff_sec < 0:
        return 0, "0s"
    mins = diff_sec // 60
    secs = diff_sec % 60
    if mins > 0:
        return diff_sec, f"{mins}m {secs}s"
    return diff_sec, f"{secs}s"


class StudentPerformanceSummaryView(StudentPerformancePermissionMixin, APIView):
    def get(self, request):
        from api.tenant import get_user_institution
        tenant = getattr(request, 'tenant', None) or get_user_institution(request.user)
        attempts_qs, student_dept, pct_expr = _get_student_completed_attempts(request.user, tenant=tenant)

        stats = attempts_qs.aggregate(
            total_attempts=Count('id'),
            avg_score=Avg('percentage'),
            highest_score=Max('percentage'),
            lowest_score=Min('percentage'),
            last_exam_date=Max('submitted_at'),
            pass_count=Count('id', filter=Q(percentage__gte=PASSING_PERCENTAGE)),
            fail_count=Count('id', filter=Q(percentage__lt=PASSING_PERCENTAGE)),
        )

        total_attempts = stats.get('total_attempts') or 0
        avg_score = round(stats['avg_score'], 1) if stats.get('avg_score') is not None else None
        highest_score = round(stats['highest_score'], 1) if stats.get('highest_score') is not None else None
        lowest_score = round(stats['lowest_score'], 1) if stats.get('lowest_score') is not None else None
        pass_count = stats.get('pass_count') or 0
        fail_count = stats.get('fail_count') or 0
        pass_rate = round((pass_count / total_attempts) * 100.0, 1) if total_attempts > 0 else None
        last_exam_date = stats.get('last_exam_date')

        # Performance Status
        if avg_score is None:
            performance_status = 'N/A'
        elif avg_score >= 80.0:
            performance_status = 'Excellent'
        elif avg_score >= 65.0:
            performance_status = 'Good'
        elif avg_score >= 50.0:
            performance_status = 'Average'
        else:
            performance_status = 'Needs Improvement'

        # Department Rank and Percentile calculation
        department_rank = None
        department_total_students = None
        department_percentile = None

        if student_dept and avg_score is not None:
            try:
                dept_student_stats = (
                    StudentAttempt.objects.filter(
                        institution=tenant,
                        status__in=COMPLETED_STATUSES,
                        exam__department__iexact=student_dept,
                        student__student_profile__department__iexact=student_dept,
                    )
                    .values('student')
                    .annotate(avg_pct=Avg(pct_expr))
                    .filter(avg_pct__isnull=False)
                )

                all_dept_averages = [round(item['avg_pct'], 1) for item in dept_student_stats]
                if all_dept_averages:
                    higher_count = sum(1 for a in all_dept_averages if a > avg_score)
                    department_rank = higher_count + 1
                    department_total_students = len(all_dept_averages)
                    if department_total_students > 1:
                        department_percentile = round(
                            ((department_total_students - department_rank) / (department_total_students - 1)) * 100.0,
                            1
                        )
                    else:
                        department_percentile = 100.0
            except Exception as e:
                logger.warning('Failed to compute department rank: %s', e)

        return Response({
            'status': 'success',
            'data': {
                'total_attempts': total_attempts,
                'overall_average': avg_score,
                'highest_score': highest_score,
                'lowest_score': lowest_score,
                'pass_count': pass_count,
                'fail_count': fail_count,
                'pass_rate': pass_rate,
                'last_exam_date': last_exam_date.isoformat() if last_exam_date else None,
                'performance_status': performance_status,
                'department': student_dept or 'Unassigned',
                'department_rank': department_rank,
                'department_total_students': department_total_students,
                'department_percentile': department_percentile,
            }
        })


class StudentPerformanceResultsView(StudentPerformancePermissionMixin, APIView):
    def get(self, request):
        from api.tenant import get_user_institution
        tenant = getattr(request, 'tenant', None) or get_user_institution(request.user)
        attempts_qs, student_dept, _ = _get_student_completed_attempts(request.user, tenant=tenant)

        # Filters
        search_query = request.query_params.get('search', '').strip()
        if search_query:
            attempts_qs = attempts_qs.filter(
                Q(exam__title__icontains=search_query) |
                Q(exam__topics__icontains=search_query)
            )

        subject_filter = request.query_params.get('subject', '').strip()
        if subject_filter and subject_filter.lower() != 'all':
            attempts_qs = attempts_qs.filter(exam__topics__icontains=subject_filter)

        status_filter = request.query_params.get('status', '').strip().lower()
        if status_filter == 'pass':
            attempts_qs = attempts_qs.filter(percentage__gte=PASSING_PERCENTAGE)
        elif status_filter == 'fail':
            attempts_qs = attempts_qs.filter(percentage__lt=PASSING_PERCENTAGE)

        start_date = request.query_params.get('start_date', '').strip()
        if start_date:
            try:
                parsed_start = datetime.strptime(start_date, '%Y-%m-%d')
                attempts_qs = attempts_qs.filter(submitted_at__gte=parsed_start)
            except ValueError:
                pass

        end_date = request.query_params.get('end_date', '').strip()
        if end_date:
            try:
                parsed_end = datetime.strptime(end_date, '%Y-%m-%d')
                # Include the entire end day
                parsed_end = parsed_end.replace(hour=23, minute=59, second=59)
                attempts_qs = attempts_qs.filter(submitted_at__lte=parsed_end)
            except ValueError:
                pass

        # Sorting
        sort_by = request.query_params.get('sort', '-date').strip()
        sort_map = {
            '-date': '-submitted_at',
            'date': 'submitted_at',
            '-percentage': '-percentage',
            'percentage': 'percentage',
            '-score': '-total_score',
            'score': 'total_score',
            'title': 'exam__title',
            '-title': '-exam__title',
        }
        order_field = sort_map.get(sort_by, '-submitted_at')
        attempts_qs = attempts_qs.order_by(order_field, '-id')

        total_count = attempts_qs.count()

        # Pagination
        try:
            page = max(1, int(request.query_params.get('page', 1)))
        except (ValueError, TypeError):
            page = 1
        try:
            page_size = min(100, max(1, int(request.query_params.get('page_size', 10))))
        except (ValueError, TypeError):
            page_size = 10

        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        page_attempts = list(attempts_qs[start_idx:end_idx])

        from .utils.results import compute_attempt_result_status

        results = []
        for a in page_attempts:
            topics = a.exam.topics if isinstance(a.exam.topics, list) else []
            subject = a.exam.subject or (topics[0] if topics else 'General')
            faculty = a.exam.created_by
            faculty_name = f"{faculty.first_name} {faculty.last_name}".strip() or faculty.username
            time_sec, time_formatted = _format_time_taken(a.started_at, a.submitted_at)
            
            status_info = compute_attempt_result_status(a, exam=a.exam)

            results.append({
                'attempt_id': a.id,
                'exam_id': a.exam.id,
                'exam_title': a.exam.title,
                'subject': subject,
                'topics': topics,
                'department': a.exam.department,
                'faculty_name': faculty_name,
                'faculty_email': faculty.email,
                'date': a.submitted_at.isoformat() if a.submitted_at else a.started_at.isoformat(),
                'marks_obtained': status_info['marks_obtained'],
                'total_marks': status_info['total_marks'],
                'percentage': status_info['percentage'],
                'is_passed': status_info['is_passed'],
                'time_taken_seconds': time_sec,
                'time_taken': time_formatted,
                'status': a.status,
                'result_status': status_info,
            })

        total_pages = (total_count + page_size - 1) // page_size if page_size else 1

        return Response({
            'status': 'success',
            'data': results,
            'pagination': {
                'page': page,
                'page_size': page_size,
                'total_count': total_count,
                'total_pages': total_pages,
                'has_next': page < total_pages,
                'has_prev': page > 1,
            }
        })


class StudentPerformanceTrendView(StudentPerformancePermissionMixin, APIView):
    def get(self, request):
        from api.tenant import get_user_institution
        tenant = getattr(request, 'tenant', None) or get_user_institution(request.user)
        attempts_qs, _, _ = _get_student_completed_attempts(request.user, tenant=tenant)
        # Chronological order for chart
        attempts = attempts_qs.order_by('submitted_at', 'started_at', 'id')

        trend_data = []
        for a in attempts:
            d = a.submitted_at or a.started_at
            pct = round(a.percentage, 1)
            trend_data.append({
                'attempt_id': a.id,
                'date': d.strftime('%b %d, %Y') if d else '-',
                'iso_date': d.isoformat() if d else None,
                'percentage': pct,
                'marks_obtained': round(float(a.total_score or 0.0), 1),
                'total_marks': a.exam.total_marks,
                'exam_title': a.exam.title,
                'status': a.status,
            })

        return Response({
            'status': 'success',
            'data': trend_data,
        })


class StudentPerformanceSubjectsView(StudentPerformancePermissionMixin, APIView):
    def get(self, request):
        from api.tenant import get_user_institution
        tenant = getattr(request, 'tenant', None) or get_user_institution(request.user)
        attempts_qs, _, pct_expr = _get_student_completed_attempts(request.user, tenant=tenant)

        # Database aggregation: GROUP BY exam__topics
        grouped_topics = (
            attempts_qs.values('exam__topics')
            .annotate(
                avg_score=Avg(pct_expr),
                exam_count=Count('id'),
                highest_score=Max(pct_expr),
                lowest_score=Min(pct_expr),
            )
            .order_by('-avg_score')
        )

        subject_list = []
        for item in grouped_topics:
            raw_topics = item.get('exam__topics')
            subject_name = ', '.join(str(t) for t in raw_topics) if isinstance(raw_topics, list) and raw_topics else 'General'
            avg_pct = round(item['avg_score'], 1) if item.get('avg_score') is not None else 0.0
            subject_list.append({
                'subject': subject_name,
                'average_score': avg_pct,
                'exam_count': item['exam_count'],
                'highest_score': round(item['highest_score'], 1) if item.get('highest_score') is not None else avg_pct,
                'lowest_score': round(item['lowest_score'], 1) if item.get('lowest_score') is not None else avg_pct,
            })

        # Identify strongest and weakest subjects
        if subject_list:
            highest_avg = max(s['average_score'] for s in subject_list)
            lowest_avg = min(s['average_score'] for s in subject_list)

            for s in subject_list:
                s['is_strongest'] = s['average_score'] == highest_avg
                # Only mark weakest if there is more than 1 subject or distinct score
                s['is_weakest'] = (s['average_score'] == lowest_avg) and (len(subject_list) > 1 and highest_avg != lowest_avg)
        else:
            highest_avg = None
            lowest_avg = None

        return Response({
            'status': 'success',
            'data': {
                'subjects': subject_list,
                'strongest_subject': next((s['subject'] for s in subject_list if s.get('is_strongest')), None),
                'weakest_subject': next((s['subject'] for s in subject_list if s.get('is_weakest')), None),
            }
        })

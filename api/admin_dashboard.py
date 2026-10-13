import datetime
import logging
from django.core.cache import cache
from django.db.models import Avg, Count, ExpressionWrapper, F, FloatField, Q
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Exam, StudentAttempt
from .permissions import IsAdminUser
from .utils.departments import DEFAULT_DEPARTMENT_NAMES
from .utils.scoring import PASSING_PERCENTAGE
from admins.models import AdminInstitution
from faculty.models import FacultyProfile
from students.models import StudentProfile
from api.tenant import get_tenant_cache_key, get_user_institution

logger = logging.getLogger(__name__)

COMPLETED_STATUSES = [
    StudentAttempt.Status.SUBMITTED,
    StudentAttempt.Status.AUTO_SUBMITTED,
    StudentAttempt.Status.EVALUATED,
]


class AdminDashboardView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        admin_user = request.user
        now = timezone.now()
        week_ago = now - datetime.timedelta(days=7)

        # 1. Scoping by Institution
        from api.tenant import get_user_institution
        institution = getattr(request, 'tenant', None) or get_user_institution(admin_user)
        if not institution:
            return Response(
                {'status': 'error', 'message': 'Admin institution not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        students_qs = StudentProfile.objects.select_related('user', 'institution').filter(institution=institution)
        faculty_qs = FacultyProfile.objects.select_related('user', 'institution').filter(institution=institution)
        exams_qs = Exam.objects.select_related('created_by', 'created_by__faculty_profile').filter(institution=institution)

        # 2. Filters: department and range
        dept_param = request.query_params.get('department', '').strip()
        if dept_param and dept_param.lower() != 'all':
            students_qs = students_qs.filter(department__iexact=dept_param)
            faculty_qs = faculty_qs.filter(department__iexact=dept_param)
            exams_qs = exams_qs.filter(department__iexact=dept_param)

        range_param = request.query_params.get('range', 'all').strip().lower()

        cache_key = None
        try:
            cache_key = get_tenant_cache_key(
                institution.id,
                f"admin_dashboard:dept_{dept_param.lower() or 'all'}:range_{range_param or 'all'}"
            )
            if request.query_params.get('refresh') != 'true':
                cached_payload = cache.get(cache_key)
                if cached_payload is not None:
                    return Response(cached_payload)
        except Exception as e:
            logger.warning(f"Dashboard cache lookup failed: {e}")

        range_start = None
        if range_param == '7d':
            range_start = now - datetime.timedelta(days=7)
        elif range_param == '30d':
            range_start = now - datetime.timedelta(days=30)
        elif range_param == 'semester':
            range_start = now - datetime.timedelta(days=120)

        # Base exams for time-filtered counts
        filtered_exams = exams_qs
        if range_start:
            filtered_exams = filtered_exams.filter(created_at__gte=range_start)

        pct_expr = ExpressionWrapper(
            F('total_score') * 100.0 / F('exam__total_marks'),
            output_field=FloatField()
        )

        attempts_qs = (
            StudentAttempt.objects.filter(
                institution=institution,
                exam__in=exams_qs,
                status__in=COMPLETED_STATUSES,
            )
            .select_related('exam', 'student')
            .annotate(percentage=pct_expr)
        )
        if range_start:
            attempts_qs = attempts_qs.filter(submitted_at__gte=range_start)

        # 3. Overall Stats
        total_students = students_qs.count()
        total_faculty = faculty_qs.count()
        total_departments = len(DEFAULT_DEPARTMENT_NAMES)

        total_exams = filtered_exams.count()
        published_exams = filtered_exams.filter(status=Exam.Status.PUBLISHED).count()
        draft_exams = filtered_exams.filter(status=Exam.Status.DRAFT).count()
        upcoming_exams_count = filtered_exams.filter(status=Exam.Status.PUBLISHED, starts_at__gt=now).count()
        ongoing_exams_count = filtered_exams.filter(
            status=Exam.Status.PUBLISHED
        ).filter(
            Q(starts_at__isnull=True) | Q(starts_at__lte=now),
            Q(ends_at__isnull=True) | Q(ends_at__gte=now),
        ).count()
        completed_exams_count = filtered_exams.filter(
            status=Exam.Status.PUBLISHED,
            ends_at__isnull=False,
            ends_at__lt=now,
        ).count()

        attempt_stats = attempts_qs.aggregate(
            total_attempts=Count('id'),
            avg_score=Avg('percentage'),
            pass_count=Count('id', filter=Q(percentage__gte=PASSING_PERCENTAGE)),
            fail_count=Count('id', filter=Q(percentage__lt=PASSING_PERCENTAGE)),
        )
        total_attempts = attempt_stats.get('total_attempts') or 0
        overall_avg = round(attempt_stats['avg_score'], 1) if attempt_stats.get('avg_score') is not None else None
        pass_count = attempt_stats.get('pass_count') or 0
        overall_pass_rate = round((pass_count / total_attempts) * 100.0, 1) if total_attempts > 0 else None

        # Weekly Growth Indicators
        new_students_this_week = students_qs.filter(created_at__gte=week_ago).count()
        new_faculty_this_week = faculty_qs.filter(created_at__gte=week_ago).count()
        new_exams_this_week = exams_qs.filter(created_at__gte=week_ago).count()
        new_attempts_this_week = StudentAttempt.objects.filter(
            exam__in=exams_qs,
            status__in=COMPLETED_STATUSES,
            submitted_at__gte=week_ago
        ).count()

        stats_data = {
            'total_students': total_students,
            'total_faculty': total_faculty,
            'total_departments': total_departments,
            'total_exams': total_exams,
            'published_exams': published_exams,
            'draft_exams': draft_exams,
            'upcoming_exams': upcoming_exams_count,
            'ongoing_exams': ongoing_exams_count,
            'completed_exams': completed_exams_count,
            'total_attempts': total_attempts,
            'overall_average': overall_avg,
            'overall_pass_rate': overall_pass_rate,
            'new_students_this_week': new_students_this_week,
            'new_faculty_this_week': new_faculty_this_week,
            'new_exams_this_week': new_exams_this_week,
            'new_attempts_this_week': new_attempts_this_week,
        }

        # 4. Ongoing Exams (strictly institution-scoped live metrics, showing at most 6)
        from api.exams.eligibility import compute_batch_live_exam_metrics

        all_live_qs = exams_qs.filter(
            status=Exam.Status.PUBLISHED
        ).filter(
            Q(starts_at__isnull=True) | Q(starts_at__lte=now),
            Q(ends_at__isnull=True) | Q(ends_at__gt=now),
        )
        live_total = all_live_qs.count()

        # Database query slice to at most 6 exams, ordered by most recently started (-starts_at, -id)
        shown_live_qs = all_live_qs.order_by(
            F('starts_at').desc(nulls_last=True),
            '-id',
        )[:6]
        shown_live_exams = list(shown_live_qs)
        shown_count = len(shown_live_exams)
        has_more = live_total > shown_count

        all_live_exams_list = list(all_live_qs) if has_more else shown_live_exams

        ongoing_exams_list, live_summary = compute_batch_live_exam_metrics(
            exams=shown_live_exams,
            institution=institution,
            now=now,
            all_live_exams=all_live_exams_list,
        )
        stats_data.update({
            'live_exams_count': live_summary['live_exams_count'],
            'total_eligible_unique': live_summary['total_eligible_unique'],
            'total_in_progress': live_summary['total_in_progress'],
        })

        # 5. Upcoming Exams
        upcoming_qs = filtered_exams.filter(
            status=Exam.Status.PUBLISHED,
            starts_at__gt=now,
        ).order_by('starts_at', 'id')[:5]

        if not upcoming_qs.exists():
            upcoming_qs = filtered_exams.filter(status=Exam.Status.PUBLISHED).order_by('-created_at')[:5]

        upcoming_exams_list = []
        for e in upcoming_qs:
            u = e.created_by
            f_name = f"{u.first_name} {u.last_name}".strip() or u.username
            upcoming_exams_list.append({
                'id': e.id,
                'title': e.title,
                'department': e.department,
                'faculty_name': f_name,
                'duration_minutes': e.duration_minutes,
                'total_marks': e.total_marks,
                'starts_at': e.starts_at.isoformat() if e.starts_at else None,
                'ends_at': e.ends_at.isoformat() if e.ends_at else None,
            })

        # 6. Department Overview (All 11 departments)
        dept_overview = []
        for d_name in DEFAULT_DEPARTMENT_NAMES:
            d_students = StudentProfile.objects.filter(department__iexact=d_name)
            d_faculty = FacultyProfile.objects.filter(department__iexact=d_name)
            d_exams = Exam.objects.filter(department__iexact=d_name)
            if institution:
                d_students = d_students.filter(institution=institution)
                d_faculty = d_faculty.filter(institution=institution)
                d_exams = d_exams.filter(
                    Q(created_by__faculty_profile__institution=institution)
                    | Q(created_by__faculty_profile__institution__isnull=True)
                )

            d_attempts = StudentAttempt.objects.filter(
                exam__in=d_exams,
                status__in=COMPLETED_STATUSES,
            )
            d_stats = d_attempts.annotate(pct=pct_expr).aggregate(
                cnt=Count('id'),
                avg=Avg('pct'),
                passes=Count('id', filter=Q(pct__gte=PASSING_PERCENTAGE)),
            )
            c = d_stats.get('cnt') or 0
            avg_v = round(d_stats['avg'], 1) if d_stats.get('avg') is not None else None
            p_rate = round((d_stats.get('passes') or 0) / c * 100.0, 1) if c > 0 else None

            dept_overview.append({
                'department': d_name,
                'students_count': d_students.count(),
                'faculty_count': d_faculty.count(),
                'exams_count': d_exams.count(),
                'attempts_count': c,
                'average_score': avg_v,
                'pass_rate': p_rate,
            })

        # 7. Exams per Faculty (top 5)
        faculty_exam_counts = (
            faculty_qs.values(
                'user__id',
                'user__first_name',
                'user__last_name',
                'user__username',
                'user__email',
                'department',
                'employee_id',
            )
            .annotate(
                total_exams=Count('user__created_exams', distinct=True),
                published_exams=Count('user__created_exams', filter=Q(user__created_exams__status=Exam.Status.PUBLISHED), distinct=True),
                total_attempts=Count('user__created_exams__attempts', filter=Q(user__created_exams__attempts__status__in=COMPLETED_STATUSES), distinct=True),
            )
            .order_by('-total_exams')[:5]
        )
        faculty_rankings = [
            {
                'faculty_id': f['user__id'],
                'name': f"{f['user__first_name']} {f['user__last_name']}".strip() or f['user__username'],
                'email': f['user__email'],
                'department': f['department'] or 'Unassigned',
                'employee_id': f['employee_id'] or '-',
                'total_exams': f['total_exams'],
                'published_exams': f['published_exams'],
                'total_attempts': f['total_attempts'],
            }
            for f in faculty_exam_counts
        ]

        # 8. Top Students overall (top 5)
        top_students_qs = (
            attempts_qs.values(
                'student__id',
                'student__first_name',
                'student__last_name',
                'student__username',
                'student__student_profile__student_id',
                'student__student_profile__department',
            )
            .annotate(
                avg_score=Avg('percentage'),
                exams_taken=Count('id'),
            )
            .order_by('-avg_score')[:5]
        )
        top_students_list = [
            {
                'student_id': s['student__id'],
                'name': f"{s['student__first_name']} {s['student__last_name']}".strip() or s['student__username'],
                'roll_number': s.get('student__student_profile__student_id') or '-',
                'department': s.get('student__student_profile__department') or '-',
                'average_score': round(s['avg_score'], 1) if s.get('avg_score') is not None else 0.0,
                'exams_taken': s['exams_taken'],
            }
            for s in top_students_qs
        ]

        # 9. At-Risk Students (low scores <40% + 0 attempts)
        low_scorers_qs = (
            attempts_qs.values(
                'student__id',
                'student__first_name',
                'student__last_name',
                'student__username',
                'student__student_profile__student_id',
                'student__student_profile__department',
            )
            .annotate(
                avg_score=Avg('percentage'),
                exams_taken=Count('id'),
            )
            .filter(avg_score__lt=40.0)
            .order_by('avg_score')[:5]
        )
        low_scorers_list = [
            {
                'student_id': s['student__id'],
                'name': f"{s['student__first_name']} {s['student__last_name']}".strip() or s['student__username'],
                'roll_number': s.get('student__student_profile__student_id') or '-',
                'department': s.get('student__student_profile__department') or '-',
                'average_score': round(s['avg_score'], 1),
                'exams_taken': s['exams_taken'],
                'type': 'low_score',
                'issue': f"Average score {round(s['avg_score'], 1)}% (< 40%)",
            }
            for s in low_scorers_qs
        ]

        attempted_user_ids = set(
            StudentAttempt.objects.filter(
                exam__in=exams_qs,
                status__in=COMPLETED_STATUSES
            ).values_list('student_id', flat=True)
        )
        zero_attempt_students = (
            students_qs.exclude(user_id__in=attempted_user_ids)[:5]
        )
        unattempted_list = [
            {
                'student_id': p.user_id,
                'name': f"{p.user.first_name} {p.user.last_name}".strip() or p.user.username,
                'roll_number': p.student_id or '-',
                'department': p.department or 'Unassigned',
                'average_score': None,
                'exams_taken': 0,
                'type': 'unattempted',
                'issue': 'No exams taken yet',
            }
            for p in zero_attempt_students
        ]

        # 10. Activity Trend (daily breakdown for chart)
        trend_days = 14
        start_trend = now - datetime.timedelta(days=trend_days)
        date_buckets = {}
        for i in range(trend_days):
            day = (start_trend + datetime.timedelta(days=i + 1)).date()
            date_buckets[day] = {'date': day.strftime('%b %d'), 'exams_created': 0, 'attempts': 0}

        try:
            from django.db.models.functions import TruncDate

            for item in (
                exams_qs.filter(created_at__gte=start_trend)
                .annotate(day=TruncDate('created_at'))
                .values('day')
                .annotate(cnt=Count('id'))
            ):
                d_val = item.get('day')
                if d_val and d_val in date_buckets:
                    date_buckets[d_val]['exams_created'] = item['cnt']

            for item in (
                attempts_qs.filter(submitted_at__gte=start_trend)
                .annotate(day=TruncDate('submitted_at'))
                .values('day')
                .annotate(cnt=Count('id'))
            ):
                d_val = item.get('day')
                if d_val and d_val in date_buckets:
                    date_buckets[d_val]['attempts'] = item['cnt']
        except Exception as e:
            logger.warning(f"Error computing activity trend: {e}")

        activity_trend = list(date_buckets.values())

        # 11. Score Distribution
        dist_agg = attempts_qs.aggregate(
            r_0_40=Count('id', filter=Q(percentage__lt=40.0)),
            r_40_60=Count('id', filter=Q(percentage__gte=40.0, percentage__lt=60.0)),
            r_60_80=Count('id', filter=Q(percentage__gte=60.0, percentage__lt=80.0)),
            r_80_100=Count('id', filter=Q(percentage__gte=80.0)),
        )
        score_distribution = [
            {'range': '0-40%', 'count': dist_agg.get('r_0_40') or 0, 'label': 'Below Pass (<40%)'},
            {'range': '40-60%', 'count': dist_agg.get('r_40_60') or 0, 'label': 'Average (40-60%)'},
            {'range': '60-80%', 'count': dist_agg.get('r_60_80') or 0, 'label': 'Good (60-80%)'},
            {'range': '80-100%', 'count': dist_agg.get('r_80_100') or 0, 'label': 'Excellent (80-100%)'},
        ]

        # 12. Recent Activity (latest 10 system events)
        events = []
        for e in exams_qs.order_by('-created_at')[:4]:
            u = e.created_by
            events.append({
                'type': 'exam_created',
                'title': f"Exam created: {e.title}",
                'department': e.department,
                'actor': f"{u.first_name} {u.last_name}".strip() or u.username,
                'timestamp': e.created_at.isoformat(),
            })
        for a in attempts_qs.order_by('-submitted_at')[:4]:
            if a.submitted_at:
                events.append({
                    'type': 'exam_submitted',
                    'title': f"Exam submitted: {a.exam.title} ({round(a.percentage, 1)}%)",
                    'department': a.exam.department,
                    'actor': f"{a.student.first_name} {a.student.last_name}".strip() or a.student.username,
                    'timestamp': a.submitted_at.isoformat(),
                })
        for s in students_qs.order_by('-created_at')[:3]:
            events.append({
                'type': 'student_registered',
                'title': f"Student enrolled: {s.user.first_name} {s.user.last_name}".strip() or s.user.username,
                'department': s.department or 'Unassigned',
                'actor': s.student_id or s.user.username,
                'timestamp': s.created_at.isoformat(),
            })
        for f in faculty_qs.order_by('-created_at')[:3]:
            events.append({
                'type': 'faculty_registered',
                'title': f"Faculty appointed: {f.user.first_name} {f.user.last_name}".strip() or f.user.username,
                'department': f.department or 'Unassigned',
                'actor': f.employee_id or f.user.username,
                'timestamp': f.created_at.isoformat(),
            })
        events.sort(key=lambda x: x['timestamp'], reverse=True)
        recent_activity = events[:10]

        # 13. Pending Actions
        drafts = exams_qs.filter(status=Exam.Status.DRAFT)
        empty_exams = exams_qs.annotate(q_cnt=Count('questions')).filter(q_cnt=0)
        unassigned_students = students_qs.filter(Q(department__isnull=True) | Q(department=''))

        pending_actions = {
            'draft_exams_count': drafts.count(),
            'empty_exams_count': empty_exams.count(),
            'unassigned_students_count': unassigned_students.count(),
        }

        profile_data = {
            'name': f"{admin_user.first_name} {admin_user.last_name}".strip() or admin_user.username,
            'email': admin_user.email,
            'institution_name': institution.institution_name if institution else 'ExamAI Central',
            'institution_code': institution.institution_code if institution else '',
        }

        response_payload = {
            'status': 'success',
            'data': {
                'profile': profile_data,
                'stats': stats_data,
                'live_summary': live_summary,
                'live_total': live_total,
                'shown_count': shown_count,
                'has_more': has_more,
                'ongoing_exams': ongoing_exams_list,
                'upcoming_exams': upcoming_exams_list,
                'department_overview': dept_overview,
                'exams_per_faculty': faculty_rankings,
                'top_students': top_students_list,
                'at_risk_students': {
                    'low_scorers': low_scorers_list,
                    'unattempted_students': unattempted_list,
                },
                'activity_trend': activity_trend,
                'score_distribution': score_distribution,
                'recent_activity': recent_activity,
                'pending_actions': pending_actions,
                'departments': DEFAULT_DEPARTMENT_NAMES,
            }
        }

        if cache_key:
            try:
                cache.set(cache_key, response_payload, timeout=20)
            except Exception as e:
                logger.warning(f"Dashboard cache write failed: {e}")

        return Response(response_payload)


class LiveRosterView(APIView):
    """
    Drill-down endpoint for Admin: returns the student roster for a specific live exam.
    Returns eligible students categorized as not_started, in_progress, or submitted.
    Excludes students from other institutions and reports any ineligible attempts separately.
    """
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request, exam_id):
        from api.tenant import get_user_institution
        institution = getattr(request, 'tenant', None) or get_user_institution(request.user)
        if not institution:
            return Response(
                {'detail': 'Admin institution not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Multi-tenant isolation: strictly verify exam belongs to this institution
        exam = Exam.objects.filter(id=exam_id, institution=institution).select_related('created_by', 'institution').first()
        if not exam:
            return Response(
                {'detail': 'Exam not found or does not belong to your institution.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        from api.exams.eligibility import (
            COMPLETED_STATUSES,
            compute_live_exam_metrics,
            eligible_students_queryset,
            get_exam_canonical_department,
        )

        eligible_qs = eligible_students_queryset(exam).order_by('student_id', 'user__first_name')
        metrics = compute_live_exam_metrics(exam, eligible_students_qs=eligible_qs)

        # Attempts for this exam
        attempts = StudentAttempt.objects.filter(
            exam=exam,
        ).select_related('student', 'student__student_profile')

        attempts_map = {a.student_id: a for a in attempts}
        eligible_user_ids = set(eligible_qs.values_list('user_id', flat=True))

        status_filter = request.query_params.get('status', 'all').strip().lower()
        search_query = request.query_params.get('search', '').strip().lower()

        roster = []
        for sp in eligible_qs:
            att = attempts_map.get(sp.user_id)
            if att and att.status in COMPLETED_STATUSES:
                st = 'submitted'
            elif att and att.status == StudentAttempt.Status.IN_PROGRESS:
                st = 'in_progress'
            else:
                st = 'not_started'

            if status_filter != 'all' and st != status_filter:
                continue

            full_name = f"{sp.user.first_name} {sp.user.last_name}".strip() or sp.user.username
            roll = sp.student_id or '-'

            if search_query:
                if (
                    search_query not in full_name.lower()
                    and search_query not in roll.lower()
                    and search_query not in sp.user.email.lower()
                ):
                    continue

            roster.append({
                'student_id': roll,
                'user_id': sp.user_id,
                'name': full_name,
                'email': sp.user.email,
                'department': sp.department,
                'status': st,
                'started_at': att.started_at.isoformat() if att else None,
                'submitted_at': att.submitted_at.isoformat() if att and att.submitted_at else None,
                'score': att.total_score if att and att.status in COMPLETED_STATUSES else None,
            })

        # Track any attempts by students no longer eligible (e.g. transferred, deactivated, cross-tenant)
        ineligible_roster = []
        for att in attempts:
            if att.student_id not in eligible_user_ids:
                u = att.student
                sp = getattr(u, 'student_profile', None)
                if sp and sp.institution_id != exam.institution_id:
                    reason = 'Student belongs to a different institution'
                elif not u.is_active:
                    reason = 'Student account is inactive'
                else:
                    reason = 'Student department mismatch or transferred'

                ineligible_roster.append({
                    'student_id': sp.student_id if sp else '-',
                    'user_id': u.id,
                    'name': f"{u.first_name} {u.last_name}".strip() or u.username,
                    'email': u.email,
                    'department': sp.department if sp else 'Unknown',
                    'status': att.status,
                    'started_at': att.started_at.isoformat() if att else None,
                    'submitted_at': att.submitted_at.isoformat() if att and att.submitted_at else None,
                    'score': att.total_score if att.status in COMPLETED_STATUSES else None,
                    'reason': reason,
                })

        try:
            page = max(1, int(request.query_params.get('page', 1)))
        except (TypeError, ValueError):
            page = 1
        try:
            page_size = max(1, min(100, int(request.query_params.get('page_size', 20))))
        except (TypeError, ValueError):
            page_size = 20

        total_items = len(roster)
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paginated_roster = roster[start_idx:end_idx]

        return Response({
            'status': 'success',
            'data': {
                'exam': {
                    'id': exam.id,
                    'title': exam.title,
                    'department': get_exam_canonical_department(exam),
                    'faculty_name': metrics['faculty_name'],
                    'starts_at': metrics['starts_at'],
                    'ends_at': metrics['ends_at'],
                    'seconds_remaining': metrics['seconds_remaining'],
                },
                'metrics': metrics,
                'roster': paginated_roster,
                'ineligible_attempts': ineligible_roster,
                'pagination': {
                    'page': page,
                    'page_size': page_size,
                    'total_items': total_items,
                    'total_pages': max(1, (total_items + page_size - 1) // page_size),
                },
            }
        })

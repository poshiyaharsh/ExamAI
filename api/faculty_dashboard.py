import logging
import uuid
from django.db import models
from django.db.models import Avg, Count, ExpressionWrapper, F, FloatField, Q, Sum
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Exam, StudentAnswer, StudentAttempt
from .permissions import IsFacultyUser
from students.models import StudentProfile
from .utils.scoring import PASSING_PERCENTAGE

logger = logging.getLogger(__name__)

COMPLETED_STATUSES = [
    StudentAttempt.Status.SUBMITTED,
    StudentAttempt.Status.AUTO_SUBMITTED,
    StudentAttempt.Status.EVALUATED,
]


class FacultyDashboardView(APIView):
    permission_classes = [IsAuthenticated, IsFacultyUser]

    def get(self, request):
        req_id = str(uuid.uuid4())[:8]
        try:
            user = request.user
            now = timezone.now()
            from api.tenant import get_user_institution
            tenant = getattr(request, 'tenant', None) or get_user_institution(user)
            if not tenant:
                return Response({'status': 'error', 'message': 'No active institution found.'}, status=status.HTTP_400_BAD_REQUEST)
            return self._build_dashboard(request, user, tenant, now)
        except Exception as exc:
            logger.exception("[%s] Unexpected error in FacultyDashboardView: %s", req_id, exc)
            return Response({
                'status': 'error',
                'message': 'Failed to load faculty dashboard. Please try again.',
                'request_id': req_id,
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def _build_dashboard(self, request, user, tenant, now):
        faculty_profile = getattr(user, 'faculty_profile', None)
        dept = faculty_profile.department if faculty_profile else ''

        # 1. Profile information
        full_name = f"{user.first_name} {user.last_name}".strip() or user.username
        faculty_exams = Exam.objects.filter(created_by=user, institution=tenant)

        all_topics = set()
        for topics_list in faculty_exams.values_list('topics', flat=True):
            if isinstance(topics_list, list):
                for t in topics_list:
                    if str(t).strip():
                        all_topics.add(str(t).strip())
        subjects_taught = sorted(list(all_topics))

        profile_data = {
            'name': full_name,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'email': user.email,
            'department': dept or 'Unassigned',
            'designation': faculty_profile.designation if faculty_profile else '',
            'employee_id': faculty_profile.employee_id if faculty_profile else '',
            'subjects_taught': subjects_taught,
        }

        # 2. Stats
        total_exams = faculty_exams.count()
        published_exams = faculty_exams.filter(status=Exam.Status.PUBLISHED).count()
        draft_exams = faculty_exams.filter(status=Exam.Status.DRAFT).count()
        upcoming_exams_count = faculty_exams.filter(status=Exam.Status.PUBLISHED, starts_at__gt=now).count()
        ongoing_exams_count = faculty_exams.filter(
            status=Exam.Status.PUBLISHED
        ).filter(
            Q(starts_at__isnull=True) | Q(starts_at__lte=now),
            Q(ends_at__isnull=True) | Q(ends_at__gte=now),
        ).count()
        completed_exams_count = faculty_exams.filter(
            status=Exam.Status.PUBLISHED,
            ends_at__isnull=False,
            ends_at__lt=now,
        ).count()

        total_students = StudentProfile.objects.filter(institution=tenant, department__iexact=dept).count() if dept else 0

        pct_expr = ExpressionWrapper(
            F('total_score') * 100.0 / F('exam__total_marks'),
            output_field=FloatField()
        )

        faculty_attempts = StudentAttempt.objects.filter(
            institution=tenant,
            exam__created_by=user,
            status__in=COMPLETED_STATUSES,
        )

        attempt_stats = faculty_attempts.annotate(pct=pct_expr).aggregate(
            total_attempts=Count('id'),
            avg_score=Avg('pct'),
            pass_count=Count('id', filter=Q(pct__gte=PASSING_PERCENTAGE)),
            fail_count=Count('id', filter=Q(pct__lt=PASSING_PERCENTAGE)),
        )

        total_attempts = attempt_stats.get('total_attempts') or 0
        overall_avg = round(attempt_stats['avg_score'], 1) if attempt_stats.get('avg_score') is not None else None
        pass_count = attempt_stats.get('pass_count') or 0
        overall_pass_rate = round((pass_count / total_attempts) * 100.0, 1) if total_attempts > 0 else None

        stats_data = {
            'total_exams': total_exams,
            'published_exams': published_exams,
            'draft_exams': draft_exams,
            'upcoming_exams': upcoming_exams_count,
            'ongoing_exams': ongoing_exams_count,
            'completed_exams': completed_exams_count,
            'total_students': total_students,
            'total_attempts': total_attempts,
            'overall_average': overall_avg,
            'overall_pass_rate': overall_pass_rate,
            'pass_count': pass_count,
            'fail_count': attempt_stats.get('fail_count') or 0,
        }

        # 3. Ongoing Exams (currently live)
        ongoing_qs = faculty_exams.filter(
            status=Exam.Status.PUBLISHED
        ).filter(
            Q(starts_at__isnull=True) | Q(starts_at__lte=now),
            Q(ends_at__isnull=True) | Q(ends_at__gte=now),
        ).order_by('ends_at', '-created_at')[:5]

        from api.exams.eligibility import compute_live_exam_metrics

        ongoing_exams_list = []
        try:
            for e in ongoing_qs:
                m = compute_live_exam_metrics(e, now=now)
                m['subject'] = e.subject or (e.topics[0] if isinstance(e.topics, list) and e.topics else 'General Course')
                viol_stats = StudentAttempt.objects.filter(exam=e).aggregate(
                    total_violations=Sum('violation_count'),
                    flagged_students=Count('id', filter=Q(violation_count__gt=0)),
                )
                m['total_violations'] = viol_stats.get('total_violations') or 0
                m['flagged_students'] = viol_stats.get('flagged_students') or 0
                m['question_count'] = e.questions.filter(is_deleted=False).count()
                m['topics'] = e.topics[:2] if isinstance(e.topics, list) else []
                ongoing_exams_list.append(m)
        except Exception as ex:
            logger.warning("Error computing ongoing live exams: %s", ex, exc_info=True)

        # 4. Upcoming Exams (scheduled for future or next unattempted)
        upcoming_qs = faculty_exams.filter(
            status=Exam.Status.PUBLISHED,
            starts_at__gt=now,
        ).order_by('starts_at', 'id')[:5]

        if not upcoming_qs.exists():
            upcoming_qs = faculty_exams.filter(status=Exam.Status.PUBLISHED).order_by('-created_at')[:5]

        upcoming_exams_list = []
        for e in upcoming_qs:
            upcoming_exams_list.append({
                'id': e.id,
                'title': e.title,
                'subject': e.subject or (e.topics[0] if isinstance(e.topics, list) and e.topics else 'General Course'),
                'department': e.department,
                'duration_minutes': e.duration_minutes,
                'total_marks': e.total_marks,
                'starts_at': e.starts_at.isoformat() if e.starts_at else None,
                'ends_at': e.ends_at.isoformat() if e.ends_at else None,
                'eligible_students': total_students,
            })

        # 5. Recent Exams (last 5 created by faculty)
        recent_exams_qs = faculty_exams.order_by('-created_at')[:5]
        recent_exams_list = []
        for e in recent_exams_qs:
            e_attempts = StudentAttempt.objects.filter(exam=e, status__in=COMPLETED_STATUSES)
            e_stats = e_attempts.annotate(pct=pct_expr).aggregate(
                cnt=Count('id'),
                avg=Avg('pct'),
                passes=Count('id', filter=Q(pct__gte=PASSING_PERCENTAGE)),
            )
            cnt = e_stats.get('cnt') or 0
            e_avg = round(e_stats['avg'], 1) if e_stats.get('avg') is not None else None
            passes = e_stats.get('passes') or 0
            e_pass_rate = round((passes / cnt) * 100.0, 1) if cnt > 0 else None

            needs_attention = False
            attention_reason = ""
            if not e.is_reviewed and e.status == Exam.Status.DRAFT:
                needs_attention = True
                attention_reason = "Review required"
            elif e.marks_shortfall and e.marks_shortfall > 0:
                needs_attention = True
                attention_reason = f"{e.marks_shortfall} short"

            recent_exams_list.append({
                'id': e.id,
                'title': e.title,
                'subject': e.subject or (e.topics[0] if isinstance(e.topics, list) and e.topics else 'General Course'),
                'department': e.department,
                'created_at': e.created_at.isoformat(),
                'status': e.status,
                'question_count': e.questions.filter(is_deleted=False).count(),
                'total_marks': e.total_marks,
                'target_total_marks': e.target_total_marks or e.total_marks,
                'marks_shortfall': e.marks_shortfall or 0,
                'attempts_count': cnt,
                'average_score': e_avg,
                'pass_rate': e_pass_rate,
                'is_reviewed': e.is_reviewed,
                'needs_attention': needs_attention,
                'attention_reason': attention_reason,
                'topics': e.topics if isinstance(e.topics, list) else [],
            })

        # 6. Exam Performance for Bar Chart (last 8-10 published exams)
        perf_exams = list(faculty_exams.filter(status=Exam.Status.PUBLISHED).order_by('-created_at')[:8])
        perf_exams.reverse()
        exam_perf_data = []
        for e in perf_exams:
            e_attempts = StudentAttempt.objects.filter(exam=e, status__in=COMPLETED_STATUSES)
            avg_val = e_attempts.annotate(pct=pct_expr).aggregate(avg=Avg('pct')).get('avg')
            exam_perf_data.append({
                'id': e.id,
                'exam_title': e.title,
                'average_score': round(avg_val, 1) if avg_val is not None else 0.0,
                'attempts_count': e_attempts.count(),
            })

        # 7. Score Distribution
        dist_agg = faculty_attempts.annotate(pct=pct_expr).aggregate(
            r_0_40=Count('id', filter=Q(pct__lt=40.0)),
            r_40_60=Count('id', filter=Q(pct__gte=40.0, pct__lt=60.0)),
            r_60_80=Count('id', filter=Q(pct__gte=60.0, pct__lt=80.0)),
            r_80_100=Count('id', filter=Q(pct__gte=80.0)),
        )
        score_distribution = [
            {'range': '0-40%', 'count': dist_agg.get('r_0_40') or 0, 'label': 'Below Pass (<40%)'},
            {'range': '40-60%', 'count': dist_agg.get('r_40_60') or 0, 'label': 'Average (40-60%)'},
            {'range': '60-80%', 'count': dist_agg.get('r_60_80') or 0, 'label': 'Good (60-80%)'},
            {'range': '80-100%', 'count': dist_agg.get('r_80_100') or 0, 'label': 'Excellent (80-100%)'},
        ]

        # 8. Top Performers
        top_qs = (
            faculty_attempts.values(
                'student__id',
                'student__first_name',
                'student__last_name',
                'student__username',
                'student__student_profile__student_id',
                'student__student_profile__department',
            )
            .annotate(
                avg_score=Avg(pct_expr),
                exams_taken=Count('id'),
            )
            .order_by('-avg_score')[:5]
        )
        top_performers_list = []
        for s in top_qs:
            s_name = f"{s['student__first_name']} {s['student__last_name']}".strip() or s['student__username']
            top_performers_list.append({
                'student_id': s['student__id'],
                'name': s_name,
                'roll_number': s.get('student__student_profile__student_id') or '-',
                'department': s.get('student__student_profile__department') or '-',
                'average_score': round(s['avg_score'], 1) if s.get('avg_score') is not None else 0.0,
                'exams_taken': s['exams_taken'],
            })

        # 9. Needs Attention (Low scorers + unattempted students)
        low_qs = (
            faculty_attempts.values(
                'student__id',
                'student__first_name',
                'student__last_name',
                'student__username',
                'student__student_profile__student_id',
                'student__student_profile__department',
            )
            .annotate(
                avg_score=Avg(pct_expr),
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
            for s in low_qs
        ]

        unattempted_list = []
        if dept:
            attempted_student_ids = set(
                StudentAttempt.objects.filter(institution=tenant, exam__department__iexact=dept).values_list('student_id', flat=True)
            )
            unattempted_students = (
                StudentProfile.objects.filter(institution=tenant, department__iexact=dept)
                .exclude(user_id__in=attempted_student_ids)
                .select_related('user')[:5]
            )
            unattempted_list = [
                {
                    'student_id': p.user_id,
                    'name': f"{p.user.first_name} {p.user.last_name}".strip() or p.user.username,
                    'roll_number': p.student_id or '-',
                    'department': p.department,
                    'average_score': None,
                    'exams_taken': 0,
                    'type': 'unattempted',
                    'issue': 'No department exams taken yet',
                }
                for p in unattempted_students
            ]

        # 10. Hardest Questions
        hardest_qs = (
            StudentAnswer.objects.filter(
                institution=tenant,
                attempt__exam__created_by=user,
                attempt__status__in=COMPLETED_STATUSES,
            )
            .values(
                'question_id',
                'question__text',
                'question__topic',
                'question__difficulty',
                'question__exam__title',
                'question__exam__id',
            )
            .annotate(
                total_answers=Count('id'),
                wrong_answers=Count('id', filter=Q(is_correct=False)),
            )
            .filter(wrong_answers__gt=0)
            .order_by('-wrong_answers', '-total_answers')[:5]
        )
        hardest_questions_list = []
        for q in hardest_qs:
            tot = q['total_answers']
            wrg = q['wrong_answers']
            error_rate = round((wrg / tot) * 100.0, 1) if tot > 0 else 0.0
            hardest_questions_list.append({
                'question_id': q['question_id'],
                'exam_id': q['question__exam__id'],
                'exam_title': q['question__exam__title'],
                'text': q['question__text'],
                'topic': q['question__topic'] or 'General',
                'difficulty': q['question__difficulty'],
                'total_answers': tot,
                'wrong_answers': wrg,
                'error_rate': error_rate,
            })

        # 11. Pending Actions (Drafts & Empty Exams)
        drafts = faculty_exams.filter(status=Exam.Status.DRAFT)
        empty_exams = faculty_exams.annotate(q_cnt=Count('questions')).filter(q_cnt=0)
        pending_actions = {
            'draft_exams_count': drafts.count(),
            'drafts': [
                {'id': d.id, 'title': d.title, 'created_at': d.created_at.isoformat()}
                for d in drafts[:5]
            ],
            'empty_exams_count': empty_exams.count(),
            'empty_exams': [
                {'id': em.id, 'title': em.title}
                for em in empty_exams[:5]
            ],
        }

        return Response({
            'status': 'success',
            'data': {
                'profile': profile_data,
                'stats': stats_data,
                'ongoing_exams': ongoing_exams_list,
                'upcoming_exams': upcoming_exams_list,
                'recent_exams': recent_exams_list,
                'exam_performance': exam_perf_data,
                'score_distribution': score_distribution,
                'top_performers': top_performers_list,
                'needs_attention': {
                    'low_scorers': low_scorers_list,
                    'unattempted_students': unattempted_list,
                },
                'hardest_questions': hardest_questions_list,
                'pending_actions': pending_actions,
            }
        })

"""
Faculty Live Exam Real-Time Monitoring API.
Strictly scoped to exam creator faculty and their department (IDOR protected).
Never exposes student answers, questions rubrics, or private keys.
"""

import logging
from django.db.models import Count
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .exam_management import FacultyExamViewMixin
from .models import Exam, StudentAttempt, StudentAnswer, AttemptEvent
from .exams.eligibility import compute_live_exam_metrics, eligible_students_queryset

logger = logging.getLogger(__name__)


class FacultyLiveMonitorView(FacultyExamViewMixin, APIView):
    """
    Real-time monitoring endpoint for a live exam.
    Returns:
    - Exam configuration & window status (server_now, seconds_remaining, is_live)
    - Participation summary tiles (strictly invariant counts)
    - Full eligible student roster with live progress, violation counts, and event timeline
    """
    def get(self, request, exam_id):
        exam = self.get_exam(request, exam_id)
        if not exam:
            return Response(
                {'detail': 'Exam not found or you do not have permission to monitor it.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        now = timezone.now()

        # 1. Summary metrics
        metrics = compute_live_exam_metrics(exam, now=now)
        total_questions = exam.questions.filter(is_deleted=False).count()

        # 2. Eligible students & attempt mapping
        eligible_qs = eligible_students_queryset(exam).select_related('user').order_by('user__last_name', 'user__first_name')
        
        attempts = list(
            StudentAttempt.objects.filter(exam=exam).select_related('student')
        )
        attempts_by_student = {att.student_id: att for att in attempts}

        # 3. Questions answered per attempt
        answered_counts = dict(
            StudentAnswer.objects.filter(attempt__exam=exam)
            .exclude(answer_text='', blank_answers=[], selected_option_order=None)
            .values('attempt_id')
            .annotate(cnt=Count('id'))
            .values_list('attempt_id', 'cnt')
        )

        # 4. Proctored violation events grouped by attempt for drawer timeline
        events_by_attempt = {}
        for ev in AttemptEvent.objects.filter(attempt__exam=exam).order_by('-timestamp'):
            events_by_attempt.setdefault(ev.attempt_id, []).append({
                'id': ev.id,
                'event_type': ev.event_type,
                'event_label': ev.get_event_type_display(),
                'metadata': ev.metadata,
                'timestamp': ev.timestamp.isoformat(),
            })

        # 5. Build live student roster
        roster = []
        for sp in eligible_qs:
            u = sp.user
            att = attempts_by_student.get(u.id)

            if not att:
                st = 'not_started'
                answered = 0
                time_left_sec = (exam.duration_minutes or 60) * 60
                viol_cnt = 0
                last_activity = None
                att_id = None
                timeline = []
                submit_reason = None
            else:
                st = att.status
                att_id = att.id
                answered = answered_counts.get(att.id, 0)
                viol_cnt = att.violation_count
                timeline = events_by_attempt.get(att.id, [])
                submit_reason = att.submit_reason
                
                if att.submitted_at:
                    last_activity = att.submitted_at.isoformat()
                elif timeline:
                    last_activity = timeline[0]['timestamp']
                else:
                    last_activity = att.started_at.isoformat()

                if att.status in {StudentAttempt.Status.SUBMITTED, StudentAttempt.Status.AUTO_SUBMITTED, StudentAttempt.Status.EVALUATED}:
                    time_left_sec = 0
                elif att.expires_at:
                    time_left_sec = max(0, int((att.expires_at - now).total_seconds()))
                else:
                    elapsed = int((now - att.started_at).total_seconds())
                    time_left_sec = max(0, ((exam.duration_minutes or 60) * 60) - elapsed)

            roster.append({
                'student_user_id': u.id,
                'student_id': sp.student_id or f"STU-{u.id:04d}",
                'name': f"{u.first_name} {u.last_name}".strip() or u.username,
                'email': u.email,
                'department': sp.department,
                'status': st,
                'submit_reason': submit_reason,
                'questions_answered': answered,
                'total_questions': total_questions,
                'progress_percent': round((answered / total_questions) * 100.0, 1) if total_questions > 0 else 0.0,
                'time_left_seconds': time_left_sec,
                'violation_count': viol_cnt,
                'last_activity': last_activity,
                'attempt_id': att_id,
                'violations_timeline': timeline,
            })

        # Check if exam is actively live
        is_live = exam.status == Exam.Status.PUBLISHED
        if is_live and exam.starts_at and now < exam.starts_at:
            is_live = False
        if is_live and exam.ends_at and now > exam.ends_at:
            is_live = False

        return Response({
            'status': 'success',
            'data': {
                'exam': {
                    'id': exam.id,
                    'title': exam.title,
                    'subject': exam.subject or (exam.topics[0] if isinstance(exam.topics, list) and exam.topics else 'General Course'),
                    'department': metrics['department'],
                    'status': exam.status,
                    'is_live': is_live,
                    'duration_minutes': exam.duration_minutes,
                    'total_marks': exam.total_marks,
                    'max_warnings': exam.max_warnings,
                    'starts_at': metrics['starts_at'],
                    'ends_at': metrics['ends_at'],
                    'seconds_remaining': metrics['seconds_remaining'],
                    'window_total_seconds': metrics.get('window_total_seconds'),
                    'server_now': now.isoformat(),
                    'total_questions': total_questions,
                },
                'summary': {
                    'assigned_total': metrics['assigned_total'],
                    'in_progress': metrics['in_progress'],
                    'submitted': metrics['submitted'],
                    'not_started': metrics['not_started'],
                    'flagged_students': metrics['flagged_students'],
                    'total_violations': metrics['total_violations'],
                    'participation_percent': metrics['participation_percent'],
                },
                'roster': roster,
            }
        })

"""
Shared Server-Side Analytics & Visualization Engine for ExamAI.

Single source of truth for:
- Classification thresholds (Strong >= 75%, Average 50-74.9%, Needs Focus < 50%)
- Student performance subject & topic breakdown
- Faculty exam performance overview
- Cohort privacy protections (minimum cohort size of 5)
- Safe zero/divide-by-zero handling
- Fully-graded attempt gating (quarantining pending grading & not attempted)
"""

import logging
from typing import Any, Dict, List, Optional, Tuple
from django.db.models import Avg, Count, Max, Min, Q
from django.utils import timezone
from .results import compute_attempt_result_status, ResultStatusCode
from .scoring import PASSING_PERCENTAGE

logger = logging.getLogger(__name__)

# Canonical classification thresholds shared across all charts
CLASSIFICATION_CONFIG = {
    'STRONG': {
        'code': 'strong',
        'label': 'Strong',
        'color': '#10B981',  # Emerald
        'token': 'emerald',
        'min': 75.0,
    },
    'AVERAGE': {
        'code': 'average',
        'label': 'Average',
        'color': '#3B82F6',  # Blue
        'token': 'blue',
        'min': 50.0,
        'max': 74.9,
    },
    'NEEDS_FOCUS': {
        'code': 'needs_focus',
        'label': 'Needs Focus',
        'color': '#F59E0B',  # Amber
        'token': 'amber',
        'max': 49.9,
    },
    'NO_RESULTS': {
        'code': 'no_results',
        'label': 'No Graded Results',
        'color': '#9CA3AF',  # Muted Slate
        'token': 'muted',
    },
}

MIN_COHORT_SIZE = 5


def classify_score(percentage: Optional[float]) -> Dict[str, Any]:
    """
    Returns single canonical classification dictionary for a given score percentage.
    """
    if percentage is None:
        return CLASSIFICATION_CONFIG['NO_RESULTS'].copy()
    try:
        pct = round(float(percentage), 1)
    except (ValueError, TypeError):
        return CLASSIFICATION_CONFIG['NO_RESULTS'].copy()

    if pct >= CLASSIFICATION_CONFIG['STRONG']['min']:
        return {**CLASSIFICATION_CONFIG['STRONG'], 'value': pct}
    if pct >= CLASSIFICATION_CONFIG['AVERAGE']['min']:
        return {**CLASSIFICATION_CONFIG['AVERAGE'], 'value': pct}
    return {**CLASSIFICATION_CONFIG['NEEDS_FOCUS'], 'value': pct}


def resolve_short_subject(exam: Any) -> str:
    """
    Determines clean, short subject name for an exam without topic pollution.
    Fallbacks: exam.subject -> question bank subject -> clean title -> department -> 'General Course'.
    """
    subj = getattr(exam, 'subject', None)
    if subj and str(subj).strip():
        s = str(subj).strip()
        if ',' in s:
            s = s.split(',')[0].strip()
        if not s.lower().startswith('exam_'):
            return s[:60]

    # Check question bank subject if available
    if hasattr(exam, 'questions'):
        try:
            q_subj = exam.questions.filter(
                subject__isnull=False, is_deleted=False
            ).values_list('subject__name', flat=True).first()
            if q_subj and str(q_subj).strip():
                return str(q_subj).strip()[:60]
        except Exception:
            pass

    # Clean from title (stripping CH_..., Unit..., etc.)
    title = getattr(exam, 'title', '') or ''
    clean_t = (
        title.split(" - ")[0]
        .split(" CH_")[0]
        .split(" Ch_")[0]
        .split(" Unit")[0]
        .split(" unit")[0]
        .strip()
    )
    if clean_t and not clean_t.lower().startswith('exam_'):
        return clean_t[:60]

    dept = getattr(exam, 'department', '')
    if dept and str(dept).strip():
        return str(dept).strip()[:60]

    return title[:60] or 'General Course'


def is_attempt_fully_graded(attempt: Any) -> Tuple[bool, str]:
    """
    Checks if an attempt is 100% graded.
    Returns (is_graded, state_code) where state_code is:
    'graded', 'pending_grading', 'in_progress', 'expired', 'not_attempted'.
    """
    if not attempt:
        return False, 'not_attempted'

    status_str = str(getattr(attempt, 'status', '')).lower()
    if status_str in {'in_progress', 'started'}:
        expires_at = getattr(attempt, 'expires_at', None)
        if expires_at and timezone.now() > expires_at:
            return False, 'expired'
        return False, 'in_progress'

    if status_str == 'submitted':
        return False, 'pending_grading'

    if status_str == 'evaluated':
        return True, 'graded'

    if status_str == 'auto_submitted':
        # If auto_submitted, check if any answered question has not been scored yet
        if hasattr(attempt, 'answers'):
            try:
                from api.models import StudentAnswer
                unscored = attempt.answers.filter(
                    score_awarded__isnull=True
                ).exclude(
                    answer_text='', blank_answers=[]
                ).exists()
                if unscored:
                    return False, 'pending_grading'
            except Exception:
                pass
        return True, 'graded'

    return False, 'pending_grading'


def compute_student_subjects_breakdown(
    user: Any,
    tenant: Any,
) -> Dict[str, Any]:
    """
    Computes rigorous student subject performance breakdown.
    - Includes ONLY fully-graded completed attempts on published exams.
    - Quarantines pending grading and missed exams.
    - Calculates genuine per-question topic data if available; never fakes topics.
    - Cohort average enforced by privacy rule (>= 5 students).
    """
    from api.models import Exam, StudentAttempt, StudentAnswer
    from api.utils.departments import get_student_department

    student_dept = get_student_department(user)
    now = timezone.now()

    # 1. Base query for all published exams accessible to student
    exams_qs = Exam.objects.filter(
        institution=tenant,
        status=Exam.Status.PUBLISHED,
    )
    if student_dept:
        exams_qs = exams_qs.filter(department__iexact=student_dept)

    # 2. Student attempts query
    attempts_qs = StudentAttempt.objects.filter(
        student=user,
        institution=tenant,
        exam__in=exams_qs,
    ).select_related('exam')

    attempts_by_exam: Dict[int, List[Any]] = {}
    for att in attempts_qs:
        attempts_by_exam.setdefault(att.exam_id, []).append(att)

    # 3. Subject-level buckets
    subjects_map: Dict[str, Dict[str, Any]] = {}
    total_pending_count = 0
    total_missed_count = 0

    for exam in exams_qs:
        clean_subj = resolve_short_subject(exam)
        if clean_subj not in subjects_map:
            subjects_map[clean_subj] = {
                'subject': clean_subj,
                'graded_exams': [],
                'pending_exams_count': 0,
                'missed_exams_count': 0,
                'exam_ids': set(),
                'question_topics': {},  # topic_name -> {'awarded': float, 'total': float}
            }
        bucket = subjects_map[clean_subj]
        bucket['exam_ids'].add(exam.id)

        exam_attempts = attempts_by_exam.get(exam.id, [])
        if not exam_attempts:
            # Check if exam window ended (missed) or currently open
            bucket['missed_exams_count'] += 1
            total_missed_count += 1
            continue

        # Get latest attempt
        latest_attempt = max(exam_attempts, key=lambda a: a.started_at or now)
        is_graded, state_code = is_attempt_fully_graded(latest_attempt)

        if not is_graded:
            if state_code == 'pending_grading':
                bucket['pending_exams_count'] += 1
                total_pending_count += 1
            else:
                bucket['missed_exams_count'] += 1
                total_missed_count += 1
            continue

        # Attempt is fully graded! Compute percentage safely
        tot_marks = float(latest_attempt.max_score or exam.total_marks or 0.0)
        score = float(latest_attempt.total_score or 0.0)
        if tot_marks > 0:
            pct = round((score / tot_marks) * 100.0, 1)
        else:
            pct = 0.0

        bucket['graded_exams'].append({
            'exam_id': exam.id,
            'exam_title': exam.title,
            'percentage': pct,
            'score': score,
            'total_marks': tot_marks,
            'attempt_id': latest_attempt.id,
        })

        # Check real question-level topic data from StudentAnswers
        answers = StudentAnswer.objects.filter(
            attempt=latest_attempt,
            question__is_deleted=False,
        ).select_related('question', 'question__topic')

        for ans in answers:
            q = ans.question
            # Determine topic name
            t_name = ""
            if q.topic and q.topic.name and q.topic.name.strip():
                t_name = q.topic.name.strip()
            elif q.topic_text and q.topic_text.strip():
                t_name = q.topic_text.strip()

            # Ignore placeholder topic tags like "Topic_01", "Exam_01", etc.
            if t_name and not t_name.lower().startswith(('topic_', 'exam_')):
                q_marks = float(q.marks or 1.0)
                a_score = float(ans.score_awarded or 0.0) if ans.score_awarded is not None else 0.0
                if t_name not in bucket['question_topics']:
                    bucket['question_topics'][t_name] = {'awarded': 0.0, 'total': 0.0, 'count': 0}
                bucket['question_topics'][t_name]['awarded'] += a_score
                bucket['question_topics'][t_name]['total'] += q_marks
                bucket['question_topics'][t_name]['count'] += 1

    # 4. Cohort Class Averages (Enforce Privacy Rule: cohort >= 5)
    cohort_averages_by_subject: Dict[str, Optional[float]] = {}
    if student_dept:
        try:
            # Query all fully evaluated attempts in this department across all students
            dept_graded = StudentAttempt.objects.filter(
                institution=tenant,
                exam__status=Exam.Status.PUBLISHED,
                exam__department__iexact=student_dept,
                status=StudentAttempt.Status.EVALUATED,
            ).select_related('exam')

            dept_subj_students: Dict[str, set] = {}
            dept_subj_scores: Dict[str, List[float]] = {}

            for a in dept_graded:
                clean_s = resolve_short_subject(a.exam)
                t_m = float(a.max_score or a.exam.total_marks or 0.0)
                if t_m > 0:
                    pct = (float(a.total_score or 0.0) / t_m) * 100.0
                    dept_subj_students.setdefault(clean_s, set()).add(a.student_id)
                    dept_subj_scores.setdefault(clean_s, []).append(pct)

            for s_name, students_set in dept_subj_students.items():
                if len(students_set) >= MIN_COHORT_SIZE:
                    scores_list = dept_subj_scores.get(s_name, [])
                    cohort_averages_by_subject[s_name] = round(sum(scores_list) / len(scores_list), 1) if scores_list else None
                else:
                    cohort_averages_by_subject[s_name] = None
        except Exception as e:
            logger.warning("Error computing cohort averages: %s", e)

    # 5. Format Subject Performance Output
    active_subjects_list = []
    unattempted_subjects_list = []

    for s_name, data in subjects_map.items():
        graded_list = data['graded_exams']
        if graded_list:
            scores = [g['percentage'] for g in graded_list]
            avg_score = round(sum(scores) / len(scores), 1)
            highest_g = max(graded_list, key=lambda g: g['percentage'])
            lowest_g = min(graded_list, key=lambda g: g['percentage'])

            # Topic breakdown if real question-level topic data exists
            topics_data = []
            has_topic_data = False
            if data['question_topics']:
                has_topic_data = True
                for top_name, top_stats in sorted(data['question_topics'].items()):
                    if top_stats['total'] > 0:
                        top_pct = round((top_stats['awarded'] / top_stats['total']) * 100.0, 1)
                    else:
                        top_pct = 0.0
                    topics_data.append({
                        'topic': top_name,
                        'average_score': top_pct,
                        'questions_count': top_stats['count'],
                        'classification': classify_score(top_pct),
                    })
                # Sort topics: weakest first for actionable focus
                topics_data.sort(key=lambda t: t['average_score'])

            active_subjects_list.append({
                'subject': s_name,
                'average_score': avg_score,
                'exams_counted': len(graded_list),
                'highest_score': highest_g['percentage'],
                'lowest_score': lowest_g['percentage'],
                'best_exam_title': highest_g['exam_title'],
                'worst_exam_title': lowest_g['exam_title'],
                'classification': classify_score(avg_score),
                'cohort_average': cohort_averages_by_subject.get(s_name),
                'pending_exams_count': data['pending_exams_count'],
                'missed_exams_count': data['missed_exams_count'],
                'has_topic_data': has_topic_data,
                'topics': topics_data,
            })
        else:
            unattempted_subjects_list.append({
                'subject': s_name,
                'exams_total': len(data['exam_ids']),
                'pending_exams_count': data['pending_exams_count'],
                'missed_exams_count': data['missed_exams_count'],
                'status': 'pending_grading' if data['pending_exams_count'] > 0 else 'no_attempts',
            })

    # Sort active subjects: weakest first by default
    active_subjects_list.sort(key=lambda s: s['average_score'])

    # Build genuine insight string
    if active_subjects_list:
        strongest_subj = max(active_subjects_list, key=lambda s: s['average_score'])
        weakest_subj = min(active_subjects_list, key=lambda s: s['average_score'])
        if len(active_subjects_list) == 1:
            insight_str = f"{strongest_subj['subject']}: {strongest_subj['average_score']}% average."
        elif strongest_subj['average_score'] == weakest_subj['average_score']:
            insight_str = f"Consistent performance across all {len(active_subjects_list)} subjects ({strongest_subj['average_score']}%)."
        else:
            insight_str = (
                f"Strongest: {strongest_subj['subject']} ({strongest_subj['average_score']}%). "
                f"Needs focus: {weakest_subj['subject']} ({weakest_subj['average_score']}%)."
            )
        strongest_label = f"{strongest_subj['subject']} ({strongest_subj['average_score']}%)"
        weakest_label = f"{weakest_subj['subject']} ({weakest_subj['average_score']}%)" if len(active_subjects_list) > 1 else None
    else:
        insight_str = "No graded exam results recorded yet."
        strongest_label = None
        weakest_label = None

    excluded_note = ""
    if total_pending_count > 0:
        plural = "exams are" if total_pending_count > 1 else "exam is"
        excluded_note = f"{total_pending_count} {plural} pending grading and not included in subject averages."

    return {
        'title': 'Subject Performance',
        'subjects': active_subjects_list,
        'unattempted_subjects': unattempted_subjects_list,
        'strongest_subject': strongest_label,
        'weakest_subject': weakest_label,
        'insight': insight_str,
        'total_graded_subjects': len(active_subjects_list),
        'total_pending_exams': total_pending_count,
        'total_missed_exams': total_missed_count,
        'excluded_exams_note': excluded_note,
        'thresholds': {
            'strong': CLASSIFICATION_CONFIG['STRONG']['min'],
            'average': CLASSIFICATION_CONFIG['AVERAGE']['min'],
            'needs_focus': 0.0,
        },
        'generated_at': now.isoformat(),
    }


def compute_faculty_exam_performance_overview(
    user: Any,
    tenant: Any,
    limit: int = 8,
) -> Dict[str, Any]:
    """
    Computes rigorous faculty 'Exam Performance Overview' data.
    - Most recent N published exams created by the faculty.
    - Accurately reports class average only from fully-graded attempts.
    - Exams with 0 submissions or pending grading return status & average: null (NEVER 0.0).
    - Summary badge counts accurately (e.g. '8 exams · 2 with results').
    """
    from api.models import Exam, StudentAttempt
    from students.models import StudentProfile

    now = timezone.now()
    faculty_profile = getattr(user, 'faculty_profile', None)
    dept = faculty_profile.department if faculty_profile else ''

    # Total eligible students in faculty's department
    eligible_students = (
        StudentProfile.objects.filter(institution=tenant, department__iexact=dept).count()
        if dept else 0
    )

    # 1. Recent published exams
    faculty_exams = Exam.objects.filter(
        created_by=user,
        institution=tenant,
        status=Exam.Status.PUBLISHED,
    ).order_by('-created_at')[:limit]

    # Chronological or reverse creation order
    exams_list = list(faculty_exams)
    exams_list.reverse()

    perf_data = []
    exams_with_results_count = 0

    for exam in exams_list:
        clean_subj = resolve_short_subject(exam)
        attempts = StudentAttempt.objects.filter(
            exam=exam,
            institution=tenant,
        )

        total_attempts_count = attempts.count()
        graded_scores: List[float] = []
        pending_count = 0

        for att in attempts:
            is_graded, state_code = is_attempt_fully_graded(att)
            if is_graded:
                tot = float(att.max_score or exam.total_marks or 0.0)
                if tot > 0:
                    score = float(att.total_score or 0.0)
                    graded_scores.append(round((score / tot) * 100.0, 1))
            elif state_code == 'pending_grading':
                pending_count += 1

        fully_graded_count = len(graded_scores)
        not_attempted_count = max(0, eligible_students - total_attempts_count)

        if fully_graded_count > 0:
            exams_with_results_count += 1
            avg_score = round(sum(graded_scores) / fully_graded_count, 1)
            high_score = max(graded_scores)
            low_score = min(graded_scores)
            pass_count = sum(1 for s in graded_scores if s >= PASSING_PERCENTAGE)
            pass_rate = round((pass_count / fully_graded_count) * 100.0, 1)
            exam_status = 'has_results'
            classification = classify_score(avg_score)
        elif pending_count > 0:
            avg_score = None
            high_score = None
            low_score = None
            pass_rate = None
            exam_status = 'pending_grading'
            classification = classify_score(None)
        else:
            avg_score = None
            high_score = None
            low_score = None
            pass_rate = None
            exam_status = 'no_submissions'
            classification = classify_score(None)

        perf_data.append({
            'id': exam.id,
            'exam_title': exam.title,
            'subject': clean_subj,
            'department': exam.department or dept,
            'status': exam_status,
            'average_score': avg_score,
            'highest_score': high_score,
            'lowest_score': low_score,
            'pass_rate': pass_rate,
            'passing_percentage': PASSING_PERCENTAGE,
            'submissions_count': total_attempts_count,
            'attempts_count': total_attempts_count,
            'graded_count': fully_graded_count,
            'eligible_students_count': eligible_students,
            'pending_grading_count': pending_count,
            'not_attempted_count': not_attempted_count,
            'ends_at': exam.ends_at.isoformat() if exam.ends_at else None,
            'starts_at': exam.starts_at.isoformat() if exam.starts_at else None,
            'created_at': exam.created_at.isoformat(),
            'classification': classification,
        })

    total_returned = len(perf_data)
    badge_text = (
        f"{total_returned} exams \u00b7 {exams_with_results_count} with results"
        if total_returned > 0
        else "0 exams"
    )

    return {
        'exams': perf_data,
        'summary': {
            'total_exams': total_returned,
            'with_results': exams_with_results_count,
            'badge_text': badge_text,
            'thresholds': {
                'strong': CLASSIFICATION_CONFIG['STRONG']['min'],
                'average': CLASSIFICATION_CONFIG['AVERAGE']['min'],
                'needs_focus': 0.0,
            },
        },
        'generated_at': now.isoformat(),
    }

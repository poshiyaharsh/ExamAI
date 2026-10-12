import logging
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)

PASSING_PERCENTAGE = 40.0


def normalize_text(value):
    if value is None:
        return ""
    return " ".join(str(value).split()).casefold()


def is_objective_question(question):
    return question.question_type in {"mcq", "truefalse", "fillblank"}


def is_objective_answer_correct(question, answer_text):
    submitted = normalize_text(answer_text)
    if not submitted:
        return False

    raw_correct = question.correct_answer
    options = question.options or []
    norm_options = [normalize_text(opt) for opt in options]

    # 1. Direct text match with correct_answer
    if submitted == normalize_text(raw_correct):
        return True

    # 2. True/False question handling
    if question.question_type == "truefalse":
        if isinstance(raw_correct, bool):
            expected = "true" if raw_correct else "false"
            return submitted == expected
        norm_correct = normalize_text(raw_correct)
        if norm_correct in {"a", "true"}:
            return submitted == "true"
        if norm_correct in {"b", "false"}:
            return submitted == "false"

    # 3. Letter choice ('A', 'B', 'C', 'D')
    letter_map = {"A": 0, "B": 1, "C": 2, "D": 3}
    correct_str = str(raw_correct or "").strip().upper()
    if correct_str in letter_map:
        idx = letter_map[correct_str]
        if idx < len(norm_options):
            if submitted == norm_options[idx]:
                return True
        if submitted == correct_str.lower():
            return True

    # 4. Integer index (0-based or 1-based)
    if isinstance(raw_correct, int) or (isinstance(raw_correct, str) and str(raw_correct).strip().isdigit()):
        num = int(raw_correct)
        # Check 0-based index
        if 0 <= num < len(norm_options) and submitted == norm_options[num]:
            return True
        # Check 1-based index
        if 1 <= num <= len(norm_options) and submitted == norm_options[num - 1]:
            return True

    # 5. Reverse check: if submitted is a letter ('A', 'B', 'C', 'D') and matches raw_correct text
    submitted_upper = submitted.upper()
    if submitted_upper in letter_map:
        idx = letter_map[submitted_upper]
        if idx < len(norm_options):
            if norm_options[idx] == normalize_text(raw_correct):
                return True

    # 6. If raw_correct matched one of options, and submitted is that option
    for opt in norm_options:
        if opt == normalize_text(raw_correct) and submitted == opt:
            return True

    return False


def calculate_and_save_attempt_score(attempt, is_auto_submit=False):
    """
    Single source of truth for calculating and saving student attempt scores.
    Evaluates objective questions, computes marks obtained, total marks, percentage,
    and pass/fail status.
    """
    from ..models import StudentAnswer, StudentAttempt

    exam = attempt.exam
    now = timezone.now()
    subjective_answers = []

    with transaction.atomic():
        for question in exam.questions.all():
            answer, _ = StudentAnswer.objects.get_or_create(attempt=attempt, question=question)
            if is_objective_question(question):
                correct = is_objective_answer_correct(question, answer.answer_text)
                answer.is_correct = correct
                answer.score_awarded = question.marks if correct else 0
                answer.save(update_fields=["is_correct", "score_awarded"])
            else:
                subjective_answers.append(answer)

        # Marks obtained so far
        marks_obtained = sum(
            ans.score_awarded or 0
            for ans in StudentAnswer.objects.filter(attempt=attempt)
        )
        exam_total = exam.total_marks or sum(q.marks for q in exam.questions.all()) or 1
        percentage = round((marks_obtained / exam_total) * 100.0, 2)
        is_passed = percentage >= PASSING_PERCENTAGE

        if not attempt.submitted_at:
            attempt.submitted_at = now

        if subjective_answers:
            attempt.status = StudentAttempt.Status.SUBMITTED
        else:
            attempt.status = (
                StudentAttempt.Status.AUTO_SUBMITTED
                if is_auto_submit
                else StudentAttempt.Status.EVALUATED
            )

        attempt.total_score = marks_obtained
        attempt.save(update_fields=["submitted_at", "status", "total_score"])

    # If subjective questions exist, trigger evaluation in background
    if subjective_answers:
        from ..evaluation import evaluate_attempt_subjectives
        import threading
        threading.Thread(target=evaluate_attempt_subjectives, args=(attempt.id,), daemon=True).start()

    return {
        "marks_obtained": marks_obtained,
        "total_marks": exam_total,
        "percentage": percentage,
        "is_passed": is_passed,
        "status": attempt.status,
        "has_subjective": bool(subjective_answers),
    }

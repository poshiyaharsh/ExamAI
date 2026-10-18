import logging
from django.db import transaction
from django.utils import timezone
from .options import clean_option_text

logger = logging.getLogger(__name__)

PASSING_PERCENTAGE = 40.0


def normalize_text(value):
    if value is None:
        return ""
    return " ".join(str(value).split()).casefold()


def is_objective_question(question):
    return question.question_type in {"mcq", "truefalse", "fillblank"}


def is_objective_answer_correct(question, answer_text):
    submitted = normalize_text(clean_option_text(answer_text))
    if not submitted:
        return False

    raw_correct = question.correct_answer
    options = question.options or []
    norm_options = [normalize_text(clean_option_text(opt)) for opt in options]

    # 1. Direct text match with correct_answer
    if submitted == normalize_text(clean_option_text(raw_correct)):
        return True

    # 2. True/False question handling
    if question.question_type == "truefalse":
        if isinstance(raw_correct, bool):
            expected = "true" if raw_correct else "false"
            return submitted == expected
        norm_correct = normalize_text(clean_option_text(raw_correct))
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
            if norm_options[idx] == normalize_text(clean_option_text(raw_correct)):
                return True

    # 6. If raw_correct matched one of options, and submitted is that option
    for opt in norm_options:
        if opt == normalize_text(clean_option_text(raw_correct)) and submitted == opt:
            return True

    return False


def calculate_and_save_attempt_score(attempt, is_auto_submit=False):
    """
    Single source of truth for calculating and saving student attempt scores.
    Evaluates objective questions, computes marks obtained, total marks, percentage,
    and pass/fail status.
    Ensures any unanswered questions have StudentAnswer rows created with institution set.
    """
    from ..models import StudentAnswer, StudentAttempt

    exam = attempt.exam
    now = timezone.now()
    subjective_answers = []

    with transaction.atomic():
        if attempt.question_order:
            q_map = {
                q.id: q
                for q in exam.questions.filter(id__in=attempt.question_order, is_deleted=False)
            }
            questions = [q_map[qid] for qid in attempt.question_order if qid in q_map]
        else:
            questions = list(exam.questions.filter(is_deleted=False).order_by('order', 'id'))
        if not questions:
            if not attempt.submitted_at:
                attempt.submitted_at = now
            attempt.status = (
                StudentAttempt.Status.AUTO_SUBMITTED
                if is_auto_submit
                else StudentAttempt.Status.EVALUATED
            )
            attempt.total_score = 0
            attempt.save(update_fields=["submitted_at", "status", "total_score"])
            return {
                "marks_obtained": 0,
                "total_marks": exam.total_marks or 0,
                "percentage": 0.0,
                "is_passed": False,
                "status": attempt.status,
                "has_subjective": False,
            }

        # 1. Fetch all existing answers for this attempt
        existing_answers = {
            ans.question_id: ans
            for ans in StudentAnswer.objects.filter(attempt=attempt)
        }

        # 2. Identify missing answers and bulk create them with institution set
        missing_answers = []
        for q in questions:
            if q.id not in existing_answers:
                missing_answers.append(
                    StudentAnswer(
                        institution=attempt.institution,
                        attempt=attempt,
                        question=q,
                        answer_text="",
                        is_correct=False,
                        score_awarded=0,
                    )
                )

        if missing_answers:
            StudentAnswer.objects.bulk_create(missing_answers, ignore_conflicts=True)
            existing_answers = {
                ans.question_id: ans
                for ans in StudentAnswer.objects.filter(attempt=attempt)
            }

        # 3. Evaluate questions and collect updates
        answers_to_update = []
        for q in questions:
            answer = existing_answers.get(q.id)
            if not answer:
                continue

            if is_objective_question(q):
                correct = is_objective_answer_correct(q, answer.answer_text)
                answer.is_correct = correct
                answer.score_awarded = q.marks if correct else 0
                answers_to_update.append(answer)
            else:
                # Subjective question
                if not (answer.answer_text and answer.answer_text.strip()):
                    answer.is_correct = False
                    answer.score_awarded = 0
                    answer.ai_feedback = "No answer provided."
                    answers_to_update.append(answer)
                else:
                    subjective_answers.append(answer)

        if answers_to_update:
            StudentAnswer.objects.bulk_update(
                answers_to_update,
                ["is_correct", "score_awarded", "ai_feedback"]
            )

        # 4. Compute totals
        marks_obtained = sum(
            (ans.score_awarded or 0)
            for ans in existing_answers.values()
        )
        exam_total = float(attempt.max_score or exam.total_marks or sum(q.marks for q in questions) or 1)
        percentage = round((float(marks_obtained) / float(exam_total)) * 100.0, 2)
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

    # If subjective questions with student text exist, trigger evaluation in background
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

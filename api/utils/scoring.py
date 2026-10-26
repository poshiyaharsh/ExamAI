import logging
from django.db import transaction
from django.utils import timezone
from .options import clean_option_text
from .validate_paper import canonicalize_type

logger = logging.getLogger(__name__)

PASSING_PERCENTAGE = 40.0


def normalize_text(value):
    if value is None:
        return ""
    return " ".join(str(value).split()).casefold()


def is_objective_question(question):
    q_type = canonicalize_type(getattr(question, 'question_type', ''))
    return q_type in {"mcq", "true_false", "fill_blank"}


def evaluate_fill_blank(question, student_answer_obj):
    """
    Evaluates fill_blank question against accepted_answers or correct_answer.
    Returns (score_awarded, is_correct, feedback_str).
    Partial marks awarded proportionally: (correct_count / total_blanks) * marks.
    No negative marks.
    """
    import re
    q_marks = float(question.marks or 1.0)

    # 1. Parse student blanks
    student_blanks = []
    if student_answer_obj.blank_answers and isinstance(student_answer_obj.blank_answers, list):
        student_blanks = [normalize_text(b) for b in student_answer_obj.blank_answers]
    elif student_answer_obj.answer_text:
        parts = re.split(r'[,|;]', str(student_answer_obj.answer_text))
        student_blanks = [normalize_text(p) for p in parts if p.strip()]

    # 2. Parse accepted answers from question
    expected_groups = []
    raw_acc = question.accepted_answers
    if raw_acc and isinstance(raw_acc, list):
        for item in raw_acc:
            if isinstance(item, list):
                expected_groups.append([normalize_text(alt) for alt in item if str(alt).strip()])
            elif item is not None:
                expected_groups.append([normalize_text(item)])

    if not expected_groups:
        raw_corr = question.correct_answer
        if isinstance(raw_corr, list):
            expected_groups = [[normalize_text(x)] for x in raw_corr]
        elif raw_corr:
            parts = re.split(r'[,|;]', str(raw_corr))
            expected_groups = [[normalize_text(p)] for p in parts if p.strip()]

    if not expected_groups:
        expected_groups = [[]]

    total_blanks = max(1, len(expected_groups))
    correct_count = 0
    feedback_parts = []

    for i, group in enumerate(expected_groups):
        stud_val = student_blanks[i] if i < len(student_blanks) else ""
        matched = False
        if stud_val:
            for alt in group:
                if stud_val == alt:
                    matched = True
                    break
        if matched:
            correct_count += 1
            feedback_parts.append(f"Blank {i+1}: Correct")
        else:
            feedback_parts.append(f"Blank {i+1}: Incorrect")

    score = round((correct_count / total_blanks) * q_marks, 2)
    is_correct = (correct_count == total_blanks and total_blanks > 0)
    feedback = f"{correct_count}/{total_blanks} blanks correct. " + ", ".join(feedback_parts)
    return score, is_correct, feedback


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
    if question.question_type in {"true_false", "truefalse"}:
        if isinstance(raw_correct, bool):
            expected = "true" if raw_correct else "false"
            return submitted == expected
        norm_correct = normalize_text(clean_option_text(raw_correct))
        if norm_correct in {"a", "true", "t", "1"}:
            return submitted in {"true", "t", "a"}
        if norm_correct in {"b", "false", "f", "0"}:
            return submitted in {"false", "f", "b"}

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


def calculate_and_save_attempt_score(attempt, is_auto_submit=False, trigger_ai=False):
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

            canon_type = canonicalize_type(getattr(q, 'question_type', ''))
            if canon_type == "fill_blank":
                score, is_corr, fb = evaluate_fill_blank(q, answer)
                answer.score_awarded = score
                answer.is_correct = is_corr
                answer.ai_feedback = fb
                answer.auto_marks = score
                answer.auto_is_correct = bool(is_corr)
                answer.auto_feedback = fb
                answer.auto_source = 'rule'
                answer.auto_evaluated_at = now
                answer.ai_status = 'ready'
                answer.evaluation_status = StudentAnswer.EvaluationStatus.REVIEWED
                answer.evaluation_provider = "deterministic"
                answer.evaluation_model = "exact_match"
                answers_to_update.append(answer)
            elif canon_type in {"mcq", "true_false"}:
                correct = is_objective_answer_correct(q, answer.answer_text)
                score = q.marks if correct else 0.0
                answer.is_correct = correct
                answer.score_awarded = score
                answer.ai_feedback = "Correct" if correct else "Incorrect"
                answer.auto_marks = score
                answer.auto_is_correct = bool(correct)
                answer.auto_feedback = answer.ai_feedback
                answer.auto_source = 'rule'
                answer.auto_evaluated_at = now
                answer.ai_status = 'ready'
                answer.evaluation_status = StudentAnswer.EvaluationStatus.REVIEWED
                answer.evaluation_provider = "deterministic"
                answer.evaluation_model = "exact_match"
                answers_to_update.append(answer)
            else:
                # Subjective question (short_answer, long_answer, subjective)
                if not (answer.answer_text and str(answer.answer_text).strip()):
                    answer.is_correct = False
                    answer.score_awarded = 0.0
                    answer.ai_feedback = "No answer provided."
                    answer.auto_marks = 0.0
                    answer.auto_is_correct = False
                    answer.auto_feedback = "No answer provided."
                    answer.auto_source = 'empty'
                    answer.auto_evaluated_at = now
                    answer.ai_status = 'ready'
                    answer.evaluation_status = StudentAnswer.EvaluationStatus.REVIEWED
                    answer.evaluation_provider = "empty_check"
                    answer.evaluation_model = "none"
                    answers_to_update.append(answer)
                else:
                    # Student provided an answer: mark pending AI evaluation
                    answer.is_correct = None
                    answer.score_awarded = 0.0
                    answer.ai_feedback = "Answer submitted. Evaluation in progress."
                    answer.auto_marks = 0.0
                    answer.auto_is_correct = None
                    answer.auto_feedback = "Pending AI evaluation."
                    answer.auto_source = 'ai'
                    answer.auto_evaluated_at = now
                    answer.ai_status = 'running'
                    answer.evaluation_status = StudentAnswer.EvaluationStatus.PENDING_REVIEW
                    answer.evaluation_provider = "pending"
                    answer.evaluation_model = "none"
                    answers_to_update.append(answer)
                    subjective_answers.append(answer)

        if answers_to_update:
            StudentAnswer.objects.bulk_update(
                answers_to_update,
                [
                    "is_correct",
                    "score_awarded",
                    "ai_feedback",
                    "auto_marks",
                    "auto_is_correct",
                    "auto_feedback",
                    "auto_source",
                    "auto_evaluated_at",
                    "ai_status",
                    "evaluation_status",
                    "evaluation_provider",
                    "evaluation_model",
                ]
            )

        # 4. Compute totals
        auto_obtained = sum(
            float(ans.auto_marks or 0.0)
            for ans in existing_answers.values()
        )
        marks_obtained = sum(
            float(ans.effective_marks if getattr(ans, 'overridden', False) else (ans.score_awarded or 0.0))
            for ans in existing_answers.values()
        )
        exam_total = float(attempt.max_score or exam.total_marks or sum(q.marks for q in questions) or 1)
        percentage = round((float(marks_obtained) / float(exam_total)) * 100.0, 2)
        is_passed = percentage >= PASSING_PERCENTAGE

        if not attempt.submitted_at:
            attempt.submitted_at = now

        if is_auto_submit:
            attempt.status = StudentAttempt.Status.AUTO_SUBMITTED
        elif subjective_answers:
            attempt.status = StudentAttempt.Status.SUBMITTED
        else:
            attempt.status = StudentAttempt.Status.EVALUATED

        attempt.total_score = marks_obtained
        attempt.auto_total = auto_obtained
        attempt.final_total = marks_obtained
        if not attempt.review_status or attempt.review_status == StudentAttempt.ReviewStatus.AUTO_EVALUATED:
            attempt.review_status = StudentAttempt.ReviewStatus.AUTO_EVALUATED
        attempt.save(update_fields=["submitted_at", "status", "total_score", "auto_total", "final_total", "review_status"])

    # If subjective questions exist and AI evaluation requested, dispatch background thread
    if trigger_ai and subjective_answers:
        try:
            import threading
            from ..evaluation import evaluate_attempt_subjectives
            threading.Thread(target=evaluate_attempt_subjectives, args=(attempt.id,), daemon=True).start()
        except Exception as exc:
            logger.warning("Failed to start background subjective evaluation thread: %s", exc)

    return {
        "marks_obtained": marks_obtained,
        "total_marks": exam_total,
        "percentage": percentage,
        "is_passed": is_passed,
        "status": attempt.status,
        "has_subjective": bool(subjective_answers),
    }

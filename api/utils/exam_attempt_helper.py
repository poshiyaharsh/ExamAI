import random
import secrets
from typing import Any, Dict, List, Optional, Tuple
from api.models import Exam, Question, StudentAttempt
from api.utils.options import clean_options_list, clean_option_text


def fisher_yates_shuffle(items: List[Any], rng=None) -> List[Any]:
    """
    In-place Fisher-Yates shuffle returning a newly shuffled list.
    Uses cryptographically secure random generator if none provided.
    """
    if rng is None:
        rng = secrets.SystemRandom()
    arr = list(items)
    for i in range(len(arr) - 1, 0, -1):
        j = rng.randint(0, i)
        arr[i], arr[j] = arr[j], arr[i]
    return arr


def select_balanced_subset(
    questions: List[Question],
    subset_size: int,
    topics: Optional[List[str]] = None,
    difficulty_distribution: Optional[Dict[str, Any]] = None,
    rng=None,
) -> List[Question]:
    """
    Selects a balanced subset of questions respecting difficulty and topics where possible.
    """
    if not questions or subset_size <= 0:
        return []
    if subset_size >= len(questions):
        return list(questions)

    if rng is None:
        rng = secrets.SystemRandom()

    # Group by difficulty
    by_diff: Dict[str, List[Question]] = {}
    for q in questions:
        diff = (q.difficulty or 'MEDIUM').upper()
        by_diff.setdefault(diff, []).append(q)

    # Calculate target counts per difficulty
    total_q = len(questions)
    target_counts: Dict[str, int] = {}
    if difficulty_distribution and isinstance(difficulty_distribution, dict):
        total_pct = sum(float(v) for v in difficulty_distribution.values() if isinstance(v, (int, float)))
        if total_pct > 0:
            for diff, pct in difficulty_distribution.items():
                if isinstance(pct, (int, float)):
                    target_counts[diff.upper()] = max(0, int(round((float(pct) / total_pct) * subset_size)))

    # If target counts not specified or don't sum to subset_size, allocate proportionally to existing pool
    allocated_sum = sum(target_counts.values())
    if allocated_sum != subset_size:
        target_counts = {}
        remaining = subset_size
        diff_keys = list(by_diff.keys())
        for diff in diff_keys:
            count_available = len(by_diff[diff])
            ideal = int(round((count_available / total_q) * subset_size))
            actual = min(count_available, ideal)
            target_counts[diff] = actual
            remaining -= actual

        # If remainder still exists, fill from available pools
        if remaining > 0:
            for diff in diff_keys:
                can_add = len(by_diff[diff]) - target_counts.get(diff, 0)
                to_add = min(remaining, can_add)
                target_counts[diff] = target_counts.get(diff, 0) + to_add
                remaining -= to_add
                if remaining <= 0:
                    break

    selected: List[Question] = []
    pool_leftovers: List[Question] = []

    for diff, q_list in by_diff.items():
        shuffled = fisher_yates_shuffle(q_list, rng=rng)
        target = target_counts.get(diff, 0)
        selected.extend(shuffled[:target])
        pool_leftovers.extend(shuffled[target:])

    # If still need more questions to meet exact subset_size
    shortfall = subset_size - len(selected)
    if shortfall > 0 and pool_leftovers:
        shuffled_leftovers = fisher_yates_shuffle(pool_leftovers, rng=rng)
        selected.extend(shuffled_leftovers[:shortfall])

    return selected[:subset_size]


def initialize_attempt_orders(attempt: StudentAttempt, exam: Exam) -> None:
    """
    Initializes question_order and option_orders for a new student attempt
    using Fisher-Yates shuffling. Persists them to attempt.
    Reloading later will preserve this exact order.
    """
    rng = secrets.SystemRandom()
    all_questions = list(
        exam.questions.filter(is_deleted=False).order_by('order', 'id')
    )
    if not all_questions:
        attempt.question_order = []
        attempt.option_orders = {}
        attempt.max_score = 0.0
        return

    # 1. Subset selection if specified
    if exam.random_subset_size and 0 < exam.random_subset_size < len(all_questions):
        selected_questions = select_balanced_subset(
            all_questions,
            exam.random_subset_size,
            topics=exam.topics,
            difficulty_distribution=exam.difficulty_distribution,
            rng=rng,
        )
    else:
        selected_questions = list(all_questions)

    # 2. Shuffle questions if enabled
    if exam.shuffle_questions:
        selected_questions = fisher_yates_shuffle(selected_questions, rng=rng)

    question_order = [q.id for q in selected_questions]

    # 3. Shuffle options per question if enabled
    option_orders: Dict[str, List[int]] = {}
    for q in selected_questions:
        raw_opts = clean_options_list(q.options)
        if exam.shuffle_options and raw_opts and len(raw_opts) > 1 and q.question_type in {'mcq', 'MCQ_SINGLE', 'MCQ_MULTIPLE'}:
            perm = list(range(len(raw_opts)))
            perm = fisher_yates_shuffle(perm, rng=rng)
            option_orders[str(q.id)] = perm
        else:
            # Identity order
            if raw_opts:
                option_orders[str(q.id)] = list(range(len(raw_opts)))

    max_score = sum(float(q.marks or 0.0) for q in selected_questions)

    attempt.question_order = question_order
    attempt.option_orders = option_orders
    attempt.max_score = max_score


def sanitize_questions_for_attempt(attempt: StudentAttempt) -> List[Dict[str, Any]]:
    """
    Prepares sanitized question payload for student exam UI.
    Guarantees:
    - Questions returned in exact attempt.question_order.
    - Options permuted according to attempt.option_orders.
    - NEVER reveals correct_answer, explanation, or model_answer.
    """
    if not attempt.question_order:
        # Fallback if attempt was created before shuffle feature or has empty order
        questions = list(attempt.exam.questions.filter(is_deleted=False).order_by('order', 'id'))
    else:
        q_map = {
            q.id: q
            for q in Question.objects.filter(id__in=attempt.question_order, exam=attempt.exam, is_deleted=False)
        }
        questions = [q_map[qid] for qid in attempt.question_order if qid in q_map]

    sanitized = []
    option_orders = attempt.option_orders or {}

    for idx, q in enumerate(questions, start=1):
        raw_opts = clean_options_list(q.options)
        perm = option_orders.get(str(q.id))

        if perm and raw_opts and len(perm) == len(raw_opts):
            # Apply permutation
            shuffled_options = [raw_opts[i] for i in perm]
        else:
            shuffled_options = raw_opts

        marks_float = float(q.marks) if q.marks is not None else 0.0

        sanitized.append({
            'id': q.id,
            'order': idx,
            'question_type': q.question_type,
            'difficulty': q.difficulty,
            'text': q.text,
            'options': shuffled_options,
            'marks': marks_float,
            'topic': q.topic.name if q.topic else (q.topic_text or ''),
        })

    return sanitized


def map_submitted_answer_to_canonical(
    attempt: StudentAttempt,
    question: Question,
    submitted_answer_text: str,
) -> Tuple[str, Optional[List[int]]]:
    """
    Maps student's submitted answer (which may be a letter index 'A', 'B', 'C', 'D'
    or the text of a shuffled option) back to the canonical original option text.
    Returns (canonical_answer_text, applied_option_order).
    """
    submitted = str(submitted_answer_text or '').strip()
    if not submitted:
        return '', None

    raw_options = clean_options_list(question.options)
    if not raw_options:
        return submitted, None

    option_orders = attempt.option_orders or {}
    perm = option_orders.get(str(question.id))

    if not perm or len(perm) != len(raw_options):
        # No permutation applied, return as-is
        return submitted, None

    # Student saw options in order: [raw_options[perm[0]], raw_options[perm[1]], ...]
    shuffled_options = [raw_options[i] for i in perm]

    letter_map = {'A': 0, 'B': 1, 'C': 2, 'D': 3}
    cleaned_submitted = clean_option_text(submitted)
    upper_submitted = cleaned_submitted.upper()

    # Case 1: Student sent letter 'A', 'B', 'C', 'D' or 0-based index
    if upper_submitted in letter_map:
        student_pos = letter_map[upper_submitted]
        if student_pos < len(perm):
            canonical_idx = perm[student_pos]
            if canonical_idx < len(raw_options):
                return raw_options[canonical_idx], perm

    if submitted.isdigit():
        num = int(submitted)
        # Check 0-based
        if 0 <= num < len(perm):
            canonical_idx = perm[num]
            if canonical_idx < len(raw_options):
                return raw_options[canonical_idx], perm
        # Check 1-based
        if 1 <= num <= len(perm):
            canonical_idx = perm[num - 1]
            if canonical_idx < len(raw_options):
                return raw_options[canonical_idx], perm

    # Case 2: Student sent option text.
    # Check if matches any shuffled option
    norm_submitted = ' '.join(cleaned_submitted.split()).casefold()
    for student_pos, opt_text in enumerate(shuffled_options):
        norm_opt = ' '.join(clean_option_text(opt_text).split()).casefold()
        if norm_submitted == norm_opt:
            canonical_idx = perm[student_pos]
            if canonical_idx < len(raw_options):
                return raw_options[canonical_idx], perm

    # If it already matches canonical option text directly, return it
    for opt_text in raw_options:
        norm_opt = ' '.join(clean_option_text(opt_text).split()).casefold()
        if norm_submitted == norm_opt:
            return opt_text, perm

    # Otherwise return as-is (e.g. for fill-in-the-blank or subjective)
    return submitted, perm

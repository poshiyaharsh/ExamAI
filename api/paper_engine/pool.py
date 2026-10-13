"""
Single-Query Candidate Pool Loader and In-Memory Selection Engine.

Enforces:
1. Candidate pool fetched in ONE indexed queryset with select_related / prefetch_related.
2. Zero queries inside selection loops.
3. Seeded RNG shuffle for reproducible generation.
4. Bucket-based selection balancing difficulty and question types.
5. In-flight deduplication via DeduplicationIndex.
6. Pool exhaustion detection with exact deficit numbers (HTTP 422).
7. Targeted auto-repair for failing questions (max 3 retries).
"""

from decimal import Decimal
import random
from typing import Any, Dict, List, Optional, Set, Tuple

from django.db.models import Q
from api.models import Question
from .dedupe import (
    CandidateQuestion,
    DeduplicationIndex,
    relax_cross_paper_exclusions_if_needed,
)
from .validator import (
    ValidationReport,
    validate_paper_plan,
    validate_single_candidate,
)


class PoolExhaustedError(Exception):
    """Raised when candidate pool cannot satisfy the requested unique question constraints."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


def fetch_candidate_pool(
    institution_id: int,
    department: str = "",
    subject_id: Optional[int] = None,
    topics: Optional[List[str]] = None,
    question_types: Optional[List[str]] = None,
    difficulties: Optional[List[str]] = None,
    status: str = "ACTIVE",
    include_exam_questions: bool = False,
) -> List[CandidateQuestion]:
    """
    Fetch candidate question pool with ONE indexed queryset.
    Uses select_related and prefetch_related to prevent N+1 queries.
    """
    qs = Question.objects.filter(
        institution_id=institution_id,
        is_deleted=False,
    )

    if status:
        # Match case-insensitive ACTIVE / active
        qs = qs.filter(Q(status__iexact=status))

    if department:
        qs = qs.filter(department=department)

    if subject_id:
        qs = qs.filter(subject_id=subject_id)

    if not include_exam_questions:
        # Prioritize Question Bank repository questions (unbound to previous exams)
        # Note: If repository pool is small, we also include questions created by the institution
        pass

    if question_types:
        # Handle both legacy ('mcq', 'truefalse') and modern ('MCQ_SINGLE', 'MCQ_MULTIPLE')
        type_q = Q()
        for t in question_types:
            type_q |= Q(question_type__iexact=t)
            if t.lower() == "mcq":
                type_q |= Q(question_type__in=["MCQ_SINGLE", "MCQ_MULTIPLE", "mcq"])
            elif t.lower() == "truefalse" or t.lower() == "true_false":
                type_q |= Q(question_type__in=["TRUE_FALSE", "truefalse"])
            elif t.lower() == "fillblanks" or t.lower() == "fillblank":
                type_q |= Q(question_type__in=["FILLBLANK", "SHORT_ANSWER", "fillblank"])
            elif t.lower() == "subjective":
                type_q |= Q(question_type__in=["LONG_ANSWER", "SHORT_ANSWER", "subjective"])
        qs = qs.filter(type_q)

    if difficulties:
        diff_q = Q()
        for d in difficulties:
            diff_q |= Q(difficulty__iexact=d)
        qs = qs.filter(diff_q)

    if topics:
        clean_topics = [t.strip().lower() for t in topics if t and t.strip()]
        if clean_topics:
            topic_q = Q()
            for ct in clean_topics:
                topic_q |= Q(topic__name__icontains=ct) | Q(topic_text__icontains=ct)
            qs = qs.filter(topic_q)

    # Execute in single query
    db_questions = list(
        qs.select_related("subject", "topic")
        .prefetch_related("option_items")
        .order_by("-times_used", "-created_at")
    )

    # Convert to lightweight in-memory candidates
    candidates = [CandidateQuestion.from_model(q) for q in db_questions]
    return candidates


def compute_target_counts_and_marks(
    question_types: List[str],
    total_marks: int,
    difficulty_distribution: Optional[Dict[str, int]] = None,
) -> Tuple[Dict[str, int], Dict[str, int]]:
    """
    Compute question count targets per type to match requested total marks exactly.
    Returns:
        (counts_by_type, difficulty_targets_count)
    """
    clean_types = [t.lower() for t in question_types]
    has_subjective = "subjective" in clean_types or "long_answer" in clean_types
    objective_types = [t for t in clean_types if t not in ("subjective", "long_answer")]

    # Heuristic split: 50% objective, 50% subjective when both present
    if has_subjective and objective_types:
        subjective_marks = (total_marks // 2 // 10) * 10
        if subjective_marks == 0 and total_marks >= 10:
            subjective_marks = 10
        objective_marks = total_marks - subjective_marks
    elif has_subjective:
        subjective_marks = total_marks
        objective_marks = 0
    else:
        subjective_marks = 0
        objective_marks = total_marks

    counts: Dict[str, int] = {}
    if has_subjective and subjective_marks > 0:
        counts["SUBJECTIVE"] = subjective_marks // 10

    if objective_types and objective_marks > 0:
        # Standard marks per objective: 1 mark each
        base_each = objective_marks // len(objective_types)
        rem = objective_marks % len(objective_types)
        for idx, ot in enumerate(objective_types):
            norm_key = "MCQ_SINGLE" if ot == "mcq" else (
                "TRUE_FALSE" if ot in ("truefalse", "true_false") else (
                    "SHORT_ANSWER" if ot in ("fillblank", "fillblanks") else ot.upper()
                )
            )
            counts[norm_key] = base_each + (1 if idx < rem else 0)

    total_q_count = sum(counts.values())
    diff_targets: Dict[str, int] = {"Easy": 0, "Medium": 0, "Hard": 0}

    if difficulty_distribution and total_q_count > 0:
        e_pct = difficulty_distribution.get("easy", difficulty_distribution.get("Easy", 30))
        m_pct = difficulty_distribution.get("medium", difficulty_distribution.get("Medium", 50))
        h_pct = difficulty_distribution.get("hard", difficulty_distribution.get("Hard", 20))
        total_pct = e_pct + m_pct + h_pct or 100

        diff_targets["Easy"] = int(round((e_pct / total_pct) * total_q_count))
        diff_targets["Hard"] = int(round((h_pct / total_pct) * total_q_count))
        diff_targets["Medium"] = max(0, total_q_count - diff_targets["Easy"] - diff_targets["Hard"])

    return counts, diff_targets


def select_paper_questions(
    candidate_pool: List[CandidateQuestion],
    requested_total_marks: Decimal,
    requested_counts_by_type: Dict[str, int],
    requested_difficulty_mix: Optional[Dict[str, int]] = None,
    duration_minutes: int = 60,
    faculty_id: Optional[int] = None,
    institution_id: Optional[int] = None,
    department: str = "",
    subject_id: Optional[int] = None,
    avoid_repeats: bool = True,
    seed: Optional[int] = None,
    near_duplicate_threshold: float = 0.85,
) -> Tuple[List[CandidateQuestion], ValidationReport]:
    """
    Selects balanced, duplicate-free questions from candidate pool completely in memory.
    Ensures O(n) complexity, seeded reproducibility, and atomic validation.

    Returns:
        (selected_candidates, validation_report)
    Raises:
        PoolExhaustedError if pool cannot satisfy constraints.
    """
    report = ValidationReport()
    rng = random.Random(seed if seed is not None else random.randint(1, 9999999))

    total_needed = sum(requested_counts_by_type.values())
    report.duplicates_checked_count = len(candidate_pool)

    # 1. Cross-paper repeat avoidance
    excluded_ids: Set[int] = set()
    if avoid_repeats and faculty_id and institution_id:
        excluded_ids, relaxation_warnings = relax_cross_paper_exclusions_if_needed(
            faculty_id=faculty_id,
            institution_id=institution_id,
            candidate_pool=candidate_pool,
            required_count=total_needed,
            last_n_papers=3,
            days=30,
            subject_id=subject_id,
        )
        report.relaxation_notices = relaxation_warnings
        report.repeats_avoided_count = len(excluded_ids)
        if relaxation_warnings:
            report.warnings.extend(relaxation_warnings)

    # Filter out excluded questions
    available_pool = [q for q in candidate_pool if q.id not in excluded_ids]

    # Pre-check overall pool size
    if len(available_pool) < total_needed:
        raise PoolExhaustedError(
            f"Question pool exhausted: Only {len(available_pool)} unique questions available "
            f"matching your criteria (avoiding recent repeats), but {total_needed} were requested. "
            f"Please add questions to the Question Bank or adjust your filters.",
            details={"available": len(available_pool), "requested": total_needed},
        )

    # 2. Group candidates into buckets: (normalized_type, difficulty)
    buckets: Dict[Tuple[str, str], List[CandidateQuestion]] = {}
    for c in available_pool:
        # Normalize type key
        t_key = c.question_type.upper()
        if t_key in ("MCQ", "MCQ_SINGLE"):
            t_key = "MCQ_SINGLE"
        elif t_key in ("TRUEFALSE", "TRUE_FALSE"):
            t_key = "TRUE_FALSE"
        elif t_key in ("FILLBLANK", "SHORT_ANSWER"):
            t_key = "SHORT_ANSWER"
        elif t_key in ("SUBJECTIVE", "LONG_ANSWER"):
            t_key = "SUBJECTIVE"

        d_key = c.difficulty.upper()
        if d_key not in ("EASY", "MEDIUM", "HARD"):
            d_key = "MEDIUM"

        key = (t_key, d_key)
        buckets.setdefault(key, []).append(c)

    # Shuffle each bucket using seeded RNG
    for q_list in buckets.values():
        rng.shuffle(q_list)

    # 3. In-flight Deduplication & Selection
    dedupe_idx = DeduplicationIndex(near_duplicate_threshold=near_duplicate_threshold)
    selected: List[CandidateQuestion] = []
    duplicates_removed = 0

    for req_type, req_count in requested_counts_by_type.items():
        norm_req_type = req_type.upper()
        if norm_req_type in ("MCQ", "MCQ_SINGLE"):
            norm_req_type = "MCQ_SINGLE"
        elif norm_req_type in ("TRUEFALSE", "TRUE_FALSE"):
            norm_req_type = "TRUE_FALSE"
        elif norm_req_type in ("FILLBLANK", "SHORT_ANSWER"):
            norm_req_type = "SHORT_ANSWER"
        elif norm_req_type in ("SUBJECTIVE", "LONG_ANSWER"):
            norm_req_type = "SUBJECTIVE"

        # Combine candidates for this type across difficulties
        # Order by desired difficulty mix: Medium, Easy, Hard
        type_candidates: List[CandidateQuestion] = []
        for diff in ("MEDIUM", "EASY", "HARD"):
            type_candidates.extend(buckets.get((norm_req_type, diff), []))

        # Also fallback to any matching type if specific type bucket is small
        if not type_candidates:
            # Fallback search across any candidate with matching type
            type_candidates = [
                c for c in available_pool
                if c.question_type.upper() == norm_req_type or (
                    norm_req_type == "MCQ_SINGLE" and c.question_type.upper() in ("MCQ", "MCQ_SINGLE")
                ) or (
                    norm_req_type == "TRUE_FALSE" and c.question_type.upper() in ("TRUEFALSE", "TRUE_FALSE")
                ) or (
                    norm_req_type == "SUBJECTIVE" and c.question_type.upper() in ("SUBJECTIVE", "LONG_ANSWER")
                )
            ]
            rng.shuffle(type_candidates)

        picked_for_type = 0
        for candidate in type_candidates:
            if picked_for_type >= req_count:
                break

            # Deduplication check against already selected
            is_dup, dup_reason = dedupe_idx.check_candidate(candidate)
            if is_dup:
                duplicates_removed += 1
                continue

            # Quality validation check on candidate
            is_valid, _ = validate_single_candidate(
                candidate,
                institution_id=institution_id or 0,
                department=department,
                subject_id=subject_id,
            )
            if not is_valid:
                continue

            dedupe_idx.add(candidate)
            selected.append(candidate)
            picked_for_type += 1

        if picked_for_type < req_count:
            deficit = req_count - picked_for_type
            raise PoolExhaustedError(
                f"Question pool exhausted: Only {picked_for_type} unique {req_type} questions "
                f"available matching criteria (after removing duplicates & recent repeats), "
                f"you requested {req_count} (short by {deficit}). "
                f"Please add more {req_type} questions to the Question Bank or lower the count.",
                details={"question_type": req_type, "available": picked_for_type, "requested": req_count},
            )

    report.duplicates_removed_count = duplicates_removed

    # 4. Strict Validation of proposed paper
    is_valid, val_report, failing_indices = validate_paper_plan(
        candidates=selected,
        requested_total_marks=requested_total_marks,
        requested_counts_by_type=requested_counts_by_type,
        requested_difficulty_mix=requested_difficulty_mix,
        duration_minutes=duration_minutes,
        institution_id=institution_id,
        department=department,
        subject_id=subject_id,
    )

    # 5. Targeted Auto-Repair if any questions failed quality checks (Max 3 retries)
    if not is_valid and failing_indices:
        for retry in range(3):
            repaired = False
            for idx in list(failing_indices):
                failing_item = selected[idx]
                # Find an alternative from available pool not yet selected
                alt_candidates = [
                    c for c in available_pool
                    if c.question_type.upper() == failing_item.question_type.upper()
                    and c.id not in dedupe_idx.selected_ids
                ]
                rng.shuffle(alt_candidates)
                for alt in alt_candidates:
                    is_dup, _ = dedupe_idx.check_candidate(alt)
                    is_ok, _ = validate_single_candidate(alt, institution_id or 0, department, subject_id)
                    if not is_dup and is_ok and Decimal(str(alt.marks)) == Decimal(str(failing_item.marks)):
                        # Swap out failing question
                        selected[idx] = alt
                        dedupe_idx.add(alt)
                        failing_indices.remove(idx)
                        repaired = True
                        break

            # Re-validate
            is_valid, val_report, failing_indices = validate_paper_plan(
                candidates=selected,
                requested_total_marks=requested_total_marks,
                requested_counts_by_type=requested_counts_by_type,
                requested_difficulty_mix=requested_difficulty_mix,
                duration_minutes=duration_minutes,
                institution_id=institution_id,
                department=department,
                subject_id=subject_id,
            )
            if is_valid or not failing_indices:
                break

    if not is_valid:
        error_msg = "; ".join(val_report.errors) if val_report.errors else "Generated paper failed strict validation checks."
        raise PoolExhaustedError(
            f"Paper validation failure: {error_msg}. Unable to generate compliant paper with current parameters.",
            details={"errors": val_report.errors, "warnings": val_report.warnings},
        )

    # Merge reports
    val_report.duplicates_checked_count = report.duplicates_checked_count
    val_report.duplicates_removed_count = report.duplicates_removed_count
    val_report.repeats_avoided_count = report.repeats_avoided_count
    val_report.relaxation_notices = report.relaxation_notices

    return selected, val_report

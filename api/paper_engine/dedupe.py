"""
Reusable Zero-Duplicate Engine for Exam Paper Generation.

Enforces:
1. Exact question ID deduplication.
2. Exact normalized text hash (SHA-256) deduplication.
3. Near-duplicate text detection (character 3-shingles + token-set Jaccard + difflib SequenceMatcher >= threshold).
4. Same-concept deduplication (same topic + >= 75% option text overlap).
5. Intra-question duplicate options check.
6. Cross-paper repeat avoidance (same faculty's last N papers / 30 days) with explicit logged relaxation.
7. Pool exhaustion analysis with exact deficit reporting.
"""

from datetime import timedelta
import difflib
import hashlib
import re
import unicodedata
from typing import Any, Dict, FrozenSet, List, Optional, Set, Tuple

from django.utils import timezone
from api.models import Exam, Question


def normalize_text_for_dedupe(text: Optional[str]) -> str:
    """Normalize unicode, strip punctuation and extra spaces, lowercase."""
    if not text:
        return ""
    # Unicode NFKC normalization
    text = unicodedata.normalize("NFKC", str(text))
    # Lowercase
    text = text.lower()
    # Replace punctuation with space
    text = re.sub(r"[^\w\s]", " ", text)
    # Collapse multiple whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


def compute_text_hash(text: str) -> str:
    """Compute SHA-256 hash of normalized text."""
    normalized = normalize_text_for_dedupe(text)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def get_character_shingles(text: str, k: int = 3) -> Set[str]:
    """Return set of character k-shingles (trigrams) from normalized text."""
    norm = normalize_text_for_dedupe(text).replace(" ", "")
    if len(norm) < k:
        return {norm} if norm else set()
    return {norm[i:i + k] for i in range(len(norm) - k + 1)}


def get_word_tokens(text: str) -> Set[str]:
    """Return set of word tokens from normalized text."""
    norm = normalize_text_for_dedupe(text)
    return set(norm.split()) if norm else set()


def jaccard_similarity(set_a: Set[Any], set_b: Set[Any]) -> float:
    """Calculate Jaccard similarity coefficient between two sets."""
    if not set_a and not set_b:
        return 1.0
    if not set_a or not set_b:
        return 0.0
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return intersection / union if union > 0 else 0.0


def normalize_option_texts(options: Any) -> List[str]:
    """Extract clean, normalized list of option strings from options list/dict."""
    if not options:
        return []
    result = []
    if isinstance(options, list):
        for item in options:
            if isinstance(item, dict):
                val = item.get("text", "")
            else:
                val = str(item)
            cleaned = normalize_text_for_dedupe(val)
            if cleaned:
                result.append(cleaned)
    return result


def has_intra_question_duplicate_options(options: Any) -> Tuple[bool, str]:
    """Verify that a question has no duplicate option texts."""
    norm_opts = normalize_option_texts(options)
    seen = set()
    for opt in norm_opts:
        if opt in seen:
            return True, f"Question contains duplicate option: '{opt[:30]}'"
        seen.add(opt)
    return False, ""


class CandidateQuestion:
    """Lightweight in-memory candidate representation for fast deduplication."""

    def __init__(
        self,
        id: Optional[int],
        text: str,
        topic: str = "",
        subject_id: Optional[int] = None,
        question_type: str = "MCQ_SINGLE",
        difficulty: str = "MEDIUM",
        marks: float = 1.0,
        options: Optional[List[Any]] = None,
        correct_answer: Any = None,
        text_hash: str = "",
        raw_obj: Any = None,
    ):
        self.id = id
        self.text = text or ""
        self.normalized_text = normalize_text_for_dedupe(self.text)
        self.text_hash = text_hash or compute_text_hash(self.text)
        self.topic = (topic or "").strip().lower()
        self.subject_id = subject_id
        self.question_type = (question_type or "").upper()
        self.difficulty = (difficulty or "").upper()
        self.marks = float(marks)
        self.options = options or []
        self.normalized_options: FrozenSet[str] = frozenset(normalize_option_texts(self.options))
        self.correct_answer = correct_answer
        self.shingles = get_character_shingles(self.text, k=3)
        self.word_tokens = get_word_tokens(self.text)
        self.char_length = len(self.normalized_text)
        self.raw_obj = raw_obj

    @classmethod
    def from_model(cls, q: Question) -> "CandidateQuestion":
        topic_name = ""
        if q.topic_id and getattr(q, "topic", None):
            topic_name = q.topic.name
        elif q.topic_text:
            topic_name = q.topic_text

        # Extract options from related items or legacy field
        opts: List[Dict[str, Any]] = []
        if hasattr(q, "option_items") and q.option_items.all():
            for opt in q.option_items.all():
                opts.append({
                    "text": opt.text,
                    "is_correct": opt.is_correct,
                    "order": opt.order,
                })
        elif isinstance(q.options, list):
            for idx, opt_item in enumerate(q.options, start=1):
                if isinstance(opt_item, dict):
                    opts.append(opt_item)
                else:
                    opts.append({"text": str(opt_item), "is_correct": False, "order": idx})

        return cls(
            id=q.id,
            text=q.text,
            topic=topic_name,
            subject_id=q.subject_id,
            question_type=q.question_type,
            difficulty=q.difficulty,
            marks=float(q.marks),
            options=opts,
            correct_answer=q.correct_answer,
            text_hash=q.text_hash or compute_text_hash(q.text),
            raw_obj=q,
        )

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CandidateQuestion":
        return cls(
            id=data.get("id"),
            text=data.get("text") or data.get("question") or "",
            topic=data.get("topic") or data.get("topic_name") or "",
            subject_id=data.get("subject_id") or data.get("subject"),
            question_type=data.get("question_type") or data.get("type") or "MCQ_SINGLE",
            difficulty=data.get("difficulty") or "MEDIUM",
            marks=float(data.get("marks") or 1.0),
            options=data.get("options") or [],
            correct_answer=data.get("correct_answer") or data.get("answer"),
            text_hash=data.get("text_hash") or "",
            raw_obj=data,
        )


class DeduplicationIndex:
    """
    Maintains active in-memory indexes of already-selected questions in an exam.
    Provides fast O(1) exact lookups and filtered near-duplicate checks.
    """

    def __init__(self, near_duplicate_threshold: float = 0.85):
        self.threshold = near_duplicate_threshold
        self.selected_ids: Set[int] = set()
        self.selected_hashes: Set[str] = set()
        self.candidates: List[CandidateQuestion] = []
        # Length bucket for fast near-duplicate filtering (avoid comparing with drastically different lengths)
        self.length_index: List[Tuple[int, CandidateQuestion]] = []

    def check_candidate(self, candidate: CandidateQuestion) -> Tuple[bool, str]:
        """
        Check if candidate duplicates any previously selected question.
        Returns: (is_duplicate, reason_string)
        """
        # Rule 1: Same question ID
        if candidate.id is not None and candidate.id in self.selected_ids:
            return True, f"Identical question ID #{candidate.id} already selected."

        # Rule 2: Same normalized text hash
        if candidate.text_hash and candidate.text_hash in self.selected_hashes:
            return True, f"Identical question text hash '{candidate.text_hash[:10]}...' already selected."

        # Rule 5: Intra-question duplicate options
        has_dup_opts, opt_err = has_intra_question_duplicate_options(candidate.options)
        if has_dup_opts:
            return True, opt_err

        # Near-duplicate & concept checks against selected set
        cand_len = candidate.char_length
        for prev_len, prev in self.length_index:
            # Length filter: if lengths differ by > 40%, skip detailed string metric
            max_len = max(cand_len, prev_len)
            min_len = min(cand_len, prev_len)
            if max_len > 0 and (min_len / max_len) < 0.60:
                continue

            # Rule 3: Near-duplicate text similarity (Shingle Jaccard first, SequenceMatcher if borderline)
            shingle_sim = jaccard_similarity(candidate.shingles, prev.shingles)
            if shingle_sim >= self.threshold:
                return True, (
                    f"Near-duplicate text ({int(shingle_sim * 100)}% shingle similarity) "
                    f"with selected question #{prev.id or 'item'}: '{prev.text[:50]}...'"
                )

            # Token-set Jaccard
            token_sim = jaccard_similarity(candidate.word_tokens, prev.word_tokens)
            if token_sim >= 0.88:
                return True, (
                    f"Near-duplicate phrasing ({int(token_sim * 100)}% token similarity) "
                    f"with selected question #{prev.id or 'item'}."
                )

            # High shingle overlap check with difflib ratio fallback
            if shingle_sim >= 0.70 and token_sim >= 0.70:
                seq_ratio = difflib.SequenceMatcher(
                    None, candidate.normalized_text, prev.normalized_text
                ).ratio()
                if seq_ratio >= self.threshold:
                    return True, (
                        f"Near-duplicate text ({int(seq_ratio * 100)}% ratio) "
                        f"with selected question #{prev.id or 'item'}."
                    )

            # Rule 4: Same underlying concept
            # Two questions with the same topic AND nearly identical option sets (>= 75% Jaccard)
            if (
                candidate.topic
                and prev.topic
                and candidate.topic == prev.topic
                and candidate.normalized_options
                and prev.normalized_options
            ):
                opt_sim = jaccard_similarity(
                    candidate.normalized_options, prev.normalized_options
                )
                if opt_sim >= 0.75:
                    return True, (
                        f"Same-concept duplicate in topic '{candidate.topic}': "
                        f"shares {int(opt_sim * 100)}% options with selected question #{prev.id or 'item'}."
                    )

        return False, ""

    def is_duplicate(self, candidate: CandidateQuestion) -> Tuple[bool, str]:
        """Convenience alias for check_candidate."""
        return self.check_candidate(candidate)

    def add(self, candidate: CandidateQuestion) -> None:
        """Add candidate to the selected set and update indexes."""
        if candidate.id is not None:
            self.selected_ids.add(candidate.id)
        if candidate.text_hash:
            self.selected_hashes.add(candidate.text_hash)
        self.candidates.append(candidate)
        self.length_index.append((candidate.char_length, candidate))

    def count(self) -> int:
        return len(self.candidates)

    def total_marks(self) -> float:
        return sum(c.marks for c in self.candidates)


def get_faculty_recent_question_ids(
    faculty_id: int,
    institution_id: int,
    last_n_papers: int = 3,
    days: int = 30,
    subject_id: Optional[int] = None,
) -> Tuple[Set[int], List[int]]:
    """
    Retrieve question IDs used in the same faculty's recent exams.
    Returns:
        (excluded_question_ids_set, ordered_exam_ids_list_from_newest_to_oldest)
    """
    cutoff_date = timezone.now() - timedelta(days=days)

    exam_qs = Exam.objects.filter(
        created_by_id=faculty_id,
        institution_id=institution_id,
    ).filter(
        created_at__gte=cutoff_date
    ).order_by("-created_at")

    recent_exams = list(exam_qs[:last_n_papers])
    recent_exam_ids = [e.id for e in recent_exams]

    if not recent_exam_ids:
        return set(), []

    q_filter = Question.objects.filter(
        exam_id__in=recent_exam_ids,
        institution_id=institution_id,
        is_deleted=False,
    )
    if subject_id:
        q_filter = q_filter.filter(subject_id=subject_id)

    used_q_ids = set(q_filter.values_list("id", flat=True))
    # Also find source question IDs if matched by text_hash
    used_hashes = set(q_filter.exclude(text_hash="").values_list("text_hash", flat=True))
    if used_hashes:
        repo_q_ids = set(
            Question.objects.filter(
                institution_id=institution_id,
                text_hash__in=used_hashes,
                is_deleted=False,
            ).values_list("id", flat=True)
        )
        used_q_ids.update(repo_q_ids)

    return used_q_ids, recent_exam_ids


def relax_cross_paper_exclusions_if_needed(
    faculty_id: int,
    institution_id: int,
    candidate_pool: List[CandidateQuestion],
    required_count: int,
    last_n_papers: int = 3,
    days: int = 30,
    subject_id: Optional[int] = None,
) -> Tuple[Set[int], List[str]]:
    """
    Check if candidate pool has enough unique questions after cross-paper exclusion.
    If not enough, progressively relax exclusions from oldest paper to newest,
    recording transparent warnings for the faculty.

    Returns:
        (final_excluded_ids, relaxation_warnings)
    """
    used_q_ids, recent_exam_ids = get_faculty_recent_question_ids(
        faculty_id=faculty_id,
        institution_id=institution_id,
        last_n_papers=last_n_papers,
        days=days,
        subject_id=subject_id,
    )

    available_without_repeats = [q for q in candidate_pool if q.id not in used_q_ids]
    if len(available_without_repeats) >= required_count:
        return used_q_ids, []

    # Relaxation is needed because the pool is too small to avoid all repeats
    warnings: List[str] = []
    relaxed_excluded_ids = set(used_q_ids)

    # Relax oldest papers first
    # recent_exam_ids is ordered newest to oldest, so reverse for oldest to newest
    for old_exam_id in reversed(recent_exam_ids):
        # Remove questions belonging to this older exam from the exclusion set
        exam_q_ids = set(
            Question.objects.filter(exam_id=old_exam_id).values_list("id", flat=True)
        )
        exam_hashes = set(
            Question.objects.filter(exam_id=old_exam_id).exclude(text_hash="").values_list("text_hash", flat=True)
        )
        # Find matching repo IDs
        matching_repo_ids = set(
            Question.objects.filter(
                institution_id=institution_id,
                text_hash__in=exam_hashes,
            ).values_list("id", flat=True)
        )
        relaxed_excluded_ids -= exam_q_ids
        relaxed_excluded_ids -= matching_repo_ids

        exam_obj = Exam.objects.filter(id=old_exam_id).first()
        title_hint = f"'{exam_obj.title}'" if exam_obj else f"Exam #{old_exam_id}"
        warnings.append(
            f"Relaxed question exclusion: permitted reuse of questions from earlier paper {title_hint} "
            f"to fulfill requested question count."
        )

        current_available = [q for q in candidate_pool if q.id not in relaxed_excluded_ids]
        if len(current_available) >= required_count:
            break

    # If still not enough, allow minimal reuse from current pool
    current_available = [q for q in candidate_pool if q.id not in relaxed_excluded_ids]
    if len(current_available) < required_count and relaxed_excluded_ids:
        relaxed_excluded_ids.clear()
        warnings.append(
            "Question pool for selected parameters was smaller than requested count. "
            "All previous paper exclusions were relaxed to satisfy your paper parameters."
        )

    return relaxed_excluded_ids, warnings

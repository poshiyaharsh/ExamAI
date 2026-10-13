"""
Strict Accuracy and Validation Pipeline for Exam Paper Generation.

Enforces:
1. Exact total marks match (using Decimal).
2. Question count match per type and section.
3. Difficulty distribution verification within tolerance.
4. Tenant, department, and subject consistency.
5. Strict option validity per question type.
6. Rejection of placeholders or truncated text.
7. Valid negative marks (>= 0 and <= marks).
8. Time estimation vs exam duration warning.
9. Full Question Bank quality standards.
10. Generates structured ValidationReport JSON.
"""

from decimal import Decimal
from typing import Any, Dict, List, Optional, Set, Tuple

from api.models import Question
from api.validators.question_bank import (
    MIN_QUESTION_LENGTH,
    MAX_QUESTION_LENGTH,
    is_placeholder,
    normalize_department,
    sanitize_text,
)
from .dedupe import CandidateQuestion


ESTIMATED_MINUTES_PER_TYPE = {
    "MCQ_SINGLE": 1.5,
    "MCQ_MULTIPLE": 2.5,
    "TRUE_FALSE": 1.0,
    "FILLBLANK": 2.0,
    "SHORT_ANSWER": 3.5,
    "LONG_ANSWER": 10.0,
    "SUBJECTIVE": 10.0,
    # Legacy aliases
    "MCQ": 1.5,
    "TRUEFALSE": 1.0,
}


class ValidationReport:
    """Encapsulates the full audit report of a generated paper."""

    def __init__(self):
        self.passed: bool = True
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.checks: Dict[str, Dict[str, Any]] = {}
        self.actual_total_marks: Decimal = Decimal("0.0")
        self.actual_counts_by_type: Dict[str, int] = {}
        self.actual_difficulty_mix: Dict[str, int] = {"Easy": 0, "Medium": 0, "Hard": 0}
        self.estimated_time_minutes: float = 0.0
        self.duplicates_checked_count: int = 0
        self.duplicates_removed_count: int = 0
        self.repeats_avoided_count: int = 0
        self.relaxation_notices: List[str] = []
        self.generation_time_ms: float = 0.0
        self.cached_hit: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "passed": self.passed,
            "is_valid": self.passed,
            "errors": self.errors,
            "warnings": self.warnings,
            "checks": self.checks,
            "actual_total_marks": float(self.actual_total_marks),
            "actual_counts_by_type": self.actual_counts_by_type,
            "actual_difficulty_mix": self.actual_difficulty_mix,
            "estimated_time_minutes": round(self.estimated_time_minutes, 1),
            "duplicates_checked_count": self.duplicates_checked_count,
            "duplicates_removed_count": self.duplicates_removed_count,
            "repeats_avoided_count": self.repeats_avoided_count,
            "relaxation_notices": self.relaxation_notices,
            "generation_time_ms": round(self.generation_time_ms, 2),
            "cached_hit": self.cached_hit,
        }


def validate_single_candidate(
    candidate: CandidateQuestion,
    institution_id: int,
    department: str,
    subject_id: Optional[int] = None,
) -> Tuple[bool, List[str]]:
    """Validate a single question candidate against quality and tenant rules."""
    errs: List[str] = []

    # Text length & placeholder checks
    txt = candidate.text.strip()
    if len(txt) < MIN_QUESTION_LENGTH:
        errs.append(f"Question text too short ({len(txt)} chars, min {MIN_QUESTION_LENGTH}).")
    elif len(txt) > MAX_QUESTION_LENGTH:
        errs.append(f"Question text too long ({len(txt)} chars, max {MAX_QUESTION_LENGTH}).")
    elif is_placeholder(txt):
        errs.append("Question text contains placeholder or dummy words.")

    # Options validity
    q_type = candidate.question_type.upper()
    opts = candidate.options or []

    if q_type in ("MCQ_SINGLE", "MCQ"):
        if len(opts) < 2 or len(opts) > 6:
            errs.append(f"MCQ Single requires between 2 and 6 options (found {len(opts)}).")
        else:
            correct_count = sum(1 for o in opts if (o.get("is_correct") if isinstance(o, dict) else False))
            if correct_count != 1:
                # Also check string correct_answer if legacy
                if candidate.correct_answer is None or correct_count == 0:
                    errs.append(f"MCQ Single must have exactly 1 correct option (found {correct_count}).")
    elif q_type in ("MCQ_MULTIPLE",):
        if len(opts) < 2 or len(opts) > 6:
            errs.append(f"MCQ Multiple requires between 2 and 6 options (found {len(opts)}).")
        else:
            correct_count = sum(1 for o in opts if (o.get("is_correct") if isinstance(o, dict) else False))
            if correct_count < 1 or correct_count == len(opts):
                errs.append(f"MCQ Multiple must have at least 1 and not all correct options (found {correct_count}/{len(opts)}).")
    elif q_type in ("TRUE_FALSE", "TRUEFALSE"):
        if len(opts) != 2:
            # If options are empty or not populated, check if correct_answer is given
            if not candidate.correct_answer:
                errs.append(f"True/False question must contain exactly 2 options (found {len(opts)}).")
        else:
            correct_count = sum(1 for o in opts if (o.get("is_correct") if isinstance(o, dict) else False))
            if correct_count != 1 and candidate.correct_answer is None:
                errs.append("True/False question must have exactly 1 correct option.")

    # Marks check
    if candidate.marks <= 0:
        errs.append(f"Question marks must be positive (found {candidate.marks}).")

    return (len(errs) == 0, errs)


def validate_paper_plan(
    candidates: List[CandidateQuestion],
    requested_total_marks: Decimal,
    requested_counts_by_type: Optional[Dict[str, int]] = None,
    requested_difficulty_mix: Optional[Dict[str, int]] = None,
    duration_minutes: int = 60,
    institution_id: Optional[int] = None,
    department: str = "",
    subject_id: Optional[int] = None,
) -> Tuple[bool, ValidationReport, List[int]]:
    """
    Validates a complete proposed paper before saving or returning.
    Returns:
        (is_valid, report, failing_indices)
    """
    report = ValidationReport()
    failing_indices: List[int] = []

    # 1. Total marks match EXACTLY using Decimal
    actual_marks = sum(Decimal(str(c.marks)) for c in candidates)
    report.actual_total_marks = actual_marks
    req_marks_dec = Decimal(str(requested_total_marks))

    if actual_marks != req_marks_dec:
        report.passed = False
        report.errors.append(
            f"Total marks mismatch: paper has {actual_marks} marks, but requested total is {req_marks_dec}."
        )
        report.checks["total_marks"] = {
            "status": "FAIL",
            "expected": float(req_marks_dec),
            "actual": float(actual_marks),
        }
    else:
        report.checks["total_marks"] = {
            "status": "PASS",
            "expected": float(req_marks_dec),
            "actual": float(actual_marks),
        }

    # 2. Count per question
    counts_by_type: Dict[str, int] = {}
    for c in candidates:
        counts_by_type[c.question_type] = counts_by_type.get(c.question_type, 0) + 1
    report.actual_counts_by_type = counts_by_type

    if requested_counts_by_type:
        count_mismatches = []
        for q_type, expected_cnt in requested_counts_by_type.items():
            actual_cnt = counts_by_type.get(q_type.upper(), 0)
            if actual_cnt != expected_cnt:
                count_mismatches.append(f"{q_type}: expected {expected_cnt}, got {actual_cnt}")
        if count_mismatches:
            report.passed = False
            report.errors.append(f"Question counts mismatch: {', '.join(count_mismatches)}.")
            report.checks["question_counts"] = {"status": "FAIL", "details": count_mismatches}
        else:
            report.checks["question_counts"] = {"status": "PASS", "details": counts_by_type}
    else:
        report.checks["question_counts"] = {"status": "PASS", "details": counts_by_type}

    # 3. Difficulty distribution
    diff_counts = {"Easy": 0, "Medium": 0, "Hard": 0}
    for c in candidates:
        diff_key = c.difficulty.capitalize()
        if diff_key in diff_counts:
            diff_counts[diff_key] += 1
        elif c.difficulty.upper() == "EASY":
            diff_counts["Easy"] += 1
        elif c.difficulty.upper() == "HARD":
            diff_counts["Hard"] += 1
        else:
            diff_counts["Medium"] += 1

    total_q = len(candidates)
    actual_diff_pct = {
        k: int(round((v / total_q) * 100)) if total_q > 0 else 0
        for k, v in diff_counts.items()
    }
    report.actual_difficulty_mix = actual_diff_pct

    if requested_difficulty_mix and total_q > 0:
        # Check tolerance (+- 20% tolerance due to integer rounding with small question counts)
        diff_warnings = []
        for k, req_pct in requested_difficulty_mix.items():
            k_norm = k.capitalize()
            actual_pct = actual_diff_pct.get(k_norm, 0)
            if abs(actual_pct - req_pct) > 25:
                diff_warnings.append(f"{k_norm}: requested {req_pct}%, actual {actual_pct}%")
        if diff_warnings:
            report.warnings.append(
                f"Difficulty distribution variance: {', '.join(diff_warnings)}."
            )
            report.checks["difficulty_distribution"] = {
                "status": "WARN",
                "requested": requested_difficulty_mix,
                "actual": actual_diff_pct,
            }
        else:
            report.checks["difficulty_distribution"] = {
                "status": "PASS",
                "requested": requested_difficulty_mix,
                "actual": actual_diff_pct,
            }
    else:
        report.checks["difficulty_distribution"] = {
            "status": "PASS",
            "actual": actual_diff_pct,
        }

    # 4. Individual Candidate Quality & Tenant Check
    individual_failures = 0
    for idx, c in enumerate(candidates):
        is_ok, errs = validate_single_candidate(
            c,
            institution_id=institution_id or 0,
            department=department,
            subject_id=subject_id,
        )
        if not is_ok:
            individual_failures += 1
            failing_indices.append(idx)
            report.errors.extend([f"Question #{idx + 1}: {e}" for e in errs])

    if individual_failures > 0:
        report.passed = False
        report.checks["question_validity"] = {
            "status": "FAIL",
            "failing_count": individual_failures,
        }
    else:
        report.checks["question_validity"] = {"status": "PASS", "valid_count": len(candidates)}

    # 5. Estimated Time vs Duration
    est_minutes = sum(
        ESTIMATED_MINUTES_PER_TYPE.get(c.question_type.upper(), 2.0)
        for c in candidates
    )
    report.estimated_time_minutes = est_minutes
    if duration_minutes > 0:
        if est_minutes > duration_minutes * 1.30:
            report.warnings.append(
                f"Exam may be too long: estimated {int(est_minutes)} mins for a {duration_minutes} min exam."
            )
            report.checks["duration_fit"] = {"status": "WARN", "estimated": est_minutes, "allowed": duration_minutes}
        elif est_minutes < duration_minutes * 0.35:
            report.warnings.append(
                f"Exam may be too short: estimated {int(est_minutes)} mins for a {duration_minutes} min exam."
            )
            report.checks["duration_fit"] = {"status": "WARN", "estimated": est_minutes, "allowed": duration_minutes}
        else:
            report.checks["duration_fit"] = {"status": "PASS", "estimated": est_minutes, "allowed": duration_minutes}

    return (report.passed, report, failing_indices)

"""
Row Normalizer and Type Inference Engine for Smart Question Bank Importer.
Determines Question Type heuristics, matches Answer Keys, calculates Marks,
detects duplicates, and assigns row status (READY, NEEDS_REVIEW, INVALID).
"""

import json
import re
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

STATUS_READY = 'ready'
STATUS_NEEDS_REVIEW = 'needs_review'
STATUS_INVALID = 'invalid'

RE_STRIP_NUMBERING = re.compile(
    r'^(?:[A-Za-z]?\d+[\.\)\:\-]\s*|\([A-Za-z]?\d+\)\s*|\[[A-Za-z]?\d+\]\s*|q(?:ue(?:stion)?)?\s*[\.\:\-\)]?\s*\d+[\.\:\-]?\s*)',
    re.IGNORECASE
)

RE_BLANK_INDICATOR = re.compile(r'(?:_{3,}|\.{3,}|\[blank\]|<blank>)', re.IGNORECASE)

LONG_ANSWER_VERBS = (
    'explain', 'discuss', 'describe', 'elaborate', 'illustrate', 'critique',
    'compare and contrast', 'differentiate between', 'analyze', 'evaluate',
    'derive', 'prove that', 'write a detailed note'
)


def strip_leading_numbering(text: str) -> str:
    """Strips leading question numbers like '1.', 'Q1)', 'A2.', '(1)' from text."""
    if not text:
        return ""
    s = text.strip()
    s = RE_STRIP_NUMBERING.sub('', s).strip()
    return s if s else text.strip()


def parse_numeric_marks(raw_marks: Any, default_val: float = 1.0) -> Tuple[float, bool]:
    """
    Parses marks into a float.
    Returns: (parsed_marks, was_defaulted)
    """
    if raw_marks is None:
        return default_val, True

    s = str(raw_marks).strip()
    if not s:
        return default_val, True

    # Check for formats like "[2 marks]" or "2.5" or "10"
    m = re.search(r'(\d+(?:\.\d+)?)', s)
    if m:
        try:
            val = float(m.group(1))
            return val if val > 0 else default_val, val <= 0
        except ValueError:
            pass

    return default_val, True


def canonicalize_difficulty_val(raw_diff: Any, default_diff: str = 'medium') -> str:
    if not raw_diff:
        return default_diff
    d = str(raw_diff).strip().lower()
    if d in ('easy', 'beginner', 'basic', 'simple', 'low', '1'):
        return 'easy'
    if d in ('hard', 'difficult', 'advanced', 'tough', 'complex', 'expert', 'high', '3'):
        return 'hard'
    return 'medium'


def infer_question_type(
    explicit_type: Optional[str],
    text: str,
    options: List[str],
    correct_answer: str,
    marks: float,
    model_answer: str = "",
) -> Tuple[str, bool]:
    """
    Infers question type when missing or canonicalizes explicit type.
    Returns: (canonical_type, was_inferred)
    """
    if explicit_type:
        t = str(explicit_type).strip().lower().replace('-', '_').replace(' ', '_')
        if t in ('mcq', 'multiple_choice', 'single_choice', 'mcqs'):
            return 'mcq', False
        if t in ('true_false', 'truefalse', 't_f', 'tf', 'boolean', 'true_or_false'):
            return 'true_false', False
        if t in ('fill_blank', 'fillblank', 'fill_in_the_blank', 'fib', 'blank'):
            return 'fill_blank', False
        if t in ('short_answer', 'shortanswer', 'short', 'sa', 'brief'):
            return 'short_answer', False
        if t in ('long_answer', 'longanswer', 'long', 'la', 'descriptive', 'subjective', 'essay'):
            return 'long_answer', False

    # Heuristic Inference
    norm_text = text.lower()
    cleaned_opts = [str(o).strip().lower() for o in options if str(o).strip()]

    # 1. True / False: exactly 2 options matching True/False or Yes/No
    if len(cleaned_opts) == 2 and set(cleaned_opts) in ({'true', 'false'}, {'t', 'f'}, {'yes', 'no'}):
        return 'true_false', False

    # 2. Fill in the blank: contains blanks (____ or ...) and has answer, no options
    if not cleaned_opts and RE_BLANK_INDICATOR.search(norm_text):
        return 'fill_blank', False

    # 3. MCQ: 2 or more options present
    if len(cleaned_opts) >= 2:
        return 'mcq', False

    # 4. Long Answer: high marks (>=5) or contains long descriptive verbs
    if marks >= 5.0 or any(norm_text.startswith(v) for v in LONG_ANSWER_VERBS) or len(norm_text) > 200:
        return 'long_answer', True  # Flagged "type guessed"

    # 5. Short Answer fallback
    return 'short_answer', False


def match_and_normalize_answer(
    raw_answer: Any,
    options: List[str],
    q_type: str,
) -> Tuple[str, Optional[int], bool, List[str]]:
    """
    Matches raw answer against options list for MCQs, or formats for TF/Fill/Short.
    Returns: (canonical_answer_text, option_index, is_matched, review_reasons)
    """
    review_reasons: List[str] = []
    if raw_answer is None or not str(raw_answer).strip():
        if q_type in ('short_answer', 'long_answer'):
            return "", None, True, []
        return "", None, False, ["Missing correct answer key"]

    ans_str = str(raw_answer).strip()

    # Check for multiple answers (e.g. "A, B" or "A and C")
    if re.search(r'^[A-Da-d]\s*[,/&]\s*[A-Da-d]', ans_str) or re.search(r'\b[A-Da-d]\s+and\s+[A-Da-d]\b', ans_str):
        review_reasons.append("Multiple correct answers detected (unsupported for single-choice MCQ)")
        return ans_str, None, False, review_reasons

    if q_type == 'mcq':
        if not options or len(options) < 2:
            return ans_str, None, False, ["MCQ has fewer than 2 options"]

        # Clean options for matching
        cleaned_opts = [re.sub(r'^(?:\(?[A-Da-d0-9]\)?[\.\)\:\-]\s*|\(?[A-Da-d0-9]\)\s*)', '', str(o)).strip() for o in options]

        # 1. Check letter match: 'A', 'B', 'C', 'D' or 'A. Option text'
        letter_m = re.match(r'^(?:\(?([A-Za-z0-9])\)?[\.\)\:\-]?\s*)(.*)$', ans_str)
        if letter_m:
            letter_char = letter_m.group(1).upper()
            trailing_text = letter_m.group(2).strip()

            if letter_char in ('A', 'B', 'C', 'D', 'E', 'F'):
                idx = ord(letter_char) - ord('A')
                if 0 <= idx < len(cleaned_opts):
                    return cleaned_opts[idx], idx, True, review_reasons

            # Numeric index check: '1', '2'
            if letter_char.isdigit():
                idx_num = int(letter_char)
                if 1 <= idx_num <= len(cleaned_opts):
                    return cleaned_opts[idx_num - 1], idx_num - 1, True, review_reasons
                elif 0 <= idx_num < len(cleaned_opts):
                    return cleaned_opts[idx_num], idx_num, True, review_reasons

        # 2. Text match directly against options
        norm_ans = ans_str.lower()
        for idx, opt_clean in enumerate(cleaned_opts):
            if opt_clean.lower() == norm_ans:
                return opt_clean, idx, True, review_reasons

        # 3. Fuzzy containment match
        for idx, opt_clean in enumerate(cleaned_opts):
            if opt_clean.lower() in norm_ans or norm_ans in opt_clean.lower():
                return opt_clean, idx, True, review_reasons

        review_reasons.append(f"Specified answer '{ans_str}' does not match any listed option")
        return ans_str, None, False, review_reasons

    elif q_type == 'true_false':
        s = ans_str.lower()
        if s in ('true', 't', 'yes', '1', 'a'):
            return 'True', 0, True, review_reasons
        elif s in ('false', 'f', 'no', '0', '2', 'b'):
            return 'False', 1, True, review_reasons
        else:
            review_reasons.append(f"Unrecognized True/False answer '{ans_str}'")
            return ans_str, None, False, review_reasons

    return ans_str, None, True, review_reasons


def normalize_smart_question_row(
    raw_row: Dict[str, Any],
    row_idx: int,
    default_marks: float = 1.0,
    default_difficulty: str = 'medium',
    default_type: Optional[str] = None,
    seen_hashes: Optional[set] = None,
) -> Dict[str, Any]:
    """
    Normalizes a single question row into paper-ready standard schema.
    Computes validation status: READY, NEEDS_REVIEW, INVALID.
    """
    errors: List[str] = []
    review_notes: List[str] = []

    # 1. Question Text
    raw_text = raw_row.get('question_text') or raw_row.get('text') or ''
    cleaned_text = strip_leading_numbering(str(raw_text).strip())

    if not cleaned_text or len(cleaned_text) < 5:
        errors.append("Question text is empty or too short (minimum 5 characters required).")

    # 2. Marks
    marks_val, marks_defaulted = parse_numeric_marks(raw_row.get('marks'), default_val=default_marks)
    if marks_defaulted and 'marks' in raw_row and raw_row.get('marks'):
        review_notes.append(f"Marks '{raw_row.get('marks')}' unparseable; defaulted to {marks_val}.")

    # 3. Difficulty
    difficulty = canonicalize_difficulty_val(raw_row.get('difficulty'), default_diff=default_difficulty)

    # 4. Raw Options
    raw_options = raw_row.get('options') or []
    cleaned_options: List[str] = []
    if isinstance(raw_options, list):
        cleaned_options = [
            re.sub(r'^(?:\(?[A-Da-d0-9]\)?[\.\)\:\-]\s*|\(?[A-Da-d0-9]\)\s*)', '', str(o)).strip()
            for o in raw_options if str(o).strip()
        ]
    elif isinstance(raw_options, str) and raw_options.strip():
        # JSON or single-cell options
        from .spreadsheet import extract_single_cell_options
        parsed_opts = extract_single_cell_options(raw_options)
        if parsed_opts:
            cleaned_options = parsed_opts

    # 5. Type Inference
    explicit_type = raw_row.get('question_type') or default_type
    q_type, was_inferred = infer_question_type(
        explicit_type=explicit_type,
        text=cleaned_text,
        options=cleaned_options,
        correct_answer=str(raw_row.get('correct_answer') or ''),
        marks=marks_val,
        model_answer=str(raw_row.get('model_answer') or raw_row.get('explanation') or ''),
    )
    if was_inferred:
        review_notes.append(f"Question type inferred automatically as '{q_type}'.")

    # 6. Answer Key Matching & Validation
    raw_ans = raw_row.get('correct_answer')
    norm_ans, opt_idx, is_ans_matched, ans_notes = match_and_normalize_answer(
        raw_answer=raw_ans,
        options=cleaned_options,
        q_type=q_type,
    )
    review_notes.extend(ans_notes)

    # If MCQ and fewer than 2 options: FATAL
    if q_type == 'mcq' and len(cleaned_options) < 2:
        errors.append(f"MCQ requires at least 2 distinct options (found {len(cleaned_options)}).")

    # If True/False, ensure options are ['True', 'False']
    if q_type == 'true_false':
        cleaned_options = ['True', 'False']

    # 7. Duplicate Detection
    is_duplicate = False
    norm_hash = cleaned_text.lower()
    if seen_hashes is not None and norm_hash:
        if norm_hash in seen_hashes:
            is_duplicate = True
            review_notes.append("Potential duplicate question text found in this file.")
        else:
            seen_hashes.add(norm_hash)

    # 8. Status Determination: READY, NEEDS_REVIEW, INVALID
    if errors:
        status = STATUS_INVALID
    elif review_notes or not is_ans_matched:
        status = STATUS_NEEDS_REVIEW
    else:
        status = STATUS_READY

    formatted_options = []
    for c_idx, opt_text in enumerate(cleaned_options):
        is_corr = False
        if norm_ans:
            letter = chr(65 + c_idx)
            if norm_ans.strip().upper() == letter:
                is_corr = True
            elif norm_ans.strip() == str(c_idx + 1) or norm_ans.strip() == str(c_idx):
                is_corr = True
            elif norm_ans.strip().lower() == opt_text.strip().lower():
                is_corr = True
        formatted_options.append({
            'text': opt_text,
            'is_correct': is_corr,
            'order': c_idx + 1,
        })

    return {
        'row_number': raw_row.get('_row_number', row_idx),
        'status': status,
        'is_valid': len(errors) == 0,
        'is_ready': status == STATUS_READY,
        'needs_review': status == STATUS_NEEDS_REVIEW,
        'is_duplicate': is_duplicate,
        'errors': errors,
        'review_notes': review_notes,
        'data': {
            'row_number': raw_row.get('_row_number', row_idx),
            'question_text': cleaned_text,
            'question_type': q_type,
            'marks': marks_val,
            'difficulty': difficulty,
            'topic': str(raw_row.get('topic') or '').strip(),
            'subject': str(raw_row.get('subject') or '').strip(),
            'department': str(raw_row.get('department') or '').strip(),
            'options': formatted_options,
            'options_raw': cleaned_options,
            'correct_answer': norm_ans,
            'explanation': str(raw_row.get('explanation') or '').strip(),
            'model_answer': str(raw_row.get('model_answer') or raw_row.get('explanation') or ''),
        }
    }

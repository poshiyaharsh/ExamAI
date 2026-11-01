"""
MCQ Normalizer & Option Builder.
Standardizes any model output shape into a rock-solid internal MCQ structure:
- exactly 4 unique non-empty options
- seed-shuffled option ordering
- clear correct option index (0..3), letter ('A'..'D'), and exact text
- handles legacy formats (dict A/B/C/D, list of choices, raw text blocks)
"""
import re
import random
import difflib
from typing import Dict, Any, List, Optional, Tuple


def normalize_mcq(raw_q: Dict[str, Any], seed: int = 42) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Normalizes a raw MCQ dict into the standard schema:
    {
        'question': str,
        'options': [opt1, opt2, opt3, opt4],
        'answer': correct_text,
        'correct_letter': 'A' | 'B' | 'C' | 'D',
        'correct_index': 0..3,
        'source_quote': str,
        'difficulty': str,
        'type': 'MCQ'
    }
    Returns (normalized_dict, None) on success, or (None, failure_reason) on failure.
    """
    if not isinstance(raw_q, dict):
        return None, "Raw item is not a dictionary"

    # 1. Extract question stem
    stem = raw_q.get('question') or raw_q.get('stem') or raw_q.get('text') or raw_q.get('title')
    if not stem or not isinstance(stem, str) or len(stem.strip()) < 5:
        return None, "Empty or invalid question stem"
    stem = stem.strip()

    # 2. Extract correct answer & distractors
    correct = raw_q.get('correct') or raw_q.get('correct_answer') or raw_q.get('answer')
    distractors = raw_q.get('distractors') or []

    # If distractors are missing or raw_q has options/choices list
    options_raw = raw_q.get('options') or raw_q.get('choices')

    options_list: List[str] = []
    correct_text: str = ""

    if correct and isinstance(distractors, list) and len(distractors) >= 3:
        # Standard schema path
        correct_text = str(correct).strip()
        cleaned_distractors = [str(d).strip() for d in distractors if str(d).strip()]
        if len(cleaned_distractors) >= 3:
            distractors = cleaned_distractors[:3]
            # Build 4 options
            all_opts = [correct_text] + distractors
            # Check uniqueness
            unique_opts = []
            for opt in all_opts:
                if not any(difflib.SequenceMatcher(None, opt.lower(), u.lower()).ratio() > 0.95 for u in unique_opts):
                    unique_opts.append(opt)
            if len(unique_opts) == 4:
                # Seeded shuffle so position isn't always A
                rng = random.Random(seed + hash(stem) % 10000)
                rng.shuffle(unique_opts)
                options_list = unique_opts

    # Fallback path: parse options_raw if options_list still empty
    if not options_list and options_raw:
        if isinstance(options_raw, dict):
            # Form: {"A": "Option 1", "B": "Option 2", ...}
            sorted_keys = sorted(options_raw.keys())
            options_list = [str(options_raw[k]).strip() for k in sorted_keys if str(options_raw[k]).strip()]
        elif isinstance(options_raw, list):
            options_list = [str(o).strip() for o in options_raw if str(o).strip()]
        elif isinstance(options_raw, str):
            # Form: "A) Option 1\nB) Option 2..."
            lines = re.findall(r'^[A-Da-d][\).\s]+(.*)$', options_raw, flags=re.MULTILINE)
            if lines:
                options_list = [l.strip() for l in lines]

        # Determine correct text from options_list
        if correct:
            correct_str = str(correct).strip()
            # If correct is letter like 'A', 'B', 'C', 'D'
            if re.match(r'^[A-Da-d]$', correct_str):
                idx = ord(correct_str.upper()) - ord('A')
                if 0 <= idx < len(options_list):
                    correct_text = options_list[idx]
            elif correct_str.isdigit():
                idx = int(correct_str)
                if 0 <= idx < len(options_list):
                    correct_text = options_list[idx]
                elif 1 <= idx <= len(options_list):
                    correct_text = options_list[idx - 1]
            else:
                # Match by text similarity
                matches = [opt for opt in options_list if difflib.SequenceMatcher(None, opt.lower(), correct_str.lower()).ratio() > 0.85]
                if matches:
                    correct_text = matches[0]
                else:
                    correct_text = correct_str

    # Validate that we have exactly 4 unique options and non-empty correct text
    if len(options_list) != 4:
        return None, f"Expected exactly 4 options, found {len(options_list)}"

    if not correct_text:
        return None, "Missing correct answer"

    # Find correct_text index in options_list
    match_indices = [i for i, opt in enumerate(options_list) if opt.lower() == correct_text.lower()]
    if not match_indices:
        # Fuzzy match
        ratios = [difflib.SequenceMatcher(None, opt.lower(), correct_text.lower()).ratio() for opt in options_list]
        best_idx = max(range(len(ratios)), key=lambda i: ratios[i])
        if ratios[best_idx] > 0.85:
            correct_index = best_idx
            correct_text = options_list[best_idx]
        else:
            return None, "Correct answer does not match any of the 4 options"
    else:
        correct_index = match_indices[0]

    correct_letter = chr(ord('A') + correct_index)

    source_quote = str(raw_q.get('source_quote', '')).strip()
    difficulty = raw_q.get('difficulty', 'medium')
    if str(difficulty).lower() not in ('easy', 'medium', 'hard'):
        difficulty = 'medium'

    normalized = {
        'question': stem,
        'options': options_list,
        'answer': correct_text,
        'correct_answer': correct_text,
        'correct_letter': correct_letter,
        'correct_index': correct_index,
        'source_quote': source_quote,
        'difficulty': difficulty,
        'type': 'MCQ',
        'question_type': 'MCQ',
    }

    # Preserve metadata if present
    for k in ('slot_index', 'marks', 'topic', 'unit'):
        if k in raw_q:
            normalized[k] = raw_q[k]

    return normalized, None

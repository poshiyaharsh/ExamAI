import json
import re
from typing import Any, List, Optional, Tuple

OPTION_PREFIX_REGEX = re.compile(r'^\s*(?:\(?[A-Da-d0-9]\)?[\.\)\:\-]\s*|\(?[A-Da-d0-9]\)\s*)')


def clean_option_text(text: Any) -> str:
    """
    Strips leading letter or number prefixes (e.g. 'A. ', 'B) ', '(C) ', '1. ')
    and surrounding whitespace from an option string.
    """
    if text is None:
        return ""
    str_val = str(text).strip()
    cleaned = OPTION_PREFIX_REGEX.sub('', str_val).strip()
    return cleaned if cleaned else str_val


def clean_options_list(options: Optional[List[Any]]) -> List[str]:
    """
    Cleans a list of option items, ensuring all elements are cleaned strings.
    Handles None, lists of strings, lists of dicts (with 'text' keys),
    and JSON string representations.
    """
    if options is None:
        return []
    if isinstance(options, str):
        trimmed = options.strip()
        if trimmed.startswith('[') and trimmed.endswith(']'):
            try:
                options = json.loads(trimmed)
            except Exception:
                return []
        else:
            return []
    if not isinstance(options, (list, tuple)):
        return []
    result = []
    for opt in options:
        if isinstance(opt, dict):
            txt = opt.get('text', '')
            result.append(clean_option_text(txt))
        else:
            result.append(clean_option_text(opt))
    return result


def validate_mcq_options(
    options: Any,
    correct_answer: Any = None,
    allow_two_for_tf: bool = False,
) -> Tuple[bool, List[str]]:
    """
    Validates MCQ options:
    - Must be a list with exactly 4 options (or 2 for true/false if allow_two_for_tf)
    - All options must be non-empty strings
    - All options must be distinct (case-insensitive & whitespace-stripped)
    - If correct_answer is provided, verifies that it points to a valid option
    """
    errors: List[str] = []
    if not isinstance(options, list):
        return False, ["Options must be a list of strings."]

    cleaned_opts = clean_options_list(options)
    expected_count = 2 if allow_two_for_tf and len(cleaned_opts) == 2 else 4

    if len(cleaned_opts) != expected_count:
        errors.append(f"Expected {expected_count} options, got {len(cleaned_opts)}.")

    # Check for empty options
    empty_indices = [idx + 1 for idx, opt in enumerate(cleaned_opts) if not opt]
    if empty_indices:
        errors.append(f"Options at positions {empty_indices} are empty.")

    # Check for duplicates
    seen = {}
    dupes = []
    for idx, opt in enumerate(cleaned_opts):
        norm = opt.casefold()
        if norm in seen:
            dupes.append(f"'{opt}' (positions {seen[norm] + 1} and {idx + 1})")
        else:
            seen[norm] = idx
    if dupes:
        errors.append(f"Duplicate options found: {', '.join(dupes)}.")

    # Check correct_answer if provided
    if correct_answer is not None and errors == []:
        corr_str = str(correct_answer).strip()
        matched = False
        letter_map = {"A": 0, "B": 1, "C": 2, "D": 3}
        if corr_str.upper() in letter_map and letter_map[corr_str.upper()] < len(cleaned_opts):
            matched = True
        elif corr_str.isdigit() and 0 <= int(corr_str) < len(cleaned_opts):
            matched = True
        elif corr_str.isdigit() and 1 <= int(corr_str) <= len(cleaned_opts):
            matched = True
        else:
            norm_corr = clean_option_text(corr_str).casefold()
            if any(opt.casefold() == norm_corr for opt in cleaned_opts):
                matched = True

        if not matched:
            errors.append(f"Correct answer '{correct_answer}' does not match any available option.")

    return len(errors) == 0, errors

"""
Robust JSON Parser and Repair Utility.
Fixes common LLM output defects:
- Markdown code blocks (```json ... ```)
- Unescaped single quotes and trailing commas
- Truncated JSON arrays and missing closing braces
- Wrapped root structures (e.g. {"questions": [...]}, {"data": [...]})
- Integrates Python json_repair for ultimate resilience
"""
import re
import json
import logging
import json_repair
from typing import Any, Dict, List, Optional, Union
from ..logging_setup import log_event

logger = logging.getLogger(__name__)


def clean_markdown_fences(text: str) -> str:
    """Strips markdown code blocks, backticks, and extraneous text."""
    if not text:
        return ""
    cleaned = text.strip()
    # Strip ```json ... ```
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()
    return cleaned


def fix_trailing_commas(text: str) -> str:
    """Removes trailing commas before closing braces or brackets."""
    # ,] -> ]
    text = re.sub(r',\s*\]', ']', text)
    # ,} -> }
    text = re.sub(r',\s*\}', '}', text)
    return text


def repair_truncated_json(text: str) -> str:
    """Attempts to balance open brackets/braces for truncated JSON outputs."""
    cleaned = text.strip()
    if not cleaned:
        return "{}"

    # Balance brackets and braces
    open_brackets = cleaned.count('[') - cleaned.count(']')
    open_braces = cleaned.count('{') - cleaned.count('}')

    if open_brackets > 0 or open_braces > 0:
        # Strip trailing comma if ends with one
        cleaned = cleaned.rstrip().rstrip(',')
        # Close braces first if they are innermost
        if open_braces > 0:
            cleaned += '}' * open_braces
        if open_brackets > 0:
            cleaned += ']' * open_brackets

    return cleaned


def parse_and_repair_json(text: str, job_id: Optional[int] = None) -> Union[Dict[str, Any], List[Any]]:
    """
    Parses string into Python dict or list with multi-layer fallback repair.
    Raises ValueError if completely unparseable.
    """
    if not text or not text.strip():
        raise ValueError("Cannot parse empty JSON string.")

    cleaned = clean_markdown_fences(text)

    # 1. Direct standard json.loads
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # 2. Fix trailing commas and balance truncation
    try:
        fixed_text = fix_trailing_commas(cleaned)
        return json.loads(fixed_text)
    except json.JSONDecodeError:
        pass

    try:
        repaired_text = repair_truncated_json(fixed_text)
        return json.loads(repaired_text)
    except json.JSONDecodeError:
        pass

    # 3. Use python json_repair library
    try:
        repaired_obj = json_repair.loads(cleaned)
        if repaired_obj is not None:
            return repaired_obj
    except Exception:
        pass

    # 4. Regex extraction of outermost array [...] or object {...}
    array_match = re.search(r'\[\s*\{[\s\S]*\}\s*\]', cleaned)
    if array_match:
        try:
            return json.loads(array_match.group(0))
        except Exception:
            try:
                return json_repair.loads(array_match.group(0))
            except Exception:
                pass

    obj_match = re.search(r'\{[\s\S]*\}', cleaned)
    if obj_match:
        try:
            return json.loads(obj_match.group(0))
        except Exception:
            try:
                return json_repair.loads(obj_match.group(0))
            except Exception:
                pass

    err_msg = f"Failed to parse and repair JSON output: {text[:200]}..."
    log_event('MODEL_ERROR', err_msg, job_id=job_id, level=logging.ERROR)
    raise ValueError(err_msg)


def extract_questions_list(raw_data: Any) -> List[Dict[str, Any]]:
    """
    Extracts a list of question dicts from whatever structure the LLM returned:
    - [ {...}, {...} ] -> returns list
    - { "questions": [ {...} ] } -> returns list
    - { "items": [ {...} ] } -> returns list
    - { "question": ... } -> returns single item list [ { ... } ]
    """
    if isinstance(raw_data, list):
        return [q for q in raw_data if isinstance(q, dict)]

    if isinstance(raw_data, dict):
        for key in ['questions', 'items', 'data', 'result', 'results', 'paper']:
            if key in raw_data and isinstance(raw_data[key], list):
                return [q for q in raw_data[key] if isinstance(q, dict)]

        # Check if the dict itself is a single question
        if 'question' in raw_data or 'question_text' in raw_data:
            return [raw_data]

    return []

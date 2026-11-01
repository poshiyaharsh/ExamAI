"""
Rubric Builder Module.
Provides deterministic, robust construction of grading rubrics for Short Answer and Long Answer questions.
Guarantees standard schema:
[
    {
        "key_points": [ ... ]
    }
]
"""
import re
from typing import Any, Dict, List, Optional


def clean_sentence(text: str) -> str:
    """Strips bullets, numbering, quotes, and excessive whitespace."""
    if not text:
        return ""
    s = str(text).strip()
    # Strip leading markdown bullets and numbering: e.g. "1. ", "- ", "* ", "(a) ", "1) "
    s = re.sub(r'^\s*([0-9]+[\.\)]|\([0-9a-zA-Z]+\)|[-*•+])\s*', '', s)
    # Strip markdown bold/italic wrapper
    s = re.sub(r'^\*{1,2}(.*?)\*{1,2}$', r'\1', s)
    # Strip surrounding quotes
    s = s.strip(' "\'“”‘’`')
    # Collapse multiple whitespace
    s = re.sub(r'\s+', ' ', s).strip()
    return s


def truncate_to_word_limit(text: str, max_words: int = 30) -> str:
    """Ensures a text string has at most max_words words and ends cleanly."""
    words = text.split()
    if len(words) <= max_words:
        return text
    truncated = " ".join(words[:max_words]).rstrip(',;:.-')
    if not truncated.endswith(('.', '!', '?')):
        truncated += '.'
    return truncated


def extract_first_sentence(text: str) -> str:
    """Extracts the first complete sentence from a text block."""
    clean = clean_sentence(text)
    if not clean:
        return ""
    # Split by sentence terminators
    parts = re.split(r'(?<=[.!?])\s+', clean)
    if parts:
        return parts[0].strip()
    return clean


def parse_raw_points(raw_points: Any) -> List[str]:
    """
    Parses raw answer points from any format into a list of strings:
    - list of strings
    - list of dicts (with heading, text, detail, point, criterion, etc.)
    - single string with newlines or bullets
    """
    if raw_points is None:
        return []

    # If it's a list containing a dict with 'key_points', unwrap it
    if isinstance(raw_points, list) and len(raw_points) == 1 and isinstance(raw_points[0], dict) and 'key_points' in raw_points[0]:
        return parse_raw_points(raw_points[0]['key_points'])

    parsed: List[str] = []

    if isinstance(raw_points, str):
        # Split on newlines, semicolons, or bullet points
        lines = re.split(r'[\r\n;]+|(?<=\.)\s+(?=[-*•\d])', raw_points)
        for line in lines:
            c = clean_sentence(line)
            if c:
                parsed.append(c)
        return parsed

    if isinstance(raw_points, list):
        for item in raw_points:
            if isinstance(item, str):
                c = clean_sentence(item)
                if c:
                    parsed.append(c)
            elif isinstance(item, dict):
                # Check known keys
                heading = item.get('heading') or item.get('title') or item.get('criterion') or item.get('name') or ''
                heading = clean_sentence(heading)

                body = (
                    item.get('text') or
                    item.get('detail') or
                    item.get('description') or
                    item.get('point') or
                    item.get('explanation') or
                    ''
                )
                body = clean_sentence(body)

                first_sent = extract_first_sentence(body)

                if heading and first_sent:
                    # Strip trailing colon from heading if present
                    h_clean = heading.rstrip(':')
                    point_str = f"{h_clean}: {first_sent}"
                elif heading:
                    point_str = heading
                elif first_sent:
                    point_str = first_sent
                else:
                    # Fallback to any string representation
                    point_str = clean_sentence(str(item))

                if point_str:
                    parsed.append(point_str)
            else:
                c = clean_sentence(str(item))
                if c:
                    parsed.append(c)

    return parsed


def build_rubric(
    question_type: str,
    marks: Any,
    answer_points: Any = None,
    question_text: str = "",
    model_answer: str = "",
) -> List[Dict[str, List[str]]]:
    """
    Pure, deterministic rubric builder.
    - Short Answer (M marks): exactly M key points (1 point per mark).
    - Long Answer (M marks): at most 8 key points (min(M, 8)).
    - Each point: cleaned, 3 to 30 words, formatted.
    - Guaranteed non-empty output matching exact expected count.
    - Returns: [{'key_points': [ ... ]}]
    """
    q_type = str(question_type or '').strip()
    if q_type not in ('Short Answer', 'Long Answer', 'short_answer', 'long_answer'):
        return [{'key_points': []}]

    try:
        m_val = float(marks) if marks is not None else 1.0
        m_int = max(1, int(round(m_val)))
    except (ValueError, TypeError):
        m_int = 1

    is_long = q_type in ('Long Answer', 'long_answer')
    target_count = min(8, m_int) if is_long else m_int

    # 1. Parse raw answer points
    candidates = parse_raw_points(answer_points)

    # If empty, try extracting from model_answer
    if not candidates and model_answer:
        candidates = parse_raw_points(model_answer)

    # 2. Clean, deduplicate, and enforce word limit
    cleaned_points: List[str] = []
    seen = set()

    for p in candidates:
        cleaned = clean_sentence(p)
        if not cleaned:
            continue

        # Format if Long Answer with heading
        if is_long and ':' in cleaned:
            parts = cleaned.split(':', 1)
            h = clean_sentence(parts[0]).rstrip(':')
            t = extract_first_sentence(parts[1])
            if h and t:
                cleaned = f"{h}: {t}"

        # Cap at 30 words
        cleaned = truncate_to_word_limit(cleaned, max_words=30)

        # Enforce minimum 3 words if possible
        words = cleaned.split()
        if len(words) < 3:
            if question_text:
                q_words = [w for w in re.findall(r'\b\w+\b', question_text) if len(w) > 3]
                context_hint = " ".join(q_words[:3])
                cleaned = f"{cleaned} in {context_hint}" if context_hint else f"{cleaned} concept defined"
            else:
                cleaned = f"Key principle of {cleaned}"

        # Deduplicate preserving order
        norm_key = cleaned.lower()
        if norm_key not in seen:
            seen.add(norm_key)
            cleaned_points.append(cleaned)

    # 3. Adjust count to match target_count exactly
    if len(cleaned_points) > target_count:
        final_points = cleaned_points[:target_count]
    elif len(cleaned_points) < target_count:
        final_points = list(cleaned_points)

        # Attempt to split longer multi-sentence points if available
        if len(final_points) < target_count and model_answer:
            sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', model_answer) if s.strip()]
            for sent in sentences:
                cs = clean_sentence(sent)
                if cs and cs.lower() not in seen and len(cs.split()) >= 3:
                    cs_capped = truncate_to_word_limit(cs, 30)
                    seen.add(cs.lower())
                    final_points.append(cs_capped)
                    if len(final_points) == target_count:
                        break

        # Synthesize remaining grounded points if still short
        filler_idx = 1
        q_clean = clean_sentence(question_text) or "Fundamental Concepts"
        # Extract main noun phrase from question
        q_topic = re.sub(r'^(explain|define|describe|discuss|state|what is|how does)\s+', '', q_clean, flags=re.IGNORECASE).rstrip('?.')
        if not q_topic:
            q_topic = "Subject Core Analysis"

        aspects = [
            f"Core definition and operational principles of {q_topic}",
            f"Key functional methodology and implementation details of {q_topic}",
            f"Practical advantages and architectural significance of {q_topic}",
            f"Comparative analysis and system trade-offs of {q_topic}",
            f"Critical execution parameters and performance outcomes of {q_topic}",
            f"Standard evaluation criteria and verification mechanisms of {q_topic}",
            f"System reliability and optimization strategies for {q_topic}",
            f"Comprehensive summary and industry best practices for {q_topic}",
        ]

        while len(final_points) < target_count:
            asp = aspects[(filler_idx - 1) % len(aspects)]
            asp_clean = truncate_to_word_limit(clean_sentence(asp), 30)
            if asp_clean.lower() not in seen:
                seen.add(asp_clean.lower())
                final_points.append(asp_clean)
            else:
                synth = f"Point {len(final_points) + 1}: Detailed technical specification of {q_topic}."
                final_points.append(truncate_to_word_limit(synth, 30))
            filler_idx += 1
    else:
        final_points = cleaned_points

    # Final sanity check: ensure all points are strings and 3-30 words
    sanitized: List[str] = []
    for pt in final_points:
        s = clean_sentence(pt)
        s = truncate_to_word_limit(s, 30)
        if len(s.split()) < 3:
            s = f"{s} concept breakdown"
        sanitized.append(s)

    return [{'key_points': sanitized}]

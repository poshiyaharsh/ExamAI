from copy import deepcopy
import re
from .options import clean_option_text, clean_options_list, validate_mcq_options


VALID_TYPES = {
    'mcq', 'true_false', 'fill_blank', 'short_answer', 'long_answer',
    # Legacy aliases
    'truefalse', 'fillblank', 'subjective', 'short', 'long', 'essay',
    'mcq_single', 'mcq_multiple'
}
VALID_DIFFICULTIES = {'easy', 'medium', 'hard'}
CANONICAL_TYPES = ('mcq', 'true_false', 'fill_blank', 'short_answer', 'long_answer')
CANONICAL_DIFFICULTIES = ('easy', 'medium', 'hard')
OBJECTIVE_TYPES = {'mcq', 'true_false', 'fill_blank', 'truefalse', 'fillblank'}
OPTION_LABELS = ('A', 'B', 'C', 'D', 'E', 'F')

TYPE_LEGACY_MAP = {
    'mcq_single': 'mcq',
    'mcq_multiple': 'mcq',
    'multiple_choice': 'mcq',
    'truefalse': 'true_false',
    'tf': 'true_false',
    'legacy_true_false': 'true_false',
    'fillblank': 'fill_blank',
    'short': 'short_answer',
    'legacy_short_answer': 'short_answer',
    'long': 'long_answer',
    'subjective': 'long_answer',
    'essay': 'long_answer',
    'legacy_long_answer': 'long_answer',
}

DIFFICULTY_LEGACY_MAP = {
    'upper_easy': 'easy',
    'upper_medium': 'medium',
    'upper_hard': 'hard',
    'med': 'medium',
}


def canonicalize_type(q_type: str) -> str:
    norm = str(q_type or '').strip().lower()
    if norm in TYPE_LEGACY_MAP:
        return TYPE_LEGACY_MAP[norm]
    if norm in CANONICAL_TYPES:
        return norm
    if 'true' in norm and 'false' in norm:
        return 'true_false'
    if 'fill' in norm or 'blank' in norm:
        return 'fill_blank'
    if 'short' in norm:
        return 'short_answer'
    if 'long' in norm or 'subjective' in norm or 'essay' in norm:
        return 'long_answer'
    return 'mcq'


def canonicalize_difficulty(diff: str) -> str:
    norm = str(diff or '').strip().lower()
    if norm in DIFFICULTY_LEGACY_MAP:
        return DIFFICULTY_LEGACY_MAP[norm]
    if norm in CANONICAL_DIFFICULTIES:
        return norm
    return 'medium'


def _normalise_correct_answer(question_type, raw_answer, options):
    canon = canonicalize_type(question_type)
    if canon == 'true_false':
        if isinstance(raw_answer, bool):
            return 'True' if raw_answer else 'False'
        answer = str(raw_answer or '').strip().casefold()
        if answer in {'a', 'true', 't', '1'}:
            return 'True'
        if answer in {'b', 'false', 'f', '0'}:
            return 'False'
        return 'True'

    if canon == 'mcq':
        if isinstance(raw_answer, int) and 0 <= raw_answer < len(options or []):
            return OPTION_LABELS[raw_answer]
        answer = str(raw_answer or '').strip()
        if answer.upper() in OPTION_LABELS[:len(options or [])]:
            return answer.upper()
        norm_answer = clean_option_text(answer).casefold()
        for index, option in enumerate(options or []):
            if norm_answer == clean_option_text(option).casefold():
                return OPTION_LABELS[index]
        return 'A'

    if canon == 'fill_blank':
        if isinstance(raw_answer, list) and raw_answer:
            return str(raw_answer[0]).strip()
        return str(raw_answer or '').strip()

    return raw_answer


def compute_question_counts(question_types, total_marks, blueprint=None):
    """
    Computes exact question counts per type and marks.
    If blueprint is provided (from wizard), respects blueprint counts and marks per type.
    Otherwise allocates deterministically using allocate_blueprint_to_target.
    """
    from .blueprint_allocator import allocate_blueprint_to_target, compute_blueprint_total, to_decimal

    target_dec = to_decimal(total_marks)
    if blueprint and isinstance(blueprint, dict):
        counts = {}
        for q_type, config in blueprint.items():
            if isinstance(config, dict) and config.get('enabled', True):
                c = int(config.get('count', 0))
                if c > 0:
                    c_type = canonicalize_type(q_type)
                    counts[c_type] = c
        actual_total = compute_blueprint_total(blueprint)
        return counts, float(actual_total)

    selected_types = [canonicalize_type(t) for t in (question_types or ['mcq'])]
    alloc_res = allocate_blueprint_to_target(target_dec, enabled_types=selected_types)
    allocated_bp = alloc_res[0]
    counts = {t: allocated_bp[t]['count'] for t in selected_types if allocated_bp.get(t, {}).get('count', 0) > 0}
    actual_total = compute_blueprint_total(allocated_bp)
    return counts, float(actual_total)



def validate_and_fix_paper(data, expected_total_marks=None, default_marks=1):
    if not isinstance(data, dict):
        raise ValueError('Generated paper must be a JSON object.')

    valid_questions = []
    for raw_question in data.get('questions', []):
        if not isinstance(raw_question, dict):
            continue
        raw_type = str(raw_question.get('type', '')).strip().lower()
        if raw_type not in VALID_TYPES:
            continue
        q_type = canonicalize_type(raw_type)

        difficulty = str(raw_question.get('difficulty', 'medium')).strip().lower()
        if difficulty not in VALID_DIFFICULTIES:
            difficulty = 'medium'

        text = str(raw_question.get('text', '')).strip()
        if not text:
            continue

        marks_val = raw_question.get('marks')
        try:
            marks = float(marks_val) if marks_val is not None else float(default_marks)
            if marks <= 0:
                marks = 1.0
        except (ValueError, TypeError):
            marks = 1.0

        cleaned_options = None
        accepted_answers = []
        rubric = []
        word_limit = None
        model_answer = ""
        correct_answer = raw_question.get('correct_answer')

        if q_type == 'mcq':
            options = raw_question.get('options')
            is_valid, _ = validate_mcq_options(options, correct_answer)
            if not is_valid:
                continue
            cleaned_options = clean_options_list(options)
            correct_answer = _normalise_correct_answer(q_type, correct_answer, cleaned_options)

        elif q_type == 'true_false':
            cleaned_options = ['True', 'False']
            correct_answer = _normalise_correct_answer(q_type, correct_answer, cleaned_options)

        elif q_type == 'fill_blank':
            # Check for blank marker ____
            if '____' not in text and '___' not in text and '[blank]' not in text:
                # If model omitted blank marker, try to replace primary answer in text with ____
                ans_str = str(correct_answer or '').strip()
                if ans_str and re.search(re.escape(ans_str), text, re.IGNORECASE):
                    text = re.sub(re.escape(ans_str), '____', text, count=1, flags=re.IGNORECASE)
                else:
                    text = text.rstrip('. ') + ' is ____.'
            # Normalize blanks to ____
            text = re.sub(r'_{2,}', '____', text)

            raw_accepted = raw_question.get('accepted_answers')
            if isinstance(raw_accepted, list) and raw_accepted:
                if isinstance(raw_accepted[0], list):
                    accepted_answers = [[str(x).strip() for x in group if str(x).strip()] for group in raw_accepted]
                else:
                    accepted_answers = [[str(x).strip() for x in raw_accepted if str(x).strip()]]
            else:
                primary = str(correct_answer or '').strip()
                accepted_answers = [[primary]] if primary else [["answer"]]

            if not correct_answer and accepted_answers and accepted_answers[0]:
                correct_answer = accepted_answers[0][0]

        elif q_type in {'short_answer', 'long_answer'}:
            model_answer = str(raw_question.get('model_answer') or '').strip()
            if not model_answer and correct_answer:
                model_answer = str(correct_answer).strip()
            correct_answer = None

            raw_rubric = raw_question.get('rubric')
            if isinstance(raw_rubric, list):
                rubric = raw_rubric
            elif isinstance(raw_rubric, dict):
                rubric = [{'criterion': k, 'marks': v} for k, v in raw_rubric.items()]
            else:
                rubric = []

            # Deterministic rubric marks repair to guarantee criteria sum == marks
            rubric = repair_rubric_marks(rubric, marks)

            word_limit = raw_question.get('word_limit')
            if not word_limit or not isinstance(word_limit, int):
                word_limit = 120 if q_type == 'short_answer' else 350

        # Grounding & Verification
        source_evidence = str(raw_question.get('source_evidence') or '').strip()
        needs_review = False
        if q_type in {'short_answer', 'long_answer'}:
            # Flag for review if model answer is under 40 words
            if len(model_answer.split()) < 40:
                needs_review = True

        question = {
            'type': q_type,
            'difficulty': difficulty,
            'topic': str(raw_question.get('topic') or '').strip(),
            'text': text,
            'marks': marks,
            'options': cleaned_options,
            'correct_answer': correct_answer,
            'model_answer': model_answer,
            'accepted_answers': accepted_answers,
            'rubric': rubric,
            'word_limit': word_limit,
            'source_evidence': source_evidence,
            'needs_review': needs_review,
            'source': 'ai_generated',
        }
        valid_questions.append(question)

    if not valid_questions:
        raise ValueError('Generated paper contained no valid questions matching the schema.')

    fixed_data = deepcopy(data)
    fixed_data['questions'] = valid_questions
    actual_total_marks = sum(q['marks'] for q in valid_questions)
    fixed_data['total_marks'] = actual_total_marks
    return fixed_data, actual_total_marks


def repair_rubric_marks(rubric: list, target_marks: float) -> list:
    """
    Deterministically repairs rubric criteria marks so they sum EXACTLY to target_marks.
    Never rejects a question due to model arithmetic errors.
    """
    target = round(float(target_marks), 1)
    if target <= 0:
        target = 1.0

    if not isinstance(rubric, list) or not rubric:
        return [
            {"criterion": "Core concepts and definition", "marks": round(target * 0.3, 1)},
            {"criterion": "Detailed breakdown and mechanisms", "marks": round(target * 0.4, 1)},
            {"criterion": "Practical application or example", "marks": round(target - round(target * 0.3, 1) - round(target * 0.4, 1), 1)}
        ]

    cleaned = []
    for item in rubric:
        if isinstance(item, dict):
            crit = str(item.get("criterion") or item.get("name") or "Core concept").strip()
            try:
                m = float(item.get("marks", 0))
            except (ValueError, TypeError):
                m = 0.0
            cleaned.append({"criterion": crit, "marks": max(0.0, m)})
        elif isinstance(item, str) and item.strip():
            cleaned.append({"criterion": item.strip(), "marks": 0.0})

    if not cleaned:
        return repair_rubric_marks([], target)

    current_sum = sum(x["marks"] for x in cleaned)
    if current_sum <= 0:
        each = round(target / len(cleaned), 1)
        for x in cleaned:
            x["marks"] = each
        cleaned[-1]["marks"] = round(target - sum(x["marks"] for x in cleaned[:-1]), 1)
        return cleaned

    scaled = []
    running = 0.0
    for i, x in enumerate(cleaned):
        if i == len(cleaned) - 1:
            final_mark = round(target - running, 1)
            scaled.append({"criterion": x["criterion"], "marks": final_mark})
        else:
            proportional = round((x["marks"] / current_sum) * target, 1)
            running += proportional
            scaled.append({"criterion": x["criterion"], "marks": proportional})

    return scaled


import unicodedata


def normalize_grounding_text(text: str) -> str:
    """
    Normalizes text for robust grounding and evidence verification.
    Handles:
    - Unicode NFKD decomposition (accents, diacritics)
    - Ligatures (fi, fl, ff, ffi, ffl, etc.)
    - Smart quotes, curved apostrophes, em-dashes
    - Hyphenation across linebreaks (e.g. 'archi- \n tecture' -> 'architecture')
    - Non-breaking spaces and irregular whitespace
    - Punctuation removal and case folding
    """
    if not text:
        return ""
    norm = unicodedata.normalize('NFKD', str(text))
    ligatures = {
        'ﬁ': 'fi', 'ﬂ': 'fl', 'ﬀ': 'ff', 'ﬃ': 'ffi', 'ﬄ': 'ffl',
        'æ': 'ae', 'œ': 'oe', 'ß': 'ss'
    }
    for lig, rep in ligatures.items():
        norm = norm.replace(lig, rep)
    quotes = {
        '“': '"', '”': '"', '‘': "'", '’': "'", '«': '"', '»': '"',
        '„': '"', '‟': '"', '—': '-', '–': '-', '•': ' ', '·': ' ',
        '\xa0': ' ', '\u200b': ''
    }
    for q, rep in quotes.items():
        norm = norm.replace(q, rep)
    norm = re.sub(r'(\w+)-\s*\n\s*(\w+)', r'\1\2', norm)
    norm = re.sub(r'[^a-zA-Z0-9\s]', ' ', norm)
    norm = re.sub(r'\s+', ' ', norm).strip().lower()
    return norm


def verify_grounding_evidence(source_evidence: str, syllabus_text: str) -> bool:
    """
    Checks if source_evidence quote exists in the syllabus text
    via normalized substring, multi-word sliding window, or substantive token containment.
    """
    if not source_evidence or not syllabus_text:
        return False

    clean_ev = normalize_grounding_text(source_evidence)
    clean_syl = normalize_grounding_text(syllabus_text)

    if len(clean_ev) < 6:
        return False

    # 1. Exact normalized substring
    if clean_ev in clean_syl:
        return True

    words = clean_ev.split()

    # 2. Sliding window check (3 or 4-word sequences)
    if len(words) >= 3:
        window_size = min(4, len(words))
        for idx in range(len(words) - window_size + 1):
            sub = ' '.join(words[idx : idx + window_size])
            if sub in clean_syl:
                return True

    # 3. Substantive content word containment (words > 3 chars)
    content_words = [w for w in words if len(w) > 3]
    if len(content_words) >= 4:
        syl_words_set = set(clean_syl.split())
        matched = sum(1 for w in content_words if w in syl_words_set)
        if matched / len(content_words) >= 0.75:
            return True

    return False


def audit_question_scope(question_obj, syllabus_text: str, selected_topics: list = None) -> dict:
    """
    Verifies if a question is grounded in the syllabus text and matches selected topics.
    Returns:
    {
        'in_scope': bool,
        'reason': str,
        'is_manual': bool,
        'word_match_ratio': float,
        'grounding_verified': bool,
    }
    """
    if getattr(question_obj, 'source', '') == 'manual':
        return {
            'in_scope': True,
            'reason': 'Manually authored question (excluded from scope check)',
            'is_manual': True,
            'word_match_ratio': 1.0,
            'grounding_verified': True,
        }

    if not syllabus_text:
        return {
            'in_scope': True,
            'reason': 'No syllabus document attached to exam',
            'is_manual': False,
            'word_match_ratio': 1.0,
            'grounding_verified': True,
        }

    text = getattr(question_obj, 'text', '') or ''
    ev = ""
    if "Source evidence:" in text:
        ev = text.split("Source evidence:")[1].split("(")[0].strip("' \"")
    elif "source evidence" in text.lower():
        ev = text.lower().split("source evidence")[1].strip(": '\"")

    grounded = verify_grounding_evidence(ev, syllabus_text) if ev else False

    # Check substantive words (words > 4 letters)
    words = [w.lower().strip(".,:;?'\"()") for w in text.split() if len(w) > 4]
    matched = [w for w in words if w in syllabus_text.lower()]
    ratio = len(matched) / max(len(words), 1)

    # Topic check: topic must be present in syllabus or selected_topics
    topic = (getattr(question_obj, 'topic_text', '') or '').strip()
    if selected_topics:
        topic_in_doc = any(re.sub(r'\s+', ' ', topic).lower() == re.sub(r'\s+', ' ', str(t)).lower() for t in selected_topics)
    elif topic:
        clean_top = re.sub(r'\s+', ' ', topic).lower()
        clean_syl = re.sub(r'\s+', ' ', syllabus_text).lower()
        topic_in_doc = clean_top in clean_syl or any(w in clean_syl for w in clean_top.split() if len(w) > 4)
    else:
        topic_in_doc = True

    # Support determination: must have topic in document AND (grounded or strong word match)
    if not topic_in_doc:
        is_supported = False
        reason = f"Topic '{topic}' is not in the source document"
    elif grounded:
        is_supported = True
        reason = "Grounded with verbatim source evidence quote"
    elif ratio >= 0.60:
        is_supported = True
        reason = f"Supported by syllabus text ({int(ratio * 100)}% keyword match)"
    else:
        is_supported = False
        reason = f"Insufficient syllabus grounding (only {int(ratio * 100)}% keyword match)"

    return {
        'in_scope': is_supported,
        'reason': reason,
        'is_manual': False,
        'word_match_ratio': round(ratio, 2),
        'grounding_verified': grounded,
    }




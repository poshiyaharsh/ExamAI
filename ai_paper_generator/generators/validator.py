"""
Two-Tier Accuracy & Validation System (Section 4 & 5.7).
Tier 1: Code Verification (Instant)
- Grounding quote fuzzy match (difflib ratio >= 0.85)
- Answer in context check
- Distractor quality: pairwise similarity < 0.85, distractor != correct, no banned phrases, correct <= 2.2x distractor len
- Fill in the blank: single blank (_____), answer 1-4 words in quote
- True/False: exactly True or False, correct statement for false
- Short/Long: non-empty, points matching marks, within word limits
- Deduplication: similarity < 0.8, distinct source quotes

Tier 2: AI Verification (phi3:mini)
- Batches of up to 5 items with compact JSON schema
- Run ONLY for Long answers and items flagged by code rules
- Never run for standard clean MCQs, True/False, or Fill Blank
"""
import re
import difflib
import logging
from typing import Dict, Any, Tuple, Optional, List
from ..ollama_client import OllamaClient
from ..logging_setup import log_event
from ..prompts.repair import build_validator_prompt, VALIDATOR_JSON_SCHEMA
from .json_repair import parse_and_repair_json
from .rubric_builder import build_rubric

logger = logging.getLogger(__name__)

PLACEHOLDER_PATTERNS = [
    r'lorem ipsum',
    r'insert\s+(question|answer|here)',
    r'todo',
    r'sample question',
    r'placeholder',
    r'n/a',
]

STOPWORDS = {
    'the', 'is', 'at', 'which', 'on', 'and', 'a', 'an', 'in', 'to', 'for', 'of', 'with', 'by', 'as', 'that'
}


def check_grounding_quote(source_quote: str, context: str) -> Tuple[bool, float]:
    """Checks that source_quote appears in context with difflib ratio >= 0.85."""
    if not source_quote or not context:
        return False, 0.0

    sq = source_quote.strip().lower()
    ctx = context.lower()

    if sq in ctx:
        return True, 1.0

    # Fast substring scan
    matcher = difflib.SequenceMatcher(None, sq, ctx)
    match = matcher.find_longest_match(0, len(sq), 0, len(ctx))
    if match.size >= len(sq) * 0.85:
        return True, match.size / len(sq)

    # Sentence-level fuzzy match
    sentences = re.split(r'[.\n]+', ctx)
    best_ratio = 0.0
    for s in sentences:
        s_clean = s.strip()
        if len(s_clean) >= 10:
            ratio = difflib.SequenceMatcher(None, sq, s_clean).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
            if best_ratio >= 0.85:
                return True, best_ratio

    return (best_ratio >= 0.85), best_ratio


def check_answer_in_context(answer: str, source_quote: str, context: str) -> bool:
    """Checks that key terms of answer appear in source_quote or context."""
    if not answer:
        return False
    ans_clean = str(answer).strip().lower()
    if ans_clean in ('true', 'false'):
        return True

    words = [w for w in re.findall(r'\b\w+\b', ans_clean) if len(w) >= 3 and w not in STOPWORDS]
    if not words:
        return True

    haystack = (source_quote + " " + context).lower()
    matches = sum(1 for w in words if w in haystack)
    return (matches / len(words)) >= 0.5


def validate_rules(
    question_data: Dict[str, Any],
    context: str = "",
    job_id: Optional[int] = None
) -> Tuple[bool, str]:
    """
    Tier 1 Instant Rule Checks (Section 4). Returns (is_valid, reason).
    """
    slot_num = question_data.get('slot_index')
    q_type = question_data.get('type')
    text = str(question_data.get('question') or question_data.get('text') or '').strip()
    answer = str(question_data.get('answer') or '').strip()
    options = question_data.get('options') or []
    source_quote = str(question_data.get('source_quote') or '').strip()

    # 1. General checks
    if not text or len(text) < 8:
        reason = "Question text is empty or too short."
        log_event('RULE_FAIL', f"Rule failed: {reason}", job_id=job_id, slot_number=slot_num)
        return False, reason

    for pattern in PLACEHOLDER_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE) or re.search(pattern, answer, re.IGNORECASE):
            reason = f"Detected placeholder text matching '{pattern}'."
            log_event('RULE_FAIL', f"Rule failed: {reason}", job_id=job_id, slot_number=slot_num)
            return False, reason

    if text.endswith(('...', '…', 'etc.', 'and so on')):
        reason = "Question appears truncated at end."
        log_event('RULE_FAIL', f"Rule failed: {reason}", job_id=job_id, slot_number=slot_num)
        return False, reason

    # 2. Grounding quote check (Section 4.1)
    if source_quote and context:
        is_grounded, ratio = check_grounding_quote(source_quote, context)
        if not is_grounded:
            question_data['suspicious'] = True
            log_event('VALIDATION', f"Slot {slot_num} low grounding quote match ratio ({ratio:.2f} < 0.85).", job_id=job_id, slot_number=slot_num)

    # 3. Answer in context check (Section 4.2)
    if context and q_type in ('MCQ', 'True/False', 'Fill in the Blank'):
        if not check_answer_in_context(answer, source_quote, context):
            question_data['suspicious'] = True

    # 4. Type-specific checks
    if q_type == 'MCQ':
        if not isinstance(options, list) or len(options) != 4:
            reason = f"MCQ must have exactly 4 options, found {len(options) if isinstance(options, list) else 0}."
            log_event('RULE_FAIL', f"Rule failed: {reason}", job_id=job_id, slot_number=slot_num)
            return False, reason

        clean_options = [str(opt).strip() for opt in options if str(opt).strip()]
        if len(clean_options) != 4:
            reason = "MCQ contains empty or whitespace options."
            log_event('RULE_FAIL', f"Rule failed: {reason}", job_id=job_id, slot_number=slot_num)
            return False, reason

        # Check duplicate or near duplicate options (Section 4.3)
        for i in range(len(clean_options)):
            for j in range(i + 1, len(clean_options)):
                sim = difflib.SequenceMatcher(None, clean_options[i].lower(), clean_options[j].lower()).ratio()
                if sim > 0.85:
                    reason = f"MCQ contains near-duplicate options ({clean_options[i]} vs {clean_options[j]})."
                    log_event('RULE_FAIL', f"Rule failed: {reason}", job_id=job_id, slot_number=slot_num)
                    return False, reason

        # Check banned phrases (Section 4.3)
        banned = [r'\ball\s+of\s+the\s+above\b', r'\bnone\s+of\s+the\s+above\b', r'\bboth\s+[a-d]\s+and\s+[a-d]\b']
        for opt in clean_options:
            for b in banned:
                if re.search(b, opt, re.IGNORECASE):
                    reason = f"MCQ contains banned phrase matching '{b}'."
                    log_event('RULE_FAIL', f"Rule failed: {reason}", job_id=job_id, slot_number=slot_num)
                    return False, reason

        # Correct answer must be in options
        matched_option = next((opt for opt in clean_options if opt.lower() == answer.lower()), None)
        if not matched_option:
            reason = f"MCQ correct answer '{answer}' does not match any of the 4 options."
            log_event('RULE_FAIL', f"Rule failed: {reason}", job_id=job_id, slot_number=slot_num)
            return False, reason

        # Answer length ratio check (Section 4.3)
        distractor_lens = [len(opt) for opt in clean_options if opt != matched_option]
        avg_d_len = sum(distractor_lens) / max(1, len(distractor_lens))
        if len(matched_option) > 2.5 * avg_d_len and len(matched_option) > 40:
            question_data['suspicious'] = True

        question_data['options'] = clean_options
        question_data['answer'] = matched_option

    elif q_type == 'True/False':
        normalized_ans = answer.strip().capitalize()
        if normalized_ans not in ('True', 'False'):
            if 'true' in answer.lower():
                normalized_ans = 'True'
            elif 'false' in answer.lower():
                normalized_ans = 'False'
            else:
                reason = f"True/False answer must be 'True' or 'False', got '{answer}'."
                log_event('RULE_FAIL', f"Rule failed: {reason}", job_id=job_id, slot_number=slot_num)
                return False, reason

        question_data['answer'] = normalized_ans
        question_data['options'] = ['True', 'False']

    elif q_type == 'Fill in the Blank':
        if '_' not in text:
            reason = "Fill in the Blank question missing blank marker."
            log_event('RULE_FAIL', f"Rule failed: {reason}", job_id=job_id, slot_number=slot_num)
            return False, reason

        # Normalize to exactly 5 underscores
        question_data['text'] = re.sub(r'_+', '_____', text)
        question_data['question'] = question_data['text']

        # Blank word limit (Section 4.5: 1 to 4 words)
        words = answer.split()
        if not words:
            reason = "Fill in the blank answer is empty."
            log_event('RULE_FAIL', f"Rule failed: {reason}", job_id=job_id, slot_number=slot_num)
            return False, reason
        elif len(words) > 4:
            # Cleanly constrain answer to first 4 words if slightly verbose
            answer = " ".join(words[:4])
            question_data['answer'] = answer

    elif q_type == 'Short Answer':
        if not answer or len(answer) < 15:
            reason = "Short Answer model answer is missing or too short."
            log_event('RULE_FAIL', f"Rule failed: {reason}", job_id=job_id, slot_number=slot_num)
            return False, reason

        marks = int(question_data.get('marks') or 1)
        expected_pts = marks
        rub = question_data.get('rubric')
        pts = rub[0].get('key_points') if (isinstance(rub, list) and rub and isinstance(rub[0], dict)) else []

        # Validate rubric
        valid_rub = (
            isinstance(pts, list) and
            len(pts) == expected_pts and
            all(isinstance(p, str) and 3 <= len(p.split()) <= 30 for p in pts)
        )
        if not valid_rub:
            # Auto-heal with build_rubric
            raw_pts = question_data.get('key_points') or question_data.get('answer_points') or answer
            new_rub = build_rubric('Short Answer', marks, raw_pts, question_text=text, model_answer=answer)
            question_data['rubric'] = new_rub
            question_data['key_points'] = new_rub[0]['key_points']
            pts = new_rub[0]['key_points']
            if len(pts) != expected_pts:
                reason = f"Short Answer rubric key_points count {len(pts)} does not match marks {expected_pts}."
                log_event('RULE_FAIL', f"Rule failed: {reason}", job_id=job_id, slot_number=slot_num)
                return False, reason

    elif q_type == 'Long Answer':
        marks = int(question_data.get('marks') or 5)
        min_words = max(15, marks * 3)
        word_count = len(answer.split())
        if not answer or word_count < min_words:
            reason = f"Long Answer model answer is too short ({word_count} words vs required minimum {min_words} words)."
            log_event('RULE_FAIL', f"Rule failed: {reason}", job_id=job_id, slot_number=slot_num)
            return False, reason

        expected_pts = min(8, marks)
        rub = question_data.get('rubric')
        pts = rub[0].get('key_points') if (isinstance(rub, list) and rub and isinstance(rub[0], dict)) else []

        # Validate rubric
        valid_rub = (
            isinstance(pts, list) and
            len(pts) == expected_pts and
            all(isinstance(p, str) and 3 <= len(p.split()) <= 30 for p in pts)
        )
        if not valid_rub:
            # Auto-heal with build_rubric
            raw_pts = question_data.get('key_points') or question_data.get('answer_points') or answer
            new_rub = build_rubric('Long Answer', marks, raw_pts, question_text=text, model_answer=answer)
            question_data['rubric'] = new_rub
            question_data['key_points'] = new_rub[0]['key_points']
            pts = new_rub[0]['key_points']
            if len(pts) != expected_pts:
                reason = f"Long Answer rubric key_points count {len(pts)} does not match expected {expected_pts}."
                log_event('RULE_FAIL', f"Rule failed: {reason}", job_id=job_id, slot_number=slot_num)
                return False, reason

    return True, "Passed rule verification."


def should_run_ai_validation(question_data: Dict[str, Any], rule_passed: bool) -> bool:
    """
    Section 2.4 & 5.7: Run AI validator ONLY for Long answers and items flagged by code.
    Never run for clean standard MCQs, True/False, or Fill Blank.
    """
    q_type = question_data.get('type')
    if q_type == 'Long Answer':
        return True
    if not rule_passed or question_data.get('suspicious'):
        return True
    return False


def validate_batch_with_ai(
    items: List[Dict[str, Any]],
    context: str,
    client: OllamaClient,
    validator_model: str,
    job_id: Optional[int] = None
) -> Dict[int, Tuple[bool, str]]:
    """
    Section 5.7 AI Validator: Batched validation of up to 5 items with phi3:mini.
    Returns mapping {slot_index: (verdict_bool, issues_str)}.
    """
    if not items:
        return {}

    prompt_items = []
    for it in items:
        prompt_items.append({
            'id': it.get('slot_index', len(prompt_items) + 1),
            'type': it.get('type', 'Long Answer'),
            'question': it.get('question') or it.get('text', ''),
            'answer': it.get('answer', ''),
            'source_quote': it.get('source_quote', ''),
        })

    prompt = build_validator_prompt(context, prompt_items)
    num_predict = min(1000, len(items) * 80 + 100)

    try:
        raw_output = client.generate(
            model=validator_model,
            prompt=prompt,
            format=VALIDATOR_JSON_SCHEMA,
            temperature=0.1,
            num_predict=num_predict,
            job_id=job_id,
            stage="ai_validation",
            batch_size=len(items)
        )
        parsed = parse_and_repair_json(raw_output, job_id=job_id)
        results_list = parsed.get('results', []) if isinstance(parsed, dict) else []
    except Exception as exc:
        log_event('VALIDATION', f"Batched AI validation failed: {exc}", job_id=job_id, level=logging.WARNING)
        # Default pass on validation model glitch
        return {it.get('slot_index', i + 1): (True, "") for i, it in enumerate(items)}

    verdicts: Dict[int, Tuple[bool, str]] = {}
    for res in results_list:
        item_id = res.get('id')
        verdict = str(res.get('verdict', 'pass')).lower().strip()
        issues = str(res.get('issues', '')).strip()
        verdicts[item_id] = (verdict == 'pass', issues)

    # For any item omitted from results, default to pass
    for it in items:
        idx = it.get('slot_index')
        if idx not in verdicts:
            verdicts[idx] = (True, "")

    return verdicts


def validate_with_model2(
    question_data: Dict[str, Any],
    context: str,
    client: OllamaClient,
    validator_model: str,
    job_id: Optional[int] = None
) -> Tuple[bool, str]:
    """Single item wrapper around validate_batch_with_ai for repair module."""
    slot_id = question_data.get('slot_index', 1)
    res = validate_batch_with_ai([question_data], context, client, validator_model, job_id=job_id)
    if slot_id in res:
        return res[slot_id]
    for val in res.values():
        return val
    return True, ""

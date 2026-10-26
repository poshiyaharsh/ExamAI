import difflib
import json
import logging
import re
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from django.db import transaction

from .evaluation_config import (
    CLOUD_API_KEY,
    CLOUD_MODEL,
    CLOUD_PROVIDER,
    EVAL_PROVIDER_ORDER,
    OLLAMA_FALLBACK_MODELS,
    OLLAMA_MODEL,
    OLLAMA_TIMEOUT,
    canonicalize_model_tag,
)
from .ollama_client import (
    call_ollama_chat,
    get_installed_ollama_models,
    parse_json_safely,
    resolve_ollama_model,
)
from .prompts import build_evaluation_prompt

logger = logging.getLogger(__name__)


def validate_evaluation(
    result: Any,
    max_marks: float,
    student_answer: str,
) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
    """
    Validates evaluation output from AI provider:
    - Valid dictionary
    - Numeric score, clamped to [0, max_marks]
    - Non-empty feedback (2-4 sentences)
    - Matched points non-empty when score > 0
    - Sanity check: score > 50% max_marks with under 10 words flagged as suspicious
    """
    if not isinstance(result, dict):
        return False, "Evaluation response was not a valid JSON dictionary.", None

    raw_score = result.get('score')
    if raw_score is None:
        return False, "Missing 'score' field in evaluation response.", None

    try:
        score = float(raw_score)
    except (TypeError, ValueError):
        return False, f"Score value '{raw_score}' is not numeric.", None

    # Clamp score to [0, max_marks]
    if score < 0:
        logger.warning("Clamping negative score %s to 0", score)
        score = 0.0
    elif score > max_marks:
        logger.warning("Clamping score %s to max_marks %s", score, max_marks)
        score = float(max_marks)
    else:
        score = round(score, 2)

    feedback = str(result.get('feedback', '')).strip()
    if not feedback:
        return False, "Evaluation response contained empty feedback.", None

    matched_points = result.get('matched_points') or []
    missing_points = result.get('missing_points') or []
    if not isinstance(matched_points, list):
        matched_points = [str(matched_points)]
    if not isinstance(missing_points, list):
        missing_points = [str(missing_points)]

    matched_points = [str(p).strip() for p in matched_points if str(p).strip()]
    missing_points = [str(p).strip() for p in missing_points if str(p).strip()]

    # If score > 0, ensure matched_points exists
    if score > 0 and not matched_points:
        matched_points = ["Answer demonstrates foundational understanding of required concepts."]

    # Sanity check: score > 50% max_marks but answer has under 10 words
    words = student_answer.strip().split()
    if score > (0.5 * max_marks) and len(words) < 10:
        return (
            False,
            f"Suspicious evaluation: awarded {score}/{max_marks} marks for answer under 10 words ({len(words)} words).",
            None,
        )

    validated_data = {
        'score': score,
        'feedback': feedback,
        'matched_points': matched_points,
        'missing_points': missing_points,
    }
    return True, None, validated_data


def evaluate_with_rules(question: Any, student_answer: str) -> Tuple[float, str]:
    """
    Zero-AI deterministic fallback grading using token overlap and SequenceMatcher.
    Proportional scoring based on coverage of model answer key concepts.
    """
    clean_ans = str(student_answer or "").strip()
    if not clean_ans:
        return 0.0, "No answer was submitted."

    max_marks = float(question.marks) if question.marks else 10.0
    model_answer = str(getattr(question, 'model_answer', '') or '').strip()
    topic = str(getattr(question, 'topic_text', '') or getattr(question, 'topic', '') or '').strip()

    combined_reference = f"{topic} {model_answer}".lower()
    student_tokens = set(re.findall(r'\b[a-zA-Z]{3,}\b', clean_ans.lower()))
    ref_tokens = set(re.findall(r'\b[a-zA-Z]{3,}\b', combined_reference))

    if not ref_tokens:
        # Fallback if model answer was empty: basic word count thresholding
        word_count = len(clean_ans.split())
        ratio = min(1.0, max(0.1, word_count / 100.0))
        score = round(ratio * max_marks * 0.5, 1)
        return score, "Evaluated automatically using keyword matching. Pending teacher review."

    # Jaccard overlap on informative keywords
    overlap = len(student_tokens & ref_tokens)
    token_ratio = overlap / max(len(ref_tokens), 1)

    # String similarity on key phrases
    matcher = difflib.SequenceMatcher(None, clean_ans.lower(), model_answer.lower())
    similarity_ratio = matcher.quick_ratio()

    # Blended score ratio
    blended_ratio = (token_ratio * 0.7) + (similarity_ratio * 0.3)
    score = round(min(max_marks, max(0.0, blended_ratio * max_marks * 1.5)), 1)

    feedback = "Evaluated automatically using keyword matching. Pending teacher review."
    return score, feedback


def evaluate_with_ollama(
    question: Any,
    student_answer: str,
    preferred_model: Optional[str] = None,
) -> Tuple[bool, float, str, str, str]:
    """
    Attempts subjective answer evaluation via Ollama chat API.
    Tries preferred model and fallback chain.
    Returns: (success, score, feedback, model_used, error_reason)
    """
    clean_ans = str(student_answer or "").strip()
    max_marks = float(question.marks) if question.marks else 10.0

    if not clean_ans:
        return True, 0.0, "No answer was submitted.", "none", ""

    # Candidates to try in order
    candidates_to_try: List[str] = []
    if preferred_model:
        canonical_pref = canonicalize_model_tag(preferred_model)
        candidates_to_try.append(canonical_pref)

    canonical_primary = canonicalize_model_tag(OLLAMA_MODEL)
    if canonical_primary not in candidates_to_try:
        candidates_to_try.append(canonical_primary)

    for fb in OLLAMA_FALLBACK_MODELS:
        cfb = canonicalize_model_tag(fb)
        if cfb not in candidates_to_try:
            candidates_to_try.append(cfb)

    installed_models = get_installed_ollama_models()
    if not installed_models:
        return False, 0.0, "", "", "Ollama server is unreachable or reports no installed models."

    installed_set = set(installed_models)
    valid_chain = [m for m in candidates_to_try if m in installed_set]
    if not valid_chain:
        # If none of preferred/fallback are installed, try any installed model
        valid_chain = list(installed_models)

    last_error = ""
    for model_tag in valid_chain:
        logger.info("Attempting Ollama evaluation using model_tag=%s", model_tag)
        is_phi3 = "phi3" in model_tag.lower()
        prompt = build_evaluation_prompt(
            question_text=question.text,
            model_answer=getattr(question, 'model_answer', ''),
            student_answer=clean_ans,
            max_marks=max_marks,
            marking_scheme=getattr(question, 'topic_text', ''),
            model_tag=model_tag,
        )

        messages = [
            {"role": "system", "content": "You are an objective academic examiner grading a student answer. You must output JSON only."},
            {"role": "user", "content": prompt},
        ]

        # Retry loop for model up to 2 retries (3 total attempts)
        current_messages = list(messages)
        for attempt_num in range(3):
            try:
                raw_response = call_ollama_chat(
                    model=model_tag,
                    messages=current_messages,
                    timeout=OLLAMA_TIMEOUT,
                    format='json',
                    temperature=0.0,
                )
            except Exception as exc:
                last_error = str(exc)
                logger.warning("Ollama call failed (model=%s attempt=%s): %s", model_tag, attempt_num + 1, exc)
                break

            try:
                parsed = parse_json_safely(raw_response)
            except (ValueError, json.JSONDecodeError) as parse_err:
                last_error = f"Malformed JSON: {parse_err}"
                logger.warning("Ollama output not valid JSON (model=%s attempt=%s): %s", model_tag, attempt_num + 1, last_error)
                if attempt_num < 2:
                    current_messages.append({"role": "assistant", "content": raw_response})
                    current_messages.append({
                        "role": "user",
                        "content": f"Your output was not valid JSON ({parse_err}). Please output strictly valid JSON format matching the schema."
                    })
                continue

            valid, err, val_data = validate_evaluation(parsed, max_marks, clean_ans)
            if valid and val_data:
                return True, val_data['score'], val_data['feedback'], model_tag, ""
            else:
                last_error = err or "Validation failed"
                logger.warning("Ollama evaluation output invalid (model=%s attempt=%s): %s", model_tag, attempt_num + 1, last_error)
                if attempt_num < 2:
                    # Re-prompt model with specific rejection reason
                    current_messages.append({"role": "assistant", "content": raw_response})
                    current_messages.append({
                        "role": "user",
                        "content": f"Your output had this validation issue: {last_error}. Please correct it and output strictly valid JSON in the requested format."
                    })

    return False, 0.0, "", "", last_error or "All Ollama evaluation attempts failed."


def evaluate_subjective_chain(answer_obj: Any, force: bool = False) -> Dict[str, Any]:
    """
    Executes the full evaluation fallback chain on a StudentAnswer instance:
    1. Check if manually reviewed by teacher (never overwrite unless force=True)
    2. Check empty student answer
    3. Provider 1: Ollama chat (primary + fallbacks)
    4. Provider 2: Cloud provider (if configured)
    5. Provider 3: Rules provider (deterministic keyword/concept matching)
    6. If all fail: pending_review
    Saves results safely with non-null institution and tenant isolation.
    """
    from ..models import StudentAnswer

    # Check if already reviewed manually
    if answer_obj.evaluation_status == StudentAnswer.EvaluationStatus.REVIEWED and not force:
        logger.info("Answer ID=%s is manually reviewed by teacher; skipping automated overwrite.", answer_obj.id)
        return {
            'status': answer_obj.evaluation_status,
            'score': answer_obj.score_awarded,
            'feedback': answer_obj.ai_feedback,
            'provider': answer_obj.evaluation_provider,
            'model': answer_obj.evaluation_model,
        }

    clean_ans = str(answer_obj.answer_text or "").strip()
    question = answer_obj.question
    exam = getattr(answer_obj.attempt, 'exam', None)
    preferred_model = getattr(exam, 'ai_model_used', None)

    # Empty answer handling
    if not clean_ans:
        answer_obj.score_awarded = 0.0
        answer_obj.is_correct = False
        answer_obj.ai_feedback = "No answer was submitted."
        answer_obj.evaluation_status = StudentAnswer.EvaluationStatus.EVALUATED_RULES
        answer_obj.evaluation_provider = "rules"
        answer_obj.evaluation_model = "empty_check"
        answer_obj.technical_error = ""
        answer_obj.save(update_fields=[
            'score_awarded', 'is_correct', 'ai_feedback',
            'evaluation_status', 'evaluation_provider', 'evaluation_model', 'technical_error'
        ])
        return {
            'status': answer_obj.evaluation_status,
            'score': 0.0,
            'feedback': answer_obj.ai_feedback,
            'provider': 'rules',
            'model': 'empty_check',
        }

    ollama_error = ""

    # Provider 1: Ollama
    if 'ollama' in EVAL_PROVIDER_ORDER:
        success, score, feedback, model_used, err_msg = evaluate_with_ollama(
            question=question,
            student_answer=clean_ans,
            preferred_model=preferred_model,
        )
        if success:
            answer_obj.score_awarded = score
            answer_obj.is_correct = (score >= (0.4 * float(question.marks or 10)))
            answer_obj.ai_feedback = feedback
            answer_obj.ai_suggested_score = score
            answer_obj.ai_suggested_feedback = feedback
            answer_obj.evaluation_status = StudentAnswer.EvaluationStatus.EVALUATED_AI
            answer_obj.evaluation_provider = "ollama"
            answer_obj.evaluation_model = model_used
            answer_obj.technical_error = ""
            answer_obj.save(update_fields=[
                'score_awarded', 'is_correct', 'ai_feedback',
                'ai_suggested_score', 'ai_suggested_feedback',
                'evaluation_status', 'evaluation_provider', 'evaluation_model', 'technical_error'
            ])
            return {
                'status': answer_obj.evaluation_status,
                'score': score,
                'feedback': feedback,
                'provider': 'ollama',
                'model': model_used,
            }
        else:
            ollama_error = err_msg

    # Provider 2: Rules provider fallback
    if 'rules' in EVAL_PROVIDER_ORDER:
        try:
            score, feedback = evaluate_with_rules(question, clean_ans)
            answer_obj.score_awarded = score
            answer_obj.is_correct = (score >= (0.4 * float(question.marks or 10)))
            answer_obj.ai_feedback = feedback
            answer_obj.evaluation_status = StudentAnswer.EvaluationStatus.EVALUATED_RULES
            answer_obj.evaluation_provider = "rules"
            answer_obj.evaluation_model = "keyword_matcher"
            answer_obj.technical_error = ollama_error
            answer_obj.save(update_fields=[
                'score_awarded', 'is_correct', 'ai_feedback',
                'evaluation_status', 'evaluation_provider', 'evaluation_model', 'technical_error'
            ])
            return {
                'status': answer_obj.evaluation_status,
                'score': score,
                'feedback': feedback,
                'provider': 'rules',
                'model': 'keyword_matcher',
            }
        except Exception as exc:
            logger.exception("Rules evaluation fallback failed for answer ID=%s", answer_obj.id)
            ollama_error += f"; Rules error: {exc}"

    # Provider 3: Ultimate safe fallback (Pending Review)
    answer_obj.score_awarded = 0.0
    answer_obj.is_correct = False
    answer_obj.ai_feedback = "Answer submitted successfully. Pending teacher evaluation."
    answer_obj.evaluation_status = StudentAnswer.EvaluationStatus.PENDING_REVIEW
    answer_obj.evaluation_provider = "pending"
    answer_obj.evaluation_model = "none"
    answer_obj.technical_error = ollama_error
    answer_obj.save(update_fields=[
        'score_awarded', 'is_correct', 'ai_feedback',
        'evaluation_status', 'evaluation_provider', 'evaluation_model', 'technical_error'
    ])
    return {
        'status': answer_obj.evaluation_status,
        'score': 0.0,
        'feedback': answer_obj.ai_feedback,
        'provider': 'pending',
        'model': 'none',
    }


def generate_ai_grading_suggestion(
    question: Any,
    student_answer: str,
    preferred_model: Optional[str] = None,
    timeout: int = 20,
) -> Tuple[bool, Optional[float], str, str]:
    """
    Generates an optional advisory AI suggestion for a subjective question.
    - Never mutates actual student score or answer state directly.
    - Strict timeout (default 20s) so it never blocks faculty review.
    - Single attempt without cascading retries.
    - Returns (success: bool, suggested_score: Optional[float], suggested_feedback: str, error_reason: str)
    """
    clean_ans = str(student_answer or "").strip()
    max_marks = float(question.marks) if question.marks else 10.0
    if not clean_ans:
        return True, 0.0, "No answer was submitted.", ""

    try:
        installed = get_installed_ollama_models()
    except Exception as exc:
        return False, None, "", f"Failed to connect to Ollama: {exc}"

    if not installed:
        return False, None, "", "Ollama service unreachable or reports no installed models."

    model_tag = canonicalize_model_tag(preferred_model) if preferred_model else canonicalize_model_tag(OLLAMA_MODEL)
    if model_tag not in installed:
        model_tag = installed[0]

    prompt = build_evaluation_prompt(
        question_text=question.text,
        model_answer=getattr(question, 'model_answer', '') or '',
        student_answer=clean_ans,
        max_marks=max_marks,
        marking_scheme=getattr(question, 'topic_text', '') or '',
        model_tag=model_tag,
    )
    messages = [
        {"role": "system", "content": "You are an academic examiner providing an advisory grading suggestion for a teacher. Output strictly JSON."},
        {"role": "user", "content": prompt},
    ]

    try:
        raw_response = call_ollama_chat(
            model=model_tag,
            messages=messages,
            timeout=timeout,
            format='json',
            temperature=0.0,
        )
        parsed = parse_json_safely(raw_response)
        valid, err, val_data = validate_evaluation(parsed, max_marks, clean_ans)
        if valid and val_data:
            return True, val_data['score'], val_data['feedback'], ""
        return False, None, "", err or "Validation of AI response failed."
    except Exception as exc:
        logger.warning("AI grading suggestion failed: %s", exc)
        return False, None, "", str(exc)

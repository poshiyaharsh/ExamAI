from datetime import timedelta
import difflib
import hashlib
import json
import logging
import threading
import time
import uuid

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Exam, Notification, PaperGenerationJob, Question, Subject
from .permissions import IsFacultyUser
from .tenant import get_user_institution
from .utils.blueprint_allocator import compute_blueprint_total, to_decimal
from .utils.generation_pipeline import (
    PAPER_HARD_DEADLINE,
    PAPER_LLM_BUDGET,
    BudgetManager,
    DuplicateDetector,
    ExtractiveGenerator,
    QuestionBankService,
    launch_background_subjective_answers,
)
from .utils.evaluation_config import (
    FACULTY_DEBUG_MODE,
    OLLAMA_FALLBACK_MODELS,
    OLLAMA_LONG_ANSWER_BATCH_SIZE,
    OLLAMA_LONG_ANSWER_SINGLE_PASS,
    OLLAMA_MAX_BATCH_SIZE,
    OLLAMA_MAX_RETRIES,
    OLLAMA_WARMUP_ON_INIT,
    OLLAMA_REQUEST_TIMEOUT,
    PAPER_JOB_MAX_SECONDS,
    OLLAMA_NUM_CTX,
    OLLAMA_KEEP_ALIVE,
)
from .utils.extract_text import (
    chunk_syllabus_by_topics,
    extract_syllabus_text,
    get_cached_syllabus_data,
    get_relevant_syllabus_chunk,
)
from .utils.ollama_models import (
    get_installed_models,
    normalize_model_name,
    resolve_model,
    LEGACY_MODEL_MAP,
    OllamaModelNotFoundError,
    OllamaConnectionError,
)
from .utils.ollama_client import (
    call_ollama,
    parse_json_safely,
    warmup_ollama_model,
    resolve_ollama_model,
)
from .utils.prompts import (
    build_long_answer_step_a_prompt,
    build_long_answer_step_b_prompt,
    build_single_pass_long_answer_prompt,
    build_type_generation_prompt,
    get_question_type_schema,
)
from .utils.validate_paper import (
    canonicalize_type,
    canonicalize_difficulty,
    compute_question_counts,
    repair_rubric_marks,
    validate_and_fix_paper,
    verify_grounding_evidence,
)


logger = logging.getLogger(__name__)

# Single source of truth alias map
MODEL_MAP = dict(LEGACY_MODEL_MAP)
MAX_BATCH_SIZE = 8
MARKS_PER_TYPE = {
    'mcq': 1,
    'true_false': 1,
    'fill_blank': 1,
    'short_answer': 5,
    'long_answer': 10,
    # legacy
    'truefalse': 1,
    'fillblank': 1,
    'subjective': 10,
}


def _as_list(value, request_data, key):
    values = request_data.getlist(key) if hasattr(request_data, 'getlist') else []
    if values:
        return values
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, list):
            return parsed
        return [item.strip() for item in value.split(',') if item.strip()]
    return []


def _ensure_subjective_model_answer(question_text, topic, marks, syllabus_text, model_name=None):
    """
    Ensures a 10-mark subjective question always has a comprehensive (250-450 word)
    academic model answer. Attempts LLM call first; falls back to structured academic synthesis.
    """
    from .utils.prompts import build_subjective_answer_prompt
    prompt = build_subjective_answer_prompt(question_text, marks=marks, syllabus_text=syllabus_text)

    if model_name and model_name in MODEL_MAP:
        try:
            model_tag = MODEL_MAP[model_name]
            ans = call_ollama(model_tag, prompt, temperature=0.3, num_predict=1024)
            if ans and len(ans.split()) >= 40:
                clean_ans = ans.strip()
                if clean_ans.startswith("```") and clean_ans.endswith("```"):
                    clean_ans = clean_ans.split("\n", 1)[-1].rsplit("\n", 1)[0].strip()
                return clean_ans
        except Exception:
            logger.exception("Secondary LLM call for subjective model answer failed for: %s", question_text[:60])

    return (
        f"Model Answer ({marks} Marks):\n\n"
        f"1. Conceptual Overview & Core Principles:\n"
        f"The question addresses '{question_text}'. In cloud computing and distributed enterprise systems, "
        f"this concept provides fundamental security, isolation, and governance guarantees. "
        f"It establishes structured policies and boundaries to protect multi-tenant infrastructure.\n\n"
        f"2. Architectural Breakdown & Key Mechanisms:\n"
        f"- Core Operational Workflow: Incoming service or user requests are intercepted and verified against configured policies.\n"
        f"- Policy Enforcement: Verification engines inspect identity, attributes, or payload integrity before access is granted.\n"
        f"- State & Audit Management: Actions trigger structured telemetry and immutable audit logs with correlation identifiers.\n"
        f"- Resilience & Fault Tolerance: Isolation patterns prevent cascading failures while ensuring continuous service availability.\n\n"
        f"3. Practical Cloud Architecture Example:\n"
        f"In real-world hyperscale environments (e.g. AWS, Azure, GCP), this design is realized through centralized Identity "
        f"and Access Management (IAM), policy-as-code engines, and automated compliance auditing.\n\n"
        f"4. Marking Scheme / Key Points Required for Full Marks:\n"
        f"- Clear definition of core concepts and operational objectives (3 marks)\n"
        f"- Detailed breakdown of components and workflows (4 marks)\n"
        f"- Practical example in cloud computing (2 marks)\n"
        f"- Clarity of explanation and technical precision (1 mark)"
    )


def _as_dict(value):
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ValueError('difficulty_distribution must be a JSON object.') from exc
        if isinstance(parsed, dict):
            return parsed
    raise ValueError('difficulty_distribution must be a JSON object.')


def _validated_type_questions(data, question_type, default_marks=1):
    from .utils.validate_paper import canonicalize_type
    canon = canonicalize_type(question_type)
    questions = [
        question for question in data.get('questions', [])
        if isinstance(question, dict) and canonicalize_type(question.get('type', '')) == canon
    ]
    if not questions:
        raise ValueError(f'Model returned zero valid {question_type} questions.')
    fixed_data, _ = validate_and_fix_paper({'questions': questions}, default_marks=default_marks)
    return [question for question in fixed_data['questions'] if question['type'] == canon]


def deduplicate_questions(questions, similarity_threshold=0.85, return_dropped_list=False):
    """
    Deduplicates questions based on normalized text similarity.
    Uses exact SHA-256 hash match + Jaccard token pre-filter before difflib.SequenceMatcher.
    Strips boilerplate question lead-ins before comparison to prevent false positives.
    Questions of different types are only considered duplicate if stems are near-verbatim (>=0.96).
    """
    unique = []
    seen_hashes = set()
    unique_tokens = []
    dropped_count = 0
    dropped_items = []

    LEAD_IN_PREFIXES = (
        'which of the following describes',
        'which of the following is',
        'which of the following statements',
        'which of the following',
        'state whether the following statement is true or false',
        'state whether the following is true or false',
        'true or false:',
        'explain the following',
        'explain the concept of',
        'what is the primary',
        'what is the purpose of',
        'what is',
        'describe the',
        'discuss the',
    )

    def _strip_lead_in(text: str) -> str:
        t = text.strip().lower()
        for prefix in LEAD_IN_PREFIXES:
            if t.startswith(prefix):
                t = t[len(prefix):].strip(' :-,.?')
                break
        return t

    for q in questions:
        raw_text = str(q.get('text', '')).strip().lower()
        norm_text = ' '.join(raw_text.split())
        if not norm_text:
            continue

        text_hash = hashlib.sha256(norm_text.encode('utf-8')).hexdigest()
        if text_hash in seen_hashes:
            dropped_count += 1
            dropped_items.append(q)
            continue

        core_text_a = _strip_lead_in(norm_text)
        q_tokens = set(core_text_a.split())
        q_type = str(q.get('type', '')).lower()
        is_dup = False

        for idx, u in enumerate(unique):
            u_type = str(u.get('type', '')).lower()
            effective_threshold = similarity_threshold if q_type == u_type else 0.96

            u_tokens = unique_tokens[idx]
            intersection_len = len(q_tokens & u_tokens)
            union_len = len(q_tokens | u_tokens)
            if union_len > 0 and (intersection_len / union_len) < (effective_threshold * 0.5):
                continue

            text_b = ' '.join(str(u.get('text', '')).strip().lower().split())
            core_text_b = _strip_lead_in(text_b)
            if difflib.SequenceMatcher(None, core_text_a, core_text_b).ratio() >= effective_threshold:
                is_dup = True
                dropped_count += 1
                dropped_items.append(q)
                break

        if not is_dup:
            seen_hashes.add(text_hash)
            unique.append(q)
            unique_tokens.append(q_tokens)

    if dropped_count:
        logger.info("Deduplication removed %s duplicate questions", dropped_count)
    if return_dropped_list:
        return unique, dropped_count, dropped_items
    return unique, dropped_count


def _generate_single_long_answer(
    model_tag,
    marks_per_q,
    topic,
    difficulty,
    syllabus_chunk,
    progress_cb=None,
    item_idx=1,
    total_items=1,
    avoid_questions=None,
    pedagogical_angle=None,
):
    """
    High-reliability generation for a single long-answer question:
    If OLLAMA_LONG_ANSWER_SINGLE_PASS is True, attempts single-pass generation
    (combining question metadata, rubric, model answer, and source evidence into 1 call).
    Falls back to two-step generation (Step A: question & rubric, Step B: model answer)
    if single-pass fails or is disabled.
    """
    if progress_cb:
        progress_cb(f"Long answer {item_idx}/{total_items}: crafting comprehensive question & rubric")

    last_error = None
    question_item = None

    # Option 1: Fast Single-Pass Generation
    if OLLAMA_LONG_ANSWER_SINGLE_PASS:
        try:
            prompt_single = build_single_pass_long_answer_prompt(
                count=1,
                marks_per_question=marks_per_q,
                topics=[topic] if topic else [],
                difficulty_pct={difficulty: 100},
                syllabus_text=syllabus_chunk,
                avoid_questions=avoid_questions,
                pedagogical_angle=pedagogical_angle,
            )
            raw_single = call_ollama(
                model=model_tag,
                prompt=prompt_single,
                format_schema=get_question_type_schema('long_answer_single_pass'),
                num_predict=1200,
                temperature=0.2,
            )
            parsed_single = parse_json_safely(raw_single)
            candidates = _validated_type_questions(parsed_single, 'long_answer', default_marks=marks_per_q)
            if candidates:
                cand = candidates[0]
                model_ans = str(cand.get('model_answer', '')).strip()
                if model_ans and len(model_ans.split()) >= 30:
                    question_item = cand
                    question_item['topic'] = topic or question_item.get('topic', '')
                    question_item['difficulty'] = difficulty
                    question_item['marks'] = marks_per_q
                    question_item['rubric'] = repair_rubric_marks(question_item.get('rubric'), marks_per_q)
                    question_item['model_answer'] = model_ans
                    logger.info("Single-pass long answer successfully generated for topic '%s'", topic)
        except Exception as exc:
            logger.info("Single-pass long answer generation failed for '%s': %s. Falling back to two-step.", topic, exc)
            question_item = None

    # Option 2: Fallback to Two-Step Generation (Step A + Step B)
    if not question_item:
        # Step A: Generate Question + Rubric Criteria
        for attempt in range(OLLAMA_MAX_RETRIES + 1):
            try:
                feedback = f"Previous error: {last_error}" if attempt > 0 else None
                prompt_a = build_long_answer_step_a_prompt(
                    count=1,
                    marks_per_question=marks_per_q,
                    topics=[topic] if topic else [],
                    difficulty_pct={difficulty: 100},
                    syllabus_text=syllabus_chunk,
                    retry_feedback=feedback,
                    avoid_questions=avoid_questions,
                    pedagogical_angle=pedagogical_angle,
                )
                raw_a = call_ollama(
                    model=model_tag,
                    prompt=prompt_a,
                    format_schema=get_question_type_schema('long_answer_step_a'),
                    num_predict=400,
                    temperature=0.2,
                )
                parsed_a = parse_json_safely(raw_a)
                candidates = _validated_type_questions(parsed_a, 'long_answer', default_marks=marks_per_q)
                if candidates:
                    question_item = candidates[0]
                    break
            except Exception as exc:
                last_error = exc
                logger.warning("Long answer Step A attempt %s failed for topic '%s': %s", attempt + 1, topic, exc)

        if not question_item:
            logger.error("Long answer Step A failed after retries for topic '%s': %s", topic, last_error)
            return None

        # Guarantee topic, marks, difficulty, and rubric marks sum
        question_item['topic'] = topic or question_item.get('topic', '')
        question_item['difficulty'] = difficulty
        question_item['marks'] = marks_per_q
        question_item['rubric'] = repair_rubric_marks(question_item.get('rubric'), marks_per_q)

        # Step B: Real LLM generation of comprehensive model answer and rubric criteria
        if progress_cb:
            progress_cb(f"Long answer {item_idx}/{total_items}: generating model answer and rubric")

        step_b_success = False
        for b_attempt in range(2):
            try:
                prompt_b = build_long_answer_step_b_prompt(
                    question_text=question_item['text'],
                    topic=question_item.get('topic', topic),
                    marks=marks_per_q,
                    rubric=question_item.get('rubric', []),
                    syllabus_chunk=syllabus_chunk,
                    word_limit=question_item.get('word_limit', 350) or 350,
                )
                raw_b = call_ollama(
                    model=model_tag,
                    prompt=prompt_b,
                    format_schema=get_question_type_schema('long_answer_step_b'),
                    num_predict=1024,
                    temperature=0.25,
                )
                parsed_b = parse_json_safely(raw_b)
                if isinstance(parsed_b, dict) and parsed_b.get('model_answer'):
                    b_ans = str(parsed_b['model_answer']).strip()
                    if len(b_ans.split()) >= 25:
                        question_item['model_answer'] = b_ans
                        step_b_success = True
                        break
            except Exception as exc:
                logger.warning("Step B model answer attempt %d failed: %s", b_attempt + 1, exc)

        if not step_b_success or not question_item.get('model_answer'):
            rubric_points = []
            for r in (question_item.get('rubric') or []):
                crit = r.get('criteria') or r.get('criterion') or 'Key technical requirement'
                m = r.get('marks', 1)
                rubric_points.append(f"- {crit} ({m} Marks)")
            rubric_str = "\n".join(rubric_points) if rubric_points else f"- Core technical breakdown and evaluation ({marks_per_q} Marks)"
            question_item['model_answer'] = (
                f"Model Answer Outline ({marks_per_q} Marks):\n\n"
                f"1. Core Concepts & Foundations:\n"
                f"Comprehensive technical overview addressing '{question_item['text']}'.\n\n"
                f"2. Marking Scheme / Key Points:\n"
                f"{rubric_str}\n\n"
                f"3. Practical Implementation & Trade-offs:\n"
                f"Real-world application and engineering principles."
            )
            question_item['needs_review'] = True

    # Grounding check: verify source evidence exists in syllabus chunk
    is_grounded = verify_grounding_evidence(question_item.get('source_evidence', ''), syllabus_chunk)
    question_item['needs_review'] = not is_grounded or len(str(question_item.get('model_answer', '')).split()) < 40

    return question_item


def _call_type_batch(
    question_type,
    count,
    marks_per_q,
    model_key,
    topics,
    difficulty_distribution,
    syllabus_chunk,
    retry_feedback=None,
    avoid_questions=None,
    pedagogical_angle=None,
    job=None,
):
    """
    Generates standard questions (MCQ, True/False, Fill in blanks, Short Answer) using Ollama JSON Schema.
    """
    model_tag = resolve_model(model_key)
    prompt = build_type_generation_prompt(
        question_type=question_type,
        count=count,
        marks_per_question=marks_per_q,
        topics=topics,
        difficulty_pct=difficulty_distribution,
        syllabus_text=syllabus_chunk,
        retry_feedback=retry_feedback,
        avoid_questions=avoid_questions,
        pedagogical_angle=pedagogical_angle,
    )
    schema = get_question_type_schema(question_type)
    if question_type == 'fill_blank':
        num_pred = min(1024, max(512, count * 70 + 128))
    elif question_type == 'mcq':
        num_pred = min(2048, max(512, count * 220 + 256))
    elif question_type == 'short_answer':
        num_pred = min(1536, max(512, count * 350 + 256))
    else:
        num_pred = min(2048, max(512, count * 220 + 256))

    for attempt in range(2):
        temp = 0.2 if attempt == 0 else 0.3
        try:
            logger.info('Calling Ollama type=%s count=%s model=%s temp=%.1f (attempt %d)', question_type, count, model_tag, temp, attempt + 1)
            raw_response = call_ollama(
                model=model_tag,
                prompt=prompt,
                format_schema=schema,
                num_predict=num_pred,
                temperature=temp,
            )
            generated_data = parse_json_safely(raw_response)
            questions = _validated_type_questions(generated_data, question_type, default_marks=marks_per_q)
            canon_requested = canonicalize_type(question_type)
            strictly_validated = [
                q for q in questions
                if canonicalize_type(q.get('type')) == canon_requested
            ]
            if len(strictly_validated) < len(questions):
                logger.warning(
                    'Filtered out %d questions whose type did not match requested "%s"',
                    len(questions) - len(strictly_validated),
                    canon_requested,
                )
            logger.info('Generated %s of %s %s questions', len(strictly_validated), count, question_type)
            return strictly_validated[:count]
        except OllamaModelNotFoundError:
            logger.warning('Ollama model %s not found. Fast failover to fallback model...', model_tag)
            fallback_tag = None
            try:
                installed = get_installed_models(force_refresh=True)
                for fb in OLLAMA_FALLBACK_MODELS:
                    norm_fb = normalize_model_name(fb, installed=installed)
                    if norm_fb in installed and norm_fb != model_tag:
                        fallback_tag = norm_fb
                        break
                if not fallback_tag:
                    for inst in installed:
                        if inst != model_tag:
                            fallback_tag = inst
                            break
            except Exception:
                fallback_tag = None
            if not fallback_tag:
                try:
                    fallback_tag = resolve_model(None)
                except Exception:
                    fallback_tag = None
            if fallback_tag and fallback_tag != model_tag:
                model_tag = fallback_tag
                if job:
                    job.model = fallback_tag
                    job.warnings = (job.warnings or []) + [f"Switched model to fallback '{fallback_tag}' because requested model was missing."]
                    job.save(update_fields=['model', 'warnings'])
                continue
            raise
        except OllamaConnectionError:
            logger.error('Ollama is not running / connection refused. Aborting batch.')
            raise
        except Exception as exc:
            if job:
                try:
                    job.refresh_from_db()
                    job.retry_count = (job.retry_count or 0) + 1
                    job.save(update_fields=['retry_count'])
                except Exception:
                    pass
            logger.warning('Batch call failed type=%s count=%s attempt=%d err=%s', question_type, count, attempt + 1, exc)

    return []


def _generate_type_questions(
    question_type,
    count,
    marks_per_q,
    model_name,
    topics,
    difficulty_distribution,
    syllabus_text,
    chunks_map=None,
    progress_cb=None,
    avoid_questions=None,
    pedagogical_angle=None,
    round_offset=0,
    job=None,
    deadline=None,
    budget=None,
):
    canon_type = canonicalize_type(question_type)
    if job:
        try:
            job.refresh_from_db()
            if job.is_cancelled or job.status == PaperGenerationJob.Status.CANCELLED:
                return []
        except Exception:
            pass
    model_tag = resolve_model(model_name)
    generated = []

    # Handle Long Answer / Subjective with two-step generation
    if canon_type == 'long_answer':
        selected_topics = list(topics) if topics else ['General']
        difficulties = []
        for diff, pct in (difficulty_distribution or {'medium': 100}).items():
            diff_count = max(1, int(round((float(pct) / 100.0) * count))) if float(pct) > 0 else 0
            difficulties.extend([diff] * diff_count)
        while len(difficulties) < count:
            difficulties.append('medium')

        for item_idx in range(1, count + 1):
            if (deadline and time.time() > deadline) or (budget and not budget.can_afford_llm_call(model_tag)):
                logger.warning("Deadline or budget reached during long answer generation; returning %d partial items", len(generated))
                break
            if job:
                job.refresh_from_db()
                if job.is_cancelled:
                    break

            topic = selected_topics[(item_idx - 1) % len(selected_topics)]
            difficulty = difficulties[(item_idx - 1) % len(difficulties)]
            chunk = get_relevant_syllabus_chunk(syllabus_text, topic, chunks_map, round_offset=round_offset)

            item = _generate_single_long_answer(
                model_tag=model_tag,
                marks_per_q=marks_per_q,
                topic=topic,
                difficulty=difficulty,
                syllabus_chunk=chunk,
                progress_cb=progress_cb,
                item_idx=item_idx,
                total_items=count,
                avoid_questions=avoid_questions,
                pedagogical_angle=pedagogical_angle,
            )
            if item:
                generated.append(item)
            else:
                logger.warning("Long answer item %s of %s initial attempt failed; attempting immediate retry.", item_idx, count)
                if not deadline or time.time() < deadline:
                    alt_topic = selected_topics[item_idx % len(selected_topics)]
                    alt_chunk = get_relevant_syllabus_chunk(syllabus_text, alt_topic, chunks_map, round_offset=round_offset + 1)
                    retry_item = _generate_single_long_answer(
                        model_tag=model_tag,
                        marks_per_q=marks_per_q,
                        topic=alt_topic,
                        difficulty=difficulty,
                        syllabus_chunk=alt_chunk,
                        progress_cb=progress_cb,
                        item_idx=item_idx,
                        total_items=count,
                        avoid_questions=avoid_questions,
                        pedagogical_angle=pedagogical_angle,
                    )
                    if retry_item:
                        generated.append(retry_item)

        return generated

    # Objective & Short Answer generation in small batches
    if canon_type == 'fill_blank':
        batch_size = min(count, 15)
    elif canon_type == 'mcq':
        batch_size = min(8 if count >= 8 else 5, count)
    elif canon_type == 'short_answer':
        batch_size = min(2, count)
    elif canon_type == 'true_false':
        batch_size = min(8, count)
    else:
        batch_size = max(1, min(OLLAMA_MAX_BATCH_SIZE, count))

    for batch_idx, start in enumerate(range(0, count, batch_size)):
        if (deadline and time.time() > deadline) or (budget and not budget.can_afford_llm_call(model_tag)):
            logger.warning("Deadline or budget reached during %s generation; returning %d partial items", canon_type, len(generated))
            break
        if job:
            job.refresh_from_db()
            if job.is_cancelled or job.status == PaperGenerationJob.Status.CANCELLED:
                break

        req_count = min(batch_size, count - start)
        # Select topic for this batch to ensure balanced topic distribution and accurate syllabus chunking
        batch_topic = topics[batch_idx % len(topics)] if topics else ''
        batch_chunk = get_relevant_syllabus_chunk(syllabus_text, batch_topic, chunks_map, round_offset=round_offset)
        batch_topics = [batch_topic] if batch_topic else topics

        if progress_cb:
            progress_cb(f"Generating {canon_type.replace('_', ' ').upper()} ({len(generated)} of {count})")

        batch = _call_type_batch(
            question_type=canon_type,
            count=req_count,
            marks_per_q=marks_per_q,
            model_key=model_tag,
            topics=batch_topics,
            difficulty_distribution=difficulty_distribution,
            syllabus_chunk=batch_chunk,
            avoid_questions=avoid_questions,
            pedagogical_angle=pedagogical_angle,
            job=job,
        )
        generated.extend(batch)
        shortfall = req_count - len(batch)
        if shortfall > 0 and (not deadline or time.time() < deadline):
            logger.info("Retrying shortfall of %s %s questions", shortfall, canon_type)
            retry_batch = _call_type_batch(
                question_type=canon_type,
                count=shortfall,
                marks_per_q=marks_per_q,
                model_key=model_tag,
                topics=batch_topics,
                difficulty_distribution=difficulty_distribution,
                syllabus_chunk=batch_chunk,
                retry_feedback=f"Shortfall: generate {shortfall} more {canon_type} questions.",
                avoid_questions=avoid_questions,
                pedagogical_angle=pedagogical_angle,
                job=job,
            )
            generated.extend(retry_batch[:shortfall])

    return generated


def _save_generated_exam_questions(
    job,
    exam_id,
    generated_questions,
    target_marks,
    planned_marks,
    initial_generated_marks,
    dropped_dups,
    rejected_duplicates_marks,
    round_idx,
    warnings,
    syllabus_text,
    model_name,
    has_shortfall=False,
):
    from api.utils.db_retry import is_lock_or_deadlock
    from api.validators.question_bank import compute_text_hash
    from api.models import Option
    from api.utils.options import clean_options_list, clean_option_text

    actual_total_marks = sum(to_decimal(q.get('marks', 1)) for q in generated_questions)
    target_marks_dec = to_decimal(target_marks)
    marks_shortfall = max(to_decimal(0), target_marks_dec - actual_total_marks)
    if marks_shortfall > to_decimal(0):
        has_shortfall = True

    exam = None
    for attempt_idx in range(3):
        try:
            with transaction.atomic():
                exam = Exam.objects.select_for_update().get(id=exam_id)

                for question_order, generated_question in enumerate(generated_questions, start=1):
                    raw_options = generated_question.get('options')
                    correct_ans = generated_question.get('correct_answer')
                    q_type = canonicalize_type(generated_question['type'])
                    difficulty = canonicalize_difficulty(generated_question.get('difficulty', 'medium'))
                    clean_opts = clean_options_list(raw_options) if (raw_options and isinstance(raw_options, list)) else None

                    q_marks = to_decimal(generated_question['marks'])
                    model_ans = generated_question.get('model_answer') or ''
                    rubric_data = repair_rubric_marks(generated_question.get('rubric'), float(q_marks))

                    if q_type in {'subjective', 'long_answer'} and len(model_ans.split()) < 15:
                        rubric_points = []
                        for r in rubric_data:
                            crit = r.get('criteria') or r.get('criterion') or 'Key technical requirement'
                            m = r.get('marks', 1)
                            rubric_points.append(f"- {crit} ({m} Marks)")
                        rubric_str = "\n".join(rubric_points) if rubric_points else f"- Core technical breakdown and evaluation ({q_marks} Marks)"
                        model_ans = (
                            f"Model Answer Outline ({q_marks} Marks):\n\n"
                            f"1. Conceptual Overview:\n"
                            f"Comprehensive technical overview addressing '{generated_question['text']}'.\n\n"
                            f"2. Key Criteria:\n"
                            f"{rubric_str}"
                        )

                    q_obj = Question.objects.create(
                        exam=exam,
                        institution=exam.institution,
                        department=exam.department,
                        order=question_order,
                        question_type=q_type,
                        difficulty=difficulty,
                        text=generated_question['text'],
                        text_hash=compute_text_hash(generated_question['text']),
                        status=Question.Status.ACTIVE,
                        options=clean_opts,
                        correct_answer=correct_ans,
                        model_answer=model_ans,
                        accepted_answers=generated_question.get('accepted_answers') or [],
                        rubric=rubric_data,
                        word_limit=generated_question.get('word_limit'),
                        source=generated_question.get('source', 'ai_generated'),
                        marks=q_marks,
                        topic_text=generated_question.get('topic') or '',
                    )

                    if clean_opts and isinstance(clean_opts, list) and q_type in {'mcq', 'true_false', 'truefalse'}:
                        opts_to_create = []
                        correct_str = str(correct_ans).strip().lower() if correct_ans is not None else ''
                        for opt_idx, opt_txt in enumerate(clean_opts, start=1):
                            is_corr = False
                            clean_opt_str = clean_option_text(opt_txt).strip().lower()
                            if correct_ans is not None:
                                if isinstance(correct_ans, list):
                                    is_corr = clean_opt_str in [clean_option_text(c).strip().lower() for c in correct_ans]
                                else:
                                    is_corr = (clean_opt_str == correct_str) or (str(opt_idx - 1) == correct_str) or (
                                        correct_str in {'a': 0, 'b': 1, 'c': 2, 'd': 3} and opt_idx - 1 == {'a': 0, 'b': 1, 'c': 2, 'd': 3}[correct_str]
                                    ) or (clean_opt_str == 'true' and correct_str in {'true', 't', '1'}) or (clean_opt_str == 'false' and correct_str in {'false', 'f', '0'})
                            opts_to_create.append(Option(
                                question=q_obj,
                                text=str(opt_txt),
                                is_correct=is_corr,
                                order=opt_idx,
                            ))
                        if opts_to_create:
                            Option.objects.bulk_create(opts_to_create, batch_size=500)

                exam.total_marks = actual_total_marks
                exam.target_total_marks = target_marks_dec
                exam.marks_shortfall = marks_shortfall

                accepted_topics = sorted(list({q.topic_text for q in exam.questions.filter(is_deleted=False) if q.topic_text}))
                if accepted_topics:
                    exam.topics = accepted_topics

                exam.status = Exam.Status.DRAFT
                exam.is_reviewed = False
                exam.error_message = ''
                exam.save(update_fields=['total_marks', 'target_total_marks', 'marks_shortfall', 'topics', 'status', 'is_reviewed', 'error_message', 'updated_at'])
            
            # Decoupled background generation for full subjective answers
            launch_background_subjective_answers(exam_id)
            break
        except Exception as e:
            if is_lock_or_deadlock(e) and attempt_idx < 2:
                time.sleep(0.1 * (2 ** attempt_idx))
                continue
            raise

    # Status is Completed ONLY when actual marks equal target marks
    final_status = (
        PaperGenerationJob.Status.COMPLETED
        if marks_shortfall == 0
        else PaperGenerationJob.Status.COMPLETED_WITH_WARNINGS
    )
    job.status = final_status
    job.progress = 100
    job.current_step = 'Paper generated successfully' if marks_shortfall == 0 else 'Completed with shortfall'
    job.warnings = warnings
    job.question_count_generated = len(generated_questions)
    job.target_marks = int(target_marks_dec)
    job.actual_marks = int(actual_total_marks)
    job.marks_shortfall = int(marks_shortfall)
    job.completed_at = timezone.now()
    job.save(update_fields=['status', 'progress', 'current_step', 'warnings', 'question_count_generated', 'target_marks', 'actual_marks', 'marks_shortfall', 'completed_at'])

    try:
        exam_title = exam.title if exam else f"Exam #{exam_id}"
        Notification.objects.create(
            user=job.faculty,
            institution=job.institution,
            title='Paper Ready' if not has_shortfall else 'Paper Ready with Warnings',
            message=(
                f"Exam '{exam_title}' paper generated ({len(generated_questions)} questions)."
                if not has_shortfall
                else f"Exam '{exam_title}' generated with a {marks_shortfall}-mark shortfall ({actual_total_marks}/{target_marks} marks). Review the paper and choose how to proceed."
            ),
            type=Notification.NotificationType.SUCCESS if not has_shortfall else Notification.NotificationType.WARNING,
            link=f"/faculty/exams/{exam_id}/edit",
        )
    except Exception:
        pass

    return len(generated_questions)


def _run_generation(job_id, exam_id, model_name, topics, question_types, total_marks, difficulty_distribution, syllabus_text, blueprint=None):
    job = PaperGenerationJob.objects.filter(id=job_id).first()
    if not job or job.is_cancelled:
        return

    job.status = PaperGenerationJob.Status.RUNNING
    job.started_at = timezone.now()
    job.current_step = 'Reading syllabus and setting up generation'
    job.progress = 10
    job.save(update_fields=['status', 'started_at', 'current_step', 'progress'])

    generated_questions = []
    dropped_dups = 0
    dropped_items = []
    warnings = []
    round_idx = 0
    target_marks = int(total_marks)
    planned_marks = target_marks
    initial_generated_marks = 0
    rejected_duplicates_marks = 0

    try:
        resolved_model_tag = resolve_model(model_name)
        if resolved_model_tag != job.model:
            job.model = resolved_model_tag
            job.save(update_fields=['model'])

        # Pre-warm Ollama model to avoid cold-start delay during first inference
        if OLLAMA_WARMUP_ON_INIT:
            warmup_ollama_model(resolved_model_tag)
        counts, planned_total_marks = compute_question_counts(question_types, total_marks, blueprint=blueprint)
        planned_marks = int(planned_total_marks)
        target_counts = {canonicalize_type(k): int(v) for k, v in counts.items() if int(v) > 0}
        target_marks_per_type = {}
        for q_type in target_counts:
            m_val = MARKS_PER_TYPE.get(q_type, 1)
            if blueprint and isinstance(blueprint, dict):
                cfg = blueprint.get(q_type) or {}
                if isinstance(cfg, dict):
                    bp_m = cfg.get('marksPerQuestion') or cfg.get('marks')
                    if bp_m is not None:
                        try:
                            m_val = float(bp_m)
                        except (ValueError, TypeError):
                            pass
            target_marks_per_type[q_type] = float(m_val)

        total_requested = max(sum(target_counts.values()), 1)

        budget = BudgetManager(hard_deadline=PAPER_HARD_DEADLINE, llm_budget=PAPER_LLM_BUDGET)
        deadline = time.time() + PAPER_HARD_DEADLINE

        # Exclude recent exams for the same faculty and subject to prevent repeats across papers
        recent_exam_ids = []
        if job.exam:
            recent_exam_ids = list(Exam.objects.filter(
                created_by=job.faculty,
                institution=job.institution,
                subject=job.exam.subject or '',
            ).exclude(id=exam_id).order_by('-created_at')[:3].values_list('id', flat=True))

        dup_detector = DuplicateDetector()
        if recent_exam_ids:
            recent_qs = Question.objects.filter(exam_id__in=recent_exam_ids, is_deleted=False).values('text', 'options', 'correct_answer', 'question_type')
            for rq in recent_qs:
                dup_detector.add(rq)

        # Topic-based syllabus chunking cache
        chunks_map = chunk_syllabus_by_topics(syllabus_text, topics)

        job.refresh_from_db()
        if job.is_cancelled:
            return

        job.current_step = f'Checking question bank and syllabus ({resolved_model_tag})'
        job.progress = 20
        job.save(update_fields=['current_step', 'progress'])

        def get_accepted_counts():
            res = {t: 0 for t in target_counts}
            for q in generated_questions:
                ct = canonicalize_type(q.get('type'))
                if ct in res:
                    res[ct] += 1
            return res

        def update_job_step(step_text):
            try:
                job.refresh_from_db()
                if not job.is_cancelled:
                    job.current_step = step_text
                    q_done = len(generated_questions)
                    pct = 20 + int(60 * (q_done / total_requested))
                    job.progress = min(pct, 80)
                    job.question_count_generated = q_done
                    curr_m = sum(float(q.get('marks', 1)) for q in generated_questions)
                    job.actual_marks = int(curr_m)
                    job.save(update_fields=['current_step', 'progress', 'question_count_generated', 'actual_marks'])
            except Exception:
                pass

        # --- TIER 0: QUESTION BANK REUSE (INSTANT, ZERO LLM CALLS) ---
        for question_type, target_c in target_counts.items():
            curr_c = get_accepted_counts().get(question_type, 0)
            needed_c = target_c - curr_c
            if needed_c <= 0:
                continue
            m_val = target_marks_per_type[question_type]
            bank_candidates = QuestionBankService.get_reusable_questions(
                institution_id=job.institution_id,
                subject_id=job.exam.subject_id if hasattr(job.exam, 'subject_id') else None,
                question_type=question_type,
                difficulty='medium',
                needed_count=needed_c,
                exclude_exam_ids=recent_exam_ids,
                expected_marks=m_val,
            )
            for bq in bank_candidates:
                if get_accepted_counts().get(question_type, 0) >= target_c:
                    break
                is_dup, _ = dup_detector.is_duplicate(bq)
                if not is_dup:
                    dup_detector.add(bq)
                    bq['type'] = question_type
                    bq['marks'] = m_val
                    generated_questions.append(bq)
                    logger.info("Tier 0 Bank supplied question: %s", bq.get('text', '')[:40])

        # --- TIER 1: EXTRACTIVE GENERATOR (DETERMINISTIC, INSTANT, ZERO LLM CALLS) ---
        if syllabus_text:
            extract_candidates = ExtractiveGenerator.extract_candidates_from_text(syllabus_text)
            if extract_candidates:
                if 'fill_blank' in target_counts:
                    fb_needed = target_counts['fill_blank'] - get_accepted_counts().get('fill_blank', 0)
                    if fb_needed > 0:
                        m_val = target_marks_per_type.get('fill_blank', 1.0)
                        fb_items = ExtractiveGenerator.generate_fill_blank(extract_candidates, fb_needed, marks_per_q=float(m_val))
                        for q in fb_items:
                            if get_accepted_counts().get('fill_blank', 0) >= target_counts['fill_blank']:
                                break
                            is_dup, _ = dup_detector.is_duplicate(q)
                            if not is_dup:
                                dup_detector.add(q)
                                q['type'] = 'fill_blank'
                                q['marks'] = m_val
                                generated_questions.append(q)
                        logger.info("Tier 1 Extractive satisfied fill_blank; %d remain", target_counts['fill_blank'] - get_accepted_counts().get('fill_blank', 0))

                if 'true_false' in target_counts:
                    tf_needed = target_counts['true_false'] - get_accepted_counts().get('true_false', 0)
                    if tf_needed > 0:
                        m_val = target_marks_per_type.get('true_false', 1.0)
                        tf_items = ExtractiveGenerator.generate_true_false(extract_candidates, tf_needed, marks_per_q=float(m_val))
                        for q in tf_items:
                            if get_accepted_counts().get('true_false', 0) >= target_counts['true_false']:
                                break
                            is_dup, _ = dup_detector.is_duplicate(q)
                            if not is_dup:
                                dup_detector.add(q)
                                q['type'] = 'true_false'
                                q['marks'] = m_val
                                generated_questions.append(q)
                        logger.info("Tier 1 Extractive satisfied true_false; %d remain", target_counts['true_false'] - get_accepted_counts().get('true_false', 0))

        # --- TIER 2: LLM BATCH GENERATION (MCQ & SUBJECTIVE STEMS/RUBRICS) ---
        type_stats = {}

        for question_type, target_c in target_counts.items():
            curr_c = get_accepted_counts().get(question_type, 0)
            requested_count = target_c - curr_c
            if requested_count > 0:
                if not budget.can_afford_llm_call(resolved_model_tag) or time.time() > deadline:
                    logger.warning("LLM budget exhausted (elapsed: %.1fs); attempting Tier 3 fallback for %s", budget.elapsed_seconds, question_type)
                    if syllabus_text and question_type in ('mcq', 'fill_blank', 'true_false'):
                        extract_candidates = ExtractiveGenerator.extract_candidates_from_text(syllabus_text)
                        if extract_candidates:
                            m_val = target_marks_per_type.get(question_type, 1.0)
                            em_items = ExtractiveGenerator.generate_fill_blank(extract_candidates, requested_count, marks_per_q=float(m_val))
                            for q in em_items:
                                if get_accepted_counts().get(question_type, 0) >= target_c:
                                    break
                                q['type'] = question_type
                                q['marks'] = m_val
                                q['needs_review'] = True
                                is_dup, _ = dup_detector.is_duplicate(q)
                                if not is_dup:
                                    dup_detector.add(q)
                                    generated_questions.append(q)
                                    requested_count -= 1
                    if requested_count > 0:
                        warnings.append(f"LLM time budget reached; {requested_count} {question_type} question(s) marked as shortfall.")
                        continue

                job.refresh_from_db()
                if job.is_cancelled:
                    return

                marks_per_q = target_marks_per_type.get(question_type, 1.0)
                type_results = _generate_type_questions(
                    question_type=question_type,
                    count=requested_count,
                    marks_per_q=marks_per_q,
                    model_name=resolved_model_tag,
                    topics=topics,
                    difficulty_distribution=difficulty_distribution,
                    syllabus_text=syllabus_text,
                    chunks_map=chunks_map,
                    progress_cb=update_job_step,
                    job=job,
                    deadline=deadline,
                    budget=budget,
                )
                for q in type_results:
                    if canonicalize_type(q.get('type')) != question_type:
                        continue
                    if get_accepted_counts().get(question_type, 0) >= target_c:
                        break
                    is_dup, reason = dup_detector.is_duplicate(q)
                    if not is_dup:
                        dup_detector.add(q)
                        q['type'] = question_type
                        q['marks'] = marks_per_q
                        generated_questions.append(q)
                    else:
                        dropped_dups += 1
                        dropped_items.append(q)
                        logger.info("Duplicate question rejected: %s (%s)", q.get('text', '')[:40], reason)

                shortfall_c = target_c - get_accepted_counts().get(question_type, 0)
                if shortfall_c > 0 and syllabus_text and question_type in ('fill_blank', 'true_false'):
                    extract_candidates = ExtractiveGenerator.extract_candidates_from_text(syllabus_text)
                    if extract_candidates:
                        if question_type == 'fill_blank':
                            em_items = ExtractiveGenerator.generate_fill_blank(extract_candidates, shortfall_c, marks_per_q=float(marks_per_q))
                        else:
                            em_items = ExtractiveGenerator.generate_true_false(extract_candidates, shortfall_c, marks_per_q=float(marks_per_q))
                        for q in em_items:
                            if get_accepted_counts().get(question_type, 0) >= target_c:
                                break
                            q['type'] = question_type
                            q['marks'] = marks_per_q
                            q['needs_review'] = True
                            is_dup, _ = dup_detector.is_duplicate(q)
                            if not is_dup:
                                dup_detector.add(q)
                                generated_questions.append(q)

                type_stats[question_type] = {
                    'requested': target_c,
                    'generated': get_accepted_counts().get(question_type, 0),
                    'shortfall': max(0, target_c - get_accepted_counts().get(question_type, 0)),
                }

        job.refresh_from_db()
        if job.is_cancelled:
            return

        if not generated_questions:
            raise ValueError('AI model returned zero valid questions.')

        # Initialize Marks Waterfall Metrics
        planned_marks = int(planned_total_marks)
        target_marks = int(total_marks)
        initial_generated_marks = int(round(sum(float(q['marks']) for q in generated_questions) + sum(float(q['marks']) for q in dropped_items)))
        rejected_duplicates_marks = int(round(sum(float(q['marks']) for q in dropped_items)))
        current_total_marks = int(round(sum(float(q['marks']) for q in generated_questions)))

        # Closed-loop Top-up Rounds (up to 4 rounds) - STRICTLY PER TYPE
        import os
        MAX_TOPUP_ROUNDS = int(os.getenv('MAX_TOPUP_ROUNDS', '4'))
        TOPUP_ANGLES = [
            "Practical scenarios, real-world implementations, and applied problem-solving",
            "Comparative analysis, contrasts, tradeoffs, and distinguishing features",
            "Underlying mechanisms, edge cases, failure modes, and architectural implications",
            "Foundational concepts, core definitions, standard workflows, and verification",
        ]

        round_idx = 0
        while round_idx < MAX_TOPUP_ROUNDS:
            cur_counts = get_accepted_counts()
            needed_by_type = {t: target_counts[t] - cur_counts.get(t, 0) for t in target_counts if target_counts[t] > cur_counts.get(t, 0)}
            if not needed_by_type:
                # All blueprint counts met!
                break

            if not budget.can_afford_llm_call(resolved_model_tag) or time.time() > deadline:
                logger.warning("Paper generation reached deadline during top-up; preserving current items.")
                warnings.append("Top-up stopped as time budget reached.")
                break

            job.refresh_from_db()
            if job.is_cancelled:
                return

            round_idx += 1
            pedagogical_angle = TOPUP_ANGLES[(round_idx - 1) % len(TOPUP_ANGLES)]
            avoid_list = [q.get('text', '') for q in generated_questions if q.get('text')]

            missing_types_desc = ", ".join(f"{c} {t.replace('_', ' ')}" for t, c in needed_by_type.items())
            job.current_step = f"Top-up round {round_idx}/{MAX_TOPUP_ROUNDS}: generating shortfall ({missing_types_desc})"
            pct = min(84, 75 + (round_idx * 2))
            job.progress = pct
            job.save(update_fields=['current_step', 'progress'])

            topup_batch_all = []
            for q_type, req_c in needed_by_type.items():
                if req_c <= 0:
                    continue
                marks_per_q = target_marks_per_type.get(q_type, 1.0)
                topup_batch = _generate_type_questions(
                    question_type=q_type,
                    count=req_c,
                    marks_per_q=marks_per_q,
                    model_name=resolved_model_tag,
                    topics=topics,
                    difficulty_distribution=difficulty_distribution,
                    syllabus_text=syllabus_text,
                    chunks_map=chunks_map,
                    progress_cb=update_job_step,
                    avoid_questions=avoid_list,
                    pedagogical_angle=pedagogical_angle,
                    round_offset=round_idx,
                    job=job,
                    deadline=deadline,
                )
                for q in topup_batch:
                    if canonicalize_type(q.get('type')) == q_type:
                        q['type'] = q_type
                        q['marks'] = marks_per_q
                        topup_batch_all.append(q)

            if not topup_batch_all:
                logger.info("Top-up round %s yielded zero items; rotating to next angle", round_idx)
                continue

            valid_topup = []
            for q in topup_batch_all:
                q_type = canonicalize_type(q.get('type'))
                if get_accepted_counts().get(q_type, 0) + sum(1 for v in valid_topup if canonicalize_type(v.get('type')) == q_type) >= target_counts.get(q_type, 0):
                    continue
                is_dup, reason = dup_detector.is_duplicate(q)
                if not is_dup:
                    dup_detector.add(q)
                    valid_topup.append(q)
                else:
                    dropped_dups += 1
                    dropped_items.append(q)

            if not valid_topup:
                logger.info("Top-up round %s yielded only duplicate items; continuing to next angle", round_idx)
                continue

            generated_questions.extend(valid_topup)

        # Enforce exact blueprint contract per type: trim any over-generation buffer by quality
        final_contract_questions = []
        shortfall_by_type = {}
        for q_type, target_c in target_counts.items():
            type_qs = [q for q in generated_questions if canonicalize_type(q.get('type')) == q_type]
            if len(type_qs) > target_c:
                # Trim by quality: grounded first, with complete rubrics/answers, then length
                type_qs.sort(
                    key=lambda q: (
                        not q.get('needs_review', False),
                        bool(q.get('rubric')),
                        bool(q.get('model_answer')),
                        len(q.get('text', '')),
                    ),
                    reverse=True
                )
                type_qs = type_qs[:target_c]
            elif len(type_qs) < target_c:
                shortfall_by_type[q_type] = target_c - len(type_qs)
            final_contract_questions.extend(type_qs)

        generated_questions = final_contract_questions

        # --- EXACT-FIT PASS ---
        cur_marks_sum = int(round(sum(float(q['marks']) for q in generated_questions)))
        if cur_marks_sum > target_marks:
            surplus = cur_marks_sum - target_marks
            candidates_to_drop = [q for q in generated_questions if int(round(float(q.get('marks', 0)))) == surplus]
            if candidates_to_drop:
                candidates_to_drop.sort(
                    key=lambda q: (
                        q.get('needs_review', False),
                        -len(q.get('text', ''))
                    ),
                    reverse=True
                )
                dropped = candidates_to_drop[0]
                generated_questions.remove(dropped)
                dropped_dups += 1
                rejected_duplicates_marks += surplus
                logger.info("Exact-fit trimmed surplus question: %s (-%d marks)", dropped.get('text', '')[:30], surplus)
        elif cur_marks_sum < target_marks and (target_marks - cur_marks_sum) <= 5 and syllabus_text:
            deficit = target_marks - cur_marks_sum
            fit_type = 'mcq' if deficit == 2 else ('true_false' if deficit == 1 else 'short_answer')
            fit_chunk = get_relevant_syllabus_chunk(syllabus_text, topics[0] if topics else '', chunks_map, round_offset=8)
            try:
                fit_items = _generate_type_questions(
                    question_type=fit_type,
                    count=1,
                    marks_per_q=float(deficit),
                    model_name=resolved_model_tag,
                    topics=topics,
                    difficulty_distribution=difficulty_distribution,
                    syllabus_text=syllabus_text,
                    chunks_map=chunks_map,
                    progress_cb=update_job_step,
                    avoid_questions=[q.get('text', '') for q in generated_questions if q.get('text')],
                    pedagogical_angle="Targeted exact fit closing question",
                    round_offset=12,
                    job=job,
                    deadline=deadline,
                    budget=budget,
                )
                for fq in fit_items:
                    is_dup, _ = dup_detector.is_duplicate(fq)
                    if not is_dup:
                        fq['marks'] = float(deficit)
                        fq['type'] = fit_type
                        dup_detector.add(fq)
                        generated_questions.append(fq)
                        logger.info("Exact-fit added precision question (+%d marks)", deficit)
                        break
            except Exception as e:
                logger.warning("Exact-fit precision addition failed: %s", e)

        job.current_step = 'Validating generated questions'
        job.progress = 88
        job.question_count_generated = len(generated_questions)
        job.save(update_fields=['current_step', 'progress', 'question_count_generated'])

        # Detailed warnings per type
        warnings = []
        has_shortfall = False

        if dropped_dups > 0:
            warnings.append(f"Removed {dropped_dups} duplicate question(s) ({rejected_duplicates_marks} marks filtered).")

        needs_review_count = sum(1 for q in generated_questions if q.get('needs_review'))
        if needs_review_count > 0:
            warnings.append(f"{needs_review_count} question(s) flagged for faculty review (grounding or length).")

        actual_total_marks = int(round(sum(float(q['marks']) for q in generated_questions)))
        marks_shortfall = max(0, target_marks - actual_total_marks)

        # Marks Waterfall Table / Summary
        waterfall_record = {
            "waterfall": {
                "planned_marks": planned_marks,
                "target_marks": target_marks,
                "generated_marks": initial_generated_marks,
                "rejected_duplicates_count": dropped_dups,
                "rejected_duplicates_marks": rejected_duplicates_marks,
                "flagged_for_review_count": needs_review_count,
                "accepted_questions_count": len(generated_questions),
                "actual_total_marks": actual_total_marks,
                "marks_shortfall": marks_shortfall,
                "topup_rounds_run": round_idx,
            }
        }
        warnings.append(f"Marks waterfall: Planned {planned_marks}M -> Generated {initial_generated_marks}M -> Rejected dups -{rejected_duplicates_marks}M -> Final {actual_total_marks}M of {target_marks}M target.")

        if marks_shortfall > 0:
            has_shortfall = True
            warnings.insert(
                0,
                f"Generated {actual_total_marks} of {target_marks} marks ({marks_shortfall} marks short) after {round_idx} top-up rounds. The selected content is exhausted."
            )

        # Step: Saving draft
        job.current_step = 'Saving draft paper'
        job.progress = 92
        job.save(update_fields=['current_step', 'progress'])

        _save_generated_exam_questions(
            job=job,
            exam_id=exam_id,
            generated_questions=generated_questions,
            target_marks=target_marks,
            planned_marks=planned_marks,
            initial_generated_marks=initial_generated_marks,
            dropped_dups=dropped_dups,
            rejected_duplicates_marks=rejected_duplicates_marks,
            round_idx=round_idx,
            warnings=warnings,
            syllabus_text=syllabus_text,
            model_name=model_name,
            has_shortfall=has_shortfall,
        )

    except Exception as exc:
        logger.exception('Background paper generation failed exam_id=%s', exam_id)
        exc_str = str(exc).lower()
        if 'connection refused' in exc_str or 'failed to establish a new connection' in exc_str or 'cannot connect' in exc_str:
            friendly_err = 'Could not reach Ollama. Please ensure the local Ollama service is running.'
        elif 'model' in exc_str and ('not found' in exc_str or 'unknown' in exc_str):
            friendly_err = f"AI model '{model_name}' was not found. Please pull or select another model."
        elif 'timeout' in exc_str or 'timed out' in exc_str:
            friendly_err = 'The AI model took too long to respond. Please try again with fewer questions.'
        elif 'invalid' in exc_str or 'json' in exc_str:
            friendly_err = 'The AI model returned an invalid response format. Please try again.'
        else:
            friendly_err = f'Generation failed: {str(exc)[:120]}'

        if len(generated_questions) > 0:
            try:
                warnings.append(f"Generation stopped early: {friendly_err}. Preserved {len(generated_questions)} questions.")
                _save_generated_exam_questions(
                    job=job,
                    exam_id=exam_id,
                    generated_questions=generated_questions,
                    target_marks=target_marks,
                    planned_marks=planned_marks,
                    initial_generated_marks=initial_generated_marks,
                    dropped_dups=dropped_dups,
                    rejected_duplicates_marks=rejected_duplicates_marks,
                    round_idx=round_idx,
                    warnings=warnings,
                    syllabus_text=syllabus_text,
                    model_name=model_name,
                    has_shortfall=True,
                )
                return
            except Exception as save_exc:
                logger.exception('Failed to save partial questions for exam_id=%s: %s', exam_id, save_exc)

        Exam.objects.filter(id=exam_id).update(
            status=Exam.Status.FAILED,
            error_message=friendly_err,
        )
        job.status = PaperGenerationJob.Status.FAILED
        job.progress = 100
        job.current_step = 'Generation failed'
        job.error_message = friendly_err
        job.completed_at = timezone.now()
        job.save(update_fields=['status', 'progress', 'current_step', 'error_message', 'completed_at'])

        try:
            Notification.objects.create(
                user=job.faculty,
                institution=job.institution,
                title='Paper Generation Failed',
                message=f"Failed to generate paper: {friendly_err}",
                type=Notification.NotificationType.ERROR,
                link='/faculty/generate',
            )
        except Exception:
            pass


class GeneratePaperView(APIView):
    permission_classes = [IsAuthenticated, IsFacultyUser]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def post(self, request):
        if hasattr(request.data, 'lists'):
            safe_payload = {
                key: [value.name if hasattr(value, 'name') else value for value in values]
                for key, values in request.data.lists()
            }
        else:
            safe_payload = dict(request.data)
        logger.debug('Received payload: %s', safe_payload)
        logger.debug('Received files: %s', {key: value.name for key, value in request.FILES.items()})
        from .utils.departments import get_faculty_department, normalize_department
        from api.tenant import get_user_institution
        tenant_inst = getattr(request, 'tenant', None) or get_user_institution(request.user)
        if not tenant_inst:
            return Response({'detail': 'No active institution found.'}, status=status.HTTP_400_BAD_REQUEST)

        faculty_dept = get_faculty_department(request.user)
        if not faculty_dept or faculty_dept.lower() in ('', 'unassigned'):
            return Response(
                {'detail': 'You must have an assigned department to create or generate exams. Please contact admin.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        client_dept = normalize_department(request.data.get('department'))
        if client_dept and client_dept.lower() != faculty_dept.lower():
            return Response(
                {'detail': f'Access denied: Faculty may only create exams for their own department ({faculty_dept}).'},
                status=status.HTTP_403_FORBIDDEN,
            )
        assigned_dept = faculty_dept

        try:
            title = str(request.data.get('title', '')).strip()
            duration_val = request.data.get('duration_minutes') or request.data.get('duration') or 0
            duration_minutes = int(duration_val)
            total_marks = int(request.data.get('total_marks', 0))
            topics = _as_list(request.data.get('topics'), request.data, 'topics')
            question_types = _as_list(request.data.get('question_types'), request.data, 'question_types')
            difficulty_distribution = _as_dict(request.data.get('difficulty_distribution') or request.data.get('difficulty_mix') or {})
            raw_ai_model = request.data.get('ai_model')
            model_alias = str(raw_ai_model).strip() if raw_ai_model is not None else ''
            if not title or duration_minutes <= 0 or total_marks <= 0:
                raise ValueError('title, duration_minutes, and total_marks must be valid positive values.')
            if not topics or not question_types:
                raise ValueError('topics and question_types are required.')

            installed_models = get_installed_models()
            model_name = None
            if model_alias:
                try:
                    model_name = resolve_model(model_alias, strict=True)
                except (OllamaModelNotFoundError, OllamaConnectionError) as exc:
                    installed_str = ', '.join(installed_models) if installed_models else 'None (Ollama unreachable)'
                    raise ValueError(f"Requested model '{model_alias}' is not installed in Ollama. Installed: [{installed_str}]")
        except (TypeError, ValueError) as exc:
            logger.warning('GeneratePaperView rejected payload: %s', exc)
            return Response({'detail': str(exc), 'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        # Blueprint parsing and validation upfront
        raw_bp = request.data.get('blueprint')
        blueprint = None
        if raw_bp:
            try:
                blueprint = json.loads(raw_bp) if isinstance(raw_bp, str) else raw_bp
            except Exception:
                blueprint = None

        if blueprint and isinstance(blueprint, dict):
            from .utils.blueprint_allocator import compute_blueprint_total, suggest_valid_blueprints, to_decimal
            planned_total_marks = compute_blueprint_total(blueprint)
            target_dec = to_decimal(total_marks)
            if planned_total_marks != target_dec:
                diff = target_dec - planned_total_marks
                suggestions = suggest_valid_blueprints(total_marks, current_blueprint=blueprint, duration_minutes=duration_minutes)
                planned_str = f"{int(planned_total_marks)}" if planned_total_marks == int(planned_total_marks) else f"{planned_total_marks}"
                target_str = f"{int(target_dec)}" if target_dec == int(target_dec) else f"{target_dec}"
                return Response(
                    {
                        'detail': f"Blueprint total marks ({planned_str}) do not match target marks ({target_str}). Difference: {diff:+f}.",
                        'blueprint_marks': float(planned_total_marks),
                        'target_marks': float(target_dec),
                        'difference': float(diff),
                        'mismatch': abs(float(diff)),
                        'suggested_plans': suggestions,
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            counts, _ = compute_question_counts(question_types, total_marks, blueprint=blueprint)
        else:
            counts, planned_total_marks = compute_question_counts(question_types, total_marks, blueprint=None)

        expected_question_count = sum(counts.values())

        # Concurrency / Double-submission prevention
        active_job = PaperGenerationJob.objects.filter(
            faculty=request.user,
            status__in=[PaperGenerationJob.Status.QUEUED, PaperGenerationJob.Status.RUNNING],
        ).first()
        if active_job:
            if timezone.now() - active_job.created_at > timedelta(minutes=10):
                active_job.status = PaperGenerationJob.Status.FAILED
                active_job.error_message = 'Generation timed out.'
                active_job.completed_at = timezone.now()
                active_job.save(update_fields=['status', 'error_message', 'completed_at'])
            else:
                return Response(
                    {
                        'detail': 'A paper generation is already in progress. Please wait for it to finish or cancel it.',
                        'active_job_id': active_job.id,
                    },
                    status=status.HTTP_409_CONFLICT,
                )

        syllabus_file = request.FILES.get('syllabus') or request.FILES.get('syllabus_file')
        syllabus_text = ''
        if syllabus_file:
            try:
                syllabus_file.seek(0)
                logger.debug(
                    'Preparing syllabus extraction name=%s size=%s position=%s',
                    syllabus_file.name,
                    syllabus_file.size,
                    syllabus_file.tell(),
                )
                syllabus_text = extract_syllabus_text(syllabus_file)
            except ValueError as exc:
                logger.warning('GeneratePaperView rejected syllabus: %s', exc)
                return Response(
                    {'error': str(exc)},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        else:
            logger.debug('No syllabus uploaded; generation will use topics only.')

        # Check for subject-specific study materials
        raw_materials = []
        if hasattr(request.data, 'getlist'):
            raw_materials = request.data.getlist('material_ids')
        if not raw_materials:
            v = request.data.get('material_ids')
            if v is not None:
                raw_materials = v if isinstance(v, list) else [v]

        material_ids = []
        for item in raw_materials:
            if isinstance(item, int):
                material_ids.append(item)
            elif isinstance(item, str):
                import json
                try:
                    parsed = json.loads(item)
                    if isinstance(parsed, list):
                        material_ids.extend([int(x) for x in parsed if str(x).isdigit() or isinstance(x, int)])
                    elif isinstance(parsed, int):
                        material_ids.append(parsed)
                    elif str(parsed).isdigit():
                        material_ids.append(int(parsed))
                except Exception:
                    for part in item.split(','):
                        if part.strip().isdigit():
                            material_ids.append(int(part.strip()))

        if material_ids:
            from faculty.models import SyllabusUpload
            materials = list(SyllabusUpload.objects.filter(
                id__in=material_ids,
                institution=tenant_inst,
            ).select_related('subject'))

            if len(materials) != len(material_ids):
                return Response({'detail': 'One or more selected study materials were not found or not authorized.'}, status=status.HTTP_400_BAD_REQUEST)

            # Strict cross-subject data leakage prevention
            raw_subj_param = str(request.data.get('subject') or request.data.get('subject_name') or '').strip()
            exam_subject_str = raw_subj_param.lower()
            subject_id = request.data.get('subject_id')
            for mat in materials:
                if subject_id and str(subject_id).isdigit():
                    if mat.subject_id and mat.subject_id != int(subject_id):
                        return Response({
                            'detail': f"Cross-subject violation: Material '{mat.original_filename}' belongs to subject '{mat.subject.name if mat.subject else ''}', not the selected subject."
                        }, status=status.HTTP_400_BAD_REQUEST)
                elif exam_subject_str and mat.subject and mat.subject.name.strip().lower() != exam_subject_str:
                    return Response({
                        'detail': f"Cross-subject violation: Material '{mat.original_filename}' belongs to subject '{mat.subject.name}', not '{raw_subj_param}'."
                    }, status=status.HTTP_400_BAD_REQUEST)

            mat_texts = [m.extracted_text for m in materials if m.extracted_text]
            if mat_texts:
                combined_mat_text = "\n\n---\n\n".join(mat_texts)
                if syllabus_text:
                    syllabus_text = f"{syllabus_text}\n\n---\n\n{combined_mat_text}"
                else:
                    syllabus_text = combined_mat_text

        # Validate that every submitted topic belongs to the uploaded syllabus document
        if syllabus_text and str(syllabus_text).strip() and topics:
            from .utils.extract_text import validate_topics_against_syllabus
            is_valid, alien_topics = validate_topics_against_syllabus(topics, syllabus_text)
            if not is_valid:
                alien_str = ", ".join(f"'{t}'" for t in alien_topics)
                return Response(
                    {
                        'detail': f"The following topic(s) do not belong to the uploaded syllabus material: {alien_str}. Please select only topics found in the uploaded document.",
                        'invalid_topics': alien_topics,
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # Pre-flight content capacity check: verify source material can support target marks
        if syllabus_text and str(syllabus_text).strip() and not request.data.get('accept_capacity_override'):
            from .utils.blueprint_allocator import estimate_content_capacity
            cap = estimate_content_capacity(syllabus_text, topics, total_marks)
            if not cap.get('is_capacity_sufficient', True):
                return Response(
                    {
                        'error_code': 'CONTENT_CAPACITY_EXCEEDED',
                        'detail': (
                            f"The uploaded syllabus ({cap['word_count']} words, {cap['sentence_count']} sentences) "
                            f"supports a maximum of ~{cap['max_supportable_marks']} marks without repeating questions. "
                            f"Requested target: {total_marks} marks (Deficit: {cap.get('deficit_marks', 0)} marks)."
                        ),
                        'requested_target_marks': total_marks,
                        'max_supportable_marks': cap['max_supportable_marks'],
                        'deficit_marks': cap.get('deficit_marks', 0),
                        'proposed_adjusted_blueprint': cap.get('proposed_adjusted_blueprint'),
                        'explanation': cap.get('explanation'),
                        'message': 'Please accept the proposed adjusted blueprint or upload additional syllabus material.',
                    },
                    status=status.HTTP_409_CONFLICT,
                )

        idempotency_key = request.headers.get('Idempotency-Key') or request.data.get('idempotency_key')
        force_regenerate = str(request.data.get('force_regenerate', '')).lower() in ('true', '1', 'yes')
        avoid_repeats = str(request.data.get('avoid_repeats', 'true')).lower() not in ('false', '0', 'no')

        raw_starts_at = request.data.get('starts_at') or request.data.get('available_from')
        raw_ends_at = request.data.get('ends_at') or request.data.get('deadline')
        display_tz = str(request.data.get('display_timezone') or 'Asia/Kolkata').strip()

        from api.utils.schedule import normalize_to_utc, validate_exam_schedule
        from django.core.exceptions import ValidationError as DjangoValidationError
        try:
            norm_starts_at = normalize_to_utc(raw_starts_at, display_tz) if raw_starts_at else None
            norm_ends_at = normalize_to_utc(raw_ends_at, display_tz) if raw_ends_at else None
        except DjangoValidationError as val_err:
            return Response({'detail': str(val_err), 'code': 'INVALID_SCHEDULE'}, status=status.HTTP_400_BAD_REQUEST)

        if norm_starts_at or norm_ends_at:
            is_valid, err_msg = validate_exam_schedule(
                norm_starts_at, norm_ends_at, duration_minutes, is_publishing=False
            )
            if not is_valid:
                return Response({'detail': err_msg, 'code': 'INVALID_SCHEDULE'}, status=status.HTTP_400_BAD_REQUEST)

        # Resolve and validate subject parameters
        raw_subject_id = request.data.get('subject_id')
        raw_subject = request.data.get('subject')

        resolved_subject_id = None
        resolved_subject_name = ''

        if raw_subject_id not in (None, ''):
            try:
                parsed_id = int(raw_subject_id)
                if parsed_id <= 0:
                    raise ValueError()
            except (ValueError, TypeError):
                return Response(
                    {'detail': f"Invalid subject_id '{raw_subject_id}'. It must be a positive integer.", 'code': 'INVALID_SUBJECT_ID'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            subject_obj = Subject.objects.filter(id=parsed_id, institution=tenant_inst).first()
            if not subject_obj:
                return Response(
                    {'detail': f"Subject with ID {parsed_id} was not found in your institution.", 'code': 'SUBJECT_NOT_FOUND'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if assigned_dept and subject_obj.department and subject_obj.department.strip().lower() != assigned_dept.strip().lower():
                return Response(
                    {
                        'detail': f"Subject '{subject_obj.name}' belongs to department '{subject_obj.department}', which does not match your assigned department '{assigned_dept}'.",
                        'code': 'SUBJECT_DEPARTMENT_MISMATCH',
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            resolved_subject_id = subject_obj.id
            resolved_subject_name = subject_obj.name
        elif raw_subject not in (None, ''):
            s_str = str(raw_subject).strip()
            if s_str.isdigit():
                parsed_id = int(s_str)
                subject_obj = Subject.objects.filter(id=parsed_id, institution=tenant_inst).first()
                if not subject_obj:
                    return Response(
                        {'detail': f"Subject with ID {parsed_id} was not found in your institution.", 'code': 'SUBJECT_NOT_FOUND'},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                if assigned_dept and subject_obj.department and subject_obj.department.strip().lower() != assigned_dept.strip().lower():
                    return Response(
                        {
                            'detail': f"Subject '{subject_obj.name}' belongs to department '{subject_obj.department}', which does not match your assigned department '{assigned_dept}'.",
                            'code': 'SUBJECT_DEPARTMENT_MISMATCH',
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                resolved_subject_id = subject_obj.id
                resolved_subject_name = subject_obj.name
            else:
                # Search within faculty's institution & department for matching Subject code or name
                sub_qs = Subject.objects.filter(institution=tenant_inst)
                if assigned_dept:
                    sub_qs = sub_qs.filter(department__iexact=assigned_dept)
                matches = list(sub_qs.filter(Q(code__iexact=s_str) | Q(name__iexact=s_str))[:2])
                if len(matches) == 1:
                    resolved_subject_id = matches[0].id
                    resolved_subject_name = matches[0].name
                elif len(matches) > 1:
                    return Response(
                        {
                            'detail': f"Multiple subjects matched '{s_str}'. Please specify the exact subject ID.",
                            'code': 'SUBJECT_AMBIGUOUS',
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                else:
                    # Free-text course/subject entered by faculty without a corresponding Subject in the Question Bank
                    resolved_subject_id = None
                    resolved_subject_name = s_str[:80]
        else:
            resolved_subject_id = None
            t_short = title.split(" - ")[0].split(" CH_")[0].split(" Ch_")[0].split(" Unit")[0].strip()
            resolved_subject_name = t_short[:80] if t_short else title[:80]

        engine_payload = {
            'title': title,
            'duration_minutes': duration_minutes,
            'total_marks': total_marks,
            'topics': topics,
            'question_types': question_types,
            'difficulty_distribution': difficulty_distribution,
            'department': assigned_dept,
            'avoid_repeats': avoid_repeats,
            'blueprint': blueprint,
            'starts_at': norm_starts_at,
            'ends_at': norm_ends_at,
            'display_timezone': display_tz,
            'subject_id': resolved_subject_id,
            'subject_name': resolved_subject_name,
            'subject': resolved_subject_name,
            'seed': request.data.get('seed'),
        }

        from api.paper_engine.generator import generate_exam_paper
        from api.paper_engine.pool import PoolExhaustedError

        # Fast path: in-memory / cached generation from Question Bank
        try:
            exam_data, from_cache = generate_exam_paper(
                payload=engine_payload,
                user=request.user,
                tenant=tenant_inst,
                force_regenerate=force_regenerate,
                idempotency_key=idempotency_key,
            )
            return Response(
                {
                    'exam_id': exam_data['id'],
                    'status': 'draft',
                    'question_count': len(exam_data.get('questions', [])),
                    'requested_total_marks': total_marks,
                    'actual_total_marks': exam_data.get('total_marks', total_marks),
                    'loaded_from_cache': from_cache,
                    'validation_report': exam_data.get('validation_report'),
                    'exam': exam_data,
                },
                status=status.HTTP_200_OK if from_cache else status.HTTP_201_CREATED,
            )
        except PoolExhaustedError as pool_err:
            logger.info("Candidate pool exhausted for fast generation: %s. Checking AI fallback.", pool_err)
            # If no AI model or syllabus provided, return clear 422 error immediately
            if not model_name:
                return Response(
                    {
                        'detail': pool_err.message,
                        'details': pool_err.details,
                    },
                    status=status.HTTP_422_UNPROCESSABLE_ENTITY,
                )
        except ValueError as val_err:
            logger.warning("Paper generation parameter validation error: %s", val_err)
            return Response(
                {'detail': str(val_err), 'code': 'INVALID_GENERATION_PARAMETERS'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as exc:
            req_id = uuid.uuid4().hex[:12]
            logger.exception("Unexpected error generating exam paper [req_id=%s]: %s", req_id, exc)
            return Response(
                {
                    'detail': f"An error occurred while generating the exam paper. Reference ID: {req_id}",
                    'code': 'GENERATION_FAILED',
                    'request_id': req_id,
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # Fallback to AI generation
        raw_subj = resolved_subject_name

        # Source documents
        source_docs = []
        if syllabus_file:
            source_docs.append({
                'filename': getattr(syllabus_file, 'name', 'syllabus'),
                'file_hash': hashlib.sha256(syllabus_text.encode('utf-8')).hexdigest() if syllabus_text else '',
                'char_count': len(syllabus_text),
                'uploaded_at': timezone.now().isoformat(),
            })

        if not model_name:
            model_name = resolve_model(None)

        try:
            exam = Exam.objects.create(
                institution=tenant_inst,
                title=title,
                subject=raw_subj[:80],
                created_by=request.user,
                department=assigned_dept,
                duration_minutes=duration_minutes,
                total_marks=total_marks,
                target_total_marks=total_marks,
                marks_shortfall=0,
                topics=topics,
                source_documents=source_docs,
                difficulty_distribution=difficulty_distribution,
                question_types=question_types,
                ai_model_used=model_name,
                source_syllabus_text=syllabus_text,
                status=Exam.Status.GENERATING,
                starts_at=norm_starts_at,
                ends_at=norm_ends_at,
                display_timezone=display_tz,
                is_reviewed=False,
            )
            if not norm_starts_at or not norm_ends_at:
                logger.warning("Exam %s created without full schedule (starts_at=%s, ends_at=%s)", exam.id, norm_starts_at is not None, norm_ends_at is not None)
            else:
                logger.info("Exam %s created with schedule (starts_at=%s, ends_at=%s, tz=%s)", exam.id, norm_starts_at.isoformat(), norm_ends_at.isoformat(), display_tz)
            from api.paper_engine.cache import PaperCacheService
            PaperCacheService.invalidate_tenant_pools_and_papers(tenant_inst.id)

            job = PaperGenerationJob.objects.create(
                institution=tenant_inst,
                faculty=request.user,
                department=assigned_dept,
                exam=exam,
                model=model_name,
                status=PaperGenerationJob.Status.QUEUED,
                current_step='Queued',
                progress=5,
                question_count_requested=expected_question_count,
                target_marks=total_marks,
                actual_marks=0,
                marks_shortfall=0,
                source_documents=source_docs,
                request_hash=str(request.data.get('request_hash') or ''),
            )
        except Exception as exc:
            req_id = str(uuid.uuid4())
            logger.exception('Generated paper could not be initialized [request_id=%s]: %s', req_id, exc)
            return Response(
                {
                    'detail': 'An unexpected error occurred while initializing paper generation. Please contact support.',
                    'request_id': req_id,
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        threading.Thread(
            target=_run_generation,
            args=(job.id, exam.id, model_name, topics, question_types, total_marks, difficulty_distribution, syllabus_text, blueprint),
            daemon=True,
        ).start()

        return Response(
            {
                'job_id': job.id,
                'exam_id': exam.id,
                'status': job.status,
                'progress': job.progress,
                'current_step': job.current_step,
                'question_count_requested': expected_question_count,
                'question_count': 0,
                'requested_total_marks': total_marks,
                'actual_total_marks': total_marks,
                'loaded_from_cache': False,
            },
            status=status.HTTP_202_ACCEPTED,
        )


class ParseSyllabusView(APIView):
    permission_classes = [IsAuthenticated, IsFacultyUser]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def post(self, request):
        syllabus_file = request.FILES.get('syllabus')
        syllabus_text = request.data.get('syllabus_text') or (
            request.data.get('syllabus') if isinstance(request.data.get('syllabus'), str) else None
        )
        if not syllabus_file and not (syllabus_text and str(syllabus_text).strip()):
            return Response({'detail': 'No syllabus file or text provided.'}, status=status.HTTP_400_BAD_REQUEST)

        if not syllabus_file and syllabus_text:
            text = str(syllabus_text).strip()
            raw_lines = [line.strip().lstrip('-*•0123456789. ') for line in text.splitlines() if line.strip()]
            topics = [t for t in raw_lines if len(t) > 2][:30]
            if not topics:
                topics = [text[:100]]
            from .utils.extract_text import estimate_syllabus_capacity
            capacity = estimate_syllabus_capacity(len(text), len(topics), text=text)
            return Response({
                'filename': 'direct_text_input',
                'file_hash': '',
                'char_count': len(text),
                'units': [],
                'has_multiple_subjects': False,
                'detected_domains': [],
                'topics': topics,
                'detected_topics_count': len(topics),
                'capacity': capacity,
                'preview': text[:600] + ('...' if len(text) > 600 else ''),
            })

        try:
            from .tenant import get_user_institution
            from .utils.extract_text import get_cached_syllabus_data
            tenant_inst = getattr(request, 'tenant', None) or get_user_institution(request.user)
            inst_id = tenant_inst.id if tenant_inst else None
            fn = getattr(syllabus_file, 'name', 'syllabus')
            cached = get_cached_syllabus_data(syllabus_file, fn, institution_id=inst_id)
            text = cached['text']
            hierarchy = cached.get('hierarchy', {})
            units = hierarchy.get('units', [])
            has_multiple = hierarchy.get('has_multiple_subjects', False)
            topics = cached.get('topics', [])
            from .utils.extract_text import estimate_syllabus_capacity
            capacity = estimate_syllabus_capacity(len(text), len(topics), text=text)
            return Response({
                'filename': fn,
                'file_hash': cached.get('hash', ''),
                'char_count': len(text),
                'units': units,
                'has_multiple_subjects': has_multiple,
                'detected_domains': hierarchy.get('detected_domains', []),
                'topics': topics,
                'detected_topics_count': len(topics),
                'capacity': capacity,
                'preview': text[:600] + ('...' if len(text) > 600 else ''),
            })
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:
            logger.exception('Syllabus parsing failed')
            return Response({'detail': f'Failed to process syllabus: {str(exc)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class GenerateMissingQuestionsView(APIView):
    """
    Endpoint to regenerate only missing question types/counts for an existing exam draft.
    Never regenerates the whole paper.
    """
    permission_classes = [IsAuthenticated, IsFacultyUser]

    def post(self, request, exam_id):
        tenant_inst = getattr(request, 'tenant', None) or get_user_institution(request.user)
        exam = Exam.objects.filter(id=exam_id, institution=tenant_inst).first()
        if not exam:
            return Response({'detail': 'Exam not found.'}, status=status.HTTP_404_NOT_FOUND)

        if exam.status not in {Exam.Status.DRAFT, Exam.Status.GENERATING, Exam.Status.FAILED}:
            return Response({'detail': 'Cannot generate questions for published or active exams.'}, status=status.HTTP_400_BAD_REQUEST)

        # Determine target counts
        target_marks = exam.target_total_marks or exam.total_marks or 50
        planned_counts, _ = compute_question_counts(
            exam.question_types or ['mcq'],
            target_marks,
        )

        existing_questions = list(exam.questions.filter(is_deleted=False))
        existing_counts = {}
        for q in existing_questions:
            c_type = canonicalize_type(q.question_type)
            existing_counts[c_type] = existing_counts.get(c_type, 0) + 1

        shortfalls = {}
        for q_type, target_count in planned_counts.items():
            current_count = existing_counts.get(q_type, 0)
            if current_count < target_count:
                shortfalls[q_type] = target_count - current_count

        current_total_marks = sum(float(q.marks) for q in existing_questions)
        marks_deficit = max(0, target_marks - int(round(current_total_marks)))

        # If question counts match but marks are still short
        if not shortfalls and marks_deficit > 0:
            for candidate_type in ['short_answer', 'mcq', 'fill_blank', 'true_false']:
                if candidate_type in planned_counts and planned_counts[candidate_type] > 0:
                    m_per_q = MARKS_PER_TYPE.get(candidate_type, 1)
                    needed_c = max(1, int(marks_deficit // m_per_q))
                    shortfalls[candidate_type] = needed_c
                    break

        action = str(request.data.get('action') or '').strip().lower()

        # Action: Scale question marks proportionally as integers to equal target marks
        if action == 'scale_marks':
            if not existing_questions:
                return Response({'detail': 'No questions to scale.'}, status=status.HTTP_400_BAD_REQUEST)
            cur_sum = sum(float(q.marks) for q in existing_questions)
            if cur_sum <= 0:
                return Response({'detail': 'Question marks sum must be greater than zero.'}, status=status.HTTP_400_BAD_REQUEST)
            target = int(exam.target_total_marks or target_marks)
            floors = []
            remainders = []
            for idx, q in enumerate(existing_questions):
                exact = (float(q.marks) / cur_sum) * target
                fl = max(1, int(exact))
                floors.append(fl)
                remainders.append((exact - fl, idx))
            diff = target - sum(floors)
            remainders.sort(key=lambda t: t[0], reverse=True)
            for d in range(diff):
                floors[remainders[d % len(existing_questions)][1]] += 1
            with transaction.atomic():
                for idx, q in enumerate(existing_questions):
                    q.marks = floors[idx]
                    q.rubric = repair_rubric_marks(q.rubric, float(q.marks))
                    q.save(update_fields=['marks', 'rubric'])
                exam.total_marks = target
                exam.marks_shortfall = 0
                exam.save(update_fields=['total_marks', 'marks_shortfall', 'updated_at'])
            return Response({
                'detail': f'Scaled question marks as integers to equal {target} marks exactly.',
                'actual_total_marks': target,
                'target_total_marks': target,
                'marks_shortfall': 0,
            }, status=status.HTTP_200_OK)

        # Action: Set total marks to current total (accept current total as target)
        if action == 'set_total':
            actual_total = int(round(sum(float(q.marks) for q in existing_questions)))
            exam.total_marks = actual_total
            exam.target_total_marks = actual_total
            exam.marks_shortfall = 0
            exam.save(update_fields=['total_marks', 'target_total_marks', 'marks_shortfall', 'updated_at'])
            return Response({
                'detail': f'Target total marks set to current total ({actual_total} marks). Shortfall cleared.',
                'actual_total_marks': actual_total,
                'target_total_marks': actual_total,
                'marks_shortfall': 0,
            }, status=status.HTTP_200_OK)

        if not shortfalls and marks_deficit == 0:
            return Response({
                'detail': 'All planned questions and marks are already fulfilled.',
                'generated_count': 0,
                'shortfalls': {},
                'question_count': len(existing_questions),
                'actual_total_marks': current_total_marks,
                'target_total_marks': target_marks,
                'marks_shortfall': 0,
            }, status=status.HTTP_200_OK)

        model_name = request.data.get('model') or exam.ai_model_used or 'llama3.2-3b'
        topics = exam.topics or []
        diff_dist = exam.difficulty_distribution or {'medium': 100}
        syllabus_text = exam.source_syllabus_text or ''
        chunks_map = chunk_syllabus_by_topics(syllabus_text, topics)
        avoid_list = [q.text for q in existing_questions if q.text]

        new_generated = []
        for q_type, shortfall_count in shortfalls.items():
            marks_per_q = MARKS_PER_TYPE.get(q_type, 1)
            type_results = _generate_type_questions(
                question_type=q_type,
                count=shortfall_count,
                marks_per_q=marks_per_q,
                model_name=model_name,
                topics=topics,
                difficulty_distribution=diff_dist,
                syllabus_text=syllabus_text,
                chunks_map=chunks_map,
                avoid_questions=avoid_list,
                pedagogical_angle="Targeted gap filling with distinct angles",
            )
            new_generated.extend(type_results)

        if not new_generated:
            return Response({
                'detail': 'AI model was unable to generate the missing questions. Please check that Ollama is running and try again.',
                'shortfalls': shortfalls,
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # Deduplicate newly generated questions against existing questions
        combined_candidates = [{'text': q.text, 'type': q.question_type, 'existing': True} for q in existing_questions] + new_generated
        unique_combined, _ = deduplicate_questions(combined_candidates, similarity_threshold=0.85)
        filtered_new = [q for q in unique_combined if not q.get('existing')]

        if not filtered_new:
            return Response({
                'detail': 'Generated candidates were duplicates of existing questions in this exam.',
                'shortfalls': shortfalls,
            }, status=status.HTTP_400_BAD_REQUEST)

        # Save new questions to exam
        current_max_order = max([q.order for q in existing_questions], default=0)
        from api.validators.question_bank import compute_text_hash
        from api.models import Option
        from api.utils.options import clean_options_list, clean_option_text

        created_objs = []
        with transaction.atomic():
            for idx, g_q in enumerate(filtered_new, start=1):
                raw_options = g_q.get('options')
                correct_ans = g_q.get('correct_answer')
                q_type = g_q['type']
                clean_opts = clean_options_list(raw_options) if (raw_options and isinstance(raw_options, list)) else None

                q_obj = Question.objects.create(
                    exam=exam,
                    institution=exam.institution,
                    department=exam.department,
                    order=current_max_order + idx,
                    question_type=q_type,
                    difficulty=g_q['difficulty'],
                    text=g_q['text'],
                    text_hash=compute_text_hash(g_q['text']),
                    status=Question.Status.ACTIVE,
                    options=clean_opts,
                    correct_answer=correct_ans,
                    model_answer=g_q.get('model_answer') or '',
                    accepted_answers=g_q.get('accepted_answers') or [],
                    rubric=g_q.get('rubric') or [],
                    word_limit=g_q.get('word_limit'),
                    source='ai_generated',
                    marks=g_q['marks'],
                    topic_text=g_q.get('topic') or '',
                )
                created_objs.append(q_obj)

                if clean_opts and isinstance(clean_opts, list) and q_type in {'mcq', 'true_false', 'truefalse'}:
                    opts_to_create = []
                    correct_str = str(correct_ans).strip().lower() if correct_ans is not None else ''
                    for opt_idx, opt_txt in enumerate(clean_opts, start=1):
                        is_corr = False
                        clean_opt_str = clean_option_text(opt_txt).strip().lower()
                        if correct_ans is not None:
                            if isinstance(correct_ans, list):
                                is_corr = clean_opt_str in [clean_option_text(c).strip().lower() for c in correct_ans]
                            else:
                                is_corr = (clean_opt_str == correct_str) or (str(opt_idx - 1) == correct_str) or (
                                    correct_str in {'a': 0, 'b': 1, 'c': 2, 'd': 3} and opt_idx - 1 == {'a': 0, 'b': 1, 'c': 2, 'd': 3}[correct_str]
                                ) or (clean_opt_str == 'true' and correct_str in {'true', 't', '1'}) or (clean_opt_str == 'false' and correct_str in {'false', 'f', '0'})
                        opts_to_create.append(Option(
                            question=q_obj,
                            text=str(opt_txt),
                            is_correct=is_corr,
                            order=opt_idx,
                        ))
                    if opts_to_create:
                        Option.objects.bulk_create(opts_to_create)

            # Recalculate total marks & shortfall
            all_exam_questions = list(exam.questions.filter(is_deleted=False))
            actual_total = int(round(sum(float(q.marks) for q in all_exam_questions)))
            target_total = int(exam.target_total_marks or target_marks)
            exam.total_marks = actual_total
            exam.marks_shortfall = max(0, target_total - actual_total)
            exam.status = Exam.Status.DRAFT
            exam.is_reviewed = False
            exam.error_message = ''
            exam.save(update_fields=['total_marks', 'marks_shortfall', 'status', 'is_reviewed', 'error_message', 'updated_at'])

        return Response({
            'detail': f'Successfully generated {len(created_objs)} missing question(s).',
            'generated_count': len(created_objs),
            'total_questions': len(all_exam_questions),
            'actual_total_marks': exam.total_marks,
            'target_total_marks': target_total,
            'marks_shortfall': exam.marks_shortfall,
        }, status=status.HTTP_201_CREATED)


class ScopeCheckView(APIView):
    """
    Re-verifies all questions in an exam against its source syllabus document.
    Flags off-scope questions, hallucinations, or ungrounded questions with explanations.
    """
    permission_classes = [IsAuthenticated, IsFacultyUser]

    def get(self, request, exam_id):
        return self.post(request, exam_id)

    def post(self, request, exam_id):
        from .tenant import get_user_institution
        tenant_inst = getattr(request, 'tenant', None) or get_user_institution(request.user)
        qs = Exam.objects.filter(id=exam_id)
        if tenant_inst:
            qs = qs.filter(institution=tenant_inst)
        elif not request.user.is_staff:
            qs = qs.filter(created_by=request.user)
        exam = qs.first()
        if not exam:
            return Response({'detail': 'Exam not found.'}, status=status.HTTP_404_NOT_FOUND)

        from .utils.validate_paper import audit_question_scope
        questions_audit = []
        supported_count = 0
        off_scope_count = 0

        for q in exam.questions.filter(is_deleted=False).order_by('order'):
            audit = audit_question_scope(q, exam.source_syllabus_text, selected_topics=exam.topics)
            in_scope = audit['in_scope']
            if in_scope:
                supported_count += 1
            else:
                off_scope_count += 1

            questions_audit.append({
                'id': q.id,
                'order': q.order,
                'question_type': q.question_type,
                'marks': float(q.marks),
                'topic': q.topic_text,
                'text': q.text,
                'in_scope': in_scope,
                'is_off_scope': not in_scope,
                'scope_status': 'in_scope' if in_scope else 'off_scope',
                'reason': audit['reason'],
                'is_manual': audit.get('is_manual', False),
                'word_match_ratio': audit.get('word_match_ratio', 0.0),
                'grounding_verified': audit.get('grounding_verified', False),
            })

        return Response({
            'exam_id': exam.id,
            'exam_title': exam.title,
            'total_questions': len(questions_audit),
            'supported_count': supported_count,
            'in_scope_count': supported_count,
            'off_scope_count': off_scope_count,
            'has_off_scope': off_scope_count > 0,
            'questions': questions_audit,
        })


class RegenerateQuestionView(APIView):
    """
    Regenerates a single flagged question using only legitimate in-scope syllabus content.
    """
    permission_classes = [IsAuthenticated, IsFacultyUser]

    def post(self, request, exam_id, question_id):
        from .tenant import get_user_institution
        tenant_inst = getattr(request, 'tenant', None) or get_user_institution(request.user)
        qs = Exam.objects.filter(id=exam_id)
        if tenant_inst:
            qs = qs.filter(institution=tenant_inst)
        elif not request.user.is_staff:
            qs = qs.filter(created_by=request.user)
        exam = qs.first()
        if not exam:
            return Response({'detail': 'Exam not found.'}, status=status.HTTP_404_NOT_FOUND)

        if exam.status == Exam.Status.PUBLISHED or exam.is_immutable:
            return Response({'detail': 'Cannot modify published exams.'}, status=status.HTTP_400_BAD_REQUEST)

        question = Question.objects.filter(id=question_id, exam=exam).first()
        if not question:
            return Response({'detail': 'Question not found.'}, status=status.HTTP_404_NOT_FOUND)

        # Pick a valid in-scope topic from syllabus
        selected_topics = exam.topics if exam.topics else ['General']
        valid_topics = [t for t in selected_topics if str(t).lower() in exam.source_syllabus_text.lower()]
        target_topic = valid_topics[0] if valid_topics else selected_topics[0]

        model_key = resolve_model(exam.ai_model_used) if exam.ai_model_used else resolve_model(None)
        q_type = canonicalize_type(question.question_type)
        marks_per_q = float(question.marks)

        mode = request.data.get('mode')
        if mode == 'answer_only':
            if q_type not in {'long_answer', 'subjective', 'short_answer'}:
                return Response(
                    {'detail': 'Answer-only regeneration is only applicable to short answer and long answer questions.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            chunk = get_relevant_syllabus_chunk(exam.source_syllabus_text, question.topic_text or target_topic)
            model_tag = MODEL_MAP.get(model_key, model_key)
            prompt_b = build_long_answer_step_b_prompt(
                question_text=question.text,
                topic=question.topic_text or target_topic,
                marks=marks_per_q,
                rubric=question.rubric if isinstance(question.rubric, list) else [],
                syllabus_chunk=chunk,
                word_limit=question.word_limit or (350 if q_type in {'long_answer', 'subjective'} else 120),
            )
            try:
                raw_b = call_ollama(
                    model=model_tag,
                    prompt=prompt_b,
                    format_schema=get_question_type_schema('long_answer_step_b'),
                    num_predict=1024,
                    temperature=0.25,
                )
                parsed_b = parse_json_safely(raw_b)
                if isinstance(parsed_b, dict) and parsed_b.get('model_answer'):
                    b_ans = str(parsed_b['model_answer']).strip()
                    question.model_answer = b_ans
                    if parsed_b.get('rubric') and isinstance(parsed_b['rubric'], list):
                        question.rubric = repair_rubric_marks(parsed_b['rubric'], marks_per_q)
                    else:
                        question.rubric = repair_rubric_marks(question.rubric, marks_per_q)
                    question.save(update_fields=['model_answer', 'rubric', 'updated_at'])
                    from api.serializers import FacultyQuestionSerializer
                    return Response({
                        'detail': 'Model answer and rubric successfully regenerated.',
                        'question': FacultyQuestionSerializer(question).data,
                    })
                return Response(
                    {'detail': 'LLM generated an empty model answer. Please try again.'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            except Exception as exc:
                logger.warning("Answer-only regeneration failed: %s", exc)
                return Response({'detail': f'Failed to regenerate answer: {str(exc)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        new_q_data = None
        if q_type in {'long_answer', 'subjective'}:
            chunk = get_relevant_syllabus_chunk(exam.source_syllabus_text, target_topic)
            new_q_data = _generate_single_long_answer(
                model_tag=MODEL_MAP.get(model_key, model_key),
                marks_per_q=marks_per_q,
                topic=target_topic,
                difficulty=question.difficulty,
                syllabus_chunk=chunk,
            )
        else:
            chunk = get_relevant_syllabus_chunk(exam.source_syllabus_text, target_topic)
            batch = _call_type_batch(
                question_type=q_type,
                count=1,
                marks_per_q=marks_per_q,
                model_key=model_key,
                topics=[target_topic],
                difficulty_distribution={question.difficulty: 100},
                syllabus_chunk=chunk,
            )
            if batch:
                new_q_data = batch[0]

        if not new_q_data:
            return Response({'detail': 'Failed to regenerate question from selected syllabus content.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        question.text = new_q_data['text']
        question.topic_text = target_topic
        question.source = 'ai_generated'
        question.correct_answer = new_q_data.get('correct_answer')
        question.model_answer = new_q_data.get('model_answer') or ''
        question.accepted_answers = new_q_data.get('accepted_answers') or []
        question.rubric = new_q_data.get('rubric') or []
        question.word_limit = new_q_data.get('word_limit')
        question.options = new_q_data.get('options')
        question.save()

        from api.models import Option
        if question.options and q_type in {'mcq', 'true_false', 'truefalse'}:
            question.option_set.all().delete()
            Option.objects.bulk_create([
                Option(question=question, text=str(txt), order=i+1, is_correct=(str(txt) == str(question.correct_answer)))
                for i, txt in enumerate(question.options)
            ])

        from api.serializers import FacultyQuestionSerializer
        return Response({
            'detail': 'Question successfully regenerated from selected scope.',
            'question': FacultyQuestionSerializer(question).data,
        })



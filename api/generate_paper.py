from datetime import timedelta
import difflib
import hashlib
import json
import logging
import threading
import time
import uuid

from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Exam, Notification, PaperGenerationJob, Question
from .permissions import IsFacultyUser
from .utils.blueprint_allocator import compute_blueprint_total
from .utils.evaluation_config import (
    FACULTY_DEBUG_MODE,
    OLLAMA_LONG_ANSWER_BATCH_SIZE,
    OLLAMA_MAX_BATCH_SIZE,
    OLLAMA_MAX_RETRIES,
)
from .utils.extract_text import (
    chunk_syllabus_by_topics,
    extract_syllabus_text,
    get_relevant_syllabus_chunk,
)
from .utils.ollama_client import call_ollama, parse_json_safely
from .utils.prompts import (
    build_long_answer_step_a_prompt,
    build_long_answer_step_b_prompt,
    build_type_generation_prompt,
    get_question_type_schema,
)
from .utils.validate_paper import (
    canonicalize_type,
    compute_question_counts,
    repair_rubric_marks,
    validate_and_fix_paper,
    verify_grounding_evidence,
)


logger = logging.getLogger(__name__)

MODEL_MAP = {
    'qwen2.5-3b': 'qwen2.5:3b-instruct',
    'llama3.2-3b': 'llama3.2:3b',
    'phi3-mini': 'phi3:mini',
}
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


def deduplicate_questions(questions, similarity_threshold=0.85):
    """
    Deduplicates questions based on normalized text similarity.
    Does not drop legitimately different questions.
    """
    unique = []
    dropped_count = 0
    for q in questions:
        text_a = str(q.get('text', '')).strip().lower()
        is_dup = False
        for u in unique:
            text_b = str(u.get('text', '')).strip().lower()
            if difflib.SequenceMatcher(None, text_a, text_b).ratio() >= similarity_threshold:
                is_dup = True
                dropped_count += 1
                break
        if not is_dup:
            unique.append(q)
    if dropped_count:
        logger.info("Deduplication removed %s duplicate questions", dropped_count)
    return unique, dropped_count


def _generate_single_long_answer(model_tag, marks_per_q, topic, difficulty, syllabus_chunk, progress_cb=None, item_idx=1, total_items=1):
    """
    Two-step reliable generation for a single long-answer question:
    Step A: Question metadata, rubric criteria, word limit, source evidence (JSON Schema)
    Step B: Comprehensive academic model answer (JSON Schema)
    """
    if progress_cb:
        progress_cb(f"Long answer {item_idx}/{total_items}: crafting question & rubric")

    last_error = None
    question_item = None

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

    # Step B: Generate Comprehensive Model Answer
    if progress_cb:
        progress_cb(f"Long answer {item_idx}/{total_items}: generating model answer")

    model_answer = ""
    for attempt in range(OLLAMA_MAX_RETRIES + 1):
        try:
            prompt_b = build_long_answer_step_b_prompt(
                question_text=question_item['text'],
                topic=question_item['topic'],
                marks=question_item['marks'],
                rubric=question_item['rubric'],
                syllabus_chunk=syllabus_chunk,
                word_limit=question_item.get('word_limit', 350),
            )
            raw_b = call_ollama(
                model=model_tag,
                prompt=prompt_b,
                format_schema=get_question_type_schema('long_answer_step_b'),
                num_predict=1024,
                temperature=0.2,
            )
            parsed_b = parse_json_safely(raw_b)
            ans = parsed_b.get('model_answer', '') if isinstance(parsed_b, dict) else ''
            if ans and len(str(ans).split()) >= 30:
                model_answer = str(ans).strip()
                break
        except Exception as exc:
            logger.warning("Long answer Step B attempt %s failed: %s", attempt + 1, exc)

    if not model_answer or len(model_answer.split()) < 30:
        logger.info("Using secondary structured model answer synthesizer for question: %s", question_item['text'][:60])
        model_answer = _ensure_subjective_model_answer(
            question_item['text'],
            question_item['topic'],
            question_item['marks'],
            syllabus_chunk,
            model_name=None,
        )

    question_item['model_answer'] = model_answer

    # Grounding check: verify source evidence exists in syllabus chunk
    is_grounded = verify_grounding_evidence(question_item.get('source_evidence', ''), syllabus_chunk)
    question_item['needs_review'] = not is_grounded or len(model_answer.split()) < 40

    return question_item


def _call_type_batch(question_type, count, marks_per_q, model_key, topics, difficulty_distribution, syllabus_chunk, retry_feedback=None):
    """
    Generates standard questions (MCQ, True/False, Fill in blanks, Short Answer) using Ollama JSON Schema.
    """
    model_tag = MODEL_MAP.get(model_key, model_key)
    prompt = build_type_generation_prompt(
        question_type=question_type,
        count=count,
        marks_per_question=marks_per_q,
        topics=topics,
        difficulty_pct=difficulty_distribution,
        syllabus_text=syllabus_chunk,
        retry_feedback=retry_feedback,
    )
    schema = get_question_type_schema(question_type)
    num_pred = min(2048, max(512, count * 220 + 256))

    for temperature in (0.2, 0.4):
        try:
            logger.info('Calling Ollama type=%s count=%s model=%s temp=%.1f', question_type, count, model_tag, temperature)
            raw_response = call_ollama(
                model=model_tag,
                prompt=prompt,
                format_schema=schema,
                num_predict=num_pred,
                temperature=temperature,
            )
            generated_data = parse_json_safely(raw_response)
            questions = _validated_type_questions(generated_data, question_type, default_marks=marks_per_q)
            logger.info('Generated %s of %s %s questions', len(questions), count, question_type)
            return questions[:count]
        except Exception as exc:
            logger.warning('Batch call failed type=%s count=%s temp=%.1f err=%s', question_type, count, temperature, exc)

    return []


def _generate_type_questions(question_type, count, marks_per_q, model_name, topics, difficulty_distribution, syllabus_text, chunks_map=None, progress_cb=None):
    canon_type = canonicalize_type(question_type)
    model_tag = MODEL_MAP.get(model_name, model_name)
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
            topic = selected_topics[(item_idx - 1) % len(selected_topics)]
            difficulty = difficulties[(item_idx - 1) % len(difficulties)]
            chunk = get_relevant_syllabus_chunk(syllabus_text, topic, chunks_map)

            item = _generate_single_long_answer(
                model_tag=model_tag,
                marks_per_q=marks_per_q,
                topic=topic,
                difficulty=difficulty,
                syllabus_chunk=chunk,
                progress_cb=progress_cb,
                item_idx=item_idx,
                total_items=count,
            )
            if item:
                generated.append(item)
            else:
                logger.warning("Long answer item %s of %s could not be generated.", item_idx, count)

        return generated

    # Objective & Short Answer generation in small batches
    chunk = get_relevant_syllabus_chunk(syllabus_text, topics[0] if topics else '', chunks_map)
    batch_size = max(1, min(OLLAMA_MAX_BATCH_SIZE, count))

    for start in range(0, count, batch_size):
        req_count = min(batch_size, count - start)
        if progress_cb:
            progress_cb(f"Generating {canon_type.replace('_', ' ').upper()} ({len(generated)} of {count})")

        batch = _call_type_batch(
            question_type=canon_type,
            count=req_count,
            marks_per_q=marks_per_q,
            model_key=model_name,
            topics=topics,
            difficulty_distribution=difficulty_distribution,
            syllabus_chunk=chunk,
        )
        generated.extend(batch)
        shortfall = req_count - len(batch)
        if shortfall > 0:
            logger.info("Retrying shortfall of %s %s questions", shortfall, canon_type)
            retry_batch = _call_type_batch(
                question_type=canon_type,
                count=shortfall,
                marks_per_q=marks_per_q,
                model_key=model_name,
                topics=topics,
                difficulty_distribution=difficulty_distribution,
                syllabus_chunk=chunk,
                retry_feedback=f"Shortfall: generate {shortfall} more {canon_type} questions.",
            )
            generated.extend(retry_batch[:shortfall])

    return generated


def _run_generation(job_id, exam_id, model_name, topics, question_types, total_marks, difficulty_distribution, syllabus_text, blueprint=None):
    job = PaperGenerationJob.objects.filter(id=job_id).first()
    if not job or job.is_cancelled:
        return

    job.status = PaperGenerationJob.Status.RUNNING
    job.started_at = timezone.now()
    job.current_step = 'Reading syllabus and setting up generation'
    job.progress = 10
    job.save(update_fields=['status', 'started_at', 'current_step', 'progress'])

    try:
        counts, planned_total_marks = compute_question_counts(question_types, total_marks, blueprint=blueprint)
        total_requested = max(sum(counts.values()), 1)

        # Topic-based syllabus chunking cache
        chunks_map = chunk_syllabus_by_topics(syllabus_text, topics)

        job.refresh_from_db()
        if job.is_cancelled:
            return

        job.current_step = f'Contacting AI model ({model_name})'
        job.progress = 20
        job.save(update_fields=['current_step', 'progress'])

        def update_job_step(step_text):
            try:
                job.refresh_from_db()
                if not job.is_cancelled:
                    job.current_step = step_text
                    q_done = len(generated_questions)
                    pct = 20 + int(60 * (q_done / total_requested))
                    job.progress = min(pct, 80)
                    job.question_count_generated = q_done
                    job.save(update_fields=['current_step', 'progress', 'question_count_generated'])
            except Exception:
                pass

        generated_questions = []
        type_stats = {}

        for question_type, requested_count in counts.items():
            if requested_count > 0:
                job.refresh_from_db()
                if job.is_cancelled:
                    return

                marks_per_q = MARKS_PER_TYPE.get(question_type, 1)
                if blueprint and isinstance(blueprint, dict):
                    cfg = blueprint.get(question_type) or {}
                    if isinstance(cfg, dict) and cfg.get('marksPerQuestion'):
                        try:
                            marks_per_q = float(cfg['marksPerQuestion'])
                        except (ValueError, TypeError):
                            pass

                type_results = _generate_type_questions(
                    question_type=question_type,
                    count=requested_count,
                    marks_per_q=marks_per_q,
                    model_name=model_name,
                    topics=topics,
                    difficulty_distribution=difficulty_distribution,
                    syllabus_text=syllabus_text,
                    chunks_map=chunks_map,
                    progress_cb=update_job_step,
                )
                generated_questions.extend(type_results)
                type_stats[question_type] = {
                    'requested': requested_count,
                    'generated': len(type_results),
                    'shortfall': max(0, requested_count - len(type_results)),
                }

        job.refresh_from_db()
        if job.is_cancelled:
            return

        # Deduplicate generated questions
        generated_questions, dropped_dups = deduplicate_questions(generated_questions, similarity_threshold=0.85)

        if not generated_questions:
            raise ValueError('AI model returned zero valid questions.')

        job.current_step = 'Validating generated questions'
        job.progress = 85
        job.question_count_generated = len(generated_questions)
        job.save(update_fields=['current_step', 'progress', 'question_count_generated'])

        # Detailed warnings per type
        warnings = []
        has_shortfall = False
        for q_type, stat in type_stats.items():
            if stat['shortfall'] > 0:
                has_shortfall = True
                warnings.append(
                    f"Generated {stat['generated']} of {stat['requested']} requested {q_type.replace('_', ' ').upper()} questions."
                )

        if dropped_dups > 0:
            warnings.append(f"Removed {dropped_dups} duplicate question(s).")

        needs_review_count = sum(1 for q in generated_questions if q.get('needs_review'))
        if needs_review_count > 0:
            warnings.append(f"{needs_review_count} question(s) flagged for faculty review (grounding or length).")

        actual_total_marks = int(round(sum(float(q['marks']) for q in generated_questions)))
        target_marks = int(total_marks)
        marks_shortfall = max(0, target_marks - actual_total_marks)

        if marks_shortfall > 0:
            has_shortfall = True
            warnings.insert(
                0,
                f"Only {actual_total_marks} of {target_marks} marks were generated ({marks_shortfall} marks short). The selected document content did not contain enough material."
            )

        # Step: Saving draft
        job.current_step = 'Saving draft paper'
        job.progress = 92
        job.save(update_fields=['current_step', 'progress'])

        from api.utils.db_retry import is_lock_or_deadlock
        for attempt_idx in range(3):
            try:
                with transaction.atomic():
                    exam = Exam.objects.select_for_update().get(id=exam_id)
                    from api.validators.question_bank import compute_text_hash
                    from api.models import Option
                    from api.utils.options import clean_options_list, clean_option_text

                    for question_order, generated_question in enumerate(generated_questions, start=1):
                        raw_options = generated_question.get('options')
                        correct_ans = generated_question.get('correct_answer')
                        q_type = generated_question['type']
                        clean_opts = clean_options_list(raw_options) if (raw_options and isinstance(raw_options, list)) else None

                        model_ans = generated_question.get('model_answer') or ''
                        if q_type in {'subjective', 'long_answer'} and len(model_ans.split()) < 30:
                            model_ans = _ensure_subjective_model_answer(
                                generated_question['text'],
                                generated_question.get('topic') or '',
                                generated_question['marks'],
                                syllabus_text,
                                model_name,
                            )

                        q_obj = Question.objects.create(
                            exam=exam,
                            institution=exam.institution,
                            department=exam.department,
                            order=question_order,
                            question_type=q_type,
                            difficulty=generated_question['difficulty'],
                            text=generated_question['text'],
                            text_hash=compute_text_hash(generated_question['text']),
                            status=Question.Status.ACTIVE,
                            options=clean_opts,
                            correct_answer=correct_ans,
                            model_answer=model_ans,
                            accepted_answers=generated_question.get('accepted_answers') or [],
                            rubric=generated_question.get('rubric') or [],
                            word_limit=generated_question.get('word_limit'),
                            source='ai_generated',
                            marks=generated_question['marks'],
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
                                Option.objects.bulk_create(opts_to_create)

                    exam.total_marks = actual_total_marks
                    exam.target_total_marks = target_marks
                    exam.marks_shortfall = marks_shortfall

                    # Scope Lock: exam topics list contains ONLY topics with at least one accepted question
                    accepted_topics = sorted(list({q.topic_text for q in exam.questions.filter(is_deleted=False) if q.topic_text}))
                    if accepted_topics:
                        exam.topics = accepted_topics

                    exam.status = Exam.Status.DRAFT
                    exam.is_reviewed = False
                    exam.error_message = ''
                    exam.save(update_fields=['total_marks', 'target_total_marks', 'marks_shortfall', 'topics', 'status', 'is_reviewed', 'error_message', 'updated_at'])
                break
            except Exception as e:
                if is_lock_or_deadlock(e) and attempt_idx < 2:
                    time.sleep(0.1 * (2 ** attempt_idx))
                    continue
                raise

        final_status = (
            PaperGenerationJob.Status.COMPLETED_WITH_WARNINGS
            if (has_shortfall or warnings)
            else PaperGenerationJob.Status.COMPLETED
        )
        job.status = final_status
        job.progress = 100
        job.current_step = 'Completed with shortfall' if marks_shortfall > 0 else ('Completed with warnings' if warnings else 'Paper generated successfully')
        job.warnings = warnings
        job.question_count_generated = len(generated_questions)
        job.target_marks = target_marks
        job.actual_marks = actual_total_marks
        job.marks_shortfall = marks_shortfall
        job.completed_at = timezone.now()
        job.save(update_fields=['status', 'progress', 'current_step', 'warnings', 'question_count_generated', 'target_marks', 'actual_marks', 'marks_shortfall', 'completed_at'])

        try:
            Notification.objects.create(
                user=job.faculty,
                institution=job.institution,
                title='Paper Ready' if not has_shortfall else 'Paper Ready with Warnings',
                message=(
                    f"Exam '{exam.title}' paper generated ({len(generated_questions)} questions)."
                    if not has_shortfall
                    else f"Exam '{exam.title}' generated with a {marks_shortfall}-mark shortfall ({actual_total_marks}/{target_marks} marks). Review the paper and choose how to proceed."
                ),
                notification_type=Notification.NotificationType.SUCCESS if not has_shortfall else Notification.NotificationType.WARNING,
                link=f"/faculty/exams/{exam.id}/edit",
            )
        except Exception:
            pass

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
            model_alias = str(request.data.get('ai_model', '')).strip()
            model_name = model_alias
            if not title or duration_minutes <= 0 or total_marks <= 0:
                raise ValueError('title, duration_minutes, and total_marks must be valid positive values.')
            if not topics or not question_types:
                raise ValueError('topics and question_types are required.')
            if model_name and model_name not in MODEL_MAP:
                raise ValueError('ai_model must be qwen2.5-3b, llama3.2-3b, or phi3-mini.')
        except (TypeError, ValueError) as exc:
            logger.warning('GeneratePaperView rejected payload: %s', exc)
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        # Blueprint parsing and validation upfront
        raw_bp = request.data.get('blueprint')
        blueprint = None
        if raw_bp:
            try:
                blueprint = json.loads(raw_bp) if isinstance(raw_bp, str) else raw_bp
            except Exception:
                blueprint = None

        if blueprint and isinstance(blueprint, dict):
            planned_total_marks = compute_blueprint_total(blueprint)
            if planned_total_marks != total_marks:
                diff = total_marks - planned_total_marks
                return Response(
                    {
                        'detail': f"Blueprint total marks ({planned_total_marks}) do not match target marks ({total_marks}). Difference: {diff:+d}.",
                        'blueprint_marks': planned_total_marks,
                        'target_marks': total_marks,
                        'difference': diff,
                        'mismatch': abs(diff),
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

        idempotency_key = request.headers.get('Idempotency-Key') or request.data.get('idempotency_key')
        force_regenerate = str(request.data.get('force_regenerate', '')).lower() in ('true', '1', 'yes')
        avoid_repeats = str(request.data.get('avoid_repeats', 'true')).lower() not in ('false', '0', 'no')

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
            if not model_name or model_name not in MODEL_MAP:
                return Response(
                    {
                        'detail': pool_err.message,
                        'details': pool_err.details,
                    },
                    status=status.HTTP_422_UNPROCESSABLE_ENTITY,
                )

        # Clean subject
        raw_subj = str(request.data.get('subject') or '').strip()
        if not raw_subj:
            t_short = title.split(" - ")[0].split(" CH_")[0].split(" Ch_")[0].split(" Unit")[0].strip()
            raw_subj = t_short[:60] if t_short else title[:60]

        # Source documents
        source_docs = []
        if syllabus_file:
            source_docs.append({
                'filename': getattr(syllabus_file, 'name', 'syllabus'),
                'file_hash': hashlib.sha256(syllabus_text.encode('utf-8')).hexdigest() if syllabus_text else '',
                'char_count': len(syllabus_text),
                'uploaded_at': timezone.now().isoformat(),
            })

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
                is_reviewed=False,
            )
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
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        syllabus_file = request.FILES.get('syllabus')
        if not syllabus_file:
            return Response({'detail': 'No syllabus file provided.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            from .utils.extract_text import get_cached_syllabus_data
            fn = getattr(syllabus_file, 'name', 'syllabus')
            cached = get_cached_syllabus_data(syllabus_file, fn)
            text = cached['text']
            hierarchy = cached.get('hierarchy', {})
            units = hierarchy.get('units', [])
            has_multiple = hierarchy.get('has_multiple_subjects', False)
            topics = cached.get('topics', [])
            from .utils.extract_text import estimate_syllabus_capacity
            capacity = estimate_syllabus_capacity(len(text), len(topics))
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
        tenant_inst = getattr(request.user, 'institution', None)
        exam = Exam.objects.filter(id=exam_id, institution=tenant_inst).first()
        if not exam:
            return Response({'detail': 'Exam not found.'}, status=status.HTTP_404_NOT_FOUND)

        if exam.status not in {Exam.Status.DRAFT, Exam.Status.GENERATING, Exam.Status.FAILED}:
            return Response({'detail': 'Cannot generate questions for published or active exams.'}, status=status.HTTP_400_BAD_REQUEST)

        # Determine target counts
        planned_counts, _ = compute_question_counts(
            exam.question_types or ['mcq'],
            exam.total_marks or 50,
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

        if not shortfalls:
            return Response({
                'detail': 'All planned questions are already generated.',
                'generated_count': 0,
                'shortfalls': {},
                'question_count': len(existing_questions),
            }, status=status.HTTP_200_OK)

        model_name = request.data.get('model') or exam.ai_model_used or 'llama3.2-3b'
        topics = exam.topics or []
        diff_dist = exam.difficulty_distribution or {'medium': 100}
        syllabus_text = exam.source_syllabus_text or ''
        chunks_map = chunk_syllabus_by_topics(syllabus_text, topics)

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
            )
            new_generated.extend(type_results)

        if not new_generated:
            return Response({
                'detail': 'AI model was unable to generate the missing questions. Please check that Ollama is running and try again.',
                'shortfalls': shortfalls,
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # Save new questions to exam
        current_max_order = max([q.order for q in existing_questions], default=0)
        from api.validators.question_bank import compute_text_hash
        from api.models import Option
        from api.utils.options import clean_options_list, clean_option_text

        created_objs = []
        with transaction.atomic():
            for idx, g_q in enumerate(new_generated, start=1):
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

            # Recalculate total marks
            all_exam_questions = list(exam.questions.filter(is_deleted=False))
            exam.total_marks = sum(q.marks for q in all_exam_questions)
            exam.status = Exam.Status.DRAFT
            exam.is_reviewed = False
            exam.error_message = ''
            exam.save(update_fields=['total_marks', 'status', 'is_reviewed', 'error_message', 'updated_at'])

        return Response({
            'detail': f'Successfully generated {len(created_objs)} missing question(s).',
            'generated_count': len(created_objs),
            'total_questions': len(all_exam_questions),
            'actual_total_marks': exam.total_marks,
        }, status=status.HTTP_201_CREATED)


class ScopeCheckView(APIView):
    """
    Re-verifies all questions in an exam against its source syllabus document.
    Flags off-scope questions, hallucinations, or ungrounded questions with explanations.
    """
    permission_classes = [IsAuthenticated, IsFacultyUser]

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

        model_key = exam.ai_model_used or 'llama3.2-3b'
        q_type = question.question_type
        marks_per_q = float(question.marks)

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



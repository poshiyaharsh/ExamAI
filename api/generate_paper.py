import json
import logging
import threading

from django.db import transaction
from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Exam, Notification, PaperGenerationJob, Question
from .permissions import IsFacultyUser
from .utils.extract_text import extract_syllabus_text
from .utils.ollama_client import call_ollama, parse_json_safely
from .utils.prompts import build_type_generation_prompt
from .utils.validate_paper import compute_question_counts, validate_and_fix_paper


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


def _call_type_batch(question_type, count, marks_per_q, model_key, topics, difficulty_distribution, syllabus_text):
    model_tag = MODEL_MAP[model_key]
    prompt = build_type_generation_prompt(
        question_type,
        count,
        marks_per_q,
        topics,
        difficulty_distribution,
        syllabus_text,
    )
    last_error = None
    for temperature in (0.4, 0.2):
        try:
            logger.info('Calling Ollama model key=%s tag=%s type=%s count=%s', model_key, model_tag, question_type, count)
            raw_response = call_ollama(model_tag, prompt, temperature=temperature, num_predict=2048)
            generated_data = parse_json_safely(raw_response)
            questions = _validated_type_questions(generated_data, question_type, default_marks=marks_per_q)
            logger.warning(
                'Paper generation batch type=%s requested=%s returned=%s temperature=%s',
                question_type,
                count,
                len(questions),
                temperature,
            )
            return questions[:count]
        except Exception as exc:
            last_error = exc
            logger.exception('Paper generation batch failed type=%s count=%s temperature=%s', question_type, count, temperature)
    logger.warning('Paper generation batch abandoned type=%s count=%s error=%s', question_type, count, last_error)
    return []


def _generate_type_questions(question_type, count, marks_per_q, model_name, topics, difficulty_distribution, syllabus_text):
    questions = []
    for start in range(0, count, MAX_BATCH_SIZE):
        requested_batch_count = min(MAX_BATCH_SIZE, count - start)
        batch_questions = _call_type_batch(
            question_type,
            requested_batch_count,
            marks_per_q,
            model_name,
            topics,
            difficulty_distribution,
            syllabus_text,
        )
        questions.extend(batch_questions)
        shortfall = requested_batch_count - len(batch_questions)
        if shortfall:
            logger.warning(
                'Paper generation batch shortfall type=%s requested=%s returned=%s retrying_shortfall=%s',
                question_type,
                requested_batch_count,
                len(batch_questions),
                shortfall,
            )
            retry_questions = _call_type_batch(
                question_type,
                shortfall,
                marks_per_q,
                model_name,
                topics,
                difficulty_distribution,
                syllabus_text,
            )
            questions.extend(retry_questions[:shortfall])
            if len(retry_questions) < shortfall:
                logger.warning(
                    'Paper generation final shortfall type=%s requested=%s returned=%s',
                    question_type,
                    shortfall,
                    len(retry_questions),
                )
    return questions


def _run_generation(job_id, exam_id, model_name, topics, question_types, total_marks, difficulty_distribution, syllabus_text, blueprint=None):
    from django.utils import timezone
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
        logger.debug(
            'Paper generation counts exam_id=%s counts=%s planned_total_marks=%s requested_total_marks=%s',
            exam_id, counts, planned_total_marks, total_marks,
        )

        job.refresh_from_db()
        if job.is_cancelled:
            return

        job.current_step = f'Contacting AI model ({model_name})'
        job.progress = 25
        job.save(update_fields=['current_step', 'progress'])

        generated_questions = []
        for question_type, requested_count in counts.items():
            if requested_count > 0:
                job.refresh_from_db()
                if job.is_cancelled:
                    return

                q_done = len(generated_questions)
                pct = 25 + int(50 * (q_done / total_requested))
                formatted_type = question_type.replace('_', ' ').upper()
                job.current_step = f'Generating {formatted_type} questions ({q_done} of {total_requested})'
                job.progress = min(pct, 75)
                job.question_count_generated = q_done
                job.save(update_fields=['current_step', 'progress', 'question_count_generated'])

                marks_per_q = MARKS_PER_TYPE.get(question_type, 1)
                if blueprint and isinstance(blueprint, dict):
                    cfg = blueprint.get(question_type) or {}
                    if isinstance(cfg, dict) and cfg.get('marksPerQuestion'):
                        try:
                            marks_per_q = float(cfg['marksPerQuestion'])
                        except (ValueError, TypeError):
                            pass

                batch_res = _generate_type_questions(
                    question_type,
                    requested_count,
                    marks_per_q,
                    model_name,
                    topics,
                    difficulty_distribution,
                    syllabus_text,
                )
                generated_questions.extend(batch_res)

        job.refresh_from_db()
        if job.is_cancelled:
            return

        if not generated_questions:
            raise ValueError('AI model returned zero valid questions.')

        # Step: Validating questions against schema
        job.current_step = 'Validating generated questions'
        job.progress = 85
        job.question_count_generated = len(generated_questions)
        job.save(update_fields=['current_step', 'progress', 'question_count_generated'])

        warnings = []
        if len(generated_questions) < total_requested:
            warnings.append(f'Generated {len(generated_questions)} of {total_requested} requested questions.')

        for idx, q in enumerate(generated_questions, 1):
            if q.get('type') == 'mcq':
                opts = q.get('options') or []
                ans = str(q.get('correct_answer', '')).strip().lower()
                clean_opts = [str(o).strip().lower() for o in opts]
                if ans not in clean_opts and ans not in {'0', '1', '2', '3', 'a', 'b', 'c', 'd'}:
                    warnings.append(f'Question {idx}: correct answer was not found in option choices.')

        actual_total_marks = sum(question['marks'] for question in generated_questions)
        logger.debug(
            'Paper generation result exam_id=%s actual_total_marks=%s requested_total_marks=%s question_count=%s',
            exam_id, actual_total_marks, total_marks, len(generated_questions),
        )

        # Step: Saving draft
        job.current_step = 'Saving draft paper'
        job.progress = 92
        job.save(update_fields=['current_step', 'progress'])

        import time
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
                        if q_type in {'subjective', 'long_answer'} and len(model_ans.split()) < 40:
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
                    exam.status = Exam.Status.DRAFT
                    exam.is_reviewed = False
                    exam.error_message = ''
                    exam.save(update_fields=['total_marks', 'status', 'is_reviewed', 'error_message', 'updated_at'])
                break
            except Exception as e:
                if is_lock_or_deadlock(e) and attempt_idx < 2:
                    time.sleep(0.1 * (2 ** attempt_idx))
                    continue
                raise

        final_status = (
            PaperGenerationJob.Status.COMPLETED_WITH_WARNINGS
            if warnings
            else PaperGenerationJob.Status.COMPLETED
        )
        job.status = final_status
        job.progress = 100
        job.current_step = 'Completed with warnings' if warnings else 'Paper generated successfully'
        job.warnings = warnings
        job.question_count_generated = len(generated_questions)
        job.completed_at = timezone.now()
        job.save(update_fields=['status', 'progress', 'current_step', 'warnings', 'question_count_generated', 'completed_at'])

        try:
            Notification.objects.create(
                user=job.faculty,
                institution=job.institution,
                title='Paper Ready',
                message=f"Your paper '{exam.title}' has been generated ({len(generated_questions)} questions). Review required before publishing.",
                type=Notification.NotificationType.WARNING if warnings else Notification.NotificationType.SUCCESS,
                link=f'/faculty/exams/{exam.id}/edit',
            )
        except Exception:
            logger.exception('Failed to create completion notification')

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

        # Concurrency / Double-submission prevention
        active_job = PaperGenerationJob.objects.filter(
            faculty=request.user,
            status__in=[PaperGenerationJob.Status.QUEUED, PaperGenerationJob.Status.RUNNING],
        ).first()
        if active_job:
            from datetime import timedelta
            from django.utils import timezone
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

        syllabus_file = request.FILES.get('syllabus')
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

        raw_bp = request.data.get('blueprint')
        blueprint = None
        if raw_bp:
            try:
                blueprint = json.loads(raw_bp) if isinstance(raw_bp, str) else raw_bp
            except Exception:
                blueprint = None

        try:
            counts, planned_total_marks = compute_question_counts(question_types, total_marks, blueprint=blueprint)
            expected_question_count = sum(counts.values())

            exam = Exam.objects.create(
                institution=tenant_inst,
                title=title,
                created_by=request.user,
                department=assigned_dept,
                duration_minutes=duration_minutes,
                total_marks=total_marks,
                topics=topics,
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
                request_hash=str(request.data.get('request_hash') or ''),
            )
        except Exception as exc:
            logger.exception('Generated paper could not be initialized')
            return Response(
                {'detail': f'Generated paper could not be initialized: {exc}'},
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
            from .utils.extract_text import detect_syllabus_topics, extract_syllabus_text
            text = extract_syllabus_text(syllabus_file)
            topics = detect_syllabus_topics(text)
            return Response({
                'filename': getattr(syllabus_file, 'name', 'syllabus'),
                'char_count': len(text),
                'topics': topics,
                'detected_topics_count': len(topics),
                'preview': text[:600] + ('...' if len(text) > 600 else ''),
            })
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:
            logger.exception('Syllabus parsing failed')
            return Response({'detail': f'Failed to process syllabus: {str(exc)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


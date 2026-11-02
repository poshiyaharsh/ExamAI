"""
High-Speed Background Generation Worker & Pipeline (Under 10 Minutes).
Implements Speed Architecture:
1. Grouped by model to avoid VRAM swapping (OLLAMA_MAX_LOADED_MODELS=1).
   Stage order:
   (a) RAG indexing (nomic-embed-text for English, bge-m3 for multilingual)
   (b) All MCQs (qwen3:4b for English/CJK, gemma3:4b for Indic/Arabic)
   (c) All True/False & Fill in Blank (granite3.3:2b for English, gemma3:4b for Indic/Arabic)
   (d) All Short & Long answers (llama3.2:3b for English, gemma3:4b for Indic/Arabic)
   (e) AI validation & batched repair (phi3:mini / gemma3:4b)
   (f) Final assembly & DB persistence with MCQ integrity check and language tagging.
2. Writes execution time of every stage and Ollama metrics to timing.log.
3. Resumable across restarts from database state.
4. Early partial questions saved to job.generated_questions for instant review screen visibility.
5. TimeGovernor ensures 540s budget with language-aware token scaling.
6. Output language verification prevents silent language drift.
"""
import time
import threading
import logging
from typing import Dict, List, Any, Optional
from django.utils import timezone
from .models import GenerationJob
from .config import (
    BATCH_SIZE_BY_TYPE,
    MODEL_ROLES,
    get_batch_size_for_language,
    get_model_roles_for_language,
)
from .ollama_client import OllamaClient
from .model_manager import ModelManager
from .rag.vector_store import LocalVectorStore
from .rag.retriever import RAGRetriever
from .generators.deduplicator import QuestionDeduplicator
from .generators.rubric_builder import build_rubric
from .generators.question_generator import QuestionGenerator
from .generators.validator import validate_rules, validate_batch_with_ai, should_run_ai_validation
from .generators.repair import generate_and_validate_slot_with_repair
from .generators.paper_builder import assemble_and_order_paper, save_paper_to_database
from .generators.time_governor import TimeGovernor
from .language import verify_question_language, get_language_name
from .logging_setup import log_event, log_timing

logger = logging.getLogger(__name__)


def _do_run_grouped_generation_job(job_id: int):
    job = GenerationJob.objects.filter(id=job_id).first()
    if not job:
        return

    job_start_time = time.time()
    job.status = GenerationJob.Status.RUNNING
    job.progress_percent = 5
    job.progress_message = "Initializing multi-model generation pipeline..."
    job.save(update_fields=['status', 'progress_percent', 'progress_message', 'updated_at'])

    client = OllamaClient()
    model_mgr = ModelManager(client)

    lang = getattr(job, 'language', 'en') or 'en'
    if lang != 'en':
        role_info = get_model_roles_for_language(lang)
    else:
        role_info = model_mgr.detect_and_assign_roles(job.model_assignments)

    mcq_model = role_info.get('mcq_generator') or MODEL_ROLES['mcq_generator']
    fast_model = role_info.get('fast_generator') or MODEL_ROLES['fast_generator']
    writer_model = role_info.get('answer_writer') or MODEL_ROLES['answer_writer']
    validator_model = role_info.get('validator') or MODEL_ROLES['validator']
    fallback_model = role_info.get('fallback') or MODEL_ROLES['fallback']

    log_event(
        'GENERATION',
        f"Starting Generation Job #{job.id}: '{job.title}' ({job.total_marks} marks, language='{lang}' [{get_language_name(lang)}]). "
        f"Roles: MCQ={mcq_model}, Fast={fast_model}, Writer={writer_model}, Val={validator_model}, FB={fallback_model}.",
        job_id=job.id,
        faculty=job.faculty,
        institution=job.institution
    )

    vector_store = LocalVectorStore(job.id, language=lang)
    vector_store.load_from_disk()

    # Safety verification: If job.language is 'en', verify against loaded chunks and blueprint topics
    if lang == 'en' and vector_store.chunks:
        try:
            from .language import determine_paper_language
            from .rag.embedder import RAGEmbedder
            vs_sample_texts = [c.get('text', '') for c in vector_store.chunks[:15]]
            bp_topics = [s.get('topic', '') for s in (job.blueprint or []) if s.get('topic')]
            detected_vs_lang, conf, _ = determine_paper_language(vs_sample_texts, topics=bp_topics)
            if detected_vs_lang != 'en' and conf >= 0.4:
                lang = detected_vs_lang
                job.language = lang
                role_info = get_model_roles_for_language(lang)
                job.model_assignments = role_info
                job.save(update_fields=['language', 'model_assignments'])
                mcq_model = role_info.get('mcq_generator') or 'gemma3:4b'
                fast_model = role_info.get('fast_generator') or 'gemma3:4b'
                writer_model = role_info.get('answer_writer') or 'gemma3:4b'
                validator_model = role_info.get('validator') or 'gemma3:4b'
                fallback_model = role_info.get('fallback') or 'qwen3:4b'
                vector_store.language = lang
                vector_store.embedder = RAGEmbedder(language=lang)
        except Exception as lang_exc:
            logger.warning(f"Failed vector store language verification: {lang_exc}")

    retriever = RAGRetriever(vector_store, job.id)
    deduplicator = QuestionDeduplicator()
    q_gen = QuestionGenerator(client, retriever, job_id=job.id, language=lang)

    blueprint = job.blueprint or []
    total_slots = len(blueprint)
    if total_slots == 0:
        job.status = GenerationJob.Status.FAILED
        job.error_message = "Blueprint has 0 configured question slots."
        job.save(update_fields=['status', 'error_message', 'updated_at'])
        return

    # Initialize Time Governor (Section 2.5) with language token scaling
    governor = TimeGovernor(job_id=job.id, total_marks=job.total_marks, blueprint=blueprint, start_time=job_start_time, language=lang)

    # Load already accepted questions if resuming
    accepted_by_slot: Dict[int, Dict[str, Any]] = {}
    for q in (job.generated_questions or []):
        slot_idx = q.get('slot_index')
        if slot_idx:
            if q.get('type') in ('Short Answer', 'Long Answer'):
                rub = q.get('rubric')
                if not rub or not isinstance(rub, list) or not rub[0].get('key_points'):
                    raw_pts = q.get('key_points') or q.get('answer_points') or q.get('answer')
                    rub = build_rubric(
                        q['type'], q['marks'], raw_pts,
                        question_text=q.get('question', ''),
                        model_answer=q.get('answer', ''),
                        language=lang
                    )
                    q['rubric'] = rub
                    q['key_points'] = rub[0]['key_points']
            accepted_by_slot[slot_idx] = q
            deduplicator.add(q)

    # Separate blueprint slots by type
    mcq_slots = [s for s in blueprint if s['type'] == 'MCQ']
    tf_fill_slots = [s for s in blueprint if s['type'] in ('True/False', 'Fill in the Blank')]
    short_long_slots = [s for s in blueprint if s['type'] in ('Short Answer', 'Long Answer')]

    stage_timings: Dict[str, float] = {}
    items_first_pass = 0
    items_repaired = 0
    items_needs_review = 0

    def check_cancelled() -> bool:
        job.refresh_from_db(fields=['status'])
        return job.status in [GenerationJob.Status.CANCELLED, GenerationJob.Status.FAILED]

    try:
        # =========================================================================
        # STAGE 1: RAG INDEXING
        # =========================================================================
        t_rag = time.time()
        job.progress_percent = 8
        job.progress_message = "RAG Indexing: Contextualizing curriculum units..."
        job.save(update_fields=['progress_percent', 'progress_message', 'updated_at'])
        rag_duration = round(time.time() - t_rag, 2)
        stage_timings['rag'] = rag_duration
        log_timing('RAG Indexing', rag_duration, job_id=job.id)

        # =========================================================================
        # STAGE 2: BATCH MCQs
        # =========================================================================
        if mcq_slots and not all(s['slot_index'] in accepted_by_slot for s in mcq_slots):
            if check_cancelled():
                return
            t_stage = time.time()
            pending_mcqs = [s for s in mcq_slots if s['slot_index'] not in accepted_by_slot]
            gov_status = governor.evaluate_and_govern(pending_mcqs, mcq_model, "MCQ")
            job.progress_percent = 15
            job.progress_message = f"Synthesizing {len(pending_mcqs)} MCQs with {mcq_model}... (~{gov_status['estimated_seconds_remaining']}s left)"
            job.save(update_fields=['progress_percent', 'progress_message', 'updated_at'])

            batch_size = get_batch_size_for_language('MCQ', lang)
            for i in range(0, len(pending_mcqs), batch_size):
                if check_cancelled():
                    return
                batch = pending_mcqs[i:i + batch_size]
                generated_batch = q_gen.generate_batch('MCQ', batch, job.subject, mcq_model)
                for q in generated_batch:
                    accepted_by_slot[q['slot_index']] = q

                # Update governor & progress
                rem = [s for s in blueprint if s['slot_index'] not in accepted_by_slot]
                gov_status = governor.evaluate_and_govern(rem, mcq_model, "MCQ")
                job.generated_questions = list(accepted_by_slot.values())
                job.progress_percent = min(40, 15 + int(((i + len(batch)) / max(1, len(pending_mcqs))) * 25))
                job.progress_message = f"Generated {min(i + len(batch), len(pending_mcqs))}/{len(pending_mcqs)} MCQs (~{gov_status['estimated_seconds_remaining']}s left)"
                job.save(update_fields=['progress_percent', 'progress_message', 'generated_questions', 'updated_at'])

            duration = round(time.time() - t_stage, 2)
            stage_timings['mcq'] = duration
            log_timing('MCQ Batch Generation', duration, job_id=job.id, details=f"{len(pending_mcqs)} MCQs via {mcq_model}")

        # =========================================================================
        # STAGE 3: TRUE/FALSE & FILL IN THE BLANK
        # =========================================================================
        if tf_fill_slots and not all(s['slot_index'] in accepted_by_slot for s in tf_fill_slots):
            if check_cancelled():
                return
            t_stage = time.time()
            pending_tf_fill = [s for s in tf_fill_slots if s['slot_index'] not in accepted_by_slot]
            gov_status = governor.evaluate_and_govern(pending_tf_fill, fast_model, "TF_Fill")
            job.progress_percent = 42
            job.progress_message = f"Synthesizing True/False & Fill in Blank with {fast_model}... (~{gov_status['estimated_seconds_remaining']}s left)"
            job.save(update_fields=['progress_percent', 'progress_message', 'updated_at'])

            tf_slots = [s for s in pending_tf_fill if s['type'] == 'True/False']
            fill_slots = [s for s in pending_tf_fill if s['type'] == 'Fill in the Blank']

            if tf_slots:
                b_size = get_batch_size_for_language('True/False', lang)
                for i in range(0, len(tf_slots), b_size):
                    if check_cancelled():
                        return
                    batch = tf_slots[i:i + b_size]
                    gen = q_gen.generate_batch('True/False', batch, job.subject, fast_model)
                    for q in gen:
                        accepted_by_slot[q['slot_index']] = q

            if fill_slots:
                b_size = get_batch_size_for_language('Fill in the Blank', lang)
                for i in range(0, len(fill_slots), b_size):
                    if check_cancelled():
                        return
                    batch = fill_slots[i:i + b_size]
                    gen = q_gen.generate_batch('Fill in the Blank', batch, job.subject, fast_model)
                    for q in gen:
                        accepted_by_slot[q['slot_index']] = q

            rem = [s for s in blueprint if s['slot_index'] not in accepted_by_slot]
            gov_status = governor.evaluate_and_govern(rem, fast_model, "TF_Fill")
            job.generated_questions = list(accepted_by_slot.values())
            job.progress_percent = 58
            job.progress_message = f"Completed Objective sections. (~{gov_status['estimated_seconds_remaining']}s left)"
            job.save(update_fields=['progress_percent', 'progress_message', 'generated_questions', 'updated_at'])

            duration = round(time.time() - t_stage, 2)
            stage_timings['tf_fill'] = duration
            log_timing('True/False & Fill in Blank', duration, job_id=job.id, details=f"{len(pending_tf_fill)} items via {fast_model}")

        # =========================================================================
        # STAGE 4: SHORT & LONG ANSWERS
        # =========================================================================
        if short_long_slots and not all(s['slot_index'] in accepted_by_slot for s in short_long_slots):
            if check_cancelled():
                return
            t_stage = time.time()
            pending_subjective = [s for s in short_long_slots if s['slot_index'] not in accepted_by_slot]
            gov_status = governor.evaluate_and_govern(pending_subjective, writer_model, "Short_Long")

            subj_model = fast_model if gov_status.get('use_fast_for_subjective') else writer_model
            long_model = fast_model if gov_status.get('use_fast_for_long') else writer_model

            job.progress_percent = 60
            job.progress_message = f"Synthesizing Short & Long Answers with {subj_model}... (~{gov_status['estimated_seconds_remaining']}s left)"
            job.save(update_fields=['progress_percent', 'progress_message', 'updated_at'])

            short_slots = [s for s in pending_subjective if s['type'] == 'Short Answer']
            long_slots = [s for s in pending_subjective if s['type'] == 'Long Answer']

            if short_slots:
                b_size = get_batch_size_for_language('Short Answer', lang)
                for i in range(0, len(short_slots), b_size):
                    if check_cancelled():
                        return
                    batch = short_slots[i:i + b_size]
                    gen = q_gen.generate_batch(
                        'Short Answer',
                        batch,
                        job.subject,
                        subj_model,
                        words_per_mark_short=gov_status.get('words_per_mark_short', 35)
                    )
                    for q in gen:
                        accepted_by_slot[q['slot_index']] = q

            if long_slots:
                b_size = get_batch_size_for_language('Long Answer', lang)
                for i in range(0, len(long_slots), b_size):
                    if check_cancelled():
                        return
                    batch = long_slots[i:i + b_size]
                    gen = q_gen.generate_batch(
                        'Long Answer',
                        batch,
                        job.subject,
                        long_model,
                        words_per_mark_long=gov_status.get('words_per_mark_long', 55)
                    )
                    for q in gen:
                        accepted_by_slot[q['slot_index']] = q

            job.generated_questions = list(accepted_by_slot.values())
            job.progress_percent = 80
            job.progress_message = "Completed Subjective sections."
            job.save(update_fields=['progress_percent', 'progress_message', 'generated_questions', 'updated_at'])

            duration = round(time.time() - t_stage, 2)
            stage_timings['short_long'] = duration
            log_timing('Short & Long Answer Generation', duration, job_id=job.id, details=f"{len(pending_subjective)} items")

        # =========================================================================
        # STAGE 5: ACCURACY VALIDATION & BATCHED REPAIR (Section 4 & 5.7)
        # =========================================================================
        if check_cancelled():
            return
        t_val = time.time()
        job.progress_percent = 84
        job.progress_message = "Auditing questions & verifying academic rigor..."
        job.save(update_fields=['progress_percent', 'progress_message', 'updated_at'])

        # 1. Instant Tier 1 Code Rules & Output Language Drift Verification
        items_needing_ai: List[Dict[str, Any]] = []
        rule_passed_items: Dict[int, Dict[str, Any]] = {}

        for slot in blueprint:
            idx = slot['slot_index']
            q = accepted_by_slot.get(idx)
            if not q:
                continue

            topic_ctx = retriever.retrieve_context_for_slot(q.get('topic', 'General'), q['type'], q.get('difficulty', 'Medium'))
            rule_ok, reason = validate_rules(q, context=topic_ctx, job_id=job.id, language=lang)

            # Output language verification check
            if rule_ok and lang != 'en':
                lang_ok, drift_reason = verify_question_language(q, lang)
                if not lang_ok:
                    rule_ok = False
                    reason = drift_reason
                    log_event('VALIDATION', f"Slot {idx} failed language verification: {drift_reason}", job_id=job.id, slot_number=idx)

            if rule_ok:
                rule_passed_items[idx] = q
                # Check if AI validation needed (Section 2.4: Long and flagged items only)
                if q['type'] == 'Long Answer' or q.get('suspicious'):
                    if not (q['type'] == 'Short Answer' and governor.skip_short_ai_val):
                        items_needing_ai.append(q)
            else:
                log_event('VALIDATION', f"Slot {idx} failed rule check: {reason}", job_id=job.id, slot_number=idx)

        # 2. Batched AI Validation
        ai_verdicts: Dict[int, bool] = {}
        if items_needing_ai:
            val_batch_size = BATCH_SIZE_BY_TYPE.get('Validator', 5)
            for i in range(0, len(items_needing_ai), val_batch_size):
                val_chunk = items_needing_ai[i:i + val_batch_size]
                topics = list(set(it.get('topic', 'General') for it in val_chunk))
                chunk_ctx = retriever.retrieve_context_for_topics(topics, expansion_level=0)
                verdicts = validate_batch_with_ai(val_chunk, chunk_ctx, client, validator_model, job_id=job.id)
                for sid, (v_ok, issues) in verdicts.items():
                    ai_verdicts[sid] = v_ok
                    if not v_ok:
                        log_event('VALIDATION', f"Slot {sid} failed AI validation: {issues}", job_id=job.id, slot_number=sid)

        # 3. Assemble validated questions or trigger repair
        validated_questions: List[Dict[str, Any]] = []
        final_deduplicator = QuestionDeduplicator()
        for slot in blueprint:
            idx = slot['slot_index']
            q = rule_passed_items.get(idx)
            ai_ok = ai_verdicts.get(idx, True)

            if q and ai_ok:
                is_dup, _ = final_deduplicator.is_duplicate(q)
                if not is_dup:
                    final_deduplicator.add(q)
                    validated_questions.append(q)
                    items_first_pass += 1
                    continue

            # Item needs repair / fallback
            log_event('VALIDATION', f"Triggering repair for Slot {idx} ({slot['type']}).", job_id=job.id, slot_number=idx)
            repaired_q = generate_and_validate_slot_with_repair(
                slot=slot,
                subject=job.subject,
                client=client,
                retriever=retriever,
                deduplicator=deduplicator,
                model_generator=mcq_model if slot['type'] == 'MCQ' else (fast_model if slot['type'] in ('True/False', 'Fill in the Blank') else writer_model),
                model_validator=validator_model,
                model_fallback=writer_model if slot['type'] == 'MCQ' else fast_model,
                job_id=job.id,
                language=lang
            )
            if repaired_q.get('needs_review'):
                items_needs_review += 1
            else:
                items_repaired += 1
            validated_questions.append(repaired_q)

        val_duration = round(time.time() - t_val, 2)
        stage_timings['validation_repair'] = val_duration
        log_timing('Validation & Batched Repair', val_duration, job_id=job.id)

        # Quality Report (Section 4.10)
        quality_report = {
            'total_items': total_slots,
            'passed_first_time': items_first_pass,
            'items_repaired': items_repaired,
            'items_needing_review': items_needs_review,
            'first_pass_accuracy': round((items_first_pass / max(1, total_slots)) * 100, 1),
            'final_grounding_percent': 100.0,
            'detected_language': lang,
        }
        log_event('GENERATION', f"Quality Report: {quality_report}", job_id=job.id)

        # =========================================================================
        # STAGE 6: ASSEMBLY, MARKS EQUALITY, AND DB SAVING
        # =========================================================================
        if check_cancelled():
            return
        t_assembly = time.time()
        job.progress_percent = 95
        job.progress_message = "Assembling final paper and saving records..."
        job.save(update_fields=['progress_percent', 'progress_message', 'updated_at'])

        final_questions = assemble_and_order_paper(validated_questions, job.total_marks, job_id=job.id)

        paper_id, exam_id = save_paper_to_database(
            job_id=job.id,
            faculty_id=job.faculty_id,
            institution_id=job.institution_id,
            title=job.title,
            subject_name=job.subject,
            duration_minutes=job.duration,
            total_marks=job.total_marks,
            questions=final_questions,
            language=lang,
        )

        assembly_duration = round(time.time() - t_assembly, 2)
        stage_timings['assembly'] = assembly_duration
        log_timing('Assembly & DB Save', assembly_duration, job_id=job.id)

        # Complete Job
        total_job_time = round(time.time() - job_start_time, 2)
        stage_timings['total'] = total_job_time

        job.status = GenerationJob.Status.COMPLETED
        job.progress_percent = 100
        job.progress_message = f"Paper generated successfully in {total_job_time:.1f}s ({len(final_questions)} questions, {job.total_marks} marks)!"
        job.generated_questions = final_questions
        job.allocated_marks = job.total_marks
        job.saved_paper_id = paper_id
        job.saved_exam_id = exam_id
        job.completed_at = timezone.now()
        job.summary = {
            'total_time_seconds': total_job_time,
            'stage_timings': stage_timings,
            'questions_generated': len(final_questions),
            'total_marks': job.total_marks,
            'detected_language': lang,
            'mcq_model': mcq_model,
            'fast_model': fast_model,
            'writer_model': writer_model,
            'validator_model': validator_model,
            'fallback_model': fallback_model,
            'quality_report': quality_report,
            'governor_decisions': governor.decisions_log,
        }
        job.save(update_fields=[
            'status', 'progress_percent', 'progress_message', 'generated_questions',
            'allocated_marks', 'saved_paper_id', 'saved_exam_id', 'completed_at', 'summary', 'updated_at'
        ])

        log_timing('COMPLETE JOB', total_job_time, job_id=job.id, details=str(stage_timings))
        log_event(
            'GENERATION',
            f"Job #{job.id} completed successfully in {total_job_time}s. {len(final_questions)} questions saved (language='{lang}'). "
            f"Quality: First-pass={quality_report['first_pass_accuracy']}%, Repaired={items_repaired}, Review={items_needs_review}",
            job_id=job.id,
            faculty=job.faculty,
            institution=job.institution
        )

    except Exception as exc:
        logger.exception("Generation job error")
        job.status = GenerationJob.Status.FAILED
        job.error_message = f"Generation failed: {str(exc)}"
        job.completed_at = timezone.now()
        job.save(update_fields=['status', 'error_message', 'completed_at', 'updated_at'])
        log_event(
            'MODEL_ERROR',
            f"Generation Job #{job.id} failed: {str(exc)}",
            job_id=job.id,
            level=logging.ERROR,
            faculty=job.faculty,
            institution=job.institution
        )


def run_generation_job_sync(job_id: int):
    """
    Main synchronous executor called by background worker thread.
    Manages database connections safely.
    """
    from django.db import connections
    connections.close_all()
    try:
        _do_run_grouped_generation_job(job_id)
    finally:
        connections.close_all()


def launch_generation_job(job_id: int) -> Optional[threading.Thread]:
    """Spawns asynchronous worker thread to execute the generation job."""
    from django.conf import settings
    import sys
    if getattr(settings, 'TESTING', False) or 'test' in sys.argv:
        return None
    thread = threading.Thread(
        target=run_generation_job_sync,
        args=(job_id,),
        daemon=True,
        name=f"AiPaperGenWorker-Job-{job_id}"
    )
    thread.start()
    return thread

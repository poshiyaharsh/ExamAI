"""
Main Paper Engine Coordinator.

Integrates:
- Multi-tenant caching (Cache hit < 200ms)
- Single-query candidate pool selection
- Seeded RNG in-memory duplicate-free selection
- Strict Decimal validation and ValidationReport generation
- Short atomic write transactions
- Variant shuffling and single-question replacement
"""

from decimal import Decimal
import logging
import random
import time
from typing import Any, Dict, List, Optional, Tuple

from django.db import transaction
from django.utils import timezone

from api.models import Exam, Option, Question
from api.serializers import ExamDetailSerializer
from .cache import PaperCacheService, compute_request_hash
from .dedupe import CandidateQuestion, DeduplicationIndex
from .pool import (
    PoolExhaustedError,
    compute_target_counts_and_marks,
    fetch_candidate_pool,
    select_paper_questions,
)
from .validator import (
    ValidationReport,
    validate_paper_plan,
    validate_single_candidate,
)

logger = logging.getLogger(__name__)


def generate_exam_paper(
    payload: Dict[str, Any],
    user: Any,
    tenant: Any,
    force_regenerate: bool = False,
    idempotency_key: Optional[str] = None,
) -> Tuple[Dict[str, Any], bool]:
    """
    Generate an exam paper with zero duplicates, instant caching, and strict validation.
    Returns:
        (exam_response_data, was_loaded_from_cache)
    """
    start_time = time.time()
    institution_id = tenant.id

    # 1. Compute Request Hash & Idempotency Key
    req_hash = compute_request_hash(payload)
    seed = payload.get("seed") or random.randint(100000, 999999)

    # 2. Check Cache Layer (if not forcing fresh generation)
    if not force_regenerate:
        cached = PaperCacheService.get_cached_paper(institution_id, user.id, req_hash)
        if cached:
            elapsed_ms = (time.time() - start_time) * 1000
            cached["loaded_from_cache"] = True
            if "validation_report" in cached and isinstance(cached["validation_report"], dict):
                cached["validation_report"]["cached_hit"] = True
                cached["validation_report"]["generation_time_ms"] = round(elapsed_ms, 2)
            logger.info("Serving paper from cache in %.2fms inst=%s user=%s", elapsed_ms, institution_id, user.id)
            return cached, True

    # 3. Parse Parameters
    title = str(payload.get("title", "Exam Paper")).strip()
    duration_minutes = int(payload.get("duration_minutes", 60))
    total_marks = int(payload.get("total_marks", 100))
    department = str(payload.get("department", "")).strip()
    topics = payload.get("topics") or []
    question_types = payload.get("question_types") or ["MCQ_SINGLE"]
    difficulty_mix = payload.get("difficulty_distribution") or {"easy": 30, "medium": 50, "hard": 20}
    avoid_repeats = bool(payload.get("avoid_repeats", True))
    subject_id = payload.get("subject_id") or payload.get("subject")

    # 4. Target Counts & Marks
    target_counts, target_diff = compute_target_counts_and_marks(
        question_types=question_types,
        total_marks=total_marks,
        difficulty_distribution=difficulty_mix,
    )

    # 5. Fetch Candidate Pool in ONE single indexed query
    candidate_pool = fetch_candidate_pool(
        institution_id=institution_id,
        department=department,
        subject_id=subject_id,
        topics=topics,
        question_types=question_types,
        status="ACTIVE",
    )

    # 6. Select Questions In-Memory using Seeded RNG & Deduplication Engine
    selected_candidates, validation_report = select_paper_questions(
        candidate_pool=candidate_pool,
        requested_total_marks=Decimal(str(total_marks)),
        requested_counts_by_type=target_counts,
        requested_difficulty_mix=difficulty_mix,
        duration_minutes=duration_minutes,
        faculty_id=user.id,
        institution_id=institution_id,
        department=department,
        subject_id=subject_id,
        avoid_repeats=avoid_repeats,
        seed=seed,
    )

    elapsed_ms = (time.time() - start_time) * 1000
    validation_report.generation_time_ms = elapsed_ms
    validation_report.cached_hit = False

    # 7. Write Paper in ONE short atomic transaction
    with transaction.atomic():
        # Check idempotency if key provided
        existing_exam = None
        if idempotency_key:
            existing_exam = Exam.objects.filter(
                institution=tenant,
                created_by=user,
                error_message=f"idempotency:{idempotency_key}",
            ).first()

        starts_at = payload.get('starts_at')
        ends_at = payload.get('ends_at')
        display_tz = payload.get('display_timezone') or 'Asia/Kolkata'

        if existing_exam:
            exam = existing_exam
            exam.questions.all().delete()
            exam.seed = seed
            exam.request_hash = req_hash
            exam.validation_report = validation_report.to_dict()
            update_fields = ['seed', 'request_hash', 'validation_report']
            if starts_at:
                exam.starts_at = starts_at
                update_fields.append('starts_at')
            if ends_at:
                exam.ends_at = ends_at
                update_fields.append('ends_at')
            if display_tz:
                exam.display_timezone = display_tz
                update_fields.append('display_timezone')
            exam.save(update_fields=update_fields)
        else:
            exam = Exam.objects.create(
                institution=tenant,
                title=title,
                created_by=user,
                department=department,
                duration_minutes=duration_minutes,
                total_marks=total_marks,
                topics=topics,
                difficulty_distribution=difficulty_mix,
                question_types=question_types,
                ai_model_used="Question Bank Engine",
                status=Exam.Status.DRAFT,
                starts_at=starts_at,
                ends_at=ends_at,
                display_timezone=display_tz,
                error_message=f"idempotency:{idempotency_key}" if idempotency_key else "",
                seed=seed,
                request_hash=req_hash,
                validation_report=validation_report.to_dict(),
            )

        # Batch create questions for this exam
        questions_to_create = []
        options_data_map = {}

        now = timezone.now()
        for order_idx, c in enumerate(selected_candidates, start=1):
            q_inst = Question(
                institution=tenant,
                department=department,
                subject_id=subject_id or c.subject_id,
                exam=exam,
                order=order_idx,
                question_type=c.question_type,
                difficulty=c.difficulty,
                text=c.text,
                text_hash=c.text_hash,
                active_hash=c.text_hash if (subject_id or c.subject_id) else None,
                marks=Decimal(str(c.marks)),
                negative_marks=Decimal("0.0"),
                status=Question.Status.ACTIVE,
                topic_text=c.topic,
                times_used=1,
                last_used_at=now,
                created_by=user,
            )
            questions_to_create.append(q_inst)
            options_data_map[order_idx] = c.options

        saved_questions = []
        for q_inst in questions_to_create:
            q_inst.save()
            saved_questions.append(q_inst)

        # Bulk create Options for the questions
        options_to_create = []
        for saved_q in saved_questions:
            q_opts = options_data_map.get(saved_q.order, [])
            for opt_idx, opt_data in enumerate(q_opts, start=1):
                if isinstance(opt_data, dict):
                    opt_text = opt_data.get("text", "")
                    opt_correct = opt_data.get("is_correct", False)
                else:
                    opt_text = str(opt_data)
                    opt_correct = False
                options_to_create.append(
                    Option(
                        question=saved_q,
                        text=opt_text,
                        is_correct=opt_correct,
                        order=opt_idx,
                    )
                )

        if options_to_create:
            Option.objects.bulk_create(options_to_create)

    # 8. Serialize Result
    exam.refresh_from_db()
    data = ExamDetailSerializer(exam).data
    data["loaded_from_cache"] = False
    data["validation_report"] = validation_report.to_dict()
    data["seed"] = seed
    data["request_hash"] = req_hash
    data["question_ids"] = [q.id for q in saved_questions]

    # 9. Store in Cache Layer
    PaperCacheService.set_cached_paper(
        institution_id=institution_id,
        faculty_id=user.id,
        request_hash=req_hash,
        data=data,
    )
    PaperCacheService.set_cached_paper_detail(institution_id, exam.id, data)

    logger.info(
        "Successfully generated paper id=%s in %.2fms (questions=%s, marks=%s)",
        exam.id, elapsed_ms, len(saved_questions), total_marks
    )
    return data, False


def shuffle_exam_questions(exam: Exam, user: Any, tenant: Any) -> Dict[str, Any]:
    """
    Creates a new shuffled variant of questions and options inside an exam.
    Preserves exact validity and duplicate freedom.
    """
    if exam.status == Exam.Status.PUBLISHED:
        raise ValueError("Published exams are immutable and cannot be reshuffled.")

    questions = list(exam.questions.all().order_by("order"))
    if not questions:
        return ExamDetailSerializer(exam).data

    rng = random.Random()
    rng.shuffle(questions)

    with transaction.atomic():
        for new_order, q in enumerate(questions, start=1):
            q.order = new_order
            q.save(update_fields=["order"])

            # Shuffle options
            opts = list(q.option_items.all())
            if len(opts) > 1 and q.question_type != "TRUE_FALSE":
                rng.shuffle(opts)
                for opt_idx, opt in enumerate(opts, start=1):
                    opt.order = opt_idx
                    opt.save(update_fields=["order"])

    PaperCacheService.invalidate_exam(tenant.id, exam.id)
    exam.refresh_from_db()
    return ExamDetailSerializer(exam).data


def swap_single_question(
    exam: Exam,
    question_id: int,
    user: Any,
    tenant: Any,
) -> Tuple[Dict[str, Any], ValidationReport]:
    """
    Replace a single question in an exam with another non-duplicate candidate
    from the same topic, difficulty, type, and marks.
    """
    if exam.status == Exam.Status.PUBLISHED:
        raise ValueError("Published exams are immutable and cannot be modified.")

    target_q = exam.questions.filter(id=question_id).first()
    if not target_q:
        raise ValueError(f"Question #{question_id} not found in this exam.")

    # Build active DeduplicationIndex from all other questions in the exam
    other_questions = exam.questions.exclude(id=question_id).select_related("topic").prefetch_related("option_items")
    dedupe_idx = DeduplicationIndex()
    for q in other_questions:
        dedupe_idx.add(CandidateQuestion.from_model(q))

    # Fetch pool of replacement candidates matching criteria
    candidates = fetch_candidate_pool(
        institution_id=tenant.id,
        department=exam.department,
        subject_id=target_q.subject_id,
        question_types=[target_q.question_type],
        difficulties=[target_q.difficulty],
        status="ACTIVE",
    )

    rng = random.Random()
    rng.shuffle(candidates)

    replacement: Optional[CandidateQuestion] = None
    for cand in candidates:
        if cand.id == target_q.id:
            continue
        if Decimal(str(cand.marks)) != target_q.marks:
            continue

        is_dup, _ = dedupe_idx.check_candidate(cand)
        is_valid, _ = validate_single_candidate(cand, tenant.id, exam.department, target_q.subject_id)

        if not is_dup and is_valid:
            replacement = cand
            break

    if not replacement:
        raise PoolExhaustedError(
            f"No suitable alternative question found for {target_q.difficulty} "
            f"{target_q.question_type} ({target_q.marks} marks) that avoids duplicates."
        )

    # Perform atomic swap
    with transaction.atomic():
        target_q.text = replacement.text
        target_q.text_hash = replacement.text_hash
        target_q.topic_text = replacement.topic
        target_q.marks = Decimal(str(replacement.marks))
        target_q.model_answer = getattr(replacement, 'model_answer', '') or ''
        target_q.correct_answer = replacement.correct_answer
        target_q.options = [o.get("text", "") if isinstance(o, dict) else str(o) for o in (replacement.options or [])] if replacement.options else None
        target_q.save(update_fields=["text", "text_hash", "topic_text", "marks", "model_answer", "correct_answer", "options", "updated_at"])


        # Replace options
        target_q.option_items.all().delete()
        new_opts = []
        for idx, o in enumerate(replacement.options, start=1):
            if isinstance(o, dict):
                otext = o.get("text", "")
                ocorr = o.get("is_correct", False)
            else:
                otext = str(o)
                ocorr = False
            new_opts.append(
                Option(
                    question=target_q,
                    text=otext,
                    is_correct=ocorr,
                    order=idx,
                )
            )
        if new_opts:
            Option.objects.bulk_create(new_opts)

    # Invalidate cache
    PaperCacheService.invalidate_exam(tenant.id, exam.id)

    # Re-validate whole paper
    all_updated = [CandidateQuestion.from_model(q) for q in exam.questions.all()]
    _, report, _ = validate_paper_plan(
        candidates=all_updated,
        requested_total_marks=Decimal(str(exam.total_marks)),
        duration_minutes=exam.duration_minutes,
        institution_id=tenant.id,
        department=exam.department,
    )

    from api.serializers import FacultyQuestionSerializer
    return FacultyQuestionSerializer(target_q).data, report

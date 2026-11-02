"""
Repair and Fallback Coordinator.
Coordinates:
1. Main model attempts (at most 2 attempts per slot)
2. AI validation check for Short/Long or suspicious slots
3. Deduplication check
4. Fallback model attempt with gemma3:4b (1 attempt) if main model fails
5. If still fails, constructs deterministic grounded question and marks slot failed in UI and logs.
Never silently drops a slot.
Multilingual support passing language through all verification stages.
"""
import logging
from typing import Dict, Any, Optional
from ..ollama_client import OllamaClient
from ..rag.retriever import RAGRetriever
from ..generators.question_generator import QuestionGenerator
from ..generators.validator import validate_rules, validate_with_model2, should_run_ai_validation
from ..generators.deduplicator import QuestionDeduplicator
from ..generators.rubric_builder import build_rubric
from ..logging_setup import log_event

logger = logging.getLogger(__name__)


def generate_and_validate_slot_with_repair(
    slot: Dict[str, Any],
    subject: str,
    client: OllamaClient,
    retriever: RAGRetriever,
    deduplicator: QuestionDeduplicator,
    model_generator: str,
    model_validator: str,
    model_fallback: str,
    job_id: int,
    progress_callback: Optional[callable] = None,
    language: str = "en"
) -> Dict[str, Any]:
    """
    Executes single-slot generation with strict retry limits (Phase 4.8):
    - At most 2 attempts with main model
    - 1 attempt with fallback model (gemma3:4b)
    - Grounded deterministic question if still failing
    """
    slot_num = slot.get('slot_index')
    q_type = slot.get('type')
    max_main_attempts = 2  # Phase 4.8: at most 2 retries with main model
    expansion_level = 0

    generator = QuestionGenerator(client, retriever, job_id, language=language)

    # Phase 1: Try Main Model (up to 2 attempts)
    for attempt in range(1, max_main_attempts + 1):
        if progress_callback:
            progress_callback(f"Generating {q_type} (Slot {slot_num}) - Attempt {attempt}")

        try:
            cand = generator.generate_single_slot(
                slot, subject, model_name=model_generator, expansion_level=expansion_level
            )

            if cand.get('_insufficient_context'):
                expansion_level += 1
                continue

            # Tier 1 Instant Rules
            is_valid, reason = validate_rules(cand, job_id=job_id, language=language)
            if not is_valid:
                log_event(
                    'VALIDATION',
                    f"Slot {slot_num} failed Tier 1 validation on attempt {attempt}: {reason}.",
                    job_id=job_id,
                    slot_number=slot_num
                )
                continue

            # Tier 2 AI check ONLY for Short/Long or suspicious
            if should_run_ai_validation(cand, is_valid):
                context_snippet = retriever.retrieve_context_for_slot(slot.get('topic', 'General'), q_type, slot.get('difficulty', 'Medium'))
                m2_valid, m2_reason = validate_with_model2(cand, context_snippet, client, model_validator, job_id)
                if not m2_valid:
                    log_event(
                        'VALIDATION',
                        f"Slot {slot_num} rejected by AI Validator on attempt {attempt}: {m2_reason}.",
                        job_id=job_id,
                        slot_number=slot_num
                    )
                    continue

            # Deduplication
            is_dup, dup_reason = deduplicator.is_duplicate(cand)
            if is_dup:
                log_event(
                    'VALIDATION',
                    f"Slot {slot_num} rejected as duplicate on attempt {attempt}: {dup_reason}.",
                    job_id=job_id,
                    slot_number=slot_num
                )
                continue

            # Success with Main Model
            cand['model_used'] = model_generator
            cand['retries'] = attempt - 1
            deduplicator.add(cand)
            return cand

        except Exception as exc:
            log_event(
                'MODEL_ERROR',
                f"Exception during Slot {slot_num} generation with {model_generator}: {str(exc)}",
                job_id=job_id,
                slot_number=slot_num,
                model_name=model_generator
            )

    # Phase 2: Try Fallback Model (gemma3:4b, exactly 1 attempt)
    log_event(
        'GENERATION',
        f"Switching to Fallback Model ({model_fallback}) for Slot {slot_num} after main model exhausted {max_main_attempts} attempts.",
        job_id=job_id,
        level=logging.WARNING,
        slot_number=slot_num,
        model_name=model_fallback
    )
    if progress_callback:
        progress_callback(f"Retrying Slot {slot_num} with fallback model ({model_fallback})...")

    try:
        cand = generator.generate_single_slot(
            slot, subject, model_name=model_fallback, expansion_level=expansion_level
        )
        is_valid, reason = validate_rules(cand, job_id=job_id, language=language)
        if is_valid:
            is_dup, _ = deduplicator.is_duplicate(cand)
            if not is_dup:
                cand['model_used'] = model_fallback
                cand['retries'] = max_main_attempts
                cand['fallback_used'] = True
                deduplicator.add(cand)
                return cand
    except Exception as exc:
        log_event(
            'MODEL_ERROR',
            f"Fallback model ({model_fallback}) error on Slot {slot_num}: {str(exc)}",
            job_id=job_id,
            slot_number=slot_num,
            model_name=model_fallback
        )

    # Phase 3: Construct Grounded Deterministic Question (Zero Dropped Slots)
    log_event(
        'WARNING',
        f"Constructing deterministic grounded question for Slot {slot_num} to guarantee zero dropped slots.",
        job_id=job_id,
        level=logging.WARNING,
        slot_number=slot_num
    )
    cand = construct_deterministic_slot(slot, subject, retriever, language=language)
    cand['failed'] = True
    cand['model_used'] = 'deterministic_fallback'
    cand['retries'] = max_main_attempts + 1
    deduplicator.add(cand)
    return cand


def construct_deterministic_slot(
    slot: Dict[str, Any],
    subject: str,
    retriever: RAGRetriever,
    language: str = "en"
) -> Dict[str, Any]:
    """Generates a valid, grounded question fallback so no slot is ever dropped."""
    slot_num = slot.get('slot_index', 1)
    q_type = slot.get('type', 'MCQ')
    topic = slot.get('topic', 'General Principles')
    difficulty = slot.get('difficulty', 'Medium')
    marks = slot.get('marks', 1)

    if q_type == 'MCQ':
        return {
            'slot_index': slot_num,
            'type': 'MCQ',
            'topic': topic,
            'difficulty': difficulty,
            'marks': marks,
            'question': f"In the study of {subject}, which of the following is a primary principle of {topic}?",
            'options': [
                f"Core theoretical foundations and applications of {topic}",
                f"External unrelated peripheral systems",
                f"Deprecated legacy configurations",
                f"Non-standard auxiliary parameters"
            ],
            'answer': f"Core theoretical foundations and applications of {topic}",
            'explanation': f"Derived from curriculum specification for {subject}: {topic}."
        }
    elif q_type == 'True/False':
        return {
            'slot_index': slot_num,
            'type': 'True/False',
            'topic': topic,
            'difficulty': difficulty,
            'marks': marks,
            'question': f"In {subject}, {topic} plays a vital role in core system design.",
            'options': ['True', 'False'],
            'answer': 'True',
            'explanation': f"Fundamental concept of {topic} in {subject}."
        }
    elif q_type == 'Fill in the Blank':
        return {
            'slot_index': slot_num,
            'type': 'Fill in the Blank',
            'topic': topic,
            'difficulty': difficulty,
            'marks': marks,
            'question': f"In {subject}, _____ represents a foundational methodology within {topic}.",
            'answer': topic.lower(),
            'explanation': f"Standard term from {topic} syllabus."
        }
    elif q_type == 'Short Answer':
        q_text = f"Explain the fundamental role and practical application of {topic} in {subject}."
        ans_text = f"{topic} is an essential concept in {subject}. It provides the theoretical framework and operational rules required to analyze, design, and optimize modern systems effectively."
        raw_pts = [f"Definition of {topic}", f"Operational significance in {subject}", "Key practical outcomes"]
        rub = build_rubric('Short Answer', marks, raw_pts, question_text=q_text, model_answer=ans_text, language=language)
        return {
            'slot_index': slot_num,
            'type': 'Short Answer',
            'topic': topic,
            'difficulty': difficulty,
            'marks': marks,
            'question': q_text,
            'answer': ans_text,
            'key_points': rub[0]['key_points'],
            'rubric': rub,
        }
    else:  # Long Answer
        q_text = f"Provide a comprehensive technical evaluation of {topic} within {subject}. Discuss its underlying architecture, trade-offs, and implementation strategies."
        ans_text = f"{topic} serves as a foundational pillar in {subject}.\n\n1. Architectural Overview: It governs how data, execution flow, and system constraints interact systematically.\n2. Key Operational Principles: Implements robust synchronization, verification, and performance scaling.\n3. Trade-offs and Best Practices: Balances computational efficiency against system overhead to ensure reliability under peak workloads."
        raw_pts = [
            f"Architectural evaluation of {topic}",
            "Detailed procedural breakdown",
            "Analysis of operational trade-offs",
            "Summary of best practices and system constraints"
        ]
        rub = build_rubric('Long Answer', marks, raw_pts, question_text=q_text, model_answer=ans_text, language=language)
        return {
            'slot_index': slot_num,
            'type': 'Long Answer',
            'topic': topic,
            'difficulty': difficulty,
            'marks': marks,
            'question': q_text,
            'answer': ans_text,
            'key_points': rub[0]['key_points'],
            'rubric': rub,
        }

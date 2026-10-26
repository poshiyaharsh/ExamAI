"""
High-Performance Tiered Paper Generation Engine.
Guarantees completion under 300s (5-minute hard budget) with exact Decimal marks,
zero duplicate questions, strict syllabus grounding, and background subjective answer generation.

Tiers:
- Tier 0: Question Bank reuse (instant, excluding last N papers)
- Tier 1: Extractive Fill-in-the-blank & True/False (instant, zero LLM calls)
- Tier 2: Batched LLM for MCQ and Short Answer (compact JSON schema)
- Tier 3: Emergency extractive generation (instant fallback if LLM budget low)
- Tier 4: Graceful shortfall with 'completed_with_warnings' and 'Generate remaining'
"""
from decimal import Decimal
import difflib
import hashlib
import json
import logging
import os
import re
import threading
import time
from typing import Any, Dict, List, Optional, Set, Tuple

from django.utils import timezone

from .blueprint_allocator import to_decimal
from .evaluation_config import (
    OLLAMA_BASE_URL,
    OLLAMA_FALLBACK_MODELS,
    OLLAMA_KEEP_ALIVE,
    OLLAMA_MODEL,
    OLLAMA_NUM_CTX,
    OLLAMA_REQUEST_TIMEOUT,
    OLLAMA_TEMPERATURE,
)
from .ollama_client import call_ollama, parse_json_safely
from .ollama_models import (
    get_installed_models,
    normalize_model_name,
    resolve_model,
    OllamaConnectionError,
    OllamaModelNotFoundError,
)

logger = logging.getLogger(__name__)

# Budget Constants (env-overridable)
PAPER_HARD_DEADLINE = int(os.getenv('PAPER_HARD_DEADLINE', '300'))
PAPER_LLM_BUDGET = int(os.getenv('PAPER_LLM_BUDGET', '210'))
PAPER_FINALIZE_RESERVE = int(os.getenv('PAPER_FINALIZE_RESERVE', '30'))
PER_CALL_TIMEOUT = int(os.getenv('PER_CALL_TIMEOUT', '60'))


# --- STEP 1: BUDGET MANAGER ---

class BudgetManager:
    """Tracks elapsed and remaining time budget per paper generation job."""
    def __init__(self, start_time: Optional[float] = None, hard_deadline: int = PAPER_HARD_DEADLINE, llm_budget: int = PAPER_LLM_BUDGET):
        self.start_time = start_time or time.perf_counter()
        self.hard_deadline = hard_deadline
        self.llm_budget = llm_budget
        self._calibrations = self._load_calibrations()

    def _load_calibrations(self) -> Dict[str, Any]:
        calib_path = os.path.join(os.getcwd(), 'model_calibration.json')
        if os.path.exists(calib_path):
            try:
                with open(calib_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass
        return {
            'qwen2.5:3b-instruct': {'eval_tokens_per_sec': 17.5, 'prompt_tokens_per_sec': 480.0},
            'llama3.2:3b': {'eval_tokens_per_sec': 18.5, 'prompt_tokens_per_sec': 450.0},
            'phi3:mini': {'eval_tokens_per_sec': 9.5, 'prompt_tokens_per_sec': 300.0},
        }

    @property
    def elapsed_seconds(self) -> float:
        return time.perf_counter() - self.start_time

    @property
    def remaining_hard_seconds(self) -> float:
        return max(0.0, self.hard_deadline - self.elapsed_seconds)

    @property
    def remaining_llm_seconds(self) -> float:
        return max(0.0, self.llm_budget - self.elapsed_seconds)

    def can_afford_llm_call(self, model: str, estimated_output_tokens: int = 400, prompt_tokens: int = 350) -> bool:
        if self.remaining_llm_seconds <= 10.0:
            return False
        model_calib = self._calibrations.get(model, {'eval_tokens_per_sec': 16.0, 'prompt_tokens_per_sec': 400.0})
        eval_speed = max(5.0, float(model_calib.get('eval_tokens_per_sec', 16.0)))
        prompt_speed = max(50.0, float(model_calib.get('prompt_tokens_per_sec', 400.0)))
        est_duration = (prompt_tokens / prompt_speed) + (estimated_output_tokens / eval_speed) + 2.0
        return self.remaining_llm_seconds >= est_duration

    def get_call_timeout(self) -> int:
        return max(10, min(PER_CALL_TIMEOUT, int(self.remaining_llm_seconds)))


# --- STEP 4: DUPLICATE DETECTOR ---

STOPWORDS = {
    'a', 'an', 'and', 'are', 'as', 'at', 'be', 'by', 'for', 'from', 'has', 'he',
    'in', 'is', 'it', 'its', 'of', 'on', 'that', 'the', 'to', 'was', 'were', 'will', 'with'
}

def normalize_text(text: str) -> str:
    clean = re.sub(r'^[0-9]+[.\s]+', '', str(text or '')).lower()
    clean = re.sub(r'[^\w\s]', ' ', clean)
    tokens = [w for w in clean.split() if w not in STOPWORDS]
    return ' '.join(tokens)

def compute_token_jaccard(tokens_a: Set[str], tokens_b: Set[str]) -> float:
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = len(tokens_a.intersection(tokens_b))
    union = len(tokens_a.union(tokens_b))
    return float(intersection) / float(union) if union > 0 else 0.0

class DuplicateDetector:
    """High-speed pure-python duplicate detector applying multiple similarity layers."""
    def __init__(self, existing_questions: Optional[List[Dict[str, Any]]] = None):
        self.seen_hashes: Set[str] = set()
        self.accepted_questions: List[Dict[str, Any]] = []
        if existing_questions:
            for q in existing_questions:
                self.add(q)

    def add(self, q: Dict[str, Any]) -> None:
        self.accepted_questions.append(q)
        norm_stem = normalize_text(q.get('text', ''))
        if norm_stem:
            self.seen_hashes.add(hashlib.sha256(norm_stem.encode('utf-8')).hexdigest())

    def is_duplicate(self, candidate: Dict[str, Any]) -> Tuple[bool, str]:
        cand_text = str(candidate.get('text', '')).strip()
        norm_cand = normalize_text(cand_text)
        if not norm_cand:
            return True, "Empty question stem after normalization"

        cand_hash = hashlib.sha256(norm_cand.encode('utf-8')).hexdigest()
        if cand_hash in self.seen_hashes:
            return True, "Exact normalized stem hash match"

        # Check options for duplicate choices within the same question
        raw_opts = candidate.get('options')
        if isinstance(raw_opts, list) and len(raw_opts) > 1:
            norm_opts = [normalize_text(o) for o in raw_opts if str(o).strip()]
            if len(norm_opts) != len(set(norm_opts)):
                return True, "Duplicate option choices within candidate"

        cand_tokens = set(norm_cand.split())
        cand_ans = str(candidate.get('correct_answer') or '').strip().lower()

        for idx, exist in enumerate(self.accepted_questions):
            exist_text = str(exist.get('text', '')).strip()
            norm_exist = normalize_text(exist_text)
            exist_tokens = set(norm_exist.split())

            # 1. Token Jaccard check (>= 0.7)
            jaccard = compute_token_jaccard(cand_tokens, exist_tokens)
            if jaccard >= 0.70:
                return True, f"High token overlap (Jaccard {jaccard:.2f}) with question #{idx + 1}"

            # 2. Difflib ratio check (>= 0.85)
            ratio = difflib.SequenceMatcher(None, norm_cand, norm_exist).ratio()
            if ratio >= 0.85:
                return True, f"High sequence similarity (ratio {ratio:.2f}) with question #{idx + 1}"

            # 3. Same answer and stem similarity >= 0.5
            exist_ans = str(exist.get('correct_answer') or '').strip().lower()
            if cand_ans and exist_ans and cand_ans == exist_ans and ratio >= 0.50:
                return True, f"Identical answer with high stem similarity ({ratio:.2f}) with question #{idx + 1}"

            # 4. Subjective key points Jaccard >= 0.6
            cand_kp = set(normalize_text(k) for k in candidate.get('key_points', []) if k)
            exist_kp = set(normalize_text(k) for k in exist.get('key_points', []) if k)
            if cand_kp and exist_kp:
                kp_jaccard = compute_token_jaccard(cand_kp, exist_kp)
                if ratio >= 0.40 and kp_jaccard >= 0.60:
                    return True, f"Near-identical subjective rubric and key points (Jaccard {kp_jaccard:.2f})"

        return False, ""

    def filter_and_deduplicate(self, questions: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], int, List[Dict[str, Any]]]:
        accepted = []
        rejected = []
        for q in questions:
            is_dup, reason = self.is_duplicate(q)
            if is_dup:
                rejected.append({'question': q, 'reason': reason})
            else:
                self.add(q)
                accepted.append(q)
        return accepted, len(rejected), rejected


# --- STEP 3a: TIER 0 QUESTION BANK REUSE ---

class QuestionBankService:
    """Retrieves high-quality banked questions from the same institution & subject, excluding recent exams."""
    @staticmethod
    def get_reusable_questions(
        institution_id: int,
        subject_id: Optional[int],
        question_type: str,
        difficulty: str,
        needed_count: int,
        exclude_exam_ids: Optional[List[int]] = None,
        expected_marks: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        from api.models import Question
        from api.utils.validate_paper import canonicalize_type, canonicalize_difficulty
        if needed_count <= 0:
            return []

        canon_type = canonicalize_type(question_type)
        type_candidates = [canon_type]
        for choice_val, _ in Question.QuestionType.choices:
            if canonicalize_type(choice_val) == canon_type and choice_val not in type_candidates:
                type_candidates.append(choice_val)

        qs = Question.objects.filter(
            institution_id=institution_id,
            question_type__in=type_candidates,
            is_deleted=False,
            status=Question.Status.ACTIVE,
        )
        if subject_id:
            qs = qs.filter(subject_id=subject_id)
        if difficulty and difficulty != 'any':
            canon_diff = canonicalize_difficulty(difficulty)
            diff_candidates = [canon_diff]
            for diff_val, _ in Question.Difficulty.choices:
                if canonicalize_difficulty(diff_val) == canon_diff and diff_val not in diff_candidates:
                    diff_candidates.append(diff_val)
            qs = qs.filter(difficulty__in=diff_candidates)
        if expected_marks is not None:
            qs = qs.filter(marks=expected_marks)
        if exclude_exam_ids:
            qs = qs.exclude(exam_id__in=exclude_exam_ids)
        if canon_type == 'long_answer':
            qs = qs.exclude(model_answer='').exclude(rubric=[])

        qs = qs.order_by('last_used_at', 'times_used')[:needed_count]

        banked_items = []
        for q in qs:
            options_list = None
            if q.options and isinstance(q.options, list):
                options_list = list(q.options)
            elif q.option_items.exists():
                options_list = list(q.option_items.values_list('text', flat=True))

            banked_items.append({
                'id': q.id,
                'type': canon_type,
                'difficulty': canonicalize_difficulty(q.difficulty),
                'text': q.text,
                'options': options_list,
                'correct_answer': q.correct_answer,
                'model_answer': q.model_answer or '',
                'marks': float(expected_marks if expected_marks is not None else q.marks),
                'topic': q.topic_text or (q.topic.name if q.topic else 'General'),
                'source': 'bank',
                'rubric': q.rubric or [],
                'key_points': q.rubric or [],
                'word_limit': q.word_limit,
            })
        return banked_items


# --- STEP 3b: TIER 1 EXTRACTIVE GENERATOR (ZERO LLM CALLS) ---

class ExtractiveGenerator:
    """
    Deterministically generates high-quality Fill-in-the-Blank and True/False questions
    directly from syllabus sentences in milliseconds without invoking the LLM.
    """
    SENTENCE_SPLIT_REGEX = re.compile(r'(?<=[.!?])\s+')
    KEY_TERM_REGEX = re.compile(r'\b([A-Z][a-zA-Z0-9_\-]+(?:\s+[A-Z][a-zA-Z0-9_\-]+)?)\b')

    @classmethod
    def extract_candidates_from_text(cls, text: str, topic: str = 'General') -> List[Dict[str, Any]]:
        clean_text = str(text or '').strip()
        sentences = [s.strip() for s in cls.SENTENCE_SPLIT_REGEX.split(clean_text) if len(s.strip().split()) >= 6 and len(s.strip()) <= 200]
        candidates = []
        for s in sentences:
            # Look for defining sentences
            has_def = any(kw in s.lower() for kw in ('is defined as', 'refers to', 'consists of', 'is used to', 'provides', 'means', 'is a', 'are used for'))
            terms = cls.KEY_TERM_REGEX.findall(s)
            if terms and (has_def or len(s.split()) >= 8):
                candidates.append({'sentence': s, 'terms': terms, 'topic': topic})
        return candidates

    @classmethod
    def generate_fill_blank(cls, candidates: List[Dict[str, Any]], needed_count: int, marks_per_q: float = 1.0) -> List[Dict[str, Any]]:
        results = []
        all_terms = [t for c in candidates for t in c['terms'] if len(t) >= 3]
        for c in candidates:
            if len(results) >= needed_count:
                break
            sentence = c['sentence']
            # Find the best key term to blank out
            primary_term = c['terms'][0]
            if len(primary_term) < 3:
                continue

            blanked_text = re.sub(re.escape(primary_term), '____', sentence, count=1, flags=re.IGNORECASE)
            if '____' not in blanked_text:
                continue

            # Pick 3 plausible distractors from other terms
            distractors = [t for t in all_terms if t.lower() != primary_term.lower() and abs(len(t) - len(primary_term)) <= 8]
            distractors = list(dict.fromkeys(distractors))[:3]
            while len(distractors) < 3:
                distractors.append(f"Alternative {len(distractors) + 1}")

            options = [primary_term] + distractors
            options = sorted(options, key=lambda x: hashlib.sha256(x.encode()).hexdigest())

            results.append({
                'type': 'fill_blank',
                'difficulty': 'easy',
                'topic': c['topic'],
                'text': blanked_text,
                'options': options,
                'correct_answer': primary_term,
                'accepted_answers': [[primary_term]],
                'marks': marks_per_q,
                'source': 'extractive',
            })
        return results

    @classmethod
    def generate_true_false(cls, candidates: List[Dict[str, Any]], needed_count: int, marks_per_q: float = 1.0) -> List[Dict[str, Any]]:
        results = []
        all_terms = [t for c in candidates for t in c['terms'] if len(t) >= 3]
        for idx, c in enumerate(candidates):
            if len(results) >= needed_count:
                break
            sentence = c['sentence'].rstrip('.')
            # Alternating true and false
            is_true_question = (idx % 2 == 0)
            if is_true_question:
                statement = f"{sentence}."
                correct = "True"
            else:
                # Controlled term swap or negation
                term = c['terms'][0]
                alt_terms = [t for t in all_terms if t.lower() != term.lower()]
                if alt_terms:
                    statement = re.sub(re.escape(term), alt_terms[0], sentence, count=1, flags=re.IGNORECASE) + "."
                else:
                    statement = f"It is not true that {sentence.lower()}."
                correct = "False"

            results.append({
                'type': 'true_false',
                'difficulty': 'easy',
                'topic': c['topic'],
                'text': statement,
                'options': ['True', 'False'],
                'correct_answer': correct,
                'marks': marks_per_q,
                'source': 'extractive',
            })
        return results


# --- STEP 3d: ASYNCHRONOUS SUBJECTIVE ANSWER GENERATOR ---

def generate_pending_subjective_answers_task(exam_id: int):
    """
    Background worker that enriches 6+ mark subjective questions with full model answers.
    Executes in a separate thread without holding database transactions open during generation.
    """
    from api.models import Question
    from api.utils.evaluation_config import OLLAMA_MODEL
    logger.info("Starting background subjective answer generation for Exam %s", exam_id)

    pending_qs = Question.objects.filter(
        exam_id=exam_id,
        question_type__in=['long_answer', 'subjective'],
        is_deleted=False,
    ).exclude(model_answer__regex=r'^\s*\S+(?:\s+\S+){25,}')

    if not pending_qs.exists():
        logger.info("No pending subjective model answers needed for Exam %s", exam_id)
        return

    model_tag = resolve_model(OLLAMA_MODEL)

    for q in pending_qs:
        prompt = f"""You are an expert university examiner. Write a comprehensive, high-scoring model answer (150-300 words)
for this exam question worth {q.marks} marks:

Question: {q.text}
Topic: {q.topic_text}

Provide:
1. Clear, academic definition and conceptual introduction.
2. Structured key points and architectural/technical details.
3. Real-world implementation or practical example.

Return JSON shape:
{{
  "model_answer": "Complete, thorough explanation without placeholders..."
}}
Return JSON only."""

        try:
            raw = call_ollama(
                model=model_tag,
                prompt=prompt,
                format_schema='json',
                temperature=0.2,
                num_predict=600,
                keep_alive=OLLAMA_KEEP_ALIVE,
                timeout=60,
            )
            parsed = parse_json_safely(raw)
            ans = ""
            if isinstance(parsed, dict):
                ans = str(parsed.get('model_answer') or '').strip()
            if ans and len(ans.split()) >= 20:
                q.model_answer = ans
                q.save(update_fields=['model_answer'])
                logger.info("Successfully populated background model answer for Question %s", q.id)
        except Exception as exc:
            logger.warning("Failed to generate background model answer for Question %s: %s", q.id, exc)


def launch_background_subjective_answers(exam_id: int):
    thread = threading.Thread(target=generate_pending_subjective_answers_task, args=(exam_id,), daemon=True)
    thread.start()

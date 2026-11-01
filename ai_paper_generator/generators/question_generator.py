"""
Question Generator (Multi-Model Batch & Slot Coordinator).
Supports:
1. Batch generation grouped by question type and model.
2. Structured output schema enforcement via Ollama format parameter.
3. Truncation guard (Section 3.5): retries with +50% tokens if truncated by length.
4. Normalization of MCQs (Section 3.3) ensuring 4 unique options and exact correct answer.
5. RAG context integration with INSUFFICIENT_CONTEXT fallback expansion.
6. Blueprint authority: marks strictly taken from blueprint, never model output.
"""
import re
import logging
from typing import Dict, Any, List, Optional
from ..ollama_client import OllamaClient, OllamaTruncationError
from ..rag.retriever import RAGRetriever
from ..prompts.mcq import build_batch_mcq_prompt, build_mcq_prompt, MCQ_JSON_SCHEMA, get_batch_mcq_schema
from ..prompts.true_false import build_batch_true_false_prompt, build_true_false_prompt, TRUE_FALSE_JSON_SCHEMA, get_batch_true_false_schema
from ..prompts.fill_blank import build_batch_fill_blank_prompt, build_fill_blank_prompt, FILL_BLANK_JSON_SCHEMA, get_batch_fill_blank_schema
from ..prompts.short import build_batch_short_prompt, build_short_prompt, SHORT_JSON_SCHEMA, get_batch_short_schema
from ..prompts.long import build_batch_long_prompt, build_long_prompt, LONG_JSON_SCHEMA, get_batch_long_schema
from ..prompts.system_rules import BASE_SYSTEM_PROMPT
from ..logging_setup import log_event
from ..config import TEMPERATURE_BY_TYPE, BASE_TOKENS_BY_TYPE
from .json_repair import parse_and_repair_json, extract_questions_list
from .mcq_normalizer import normalize_mcq
from .rubric_builder import build_rubric

logger = logging.getLogger(__name__)


class QuestionGenerator:
    def __init__(self, client: OllamaClient, retriever: RAGRetriever, job_id: int):
        self.client = client
        self.retriever = retriever
        self.job_id = job_id

    def generate_batch(
        self,
        q_type: str,
        slots: List[Dict[str, Any]],
        subject: str,
        model_name: str,
        words_per_mark_short: int = 35,
        words_per_mark_long: int = 55,
    ) -> List[Dict[str, Any]]:
        """
        Generates a batch of questions of the same type in a single Ollama call.
        Enforces schema format and handles truncation guards.
        """
        if not slots:
            return []

        # Retrieve combined context for topics in this batch
        topics = list(set(s.get('topic', 'General') for s in slots if s.get('topic')))
        combined_context = self.retriever.retrieve_context_for_topics(topics, expansion_level=0)

        # Select prompt builder and schema
        schema = None
        n_slots = len(slots)
        if q_type == 'MCQ':
            prompt = build_batch_mcq_prompt(subject, slots, combined_context)
            schema = get_batch_mcq_schema(n_slots)
            base_tok = 135
        elif q_type == 'True/False':
            prompt = build_batch_true_false_prompt(subject, slots, combined_context)
            schema = get_batch_true_false_schema(n_slots)
            base_tok = 90
        elif q_type == 'Fill in the Blank':
            prompt = build_batch_fill_blank_prompt(subject, slots, combined_context)
            schema = get_batch_fill_blank_schema(n_slots)
            base_tok = 90
        elif q_type == 'Short Answer':
            prompt = build_batch_short_prompt(subject, slots, combined_context, words_per_mark=words_per_mark_short)
            schema = get_batch_short_schema(n_slots)
            avg_marks = slots[0].get('marks', 2) if slots else 2
            base_tok = words_per_mark_short * avg_marks + 80
        elif q_type == 'Long Answer':
            prompt = build_batch_long_prompt(subject, slots, combined_context, words_per_mark=words_per_mark_long)
            schema = get_batch_long_schema(n_slots)
            avg_marks = slots[0].get('marks', 5) if slots else 5
            base_tok = words_per_mark_long * avg_marks + 100
        else:
            prompt = build_batch_mcq_prompt(subject, slots, combined_context)
            schema = get_batch_mcq_schema(n_slots)
            base_tok = 135

        temp = TEMPERATURE_BY_TYPE.get(q_type, 0.25)
        # Token budget (Section 2.1): expected tokens * 1.5 + 120
        expected_tokens = int(n_slots * base_tok * 1.5) + 120
        num_predict = min(4096, max(200, expected_tokens))

        raw_output = ""
        # Truncation Guard loop (Step 3.5)
        for attempt in range(2):
            try:
                raw_output = self.client.generate(
                    model=model_name,
                    prompt=prompt,
                    system_prompt=BASE_SYSTEM_PROMPT,
                    json_mode=True,
                    format=schema,
                    temperature=temp,
                    num_predict=num_predict,
                    job_id=self.job_id,
                    stage=f"batch_{q_type.lower().replace(' ', '_')}",
                    batch_size=len(slots)
                )
                break
            except OllamaTruncationError as te:
                if attempt == 0:
                    num_predict = min(4096, int(num_predict * 1.5))
                    log_event('MODEL_ERROR', f"Batch {q_type} hit length limit. Retrying with num_predict={num_predict}", job_id=self.job_id, level=logging.WARNING, model_name=model_name)
                    continue
                else:
                    raw_output = te.partial_response

        try:
            parsed = parse_and_repair_json(raw_output, job_id=self.job_id)
            extracted_list = extract_questions_list(parsed)
        except Exception as exc:
            log_event(
                'MODEL_ERROR',
                f"Batch parse failed for {q_type} ({len(slots)} items) with model '{model_name}': {str(exc)}",
                job_id=self.job_id,
                level=logging.WARNING,
                model_name=model_name
            )
            extracted_list = []

        # Map and normalize extracted questions to corresponding slots
        results = []
        for i, slot in enumerate(slots):
            raw_item = extracted_list[i] if i < len(extracted_list) else None

            if raw_item and isinstance(raw_item, dict):
                q = dict(raw_item)
            else:
                # Slot missed in batch, generate single slot
                q = self.generate_single_slot(slot, subject, model_name, words_per_mark_short=words_per_mark_short, words_per_mark_long=words_per_mark_long)

            # Normalization per type
            if q_type == 'MCQ':
                norm_q, err = normalize_mcq(q, seed=slot['slot_index'])
                if norm_q:
                    q.update(norm_q)
                else:
                    # Retry single slot if normalization failed
                    single_q = self.generate_single_slot(slot, subject, model_name)
                    norm_single, _ = normalize_mcq(single_q, seed=slot['slot_index'])
                    if norm_single:
                        q.update(norm_single)

            elif q_type == 'True/False':
                statement = q.get('statement') or q.get('question') or q.get('text') or ''
                ans_bool = q.get('answer')
                if isinstance(ans_bool, str):
                    ans_bool = (ans_bool.lower().strip() == 'true')
                q['question'] = statement
                q['text'] = statement
                q['answer'] = 'True' if ans_bool else 'False'
                q['options'] = ['True', 'False']

            elif q_type == 'Fill in the Blank':
                sentence = q.get('sentence') or q.get('question') or q.get('text') or ''
                ans = str(q.get('answer') or '').strip()
                if '_' not in sentence and ans and ans.lower() in sentence.lower():
                    pattern = re.compile(re.escape(ans), re.IGNORECASE)
                    sentence = pattern.sub('_____', sentence, count=1)
                q['question'] = sentence
                q['text'] = sentence
                q['options'] = []

            elif q_type == 'Short Answer':
                pts = q.get('answer_points') or []
                if isinstance(pts, list) and pts:
                    q['answer'] = "\n".join(f"- {p}" for p in pts)
                elif not q.get('answer'):
                    q['answer'] = q.get('model_answer') or ''
                rub = build_rubric('Short Answer', slot['marks'], pts, question_text=q.get('question', ''), model_answer=q.get('answer', ''))
                q['rubric'] = rub
                q['key_points'] = rub[0]['key_points']
                q['options'] = []

            elif q_type == 'Long Answer':
                pts = q.get('answer_points') or []
                if isinstance(pts, list) and pts:
                    formatted_pts = []
                    for pt in pts:
                        if isinstance(pt, dict):
                            h = pt.get('heading', '')
                            t = pt.get('text', '') or pt.get('detail', '')
                            formatted_pts.append(f"**{h}**: {t}" if h else t)
                        else:
                            formatted_pts.append(str(pt))
                    q['answer'] = "\n\n".join(formatted_pts)
                elif not q.get('answer'):
                    q['answer'] = q.get('model_answer') or ''
                rub = build_rubric('Long Answer', slot['marks'], pts, question_text=q.get('question', ''), model_answer=q.get('answer', ''))
                q['rubric'] = rub
                q['key_points'] = rub[0]['key_points']
                q['options'] = []

            # Blueprint authority: overwrite blueprint attributes
            q['slot_index'] = slot['slot_index']
            q['marks'] = slot['marks']
            q['difficulty'] = slot['difficulty']
            q['topic'] = slot.get('topic', 'General')
            q['type'] = slot['type']
            q['section_name'] = slot.get('section_name', slot['type'])
            text_val = str(q.get('text') or q.get('question') or q.get('prompt') or q.get('sentence') or q.get('statement') or '').strip()
            q['text'] = text_val
            q['question'] = text_val
            results.append(q)

        return results

    def generate_single_slot(
        self,
        slot: Dict[str, Any],
        subject: str,
        model_name: str,
        expansion_level: int = 0,
        words_per_mark_short: int = 35,
        words_per_mark_long: int = 55,
    ) -> Dict[str, Any]:
        """
        Generates candidate question for a single blueprint slot.
        Used for missing batch slots, repairs, and fallbacks.
        """
        q_type = slot['type']
        topic = slot.get('topic', 'General')
        difficulty = slot.get('difficulty', 'Medium')
        marks = slot.get('marks', 1)

        # Retrieve RAG context
        context = self.retriever.retrieve_context_for_slot(
            topic=topic,
            question_type=q_type,
            difficulty=difficulty,
            expansion_level=expansion_level
        )

        schema = None
        if q_type == 'MCQ':
            prompt = build_mcq_prompt(subject, topic, difficulty, marks, context)
            schema = MCQ_JSON_SCHEMA
            base_tok = 90
        elif q_type == 'True/False':
            prompt = build_true_false_prompt(subject, topic, difficulty, marks, context)
            schema = TRUE_FALSE_JSON_SCHEMA
            base_tok = 45
        elif q_type == 'Fill in the Blank':
            prompt = build_fill_blank_prompt(subject, topic, difficulty, marks, context)
            schema = FILL_BLANK_JSON_SCHEMA
            base_tok = 45
        elif q_type == 'Short Answer':
            prompt = build_short_prompt(subject, topic, difficulty, marks, context, words_per_mark=words_per_mark_short)
            schema = SHORT_JSON_SCHEMA
            base_tok = words_per_mark_short * marks + 40
        elif q_type == 'Long Answer':
            prompt = build_long_prompt(subject, topic, difficulty, marks, context, words_per_mark=words_per_mark_long)
            schema = LONG_JSON_SCHEMA
            base_tok = words_per_mark_long * marks + 40
        else:
            prompt = build_mcq_prompt(subject, topic, difficulty, marks, context)
            schema = MCQ_JSON_SCHEMA
            base_tok = 90

        temp = TEMPERATURE_BY_TYPE.get(q_type, 0.25)
        num_predict = min(4096, int(base_tok * 1.5) + 100)

        raw_output = ""
        for attempt in range(2):
            try:
                raw_output = self.client.generate(
                    model=model_name,
                    prompt=prompt,
                    system_prompt=BASE_SYSTEM_PROMPT,
                    json_mode=True,
                    format=schema,
                    temperature=temp,
                    num_predict=num_predict,
                    job_id=self.job_id,
                    stage=f"single_{q_type.lower().replace(' ', '_')}",
                    batch_size=1
                )
                break
            except OllamaTruncationError as te:
                if attempt == 0:
                    num_predict = min(4096, int(num_predict * 1.5))
                    continue
                raw_output = te.partial_response

        parsed = parse_and_repair_json(raw_output, job_id=self.job_id)
        extracted = extract_questions_list(parsed)
        item = dict(extracted[0]) if extracted else {}

        if item.get('insufficient') or item.get('_insufficient_context'):
            item['_insufficient_context'] = True
            return item

        # Blueprint authority
        item['slot_index'] = slot['slot_index']
        item['marks'] = slot['marks']
        item['difficulty'] = slot['difficulty']
        item['topic'] = topic
        item['type'] = q_type
        item['section_name'] = slot.get('section_name', q_type)

        if q_type == 'MCQ':
            norm, _ = normalize_mcq(item, seed=slot['slot_index'])
            if norm:
                item.update(norm)
        elif q_type == 'True/False':
            stmt = item.get('statement') or item.get('question') or ''
            item['question'] = stmt
            item['text'] = stmt
            item['options'] = ['True', 'False']
            ans = item.get('answer')
            if isinstance(ans, str):
                ans = (ans.lower().strip() == 'true')
            item['answer'] = 'True' if ans else 'False'
        elif q_type == 'Fill in the Blank':
            s = item.get('sentence') or item.get('question') or ''
            ans = str(item.get('answer') or '').strip()
            if '_' not in s and ans and ans.lower() in s.lower():
                pattern = re.compile(re.escape(ans), re.IGNORECASE)
                s = pattern.sub('_____', s, count=1)
            item['question'] = s
            item['text'] = s
            item['options'] = []
        elif q_type == 'Short Answer':
            q_txt = item.get('question') or item.get('text') or ''
            item['question'] = q_txt
            item['text'] = q_txt
            pts = item.get('answer_points') or []
            if isinstance(pts, list) and pts:
                item['answer'] = "\n".join(f"- {p}" for p in pts)
            elif not item.get('answer'):
                item['answer'] = item.get('model_answer') or ''
            rub = build_rubric('Short Answer', marks, pts, question_text=q_txt, model_answer=item.get('answer', ''))
            item['rubric'] = rub
            item['key_points'] = rub[0]['key_points']
            item['options'] = []
        elif q_type == 'Long Answer':
            q_txt = item.get('question') or item.get('text') or item.get('prompt') or ''
            item['question'] = q_txt
            item['text'] = q_txt
            pts = item.get('answer_points') or []
            if isinstance(pts, list) and pts:
                formatted_pts = []
                for pt in pts:
                    if isinstance(pt, dict):
                        h = pt.get('heading', '')
                        d = pt.get('text', '') or pt.get('detail', '') or pt.get('description', '')
                        formatted_pts.append(f"**{h}**: {d}" if (h and d) else (h or d))
                    else:
                        formatted_pts.append(str(pt))
                item['answer'] = "\n\n".join(formatted_pts)
            elif not item.get('answer'):
                item['answer'] = item.get('model_answer') or ''
            rub = build_rubric('Long Answer', marks, pts, question_text=q_txt, model_answer=item.get('answer', ''))
            item['rubric'] = rub
            item['key_points'] = rub[0]['key_points']
            item['options'] = []

        return item

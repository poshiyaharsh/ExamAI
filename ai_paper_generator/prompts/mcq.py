"""
MCQ Prompt Template (Section 5.2).
Model: qwen3:4b (English) / gemma3:4b (Multilingual)
Schema fields: question, correct, distractors (exactly 3), source_quote, difficulty.
"""
import copy
from typing import Any, Dict, List

MCQ_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "questions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "question": {"type": "string"},
                    "correct": {"type": "string"},
                    "distractors": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 3,
                        "maxItems": 3
                    },
                    "source_quote": {"type": "string"},
                    "difficulty": {"type": "string"}
                },
                "required": ["question", "correct", "distractors", "source_quote", "difficulty"],
                "additionalProperties": False
            }
        }
    },
    "required": ["questions"],
    "additionalProperties": False
}


def get_batch_mcq_schema(n: int) -> Dict[str, Any]:
    s = copy.deepcopy(MCQ_JSON_SCHEMA)
    s["properties"]["questions"]["minItems"] = n
    s["properties"]["questions"]["maxItems"] = n
    return s


def build_batch_mcq_prompt(
    subject: str,
    slots: List[Dict[str, Any]],
    context: str,
    unit: str = "General",
    language: str = "en"
) -> str:
    """Builds prompt to generate a batch of MCQs following Section 5.2."""
    n = len(slots)
    difficulties = [str(s.get('difficulty', 'medium')).lower() for s in slots]
    marks = slots[0].get('marks', 1) if slots else 1
    topics = list(set(s.get('topic', unit) for s in slots if s.get('topic')))
    topic_str = ", ".join(topics) if topics else unit

    prompt = f"""/no_think
Write exactly {n} multiple-choice questions.
Subject: {subject}
Unit/topic: {topic_str}
Difficulty of each question in order: {difficulties}
Marks per question: {marks}

CONTEXT:
{context}

Rules:
1. Each question tests one clear idea from the CONTEXT.
2. "correct" is the one correct answer, at most 12 words.
3. "distractors" are exactly 3 wrong but believable answers, similar in length and style to "correct", clearly wrong according to the CONTEXT, and different from each other.
4. Never use "all of the above", "none of the above" or "both A and B".
5. The question must not give away the answer.
6. "source_quote" is an exact piece of 8 to 25 words copied from the CONTEXT that proves the correct answer.
7. Every question covers a different fact.
8. Generate all {n} questions in the "questions" array."""

    if language and language != "en":
        from ..language import get_language_name
        lang_name = get_language_name(language)
        prompt += f"""
9. LANGUAGE REQUIREMENT: Write the question, correct answer, and distractors in {lang_name} ({language}) using its native script. Keep JSON keys ("question", "correct", "distractors", "source_quote", "difficulty") exactly in English. Keep technical terms, formulas, code, and proper nouns as in the CONTEXT."""

    prompt += "\n\nReturn only valid JSON matching the schema."
    return prompt


def build_mcq_prompt(
    subject: str,
    topic: str,
    difficulty: str,
    marks: int,
    context: str,
    language: str = "en"
) -> str:
    """Builds single-slot MCQ prompt."""
    slot = [{'topic': topic, 'difficulty': difficulty, 'marks': marks, 'slot_index': 1}]
    return build_batch_mcq_prompt(subject, slot, context, unit=topic, language=language)

"""
Fill in the Blank Prompt Template (Section 5.4).
Model: granite3.3:2b (English) / gemma3:4b (Multilingual)
"""
import copy
from typing import Any, Dict, List

FILL_BLANK_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "questions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "sentence": {"type": "string"},
                    "answer": {"type": "string"},
                    "source_quote": {"type": "string"},
                    "difficulty": {"type": "string"}
                },
                "required": ["sentence", "answer", "source_quote", "difficulty"],
                "additionalProperties": False
            }
        }
    },
    "required": ["questions"],
    "additionalProperties": False
}


def get_batch_fill_blank_schema(n: int) -> Dict[str, Any]:
    s = copy.deepcopy(FILL_BLANK_JSON_SCHEMA)
    s["properties"]["questions"]["minItems"] = n
    s["properties"]["questions"]["maxItems"] = n
    return s


def build_batch_fill_blank_prompt(
    subject: str,
    slots: List[Dict[str, Any]],
    context: str,
    unit: str = "General",
    language: str = "en"
) -> str:
    """Builds prompt for batch Fill in the Blank questions (Section 5.4)."""
    n = len(slots)
    difficulties = [str(s.get('difficulty', 'medium')).lower() for s in slots]
    topics = list(set(s.get('topic', unit) for s in slots if s.get('topic')))
    topic_str = ", ".join(topics) if topics else unit

    prompt = f"""Write exactly {n} fill-in-the-blank sentences.
Subject: {subject}
Unit/topic: {topic_str}
Difficulty of each sentence in order: {difficulties}

CONTEXT:
{context}

Rules:
1. Each sentence has exactly one blank written as _____ in place of one key term.
2. "answer" is 1 to 4 words, written exactly as in the CONTEXT.
3. The sentence must have enough meaning that only this answer fits. Never blank a trivial word such as an article, a pronoun or a common verb.
4. The answer must not appear anywhere else in the sentence.
5. "source_quote" is an exact piece of 8 to 25 words copied from the CONTEXT that contains the answer.
6. Every sentence covers a different fact.
7. Generate all {n} sentences in the "questions" array."""

    if language and language != "en":
        from ..language import get_language_name
        lang_name = get_language_name(language)
        prompt += f"""
8. LANGUAGE REQUIREMENT: Write the sentence and the answer in {lang_name} ({language}) using its native script with the _____ blank marker. Keep JSON keys exactly in English. Keep technical terms, formulas, code, and proper nouns as in the CONTEXT."""

    prompt += "\n\nReturn only valid JSON matching the schema."
    return prompt


def build_fill_blank_prompt(
    subject: str,
    topic: str,
    difficulty: str,
    marks: int,
    context: str,
    language: str = "en"
) -> str:
    slot = [{'topic': topic, 'difficulty': difficulty, 'marks': marks, 'slot_index': 1}]
    return build_batch_fill_blank_prompt(subject, slot, context, unit=topic, language=language)

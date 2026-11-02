"""
Long Answer Prompt Template (Section 5.6).
Model: llama3.2:3b (English) / gemma3:4b (Multilingual)
"""
import copy
from typing import Any, Dict, List

LONG_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "questions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "question": {"type": "string"},
                    "answer_points": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "heading": {"type": "string"},
                                "text": {"type": "string"}
                            },
                            "required": ["heading", "text"],
                            "additionalProperties": False
                        }
                    },
                    "source_quote": {"type": "string"},
                    "difficulty": {"type": "string"}
                },
                "required": ["question", "answer_points", "source_quote", "difficulty"],
                "additionalProperties": False
            }
        }
    },
    "required": ["questions"],
    "additionalProperties": False
}


def get_batch_long_schema(n: int) -> Dict[str, Any]:
    s = copy.deepcopy(LONG_JSON_SCHEMA)
    s["properties"]["questions"]["minItems"] = n
    s["properties"]["questions"]["maxItems"] = n
    return s


def build_batch_long_prompt(
    subject: str,
    slots: List[Dict[str, Any]],
    context: str,
    unit: str = "General",
    words_per_mark: int = 55,
    language: str = "en"
) -> str:
    """Builds prompt for batch Long Answer questions (Section 5.6)."""
    n = len(slots)
    marks = slots[0].get('marks', 5) if slots else 5
    points = min(8, marks)
    difficulties = [str(s.get('difficulty', 'medium')).lower() for s in slots]
    topics = list(set(s.get('topic', unit) for s in slots if s.get('topic')))
    topic_str = ", ".join(topics) if topics else unit

    prompt = f"""Write exactly {n} long-answer question(s) worth {marks} marks each.
Subject: {subject}
Unit/topic: {topic_str}
Difficulty: {difficulties}

CONTEXT:
{context}

Rules:
1. "question" MUST be a complete question sentence of 8 to 25 words that starts with a fitting word (Explain, Discuss, Describe, Compare, Analyse or Illustrate) and clearly specifies what topic to explain (e.g. "Explain the differences between lists and tuples in Python in detail."). NEVER output just a single word.
2. "answer_points" has exactly {points} items (one item per mark, at most 8). Each item has a "heading" of 2 to 6 words and a "text" of 1 to 2 sentences. The whole answer is about {words_per_mark} words per mark.
3. The points are different, in a logical order, and use only facts from the CONTEXT. No padding and no repeated sentences.
4. "source_quote" is an exact piece of 8 to 25 words copied from the CONTEXT.
5. Generate all {n} questions in the "questions" array."""

    if language and language != "en":
        from ..language import get_language_name
        lang_name = get_language_name(language)
        prompt += f"""
6. LANGUAGE REQUIREMENT: Write the question, headings, and detailed text points in {lang_name} ({language}) using its native script. Keep JSON keys ("question", "answer_points", "heading", "text", "source_quote", "difficulty") exactly in English. Keep technical terms, formulas, code, and proper nouns as in the CONTEXT."""

    prompt += "\n\nReturn only valid JSON matching the schema."
    return prompt


def build_long_prompt(
    subject: str,
    topic: str,
    difficulty: str,
    marks: int,
    context: str,
    words_per_mark: int = 55,
    language: str = "en"
) -> str:
    slot = [{'topic': topic, 'difficulty': difficulty, 'marks': marks, 'slot_index': 1}]
    return build_batch_long_prompt(subject, slot, context, unit=topic, words_per_mark=words_per_mark, language=language)

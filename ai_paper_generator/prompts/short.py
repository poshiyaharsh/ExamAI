"""
Short Answer Prompt Template (Section 5.5).
Model: llama3.2:3b (English) / gemma3:4b (Multilingual)
"""
import copy
from typing import Any, Dict, List

SHORT_JSON_SCHEMA = {
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
                        "items": {"type": "string"}
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


def get_batch_short_schema(n: int) -> Dict[str, Any]:
    s = copy.deepcopy(SHORT_JSON_SCHEMA)
    s["properties"]["questions"]["minItems"] = n
    s["properties"]["questions"]["maxItems"] = n
    return s


def build_batch_short_prompt(
    subject: str,
    slots: List[Dict[str, Any]],
    context: str,
    unit: str = "General",
    words_per_mark: int = 35,
    language: str = "en"
) -> str:
    """Builds prompt for batch Short Answer questions (Section 5.5)."""
    n = len(slots)
    marks = slots[0].get('marks', 2) if slots else 2
    difficulties = [str(s.get('difficulty', 'medium')).lower() for s in slots]
    topics = list(set(s.get('topic', unit) for s in slots if s.get('topic')))
    topic_str = ", ".join(topics) if topics else unit

    prompt = f"""Write exactly {n} short-answer questions worth {marks} marks each.
Subject: {subject}
Unit/topic: {topic_str}
Difficulty of each question in order: {difficulties}

CONTEXT:
{context}

Rules:
1. "question" MUST be a complete question sentence of 8 to 25 words that starts with a fitting word (Define, State, Explain, List, Differentiate or Describe) and clearly names the concept being tested (e.g. "Explain the differences between lists and tuples in Python.", "Define how dictionary lookup achieves O(1) time complexity."). NEVER output just a single word.
2. "answer_points" has exactly {marks} items. Each item is one clear, complete sentence of at most {words_per_mark} words, and each item is worth one mark.
3. The points are different from each other and use only facts from the CONTEXT.
4. "source_quote" is an exact piece of 8 to 25 words copied from the CONTEXT.
5. Generate all {n} questions in the "questions" array."""

    if language and language != "en":
        from ..language import get_language_name
        lang_name = get_language_name(language)
        prompt += f"""
6. LANGUAGE REQUIREMENT: Write the question, model answer, and all answer_points in {lang_name} ({language}) using its native script. Keep JSON keys exactly in English. Keep technical terms, formulas, code, and proper nouns as in the CONTEXT."""

    prompt += "\n\nReturn only valid JSON matching the schema."
    return prompt


def build_short_prompt(
    subject: str,
    topic: str,
    difficulty: str,
    marks: int,
    context: str,
    words_per_mark: int = 35,
    language: str = "en"
) -> str:
    slot = [{'topic': topic, 'difficulty': difficulty, 'marks': marks, 'slot_index': 1}]
    return build_batch_short_prompt(subject, slot, context, unit=topic, words_per_mark=words_per_mark, language=language)

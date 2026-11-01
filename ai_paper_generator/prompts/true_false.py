"""
True/False Prompt Template (Section 5.3).
Model: granite3.3:2b
Ensures 40% to 60% balance between True and False.
"""
import copy
from typing import Any, Dict, List

TRUE_FALSE_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "questions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "statement": {"type": "string"},
                    "answer": {"type": "boolean"},
                    "correction": {"type": "string"},
                    "source_quote": {"type": "string"},
                    "difficulty": {"type": "string"}
                },
                "required": ["statement", "answer", "correction", "source_quote", "difficulty"],
                "additionalProperties": False
            }
        }
    },
    "required": ["questions"],
    "additionalProperties": False
}


def get_batch_true_false_schema(n: int) -> Dict[str, Any]:
    s = copy.deepcopy(TRUE_FALSE_JSON_SCHEMA)
    s["properties"]["questions"]["minItems"] = n
    s["properties"]["questions"]["maxItems"] = n
    return s


def build_batch_true_false_prompt(
    subject: str,
    slots: List[Dict[str, Any]],
    context: str,
    unit: str = "General"
) -> str:
    """Builds prompt for batch True/False questions (Section 5.3)."""
    n = len(slots)
    n_true = n // 2
    n_false = n - n_true
    difficulties = [str(s.get('difficulty', 'medium')).lower() for s in slots]
    topics = list(set(s.get('topic', unit) for s in slots if s.get('topic')))
    topic_str = ", ".join(topics) if topics else unit

    return f"""Write exactly {n} true/false statements. Exactly {n_true} must be true and {n_false} must be false.
Subject: {subject}
Unit/topic: {topic_str}
Difficulty of each statement in order: {difficulties}

CONTEXT:
{context}

Rules:
1. Each statement is one complete, clear sentence about one fact.
2. A false statement is made by changing one key fact of a true statement (a term, number, cause or relation). Never make it false only by adding "not".
3. Avoid "always", "never", "all" and "only" unless the CONTEXT says so.
4. For false statements, "correction" is the correct statement in at most 15 words. For true statements it is an empty string.
5. "source_quote" is an exact piece of 8 to 25 words copied from the CONTEXT.
6. Every statement covers a different fact.
7. Generate all {n} statements in the "questions" array.

Return only valid JSON matching the schema."""


def build_true_false_prompt(
    subject: str,
    topic: str,
    difficulty: str,
    marks: int,
    context: str
) -> str:
    slot = [{'topic': topic, 'difficulty': difficulty, 'marks': marks, 'slot_index': 1}]
    return build_batch_true_false_prompt(subject, slot, context, unit=topic)

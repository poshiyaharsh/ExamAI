"""
Prompts for AI Validator (5.7), Batched Repair (5.8), and Distractor Repair (5.9).
"""
import json
from typing import Any, Dict, List

VALIDATOR_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "results": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "verdict": {"type": "string", "enum": ["pass", "fail"]},
                    "issues": {"type": "string"}
                },
                "required": ["id", "verdict", "issues"],
                "additionalProperties": False
            }
        }
    },
    "required": ["results"],
    "additionalProperties": False
}

DISTRACTOR_REPAIR_SCHEMA = {
    "type": "object",
    "properties": {
        "distractors": {
            "type": "array",
            "items": {"type": "string"}
        }
    },
    "required": ["distractors"],
    "additionalProperties": False
}


def build_validator_prompt(context: str, items: List[Dict[str, Any]]) -> str:
    """Builds prompt for Section 5.7 AI Validator (batches of 5)."""
    items_json = json.dumps(items, indent=2)
    return f"""You check exam items against the CONTEXT. For each item decide pass or fail. Fail if the answer is wrong or not supported by the CONTEXT, the answer does not answer the question, facts are invented, the answer is incomplete for its marks, or the question is unclear.

CONTEXT:
{context}

ITEMS:
{items_json}

Return only this JSON (issues at most 15 words, empty if pass):
{{"results":[{{"id":1,"verdict":"pass","issues":""}}]}}"""


def build_repair_prompt(
    item: Dict[str, Any],
    issues: str,
    context: str,
    q_type: str,
    marks: int
) -> str:
    """Builds prompt for Section 5.8 Repair."""
    item_json = json.dumps(item, indent=2)
    return f"""Fix this exam item so that it is correct and follows the rules. Use only the CONTEXT.
Type: {q_type}
Marks: {marks}

CONTEXT:
{context}

ITEM:
{item_json}

PROBLEMS:
{issues}

Return only the corrected item in the same JSON format as the item."""


def build_distractor_repair_prompt(
    question: str,
    correct: str,
    existing_distractors: List[str],
    context: str,
    k: int
) -> str:
    """Builds prompt for Section 5.9 Distractor Repair."""
    return f"""Question: {question}
Correct answer: {correct}
Already used wrong answers: {existing_distractors}

CONTEXT:
{context}

Write {k} more wrong but believable answers. They must be similar in length and style to the correct answer, clearly wrong according to the CONTEXT, and different from the correct answer and from each other.

Return only this JSON:
{{"distractors":[""]}}"""

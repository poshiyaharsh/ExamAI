import logging
from typing import Tuple
from .evaluation_service import evaluate_with_ollama, evaluate_with_rules

logger = logging.getLogger(__name__)


def evaluate_subjective_answer(question, student_answer, ollama_model=None) -> Tuple[float, str]:
    """
    Evaluates a subjective question against student answer using Ollama with automatic fallback.
    Returns: (score, feedback)
    """
    success, score, feedback, _, _ = evaluate_with_ollama(
        question=question,
        student_answer=student_answer,
        preferred_model=ollama_model,
    )
    if success:
        return score, feedback

    # Fallback to rules provider
    return evaluate_with_rules(question, student_answer)

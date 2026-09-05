from .ollama_client import call_ollama, parse_json_safely
from .prompts import build_evaluation_prompt


def evaluate_subjective_answer(question, student_answer, ollama_model):
    prompt = build_evaluation_prompt(
        question.text,
        question.model_answer,
        student_answer,
        question.marks,
    )
    result = parse_json_safely(call_ollama(ollama_model, prompt))
    try:
        score = float(result.get('score', 0))
    except (TypeError, ValueError):
        score = 0
    score = max(0, min(question.marks, score))
    feedback = str(result.get('feedback', '')).strip()
    return score, feedback

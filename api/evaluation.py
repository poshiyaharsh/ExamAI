from django.db import close_old_connections, transaction

from .models import StudentAnswer, StudentAttempt
from .utils.evaluate import evaluate_subjective_answer


def evaluate_attempt_subjectives(attempt_id):
    close_old_connections()
    try:
        attempt = StudentAttempt.objects.select_related('exam').get(id=attempt_id)
        answers = list(
            StudentAnswer.objects.select_related('question')
            .filter(attempt=attempt, question__question_type='subjective')
        )
        for answer in answers:
            if not answer.answer_text.strip():
                answer.score_awarded = 0
                answer.ai_feedback = 'No answer was submitted.'
            else:
                try:
                    answer.score_awarded, answer.ai_feedback = evaluate_subjective_answer(
                        answer.question,
                        answer.answer_text,
                        attempt.exam.ai_model_used,
                    )
                except Exception as exc:
                    answer.score_awarded = 0
                    answer.ai_feedback = f'Automatic evaluation failed: {exc}'
            answer.save(update_fields=['score_awarded', 'ai_feedback'])

        with transaction.atomic():
            attempt = StudentAttempt.objects.select_for_update().get(id=attempt_id)
            attempt.total_score = sum(
                answer.score_awarded or 0
                for answer in StudentAnswer.objects.filter(attempt=attempt)
            )
            attempt.status = StudentAttempt.Status.EVALUATED
            attempt.save(update_fields=['total_score', 'status'])
    finally:
        close_old_connections()

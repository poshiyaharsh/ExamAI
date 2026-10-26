import logging
import time
from django.db import close_old_connections, transaction

from .models import StudentAnswer, StudentAttempt
from .utils.evaluation_service import evaluate_subjective_chain
from api.utils.db_retry import is_lock_or_deadlock

logger = logging.getLogger(__name__)


def evaluate_attempt_subjectives(attempt_id, force=False):
    close_old_connections()
    try:
        attempt = StudentAttempt.objects.select_related('exam').get(id=attempt_id)
    except StudentAttempt.DoesNotExist:
        logger.info("Attempt ID=%s no longer exists, skipping subjective evaluation", attempt_id)
        return
    try:
        answers = list(
            StudentAnswer.objects.select_related('question')
            .filter(attempt=attempt, question__question_type__in=['subjective', 'short_answer', 'long_answer'])
        )
        for answer in answers:
            try:
                evaluate_subjective_chain(answer, force=force)
            except Exception as exc:
                logger.exception("Evaluation error on answer ID=%s", answer.id)
                answer.evaluation_status = StudentAnswer.EvaluationStatus.PENDING_REVIEW
                answer.evaluation_provider = "pending"
                answer.technical_error = f"Evaluation chain failed: {exc}"
                answer.ai_feedback = "Answer submitted successfully. Pending teacher evaluation."
                answer.save(update_fields=[
                    'evaluation_status', 'evaluation_provider', 'technical_error', 'ai_feedback'
                ])

        for attempt_idx in range(3):
            try:
                with transaction.atomic():
                    attempt = StudentAttempt.objects.select_for_update().get(id=attempt_id)
                    all_answers = list(StudentAnswer.objects.select_related('question').filter(attempt=attempt))
                    attempt.auto_total = round(sum(
                        float(ans.auto_marks or 0.0)
                        for ans in all_answers
                    ), 2)
                    attempt.final_total = round(sum(
                        float(ans.effective_marks)
                        for ans in all_answers
                    ), 2)
                    attempt.total_score = attempt.final_total
                    has_pending = any(
                        getattr(ans, 'ai_status', '') == 'pending'
                        for ans in all_answers
                        if ans.question.question_type in ['subjective', 'short_answer', 'long_answer']
                    )
                    if has_pending:
                        attempt.status = StudentAttempt.Status.SUBMITTED
                    elif attempt.status != StudentAttempt.Status.AUTO_SUBMITTED:
                        attempt.status = StudentAttempt.Status.EVALUATED
                    attempt.save(update_fields=['auto_total', 'final_total', 'total_score', 'status'])
                break
            except Exception as e:
                if is_lock_or_deadlock(e) and attempt_idx < 2:
                    time.sleep(0.1 * (2 ** attempt_idx))
                    continue
                raise
    finally:
        close_old_connections()

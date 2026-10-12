"""
Idempotent script to recalculate scores for old student exam submissions
that were misgraded or have 0.0 scores due to index comparison issues.
Run with: python scripts/recalculate_scores.py
"""
import os
import sys

# Setup Django environment
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings")

import django
django.setup()

from django.db import transaction
from api.models import StudentAttempt, StudentAnswer
from api.utils.scoring import is_objective_question, is_objective_answer_correct


def recalculate_old_scores(dry_run=False):
    attempts = StudentAttempt.objects.filter(
        status__in=[
            StudentAttempt.Status.SUBMITTED,
            StudentAttempt.Status.AUTO_SUBMITTED,
            StudentAttempt.Status.EVALUATED,
        ]
    ).select_related("exam", "student")

    print(f"Found {attempts.count()} completed attempt(s) to inspect.")
    updated_count = 0

    for attempt in attempts:
        exam = attempt.exam
        old_score = attempt.total_score
        answers = StudentAnswer.objects.filter(attempt=attempt).select_related("question")
        
        recalculated_score = 0.0
        has_changes = False

        with transaction.atomic():
            for answer in answers:
                question = answer.question
                if is_objective_question(question):
                    was_correct = answer.is_correct
                    now_correct = is_objective_answer_correct(question, answer.answer_text)
                    new_score = question.marks if now_correct else 0.0

                    if was_correct != now_correct or answer.score_awarded != new_score:
                        has_changes = True
                        if not dry_run:
                            answer.is_correct = now_correct
                            answer.score_awarded = new_score
                            answer.save(update_fields=["is_correct", "score_awarded"])
                    
                    recalculated_score += new_score
                else:
                    # Keep existing subjective score if already awarded
                    recalculated_score += (answer.score_awarded or 0.0)

            exam_total = exam.total_marks or 1
            percentage = round((recalculated_score / exam_total) * 100.0, 2)

            if recalculated_score != old_score or has_changes:
                updated_count += 1
                print(
                    f"Attempt #{attempt.id} (Student: {attempt.student.username}, Exam: {exam.title}): "
                    f"Score changed from {old_score} to {recalculated_score} ({percentage}% of {exam_total})"
                )
                if not dry_run:
                    attempt.total_score = recalculated_score
                    if attempt.status == StudentAttempt.Status.SUBMITTED:
                        # If no subjective answers pending, mark as evaluated
                        has_pending_subjective = any(
                            not is_objective_question(ans.question) and ans.score_awarded is None
                            for ans in answers
                        )
                        if not has_pending_subjective:
                            attempt.status = StudentAttempt.Status.EVALUATED
                    attempt.save(update_fields=["total_score", "status"])
            else:
                print(f"Attempt #{attempt.id} (Student: {attempt.student.username}): Score already accurate ({old_score}).")

    mode_str = "DRY RUN COMPLETE" if dry_run else "RECALCULATION COMPLETE"
    print(f"\n{mode_str}: {updated_count} attempt(s) updated.")
    return updated_count


if __name__ == "__main__":
    is_dry = "--dry-run" in sys.argv
    recalculate_old_scores(dry_run=is_dry)

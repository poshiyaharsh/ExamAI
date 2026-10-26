import logging
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from api.models import StudentAttempt, StudentAnswer

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Non-destructive backfill for evaluation override data on existing StudentAttempt and StudentAnswer records. "
        "Maps existing score_awarded to auto_marks and initializes review_status."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--apply',
            action='store_true',
            default=False,
            help='Apply changes to database. Defaults to dry-run mode if omitted.',
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=500,
            help='Batch size for bulk updates (default 500).',
        )

    def handle(self, *args, **options):
        is_apply = options['apply']
        batch_size = options['batch_size']
        mode_str = "APPLY" if is_apply else "DRY-RUN (No changes saved)"

        self.stdout.write(self.style.NOTICE(f"\n=== Evaluation Data Backfill [{mode_str}] ==="))

        # 1. Scan StudentAnswers
        answers_qs = StudentAnswer.objects.filter(auto_marks__isnull=True).select_related('question')
        total_answers_to_backfill = answers_qs.count()
        self.stdout.write(f"Answers needing backfill (auto_marks is NULL): {total_answers_to_backfill}")

        # 2. Scan StudentAttempts
        attempts_qs = StudentAttempt.objects.filter(auto_total=0.0, total_score__gt=0.0)
        total_attempts_to_backfill = attempts_qs.count()
        self.stdout.write(f"Attempts needing backfill: {total_attempts_to_backfill}")

        if not is_apply:
            self.stdout.write(self.style.SUCCESS(
                f"\n[DRY RUN SUMMARY]\n"
                f"- Would backfill {total_answers_to_backfill} student answers.\n"
                f"- Would backfill {total_attempts_to_backfill} student attempts.\n"
                f"Run with '--apply' to persist these updates."
            ))
            return

        # Execute backfill in batches
        updated_answers_count = 0
        answers_batch = []
        for ans in answers_qs.iterator(chunk_size=batch_size):
            ans.auto_marks = ans.score_awarded if ans.score_awarded is not None else 0.0
            ans.auto_is_correct = ans.is_correct
            ans.auto_feedback = ans.ai_feedback or ans.teacher_feedback or ""
            if ans.evaluation_status == StudentAnswer.EvaluationStatus.EVALUATED_AI:
                ans.auto_source = 'ai'
                ans.ai_status = 'ready'
            elif ans.evaluation_status == StudentAnswer.EvaluationStatus.EVALUATED_RULES:
                ans.auto_source = 'rule'
            elif not ans.answer_text and not ans.blank_answers:
                ans.auto_source = 'empty'
            else:
                ans.auto_source = 'none'

            ans.auto_evaluated_at = ans.saved_at or timezone.now()
            answers_batch.append(ans)

            if len(answers_batch) >= batch_size:
                StudentAnswer.objects.bulk_update(
                    answers_batch,
                    ['auto_marks', 'auto_is_correct', 'auto_feedback', 'auto_source', 'ai_status', 'auto_evaluated_at']
                )
                updated_answers_count += len(answers_batch)
                answers_batch = []

        if answers_batch:
            StudentAnswer.objects.bulk_update(
                answers_batch,
                ['auto_marks', 'auto_is_correct', 'auto_feedback', 'auto_source', 'ai_status', 'auto_evaluated_at']
            )
            updated_answers_count += len(answers_batch)

        # Update attempts
        updated_attempts_count = 0
        attempts_batch = []
        for att in attempts_qs.iterator(chunk_size=batch_size):
            att.auto_total = float(att.total_score or 0.0)
            att.final_total = float(att.total_score or 0.0)
            if att.status == StudentAttempt.Status.EVALUATED:
                att.review_status = StudentAttempt.ReviewStatus.FINALIZED
                att.finalized_at = att.submitted_at or timezone.now()
            else:
                att.review_status = StudentAttempt.ReviewStatus.AUTO_EVALUATED

            attempts_batch.append(att)
            if len(attempts_batch) >= batch_size:
                StudentAttempt.objects.bulk_update(
                    attempts_batch,
                    ['auto_total', 'final_total', 'review_status', 'finalized_at']
                )
                updated_attempts_count += len(attempts_batch)
                attempts_batch = []

        if attempts_batch:
            StudentAttempt.objects.bulk_update(
                attempts_batch,
                ['auto_total', 'final_total', 'review_status', 'finalized_at']
            )
            updated_attempts_count += len(attempts_batch)

        self.stdout.write(self.style.SUCCESS(
            f"\n[APPLIED SUCCESSFULLY]\n"
            f"- Backfilled {updated_answers_count} student answers.\n"
            f"- Backfilled {updated_attempts_count} student attempts.\n"
        ))

import logging
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q

from api.models import StudentAnswer, StudentAttempt
from api.utils.evaluation_service import evaluate_subjective_chain

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Re-evaluates pending or failed subjective answers using the evaluation fallback chain."

    def add_arguments(self, parser):
        parser.add_argument(
            '--apply',
            action='store_true',
            help='Apply changes to database. Default is dry-run mode.',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Run in dry-run mode without modifying data (default behavior).',
        )
        parser.add_argument(
            '--attempt-id',
            type=int,
            default=None,
            help='Target a specific attempt ID (e.g. --attempt-id 13).',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force re-evaluation even if status is already reviewed or evaluated.',
        )

    def handle(self, *args, **options):
        apply_changes = bool(options.get('apply')) and not bool(options.get('dry_run'))
        attempt_id = options.get('attempt_id')
        force = bool(options.get('force'))

        mode_str = "APPLY" if apply_changes else "DRY-RUN"
        self.stdout.write(self.style.NOTICE(f"\n=== Subjective Evaluation Service ({mode_str} MODE) ==="))

        qs = StudentAnswer.objects.select_related('attempt', 'question', 'attempt__exam', 'attempt__student').filter(
            question__question_type='subjective'
        )

        if attempt_id:
            qs = qs.filter(attempt_id=attempt_id)

        if not force:
            qs = qs.filter(
                Q(evaluation_status__in=[
                    StudentAnswer.EvaluationStatus.PENDING_REVIEW,
                    StudentAnswer.EvaluationStatus.FAILED,
                ])
                | Q(ai_feedback__icontains='Automatic evaluation failed')
                | Q(ai_feedback__icontains='HTTP 404')
                | Q(score_awarded__isnull=True)
            ).exclude(evaluation_status=StudentAnswer.EvaluationStatus.REVIEWED)

        answers = list(qs.order_by('attempt_id', 'id'))
        total_checked = len(answers)

        if total_checked == 0:
            self.stdout.write(self.style.SUCCESS("No pending or failed subjective answers found matching criteria."))
            return

        self.stdout.write(f"Found {total_checked} subjective answer(s) to process:\n")
        header = f"{'Ans ID':<8} {'Attempt':<9} {'Student':<24} {'Q ID':<7} {'Marks':<7} {'Status':<16} {'Score':<8} {'Provider':<10}"
        self.stdout.write(header)
        self.stdout.write("-" * len(header))

        for ans in answers:
            student_name = ans.attempt.student.username[:22] if ans.attempt and ans.attempt.student else 'Unknown'
            max_m = float(ans.question.marks or 10.0)
            score_disp = f"{ans.score_awarded}/{max_m}" if ans.score_awarded is not None else f"None/{max_m}"
            status_disp = ans.evaluation_status or 'unassigned'
            provider_disp = ans.evaluation_provider or '-'
            self.stdout.write(
                f"{ans.id:<8} {ans.attempt_id:<9} {student_name:<24} {ans.question_id:<7} {max_m:<7.1f} {status_disp:<16} {score_disp:<8} {provider_disp:<10}"
            )

        if not apply_changes:
            self.stdout.write(self.style.WARNING(
                f"\n[DRY-RUN COMPLETE] Checked: {total_checked}. No database modifications were made."
                f"\nTo apply re-evaluation through the fallback chain, run with: --apply"
            ))
            return

        # Apply mode
        self.stdout.write(self.style.NOTICE("\nExecuting evaluation fallback chain..."))
        evaluated_ai_count = 0
        evaluated_rules_count = 0
        failed_count = 0
        affected_attempt_ids = set()

        for idx, ans in enumerate(answers, 1):
            affected_attempt_ids.add(ans.attempt_id)
            self.stdout.write(f"[{idx}/{total_checked}] Evaluating Answer ID {ans.id} (Attempt {ans.attempt_id}, Q{ans.question_id})...", ending=" ")
            try:
                res = evaluate_subjective_chain(ans, force=force)
                st = res.get('status')
                sc = res.get('score')
                prov = res.get('provider')
                mod = res.get('model')

                if st == StudentAnswer.EvaluationStatus.EVALUATED_AI:
                    evaluated_ai_count += 1
                    self.stdout.write(self.style.SUCCESS(f"AI SUCCESS [{mod}] -> Score: {sc}"))
                elif st == StudentAnswer.EvaluationStatus.EVALUATED_RULES:
                    evaluated_rules_count += 1
                    self.stdout.write(self.style.WARNING(f"RULES FALLBACK [{mod}] -> Score: {sc}"))
                else:
                    failed_count += 1
                    self.stdout.write(self.style.ERROR(f"PENDING/FAILED -> Status: {st}"))
            except Exception as exc:
                failed_count += 1
                logger.exception("Failed evaluating answer %s", ans.id)
                self.stdout.write(self.style.ERROR(f"EXCEPTION: {exc}"))

        # Recalculate attempt total scores and statuses
        self.stdout.write(self.style.NOTICE("\nUpdating student attempt totals and statuses..."))
        for att_id in affected_attempt_ids:
            with transaction.atomic():
                att = StudentAttempt.objects.select_for_update().get(id=att_id)
                all_ans = list(StudentAnswer.objects.select_related('question').filter(attempt=att))
                new_total = sum(float(a.score_awarded or 0.0) for a in all_ans)
                has_pending = any(
                    a.evaluation_status in [
                        StudentAnswer.EvaluationStatus.PENDING_REVIEW,
                        StudentAnswer.EvaluationStatus.FAILED,
                    ]
                    for a in all_ans
                    if a.question.question_type == 'subjective'
                )
                att.total_score = round(new_total, 2)
                if has_pending:
                    att.status = StudentAttempt.Status.SUBMITTED
                else:
                    att.status = StudentAttempt.Status.EVALUATED
                att.save(update_fields=['total_score', 'status'])
                self.stdout.write(f"  Attempt {att_id}: New Total Score = {att.total_score}, Status = {att.status}")

        self.stdout.write(self.style.SUCCESS(
            f"\n=== SUMMARY ==="
            f"\nTotal checked: {total_checked}"
            f"\nEvaluated by AI: {evaluated_ai_count}"
            f"\nEvaluated by Rules: {evaluated_rules_count}"
            f"\nStill Pending / Failed: {failed_count}"
            f"\nAttempts updated: {len(affected_attempt_ids)}"
        ))

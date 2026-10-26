import logging
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.db import transaction

from api.models import (
    StudentAttempt,
    StudentAnswer,
    Question,
)
from api.utils.validate_paper import canonicalize_type
from api.utils.scoring import (
    is_objective_question,
    is_objective_answer_correct,
    evaluate_fill_blank,
)

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Audit and repair submitted attempts that have un-graded objective questions, missing answer rows, or stuck statuses. Default is --dry-run."

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            default=False,
            help="Apply the repairs to the database. If not specified, runs in dry-run mode.",
        )
        parser.add_argument(
            "--attempt-id",
            type=int,
            default=None,
            help="Audit and repair a specific attempt ID.",
        )

    def handle(self, *args, **options):
        is_apply = options["apply"]
        target_attempt_id = options.get("attempt_id")

        self.stdout.write(
            self.style.NOTICE(
                f"\n=== Starting Submitted Attempts Repair Audit (Mode: {'APPLY' if is_apply else 'DRY-RUN'}) ==="
            )
        )

        attempts_qs = StudentAttempt.objects.all().select_related("exam", "student", "institution")
        if target_attempt_id:
            attempts_qs = attempts_qs.filter(id=target_attempt_id)

        attempts = list(attempts_qs.order_by("id"))
        self.stdout.write(f"Found {len(attempts)} attempts to audit.\n")

        issues_summary = []

        for attempt in attempts:
            exam = attempt.exam
            if not exam:
                continue

            q_order = attempt.question_order or []
            existing_answers = {
                ans.question_id: ans
                for ans in StudentAnswer.objects.filter(attempt=attempt)
            }

            questions_by_id = {
                q.id: q
                for q in Question.objects.filter(exam=exam, id__in=q_order)
            }

            attempt_issues = []
            answers_to_create = []
            answers_to_update = []

            # 1. Check for missing answers for questions in question_order
            for q_id in q_order:
                if q_id not in existing_answers:
                    q = questions_by_id.get(q_id)
                    if q:
                        attempt_issues.append(f"Missing StudentAnswer row for Q#{q_id} ({q.question_type})")
                        canonical_qtype = canonicalize_type(q.question_type)
                        is_obj = is_objective_question(q)
                        answers_to_create.append(
                            StudentAnswer(
                                attempt=attempt,
                                institution=attempt.institution,
                                question=q,
                                answer_text="",
                                is_correct=False if is_obj else None,
                                score_awarded=0.0,
                                evaluation_status=StudentAnswer.EvaluationStatus.REVIEWED if is_obj else StudentAnswer.EvaluationStatus.PENDING_REVIEW,
                                evaluation_provider="deterministic" if is_obj else "pending",
                            )
                        )

            # 2. Check existing answers for un-graded objective questions or stuck subjective status
            for q_id, ans in existing_answers.items():
                q = ans.question or questions_by_id.get(q_id)
                if not q:
                    continue

                canonical_qtype = canonicalize_type(q.question_type)
                is_obj = is_objective_question(q)

                if is_obj:
                    # Objective questions should be deterministic and reviewed
                    needs_objective_score = (
                        ans.is_correct is None or
                        ans.score_awarded is None or
                        ans.evaluation_status != StudentAnswer.EvaluationStatus.REVIEWED
                    )
                    if needs_objective_score:
                        if canonical_qtype == "fill_blank":
                            score, is_corr, fb = evaluate_fill_blank(q, ans)
                        else:
                            is_corr = is_objective_answer_correct(q, ans.answer_text)
                            score = float(q.marks) if is_corr else 0.0
                            fb = "Correct" if is_corr else "Incorrect"

                        attempt_issues.append(
                            f"Objective Q#{q.id} ({canonical_qtype}) not finalized. Current score={ans.score_awarded}, calc={score}"
                        )
                        ans.is_correct = is_corr
                        ans.score_awarded = score
                        ans.ai_feedback = fb
                        ans.evaluation_status = StudentAnswer.EvaluationStatus.REVIEWED
                        ans.evaluation_provider = "deterministic"
                        answers_to_update.append(ans)
                else:
                    # Subjective questions: if status is legacy pending or evaluating, update to pending_review
                    if ans.evaluation_status in ["pending", "evaluating"]:
                        attempt_issues.append(
                            f"Subjective Q#{q.id} status stuck in '{ans.evaluation_status}' -> should be pending_review"
                        )
                        ans.evaluation_status = StudentAnswer.EvaluationStatus.PENDING_REVIEW
                        ans.evaluation_provider = "pending"
                        answers_to_update.append(ans)

            # 3. Check attempt status vs pending answers
            all_current_answers = list(existing_answers.values()) + answers_to_create
            computed_total = sum(Decimal(str(a.score_awarded or 0.0)) for a in all_current_answers)
            total_discrepancy = abs(Decimal(str(attempt.total_score or 0.0)) - computed_total) > Decimal("0.01")

            has_pending_subjectives = any(
                a.evaluation_status in ["pending", StudentAnswer.EvaluationStatus.PENDING_REVIEW, "evaluating"]
                for a in all_current_answers
            )

            expected_status = StudentAttempt.Status.SUBMITTED if has_pending_subjectives else StudentAttempt.Status.EVALUATED
            status_needs_update = attempt.status != expected_status and attempt.status in [
                StudentAttempt.Status.SUBMITTED,
                StudentAttempt.Status.EVALUATED,
                StudentAttempt.Status.AUTO_SUBMITTED,
            ]

            if total_discrepancy:
                attempt_issues.append(f"Score mismatch: recorded={attempt.total_score}, computed={computed_total}")

            if status_needs_update:
                attempt_issues.append(f"Status mismatch: recorded='{attempt.status}', expected='{expected_status}'")

            if attempt_issues:
                issues_summary.append({
                    "attempt_id": attempt.id,
                    "student": str(attempt.student),
                    "exam_id": exam.id,
                    "exam_title": exam.title,
                    "issues": attempt_issues,
                })

                if is_apply:
                    with transaction.atomic():
                        if answers_to_create:
                            StudentAnswer.objects.bulk_create(answers_to_create)
                        if answers_to_update:
                            for ans in answers_to_update:
                                ans.save()
                        if total_discrepancy or status_needs_update:
                            attempt.total_score = float(computed_total)
                            if status_needs_update:
                                attempt.status = expected_status
                            attempt.save(update_fields=["total_score", "status"])

        # Output Summary
        self.stdout.write("=" * 80)
        self.stdout.write(f"AUDIT RESULTS: {len(issues_summary)} attempts with issues out of {len(attempts)} audited.")
        self.stdout.write("=" * 80)

        for item in issues_summary:
            self.stdout.write(
                self.style.WARNING(
                    f"\nAttempt #{item['attempt_id']} | Student: {item['student']} | Exam #{item['exam_id']}: {item['exam_title']}"
                )
            )
            for iss in item["issues"]:
                self.stdout.write(f"  - {iss}")

        if not issues_summary:
            self.stdout.write(self.style.SUCCESS("\nAll audited attempts are consistent and healthy! No repairs needed."))
        elif not is_apply:
            self.stdout.write(
                self.style.NOTICE(
                    f"\nDRY-RUN COMPLETE: {len(issues_summary)} attempts can be repaired. Run with --apply to commit changes."
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"\nAPPLY COMPLETE: Successfully repaired {len(issues_summary)} attempts."
                )
            )

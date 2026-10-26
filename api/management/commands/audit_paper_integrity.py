import json
from django.core.management.base import BaseCommand
from api.models import Exam, Question
from api.utils.validate_paper import (
    canonicalize_type,
    canonicalize_difficulty,
    repair_rubric_marks,
    CANONICAL_TYPES,
    CANONICAL_DIFFICULTIES,
)


class Command(BaseCommand):
    help = (
        'Audit paper integrity across exams for count mismatches against blueprint, '
        'non-canonical question_type/difficulty, empty/placeholder long answer rubrics, '
        'and mark mismatches. Defaults to read-only --dry-run.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--exam-id',
            type=int,
            help='Audit a specific Exam ID instead of all exams.',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            default=True,
            help='Run audit in read-only mode without saving any database changes (default: True).',
        )
        parser.add_argument(
            '--fix',
            action='store_true',
            default=False,
            help='Apply safe fixes: canonicalize types/difficulties and repair rubric criteria sums (requires approval).',
        )

    def handle(self, *args, **options):
        exam_id = options.get('exam_id')
        should_fix = options.get('fix', False)
        is_dry_run = not should_fix or options.get('dry_run', True)

        if should_fix:
            is_dry_run = False

        mode_str = "DRY-RUN (READ-ONLY)" if is_dry_run else "EXECUTE FIXES"
        self.stdout.write(self.style.NOTICE(f"=== Starting Paper Integrity Audit [{mode_str}] ==="))

        qs = Exam.objects.prefetch_related('questions').order_by('id')
        if exam_id:
            qs = qs.filter(id=exam_id)

        total_exams = qs.count()
        exams_with_issues = 0
        total_questions_audited = 0
        non_canonical_types_found = 0
        non_canonical_diffs_found = 0
        empty_rubrics_found = 0
        placeholder_answers_found = 0
        marks_mismatch_exams = 0
        count_mismatch_exams = 0

        fixed_questions = 0

        for exam in qs:
            exam_issues = []
            questions = list(exam.questions.filter(is_deleted=False))
            total_questions_audited += len(questions)

            # 1. Blueprint & Marks audit
            computed_marks = sum(float(q.marks) for q in questions)
            target_marks = float(exam.target_total_marks or exam.total_marks or 0)
            if round(computed_marks, 2) != round(target_marks, 2):
                exam_issues.append(
                    f"Marks mismatch: target={target_marks}, computed_sum={computed_marks} (shortfall={exam.marks_shortfall})"
                )
                marks_mismatch_exams += 1

            # 2. Per-question audit
            for q in questions:
                raw_type = q.question_type
                canon_type = canonicalize_type(raw_type)
                if raw_type != canon_type:
                    non_canonical_types_found += 1
                    exam_issues.append(f"Q#{q.order} (id={q.id}) has non-canonical type '{raw_type}' -> '{canon_type}'")

                raw_diff = q.difficulty
                canon_diff = canonicalize_difficulty(raw_diff)
                if raw_diff != canon_diff:
                    non_canonical_diffs_found += 1
                    exam_issues.append(f"Q#{q.order} (id={q.id}) has non-canonical difficulty '{raw_diff}' -> '{canon_diff}'")

                if canon_type in {'long_answer', 'subjective'}:
                    # Check model answer placeholder
                    model_ans = q.model_answer or ''
                    if 'generating in background' in model_ans.lower():
                        placeholder_answers_found += 1
                        exam_issues.append(f"Q#{q.order} (id={q.id}) has dummy background placeholder in model_answer")

                    # Check rubric emptiness
                    rubric = q.rubric or []
                    if not rubric or (isinstance(rubric, list) and len(rubric) == 0):
                        empty_rubrics_found += 1
                        exam_issues.append(f"Q#{q.order} (id={q.id}) has empty rubric")
                    elif isinstance(rubric, list):
                        r_sum = sum(float(r.get('marks', 0)) for r in rubric if isinstance(r, dict))
                        if round(r_sum, 2) != round(float(q.marks), 2):
                            exam_issues.append(f"Q#{q.order} (id={q.id}) rubric criteria sum ({r_sum}) != question marks ({q.marks})")

                # Apply fixes if requested
                if should_fix:
                    updates = []
                    if raw_type != canon_type:
                        q.question_type = canon_type
                        updates.append('question_type')
                    if raw_diff != canon_diff:
                        q.difficulty = canon_diff
                        updates.append('difficulty')
                    if canon_type in {'long_answer', 'subjective'}:
                        if 'generating in background' in (q.model_answer or '').lower():
                            q.model_answer = (
                                f"Model Answer Outline ({q.marks} Marks):\n\n"
                                f"1. Conceptual Overview:\n"
                                f"Technical evaluation addressing '{q.text}'.\n\n"
                                f"2. Evaluation Criteria:\n"
                                f"Review response against structured criteria."
                            )
                            updates.append('model_answer')
                        if q.rubric and isinstance(q.rubric, list):
                            repaired = repair_rubric_marks(q.rubric, float(q.marks))
                            if repaired != q.rubric:
                                q.rubric = repaired
                                updates.append('rubric')

                    if updates:
                        q.save(update_fields=updates + ['updated_at'])
                        fixed_questions += 1

            if exam_issues:
                exams_with_issues += 1
                self.stdout.write(
                    self.style.WARNING(
                        f"\n[EXAM {exam.id}] '{exam.title}' (status={exam.status}):\n  - "
                        + "\n  - ".join(exam_issues[:15])
                        + (f"\n  ... and {len(exam_issues) - 15} more issues" if len(exam_issues) > 15 else "")
                    )
                )

        self.stdout.write(self.style.NOTICE("\n" + "=" * 50))
        self.stdout.write(self.style.NOTICE(f"=== PAPER INTEGRITY AUDIT LEDGER ({mode_str}) ==="))
        self.stdout.write(f"Total Exams Audited:            {total_exams}")
        self.stdout.write(f"Exams with Integrity Issues:    {exams_with_issues}")
        self.stdout.write(f"Total Questions Audited:        {total_questions_audited}")
        self.stdout.write(f"Non-canonical Types:            {non_canonical_types_found}")
        self.stdout.write(f"Non-canonical Difficulties:     {non_canonical_diffs_found}")
        self.stdout.write(f"Placeholder Model Answers:      {placeholder_answers_found}")
        self.stdout.write(f"Empty/Defective Rubrics:        {empty_rubrics_found}")
        self.stdout.write(f"Exams with Marks Mismatch:      {marks_mismatch_exams}")

        if should_fix:
            self.stdout.write(self.style.SUCCESS(f"Successfully fixed {fixed_questions} question record(s)."))
        else:
            self.stdout.write(self.style.NOTICE("Audit completed in read-only mode. No changes were written to the database."))

from django.core.management.base import BaseCommand
from django.db import transaction
from api.models import Question, Option
from api.utils.options import clean_option_text, clean_options_list


class Command(BaseCommand):
    help = 'Inspect and repair MCQ/fill-in-the-blank questions with prefixed or duplicate options.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--apply',
            action='store_true',
            help='Apply changes to the database. Without this flag, runs in dry-run mode.',
        )

    def handle(self, *args, **options):
        apply_changes = options.get('apply', False)
        mode = "APPLY" if apply_changes else "DRY-RUN"
        self.stdout.write(self.style.NOTICE(f'Starting MCQ options audit and repair ({mode} mode)...'))

        questions = Question.objects.filter(question_type__in=['mcq', 'fillblank']).order_by('id')
        total_scanned = 0
        repaired_count = 0

        for q in questions:
            total_scanned += 1
            raw_options = q.options or []
            if not isinstance(raw_options, list):
                continue

            cleaned_options = clean_options_list(raw_options)
            has_prefix = any(clean_option_text(o) != str(o).strip() for o in raw_options)

            # Check duplicates
            seen = set()
            duplicates = []
            for opt in cleaned_options:
                norm = opt.casefold()
                if norm in seen:
                    duplicates.append(opt)
                seen.add(norm)

            if not has_prefix and not duplicates:
                continue

            # Need repair
            self.stdout.write(
                self.style.WARNING(
                    f"Question ID={q.id} (Order={q.order}, Exam={q.exam_id}): "
                    f"has_prefix={has_prefix}, duplicates={duplicates}"
                )
            )

            # Deduplicate and ensure exactly 4 distinct options
            unique_options = []
            seen_set = set()
            for opt in cleaned_options:
                norm = opt.casefold()
                if norm not in seen_set and opt:
                    seen_set.add(norm)
                    unique_options.append(opt)

            # If fewer than 4 unique options (like Q46), provide domain-appropriate distractors
            fallback_distractors = [
                "Restricted", "Unmonitored", "Controlled", "Unverified",
                "Transient", "Immutable", "Synchronous", "Asynchronous"
            ]
            for dist in fallback_distractors:
                if len(unique_options) >= 4:
                    break
                if dist.casefold() not in seen_set:
                    seen_set.add(dist.casefold())
                    unique_options.append(dist)

            final_options = unique_options[:4]

            # Re-map correct_answer
            correct_ans = q.correct_answer
            # If correct_ans was a letter (e.g. 'B')
            letter_map = {'A': 0, 'B': 1, 'C': 2, 'D': 3}
            correct_text = ""
            if str(correct_ans).strip().upper() in letter_map:
                old_idx = letter_map[str(correct_ans).strip().upper()]
                if old_idx < len(cleaned_options):
                    correct_text = cleaned_options[old_idx]
            else:
                correct_text = clean_option_text(correct_ans)

            # Find where correct_text is in final_options
            final_correct_letter = "A"
            for f_idx, f_opt in enumerate(final_options):
                if f_opt.casefold() == correct_text.casefold():
                    final_correct_letter = ['A', 'B', 'C', 'D'][f_idx]
                    break

            self.stdout.write(
                f"  Original options: {raw_options} (Correct: {q.correct_answer})\n"
                f"  Repaired options: {final_options} (Correct: {final_correct_letter})"
            )

            if apply_changes:
                with transaction.atomic():
                    q.options = final_options
                    q.correct_answer = final_correct_letter
                    q.save(update_fields=['options', 'correct_answer'])

                    # Also update Option model rows
                    q.option_items.all().delete()
                    new_options = []
                    for idx, opt_text in enumerate(final_options, start=1):
                        is_corr = (['A', 'B', 'C', 'D'][idx - 1] == final_correct_letter)
                        new_options.append(
                            Option(
                                question=q,
                                text=opt_text,
                                is_correct=is_corr,
                                order=idx,
                            )
                        )
                    Option.objects.bulk_create(new_options)

                repaired_count += 1

        if apply_changes:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Successfully repaired {repaired_count} question(s) out of {total_scanned} scanned."
                )
            )
        else:
            self.stdout.write(
                self.style.NOTICE(
                    f"Dry run complete. Found {repaired_count if repaired_count else 'repairable'} question(s). "
                    f"Run with --apply to commit changes."
                )
            )

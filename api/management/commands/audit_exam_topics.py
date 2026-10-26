from django.core.management.base import BaseCommand
from api.models import Exam


class Command(BaseCommand):
    help = "Audit and safely clean stale/alien topics from Exam records that do not belong to actual exam questions."

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Prune stale topics and align exam.topics with accepted questions. Default is dry-run mode.",
        )
        parser.add_argument(
            "--exam-id",
            type=int,
            help="Audit or fix a specific exam by ID.",
        )

    def handle(self, *args, **options):
        apply_changes = options.get("apply", False)
        target_exam_id = options.get("exam_id")

        mode_str = "APPLY (CHANGES WILL BE PERSISTED)" if apply_changes else "DRY-RUN (NO CHANGES WILL BE MADE)"
        self.stdout.write(self.style.NOTICE(f"=== Exam Topics Audit [{mode_str}] ==="))

        exams = Exam.objects.prefetch_related("questions").all()
        if target_exam_id:
            exams = exams.filter(id=target_exam_id)

        audited_count = 0
        mismatch_count = 0
        fixed_count = 0

        for exam in exams:
            audited_count += 1
            stored_topics = exam.topics if isinstance(exam.topics, list) else []
            active_q_topics = list(
                exam.questions.filter(is_deleted=False)
                .exclude(topic_text__isnull=True)
                .exclude(topic_text="")
                .values_list("topic_text", flat=True)
            )

            # Unique active topics preserving order
            unique_q_topics = []
            for qt in active_q_topics:
                qt_clean = qt.strip()
                if qt_clean and qt_clean not in unique_q_topics:
                    unique_q_topics.append(qt_clean)

            stored_normalized = [t.strip().lower() for t in stored_topics if isinstance(t, str) and t.strip()]
            q_normalized = [t.lower() for t in unique_q_topics]

            # Alien/stale topics are in stored_topics but not in any question
            stale_topics = [t for t in stored_topics if isinstance(t, str) and t.strip().lower() not in q_normalized]

            if stale_topics and unique_q_topics:
                mismatch_count += 1
                self.stdout.write(
                    self.style.WARNING(
                        f"\nExam ID={exam.id} | Title='{exam.title}' | Questions={exam.questions.count()}\n"
                        f"  Stored Topics ({len(stored_topics)}): {stored_topics}\n"
                        f"  Actual Question Topics ({len(unique_q_topics)}): {unique_q_topics}\n"
                        f"  Stale/Alien Topics to prune ({len(stale_topics)}): {stale_topics}"
                    )
                )

                if apply_changes:
                    exam.topics = unique_q_topics
                    exam.save(update_fields=["topics"])
                    fixed_count += 1
                    self.stdout.write(self.style.SUCCESS(f"  -> Successfully updated exam.topics to: {unique_q_topics}"))

        self.stdout.write(
            self.style.NOTICE(
                f"\n=== Audit Complete ===\n"
                f"Total Exams Audited: {audited_count}\n"
                f"Exams with Stale/Alien Topics: {mismatch_count}\n"
                f"Exams Fixed: {fixed_count}\n"
                f"Mode: {'APPLIED' if apply_changes else 'DRY RUN ONLY'}"
            )
        )

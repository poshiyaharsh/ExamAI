from django.core.management.base import BaseCommand
from api.models import Exam, Question
from api.utils.validate_paper import audit_question_scope, normalize_grounding_text, verify_grounding_evidence


class Command(BaseCommand):
    help = (
        'Audit exam grounding: detect questions from other subjects or question banks '
        'in AI-generated exams that were supposed to be grounded strictly in uploaded syllabus material.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--exam-id',
            type=int,
            help='Audit a specific Exam ID.',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            default=True,
            help='Read-only dry run (default).',
        )
        parser.add_argument(
            '--fix',
            action='store_true',
            default=False,
            help='Fix contaminated draft exams by removing ungrounded foreign questions and recalculating marks.',
        )

    def handle(self, *args, **options):
        exam_id = options.get('exam_id')
        should_fix = options.get('fix', False)
        is_dry_run = not should_fix

        mode_str = "DRY-RUN (READ-ONLY)" if is_dry_run else "EXECUTE FIX"
        self.stdout.write(self.style.NOTICE(f"=== Starting Exam Grounding Audit [{mode_str}] ==="))

        qs = Exam.objects.prefetch_related('questions').order_by('id')
        if exam_id:
            qs = qs.filter(id=exam_id)

        contaminated_exams = []
        for exam in qs:
            syllabus_text = exam.source_syllabus_text or ''
            questions = list(exam.questions.filter(is_deleted=False).order_by('order'))
            if not questions:
                continue

            # Identify if this is an AI exam with uploaded syllabus
            has_syllabus = bool(syllabus_text.strip()) or bool(exam.source_documents)
            if not has_syllabus:
                continue

            foreign_questions = []
            grounded_questions = []

            for q in questions:
                # If question has source in bank/question_bank
                is_from_bank = q.source in ('bank', 'question_bank', 'bank_import')
                
                # Check scope against syllabus text
                audit = audit_question_scope(q, syllabus_text, selected_topics=exam.topics)
                in_scope = audit['in_scope']

                if is_from_bank or not in_scope:
                    foreign_questions.append({
                        'question': q,
                        'reason': 'From Question Bank' if is_from_bank else audit['reason'],
                        'is_bank': is_from_bank,
                    })
                else:
                    grounded_questions.append(q)

            if foreign_questions:
                contaminated_exams.append({
                    'exam': exam,
                    'total_count': len(questions),
                    'foreign_count': len(foreign_questions),
                    'grounded_count': len(grounded_questions),
                    'foreign_questions': foreign_questions,
                })

        self.stdout.write(f"\nTotal AI Exams Audited: {qs.count()}")
        self.stdout.write(self.style.WARNING(f"Contaminated AI Exams Found: {len(contaminated_exams)}\n"))

        for item in contaminated_exams:
            exam = item['exam']
            self.stdout.write(
                f"- Exam ID {exam.id} '{exam.title}' [Subject: {exam.subject}] - Status: {exam.status}: "
                f"{item['foreign_count']}/{item['total_count']} questions foreign/un-grounded!"
            )
            for fq in item['foreign_questions'][:3]:
                q = fq['question']
                self.stdout.write(f"    * Q#{q.order} (ID {q.id}, {q.question_type}, {q.marks}M): {fq['reason']} - '{q.text[:60]}...'")
            if len(item['foreign_questions']) > 3:
                self.stdout.write(f"    * ... and {len(item['foreign_questions']) - 3} more.")

            if should_fix and exam.status == Exam.Status.DRAFT:
                self.stdout.write(self.style.NOTICE(f"  Fixing Exam {exam.id}..."))
                # Remove foreign questions from draft exam
                foreign_ids = [fq['question'].id for fq in item['foreign_questions']]
                Question.objects.filter(id__in=foreign_ids, exam=exam).delete()
                
                # Re-order and re-calculate marks
                remaining = list(exam.questions.filter(is_deleted=False).order_by('order'))
                for new_idx, rq in enumerate(remaining, start=1):
                    rq.order = new_idx
                    rq.save(update_fields=['order'])

                new_total = sum(float(rq.marks) for rq in remaining)
                exam.total_marks = int(round(new_total))
                target = int(exam.target_total_marks or exam.total_marks)
                exam.marks_shortfall = max(0, target - exam.total_marks)
                exam.save(update_fields=['total_marks', 'marks_shortfall', 'updated_at'])
                self.stdout.write(self.style.SUCCESS(f"  Fixed Exam {exam.id}: {len(remaining)} grounded questions remaining ({exam.total_marks}/{target} marks)."))

        self.stdout.write(self.style.SUCCESS("\n=== Grounding Audit Complete ==="))

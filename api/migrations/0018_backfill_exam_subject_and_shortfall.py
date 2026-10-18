from django.db import migrations


def forwards_backfill_data(apps, schema_editor):
    Exam = apps.get_model('api', 'Exam')
    PaperGenerationJob = apps.get_model('api', 'PaperGenerationJob')

    for exam in Exam.objects.all():
        # Derive a short subject from the title (strip CH_..., Unit..., etc.)
        t = exam.title or ''
        title_short = t.split(" - ")[0].split(" CH_")[0].split(" Ch_")[0].split(" Unit")[0].strip()
        if not title_short or len(title_short) < 2:
            title_short = t[:60].strip()
        exam.subject = title_short[:60] or 'General'

        # Calculate actual sum of question marks
        questions = exam.questions.all()
        q_sum = sum(q.marks for q in questions)
        actual = int(round(float(q_sum))) if q_sum > 0 else (exam.total_marks or 0)
        exam.total_marks = actual

        # Determine target total marks
        if exam.id == 32:
            target = 100
        else:
            target = exam.total_marks if exam.total_marks > actual else actual
            if target == 0 and actual == 0:
                target = 100

        exam.target_total_marks = target
        exam.marks_shortfall = max(0, target - actual)

        # Backfill source_documents if syllabus text was present
        if exam.source_syllabus_text and not exam.source_documents:
            exam.source_documents = [{
                'filename': 'syllabus.pdf',
                'char_count': len(exam.source_syllabus_text),
                'source': 'migrated_syllabus'
            }]

        exam.save(update_fields=['subject', 'total_marks', 'target_total_marks', 'marks_shortfall', 'source_documents'])

    # Backfill jobs
    for job in PaperGenerationJob.objects.all():
        if job.exam:
            job.target_marks = job.exam.target_total_marks or job.exam.total_marks or 0
            job.actual_marks = job.exam.total_marks or 0
            job.marks_shortfall = job.exam.marks_shortfall or 0
            if job.exam.source_documents and not job.source_documents:
                job.source_documents = job.exam.source_documents
            job.save(update_fields=['target_marks', 'actual_marks', 'marks_shortfall', 'source_documents'])


def backwards_noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0017_exam_description_exam_marks_shortfall_and_more'),
    ]

    operations = [
        migrations.RunPython(forwards_backfill_data, backwards_noop),
    ]

import hashlib
import re
from django.db import migrations
from django.utils import timezone


def backfill_question_bank_data(apps, schema_editor):
    Question = apps.get_model('api', 'Question')
    Option = apps.get_model('api', 'Option')
    Subject = apps.get_model('api', 'Subject')
    Topic = apps.get_model('api', 'Topic')
    Exam = apps.get_model('api', 'Exam')

    type_map = {
        'mcq': 'MCQ_SINGLE',
        'truefalse': 'TRUE_FALSE',
        'fillblank': 'SHORT_ANSWER',
        'subjective': 'LONG_ANSWER',
    }
    diff_map = {
        'easy': 'EASY',
        'medium': 'MEDIUM',
        'hard': 'HARD',
    }

    subject_cache = {}
    topic_cache = {}

    def get_or_create_subject(inst_id, dept, name):
        key = (inst_id, dept, name)
        if key in subject_cache:
            return subject_cache[key]
        sub, _ = Subject.objects.get_or_create(
            institution_id=inst_id,
            department=dept,
            name=name,
            defaults={'code': name[:10].upper().replace(' ', '_')},
        )
        subject_cache[key] = sub
        return sub

    def get_or_create_topic(inst_id, subject_obj, topic_name):
        if not topic_name or not topic_name.strip():
            return None
        cleaned_tname = topic_name.strip()
        key = (subject_obj.id, cleaned_tname)
        if key in topic_cache:
            return topic_cache[key]
        top, _ = Topic.objects.get_or_create(
            institution_id=inst_id,
            subject=subject_obj,
            name=cleaned_tname[:200],
        )
        topic_cache[key] = top
        return top

    seen_bank_hashes = set()

    for q in Question.objects.select_related('exam').all():
        cleaned_text = re.sub(r'\s+', ' ', (q.text or '').strip().lower())
        h = hashlib.sha256(cleaned_text.encode('utf-8')).hexdigest()
        q.text_hash = h

        exam_dept = q.exam.department if q.exam and q.exam.department else 'Computer Science'
        q.department = exam_dept

        if q.question_type in type_map:
            q.question_type = type_map[q.question_type]
        if q.difficulty in diff_map:
            q.difficulty = diff_map[q.difficulty]

        q.status = 'ACTIVE'
        if q.exam and q.exam.created_by:
            q.created_by = q.exam.created_by
        if q.exam and hasattr(q.exam, 'created_at') and q.exam.created_at:
            q.created_at = q.exam.created_at

        # Determine subject name
        subject_name = (q.exam.title if q.exam and q.exam.title else 'Computer Science')
        if re.match(r'^Exam_\d+', subject_name, re.IGNORECASE):
            subject_name = 'Computer Science'
        sub = get_or_create_subject(q.institution_id, exam_dept, subject_name)

        # Create/link Topic if topic_text exists
        if q.topic_text:
            top = get_or_create_topic(q.institution_id, sub, q.topic_text)
            q.topic = top

        bank_key = (q.institution_id, sub.id, h)
        if bank_key not in seen_bank_hashes:
            seen_bank_hashes.add(bank_key)
            q.subject = sub
        else:
            q.subject = None

        q.save()

        # Migrate JSON options to Option records
        if q.options and isinstance(q.options, list) and not Option.objects.filter(question=q).exists():
            correct_ans = q.correct_answer
            correct_str = str(correct_ans).strip().lower() if correct_ans is not None else ''

            option_objects = []
            for idx, opt in enumerate(q.options, start=1):
                opt_str = str(opt).strip()
                is_correct = False
                if correct_ans is not None:
                    if isinstance(correct_ans, list):
                        is_correct = opt_str.lower() in [str(c).strip().lower() for c in correct_ans]
                    else:
                        is_correct = (opt_str.lower() == correct_str) or (str(idx - 1) == correct_str)
                option_objects.append(
                    Option(
                        question=q,
                        text=opt_str,
                        is_correct=is_correct,
                        order=idx,
                    )
                )
            if option_objects:
                Option.objects.bulk_create(option_objects)


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0009_alter_question_options_question_created_at_and_more'),
    ]

    operations = [
        migrations.RunPython(backfill_question_bank_data, noop_reverse),
    ]

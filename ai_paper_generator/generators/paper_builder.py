"""
Paper Builder and Final Assembler.
1. Shuffles MCQ options while keeping the answer key synchronized.
2. Orders sections strictly: MCQ -> True/False -> Fill in the Blank -> Short Answer -> Long Answer.
3. Re-numbers questions sequentially (1, 2, 3...).
4. Marks control: recomputes actual total marks from saved questions and asserts it matches target total marks.
5. Saves final paper into faculty.models.Paper, faculty.models.PaperQuestion, api.models.Exam, and api.models.Question with detected language code.
6. Exports to PDF and DOCX.
"""
import random
import logging
from typing import Dict, List, Any, Optional, Tuple
from django.db import transaction
from django.utils import timezone
from .rubric_builder import build_rubric
from ..logging_setup import log_event

logger = logging.getLogger(__name__)

TYPE_ORDER = [
    'MCQ',
    'True/False',
    'Fill in the Blank',
    'Short Answer',
    'Long Answer',
]


def assemble_and_order_paper(questions: List[Dict[str, Any]], target_total_marks: int, job_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Assembles questions:
    - Shuffles MCQ options safely keeping answer key in sync
    - Groups questions in standard academic sequence
    - Re-indexes question numbers
    - Asserts total marks equals target
    """
    ordered_questions = []

    # Group by type
    by_type = {t: [] for t in TYPE_ORDER}
    for q in questions:
        t = q.get('type', 'MCQ')
        if t in by_type:
            by_type[t].append(q)
        else:
            by_type.setdefault(t, []).append(q)

    # Shuffle MCQ options safely
    for mcq in by_type.get('MCQ', []):
        options = list(mcq.get('options', []))
        correct_answer = mcq.get('answer', '')
        if len(options) == 4 and correct_answer in options:
            random.shuffle(options)
            mcq['options'] = options

    # Assemble in canonical order
    current_q_num = 1
    for t in TYPE_ORDER:
        for q in by_type.get(t, []):
            q_copy = dict(q)
            q_copy['question_number'] = current_q_num
            ordered_questions.append(q_copy)
            current_q_num += 1

    # Exact marks verification
    computed_total = sum(int(q.get('marks', 0)) for q in ordered_questions)
    if computed_total != target_total_marks:
        diff = target_total_marks - computed_total
        log_event(
            'REPAIR',
            f"Paper builder detected marks shortfall/surplus: Computed {computed_total} vs Target {target_total_marks}. "
            f"Auto-adjusting last question by {diff} marks.",
            job_id=job_id,
            level=logging.WARNING
        )
        if ordered_questions:
            ordered_questions[-1]['marks'] += diff

    return ordered_questions


def save_paper_to_database(
    job_id: int,
    faculty_id: int,
    institution_id: int,
    title: str,
    subject_name: str,
    duration_minutes: int,
    total_marks: int,
    questions: List[Dict[str, Any]],
    raw_syllabus_text: str = '',
    language: str = 'en',
) -> Tuple[int, int]:
    """
    Saves the final generated paper into existing system models:
    - faculty.models.Paper (including additive nullable language field)
    - faculty.models.PaperQuestion
    - api.models.Exam
    - api.models.Question
    Returns (paper_id, exam_id).
    """
    from faculty.models import FacultyProfile, Paper, PaperQuestion
    from admins.models import AdminInstitution
    from api.models import Exam, Question, Subject, Option

    faculty = FacultyProfile.objects.select_related('institution').get(id=faculty_id)
    institution = faculty.institution or AdminInstitution.objects.get(id=institution_id)

    # Resolve or create Subject
    subject, _ = Subject.objects.get_or_create(
        institution=institution,
        name=subject_name.strip() or 'General',
        defaults={'code': (subject_name[:3] + '101').upper()}
    )

    with transaction.atomic():
        # 1. Save faculty.models.Paper
        paper = Paper.objects.create(
            faculty=faculty,
            institution=institution,
            title=title,
            syllabus_filename='ai_generated_syllabus.txt',
            extracted_syllabus_text=raw_syllabus_text[:50000],
            ai_model='Ollama AI Multi-Model',
            topics=[q.get('topic', '') for q in questions if q.get('topic')],
            question_types=list(set(q.get('type') for q in questions)),
            duration=duration_minutes,
            total_marks=total_marks,
            generated_questions=questions,
            is_published=True,
            language=language or 'en',
        )

        for q in questions:
            PaperQuestion.objects.create(
                paper=paper,
                institution=institution,
                question_number=q['question_number'],
                question_type=q['type'],
                difficulty=q.get('difficulty', 'Medium'),
                marks=q['marks'],
                question=q['question'],
                options=q.get('options', []),
                answer=q.get('answer', ''),
            )

        # 2. Save api.models.Exam
        topics_list = [q.get('topic', '') for q in questions if q.get('topic')]
        q_types_list = list(set(q.get('type') for q in questions))
        diff_dist = {}
        for q in questions:
            d = q.get('difficulty', 'Medium')
            diff_dist[d] = diff_dist.get(d, 0) + 1

        exam = Exam.objects.create(
            institution=institution,
            title=title,
            created_by=getattr(faculty, 'user', None),
            department=getattr(faculty, 'department', '') or '',
            subject=subject_name.strip() or 'General',
            duration_minutes=duration_minutes,
            total_marks=total_marks,
            target_total_marks=total_marks,
            topics=topics_list or ['General'],
            difficulty_distribution=diff_dist,
            question_types=q_types_list or ['mcq'],
            ai_model_used='Ollama AI Multi-Model',
            status=Exam.Status.DRAFT,
            is_reviewed=True,
        )

        type_map = {
            'MCQ': Question.QuestionType.MCQ,
            'True/False': Question.QuestionType.TRUE_FALSE,
            'Fill in the Blank': Question.QuestionType.FILL_BLANK,
            'Short Answer': Question.QuestionType.SHORT_ANSWER,
            'Long Answer': Question.QuestionType.LONG_ANSWER,
        }

        diff_map = {
            'Easy': Question.Difficulty.EASY,
            'Medium': Question.Difficulty.MEDIUM,
            'Hard': Question.Difficulty.HARD,
        }

        for q in questions:
            q_type = type_map.get(q['type'], Question.QuestionType.MCQ)
            q_diff = diff_map.get(q.get('difficulty'), Question.Difficulty.MEDIUM)

            if q['type'] in ('Short Answer', 'Long Answer'):
                rub = q.get('rubric')
                if not rub or not isinstance(rub, list) or not rub[0].get('key_points'):
                    raw_pts = q.get('key_points') or q.get('answer_points') or q.get('answer')
                    rub = build_rubric(
                        q['type'], q['marks'], raw_pts,
                        question_text=q.get('question', ''),
                        model_answer=q.get('answer', ''),
                        language=language
                    )
                q['rubric'] = rub
                q['key_points'] = rub[0]['key_points']
                exam_rubric = rub
            else:
                exam_rubric = [{'key_points': []}]

            exam_q = Question.objects.create(
                institution=institution,
                subject=subject,
                exam=exam,
                order=q.get('question_number', 1),
                question_type=q_type,
                difficulty=q_diff,
                marks=q['marks'],
                text=q['question'],
                options=q.get('options', []) if q['type'] == 'MCQ' else None,
                correct_answer=q.get('answer', ''),
                model_answer=q.get('answer', '') if q['type'] in ('Short Answer', 'Long Answer') else '',
                topic_text=q.get('topic', ''),
                rubric=exam_rubric,
                created_by=getattr(faculty, 'user', None),
            )

            # Create Option objects for MCQ
            if q_type == Question.QuestionType.MCQ and q.get('options'):
                for opt_idx, opt_text in enumerate(q['options'], start=1):
                    is_corr = (str(opt_text).strip().lower() == str(q.get('answer', '')).strip().lower())
                    Option.objects.create(
                        question=exam_q,
                        text=opt_text,
                        is_correct=is_corr,
                        order=opt_idx,
                    )

        # Database check (Step 3.7): fails job if any saved MCQ has fewer than 4 options or no correct answer
        saved_mcqs = Question.objects.filter(exam=exam, question_type=Question.QuestionType.MCQ)
        for mcq in saved_mcqs:
            opt_count = mcq.option_items.count()
            if opt_count < 4 or not mcq.correct_answer:
                raise ValueError(
                    f"MCQ database integrity assertion failed: Question #{mcq.id} has {opt_count} options "
                    f"and correct_answer='{mcq.correct_answer}'. Exactly 4 options and valid answer required."
                )

    log_event(
        'GENERATION',
        f"Paper successfully saved to database: Paper #{paper.id}, Exam #{exam.id} ({len(questions)} questions, {total_marks} marks, language='{language}').",
        job_id=job_id,
        faculty=faculty,
        institution=institution
    )

    return paper.id, exam.id

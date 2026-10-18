from copy import deepcopy
import re
from .options import clean_option_text, clean_options_list, validate_mcq_options


VALID_TYPES = {
    'mcq', 'true_false', 'fill_blank', 'short_answer', 'long_answer',
    # Legacy aliases
    'truefalse', 'fillblank', 'subjective'
}
VALID_DIFFICULTIES = {'easy', 'medium', 'hard'}
OBJECTIVE_TYPES = {'mcq', 'true_false', 'fill_blank', 'truefalse', 'fillblank'}
OPTION_LABELS = ('A', 'B', 'C', 'D', 'E', 'F')


def canonicalize_type(q_type: str) -> str:
    norm = str(q_type or '').strip().lower()
    if norm in {'truefalse', 'true_false'}:
        return 'true_false'
    if norm in {'fillblank', 'fill_blank'}:
        return 'fill_blank'
    if norm in {'subjective', 'long_answer'}:
        return 'long_answer'
    if norm == 'short_answer':
        return 'short_answer'
    return 'mcq'


def _normalise_correct_answer(question_type, raw_answer, options):
    canon = canonicalize_type(question_type)
    if canon == 'true_false':
        if isinstance(raw_answer, bool):
            return 'True' if raw_answer else 'False'
        answer = str(raw_answer or '').strip().casefold()
        if answer in {'a', 'true', 't', '1'}:
            return 'True'
        if answer in {'b', 'false', 'f', '0'}:
            return 'False'
        return 'True'

    if canon == 'mcq':
        if isinstance(raw_answer, int) and 0 <= raw_answer < len(options or []):
            return OPTION_LABELS[raw_answer]
        answer = str(raw_answer or '').strip()
        if answer.upper() in OPTION_LABELS[:len(options or [])]:
            return answer.upper()
        norm_answer = clean_option_text(answer).casefold()
        for index, option in enumerate(options or []):
            if norm_answer == clean_option_text(option).casefold():
                return OPTION_LABELS[index]
        return 'A'

    if canon == 'fill_blank':
        if isinstance(raw_answer, list) and raw_answer:
            return str(raw_answer[0]).strip()
        return str(raw_answer or '').strip()

    return raw_answer


def compute_question_counts(question_types, total_marks, blueprint=None):
    """
    Computes exact question counts per type and marks.
    If blueprint is provided (from wizard), respects blueprint counts and marks per type.
    Otherwise computes proportional defaults.
    """
    if blueprint and isinstance(blueprint, dict):
        counts = {}
        type_marks = {}
        for q_type, config in blueprint.items():
            if isinstance(config, dict) and config.get('enabled', True):
                c = int(config.get('count', 0))
                m = float(config.get('marksPerQuestion', config.get('marks', 1)))
                if c > 0:
                    c_type = canonicalize_type(q_type)
                    counts[c_type] = c
                    type_marks[c_type] = m
        if counts:
            actual_total = sum(counts[t] * type_marks[t] for t in counts)
            return counts, actual_total

    selected_types = [canonicalize_type(t) for t in (question_types or ['mcq'])]
    has_objective = any(t in {'mcq', 'true_false', 'fill_blank'} for t in selected_types)
    has_subjective = any(t in {'short_answer', 'long_answer'} for t in selected_types)

    objective_budget = total_marks // 2 if has_objective and has_subjective else total_marks if has_objective else 0
    subjective_budget = total_marks - objective_budget if has_subjective else 0

    counts = {}
    if 'long_answer' in selected_types:
        counts['long_answer'] = max(1, subjective_budget // 10) if subjective_budget >= 10 else (1 if has_subjective else 0)
        subjective_budget -= counts['long_answer'] * 10
    if 'short_answer' in selected_types:
        counts['short_answer'] = max(1, subjective_budget // 5) if subjective_budget >= 5 else (1 if has_subjective else 0)
        subjective_budget -= counts['short_answer'] * 5

    remaining_objective = total_marks - (counts.get('long_answer', 0) * 10 + counts.get('short_answer', 0) * 5)
    obj_types = [t for t in selected_types if t in {'mcq', 'true_false', 'fill_blank'}]
    if obj_types and remaining_objective > 0:
        base = remaining_objective // len(obj_types)
        rem = remaining_objective % len(obj_types)
        for idx, t in enumerate(obj_types):
            counts[t] = base + (1 if idx < rem else 0)

    actual_total = (
        counts.get('long_answer', 0) * 10
        + counts.get('short_answer', 0) * 5
        + sum(c for t, c in counts.items() if t not in {'long_answer', 'short_answer'})
    )
    return counts, actual_total


def validate_and_fix_paper(data, expected_total_marks=None, default_marks=1):
    if not isinstance(data, dict):
        raise ValueError('Generated paper must be a JSON object.')

    valid_questions = []
    for raw_question in data.get('questions', []):
        if not isinstance(raw_question, dict):
            continue
        raw_type = str(raw_question.get('type', '')).strip().lower()
        if raw_type not in VALID_TYPES:
            continue
        q_type = canonicalize_type(raw_type)

        difficulty = str(raw_question.get('difficulty', 'medium')).strip().lower()
        if difficulty not in VALID_DIFFICULTIES:
            difficulty = 'medium'

        text = str(raw_question.get('text', '')).strip()
        if not text:
            continue

        marks_val = raw_question.get('marks')
        try:
            marks = float(marks_val) if marks_val is not None else float(default_marks)
            if marks <= 0:
                marks = 1.0
        except (ValueError, TypeError):
            marks = 1.0

        cleaned_options = None
        accepted_answers = []
        rubric = []
        word_limit = None
        model_answer = ""
        correct_answer = raw_question.get('correct_answer')

        if q_type == 'mcq':
            options = raw_question.get('options')
            if not isinstance(options, list) or len(options) < 2:
                continue
            # Validate options and deduplicate
            cleaned_opts = [str(o).strip() for o in options if str(o).strip()]
            if len(cleaned_opts) < 2:
                continue
            cleaned_options = clean_options_list(cleaned_opts)
            correct_answer = _normalise_correct_answer(q_type, correct_answer, cleaned_options)

        elif q_type == 'true_false':
            cleaned_options = ['True', 'False']
            correct_answer = _normalise_correct_answer(q_type, correct_answer, cleaned_options)

        elif q_type == 'fill_blank':
            # Check for blank marker ____
            if '____' not in text and '___' not in text and '[blank]' not in text:
                # If model omitted blank marker, try to replace primary answer in text with ____
                ans_str = str(correct_answer or '').strip()
                if ans_str and re.search(re.escape(ans_str), text, re.IGNORECASE):
                    text = re.sub(re.escape(ans_str), '____', text, count=1, flags=re.IGNORECASE)
                else:
                    text = text.rstrip('. ') + ' is ____.'
            # Normalize blanks to ____
            text = re.sub(r'_{2,}', '____', text)

            raw_accepted = raw_question.get('accepted_answers')
            if isinstance(raw_accepted, list) and raw_accepted:
                if isinstance(raw_accepted[0], list):
                    accepted_answers = [[str(x).strip() for x in group if str(x).strip()] for group in raw_accepted]
                else:
                    accepted_answers = [[str(x).strip() for x in raw_accepted if str(x).strip()]]
            else:
                primary = str(correct_answer or '').strip()
                accepted_answers = [[primary]] if primary else [["answer"]]

            if not correct_answer and accepted_answers and accepted_answers[0]:
                correct_answer = accepted_answers[0][0]

        elif q_type in {'short_answer', 'long_answer'}:
            model_answer = str(raw_question.get('model_answer') or '').strip()
            if not model_answer and correct_answer:
                model_answer = str(correct_answer).strip()
            correct_answer = None

            raw_rubric = raw_question.get('rubric')
            if isinstance(raw_rubric, list):
                rubric = raw_rubric
            elif isinstance(raw_rubric, dict):
                rubric = [{'criterion': k, 'marks': v} for k, v in raw_rubric.items()]
            else:
                rubric = []

            word_limit = raw_question.get('word_limit')
            if not word_limit or not isinstance(word_limit, int):
                word_limit = 120 if q_type == 'short_answer' else 350

        question = {
            'type': q_type,
            'difficulty': difficulty,
            'topic': str(raw_question.get('topic') or '').strip(),
            'text': text,
            'marks': marks,
            'options': cleaned_options,
            'correct_answer': correct_answer,
            'model_answer': model_answer,
            'accepted_answers': accepted_answers,
            'rubric': rubric,
            'word_limit': word_limit,
            'source': 'ai_generated',
        }
        valid_questions.append(question)

    if not valid_questions:
        raise ValueError('Generated paper contained no valid questions matching the schema.')

    fixed_data = deepcopy(data)
    fixed_data['questions'] = valid_questions
    actual_total_marks = sum(q['marks'] for q in valid_questions)
    fixed_data['total_marks'] = actual_total_marks
    return fixed_data, actual_total_marks



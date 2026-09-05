from copy import deepcopy


VALID_TYPES = {'mcq', 'truefalse', 'fillblank', 'subjective'}
VALID_DIFFICULTIES = {'easy', 'medium', 'hard'}
OBJECTIVE_TYPES = {'mcq', 'truefalse', 'fillblank'}
OPTION_LABELS = ('A', 'B', 'C', 'D')


def _normalise_correct_answer(question_type, raw_answer, options):
    if question_type == 'truefalse':
        if isinstance(raw_answer, bool):
            return 'A' if raw_answer else 'B'
        answer = str(raw_answer or '').strip().casefold()
        if answer in {'a', 'true'}:
            return 'A'
        if answer in {'b', 'false'}:
            return 'B'
        return raw_answer

    if question_type in {'mcq', 'fillblank'}:
        if isinstance(raw_answer, int) and 0 <= raw_answer < 4:
            return OPTION_LABELS[raw_answer]
        answer = str(raw_answer or '').strip()
        if answer.upper() in OPTION_LABELS:
            return answer.upper()
        for index, option in enumerate(options or []):
            if answer.casefold() == str(option).strip().casefold():
                return OPTION_LABELS[index]
    return raw_answer


def compute_question_counts(question_types, total_marks):
    selected_types = set(question_types or [])
    has_objective = bool(selected_types & OBJECTIVE_TYPES)
    has_subjective = 'subjective' in selected_types
    objective_budget = total_marks // 2 if has_objective and has_subjective else total_marks if has_objective else 0
    subjective_budget = total_marks - objective_budget if has_subjective else 0
    n_subjective = subjective_budget // 10
    remaining_after_subjective = total_marks - (n_subjective * 10)
    n_objective_total = remaining_after_subjective if has_objective else 0

    selected_objective_types = [
        question_type for question_type in ('mcq', 'truefalse', 'fillblank')
        if question_type in selected_types
    ]
    counts = {'subjective': n_subjective}
    if selected_objective_types:
        base = n_objective_total // len(selected_objective_types)
        remainder = n_objective_total % len(selected_objective_types)
        for index, question_type in enumerate(selected_objective_types):
            counts[question_type] = base + (1 if index < remainder else 0)

    actual_total_marks = n_subjective * 10 + sum(
        count for question_type, count in counts.items() if question_type != 'subjective'
    )
    return counts, actual_total_marks


def validate_and_fix_paper(data, expected_total_marks=None):
    if not isinstance(data, dict):
        raise ValueError('Generated paper must be a JSON object.')

    valid_questions = []
    for raw_question in data.get('questions', []):
        if not isinstance(raw_question, dict):
            continue
        question_type = str(raw_question.get('type', '')).strip().lower()
        difficulty = str(raw_question.get('difficulty', 'medium')).strip().lower()
        text = str(raw_question.get('text', '')).strip()
        options = raw_question.get('options')
        if question_type not in VALID_TYPES or difficulty not in VALID_DIFFICULTIES or not text:
            continue
        if question_type in {'mcq', 'fillblank'} and (not isinstance(options, list) or len(options) != 4):
            continue

        question = deepcopy(raw_question)
        question.update({
            'type': question_type,
            'difficulty': difficulty,
            'text': text,
            'marks': 10 if question_type == 'subjective' else 1,
            'options': None if question_type == 'subjective' else (
                ['True', 'False'] if question_type == 'truefalse' else options
            ),
        })
        question['correct_answer'] = _normalise_correct_answer(
            question_type,
            raw_question.get('correct_answer'),
            question['options'],
        )
        valid_questions.append(question)

    if not valid_questions:
        raise ValueError('Generated paper contained no valid questions.')

    fixed_data = deepcopy(data)
    fixed_data['questions'] = valid_questions
    actual_total_marks = sum(question['marks'] for question in valid_questions)
    fixed_data['total_marks'] = actual_total_marks
    return fixed_data, actual_total_marks

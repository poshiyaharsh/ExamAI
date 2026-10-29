"""
Synonym dictionaries and fuzzy column matching for Smart Question Bank Importer.
Supports English and common Indian college / university academic variants.
"""

import re
from difflib import SequenceMatcher
from typing import Dict, List, Optional, Tuple

# Canonical system targets for spreadsheet column mapping
TARGET_QUESTION_TEXT = 'question_text'
TARGET_OPTION_A = 'option_a'
TARGET_OPTION_B = 'option_b'
TARGET_OPTION_C = 'option_c'
TARGET_OPTION_D = 'option_d'
TARGET_OPTION_E = 'option_e'
TARGET_OPTION_F = 'option_f'
TARGET_OPTIONS = 'options'  # Single column containing all options
TARGET_CORRECT_ANSWER = 'correct_answer'
TARGET_QUESTION_TYPE = 'question_type'
TARGET_MARKS = 'marks'
TARGET_DIFFICULTY = 'difficulty'
TARGET_TOPIC = 'topic'
TARGET_SUBJECT = 'subject'
TARGET_DEPARTMENT = 'department'
TARGET_EXPLANATION = 'explanation'
TARGET_MODEL_ANSWER = 'model_answer'
TARGET_IGNORE = 'ignore'

COLUMN_TARGETS = [
    TARGET_QUESTION_TEXT,
    TARGET_OPTIONS,
    TARGET_OPTION_A,
    TARGET_OPTION_B,
    TARGET_OPTION_C,
    TARGET_OPTION_D,
    TARGET_OPTION_E,
    TARGET_OPTION_F,
    TARGET_CORRECT_ANSWER,
    TARGET_QUESTION_TYPE,
    TARGET_MARKS,
    TARGET_DIFFICULTY,
    TARGET_TOPIC,
    TARGET_SUBJECT,
    TARGET_DEPARTMENT,
    TARGET_EXPLANATION,
    TARGET_MODEL_ANSWER,
    TARGET_IGNORE,
]

# Comprehensive synonyms dictionary
COLUMN_SYNONYMS: Dict[str, List[str]] = {
    TARGET_QUESTION_TEXT: [
        'question', 'que', 'q', 'question text', 'question_text', 'problem',
        'statement', 'question statement', 'prompt', 'description', 'q_text',
        'q text', 'question description', 'item', 'problem statement', 'que text',
        'que_text', 'question title', 'questions'
    ],
    TARGET_OPTION_A: [
        'option a', 'option_a', 'opta', 'opt_a', 'opt a', 'choice a', 'choice_a',
        'a', '(a)', 'a)', 'ans a', 'option 1', 'option_1', 'choice 1', 'choice_1',
        'opt 1', 'opt1', '1', '(1)', '1)'
    ],
    TARGET_OPTION_B: [
        'option b', 'option_b', 'optb', 'opt_b', 'opt b', 'choice b', 'choice_b',
        'b', '(b)', 'b)', 'ans b', 'option 2', 'option_2', 'choice 2', 'choice_2',
        'opt 2', 'opt2', '2', '(2)', '2)'
    ],
    TARGET_OPTION_C: [
        'option c', 'option_c', 'optc', 'opt_c', 'opt c', 'choice c', 'choice_c',
        'c', '(c)', 'c)', 'ans c', 'option 3', 'option_3', 'choice 3', 'choice_3',
        'opt 3', 'opt3', '3', '(3)', '3)'
    ],
    TARGET_OPTION_D: [
        'option d', 'option_d', 'optd', 'opt_d', 'opt d', 'choice d', 'choice_d',
        'd', '(d)', 'd)', 'ans d', 'option 4', 'option_4', 'choice 4', 'choice_4',
        'opt 4', 'opt4', '4', '(4)', '4)'
    ],
    TARGET_OPTION_E: [
        'option e', 'option_e', 'opte', 'opt_e', 'opt e', 'choice e', 'choice_e',
        'e', '(e)', 'e)', 'option 5', 'option_5', 'opt 5', 'opt5', '5', '(5)'
    ],
    TARGET_OPTION_F: [
        'option f', 'option_f', 'optf', 'opt_f', 'opt f', 'choice f', 'choice_f',
        'f', '(f)', 'f)', 'option 6', 'option_6', 'opt 6', 'opt6', '6', '(6)'
    ],
    TARGET_OPTIONS: [
        'options', 'choices', 'all options', 'options list', 'options (separated)',
        'option', 'options separated by pipe', 'options_list', 'mcq options'
    ],
    TARGET_CORRECT_ANSWER: [
        'answer', 'ans', 'correct', 'correct answer', 'correct_answer', 'correct option',
        'correct_option', 'key', 'answer key', 'ans key', 'solution', 'right answer',
        'right option', 'correct choice', 'correct opt', 'ans_key', 'answer_key',
        'correctans', 'correct_ans', 'right choice'
    ],
    TARGET_QUESTION_TYPE: [
        'type', 'question type', 'question_type', 'q type', 'q_type', 'category',
        'item type', 'kind', 'qtype', 'que type', 'que_type'
    ],
    TARGET_MARKS: [
        'marks', 'mark', 'points', 'point', 'score', 'weight', 'max marks',
        'maximum marks', 'marks/question', 'marks per question', 'mark/question',
        'pts', 'weightage', 'mark weight'
    ],
    TARGET_DIFFICULTY: [
        'difficulty', 'diff', 'level', 'difficulty level', 'complexity',
        'difficulty (easy/medium/hard)', 'level (easy/medium/hard)', 'bloom level',
        'blooms level', 'complexity level'
    ],
    TARGET_TOPIC: [
        'topic', 'unit', 'chapter', 'module', 'co', 'course outcome',
        'unit/topic', 'concept', 'section', 'unit name', 'topic name',
        'chapter name', 'unit no', 'unit_no', 'unit #'
    ],
    TARGET_SUBJECT: [
        'subject', 'subject name', 'course', 'course name', 'sub', 'sub name',
        'subject_name', 'course_name', 'subject code'
    ],
    TARGET_DEPARTMENT: [
        'department', 'dept', 'dept name', 'department name', 'branch', 'stream'
    ],
    TARGET_EXPLANATION: [
        'explanation', 'rationale', 'solution description', 'reason', 'remark',
        'remarks', 'hint', 'justification', 'notes'
    ],
    TARGET_MODEL_ANSWER: [
        'model answer', 'model_answer', 'sample answer', 'ideal answer',
        'descriptive answer', 'rubric answer'
    ],
    TARGET_IGNORE: [
        'sr no', 'sr. no', 'sr_no', 's.no', 's no', 'no', '#', 'sl no',
        'sl. no', 'index', 'id', 'question no', 'q.no', 'q no', 'serial no',
        'serial number', 'row id', 's_no', 'q_num', 'qnum', 'item no'
    ],
}


def normalize_header_string(header: str) -> str:
    """Cleans punctuation, whitespace, and case from header string."""
    if not header:
        return ""
    # Lowercase, replace non-alphanumeric (except underscores and hyphens) with spaces
    h = str(header).strip().lower()
    h = re.sub(r'[\r\n\t]+', ' ', h)
    h = re.sub(r'[^\w\s\(\)\#\.\-]', ' ', h)
    # Collapse multi-spaces
    h = re.sub(r'\s+', ' ', h).strip()
    return h


def match_column_name(header: str, threshold: float = 0.85) -> Tuple[str, float]:
    """
    Fuzzy matches a single raw header string to the best target column.
    Returns: (target_column_name, confidence_score)
    If no match exceeds threshold, returns ('ignore', 0.0)
    """
    norm = normalize_header_string(header)
    if not norm:
        return TARGET_IGNORE, 0.0

    # 1. Exact match in synonyms
    for target, syn_list in COLUMN_SYNONYMS.items():
        for syn in syn_list:
            if norm == syn:
                return target, 1.0

    # 2. Substring containment match with word boundaries
    best_target = TARGET_IGNORE
    best_score = 0.0

    for target, syn_list in COLUMN_SYNONYMS.items():
        for syn in syn_list:
            # Word boundary regex check
            pattern = r'\b' + re.escape(syn) + r'\b'
            if re.search(pattern, norm):
                score = len(syn) / max(len(norm), len(syn))
                score = max(score, 0.90)  # High confidence on boundary match
                if score > best_score:
                    best_score = score
                    best_target = target

    if best_score >= threshold:
        return best_target, best_score

    # 3. Fuzzy SequenceMatcher
    for target, syn_list in COLUMN_SYNONYMS.items():
        for syn in syn_list:
            ratio = SequenceMatcher(None, norm, syn).ratio()
            if ratio > best_score:
                best_score = ratio
                best_target = target

    if best_score >= threshold:
        return best_target, best_score

    return TARGET_IGNORE, 0.0


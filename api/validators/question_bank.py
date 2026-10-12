"""Centralized Zero-Mistakes validation module for Question Bank."""

import difflib
import hashlib
import html
import re
import unicodedata
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from django.db import models
from rest_framework import serializers

from api.models import Option, Question, Subject, Topic
from api.utils.departments import normalize_department

MIN_QUESTION_LENGTH = 10
MAX_QUESTION_LENGTH = 5000
MIN_OPTION_LENGTH = 1
MAX_OPTION_LENGTH = 1000

DISALLOWED_PLACEHOLDERS = {
    'test', 'testing', 'lorem ipsum', 'lorem ipsum dolor sit amet',
    'asdf', 'asdfgh', 'qwerty', 'sample', 'sample question',
    'placeholder', 'dummy', 'dummy question', 'temp', 'foo bar', 'foobar',
}

HTML_TAG_RE = re.compile(r'<[^>]*?>')
DANGEROUS_PATTERNS_RE = re.compile(r'(<\s*script|javascript:|data:\s*text/html|onload=|onerror=)', re.IGNORECASE)


def normalize_text(text: Optional[str]) -> str:
    """Normalize unicode, collapse multiple whitespace characters, and trim."""
    if not text:
        return ''
    # Normalize unicode to NFKC
    nfkc = unicodedata.normalize('NFKC', str(text))
    # Replace non-breaking spaces and collapse whitespace
    collapsed = re.sub(r'\s+', ' ', nfkc).strip()
    return collapsed


def sanitize_text(text: Optional[str]) -> str:
    """Strip dangerous HTML tags/scripts and unescape entities into clean plain text."""
    if not text:
        return ''
    cleaned = str(text)
    # Strip HTML tags
    cleaned = HTML_TAG_RE.sub('', cleaned)
    # Unescape HTML entities (e.g. &amp; -> &)
    cleaned = html.unescape(cleaned)
    return normalize_text(cleaned)


def compute_text_hash(text: str) -> str:
    """Calculate SHA-256 of lowercase, whitespace-collapsed normalized text."""
    normalized = normalize_text(text).lower()
    return hashlib.sha256(normalized.encode('utf-8')).hexdigest()


def is_placeholder(text: str) -> bool:
    """Detect if question text is just placeholder or gibberish."""
    lowered = normalize_text(text).lower()
    if lowered in DISALLOWED_PLACEHOLDERS:
        return True
    # Strip non-alphanumeric
    alphanumeric_only = re.sub(r'[^a-z0-9]', '', lowered)
    if alphanumeric_only in DISALLOWED_PLACEHOLDERS:
        return True
    # Check if text is just repetitive characters (e.g., 'aaaaaaa', '111111')
    if len(set(alphanumeric_only)) <= 2 and len(alphanumeric_only) >= 5:
        return True
    return False


def sanitize_formula_injection(val: Any) -> Any:
    """Prevent CSV/Excel Formula Injection by escaping leading =, +, -, @, tab, cr."""
    if isinstance(val, str):
        trimmed = val.strip()
        if trimmed and trimmed[0] in ('=', '+', '-', '@', '\t', '\r'):
            return "'" + val
    return val


def check_near_duplicates(
    institution_id: int,
    subject_id: int,
    text: str,
    threshold: float = 0.85,
    exclude_id: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Scan existing active questions in the same institution and subject for near duplicates."""
    normalized_input = normalize_text(text).lower()
    qs = Question.objects.filter(
        institution_id=institution_id,
        subject_id=subject_id,
        is_deleted=False,
    )
    if exclude_id:
        qs = qs.exclude(id=exclude_id)

    # Only compare with active questions
    near_matches = []
    # Check candidates
    for existing in qs.only('id', 'text')[:100]:
        norm_existing = normalize_text(existing.text).lower()
        if norm_existing == normalized_input:
            continue
        ratio = difflib.SequenceMatcher(None, normalized_input, norm_existing).ratio()
        if ratio >= threshold:
            near_matches.append({
                'id': existing.id,
                'similarity': round(ratio * 100, 1),
                'text': existing.text[:100],
            })
    return near_matches


def is_question_used_in_exam(question: Question) -> Tuple[bool, str]:
    """
    Check if question is used in published/ongoing exams or has student answers.
    Returns (is_used, reason_message).
    """
    if not question or not question.id:
        return False, ''

    # Check student answers
    from api.models import StudentAnswer
    if StudentAnswer.objects.filter(question_id=question.id).exists():
        return True, 'This question has been answered by students in past or ongoing exams.'

    # Check exam reference
    if question.exam_id:
        exam = question.exam
        if exam.status in ('published', 'ongoing', 'completed'):
            return True, f"This question is part of exam '{exam.title}' which is {exam.status}."

    return False, ''


def validate_question_payload(
    payload: Dict[str, Any],
    institution: Any,
    instance: Optional[Question] = None,
    allow_warnings: bool = True,
) -> Tuple[Dict[str, Any], List[str]]:
    """
    Enforces all Step 3 rules.
    Returns (cleaned_data, warnings_list).
    Raises serializers.ValidationError with field-level errors if validation fails.
    """
    errors: Dict[str, Any] = {}
    warnings: List[str] = []
    cleaned: Dict[str, Any] = {}

    inst_id = institution.id if hasattr(institution, 'id') else int(institution)

    # 1. Text validation
    raw_text = payload.get('text')
    if not raw_text or not str(raw_text).strip():
        errors['text'] = 'Question text is required.'
    else:
        sanitized = sanitize_text(str(raw_text))
        if len(sanitized) < MIN_QUESTION_LENGTH:
            errors['text'] = f'Question text must be at least {MIN_QUESTION_LENGTH} characters long.'
        elif len(sanitized) > MAX_QUESTION_LENGTH:
            errors['text'] = f'Question text must not exceed {MAX_QUESTION_LENGTH} characters.'
        elif is_placeholder(sanitized):
            errors['text'] = 'Question text cannot be a placeholder or dummy text.'
        else:
            cleaned['text'] = sanitized

    # Explanation sanitization
    raw_explanation = payload.get('explanation', '')
    cleaned['explanation'] = sanitize_text(str(raw_explanation)) if raw_explanation else ''

    # 2. Department validation
    dept = normalize_department(payload.get('department') or (instance.department if instance else ''))
    if not dept:
        errors['department'] = 'A valid department is required.'
    else:
        cleaned['department'] = dept

    # 3. Subject validation
    subject_raw = payload.get('subject') or payload.get('subject_id')
    subject_id = None
    if hasattr(subject_raw, 'id'):
        subject_id = subject_raw.id
    elif subject_raw is not None:
        try:
            subject_id = int(subject_raw)
        except (ValueError, TypeError):
            subject_id = None

    subject_obj = None
    if not subject_id and instance:
        subject_id = instance.subject_id

    if not subject_id:
        errors['subject'] = 'Subject is required.'
    else:
        try:
            subject_obj = Subject.objects.get(id=subject_id, institution_id=inst_id)
            if dept and subject_obj.department != dept:
                errors['subject'] = f"Subject '{subject_obj.name}' belongs to department '{subject_obj.department}', not '{dept}'."
            else:
                cleaned['subject'] = subject_obj
        except Subject.DoesNotExist:
            errors['subject'] = 'Subject not found in your institution.'

    # 4. Topic validation (optional)
    topic_raw = payload.get('topic') or payload.get('topic_id')
    topic_id = None
    if hasattr(topic_raw, 'id'):
        topic_id = topic_raw.id
    elif topic_raw is not None:
        try:
            topic_id = int(topic_raw)
        except (ValueError, TypeError):
            topic_id = None

    topic_name = payload.get('topic_name') or ''
    if topic_id:
        try:
            topic_obj = Topic.objects.get(id=topic_id, institution_id=inst_id)
            if subject_obj and topic_obj.subject_id != subject_obj.id:
                errors['topic'] = f"Topic '{topic_obj.name}' belongs to subject '{topic_obj.subject.name}', not '{subject_obj.name}'."
            else:
                cleaned['topic'] = topic_obj
                cleaned['topic_name'] = topic_obj.name
        except Topic.DoesNotExist:
            errors['topic'] = 'Topic not found in your institution.'
    else:
        cleaned['topic'] = None
        cleaned['topic_name'] = sanitize_text(topic_name) if topic_name else ''

    # 5. Question Type
    q_type = str(payload.get('question_type') or (instance.question_type if instance else 'MCQ_SINGLE')).upper()
    valid_types = [choice[0] for choice in Question.QuestionType.choices]
    if q_type not in valid_types:
        errors['question_type'] = f"Invalid question type. Allowed choices: {', '.join(valid_types)}"
    else:
        cleaned['question_type'] = q_type

    # 6. Difficulty
    difficulty = str(payload.get('difficulty') or (instance.difficulty if instance else 'MEDIUM')).upper()
    valid_diffs = [choice[0] for choice in Question.Difficulty.choices]
    if difficulty not in valid_diffs:
        errors['difficulty'] = f"Invalid difficulty level. Allowed choices: {', '.join(valid_diffs)}"
    else:
        cleaned['difficulty'] = difficulty

    # 7. Marks & Negative Marks
    try:
        marks = Decimal(str(payload.get('marks') if payload.get('marks') is not None else (instance.marks if instance else 1.0)))
        if marks <= Decimal('0'):
            errors['marks'] = 'Marks must be greater than 0.'
        elif marks > Decimal('500'):
            errors['marks'] = 'Marks cannot exceed 500.'
        else:
            cleaned['marks'] = marks
    except Exception:
        errors['marks'] = 'Marks must be a valid positive number.'

    try:
        neg_marks = Decimal(str(payload.get('negative_marks') if payload.get('negative_marks') is not None else (instance.negative_marks if instance else 0.0)))
        if neg_marks < Decimal('0'):
            errors['negative_marks'] = 'Negative marks cannot be less than 0.'
        elif 'marks' in cleaned and neg_marks > cleaned['marks']:
            errors['negative_marks'] = 'Negative marks cannot be greater than positive marks.'
        else:
            cleaned['negative_marks'] = neg_marks
    except Exception:
        errors['negative_marks'] = 'Negative marks must be a valid non-negative number.'

    # 8. Status
    status_val = str(payload.get('status') or (instance.status if instance else 'ACTIVE')).upper()
    valid_statuses = [choice[0] for choice in Question.Status.choices]
    if status_val not in valid_statuses:
        errors['status'] = f"Invalid status. Allowed choices: {', '.join(valid_statuses)}"
    else:
        cleaned['status'] = status_val

    # 9. Tags
    tags = payload.get('tags', instance.tags if instance else [])
    if isinstance(tags, list):
        cleaned['tags'] = [sanitize_text(str(t)) for t in tags if str(t).strip()][:20]
    elif isinstance(tags, str):
        cleaned['tags'] = [sanitize_text(t) for t in tags.split(',') if t.strip()][:20]
    else:
        cleaned['tags'] = []

    # 10. Model answer (for subjective/short/long)
    model_answer = sanitize_text(str(payload.get('model_answer') or (instance.model_answer if instance else '')))
    cleaned['model_answer'] = model_answer

    # 11. Options Validation
    raw_options = payload.get('options')
    if raw_options is None and instance and hasattr(instance, 'option_items'):
        # Keep existing options if not provided during partial update
        raw_options = [
            {'text': opt.text, 'is_correct': opt.is_correct, 'order': opt.order}
            for opt in instance.option_items.all()
        ]

    options_data: List[Dict[str, Any]] = []

    if q_type in ('MCQ_SINGLE', 'MCQ_MULTIPLE', 'TRUE_FALSE', 'mcq', 'truefalse'):
        if not raw_options or not isinstance(raw_options, list):
            errors['options'] = f'Options list is required for question type {q_type}.'
        else:
            normalized_opt_texts = set()
            correct_count = 0

            for idx, opt in enumerate(raw_options, start=1):
                if isinstance(opt, str):
                    opt_dict = {'text': opt, 'is_correct': False, 'order': idx}
                elif isinstance(opt, dict):
                    opt_dict = {
                        'text': str(opt.get('text', '')),
                        'is_correct': bool(opt.get('is_correct', False)),
                        'order': int(opt.get('order', idx)),
                    }
                else:
                    errors[f'options_{idx}'] = 'Invalid option structure.'
                    continue

                clean_opt_text = sanitize_text(opt_dict['text'])
                if not clean_opt_text:
                    errors[f'option_{idx}'] = f'Option {idx} text cannot be empty.'
                    continue

                # Check duplicate against question text
                if 'text' in cleaned and clean_opt_text.lower() == cleaned['text'].lower():
                    errors[f'option_{idx}'] = f'Option {idx} cannot be identical to the question text.'

                # Check duplicate option text
                norm_lower = clean_opt_text.lower()
                if norm_lower in normalized_opt_texts:
                    errors[f'option_{idx}'] = f"Duplicate option detected: '{clean_opt_text}'."
                normalized_opt_texts.add(norm_lower)

                if opt_dict['is_correct']:
                    correct_count += 1

                options_data.append({
                    'text': clean_opt_text,
                    'is_correct': opt_dict['is_correct'],
                    'order': opt_dict['order'],
                })

            # Check counts
            if q_type in ('MCQ_SINGLE', 'mcq'):
                if len(options_data) < 2 or len(options_data) > 6:
                    errors['options'] = f'MCQ Single Choice questions must have between 2 and 6 options (received {len(options_data)}).'
                elif correct_count != 1:
                    errors['options'] = f'MCQ Single Choice questions must have exactly 1 correct option (marked {correct_count}).'

            elif q_type == 'MCQ_MULTIPLE':
                if len(options_data) < 2 or len(options_data) > 6:
                    errors['options'] = f'MCQ Multiple Choice questions must have between 2 and 6 options (received {len(options_data)}).'
                elif correct_count < 1:
                    errors['options'] = 'MCQ Multiple Choice questions must have at least 1 correct option.'
                elif correct_count == len(options_data):
                    errors['options'] = 'MCQ Multiple Choice questions cannot have all options marked correct.'

            elif q_type in ('TRUE_FALSE', 'truefalse'):
                if len(options_data) != 2:
                    errors['options'] = f'True/False questions must have exactly 2 options (received {len(options_data)}).'
                elif correct_count != 1:
                    errors['options'] = f'True/False questions must have exactly 1 correct option (marked {correct_count}).'
                else:
                    opt_labels = {o['text'].lower() for o in options_data}
                    if not ({'true', 'false'}.issubset(opt_labels) or {'yes', 'no'}.issubset(opt_labels)):
                        warnings.append("True/False options should ideally be 'True' and 'False'.")

    elif q_type in ('SHORT_ANSWER', 'LONG_ANSWER', 'fillblank', 'subjective'):
        if raw_options and len(raw_options) > 0:
            errors['options'] = f'Options are not allowed for {q_type} questions.'
        if not model_answer:
            errors['model_answer'] = f'A model answer or key points are required for {q_type} questions.'
        elif len(model_answer) < 5:
            errors['model_answer'] = 'Model answer must be at least 5 characters long.'

    cleaned['options'] = options_data

    # 12. Duplicate Check by text_hash
    if 'text' in cleaned and subject_obj:
        text_hash = compute_text_hash(cleaned['text'])
        cleaned['text_hash'] = text_hash

        dup_qs = Question.objects.filter(
            institution_id=inst_id,
            subject=subject_obj,
            text_hash=text_hash,
            is_deleted=False,
        )
        if instance:
            dup_qs = dup_qs.exclude(id=instance.id)

        if dup_qs.exists():
            dup_item = dup_qs.first()
            errors['text'] = (
                f"Duplicate question detected! An identical question (ID #{dup_item.id}) "
                f"already exists in subject '{subject_obj.name}'."
            )

        # Near duplicates check
        if allow_warnings and 'text' not in errors:
            near_dups = check_near_duplicates(
                inst_id,
                subject_obj.id,
                cleaned['text'],
                threshold=0.85,
                exclude_id=instance.id if instance else None,
            )
            for nd in near_dups:
                warnings.append(
                    f"Warning: Question #{nd['id']} is very similar ({nd['similarity']}% similarity): '{nd['text']}...'"
                )

    if errors:
        raise serializers.ValidationError(errors)

    return cleaned, warnings

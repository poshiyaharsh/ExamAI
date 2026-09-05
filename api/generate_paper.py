import json
import logging

from django.db import transaction
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Exam, Question
from .permissions import IsFacultyUser
from .utils.extract_text import extract_syllabus_text
from .utils.ollama_client import call_ollama, parse_json_safely
from .utils.prompts import build_type_generation_prompt
from .utils.validate_paper import compute_question_counts, validate_and_fix_paper


logger = logging.getLogger(__name__)

MODEL_ALIASES = {
    'qwen2.5-3b': 'qwen2.5:3b-instruct',
    'llama3.2-3b': 'llama3.2:3b',
    'phi3-mini': 'phi3:mini',
}
MAX_BATCH_SIZE = 15
MARKS_PER_TYPE = {
    'mcq': 1,
    'truefalse': 1,
    'fillblank': 1,
    'subjective': 10,
}


def _as_list(value, request_data, key):
    values = request_data.getlist(key) if hasattr(request_data, 'getlist') else []
    if values:
        return values
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, list):
            return parsed
        return [item.strip() for item in value.split(',') if item.strip()]
    return []


def _as_dict(value):
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ValueError('difficulty_distribution must be a JSON object.') from exc
        if isinstance(parsed, dict):
            return parsed
    raise ValueError('difficulty_distribution must be a JSON object.')


def _validated_type_questions(data, question_type):
    questions = [
        question for question in data.get('questions', [])
        if isinstance(question, dict) and str(question.get('type', '')).strip().lower() == question_type
    ]
    if not questions:
        raise ValueError(f'Model returned zero valid {question_type} questions.')
    fixed_data, _ = validate_and_fix_paper({'questions': questions})
    return [question for question in fixed_data['questions'] if question['type'] == question_type]


def _call_type_batch(question_type, count, model_name, topics, difficulty_distribution, syllabus_text):
    prompt = build_type_generation_prompt(
        question_type,
        count,
        MARKS_PER_TYPE[question_type],
        topics,
        difficulty_distribution,
        syllabus_text,
    )
    last_error = None
    for temperature in (0.4, 0.2):
        try:
            raw_response = call_ollama(model_name, prompt, temperature=temperature, num_predict=4096)
            generated_data = parse_json_safely(raw_response)
            questions = _validated_type_questions(generated_data, question_type)
            logger.warning(
                'Paper generation batch type=%s requested=%s returned=%s temperature=%s',
                question_type,
                count,
                len(questions),
                temperature,
            )
            return questions[:count]
        except Exception as exc:
            last_error = exc
            logger.exception('Paper generation batch failed type=%s count=%s temperature=%s', question_type, count, temperature)
    logger.warning('Paper generation batch abandoned type=%s count=%s error=%s', question_type, count, last_error)
    return []


def _generate_type_questions(question_type, count, model_name, topics, difficulty_distribution, syllabus_text):
    questions = []
    for start in range(0, count, MAX_BATCH_SIZE):
        requested_batch_count = min(MAX_BATCH_SIZE, count - start)
        batch_questions = _call_type_batch(
            question_type,
            requested_batch_count,
            model_name,
            topics,
            difficulty_distribution,
            syllabus_text,
        )
        questions.extend(batch_questions)
        shortfall = requested_batch_count - len(batch_questions)
        if shortfall:
            logger.warning(
                'Paper generation batch shortfall type=%s requested=%s returned=%s retrying_shortfall=%s',
                question_type,
                requested_batch_count,
                len(batch_questions),
                shortfall,
            )
            retry_questions = _call_type_batch(
                question_type,
                shortfall,
                model_name,
                topics,
                difficulty_distribution,
                syllabus_text,
            )
            questions.extend(retry_questions[:shortfall])
            if len(retry_questions) < shortfall:
                logger.warning(
                    'Paper generation final shortfall type=%s requested=%s returned=%s',
                    question_type,
                    shortfall,
                    len(retry_questions),
                )
    return questions


class GeneratePaperView(APIView):
    permission_classes = [IsAuthenticated, IsFacultyUser]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        try:
            title = str(request.data.get('title', '')).strip()
            duration_minutes = int(request.data.get('duration_minutes', 0))
            total_marks = int(request.data.get('total_marks', 0))
            topics = _as_list(request.data.get('topics'), request.data, 'topics')
            question_types = _as_list(request.data.get('question_types'), request.data, 'question_types')
            difficulty_distribution = _as_dict(request.data.get('difficulty_distribution', {}))
            model_alias = str(request.data.get('ai_model', '')).strip()
            model_name = MODEL_ALIASES.get(model_alias)
            if not title or duration_minutes <= 0 or total_marks <= 0:
                raise ValueError('title, duration_minutes, and total_marks must be valid positive values.')
            if not topics or not question_types:
                raise ValueError('topics and question_types are required.')
            if not model_name:
                raise ValueError('ai_model must be qwen2.5-3b, llama3.2-3b, or phi3-mini.')
        except (TypeError, ValueError) as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        syllabus_file = request.FILES.get('syllabus')
        syllabus_text = ''
        if syllabus_file:
            try:
                syllabus_text = extract_syllabus_text(syllabus_file)
            except ValueError as exc:
                return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        counts, _ = compute_question_counts(question_types, total_marks)
        generated_questions = []
        for question_type in ('mcq', 'truefalse', 'fillblank', 'subjective'):
            requested_count = counts.get(question_type, 0)
            if requested_count:
                generated_questions.extend(_generate_type_questions(
                    question_type,
                    requested_count,
                    model_name,
                    topics,
                    difficulty_distribution,
                    syllabus_text,
                ))

        if not generated_questions:
            return Response(
                {'detail': 'Unable to generate a valid exam paper.'},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        actual_total_marks = sum(question['marks'] for question in generated_questions)
        warning = None
        if abs(actual_total_marks - total_marks) / total_marks > 0.10:
            warning = 'Some questions could not be generated reliably; you can add more manually before publishing.'

        try:
            with transaction.atomic():
                exam = Exam.objects.create(
                    title=title,
                    created_by=request.user,
                    duration_minutes=duration_minutes,
                    total_marks=actual_total_marks,
                    topics=topics,
                    difficulty_distribution=difficulty_distribution,
                    question_types=question_types,
                    ai_model_used=model_name,
                    source_syllabus_text=syllabus_text,
                    status=Exam.Status.DRAFT,
                )
                for question_order, generated_question in enumerate(generated_questions, start=1):
                    Question.objects.create(
                        exam=exam,
                        order=question_order,
                        question_type=generated_question['type'],
                        difficulty=generated_question['difficulty'],
                        text=generated_question['text'],
                        options=generated_question.get('options'),
                        correct_answer=generated_question.get('correct_answer'),
                        model_answer=generated_question.get('model_answer') or '',
                        marks=generated_question['marks'],
                        topic=generated_question.get('topic') or '',
                    )
        except Exception as exc:
            return Response(
                {'detail': f'Generated paper could not be saved: {exc}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(
            {
                'exam_id': exam.id,
                'status': exam.status,
                'question_count': len(generated_questions),
                'requested_total_marks': total_marks,
                'actual_total_marks': actual_total_marks,
                **({'warning': warning} if warning else {}),
            },
            status=status.HTTP_201_CREATED,
        )

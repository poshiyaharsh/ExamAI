"""
Serializers for AI Paper Generator REST API.
Handles all payload formats:
- New sections list: [{'type': 'MCQ', 'count': 10, 'marks_per_question': 2}, ...]
- Old blueprint dict: {'mcq': {'count': 10, 'marks': 2}, 'true_false': {...}}
- FormData strings, JSON blobs, camelCase / snake_case aliases.
- Provides all fields required by GenerationProgressModal and PaperGenerationJob.
"""
import json
from rest_framework import serializers
from .models import GenerationJob, GenerationLog
from .config import QUESTION_TYPES, DIFFICULTY_LEVELS


TYPE_NORMALIZATION_MAP = {
    'mcq': 'MCQ',
    'true_false': 'True/False',
    'true/false': 'True/False',
    'tf': 'True/False',
    'fill_blank': 'Fill in the Blank',
    'fill in the blank': 'Fill in the Blank',
    'fill_in_the_blank': 'Fill in the Blank',
    'short': 'Short Answer',
    'short_answer': 'Short Answer',
    'short answer': 'Short Answer',
    'long': 'Long Answer',
    'long_answer': 'Long Answer',
    'long answer': 'Long Answer',
}


class JSONStringField(serializers.Field):
    """Accepts a real list/dict OR a JSON string (multipart form data)."""

    def to_internal_value(self, data):
        if isinstance(data, (list, dict)):
            return data
        if isinstance(data, str):
            data = data.strip()
            if data == "":
                return []
            try:
                return json.loads(data)
            except json.JSONDecodeError as e:
                raise serializers.ValidationError(f"Invalid JSON: {e}")
        raise serializers.ValidationError("Expected a list/object or a JSON string.")

    def to_representation(self, value):
        return value


class SectionSerializer(serializers.Serializer):
    """
    Validates individual question section configurations.
    Checks type, count, marks_per_question (or marks), difficulty and unit.
    """
    type = serializers.CharField(max_length=50)
    count = serializers.IntegerField(min_value=1, max_value=200)
    marks_per_question = serializers.IntegerField(min_value=1, max_value=100, required=False)
    marks = serializers.IntegerField(min_value=1, max_value=100, required=False)
    section_name = serializers.CharField(max_length=120, required=False, default='', allow_blank=True)
    difficulty = serializers.CharField(max_length=50, required=False, default='medium', allow_blank=True)
    unit = serializers.CharField(max_length=120, required=False, default='', allow_blank=True)

    def validate_type(self, value):
        val_clean = str(value).strip()
        normalized = TYPE_NORMALIZATION_MAP.get(val_clean.lower(), val_clean)
        if normalized not in QUESTION_TYPES:
            raise serializers.ValidationError(
                f"Invalid question type '{value}'. Allowed: {', '.join(QUESTION_TYPES)}"
            )
        return normalized

    def validate(self, attrs):
        if 'marks_per_question' not in attrs and 'marks' in attrs:
            attrs['marks_per_question'] = attrs['marks']
        elif 'marks_per_question' not in attrs and 'marks' not in attrs:
            attrs['marks_per_question'] = 1
        return attrs


# Alias for backward compatibility
SectionConfigSerializer = SectionSerializer


class StartGenerationSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=255)
    subject = serializers.CharField(max_length=255, required=True, allow_blank=False)
    class_semester = serializers.CharField(max_length=120, required=False, default='', allow_blank=True)
    exam_type = serializers.CharField(max_length=120, required=False, default='Final Examination', allow_blank=True)
    duration = serializers.IntegerField(min_value=5, max_value=600, default=60)
    total_marks = serializers.IntegerField(min_value=1, max_value=1000)

    # Use JSONStringField for sections and all nested/list fields
    sections = JSONStringField(required=False)
    blueprint = JSONStringField(required=False)
    topics = JSONStringField(required=False)
    difficulty_distribution = JSONStringField(required=False)
    difficulty_split = JSONStringField(required=False)
    unit_weightage = JSONStringField(required=False)
    model_roles = JSONStringField(required=False)

    # Advanced Model Assignments
    model_generator = serializers.CharField(max_length=100, required=False, allow_blank=True, default='')
    model_validator = serializers.CharField(max_length=100, required=False, allow_blank=True, default='')
    model_fallback = serializers.CharField(max_length=100, required=False, allow_blank=True, default='')

    avoid_repeats = serializers.BooleanField(required=False, default=True)
    accept_capacity_override = serializers.BooleanField(required=False, default=False)

    def to_internal_value(self, data):
        # 1. Unpack QueryDict or raw dict
        if hasattr(data, 'getlist'):
            raw = {}
            for key in data.keys():
                val_list = data.getlist(key)
                if len(val_list) > 1:
                    raw[key] = val_list
                else:
                    raw[key] = data.get(key)
        elif isinstance(data, dict):
            raw = dict(data)
        elif isinstance(data, str):
            try:
                raw = json.loads(data)
            except Exception:
                raw = {}
        else:
            raw = {}

        # 2. Field name alias normalization
        if 'totalMarks' in raw and 'total_marks' not in raw:
            raw['total_marks'] = raw['totalMarks']
        if 'duration_minutes' in raw and 'duration' not in raw:
            raw['duration'] = raw['duration_minutes']
        if 'durationMinutes' in raw and 'duration' not in raw:
            raw['duration'] = raw['durationMinutes']
        if 'classSemester' in raw and 'class_semester' not in raw:
            raw['class_semester'] = raw['classSemester']
        if 'examType' in raw and 'exam_type' not in raw:
            raw['exam_type'] = raw['examType']
        if 'question_types' in raw and 'sections' not in raw:
            raw['sections'] = raw['question_types']
        if 'blueprint' in raw and 'sections' not in raw:
            raw['sections'] = raw['blueprint']
        if 'difficultyDistribution' in raw and 'difficulty_distribution' not in raw:
            raw['difficulty_distribution'] = raw['difficultyDistribution']
        if 'difficultySplit' in raw and 'difficulty_distribution' not in raw:
            raw['difficulty_distribution'] = raw['difficultySplit']
        if 'difficulty_split' in raw and 'difficulty_distribution' not in raw:
            raw['difficulty_distribution'] = raw['difficulty_split']
        if 'unit_weightage' in raw and 'unit_weightage' not in raw:
            raw['unit_weightage'] = raw['unit_weightage']
        if 'ai_model' in raw and 'model_generator' not in raw:
            raw['model_generator'] = raw['ai_model']
        if 'aiModel' in raw and 'model_generator' not in raw:
            raw['model_generator'] = raw['aiModel']

        # 3. Numeric string conversions
        for num_field in ['total_marks', 'duration']:
            val = raw.get(num_field)
            if isinstance(val, str) and val.strip().isdigit():
                raw[num_field] = int(val.strip())

        # 4. Boolean string conversions
        for bool_field in ['avoid_repeats', 'accept_capacity_override']:
            val = raw.get(bool_field)
            if isinstance(val, str):
                raw[bool_field] = val.strip().lower() in ('true', '1', 'yes')

        # 5. Empty strings to None / default for optional fields
        for opt_field in ['class_semester', 'exam_type', 'model_generator', 'model_validator', 'model_fallback']:
            val = raw.get(opt_field)
            if isinstance(val, str) and val.strip() == '':
                raw[opt_field] = ''

        # 6. Normalize topics if passed as comma-separated or plain string (non-JSON)
        if 'topics' in raw and isinstance(raw['topics'], str):
            val_trimmed = raw['topics'].strip()
            if not (val_trimmed.startswith('[') and val_trimmed.endswith(']')):
                raw['topics'] = [t.strip() for t in val_trimmed.split(',') if t.strip()]

        return super().to_internal_value(raw)

    def validate_sections(self, value):
        if not value:
            raise serializers.ValidationError("At least one section must be specified.")

        # If passed as dictionary (e.g. blueprint format: {'mcq': {'count': 10, 'marks': 2}}), convert to list
        if isinstance(value, dict):
            dict_sections = []
            for q_type, q_cfg in value.items():
                if isinstance(q_cfg, dict):
                    if q_cfg.get('enabled', True) is False:
                        continue
                    cnt = int(q_cfg.get('count', 0) or 0)
                    m = int(q_cfg.get('marks', q_cfg.get('marks_per_question', 1)) or 1)
                    if cnt > 0:
                        dict_sections.append({
                            'type': q_type,
                            'count': cnt,
                            'marks_per_question': m,
                            'section_name': q_cfg.get('section_name', q_type),
                            'difficulty': q_cfg.get('difficulty', 'medium'),
                            'unit': q_cfg.get('unit', ''),
                        })
            value = dict_sections

        if not isinstance(value, list):
            raise serializers.ValidationError("Expected a list of sections.")

        cleaned_sections = []
        for s in value:
            if isinstance(s, dict):
                if s.get('enabled', True) is False:
                    continue
                cnt = int(s.get('count', 0) or 0)
                if cnt <= 0:
                    continue
                if 'marks' in s and 'marks_per_question' not in s:
                    s['marks_per_question'] = s['marks']
                cleaned_sections.append(s)

        if not cleaned_sections:
            raise serializers.ValidationError("At least one section with count > 0 must be provided.")

        sec_serializer = SectionSerializer(data=cleaned_sections, many=True)
        if not sec_serializer.is_valid():
            raise serializers.ValidationError(sec_serializer.errors)

        return sec_serializer.validated_data

    def validate_topics(self, value):
        if isinstance(value, str):
            value = [t.strip() for t in value.split(',') if t.strip()]
        if not isinstance(value, list) or len(value) == 0:
            return ['General Curriculum']
        clean = [str(t).strip() for t in value if str(t).strip()]
        return clean or ['General Curriculum']

    def validate(self, attrs):
        total_marks = attrs.get('total_marks')
        sections = attrs.get('sections', [])

        if not sections:
            raise serializers.ValidationError({
                'sections': "Please configure at least one question section with count > 0."
            })

        # Marks exact sum check
        allocated_marks = sum(int(s['count']) * int(s['marks_per_question']) for s in sections)
        if allocated_marks != total_marks:
            raise serializers.ValidationError({
                'total_marks': f"Allocated {allocated_marks} / {total_marks} marks. Adjust question counts or marks to match the exam total exactly."
            })

        # Difficulty distribution check if provided
        diff = attrs.get('difficulty_distribution')
        if diff and isinstance(diff, dict):
            numeric_diff = {}
            for k, v in diff.items():
                try:
                    numeric_diff[k] = int(v)
                except (ValueError, TypeError):
                    pass
            if numeric_diff:
                diff_sum = sum(numeric_diff.values())
                if diff_sum != 100:
                    raise serializers.ValidationError({
                        'difficulty_distribution': f"Difficulty distribution percentages must sum to 100% (currently {diff_sum}%)."
                    })
                attrs['difficulty_distribution'] = numeric_diff

        return attrs


class GenerationJobSerializer(serializers.ModelSerializer):
    # Compatibility aliases for GenerationProgressModal and PaperGenerationJob
    exam_id = serializers.SerializerMethodField()
    exam_title = serializers.SerializerMethodField()
    progress = serializers.IntegerField(source='progress_percent', read_only=True)
    current_step = serializers.CharField(source='progress_message', read_only=True)
    target_marks = serializers.IntegerField(source='total_marks', read_only=True)
    actual_marks = serializers.IntegerField(source='allocated_marks', read_only=True)
    warnings = serializers.SerializerMethodField()
    elapsed_seconds = serializers.SerializerMethodField()
    question_count_requested = serializers.SerializerMethodField()
    question_count_generated = serializers.SerializerMethodField()
    questions = serializers.SerializerMethodField()

    class Meta:
        model = GenerationJob
        fields = [
            'id', 'title', 'subject', 'class_semester', 'exam_type',
            'total_marks', 'allocated_marks', 'duration', 'blueprint',
            'status', 'progress_percent', 'progress_message', 'current_slot_index',
            'generated_questions', 'model_assignments', 'summary',
            'error_message', 'saved_paper_id', 'saved_exam_id',
            'created_at', 'updated_at', 'completed_at',
            # Compatibility fields
            'exam_id', 'exam_title', 'progress', 'current_step',
            'target_marks', 'actual_marks', 'warnings', 'elapsed_seconds',
            'question_count_requested', 'question_count_generated', 'questions',
        ]

    def get_exam_id(self, obj):
        return obj.saved_exam_id or obj.id

    def get_exam_title(self, obj):
        return obj.title

    def get_warnings(self, obj):
        return []

    def get_elapsed_seconds(self, obj):
        if obj.completed_at and obj.created_at:
            return int((obj.completed_at - obj.created_at).total_seconds())
        from django.utils import timezone
        return int((timezone.now() - obj.created_at).total_seconds())

    def get_question_count_requested(self, obj):
        return len(obj.blueprint or [])

    def get_question_count_generated(self, obj):
        return len(obj.generated_questions or [])

    def get_questions(self, obj):
        return obj.generated_questions or []


class GenerationLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = GenerationLog
        fields = [
            'id', 'job_id', 'level', 'category', 'slot_number',
            'model_name', 'message', 'details', 'created_at',
        ]


class EditQuestionSerializer(serializers.Serializer):
    question_number = serializers.IntegerField(min_value=1)
    question = serializers.CharField()
    options = serializers.ListField(child=serializers.CharField(), required=False, default=list)
    answer = serializers.CharField()
    marks = serializers.IntegerField(min_value=1)

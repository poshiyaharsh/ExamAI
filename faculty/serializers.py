import logging

from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.db import OperationalError, ProgrammingError, transaction
from rest_framework import serializers

from admins.models import AdminInstitution
from .models import FacultyProfile, Paper, PaperQuestion, SyllabusUpload


logger = logging.getLogger(__name__)


def _validation_message(exc, fallback_message):
    message = str(exc).strip()
    if settings.DEBUG and message:
        return message
    return fallback_message


class FacultySignupSerializer(serializers.Serializer):
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8)
    institution_id = serializers.IntegerField(write_only=True)
    department = serializers.CharField(max_length=120, required=True, allow_blank=False, trim_whitespace=True)

    def validate_email(self, value):
        normalized = value.lower().strip()
        if User.objects.filter(username=normalized).exists():
            raise serializers.ValidationError('Registration could not be completed with this email. If you have an account, please sign in or reset your password.')
        return normalized

    def validate(self, attrs):
        institution = AdminInstitution.objects.filter(id=attrs.get('institution_id')).first()
        if not institution:
            raise serializers.ValidationError({'institution_id': 'Please select a valid institution.'})

        raw_dept = attrs.get('department')
        from api.utils.departments import validate_department_name
        is_valid, norm_dept = validate_department_name(raw_dept, institution=institution)
        if not is_valid:
            raise serializers.ValidationError(
                {'department': f'Invalid department "{raw_dept}". Please select a valid department from the allowed list.'}
            )
        attrs['department'] = norm_dept
        attrs['institution'] = institution
        return attrs

    def create(self, validated_data):
        email = validated_data['email']
        institution = validated_data['institution']
        department = validated_data['department']

        try:
            with transaction.atomic():
                user = User.objects.create_user(
                    username=email,
                    email=email,
                    first_name=validated_data['first_name'].strip(),
                    last_name=validated_data['last_name'].strip(),
                    password=validated_data['password'],
                )
                FacultyProfile.objects.create(user=user, institution=institution, department=department)
                return user
        except (OperationalError, ProgrammingError) as exc:
            raise serializers.ValidationError(
                _validation_message(exc, 'Database schema issue detected. Please run migrations.')
            ) from exc
        except Exception as exc:
            logger.exception('Unexpected faculty signup error')
            raise serializers.ValidationError(
                _validation_message(exc, 'Unable to create faculty account.')
            ) from exc


class FacultyLoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        email = attrs['email'].lower().strip()
        password = attrs['password']
        user = authenticate(username=email, password=password)

        if not user or not FacultyProfile.objects.filter(user=user).exists():
            raise serializers.ValidationError('Invalid email, password, or unauthorized role.')

        attrs['user'] = user
        return attrs


class FacultyProfileSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    email = serializers.EmailField(source='user.email', read_only=True)
    institution = serializers.SerializerMethodField()

    class Meta:
        model = FacultyProfile
        fields = ('full_name', 'email', 'employee_id', 'department', 'institution')
        read_only_fields = ('full_name', 'email', 'employee_id')

    def get_full_name(self, obj):
        full_name = f'{obj.user.first_name} {obj.user.last_name}'.strip()
        return full_name or obj.user.username

    def get_institution(self, obj):
        if not obj.institution:
            return None
        return {
            'id': obj.institution.id,
            'institution_name': obj.institution.institution_name,
            'institution_code': obj.institution.institution_code,
        }


class FacultyProfileDepartmentUpdateSerializer(serializers.ModelSerializer):
    department = serializers.CharField(max_length=120, allow_blank=False, trim_whitespace=True)

    class Meta:
        model = FacultyProfile
        fields = ('department',)

    def validate(self, attrs):
        if self.instance and self.instance.department and self.instance.department.strip() not in ('', 'Unassigned', 'unassigned'):
            raise serializers.ValidationError({'department': 'Department cannot be changed once assigned. Contact admin to request a change.'})

        raw_dept = attrs.get('department', '').strip()
        if not raw_dept:
            raise serializers.ValidationError({'department': 'Department must not be empty.'})

        from api.utils.departments import validate_department_name
        institution = getattr(self.instance, 'institution', None)
        is_valid, norm_dept = validate_department_name(raw_dept, institution=institution)
        if not is_valid:
            raise serializers.ValidationError(
                {'department': f'Invalid department "{raw_dept}". Please select a valid department from the allowed list.'}
            )
        attrs['department'] = norm_dept
        return attrs


ALLOWED_AI_MODELS = (
    'qwen2.5:3b-instruct',
    'llama3.2:3b',
    'phi3:mini',
    'ollama-qwen2.5-3b',
    'ollama-llama3.2-3b',
    'ollama-phi3-mini',
    'qwen2.5-3b',
    'llama3.2-3b',
    'phi3-mini',
)
ALLOWED_QUESTION_TYPES = ('MCQ', 'Subjective', 'True/False', 'Fill in the Blanks')
ALLOWED_DIFFICULTIES = ('Easy', 'Medium', 'Hard')


class SyllabusUploadSerializer(serializers.ModelSerializer):
    class Meta:
        model = SyllabusUpload
        fields = ('id', 'original_filename', 'extracted_text', 'created_at')


class PaperQuestionSerializer(serializers.ModelSerializer):
    type = serializers.CharField(source='question_type')

    class Meta:
        model = PaperQuestion
        fields = ('question_number', 'type', 'difficulty', 'marks', 'question', 'options', 'answer')


class PaperSerializer(serializers.ModelSerializer):
    model = serializers.CharField(source='ai_model')
    questions = PaperQuestionSerializer(many=True)
    institution = serializers.SerializerMethodField()

    class Meta:
        model = Paper
        fields = (
            'id',
            'title',
            'duration',
            'total_marks',
            'model',
            'topics',
            'question_types',
            'difficulty_distribution',
            'questions',
            'institution',
            'created_at',
        )

    def get_institution(self, obj):
        return {
            'id': obj.institution_id,
            'institution_name': obj.institution.institution_name,
            'institution_code': obj.institution.institution_code,
        }


class PaperHistorySerializer(serializers.ModelSerializer):
    questions = serializers.SerializerMethodField()
    difficulty = serializers.SerializerMethodField()
    model = serializers.CharField(source='ai_model')

    class Meta:
        model = Paper
        fields = ('id', 'title', 'duration', 'total_marks', 'model', 'questions', 'difficulty', 'created_at')

    def get_questions(self, obj):
        return obj.questions.count()

    def get_difficulty(self, obj):
        distribution = obj.difficulty_distribution or {}
        if not distribution:
            return 'Medium'
        return max(distribution.items(), key=lambda item: item[1])[0]


class GeneratePaperSerializer(serializers.Serializer):
    syllabus_upload_id = serializers.IntegerField()
    title = serializers.CharField(max_length=255)
    duration = serializers.IntegerField(min_value=1)
    total_marks = serializers.IntegerField(min_value=1)
    model = serializers.ChoiceField(choices=ALLOWED_AI_MODELS)
    topics = serializers.ListField(child=serializers.CharField(max_length=120), allow_empty=False)
    question_types = serializers.ListField(child=serializers.ChoiceField(choices=ALLOWED_QUESTION_TYPES), allow_empty=False)
    difficulty_distribution = serializers.DictField(child=serializers.IntegerField(min_value=0, max_value=100))

    def validate_title(self, value):
        cleaned = value.strip()
        if not cleaned:
            raise serializers.ValidationError('Exam Title is required.')
        return cleaned

    def validate_topics(self, value):
        topics = [topic.strip() for topic in value if topic.strip()]
        if not topics:
            raise serializers.ValidationError('At least one topic is required.')
        return topics

    def validate_question_types(self, value):
        unique_types = []
        for question_type in value:
            if question_type not in unique_types:
                unique_types.append(question_type)
        if not unique_types:
            raise serializers.ValidationError('At least one question type is required.')
        return unique_types

    def validate_difficulty_distribution(self, value):
        normalized = {difficulty: int(value.get(difficulty, 0)) for difficulty in ALLOWED_DIFFICULTIES}
        if sum(normalized.values()) != 100:
            raise serializers.ValidationError('Difficulty percentages must equal exactly 100%.')
        return normalized

    def validate(self, attrs):
        faculty = self.context['faculty']
        upload = (
            SyllabusUpload.objects.filter(
                id=attrs['syllabus_upload_id'],
                faculty=faculty,
                institution=faculty.institution,
            )
            .first()
        )
        if not upload:
            raise serializers.ValidationError({'syllabus_upload_id': 'Uploaded syllabus not found.'})
        attrs['syllabus_upload'] = upload
        return attrs

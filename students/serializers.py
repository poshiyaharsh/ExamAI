import logging

from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.db import OperationalError, ProgrammingError, transaction
from rest_framework import serializers

from admins.models import AdminInstitution
from faculty.models import Paper
from .models import ExamAttempt, StudentProfile


logger = logging.getLogger(__name__)


def _validation_message(exc, fallback_message):
    message = str(exc).strip()
    if settings.DEBUG and message:
        return message
    return fallback_message


class StudentSignupSerializer(serializers.Serializer):
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
                StudentProfile.objects.create(user=user, institution=institution, department=department)
                return user
        except (OperationalError, ProgrammingError) as exc:
            raise serializers.ValidationError(
                _validation_message(exc, 'Database schema issue detected. Please run migrations.')
            ) from exc
        except Exception as exc:
            logger.exception('Unexpected student signup error')
            raise serializers.ValidationError(
                _validation_message(exc, 'Unable to create student account.')
            ) from exc


class StudentLoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        email = attrs['email'].lower().strip()
        password = attrs['password']
        user = authenticate(username=email, password=password)

        if not user or not StudentProfile.objects.filter(user=user).exists():
            raise serializers.ValidationError('Invalid email, password, or unauthorized role.')

        attrs['user'] = user
        return attrs


class StudentProfileSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    email = serializers.EmailField(source='user.email', read_only=True)
    institution = serializers.SerializerMethodField()

    class Meta:
        model = StudentProfile
        fields = ('full_name', 'email', 'student_id', 'department', 'institution')
        read_only_fields = ('full_name', 'email', 'student_id')

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


class StudentProfileDepartmentUpdateSerializer(serializers.ModelSerializer):
    department = serializers.CharField(max_length=120, allow_blank=False, trim_whitespace=True)

    class Meta:
        model = StudentProfile
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


class StudentExamSummarySerializer(serializers.ModelSerializer):
    faculty = serializers.SerializerMethodField()
    question_count = serializers.SerializerMethodField()
    published = serializers.BooleanField(source='is_published')

    class Meta:
        model = Paper
        fields = ('id', 'title', 'faculty', 'duration', 'total_marks', 'question_count', 'published', 'created_at')

    def get_faculty(self, obj):
        return f'{obj.faculty.user.first_name} {obj.faculty.user.last_name}'.strip() or obj.faculty.user.username

    def get_question_count(self, obj):
        return obj.questions.count()


class StudentExamDetailSerializer(serializers.ModelSerializer):
    faculty = serializers.SerializerMethodField()
    questions = serializers.SerializerMethodField()

    class Meta:
        model = Paper
        fields = ('id', 'title', 'faculty', 'duration', 'total_marks', 'questions', 'created_at')

    def get_faculty(self, obj):
        return f'{obj.faculty.user.first_name} {obj.faculty.user.last_name}'.strip() or obj.faculty.user.username

    def get_questions(self, obj):
        return [
            {
                'question_number': question.question_number,
                'type': question.question_type,
                'difficulty': question.difficulty,
                'marks': question.marks,
                'question': question.question,
                'options': question.options,
            }
            for question in obj.questions.all()
        ]


class ExamAttemptSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExamAttempt
        fields = ('id', 'student', 'paper', 'answers', 'score', 'max_score', 'status', 'started_at', 'submitted_at')

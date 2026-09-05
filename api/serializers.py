from rest_framework import serializers

from admins.models import AdminDepartment, AdminInstitution
from .models import Exam, Question, StudentAnswer, StudentAttempt


class TestMessageSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=100)
    message = serializers.CharField(max_length=500)


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, min_length=8)

    def validate_current_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError('Current password is incorrect.')
        return value

    def validate_new_password(self, value):
        has_letter = any(char.isalpha() for char in value)
        has_number = any(char.isdigit() for char in value)
        if not (has_letter and has_number):
            raise serializers.ValidationError('New password must include at least one letter and one number.')
        return value


class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        return value.lower().strip()


class VerifyOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp = serializers.CharField(max_length=6, min_length=6)

    def validate_email(self, value):
        return value.lower().strip()

    def validate_otp(self, value):
        if not value.isdigit():
            raise serializers.ValidationError('OTP must be a 6-digit number.')
        return value


class ResetPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()
    reset_token = serializers.CharField()
    new_password = serializers.CharField(write_only=True, min_length=8)
    confirm_password = serializers.CharField(write_only=True, min_length=8)

    def validate_email(self, value):
        return value.lower().strip()

    def validate_new_password(self, value):
        has_letter = any(char.isalpha() for char in value)
        has_number = any(char.isdigit() for char in value)
        if not (has_letter and has_number):
            raise serializers.ValidationError('New password must include at least one letter and one number.')
        return value

    def validate(self, attrs):
        if attrs['new_password'] != attrs['confirm_password']:
            raise serializers.ValidationError({'confirm_password': 'Confirm password must match new password.'})
        return attrs


class InstitutionSerializer(serializers.ModelSerializer):
    class Meta:
        model = AdminInstitution
        fields = ('id', 'institution_name', 'institution_code')


class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = AdminDepartment
        fields = ('id', 'department_name')


class QuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Question
        fields = (
            'id', 'order', 'question_type', 'difficulty', 'text', 'options',
            'correct_answer', 'model_answer', 'marks', 'topic',
        )
        read_only_fields = ('id', 'order')


class FacultyQuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Question
        fields = (
            'id', 'order', 'question_type', 'difficulty', 'text', 'options',
            'correct_answer', 'model_answer', 'marks', 'topic',
        )
        read_only_fields = ('id', 'order')


class ExamListSerializer(serializers.ModelSerializer):
    question_count = serializers.IntegerField(read_only=True)
    attempts_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Exam
        fields = (
            'id', 'title', 'duration_minutes', 'total_marks', 'topics',
            'difficulty_distribution', 'question_types', 'ai_model_used',
            'status', 'starts_at', 'ends_at', 'created_at', 'updated_at',
            'question_count', 'attempts_count',
        )


class ExamDetailSerializer(serializers.ModelSerializer):
    questions = FacultyQuestionSerializer(many=True, read_only=True)

    class Meta:
        model = Exam
        fields = (
            'id', 'title', 'duration_minutes', 'total_marks', 'topics',
            'difficulty_distribution', 'question_types', 'ai_model_used',
            'source_syllabus_text', 'status', 'starts_at', 'ends_at',
            'created_at', 'updated_at', 'questions',
        )
        read_only_fields = ('id', 'ai_model_used', 'source_syllabus_text', 'created_at', 'updated_at', 'questions')


class ExamUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Exam
        fields = (
            'title', 'duration_minutes', 'total_marks', 'topics',
            'difficulty_distribution', 'question_types', 'starts_at', 'ends_at', 'status',
        )


class QuestionUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Question
        fields = (
            'question_type', 'difficulty', 'text', 'options',
            'correct_answer', 'model_answer', 'marks', 'topic',
        )


class StudentQuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Question
        fields = ('id', 'order', 'question_type', 'difficulty', 'text', 'options', 'marks', 'topic')


class StudentExamSerializer(serializers.ModelSerializer):
    questions = StudentQuestionSerializer(many=True, read_only=True)

    class Meta:
        model = Exam
        fields = ('id', 'title', 'duration_minutes', 'total_marks', 'topics', 'starts_at', 'ends_at', 'questions')


class StudentAnswerSerializer(serializers.ModelSerializer):
    question_text = serializers.CharField(source='question.text', read_only=True)
    question_type = serializers.CharField(source='question.question_type', read_only=True)
    correct_answer = serializers.JSONField(source='question.correct_answer', read_only=True)

    class Meta:
        model = StudentAnswer
        fields = ('question', 'question_text', 'question_type', 'correct_answer', 'answer_text', 'is_correct', 'score_awarded', 'ai_feedback')


class StudentAttemptSerializer(serializers.ModelSerializer):
    answers = StudentAnswerSerializer(many=True, read_only=True)
    exam_title = serializers.CharField(source='exam.title', read_only=True)
    exam_total_marks = serializers.IntegerField(source='exam.total_marks', read_only=True)

    class Meta:
        model = StudentAttempt
        fields = ('id', 'exam', 'exam_title', 'exam_total_marks', 'started_at', 'submitted_at', 'status', 'total_score', 'answers')

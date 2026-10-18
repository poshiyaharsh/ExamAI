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
    topic = serializers.SerializerMethodField()

    class Meta:
        model = Question
        fields = (
            'id', 'order', 'question_type', 'difficulty', 'text', 'options',
            'correct_answer', 'model_answer', 'accepted_answers', 'rubric',
            'word_limit', 'source', 'marks', 'topic',
        )
        read_only_fields = ('id', 'order')

    def get_topic(self, obj):
        return obj.topic.name if obj.topic else (obj.topic_text or '')


class FacultyQuestionSerializer(serializers.ModelSerializer):
    topic = serializers.SerializerMethodField()

    class Meta:
        model = Question
        fields = (
            'id', 'order', 'question_type', 'difficulty', 'text', 'options',
            'correct_answer', 'model_answer', 'accepted_answers', 'rubric',
            'word_limit', 'source', 'marks', 'topic',
        )
        read_only_fields = ('id', 'order')

    def get_topic(self, obj):
        return obj.topic.name if obj.topic else (obj.topic_text or '')


class ExamListSerializer(serializers.ModelSerializer):
    question_count = serializers.IntegerField(read_only=True)
    attempts_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Exam
        fields = (
            'id', 'title', 'department', 'subject', 'description', 'duration_minutes',
            'total_marks', 'target_total_marks', 'marks_shortfall', 'topics', 'source_documents',
            'difficulty_distribution', 'question_types', 'ai_model_used',
            'status', 'error_message', 'seed', 'request_hash', 'is_immutable', 'is_reviewed',
            'shuffle_questions', 'shuffle_options', 'random_subset_size', 'max_warnings',
            'allow_retakes', 'show_result_immediately',
            'starts_at', 'ends_at', 'created_at', 'updated_at',
            'question_count', 'attempts_count',
        )


class ExamDetailSerializer(serializers.ModelSerializer):
    questions = FacultyQuestionSerializer(many=True, read_only=True)

    class Meta:
        model = Exam
        fields = (
            'id', 'title', 'department', 'subject', 'description', 'duration_minutes',
            'total_marks', 'target_total_marks', 'marks_shortfall', 'topics', 'source_documents',
            'difficulty_distribution', 'question_types', 'ai_model_used',
            'source_syllabus_text', 'status', 'starts_at', 'ends_at',
            'error_message', 'seed', 'request_hash', 'validation_report', 'is_immutable', 'is_reviewed',
            'shuffle_questions', 'shuffle_options', 'random_subset_size', 'max_warnings',
            'allow_retakes', 'show_result_immediately',
            'created_at', 'updated_at', 'questions',
        )
        read_only_fields = ('id', 'ai_model_used', 'source_syllabus_text', 'created_at', 'updated_at', 'questions')


class ExamUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Exam
        fields = (
            'title', 'department', 'duration_minutes', 'total_marks', 'topics',
            'difficulty_distribution', 'question_types', 'starts_at', 'ends_at', 'status',
            'shuffle_questions', 'shuffle_options', 'random_subset_size', 'max_warnings',
            'allow_retakes', 'show_result_immediately',
        )


class QuestionUpdateSerializer(serializers.ModelSerializer):
    topic = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = Question
        fields = (
            'question_type', 'difficulty', 'text', 'options',
            'correct_answer', 'model_answer', 'accepted_answers', 'rubric',
            'word_limit', 'source', 'marks', 'topic',
        )

    def update(self, instance, validated_data):
        if 'topic' in validated_data:
            instance.topic_text = validated_data.pop('topic')
        return super().update(instance, validated_data)


class StudentQuestionSerializer(serializers.ModelSerializer):
    topic = serializers.SerializerMethodField()
    options = serializers.SerializerMethodField()
    marks = serializers.SerializerMethodField()

    class Meta:
        model = Question
        fields = ('id', 'order', 'question_type', 'difficulty', 'text', 'options', 'marks', 'topic', 'word_limit')

    def get_topic(self, obj):
        return obj.topic.name if obj.topic else (obj.topic_text or '')

    def get_options(self, obj):
        if not obj.options:
            return []
        from .utils.options import clean_options_list
        return clean_options_list(obj.options)

    def get_marks(self, obj):
        try:
            return float(obj.marks) if obj.marks is not None else 0.0
        except (ValueError, TypeError):
            return 0.0


class StudentExamSerializer(serializers.ModelSerializer):
    questions = StudentQuestionSerializer(many=True, read_only=True)
    total_marks = serializers.SerializerMethodField()

    class Meta:
        model = Exam
        fields = ('id', 'title', 'subject', 'description', 'department', 'duration_minutes', 'total_marks', 'topics', 'starts_at', 'ends_at', 'questions')

    def get_total_marks(self, obj):
        try:
            return float(obj.total_marks) if obj.total_marks is not None else 0.0
        except (ValueError, TypeError):
            return 0.0



class StudentAnswerSerializer(serializers.ModelSerializer):
    question_text = serializers.CharField(source='question.text', read_only=True)
    question_type = serializers.CharField(source='question.question_type', read_only=True)
    correct_answer = serializers.SerializerMethodField()
    is_correct = serializers.SerializerMethodField()
    score_awarded = serializers.SerializerMethodField()
    ai_feedback = serializers.SerializerMethodField()

    class Meta:
        model = StudentAnswer
        fields = ('question', 'question_text', 'question_type', 'correct_answer', 'answer_text', 'blank_answers', 'is_correct', 'score_awarded', 'ai_feedback')

    def _can_reveal_answers(self, obj):
        attempt = getattr(obj, 'attempt', None)
        if not attempt:
            return False
        if not getattr(attempt.exam, 'show_result_immediately', True):
            return False
        return attempt.status in (StudentAttempt.Status.SUBMITTED, StudentAttempt.Status.AUTO_SUBMITTED, StudentAttempt.Status.EVALUATED)

    def get_correct_answer(self, obj):
        if self._can_reveal_answers(obj):
            return obj.question.correct_answer
        return None

    def get_is_correct(self, obj):
        if self._can_reveal_answers(obj):
            return obj.is_correct
        return None

    def get_score_awarded(self, obj):
        if self._can_reveal_answers(obj):
            return obj.score_awarded
        return None

    def get_ai_feedback(self, obj):
        if self._can_reveal_answers(obj):
            feedback = str(obj.ai_feedback or '').strip()
            if 'Automatic evaluation failed' in feedback or 'HTTP 404' in feedback or 'Traceback' in feedback:
                return 'Answer submitted successfully. Pending teacher evaluation.'
            return feedback
        return ''


class StudentAttemptSerializer(serializers.ModelSerializer):
    answers = StudentAnswerSerializer(many=True, read_only=True)
    exam_title = serializers.CharField(source='exam.title', read_only=True)
    exam_total_marks = serializers.SerializerMethodField()

    class Meta:
        model = StudentAttempt
        fields = (
            'id', 'exam', 'exam_title', 'exam_total_marks', 'attempt_number',
            'started_at', 'submitted_at', 'expires_at', 'status', 'submit_reason',
            'violation_count', 'max_score', 'total_score', 'answers',
        )

    def get_exam_total_marks(self, obj):
        try:
            return float(obj.max_score or obj.exam.total_marks or 0.0)
        except (ValueError, TypeError):
            return 0.0

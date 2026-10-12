"""Serializers for Question Bank REST APIs."""

from rest_framework import serializers
from django.db import transaction
from django.utils import timezone

from api.models import (
    Option,
    Question,
    QuestionAuditLog,
    QuestionImportLog,
    Subject,
    Topic,
)
from api.validators.question_bank import (
    compute_text_hash,
    is_question_used_in_exam,
    validate_question_payload,
)


class OptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Option
        fields = ('id', 'text', 'is_correct', 'order')


class SubjectSerializer(serializers.ModelSerializer):
    question_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = Subject
        fields = ('id', 'name', 'code', 'department', 'question_count', 'created_at', 'updated_at')
        read_only_fields = ('id', 'created_at', 'updated_at')

    def validate(self, attrs):
        request = self.context.get('request')
        tenant = getattr(request, 'tenant', None)
        name = attrs.get('name', '').strip()
        dept = attrs.get('department', '').strip()

        if not name:
            raise serializers.ValidationError({'name': 'Subject name is required.'})
        if not dept:
            raise serializers.ValidationError({'department': 'Department is required.'})

        # Check uniqueness per (institution, department, name)
        qs = Subject.objects.filter(institution=tenant, department=dept, name__iexact=name)
        if self.instance:
            qs = qs.exclude(id=self.instance.id)
        if qs.exists():
            raise serializers.ValidationError({'name': f"Subject '{name}' already exists in department '{dept}'."})

        return attrs


class TopicSerializer(serializers.ModelSerializer):
    subject_name = serializers.CharField(source='subject.name', read_only=True)
    question_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = Topic
        fields = ('id', 'name', 'subject', 'subject_name', 'question_count', 'created_at', 'updated_at')
        read_only_fields = ('id', 'created_at', 'updated_at')

    def validate(self, attrs):
        request = self.context.get('request')
        tenant = getattr(request, 'tenant', None)
        name = attrs.get('name', '').strip()
        subject = attrs.get('subject') or (self.instance.subject if self.instance else None)

        if not name:
            raise serializers.ValidationError({'name': 'Topic name is required.'})
        if not subject:
            raise serializers.ValidationError({'subject': 'Subject is required.'})

        if subject.institution_id != tenant.id:
            raise serializers.ValidationError({'subject': 'Invalid subject for this institution.'})

        # Check uniqueness per (subject, name)
        qs = Topic.objects.filter(subject=subject, name__iexact=name)
        if self.instance:
            qs = qs.exclude(id=self.instance.id)
        if qs.exists():
            raise serializers.ValidationError({'name': f"Topic '{name}' already exists for subject '{subject.name}'."})

        return attrs


class QuestionListSerializer(serializers.ModelSerializer):
    subject_name = serializers.CharField(source='subject.name', read_only=True, default='')
    topic_name = serializers.CharField(source='topic.name', read_only=True, default='')
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True, default='')
    options_count = serializers.SerializerMethodField()

    class Meta:
        model = Question
        fields = (
            'id',
            'text',
            'department',
            'subject',
            'subject_name',
            'topic',
            'topic_name',
            'question_type',
            'difficulty',
            'marks',
            'negative_marks',
            'status',
            'times_used',
            'last_used_at',
            'version',
            'tags',
            'created_by_name',
            'options_count',
            'created_at',
            'updated_at',
        )

    def get_options_count(self, obj):
        if hasattr(obj, 'options_count_annotated'):
            return obj.options_count_annotated
        return obj.option_items.count()


class QuestionAuditLogSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.get_full_name', read_only=True, default='')

    class Meta:
        model = QuestionAuditLog
        fields = ('id', 'action', 'user_name', 'changes', 'timestamp')


class QuestionDetailSerializer(serializers.ModelSerializer):
    subject_name = serializers.CharField(source='subject.name', read_only=True, default='')
    topic_name = serializers.CharField(source='topic.name', read_only=True, default='')
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True, default='')
    options = OptionSerializer(source='option_items', many=True, read_only=True)
    audit_logs = QuestionAuditLogSerializer(many=True, read_only=True)
    usage_info = serializers.SerializerMethodField()

    class Meta:
        model = Question
        fields = (
            'id',
            'text',
            'explanation',
            'department',
            'subject',
            'subject_name',
            'topic',
            'topic_name',
            'question_type',
            'difficulty',
            'marks',
            'negative_marks',
            'status',
            'is_deleted',
            'version',
            'times_used',
            'last_used_at',
            'tags',
            'model_answer',
            'options',
            'created_by_name',
            'created_at',
            'updated_at',
            'usage_info',
            'audit_logs',
        )

    def get_usage_info(self, obj):
        used, reason = is_question_used_in_exam(obj)
        exams_list = []
        if obj.exam:
            exams_list.append({
                'id': obj.exam.id,
                'title': obj.exam.title,
                'status': obj.exam.status,
            })
        return {
            'is_locked': used,
            'reason': reason,
            'times_used': obj.times_used,
            'last_used_at': obj.last_used_at,
            'associated_exams': exams_list,
        }


class QuestionCreateUpdateSerializer(serializers.ModelSerializer):
    options = serializers.ListField(child=serializers.DictField(), required=False)
    warnings = serializers.ListField(read_only=True)
    topic_name = serializers.CharField(source='topic_text', required=False, allow_blank=True, default='')

    class Meta:
        model = Question
        fields = (
            'id',
            'text',
            'explanation',
            'department',
            'subject',
            'topic',
            'topic_name',
            'question_type',
            'difficulty',
            'marks',
            'negative_marks',
            'status',
            'tags',
            'model_answer',
            'options',
            'version',
            'warnings',
        )
        read_only_fields = ('id', 'version', 'warnings')

    def validate(self, attrs):
        request = self.context.get('request')
        tenant = getattr(request, 'tenant', None)
        if not tenant:
            raise serializers.ValidationError('No active institution context found.')

        # Call centralized Zero-Mistakes validator
        cleaned_data, warnings = validate_question_payload(
            payload={**self.initial_data, **attrs},
            institution=tenant,
            instance=self.instance,
            allow_warnings=True,
        )
        self.context['warnings'] = warnings
        self.context['cleaned_options'] = cleaned_data.pop('options', [])
        return cleaned_data

    @transaction.atomic
    def create(self, validated_data):
        request = self.context.get('request')
        tenant = request.tenant
        options_data = self.context.get('cleaned_options', [])

        validated_data['institution'] = tenant
        validated_data['created_by'] = request.user
        validated_data['version'] = 1

        # Legacy fields synchronization
        if options_data:
            validated_data['options'] = [o['text'] for o in options_data]
        topic_name = validated_data.pop('topic_name', '')
        if topic_name and not validated_data.get('topic_text'):
            validated_data['topic_text'] = topic_name

        question = Question.objects.create(**validated_data)

        # Save Option rows
        option_objs = [
            Option(
                question=question,
                text=opt['text'],
                is_correct=opt['is_correct'],
                order=opt.get('order', idx),
            )
            for idx, opt in enumerate(options_data, start=1)
        ]
        if option_objs:
            Option.objects.bulk_create(option_objs)

        # Audit log
        QuestionAuditLog.objects.create(
            institution=tenant,
            question=question,
            user=request.user,
            action='CREATE',
            changes={'created': True, 'text': question.text[:100]},
        )

        return question

    @transaction.atomic
    def update(self, instance, validated_data):
        request = self.context.get('request')
        tenant = request.tenant
        options_data = self.context.get('cleaned_options', [])

        # Check Rule 9: If used in published/ongoing exam, prevent mutation or require cloning
        is_used, reason = is_question_used_in_exam(instance)
        if is_used:
            # Check if critical exam content changed (text, marks, options)
            text_changed = 'text' in validated_data and validated_data['text'] != instance.text
            marks_changed = 'marks' in validated_data and validated_data['marks'] != instance.marks
            if text_changed or marks_changed or options_data:
                raise serializers.ValidationError({
                    'detail': f'Cannot directly modify a question used in active/completed exams ({reason}). Please duplicate this question to create a new revision instead.'
                })

        topic_name = validated_data.pop('topic_name', None)
        if topic_name is not None:
            validated_data['topic_text'] = topic_name

        # Track changes for audit log
        changes_tracked = {}
        for k, v in validated_data.items():
            old_val = getattr(instance, k, None)
            if old_val != v:
                changes_tracked[k] = {'old': str(old_val), 'new': str(v)}
                setattr(instance, k, v)

        # Increment version
        instance.version += 1

        # Synchronize legacy fields
        if options_data:
            instance.options = [o['text'] for o in options_data]
            correct_opts = [o['text'] for o in options_data if o.get('is_correct')]
            instance.correct_answer = correct_opts[0] if len(correct_opts) == 1 else correct_opts
            changes_tracked['options'] = f'Updated {len(options_data)} options'

        instance.save()

        # Update options
        if options_data:
            instance.option_items.all().delete()
            option_objs = [
                Option(
                    question=instance,
                    text=opt['text'],
                    is_correct=opt['is_correct'],
                    order=opt.get('order', idx),
                )
                for idx, opt in enumerate(options_data, start=1)
            ]
            Option.objects.bulk_create(option_objs)

        # Audit log
        if changes_tracked:
            QuestionAuditLog.objects.create(
                institution=tenant,
                question=instance,
                user=request.user,
                action='UPDATE',
                changes=changes_tracked,
            )

        return instance


class BulkActionSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=['activate', 'archive', 'delete', 'change_difficulty', 'change_topic', 'change_subject'])
    ids = serializers.ListField(child=serializers.IntegerField(), min_length=1, max_length=200)
    target_value = serializers.CharField(required=False, allow_blank=True, default='')


class QuestionImportLogSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='created_by.get_full_name', read_only=True, default='')

    class Meta:
        model = QuestionImportLog
        fields = (
            'id',
            'filename',
            'file_format',
            'total_rows',
            'imported_count',
            'duplicate_count',
            'failed_count',
            'error_details',
            'user_name',
            'created_at',
        )

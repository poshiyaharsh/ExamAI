import logging

from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.db import OperationalError, ProgrammingError, transaction
from rest_framework import serializers

from admins.models import AdminInstitution
from .models import StudentProfile


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

    def validate_email(self, value):
        normalized = value.lower().strip()
        if User.objects.filter(username=normalized).exists():
            raise serializers.ValidationError('An account with this email already exists.')
        return normalized

    def create(self, validated_data):
        email = validated_data['email']
        institution = AdminInstitution.objects.filter(id=validated_data['institution_id']).first()
        if not institution:
            raise serializers.ValidationError({'institution_id': 'Please select a valid institution.'})

        try:
            with transaction.atomic():
                user = User.objects.create_user(
                    username=email,
                    email=email,
                    first_name=validated_data['first_name'].strip(),
                    last_name=validated_data['last_name'].strip(),
                    password=validated_data['password'],
                )
                StudentProfile.objects.create(user=user, institution=institution)
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

        if not user:
            raise serializers.ValidationError('Invalid email or password.')

        if not StudentProfile.objects.filter(user=user).exists():
            raise serializers.ValidationError('This account is not registered as a student.')

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

    def validate_department(self, value):
        cleaned = value.strip()
        if not cleaned:
            raise serializers.ValidationError('Department must not be empty.')
        return cleaned

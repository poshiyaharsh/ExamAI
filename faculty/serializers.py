from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.db import OperationalError, transaction
from rest_framework import serializers

from .models import FacultyProfile


class FacultySignupSerializer(serializers.Serializer):
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8)

    def validate_email(self, value):
        normalized = value.lower().strip()
        if User.objects.filter(username=normalized).exists():
            raise serializers.ValidationError('An account with this email already exists.')
        return normalized

    def create(self, validated_data):
        email = validated_data['email']
        try:
            with transaction.atomic():
                user = User.objects.create_user(
                    username=email,
                    email=email,
                    first_name=validated_data['first_name'].strip(),
                    last_name=validated_data['last_name'].strip(),
                    password=validated_data['password'],
                )
                FacultyProfile.objects.create(user=user)
                return user
        except OperationalError as exc:
            raise serializers.ValidationError(
                'Database setup is incomplete. Run migrations using: python manage.py migrate'
            ) from exc


class FacultyLoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        email = attrs['email'].lower().strip()
        password = attrs['password']
        user = authenticate(username=email, password=password)

        if not user:
            raise serializers.ValidationError('Invalid email or password.')

        if not FacultyProfile.objects.filter(user=user).exists():
            raise serializers.ValidationError('This account is not registered as faculty.')

        attrs['user'] = user
        return attrs


class FacultyProfileSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    email = serializers.EmailField(source='user.email', read_only=True)

    class Meta:
        model = FacultyProfile
        fields = ('full_name', 'email', 'employee_id', 'department')
        read_only_fields = ('full_name', 'email', 'employee_id')

    def get_full_name(self, obj):
        full_name = f'{obj.user.first_name} {obj.user.last_name}'.strip()
        return full_name or obj.user.username


class FacultyProfileDepartmentUpdateSerializer(serializers.ModelSerializer):
    department = serializers.CharField(max_length=120, allow_blank=False, trim_whitespace=True)

    class Meta:
        model = FacultyProfile
        fields = ('department',)

    def validate_department(self, value):
        cleaned = value.strip()
        if not cleaned:
            raise serializers.ValidationError('Department must not be empty.')
        return cleaned

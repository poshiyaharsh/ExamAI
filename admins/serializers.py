from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.db import OperationalError, transaction
from django.db import IntegrityError
from django.core.validators import RegexValidator
from rest_framework import serializers

from .models import AdminInstitution, AdminProfile


class AdminSignupSerializer(serializers.Serializer):
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
                AdminProfile.objects.create(user=user)
                return user
        except OperationalError as exc:
            raise serializers.ValidationError(
                'Database setup is incomplete. Run migrations using: python manage.py migrate'
            ) from exc


class AdminLoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        email = attrs['email'].lower().strip()
        password = attrs['password']
        user = authenticate(username=email, password=password)

        if not user:
            raise serializers.ValidationError('Invalid email or password.')

        if not AdminProfile.objects.filter(user=user).exists():
            raise serializers.ValidationError('This account is not registered as admin.')

        attrs['user'] = user
        return attrs


class AdminInstitutionSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source='admin.email', read_only=True)

    class Meta:
        model = AdminInstitution
        fields = ('institution_name', 'institution_code', 'address', 'phone', 'email')
        read_only_fields = ('institution_code', 'email')


phone_validator = RegexValidator(
    regex=r'^\+?[0-9()\-\s]{7,20}$',
    message='Enter a valid phone number.',
)


class AdminInstitutionCreateSerializer(serializers.ModelSerializer):
    institution_name = serializers.CharField(max_length=255, allow_blank=False, trim_whitespace=True)
    phone = serializers.CharField(max_length=20, allow_blank=True, required=False, validators=[phone_validator])

    class Meta:
        model = AdminInstitution
        fields = ('institution_name', 'address', 'phone')

    def validate_institution_name(self, value):
        cleaned = value.strip()
        if not cleaned:
            raise serializers.ValidationError('Institution Name is required.')
        return cleaned

    def create(self, validated_data):
        user = self.context['request'].user
        try:
            return AdminInstitution.objects.create(admin=user, **validated_data)
        except IntegrityError as exc:
            raise serializers.ValidationError('Institution Code already exists. Please retry.') from exc


class AdminInstitutionUpdateSerializer(serializers.ModelSerializer):
    institution_name = serializers.CharField(max_length=255, allow_blank=False, trim_whitespace=True)
    phone = serializers.CharField(max_length=20, allow_blank=True, required=False, validators=[phone_validator])

    class Meta:
        model = AdminInstitution
        fields = ('institution_name', 'address', 'phone')

    def validate_institution_name(self, value):
        cleaned = value.strip()
        if not cleaned:
            raise serializers.ValidationError('Institution Name is required.')
        return cleaned

from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.db import OperationalError, transaction
from django.db import IntegrityError
from django.core.validators import RegexValidator
from rest_framework import serializers

from .models import AdminInstitution, AdminProfile
from students.models import StudentProfile


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


class AdminStudentListSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    email = serializers.EmailField(source='user.email', read_only=True)
    roll_number = serializers.CharField(source='student_id', read_only=True)
    year = serializers.SerializerMethodField()
    number_of_exams = serializers.SerializerMethodField()
    average_score = serializers.SerializerMethodField()

    class Meta:
        model = StudentProfile
        fields = (
            'id',
            'full_name',
            'email',
            'roll_number',
            'department',
            'year',
            'number_of_exams',
            'average_score',
        )

    def get_full_name(self, obj):
        full_name = f'{obj.user.first_name} {obj.user.last_name}'.strip()
        return full_name or obj.user.username

    def get_year(self, obj):
        return ''

    def get_number_of_exams(self, obj):
        return 0

    def get_average_score(self, obj):
        return None


class AdminStudentDetailSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    first_name = serializers.CharField(source='user.first_name', read_only=True)
    last_name = serializers.CharField(source='user.last_name', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)
    roll_number = serializers.CharField(source='student_id', read_only=True)
    year = serializers.SerializerMethodField()
    number_of_exams = serializers.SerializerMethodField()
    average_score = serializers.SerializerMethodField()
    institution = serializers.SerializerMethodField()

    class Meta:
        model = StudentProfile
        fields = (
            'id',
            'full_name',
            'first_name',
            'last_name',
            'email',
            'roll_number',
            'department',
            'year',
            'number_of_exams',
            'average_score',
            'institution',
        )

    def get_full_name(self, obj):
        full_name = f'{obj.user.first_name} {obj.user.last_name}'.strip()
        return full_name or obj.user.username

    def get_year(self, obj):
        return ''

    def get_number_of_exams(self, obj):
        return 0

    def get_average_score(self, obj):
        return None

    def get_institution(self, obj):
        if not obj.institution:
            return None
        return {
            'id': obj.institution.id,
            'institution_name': obj.institution.institution_name,
            'institution_code': obj.institution.institution_code,
        }


class AdminStudentUpdateSerializer(serializers.Serializer):
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    student_id = serializers.CharField(max_length=13, required=False)
    department = serializers.CharField(max_length=120, allow_blank=False, trim_whitespace=True, required=False)

    def validate_email(self, value):
        normalized = value.lower().strip()
        profile = self.context.get('student_profile')
        if not profile:
            return normalized

        if User.objects.filter(username=normalized).exclude(id=profile.user_id).exists():
            raise serializers.ValidationError('An account with this email already exists.')
        return normalized

    def validate_student_id(self, value):
        normalized = value.strip().upper()
        if not normalized:
            raise serializers.ValidationError('Student ID is required.')

        profile = self.context.get('student_profile')
        if not profile:
            return normalized

        if StudentProfile.objects.filter(student_id=normalized).exclude(id=profile.id).exists():
            raise serializers.ValidationError('Student ID already exists.')
        return normalized

    def validate_department(self, value):
        cleaned = value.strip()
        if not cleaned:
            raise serializers.ValidationError('Department must not be empty.')
        return cleaned

    def update(self, instance, validated_data):
        user = instance.user
        user.first_name = validated_data['first_name'].strip()
        user.last_name = validated_data['last_name'].strip()
        user.email = validated_data['email']
        user.username = validated_data['email']
        user.save(update_fields=['first_name', 'last_name', 'email', 'username'])

        update_fields = []
        if 'student_id' in validated_data:
            instance.student_id = validated_data['student_id']
            update_fields.append('student_id')

        if 'department' in validated_data:
            instance.department = validated_data['department']
            update_fields.append('department')

        if update_fields:
            instance.save(update_fields=update_fields)
        return instance

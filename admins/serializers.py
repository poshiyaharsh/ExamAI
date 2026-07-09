import re
import logging

from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.db import OperationalError, ProgrammingError, transaction
from django.db import IntegrityError
from django.core.validators import RegexValidator
from django.utils import timezone
from rest_framework import serializers

from .models import AdminDepartment, AdminInstitution, AdminProfile
from students.models import StudentProfile
from faculty.models import FacultyProfile


logger = logging.getLogger(__name__)


def _validation_message(exc, fallback_message):
    message = str(exc).strip()
    if settings.DEBUG and message:
        return message
    return fallback_message


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
        except (OperationalError, ProgrammingError) as exc:
            raise serializers.ValidationError(
                _validation_message(exc, 'Database schema issue detected. Please run migrations.')
            ) from exc
        except Exception as exc:
            logger.exception('Unexpected admin signup error')
            raise serializers.ValidationError(
                _validation_message(exc, 'Unable to create admin account.')
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
        fields = ('id', 'institution_name', 'institution_code', 'address', 'phone', 'email')
        read_only_fields = ('id', 'institution_code', 'email')


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
        student_id = getattr(obj, 'student_id', '') or ''
        parts = student_id.split('-')
        if len(parts) >= 3 and parts[1].isdigit():
            return parts[1]
        created_at = getattr(obj, 'created_at', None)
        if created_at:
            return timezone.localtime(created_at).strftime('%Y')
        return ''

    def get_number_of_exams(self, obj):
        return int(getattr(obj, 'number_of_exams', 0) or 0)

    def get_average_score(self, obj):
        average_score = getattr(obj, 'average_score', None)
        return average_score if isinstance(average_score, (int, float)) else None


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
        student_id = getattr(obj, 'student_id', '') or ''
        parts = student_id.split('-')
        if len(parts) >= 3 and parts[1].isdigit():
            return parts[1]
        created_at = getattr(obj, 'created_at', None)
        if created_at:
            return timezone.localtime(created_at).strftime('%Y')
        return ''

    def get_number_of_exams(self, obj):
        return int(getattr(obj, 'number_of_exams', 0) or 0)

    def get_average_score(self, obj):
        average_score = getattr(obj, 'average_score', None)
        return average_score if isinstance(average_score, (int, float)) else None

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
    department_id = serializers.IntegerField(required=False)

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

    def validate_department_id(self, value):
        profile = self.context.get('student_profile')
        if not profile or not profile.institution:
            raise serializers.ValidationError('Student institution not found.')

        department = AdminDepartment.objects.filter(id=value, institution=profile.institution).first()
        if not department:
            raise serializers.ValidationError('Please select a valid department.')

        self.context['department'] = department
        return value

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

        department = self.context.get('department')
        if department:
            instance.department = department.department_name
            update_fields.append('department')
        elif 'department' in validated_data:
            instance.department = validated_data['department']
            update_fields.append('department')

        if 'department' in validated_data:
            # handled above
            pass

        if update_fields:
            instance.save(update_fields=update_fields)
        return instance


class AdminStudentCreateSerializer(serializers.Serializer):
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8)
    department_id = serializers.IntegerField(write_only=True)

    def validate_email(self, value):
        normalized = value.lower().strip()
        if User.objects.filter(username=normalized).exists():
            raise serializers.ValidationError('An account with this email already exists.')
        return normalized

    def validate_password(self, value):
        if len(value) < 8:
            raise serializers.ValidationError('Password must be at least 8 characters long.')

        has_letter = re.search(r'[A-Za-z]', value) is not None
        has_number = re.search(r'\d', value) is not None
        if not has_letter or not has_number:
            raise serializers.ValidationError('Password must include at least one letter and one number.')

        return value

    def validate_department_id(self, value):
        institution = self.context.get('institution')
        if not institution:
            raise serializers.ValidationError('Admin institution not found.')

        department = AdminDepartment.objects.filter(id=value, institution=institution).first()
        if not department:
            raise serializers.ValidationError('Please select a valid department.')

        self.context['department'] = department
        return value

    def create(self, validated_data):
        institution = self.context.get('institution')
        if not institution:
            raise serializers.ValidationError({'institution_id': 'Admin institution not found.'})

        department = self.context.get('department')
        if not department:
            raise serializers.ValidationError({'department_id': 'Please select a valid department.'})

        with transaction.atomic():
            user = User.objects.create_user(
                username=validated_data['email'],
                email=validated_data['email'],
                first_name=validated_data['first_name'].strip(),
                last_name=validated_data['last_name'].strip(),
                password=validated_data['password'],
            )
            profile = StudentProfile.objects.create(
                user=user,
                institution=institution,
                department=department.department_name,
            )
            profile.ensure_student_id()
            return profile


class AdminFacultyCreateSerializer(serializers.Serializer):
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    employee_id = serializers.CharField(max_length=12, required=False, allow_blank=True)
    department_id = serializers.IntegerField(write_only=True)
    designation = serializers.CharField(max_length=120, allow_blank=True, required=False)
    is_active = serializers.BooleanField(required=False, default=True)
    password = serializers.CharField(write_only=True, min_length=8)

    def validate_email(self, value):
        normalized = value.lower().strip()
        if User.objects.filter(username=normalized).exists():
            raise serializers.ValidationError('An account with this email already exists.')
        return normalized

    def validate_employee_id(self, value):
        cleaned = value.strip().upper()
        if not cleaned:
            return ''

        if FacultyProfile.objects.filter(employee_id=cleaned).exists():
            raise serializers.ValidationError('Employee ID already exists.')
        return cleaned

    def validate_password(self, value):
        if len(value) < 8:
            raise serializers.ValidationError('Password must be at least 8 characters long.')

        has_letter = re.search(r'[A-Za-z]', value) is not None
        has_number = re.search(r'\d', value) is not None
        if not has_letter or not has_number:
            raise serializers.ValidationError('Password must include at least one letter and one number.')

        return value

    def validate_department_id(self, value):
        institution = self.context.get('institution')
        if not institution:
            raise serializers.ValidationError('Admin institution not found.')

        department = AdminDepartment.objects.filter(id=value, institution=institution).first()
        if not department:
            raise serializers.ValidationError('Please select a valid department.')

        self.context['department'] = department
        return value

    def create(self, validated_data):
        institution = self.context.get('institution')
        if not institution:
            raise serializers.ValidationError({'institution_id': 'Admin institution not found.'})

        department = self.context.get('department')
        if not department:
            raise serializers.ValidationError({'department_id': 'Please select a valid department.'})

        with transaction.atomic():
            user = User.objects.create_user(
                username=validated_data['email'],
                email=validated_data['email'],
                first_name=validated_data['first_name'].strip(),
                last_name=validated_data['last_name'].strip(),
                password=validated_data['password'],
                is_active=validated_data.get('is_active', True),
            )
            profile = FacultyProfile.objects.create(
                user=user,
                institution=institution,
                employee_id=validated_data.get('employee_id', '').strip() or None,
                department=department.department_name,
                designation=validated_data.get('designation', '').strip(),
            )
            if not profile.employee_id:
                profile.ensure_employee_id()
            return profile


class AdminFacultyListSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    email = serializers.EmailField(source='user.email', read_only=True)
    employee_id = serializers.CharField(read_only=True)
    designation = serializers.CharField(read_only=True)
    is_active = serializers.BooleanField(source='user.is_active', read_only=True)
    status = serializers.SerializerMethodField()
    institution_id = serializers.IntegerField(read_only=True)
    institute_id = serializers.IntegerField(source='institution_id', read_only=True)

    class Meta:
        model = FacultyProfile
        fields = (
            'id',
            'full_name',
            'email',
            'employee_id',
            'department',
            'designation',
            'is_active',
            'status',
            'institution_id',
            'institute_id',
        )

    def get_full_name(self, obj):
        full_name = f'{obj.user.first_name} {obj.user.last_name}'.strip()
        return full_name or obj.user.username

    def get_status(self, obj):
        return 'Active' if obj.user.is_active else 'Inactive'


class AdminFacultyDetailSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    first_name = serializers.CharField(source='user.first_name', read_only=True)
    last_name = serializers.CharField(source='user.last_name', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)
    employee_id = serializers.CharField(read_only=True)
    designation = serializers.CharField(read_only=True)
    is_active = serializers.BooleanField(source='user.is_active', read_only=True)
    status = serializers.SerializerMethodField()
    institution = serializers.SerializerMethodField()
    institution_id = serializers.IntegerField(read_only=True)
    institute_id = serializers.IntegerField(source='institution_id', read_only=True)

    class Meta:
        model = FacultyProfile
        fields = (
            'id',
            'full_name',
            'first_name',
            'last_name',
            'email',
            'employee_id',
            'department',
            'designation',
            'is_active',
            'status',
            'institution',
            'institution_id',
            'institute_id',
        )

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

    def get_status(self, obj):
        return 'Active' if obj.user.is_active else 'Inactive'


class AdminFacultyUpdateSerializer(serializers.Serializer):
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    employee_id = serializers.CharField(allow_blank=True, required=False)
    department = serializers.CharField(max_length=120, allow_blank=True, required=False)
    designation = serializers.CharField(max_length=120, allow_blank=True, required=False)
    is_active = serializers.BooleanField(required=False)

    def validate_email(self, value):
        normalized = value.lower().strip()
        faculty = self.context.get('faculty')
        if faculty and User.objects.filter(username=normalized).exclude(id=faculty.user.id).exists():
            raise serializers.ValidationError('An account with this email already exists.')
        return normalized

    def validate_employee_id(self, value):
        cleaned = value.strip()
        if not cleaned:
            return ''

        faculty = self.context.get('faculty')
        if faculty and FacultyProfile.objects.filter(employee_id=cleaned).exclude(id=faculty.id).exists():
            raise serializers.ValidationError('Employee ID already exists.')
        return cleaned

    def update(self, instance, validated_data):
        user = instance.user
        user.first_name = validated_data['first_name'].strip()
        user.last_name = validated_data['last_name'].strip()
        user.email = validated_data['email']
        user.username = validated_data['email']

        if 'is_active' in validated_data:
            user.is_active = validated_data['is_active']

        user.save(update_fields=['first_name', 'last_name', 'email', 'username', 'is_active'])

        if 'employee_id' in validated_data:
            instance.employee_id = validated_data['employee_id'] or None

        if 'department' in validated_data:
            instance.department = validated_data['department'].strip()

        if 'designation' in validated_data:
            instance.designation = validated_data['designation'].strip()

        instance.save(update_fields=['employee_id', 'department', 'designation'])
        instance.refresh_from_db()
        return instance

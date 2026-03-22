from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone


class AdminProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='admin_profile')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Admin: {self.user.username}'


class AdminInstitution(models.Model):
    admin = models.OneToOneField(User, on_delete=models.CASCADE, related_name='admin_institution')
    institution_name = models.CharField(max_length=255)
    institution_code = models.CharField(max_length=13, unique=True, editable=False)
    address = models.CharField(max_length=500, blank=True, default='')
    phone = models.CharField(max_length=20, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @staticmethod
    def build_next_institution_code():
        year = timezone.now().year
        prefix = f'INST-{year}-'
        latest_code = (
            AdminInstitution.objects.filter(institution_code__startswith=prefix)
            .order_by('-institution_code')
            .values_list('institution_code', flat=True)
            .first()
        )

        if latest_code:
            try:
                next_counter = int(latest_code.split('-')[-1]) + 1
            except (TypeError, ValueError):
                next_counter = 1
        else:
            next_counter = 1

        return f'{prefix}{next_counter:03d}'

    @classmethod
    def generate_unique_institution_code(cls):
        for _ in range(10):
            candidate = cls.build_next_institution_code()
            if not cls.objects.filter(institution_code=candidate).exists():
                return candidate
        raise ValueError('Unable to generate unique institution code. Please try again.')

    def save(self, *args, **kwargs):
        if not self.institution_code:
            self.institution_code = self.generate_unique_institution_code()
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.institution_name} ({self.institution_code})'

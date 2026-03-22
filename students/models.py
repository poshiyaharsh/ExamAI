from django.contrib.auth.models import User
from django.db import models


class StudentProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='student_profile')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Student: {self.user.username}'

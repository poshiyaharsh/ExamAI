from django.contrib.auth.models import User
from django.db import models


class FacultyProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='faculty_profile')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Faculty: {self.user.username}'

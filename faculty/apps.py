from django.apps import AppConfig


class FacultyConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'faculty'

    def ready(self):
        from backend.ai_config import get_ai_provider_manager

        get_ai_provider_manager()

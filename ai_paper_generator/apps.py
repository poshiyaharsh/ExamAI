from django.apps import AppConfig


class AiPaperGeneratorConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'ai_paper_generator'
    verbose_name = 'AI Examination Paper Generator'

    def ready(self):
        # Initialize logging handlers on app startup
        try:
            from .logging_setup import setup_generation_loggers
            setup_generation_loggers()
        except Exception:
            pass

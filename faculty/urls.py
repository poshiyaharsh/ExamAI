from django.urls import path

from .views import (
    FacultyLoginAPIView,
    FacultyProfileAPIView,
    FacultySignupAPIView,
    GeneratePaperAPIView,
    OllamaStatusAPIView,
    PaperDetailAPIView,
    PaperExportAPIView,
    PaperHistoryAPIView,
    SyllabusUploadAPIView,
)

urlpatterns = [
    path('signup/', FacultySignupAPIView.as_view(), name='faculty-signup'),
    path('login/', FacultyLoginAPIView.as_view(), name='faculty-login'),
    path('profile', FacultyProfileAPIView.as_view(), name='faculty-profile-no-slash'),
    path('profile/', FacultyProfileAPIView.as_view(), name='faculty-profile'),
    path('upload-syllabus', SyllabusUploadAPIView.as_view(), name='faculty-upload-syllabus-no-slash'),
    path('upload-syllabus/', SyllabusUploadAPIView.as_view(), name='faculty-upload-syllabus'),
    path('generate-paper', GeneratePaperAPIView.as_view(), name='faculty-generate-paper-no-slash'),
    path('generate-paper/', GeneratePaperAPIView.as_view(), name='faculty-generate-paper'),
    path('ollama-status', OllamaStatusAPIView.as_view(), name='faculty-ollama-status-no-slash'),
    path('ollama-status/', OllamaStatusAPIView.as_view(), name='faculty-ollama-status'),
    path('paper-history', PaperHistoryAPIView.as_view(), name='faculty-paper-history-no-slash'),
    path('paper-history/', PaperHistoryAPIView.as_view(), name='faculty-paper-history'),
    path('paper/<int:paper_id>', PaperDetailAPIView.as_view(), name='faculty-paper-detail-no-slash'),
    path('paper/<int:paper_id>/', PaperDetailAPIView.as_view(), name='faculty-paper-detail'),
    path('paper/<int:paper_id>/export', PaperExportAPIView.as_view(), name='faculty-paper-export-no-slash'),
    path('paper/<int:paper_id>/export/', PaperExportAPIView.as_view(), name='faculty-paper-export'),
]

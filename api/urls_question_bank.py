"""URL patterns for Question Bank."""

from django.urls import path

from api.views_question_bank import (
    QuestionBulkActionAPIView,
    QuestionBulkImportAPIView,
    QuestionDetailAPIView,
    QuestionDuplicateAPIView,
    QuestionExportAPIView,
    QuestionImportTemplateAPIView,
    QuestionListCreateAPIView,
    QuestionRestoreAPIView,
    QuestionStatsAPIView,
    SubjectDetailAPIView,
    SubjectListCreateAPIView,
    TopicDetailAPIView,
    TopicListCreateAPIView,
)

urlpatterns = [
    # Questions
    path('questions', QuestionListCreateAPIView.as_view(), name='qb-questions-list-no-slash'),
    path('questions/', QuestionListCreateAPIView.as_view(), name='qb-questions-list'),
    path('questions/<int:pk>', QuestionDetailAPIView.as_view(), name='qb-question-detail-no-slash'),
    path('questions/<int:pk>/', QuestionDetailAPIView.as_view(), name='qb-question-detail'),
    path('questions/<int:pk>/restore', QuestionRestoreAPIView.as_view(), name='qb-question-restore-no-slash'),
    path('questions/<int:pk>/restore/', QuestionRestoreAPIView.as_view(), name='qb-question-restore'),
    path('questions/<int:pk>/duplicate', QuestionDuplicateAPIView.as_view(), name='qb-question-duplicate-no-slash'),
    path('questions/<int:pk>/duplicate/', QuestionDuplicateAPIView.as_view(), name='qb-question-duplicate'),
    path('questions/bulk-action', QuestionBulkActionAPIView.as_view(), name='qb-bulk-action-no-slash'),
    path('questions/bulk-action/', QuestionBulkActionAPIView.as_view(), name='qb-bulk-action'),
    path('questions/bulk-import', QuestionBulkImportAPIView.as_view(), name='qb-bulk-import-no-slash'),
    path('questions/bulk-import/', QuestionBulkImportAPIView.as_view(), name='qb-bulk-import'),
    path('questions/export', QuestionExportAPIView.as_view(), name='qb-export-no-slash'),
    path('questions/export/', QuestionExportAPIView.as_view(), name='qb-export'),
    path('questions/template', QuestionImportTemplateAPIView.as_view(), name='qb-template-no-slash'),
    path('questions/template/', QuestionImportTemplateAPIView.as_view(), name='qb-template'),

    # Subjects & Topics
    path('subjects', SubjectListCreateAPIView.as_view(), name='qb-subjects-list-no-slash'),
    path('subjects/', SubjectListCreateAPIView.as_view(), name='qb-subjects-list'),
    path('subjects/<int:pk>', SubjectDetailAPIView.as_view(), name='qb-subject-detail-no-slash'),
    path('subjects/<int:pk>/', SubjectDetailAPIView.as_view(), name='qb-subject-detail'),
    path('topics', TopicListCreateAPIView.as_view(), name='qb-topics-list-no-slash'),
    path('topics/', TopicListCreateAPIView.as_view(), name='qb-topics-list'),
    path('topics/<int:pk>', TopicDetailAPIView.as_view(), name='qb-topic-detail-no-slash'),
    path('topics/<int:pk>/', TopicDetailAPIView.as_view(), name='qb-topic-detail'),

    # Stats
    path('stats', QuestionStatsAPIView.as_view(), name='qb-stats-no-slash'),
    path('stats/', QuestionStatsAPIView.as_view(), name='qb-stats'),
]

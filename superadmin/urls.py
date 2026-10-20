from django.urls import path
from superadmin.views import (
    SuperAdmin2FAEnrollAPIView,
    SuperAdminAuditLogAPIView,
    SuperAdminBackupAPIView,
    SuperAdminCleanupReportAPIView,
    SuperAdminDashboardAPIView,
    SuperAdminExamForceCloseAPIView,
    SuperAdminExamListAPIView,
    SuperAdminInstituteDetailAPIView,
    SuperAdminInstituteListCreateAPIView,
    SuperAdminInstituteToggleStatusAPIView,
    SuperAdminLoginAPIView,
    SuperAdminLogoutAPIView,
    SuperAdminMeAPIView,
    SuperAdminReauthAPIView,
    SuperAdminSystemSettingsAPIView,
    SuperAdminUserListAPIView,
    SuperAdminUserResetPasswordAPIView,
    SuperAdminUserTransferAPIView,
)

urlpatterns = [
    # Authentication & 2FA
    path('auth/login/', SuperAdminLoginAPIView.as_view(), name='sa-login'),
    path('auth/2fa/enroll/', SuperAdmin2FAEnrollAPIView.as_view(), name='sa-2fa-enroll'),
    path('auth/reauth/', SuperAdminReauthAPIView.as_view(), name='sa-reauth'),
    path('auth/logout/', SuperAdminLogoutAPIView.as_view(), name='sa-logout'),
    path('auth/me/', SuperAdminMeAPIView.as_view(), name='sa-me'),

    # Dashboard & Health
    path('dashboard/', SuperAdminDashboardAPIView.as_view(), name='sa-dashboard'),

    # Institutes Management
    path('institutes/', SuperAdminInstituteListCreateAPIView.as_view(), name='sa-institutes-list-create'),
    path('institutes/<int:institute_id>/', SuperAdminInstituteDetailAPIView.as_view(), name='sa-institute-detail'),
    path('institutes/<int:institute_id>/status/', SuperAdminInstituteToggleStatusAPIView.as_view(), name='sa-institute-toggle-status'),

    # Global Users Management
    path('users/', SuperAdminUserListAPIView.as_view(), name='sa-users-list'),
    path('users/<int:user_id>/reset-password/', SuperAdminUserResetPasswordAPIView.as_view(), name='sa-user-reset-password'),
    path('users/<int:user_id>/transfer/', SuperAdminUserTransferAPIView.as_view(), name='sa-user-transfer'),

    # Global Exams Overview
    path('exams/', SuperAdminExamListAPIView.as_view(), name='sa-exams-list'),
    path('exams/<int:exam_id>/force-close/', SuperAdminExamForceCloseAPIView.as_view(), name='sa-exam-force-close'),

    # System Settings & Security
    path('system/settings/', SuperAdminSystemSettingsAPIView.as_view(), name='sa-system-settings'),
    path('system/audit-logs/', SuperAdminAuditLogAPIView.as_view(), name='sa-audit-logs'),

    # Data Tools & Backups
    path('data/backups/', SuperAdminBackupAPIView.as_view(), name='sa-backups'),
    path('data/cleanup/', SuperAdminCleanupReportAPIView.as_view(), name='sa-cleanup'),
]

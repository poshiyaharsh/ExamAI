from django.urls import path
from superadmin.views import (
    SuperAdmin2FAEnrollAPIView,
    SuperAdminAIModelDeleteAPIView,
    SuperAdminAIModelSetDefaultAPIView,
    SuperAdminAIModelTestAPIView,
    SuperAdminAIModelToggleAPIView,
    SuperAdminAIModelsAPIView,
    SuperAdminAnnouncementsAPIView,
    SuperAdminAuditLogAPIView,
    SuperAdminBackupAPIView,
    SuperAdminBackupLiveRestoreAPIView,
    SuperAdminBackupTestRestoreAPIView,
    SuperAdminBulkImportAPIView,
    SuperAdminBulkImportTemplateAPIView,
    SuperAdminCleanupReportAPIView,
    SuperAdminCrossInstituteAnalyticsAPIView,
    SuperAdminDashboardAPIView,
    SuperAdminDPDPAnonymizeAPIView,
    SuperAdminDPDPDataExportAPIView,
    SuperAdminDPDPDataInventoryAPIView,
    SuperAdminErrorSummaryAPIView,
    SuperAdminExamExportAPIView,
    SuperAdminExamFilterMetadataAPIView,
    SuperAdminExamForceCloseAPIView,
    SuperAdminExamListAPIView,
    SuperAdminExportsAPIView,
    SuperAdminImpersonateAPIView,
    SuperAdminInstituteDetailAPIView,
    SuperAdminInstituteListCreateAPIView,
    SuperAdminInstituteLogoAPIView,
    SuperAdminInstitutePolicyAPIView,
    SuperAdminInstituteToggleStatusAPIView,
    SuperAdminJobActionAPIView,
    SuperAdminJobCenterAPIView,
    SuperAdminLoginAPIView,
    SuperAdminLogoutAPIView,
    SuperAdminLogsAPIView,
    SuperAdminMaintenanceWindowAPIView,
    SuperAdminMeAPIView,
    SuperAdminMonitoringHealthAPIView,
    SuperAdminNotificationAudiencePreviewAPIView,
    SuperAdminNotificationCampaignCancelAPIView,
    SuperAdminNotificationCampaignListCreateAPIView,
    SuperAdminEmailStatusAPIView,
    SuperAdminSendTestEmailAPIView,
    SuperAdminPermissionsMatrixAPIView,
    SuperAdminReauthAPIView,
    SuperAdminStuckJobDetectorAPIView,
    SuperAdminSystemSettingsAPIView,
    SuperAdminEmergencyRevokeSessionsAPIView,
    SuperAdminGlobalSearchAPIView,
    SuperAdminReportCatalogAPIView,
    SuperAdminReportDataAPIView,
    SuperAdminReportDownloadAPIView,
    SuperAdminReportExportAPIView,
    SuperAdminUserBulkActionAPIView,
    SuperAdminUserCreateAPIView,
    SuperAdminUserDetailDrawerAPIView,
    SuperAdminUserListAPIView,
    SuperAdminUserResetPasswordAPIView,
    SuperAdminUserRevokeSessionsAPIView,
    SuperAdminUserToggleActiveAPIView,
    SuperAdminUserTransferAPIView,
    SuperAdminUserUpdateProfileAPIView,
)

urlpatterns = [
    # Authentication & 2FA
    path('auth/login/', SuperAdminLoginAPIView.as_view(), name='sa-login'),
    path('auth/2fa/enroll/', SuperAdmin2FAEnrollAPIView.as_view(), name='sa-2fa-enroll'),
    path('auth/reauth/', SuperAdminReauthAPIView.as_view(), name='sa-reauth'),
    path('auth/logout/', SuperAdminLogoutAPIView.as_view(), name='sa-logout'),
    path('auth/me/', SuperAdminMeAPIView.as_view(), name='sa-me'),

    # Dashboard & Platform Health
    path('dashboard/', SuperAdminDashboardAPIView.as_view(), name='sa-dashboard'),
    path('monitoring/health/', SuperAdminMonitoringHealthAPIView.as_view(), name='sa-monitoring-health'),
    path('monitoring/logs/', SuperAdminLogsAPIView.as_view(), name='sa-monitoring-logs'),
    path('monitoring/error-summary/', SuperAdminErrorSummaryAPIView.as_view(), name='sa-monitoring-error-summary'),

    # Job Center & Background Tasks
    path('jobs/', SuperAdminJobCenterAPIView.as_view(), name='sa-jobs-center'),
    path('jobs/<int:job_id>/<str:action>/', SuperAdminJobActionAPIView.as_view(), name='sa-job-action'),
    path('jobs/stuck-detector/', SuperAdminStuckJobDetectorAPIView.as_view(), name='sa-jobs-stuck-detector'),

    # Institutes Management & Controls
    path('institutes/', SuperAdminInstituteListCreateAPIView.as_view(), name='sa-institutes-list-create'),
    path('institutes/bulk-import/template/', SuperAdminBulkImportTemplateAPIView.as_view(), name='sa-bulk-import-template'),
    path('institutes/<int:institute_id>/', SuperAdminInstituteDetailAPIView.as_view(), name='sa-institute-detail'),
    path('institutes/<int:institute_id>/status/', SuperAdminInstituteToggleStatusAPIView.as_view(), name='sa-institute-toggle-status'),
    path('institutes/<int:institute_id>/policy/', SuperAdminInstitutePolicyAPIView.as_view(), name='sa-institute-policy'),
    path('institutes/<int:institute_id>/logo/', SuperAdminInstituteLogoAPIView.as_view(), name='sa-institute-logo'),
    path('institutes/<int:institute_id>/bulk-import/', SuperAdminBulkImportAPIView.as_view(), name='sa-institute-bulk-import'),

    # Announcements System
    path('announcements/', SuperAdminAnnouncementsAPIView.as_view(), name='sa-announcements'),

    # Roles & Permission Review Matrix
    path('permissions/matrix/', SuperAdminPermissionsMatrixAPIView.as_view(), name='sa-permissions-matrix'),

    # Global Users Management & Impersonation
    path('users/', SuperAdminUserListAPIView.as_view(), name='sa-users-list'),
    path('users/create/', SuperAdminUserCreateAPIView.as_view(), name='sa-user-create'),
    path('users/bulk-action/', SuperAdminUserBulkActionAPIView.as_view(), name='sa-user-bulk-action'),
    path('users/<int:user_id>/drawer/', SuperAdminUserDetailDrawerAPIView.as_view(), name='sa-user-drawer'),
    path('users/<int:user_id>/update-profile/', SuperAdminUserUpdateProfileAPIView.as_view(), name='sa-user-update-profile'),
    path('users/<int:user_id>/toggle-active/', SuperAdminUserToggleActiveAPIView.as_view(), name='sa-user-toggle-active'),
    path('users/<int:user_id>/revoke-sessions/', SuperAdminUserRevokeSessionsAPIView.as_view(), name='sa-user-revoke-sessions'),
    path('users/<int:user_id>/reset-password/', SuperAdminUserResetPasswordAPIView.as_view(), name='sa-user-reset-password'),
    path('users/<int:user_id>/transfer/', SuperAdminUserTransferAPIView.as_view(), name='sa-user-transfer'),
    path('users/<int:user_id>/impersonate/', SuperAdminImpersonateAPIView.as_view(), name='sa-user-impersonate'),

    # Global Exams Overview
    path('exams/', SuperAdminExamListAPIView.as_view(), name='sa-exams-list'),
    path('exams/metadata/', SuperAdminExamFilterMetadataAPIView.as_view(), name='sa-exams-filter-metadata'),
    path('exams/export/', SuperAdminExamExportAPIView.as_view(), name='sa-exams-export'),
    path('exams/<int:exam_id>/force-close/', SuperAdminExamForceCloseAPIView.as_view(), name='sa-exam-force-close'),

    # Module B: AI Models & Ollama Management
    path('ai/models/', SuperAdminAIModelsAPIView.as_view(), name='sa-ai-models'),
    path('ai/models/<int:model_id>/toggle/', SuperAdminAIModelToggleAPIView.as_view(), name='sa-ai-model-toggle'),
    path('ai/models/<int:model_id>/default/', SuperAdminAIModelSetDefaultAPIView.as_view(), name='sa-ai-model-default'),
    path('ai/models/<int:model_id>/delete/', SuperAdminAIModelDeleteAPIView.as_view(), name='sa-ai-model-delete'),
    path('ai/models/<int:model_id>/test/', SuperAdminAIModelTestAPIView.as_view(), name='sa-ai-model-test'),

    # Module C: Notifications Engine & Delivery Tracking
    path('notifications/campaigns/', SuperAdminNotificationCampaignListCreateAPIView.as_view(), name='sa-campaigns'),
    path('notifications/campaigns/<int:campaign_id>/cancel/', SuperAdminNotificationCampaignCancelAPIView.as_view(), name='sa-campaign-cancel'),
    path('notifications/audience-preview/', SuperAdminNotificationAudiencePreviewAPIView.as_view(), name='sa-audience-preview'),
    path('notifications/email-status/', SuperAdminEmailStatusAPIView.as_view(), name='sa-email-status'),
    path('notifications/send-test-email/', SuperAdminSendTestEmailAPIView.as_view(), name='sa-send-test-email'),

    # System Settings & Security
    path('system/settings/', SuperAdminSystemSettingsAPIView.as_view(), name='sa-system-settings'),
    path('system/audit-logs/', SuperAdminAuditLogAPIView.as_view(), name='sa-audit-logs'),
    path('operations/maintenance/', SuperAdminMaintenanceWindowAPIView.as_view(), name='sa-maintenance-window'),

    # Reports & Cross-Institute Analytics
    path('analytics/cross-institute/', SuperAdminCrossInstituteAnalyticsAPIView.as_view(), name='sa-analytics-cross-institute'),

    # Data Tools, Exports & Backups
    path('data/exports/', SuperAdminExportsAPIView.as_view(), name='sa-exports'),
    path('data/backups/', SuperAdminBackupAPIView.as_view(), name='sa-backups'),
    path('data/backups/<int:backup_id>/test-restore/', SuperAdminBackupTestRestoreAPIView.as_view(), name='sa-backup-test-restore'),
    path('data/backups/<int:backup_id>/restore/', SuperAdminBackupLiveRestoreAPIView.as_view(), name='sa-backup-live-restore'),
    path('data/cleanup/', SuperAdminCleanupReportAPIView.as_view(), name='sa-cleanup'),

    # Data Privacy (DPDP Act Compliance Tooling)
    path('privacy/dpdp/inventory/', SuperAdminDPDPDataInventoryAPIView.as_view(), name='sa-dpdp-inventory'),
    path('privacy/dpdp/export/<int:user_id>/', SuperAdminDPDPDataExportAPIView.as_view(), name='sa-dpdp-export'),
    path('privacy/dpdp/anonymize/<int:user_id>/', SuperAdminDPDPAnonymizeAPIView.as_view(), name='sa-dpdp-anonymize'),

    # Module D & E: Reports Catalog, Data, Exports & Emergency Tools
    path('reports/', SuperAdminReportCatalogAPIView.as_view(), name='sa-reports-catalog'),
    path('reports/<str:report_id>/', SuperAdminReportDataAPIView.as_view(), name='sa-report-data'),
    path('reports/<str:report_id>/export/', SuperAdminReportExportAPIView.as_view(), name='sa-report-export'),
    path('reports/download/<str:token>/', SuperAdminReportDownloadAPIView.as_view(), name='sa-report-download'),
    path('operations/emergency-revoke-sessions/', SuperAdminEmergencyRevokeSessionsAPIView.as_view(), name='sa-emergency-revoke-sessions'),
    path('system/quick-search/', SuperAdminGlobalSearchAPIView.as_view(), name='sa-global-quick-search'),
]

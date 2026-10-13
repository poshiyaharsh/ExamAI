from django.urls import include, path

from .views import (
    AdminInstitutionAPIView,
    AdminLoginAPIView,
    AdminStudentDetailAPIView,
    AdminStudentsAPIView,
    AdminSignupAPIView,
    AdminFacultyAPIView,
    AdminFacultyDetailAPIView,
    AdminExamsAPIView,
    AdminExamDetailAPIView,
    AdminExamAuditAPIView,
    AdminStudentResultsAPIView,
)
from api.admin_dashboard import AdminDashboardView, LiveRosterView

urlpatterns = [
    path('signup/', AdminSignupAPIView.as_view(), name='admin-signup'),
    path('login/', AdminLoginAPIView.as_view(), name='admin-login'),
    path('dashboard', AdminDashboardView.as_view(), name='admin-dashboard-no-slash'),
    path('dashboard/', AdminDashboardView.as_view(), name='admin-dashboard'),
    path('institution', AdminInstitutionAPIView.as_view(), name='admin-institution-no-slash'),
    path('institution/', AdminInstitutionAPIView.as_view(), name='admin-institution'),
    path('students', AdminStudentsAPIView.as_view(), name='admin-students-no-slash'),
    path('students/', AdminStudentsAPIView.as_view(), name='admin-students'),
    path('students/<int:student_id>', AdminStudentDetailAPIView.as_view(), name='admin-student-detail-no-slash'),
    path('students/<int:student_id>/', AdminStudentDetailAPIView.as_view(), name='admin-student-detail'),
    path('students/<int:student_id>/results', AdminStudentResultsAPIView.as_view(), name='admin-student-results-no-slash'),
    path('students/<int:student_id>/results/', AdminStudentResultsAPIView.as_view(), name='admin-student-results'),
    path('faculty', AdminFacultyAPIView.as_view(), name='admin-faculty-no-slash'),
    path('faculty/', AdminFacultyAPIView.as_view(), name='admin-faculty'),
    path('faculty/<int:faculty_id>', AdminFacultyDetailAPIView.as_view(), name='admin-faculty-detail-no-slash'),
    path('faculty/<int:faculty_id>/', AdminFacultyDetailAPIView.as_view(), name='admin-faculty-detail'),
    path('exams', AdminExamsAPIView.as_view(), name='admin-exams-no-slash'),
    path('exams/', AdminExamsAPIView.as_view(), name='admin-exams'),
    path('exams/audit', AdminExamAuditAPIView.as_view(), name='admin-exams-audit-no-slash'),
    path('exams/audit/', AdminExamAuditAPIView.as_view(), name='admin-exams-audit'),
    path('exams/<int:exam_id>', AdminExamDetailAPIView.as_view(), name='admin-exam-detail-no-slash'),
    path('exams/<int:exam_id>/', AdminExamDetailAPIView.as_view(), name='admin-exam-detail'),
    path('exams/<int:exam_id>/live-roster', LiveRosterView.as_view(), name='admin-exam-live-roster-no-slash'),
    path('exams/<int:exam_id>/live-roster/', LiveRosterView.as_view(), name='admin-exam-live-roster'),
    path('question-bank/', include('api.urls_question_bank')),
]

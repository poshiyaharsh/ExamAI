from django.urls import path

from .views import (
    AdminInstitutionAPIView,
    AdminLoginAPIView,
    AdminStudentDetailAPIView,
    AdminStudentsAPIView,
    AdminSignupAPIView,
    AdminFacultyAPIView,
    AdminFacultyDetailAPIView,
)

urlpatterns = [
    path('signup/', AdminSignupAPIView.as_view(), name='admin-signup'),
    path('login/', AdminLoginAPIView.as_view(), name='admin-login'),
    path('institution', AdminInstitutionAPIView.as_view(), name='admin-institution-no-slash'),
    path('institution/', AdminInstitutionAPIView.as_view(), name='admin-institution'),
    path('students', AdminStudentsAPIView.as_view(), name='admin-students-no-slash'),
    path('students/', AdminStudentsAPIView.as_view(), name='admin-students'),
    path('students/<int:student_id>', AdminStudentDetailAPIView.as_view(), name='admin-student-detail-no-slash'),
    path('students/<int:student_id>/', AdminStudentDetailAPIView.as_view(), name='admin-student-detail'),
    path('faculty', AdminFacultyAPIView.as_view(), name='admin-faculty-no-slash'),
    path('faculty/', AdminFacultyAPIView.as_view(), name='admin-faculty'),
    path('faculty/<int:faculty_id>', AdminFacultyDetailAPIView.as_view(), name='admin-faculty-detail-no-slash'),
    path('faculty/<int:faculty_id>/', AdminFacultyDetailAPIView.as_view(), name='admin-faculty-detail'),
]

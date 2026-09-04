from django.urls import path

from .views import StudentExamDetailAPIView, StudentExamListAPIView, StudentExamStartAPIView, StudentExamSubmitAPIView, StudentLoginAPIView, StudentProfileAPIView, StudentSignupAPIView

urlpatterns = [
    path('signup/', StudentSignupAPIView.as_view(), name='student-signup'),
    path('login/', StudentLoginAPIView.as_view(), name='student-login'),
    path('profile', StudentProfileAPIView.as_view(), name='student-profile-no-slash'),
    path('profile/', StudentProfileAPIView.as_view(), name='student-profile'),
    path('exams/', StudentExamListAPIView.as_view(), name='student-exams'),
    path('exams/<int:paper_id>/', StudentExamDetailAPIView.as_view(), name='student-exam-detail'),
    path('exams/<int:paper_id>/start/', StudentExamStartAPIView.as_view(), name='student-exam-start'),
    path('exams/<int:paper_id>/submit/', StudentExamSubmitAPIView.as_view(), name='student-exam-submit'),
]

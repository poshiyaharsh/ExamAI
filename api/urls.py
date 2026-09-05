from django.urls import path

from .exam_management import ExamDetailView, ExamListView, PublishExamView, QuestionUpdateView
from .generate_paper import GeneratePaperView
from .student_exam import (
    SaveAnswerView,
    StartAttemptView,
    StudentAttemptDetailView,
    StudentExamListView,
    SubmitAttemptView,
)
from .views import (
    AuthMeAPIView,
    ChangePasswordAPIView,
    DepartmentListAPIView,
    ForgotPasswordAPIView,
    InstitutionListAPIView,
    ResetPasswordAPIView,
    TestAPIView,
    VerifyOTPAPIView,
)

urlpatterns = [
    path('test/', TestAPIView.as_view(), name='test-api'),
    path('faculty/exams/generate/', GeneratePaperView.as_view(), name='faculty-exam-generate'),
    path('faculty/exams/', ExamListView.as_view(), name='faculty-exam-list'),
    path('faculty/exams/<int:exam_id>/', ExamDetailView.as_view(), name='faculty-exam-detail'),
    path('faculty/exams/<int:exam_id>/questions/<int:question_id>/', QuestionUpdateView.as_view(), name='faculty-question-update'),
    path('faculty/exams/<int:exam_id>/publish/', PublishExamView.as_view(), name='faculty-exam-publish'),
    path('student/exams/', StudentExamListView.as_view(), name='student-exam-list'),
    path('student/exams/<int:exam_id>/start/', StartAttemptView.as_view(), name='student-exam-start'),
    path('student/attempts/<int:attempt_id>/save/', SaveAnswerView.as_view(), name='student-answer-save'),
    path('student/attempts/<int:attempt_id>/submit/', SubmitAttemptView.as_view(), name='student-attempt-submit'),
    path('student/attempts/<int:attempt_id>/', StudentAttemptDetailView.as_view(), name='student-attempt-detail'),
    path('departments', DepartmentListAPIView.as_view(), name='department-list-no-slash'),
    path('departments/', DepartmentListAPIView.as_view(), name='department-list'),
    path('auth/me', AuthMeAPIView.as_view(), name='auth-me-no-slash'),
    path('auth/me/', AuthMeAPIView.as_view(), name='auth-me'),
    path('institutions', InstitutionListAPIView.as_view(), name='institution-list-no-slash'),
    path('institutions/', InstitutionListAPIView.as_view(), name='institution-list'),
    path('auth/change-password', ChangePasswordAPIView.as_view(), name='auth-change-password-no-slash'),
    path('auth/change-password/', ChangePasswordAPIView.as_view(), name='auth-change-password'),
    path('auth/forgot-password', ForgotPasswordAPIView.as_view(), name='auth-forgot-password-no-slash'),
    path('auth/forgot-password/', ForgotPasswordAPIView.as_view(), name='auth-forgot-password'),
    path('auth/verify-otp', VerifyOTPAPIView.as_view(), name='auth-verify-otp-no-slash'),
    path('auth/verify-otp/', VerifyOTPAPIView.as_view(), name='auth-verify-otp'),
    path('auth/reset-password', ResetPasswordAPIView.as_view(), name='auth-reset-password-no-slash'),
    path('auth/reset-password/', ResetPasswordAPIView.as_view(), name='auth-reset-password'),
]

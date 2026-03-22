from django.urls import path

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

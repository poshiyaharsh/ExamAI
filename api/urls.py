from django.urls import path

from .views import ChangePasswordAPIView, TestAPIView

urlpatterns = [
    path('test/', TestAPIView.as_view(), name='test-api'),
    path('auth/change-password', ChangePasswordAPIView.as_view(), name='auth-change-password-no-slash'),
    path('auth/change-password/', ChangePasswordAPIView.as_view(), name='auth-change-password'),
]

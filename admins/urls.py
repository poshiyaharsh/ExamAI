from django.urls import path

from .views import AdminInstitutionAPIView, AdminLoginAPIView, AdminSignupAPIView

urlpatterns = [
    path('signup/', AdminSignupAPIView.as_view(), name='admin-signup'),
    path('login/', AdminLoginAPIView.as_view(), name='admin-login'),
    path('institution', AdminInstitutionAPIView.as_view(), name='admin-institution-no-slash'),
    path('institution/', AdminInstitutionAPIView.as_view(), name='admin-institution'),
]

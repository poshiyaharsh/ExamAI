from django.urls import path

from .views import AdminLoginAPIView, AdminSignupAPIView

urlpatterns = [
    path('signup/', AdminSignupAPIView.as_view(), name='admin-signup'),
    path('login/', AdminLoginAPIView.as_view(), name='admin-login'),
]

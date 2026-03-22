from django.urls import path

from .views import FacultyLoginAPIView, FacultySignupAPIView

urlpatterns = [
    path('signup/', FacultySignupAPIView.as_view(), name='faculty-signup'),
    path('login/', FacultyLoginAPIView.as_view(), name='faculty-login'),
]

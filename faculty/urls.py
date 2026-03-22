from django.urls import path

from .views import FacultyLoginAPIView, FacultyProfileAPIView, FacultySignupAPIView

urlpatterns = [
    path('signup/', FacultySignupAPIView.as_view(), name='faculty-signup'),
    path('login/', FacultyLoginAPIView.as_view(), name='faculty-login'),
    path('profile', FacultyProfileAPIView.as_view(), name='faculty-profile-no-slash'),
    path('profile/', FacultyProfileAPIView.as_view(), name='faculty-profile'),
]

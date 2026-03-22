from django.urls import path

from .views import StudentLoginAPIView, StudentProfileAPIView, StudentSignupAPIView

urlpatterns = [
    path('signup/', StudentSignupAPIView.as_view(), name='student-signup'),
    path('login/', StudentLoginAPIView.as_view(), name='student-login'),
    path('profile', StudentProfileAPIView.as_view(), name='student-profile-no-slash'),
    path('profile/', StudentProfileAPIView.as_view(), name='student-profile'),
]

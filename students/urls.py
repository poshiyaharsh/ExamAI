from django.urls import path

from .views import StudentLoginAPIView, StudentSignupAPIView

urlpatterns = [
    path('signup/', StudentSignupAPIView.as_view(), name='student-signup'),
    path('login/', StudentLoginAPIView.as_view(), name='student-login'),
]

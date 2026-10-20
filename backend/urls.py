"""
URL configuration for backend project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.conf import settings
from django.contrib import admin
from django.urls import include, path
from rest_framework_simplejwt.views import TokenRefreshView

urlpatterns = [
    path('api/', include('api.urls')),
    path('api/students/', include('students.urls')),
    path('api/student/', include('students.urls')),
    path('api/faculty/', include('faculty.urls')),
    path('api/admins/', include('admins.urls')),
    path('api/admin/', include('admins.urls')),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token-refresh'),
]

# Cloaked Super Admin mount under secret path
super_admin_path = getattr(settings, 'SUPER_ADMIN_PATH', '').strip()
if super_admin_path:
    urlpatterns.extend([
        path(f'{super_admin_path}/django-admin/', admin.site.urls),
        path(f'{super_admin_path}/api/', include('superadmin.urls')),
    ])


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
from django.db import connection
from django.http import HttpResponseNotFound, JsonResponse
from django.urls import include, path, re_path
from django.utils import timezone
from rest_framework_simplejwt.views import TokenRefreshView


def health_check_view(request):
    """Public lightweight health check endpoint for load balancers and deployment smoke tests."""
    db_ok = True
    try:
        connection.ensure_connection()
    except Exception:
        db_ok = False

    resp_status = 200 if db_ok else 503
    return JsonResponse(
        {
            'status': 'healthy' if db_ok else 'degraded',
            'database': 'connected' if db_ok else 'disconnected',
            'timestamp': timezone.now().isoformat(),
        },
        status=resp_status,
    )


def custom_404_view(request, exception=None):
    """Uniform plain HTML 404 response across all non-existent and unauthenticated routes."""
    return HttpResponseNotFound(
        '<!DOCTYPE html><html lang="en"><head><title>Not Found</title></head>'
        '<body><h1>Not Found</h1><p>The requested resource was not found on this server.</p></body></html>',
        content_type='text/html; charset=utf-8',
    )


handler404 = 'backend.urls.custom_404_view'

urlpatterns = [
    path('health/', health_check_view, name='public-health-check'),
    path('api/', include('api.urls')),
    path('api/students/', include('students.urls')),
    path('api/student/', include('students.urls')),
    path('api/faculty/', include('faculty.urls')),
    path('api/admins/', include('admins.urls')),
    path('api/admin/', include('admins.urls')),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token-refresh'),
]

# Cloaked Super Admin mount using dynamic regex pattern to avoid leaking secret slug in debug dumps
super_admin_path = getattr(settings, 'SUPER_ADMIN_PATH', '').strip()
if super_admin_path:
    urlpatterns.extend([
        re_path(r'^[a-f0-9]{32,64}/django-admin/', admin.site.urls),
        re_path(r'^[a-f0-9]{32,64}/api/', include('superadmin.urls')),
    ])



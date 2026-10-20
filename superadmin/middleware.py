from django.conf import settings
from django.http import JsonResponse
from superadmin.models import SystemSetting


class SuperAdminSecurityMiddleware:
    """
    Applies security constraints across the platform:
    1. Enforces Maintenance Mode for all standard users when enabled.
       Super Admin endpoints remain accessible to platform owners.
    2. Attaches strict no-store and noindex headers to all Super Admin endpoints.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path_info
        super_admin_path = getattr(settings, 'SUPER_ADMIN_PATH', '').strip()
        is_super_admin_url = bool(super_admin_path and (path.startswith(f'/{super_admin_path}/') or path == f'/{super_admin_path}'))

        # Maintenance Mode enforcement
        maintenance = SystemSetting.get_setting('maintenance_mode', {})
        if maintenance and maintenance.get('enabled', False) and not is_super_admin_url:
            message = maintenance.get(
                'message',
                'ExamAI is currently undergoing scheduled platform maintenance. Please check back shortly.'
            )
            return JsonResponse(
                {
                    'status': 'maintenance',
                    'message': message,
                    'estimated_end': maintenance.get('estimated_end', None),
                },
                status=503,
            )

        response = self.get_response(request)

        # Cloaked response headers for Super Admin requests
        if is_super_admin_url:
            response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0, private'
            response['Pragma'] = 'no-cache'
            response['X-Robots-Tag'] = 'noindex, nofollow, noarchive, nosnippet'

        return response

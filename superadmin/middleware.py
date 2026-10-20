import hmac
import re
from django.conf import settings
from django.http import HttpResponseNotFound, JsonResponse
from superadmin.models import MaintenanceWindow, SystemSetting

UNIFORM_404_BODY = (
    '<!DOCTYPE html><html lang="en"><head><title>Not Found</title></head>'
    '<body><h1>Not Found</h1><p>The requested resource was not found on this server.</p></body></html>'
)


class SuperAdminSecurityMiddleware:
    """
    Applies security constraints across the platform:
    1. Enforces Maintenance Mode for all standard users when enabled.
       Super Admin endpoints remain accessible to platform owners.
    2. Dynamic slug validation: any candidate slug matching [a-f0-9]{32,64} that fails
       comparison gets an immediate uniform 404.
    3. Attaches strict no-store and noindex headers to authenticated Super Admin endpoints,
       while keeping 404 responses indistinguishable from normal missing pages.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path_info
        super_admin_path = getattr(settings, 'SUPER_ADMIN_PATH', '').strip()
        is_super_admin_url = bool(super_admin_path and (path.startswith(f'/{super_admin_path}/') or path == f'/{super_admin_path}'))

        # Dynamic slug validation for cloaked paths
        slug_match = re.match(r'^/([a-f0-9]{32,64})/', path)
        if slug_match:
            candidate_slug = slug_match.group(1)
            if not super_admin_path or not hmac.compare_digest(candidate_slug, super_admin_path):
                return HttpResponseNotFound(UNIFORM_404_BODY, content_type='text/html; charset=utf-8')

        # Maintenance Mode enforcement (from MaintenanceWindow model or SystemSetting)
        is_maint_active = False
        maint_msg = 'ExamAI is currently undergoing scheduled platform maintenance. Please check back shortly.'
        maint_end = None

        win_active, win_msg = MaintenanceWindow.is_currently_active()
        if win_active:
            is_maint_active = True
            if win_msg:
                maint_msg = win_msg
            win_rec = MaintenanceWindow.objects.first()
            if win_rec and win_rec.end_time:
                maint_end = win_rec.end_time.isoformat()
        else:
            maintenance = SystemSetting.get_setting('maintenance_mode', {})
            if maintenance and maintenance.get('enabled', False):
                is_maint_active = True
                maint_msg = maintenance.get('message', maint_msg)
                maint_end = maintenance.get('estimated_end', None)

        if is_maint_active and not is_super_admin_url:
            return JsonResponse(
                {
                    'status': 'maintenance',
                    'message': maint_msg,
                    'estimated_end': maint_end,
                },
                status=503,
            )

        response = self.get_response(request)

        # Cloaked response handling for Super Admin requests
        if is_super_admin_url:
            # If request resulted in 404 and user is unauthenticated, return uniform plain 404 to eliminate oracles
            if response.status_code == 404 and not getattr(request, 'is_super_admin', False):
                return HttpResponseNotFound(UNIFORM_404_BODY, content_type='text/html; charset=utf-8')

            # Only attach security/noindex headers on non-404 responses
            if response.status_code != 404:
                response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0, private'
                response['Pragma'] = 'no-cache'
                response['X-Robots-Tag'] = 'noindex, nofollow, noarchive, nosnippet'

        return response

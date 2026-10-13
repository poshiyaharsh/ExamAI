"""Security headers middleware for ExamAI."""


class SecurityHeadersMiddleware:
    """
    Applies modern browser security headers:
    - Content-Security-Policy (CSP)
    - Permissions-Policy
    - Cross-Origin-Opener-Policy (COOP)
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # Content-Security-Policy (CSP)
        if 'Content-Security-Policy' not in response:
            response['Content-Security-Policy'] = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline'; "
                "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
                "font-src 'self' https://fonts.gstatic.com data:; "
                "img-src 'self' data: blob:; "
                "connect-src 'self' http://localhost:8000 http://127.0.0.1:8000 http://localhost:3000 http://localhost:5173; "
                "frame-ancestors 'none'; "
                "form-action 'self';"
            )

        # Permissions-Policy (disables intrusive browser hardware APIs)
        if 'Permissions-Policy' not in response:
            response['Permissions-Policy'] = (
                "accelerometer=(), "
                "camera=(), "
                "geolocation=(), "
                "gyroscope=(), "
                "magnetometer=(), "
                "microphone=(), "
                "payment=(), "
                "usb=()"
            )

        # Cross-Origin Policies
        if 'Cross-Origin-Opener-Policy' not in response:
            response['Cross-Origin-Opener-Policy'] = 'same-origin'

        return response

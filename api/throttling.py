"""Security rate limiting throttles for ExamAI."""

from rest_framework.throttling import AnonRateThrottle, UserRateThrottle


class AuthRateThrottle(AnonRateThrottle):
    """Strict throttle for public authentication endpoints (login, signup, OTP)."""
    scope = 'auth_strict'


class PasswordResetThrottle(AnonRateThrottle):
    """Strict throttle for password reset requests."""
    scope = 'auth_strict'


class PaperGenerationThrottle(UserRateThrottle):
    """Moderate throttle for CPU/GPU-intensive AI paper generation."""
    scope = 'paper_generation'

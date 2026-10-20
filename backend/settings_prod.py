import logging
import os
from pathlib import Path
from django.core.exceptions import ImproperlyConfigured

from backend.settings import *

# Strict production enforcement
DEBUG = False

# Validate Production Environment Variables
REQUIRED_PROD_ENV_VARS = [
    'SECRET_KEY',
    'SUPER_ADMIN_PATH',
    'DB_PASSWORD',
    'ALLOWED_HOSTS',
]

missing_vars = [var for var in REQUIRED_PROD_ENV_VARS if not os.getenv(var, '').strip()]
if missing_vars:
    raise ImproperlyConfigured(
        f"CRITICAL PRODUCTION ERROR: Missing required environment variable(s): {', '.join(missing_vars)}. "
        f"Production deployment cannot start without these variables."
    )

# Host & Transport Security
ALLOWED_HOSTS_RAW = os.getenv('ALLOWED_HOSTS', '')
ALLOWED_HOSTS = [h.strip() for h in ALLOWED_HOSTS_RAW.split(',') if h.strip()]
if not ALLOWED_HOSTS or '*' in ALLOWED_HOSTS:
    raise ImproperlyConfigured("CRITICAL PRODUCTION ERROR: ALLOWED_HOSTS cannot be empty or contain wildcard '*' in production.")

SECURE_SSL_REDIRECT = os.getenv('SECURE_SSL_REDIRECT', 'true').lower() == 'true'
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SAMESITE = 'Lax'

SECURE_HSTS_SECONDS = int(os.getenv('SECURE_HSTS_SECONDS', '31536000'))  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# Static Files Serving (Collectstatic destination)
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Production Logging Configuration with File Rotation
LOGS_DIR = BASE_DIR / 'logs'
os.makedirs(LOGS_DIR, exist_ok=True)


class MaskSensitiveFilter(logging.Filter):
    """Logging filter to mask tokens, passwords, and sensitive keys from file logs."""
    def filter(self, record):
        from superadmin.logs_service import mask_sensitive_data
        if isinstance(record.msg, str):
            record.msg = mask_sensitive_data(record.msg)
        if record.args:
            masked_args = []
            for arg in record.args:
                if isinstance(arg, str):
                    masked_args.append(mask_sensitive_data(arg))
                else:
                    masked_args.append(arg)
            record.args = tuple(masked_args)
        return True


LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'filters': {
        'mask_sensitive': {
            '()': MaskSensitiveFilter,
        },
    },
    'formatters': {
        'standard': {
            'format': '[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s',
            'datefmt': '%Y-%m-%d %H:%M:%S',
        },
    },
    'handlers': {
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'standard',
            'filters': ['mask_sensitive'],
        },
        'file_app': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': str(LOGS_DIR / 'examai.log'),
            'maxBytes': 10 * 1024 * 1024,  # 10 MB per file
            'backupCount': 5,
            'formatter': 'standard',
            'filters': ['mask_sensitive'],
            'encoding': 'utf-8',
        },
        'file_errors': {
            'level': 'ERROR',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': str(LOGS_DIR / 'error.log'),
            'maxBytes': 10 * 1024 * 1024,  # 10 MB per file
            'backupCount': 5,
            'formatter': 'standard',
            'filters': ['mask_sensitive'],
            'encoding': 'utf-8',
        },
    },
    'root': {
        'handlers': ['console', 'file_app', 'file_errors'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file_app', 'file_errors'],
            'level': 'INFO',
            'propagate': False,
        },
        'django.security': {
            'handlers': ['console', 'file_errors'],
            'level': 'WARNING',
            'propagate': False,
        },
        'superadmin': {
            'handlers': ['console', 'file_app', 'file_errors'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}

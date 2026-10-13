"""Global custom DRF exception handler to prevent leaking tracebacks and SQL errors."""

import logging
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler

logger = logging.getLogger('api.security.exceptions')


def custom_exception_handler(exc, context):
    """
    Standardizes error responses across DRF and guarantees no internal stack traces,
    SQL errors, or file paths leak to external clients.
    """
    response = exception_handler(exc, context)

    if response is None:
        view = context.get('view')
        view_name = view.__class__.__name__ if view else 'UnknownView'
        request = context.get('request')
        path = request.path if request else 'UnknownPath'
        
        # Log full traceback securely to server logs
        logger.exception('Unhandled exception on path=%s view=%s: %s', path, view_name, exc)

        return Response(
            {
                'status': 'error',
                'message': 'An unexpected error occurred. The incident has been logged.',
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    return response

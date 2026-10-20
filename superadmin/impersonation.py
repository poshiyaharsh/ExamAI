import logging
from datetime import timedelta
from django.contrib.auth import get_user_model
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework_simplejwt.tokens import RefreshToken

from api.tenant import get_user_institution

User = get_user_model()
logger = logging.getLogger(__name__)


def create_impersonation_session(
    super_admin_user,
    target_user_id: int,
    reason: str,
    client_ip: str = '',
) -> dict:
    """
    Generate a time-limited (15 minutes) impersonated session token for a target user.
    Strictly audited:
    - Reason is mandatory
    - Target cannot be a Super Admin
    - Token explicitly stamped with impersonation claims
    """
    if not reason or len(reason.strip()) < 5:
        raise ValidationError({'reason': 'A specific operational reason (at least 5 characters) is mandatory for impersonation.'})

    try:
        target_user = User.objects.get(pk=target_user_id)
    except User.DoesNotExist:
        raise ValidationError({'target_user_id': 'Target user not found.'})

    # Cannot impersonate super admin
    if hasattr(target_user, 'super_admin_profile') or target_user.is_superuser:
        raise PermissionDenied('Impersonation of Super Admin accounts is strictly prohibited.')

    role = 'user'
    if hasattr(target_user, 'student_profile'):
        role = 'student'
    elif hasattr(target_user, 'faculty_profile'):
        role = 'faculty'
    elif hasattr(target_user, 'admin_profile'):
        role = 'admin'

    institution = get_user_institution(target_user)

    # Issue short-lived SimpleJWT token stamped with impersonation context
    refresh = RefreshToken.for_user(target_user)
    refresh.set_exp(lifetime=timedelta(minutes=15))
    refresh['is_impersonated'] = True
    refresh['impersonated_by'] = super_admin_user.username
    refresh['impersonation_reason'] = reason.strip()
    if institution:
        refresh['institution_id'] = institution.id

    access_token = str(refresh.access_token)

    logger.warning(
        'AUDIT: Super Admin "%s" impersonated user "%s" (role=%s, inst=%s) from IP %s. Reason: %s',
        super_admin_user.username,
        target_user.username,
        role,
        institution.institution_code if institution else 'N/A',
        client_ip,
        reason,
    )

    return {
        'access_token': access_token,
        'target_user': {
            'id': target_user.id,
            'username': target_user.username,
            'email': target_user.email,
            'role': role,
            'institution_name': institution.institution_name if institution else None,
        },
        'is_impersonated': True,
        'impersonated_by': super_admin_user.username,
        'reason': reason.strip(),
        'expires_in_minutes': 15,
    }

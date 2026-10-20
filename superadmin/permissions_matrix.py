import inspect
import logging
from rest_framework.permissions import BasePermission
import api.permissions as api_perms
import superadmin.permissions as sa_perms

logger = logging.getLogger(__name__)


def generate_permissions_matrix() -> dict:
    """
    Introspect real permission classes and build a dynamic matrix of capabilities
    across Student, Faculty, Institute Admin, and Super Admin roles.
    """
    roles = ['Student', 'Faculty', 'Institute Admin', 'Super Admin']

    # Dynamically extract documented permission classes
    detected_perms = []
    for module in [api_perms, sa_perms]:
        for name, cls in inspect.getmembers(module, inspect.isclass):
            if issubclass(cls, BasePermission) and cls is not BasePermission:
                doc = (cls.__doc__ or '').strip().split('\n')[0]
                detected_perms.append({'name': name, 'doc': doc})

    capabilities = [
        {
            'category': 'Identity & Authentication',
            'action': 'Log in with Email & Password',
            'student': True,
            'faculty': True,
            'admin': True,
            'super_admin': True,
            'notes': 'Super Admin strictly requires RFC 6238 TOTP 2FA',
        },
        {
            'category': 'Identity & Authentication',
            'action': 'Self-Service Password Reset via Email OTP',
            'student': True,
            'faculty': True,
            'admin': True,
            'super_admin': False,
            'notes': 'Super Admin is strictly blocked from public reset flow',
        },
        {
            'category': 'Academic & Exams',
            'action': 'Attempt Scheduled Exams & View Own Results',
            'student': True,
            'faculty': False,
            'admin': False,
            'super_admin': False,
            'notes': 'Protected by department isolation and window verification',
        },
        {
            'category': 'Academic & Exams',
            'action': 'Generate AI Questions & Draft Exam Papers',
            'student': False,
            'faculty': True,
            'admin': False,
            'super_admin': False,
            'notes': 'Enforced by faculty tenant verification and monthly AI quotas',
        },
        {
            'category': 'Academic & Exams',
            'action': 'Publish Exams to Students',
            'student': False,
            'faculty': True,
            'admin': True,
            'super_admin': False,
            'notes': 'Governed by institute policy (faculty_can_publish_without_review)',
        },
        {
            'category': 'Academic & Exams',
            'action': 'Live Proctoring & Real-Time Monitoring',
            'student': False,
            'faculty': True,
            'admin': True,
            'super_admin': False,
            'notes': 'Monitors face violations, fullscreen exits, tab switches',
        },
        {
            'category': 'Institute Administration',
            'action': 'Onboard / Bulk Import Students & Faculty',
            'student': False,
            'faculty': False,
            'admin': True,
            'super_admin': True,
            'notes': 'Enforces immutable department and student/faculty quotas',
        },
        {
            'category': 'Institute Administration',
            'action': 'Configure Institute Logo, Timezone & Overrides',
            'student': False,
            'faculty': False,
            'admin': True,
            'super_admin': True,
            'notes': 'All modifications recorded in immutable audit log',
        },
        {
            'category': 'Platform Operations',
            'action': 'Create & Suspend Tenant Institutes',
            'student': False,
            'faculty': False,
            'admin': False,
            'super_admin': True,
            'notes': 'Requires step-up re-authentication within 5 minutes',
        },
        {
            'category': 'Platform Operations',
            'action': 'Trigger & Test Database Backups',
            'student': False,
            'faculty': False,
            'admin': False,
            'super_admin': True,
            'notes': 'Stores outside repo, computes SHA-256, verifies scratch restore',
        },
        {
            'category': 'Platform Operations',
            'action': 'Configure Scheduled Maintenance Windows',
            'student': False,
            'faculty': False,
            'admin': False,
            'super_admin': True,
            'notes': 'Returns 503 to non-superadmin users while super admin bypasses',
        },
        {
            'category': 'Platform Operations',
            'action': 'Time-Limited Audited User Impersonation',
            'student': False,
            'faculty': False,
            'admin': False,
            'super_admin': True,
            'notes': 'Requires mandatory stated reason and step-up re-auth',
        },
    ]

    return {
        'roles': roles,
        'detected_permission_classes': detected_perms,
        'matrix': capabilities,
    }

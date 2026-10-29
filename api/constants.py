from django.conf import settings

# Proctoring Rules Configuration (Single source of truth)
# 1 warning allowed; the 2nd violation auto-submits the exam.
MAX_WARNINGS: int = getattr(settings, 'MAX_WARNINGS', 1)

# Faculty configurable range for exam max_warnings
MIN_ALLOWED_WARNINGS: int = 0
MAX_ALLOWED_WARNINGS: int = 10

# Debounce window in seconds to group concurrent triggers (fullscreen exit, tab hidden, window blur)
# as one physical incident.
VIOLATION_INCIDENT_DEBOUNCE_SECONDS: float = 1.0


import functools
import logging
import random
import time
from django.db import OperationalError

logger = logging.getLogger(__name__)


def is_lock_or_deadlock(exc: Exception) -> bool:
    """
    Detect SQLite database locked or MySQL deadlock (1213) / lock wait timeout (1205).
    """
    if not isinstance(exc, OperationalError):
        return False

    # Check MySQL error codes (args[0] is often the MySQL errno int)
    if hasattr(exc, 'args') and len(exc.args) > 0:
        err_code = exc.args[0]
        if isinstance(err_code, int) and err_code in (1213, 1205):
            return True

    err_msg = str(exc).lower()
    return (
        'database is locked' in err_msg
        or 'database table is locked' in err_msg
        or 'deadlock found' in err_msg
        or 'lock wait timeout exceeded' in err_msg
        or 'try restarting transaction' in err_msg
        or '1213' in err_msg
        or '1205' in err_msg
    )


def retry_on_deadlock(max_retries: int = 3, base_delay: float = 0.1):
    """
    Decorator for transactional write operations that retries on deadlock or lock timeout
    with jittered exponential backoff.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except OperationalError as exc:
                    if is_lock_or_deadlock(exc) and attempt < max_retries - 1:
                        sleep_time = (base_delay * (2 ** attempt)) + random.uniform(0.02, 0.08)
                        logger.warning(
                            'Database lock/deadlock detected in %s, retrying in %.3fs (attempt %d/%d): %s',
                            func.__name__, sleep_time, attempt + 1, max_retries, exc
                        )
                        time.sleep(sleep_time)
                        continue
                    raise
        return wrapper
    return decorator

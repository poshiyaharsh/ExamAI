"""
Native RFC 6238 compliant TOTP and recovery code security utilities.
Zero external dependencies, relies exclusively on Python standard library
and Django authentication hashers.
"""

import base64
import hashlib
import hmac
import secrets
import struct
import time
from urllib.parse import quote
from django.contrib.auth.hashers import check_password, make_password


def generate_totp_secret() -> str:
    """Generate a random Base32 encoded 160-bit (20 bytes) secret."""
    raw_bytes = secrets.token_bytes(20)
    return base64.b32encode(raw_bytes).decode('ascii').rstrip('=')


def get_totp_code(secret: str, time_step: int | None = None) -> str:
    """
    Compute standard 6-digit RFC 6238 TOTP code for a given secret at time_step.
    """
    if time_step is None:
        time_step = int(time.time() // 30)

    # Normalize padding for Base32
    padding = (8 - (len(secret) % 8)) % 8
    normalized_secret = secret.upper() + ('=' * padding)
    key = base64.b32decode(normalized_secret, casefold=True)

    # 8-byte big-endian counter
    msg = struct.pack('>Q', time_step)
    digest = hmac.new(key, msg, hashlib.sha1).digest()

    # Dynamic truncation
    offset = digest[-1] & 0x0F
    code_int = struct.unpack('>I', digest[offset:offset + 4])[0] & 0x7FFFFFFF
    code = code_int % 1000000
    return f'{code:06d}'


def verify_totp(secret: str, code: str, window: int = 1) -> bool:
    """
    Verify a 6-digit TOTP code against the secret within a drift window (+/- 30s).
    Uses constant-time comparison to prevent timing attacks.
    """
    if not secret or not code:
        return False

    code = str(code).strip()
    if len(code) != 6 or not code.isdigit():
        return False

    current_step = int(time.time() // 30)
    for offset in range(-window, window + 1):
        candidate = get_totp_code(secret, current_step + offset)
        if hmac.compare_digest(candidate, code):
            return True

    return False


def get_totp_uri(secret: str, username: str, issuer: str = 'ExamAI') -> str:
    """
    Build standard otpauth:// URI for authenticator applications (Google Authenticator, Authy, etc.).
    """
    label = f'{quote(issuer)}:{quote(username)}'
    return f'otpauth://totp/{label}?secret={secret}&issuer={quote(issuer)}&algorithm=SHA1&digits=6&period=30'


def generate_recovery_codes(count: int = 8) -> tuple[list[str], list[str]]:
    """
    Generate readable one-time recovery codes and their salted Argon2/PBKDF2 hashes.
    Returns:
        (plain_codes, hashed_codes)
    """
    charset = '23456789ABCDEFGHJKLMNPQRSTUVWXYZ'  # Unambiguous characters
    plain_codes = []
    hashed_codes = []

    for _ in range(count):
        part1 = ''.join(secrets.choice(charset) for _ in range(4))
        part2 = ''.join(secrets.choice(charset) for _ in range(4))
        plain_code = f'{part1}-{part2}'
        plain_codes.append(plain_code)
        hashed_codes.append(make_password(plain_code))

    return plain_codes, hashed_codes


def verify_and_consume_recovery_code(plain_code: str, hashed_codes: list[str]) -> tuple[bool, list[str]]:
    """
    Verify whether the provided recovery code matches any of the stored hashes.
    If valid, returns (True, updated_hashed_codes_without_used_code).
    Otherwise returns (False, unchanged_hashed_codes).
    """
    normalized_code = str(plain_code).strip().upper()
    if not normalized_code:
        return False, hashed_codes

    for idx, code_hash in enumerate(hashed_codes):
        if check_password(normalized_code, code_hash):
            updated_hashes = [h for i, h in enumerate(hashed_codes) if i != idx]
            return True, updated_hashes

    return False, hashed_codes

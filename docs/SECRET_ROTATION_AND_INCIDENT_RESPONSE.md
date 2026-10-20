# ExamAI Secret Rotation & Incident Response Guide

This document defines emergency response protocols, incident classification tiers, and step-by-step secret rotation procedures for ExamAI.

---

## 1. Incident Classification Matrix

| Tier | Definition | Example Scenarios | Action Window |
| :--- | :--- | :--- | :--- |
| **Sev-1 (Critical)** | Core system compromise, leaked `SECRET_KEY`, audit tampering detected, unauthenticated admin access. | `SECRET_KEY` published in public repo; audit log HMAC hash chain broken. | Immediate (< 1 hour) |
| **Sev-2 (High)** | Super Admin secret slug leaked, compromised operator credentials, mass brute force attempts. | `SUPER_ADMIN_PATH` exposed in access logs or external referral headers. | < 4 hours |
| **Sev-3 (Medium)** | Isolated faculty/student account takeover, failed TOTP probe bursts. | Targeted phishing of institute faculty or admin account. | < 12 hours |
| **Sev-4 (Low)** | Non-exploitable informational scanner probes, routine credential rotation. | Periodic 90-day secret rotation. | Scheduled maintenance |

---

## 2. Emergency Incident Response Checklist

When a Sev-1 or Sev-2 incident is detected:
1. **Declare Incident**: Notify the platform owner (`harshposhiya92@gmail.com`).
2. **Enable Platform Maintenance Mode**:
   ```bash
   python -c "from superadmin.models import MaintenanceWindow; from django.utils import timezone, timedelta; MaintenanceWindow.objects.create(title='Emergency Security Containment', is_active=True, start_time=timezone.now(), end_time=timezone.now()+timedelta(hours=2), reason='Undergoing emergency security maintenance.')"
   ```
3. **Invalidate All Active Super Admin Sessions**:
   ```bash
   python -c "from superadmin.models import SuperAdminProfile; SuperAdminProfile.objects.update(active_session_id=None)"
   ```
4. **Isolate Compromised Systems**: Restrict firewall ingress to known administrator IP addresses.

---

## 3. Secret Rotation Procedures

### Procedure A: Rotating `SUPER_ADMIN_PATH` (Hidden Slug)

If the cloaked path is leaked or exposed:
1. Generate a new high-entropy 32-byte (64-character) hexadecimal string:
   ```bash
   python -c "import secrets; print(secrets.token_hex(32))"
   ```
2. Update the `.env` configuration file:
   ```env
   SUPER_ADMIN_PATH=new_64_character_hex_string_here
   ```
3. Reload the application server:
   ```bash
   sudo systemctl reload examai.service
   ```
4. Verify that requests to the old path return an immediate uniform 404 with no hints:
   ```bash
   curl -i http://127.0.0.1:8000/old_slug/api/dashboard/
   # Must return 404 Not Found
   ```

### Procedure B: Rotating `SECRET_KEY`

If Django `SECRET_KEY` is compromised:
1. Generate a new cryptographic key:
   ```bash
   python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
   ```
2. **Preserve Audit Salt**: If you wish to maintain verification compatibility for historical audit records, verify that `SUPERADMIN_AUDIT_SALT` is explicitly set in `.env` before updating `SECRET_KEY`.
3. Update `SECRET_KEY` in `/etc/examai/.env`.
4. Restart the web server. All existing Django sessions, CSRF tokens, and unsigned reset tokens will be immediately invalidated.
5. All users and super admins must log in again with new authentication tokens.

### Procedure C: Super Admin 2FA Reset & Recovery

If the owner loses access to their TOTP authenticator device:
1. Run the recovery authentication CLI on the secure server terminal:
   ```bash
   python manage.py create_super_admin --reset-totp
   ```
2. The interactive script prompts for the owner's master password (using hidden `getpass` prompt).
3. Upon successful password validation, a new TOTP QR code and 10 single-use emergency recovery backup codes are generated and displayed in the terminal.
4. Scan the new QR code in Google Authenticator or 1Password.

---

## 4. Cryptographic Audit Log Verification & Tamper Detection

ExamAI maintains an unbroken HMAC-SHA256 hash chain on all Super Admin actions:
```
Entry N: Hash = HMAC-SHA256(prev_hash + timestamp + actor + action + target + ip + salt)
```

### Verifying Chain Integrity
Run the integrity verification script:
```bash
python -c "from superadmin.models import SuperAdminAuditLog; valid, broken_id = SuperAdminAuditLog.verify_integrity(); print('Chain Valid:', valid, 'Broken ID:', broken_id)"
```

- If `Chain Valid: True`: The audit trail is cryptographically pristine and unaltered.
- If `Chain Valid: False`: The entry identified by `broken_id` was modified, deleted, or inserted out of order. Initiate Sev-1 incident investigation immediately.

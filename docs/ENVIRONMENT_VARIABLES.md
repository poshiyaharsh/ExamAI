# ExamAI Environment Variables Reference

This document catalogs all environment variables used by the ExamAI platform, backend settings (`settings.py` and `settings_prod.py`), and operational tasks.

---

## 1. Core Application Variables

| Variable | Type | Default | Description | Production Requirement |
| :--- | :--- | :--- | :--- | :--- |
| `DJANGO_SETTINGS_MODULE` | string | `backend.settings` | Target settings module (`backend.settings` for dev, `backend.settings_prod` for prod). | Must be `backend.settings_prod` in production. |
| `DEBUG` | boolean | `False` | Enables Django developer debug tracebacks and route dumps. | **Strictly `False`** in production. |
| `SECRET_KEY` | string | *None* | Primary cryptographic key for Django sessions, signing, CSRF tokens, and audit hash HMAC. | High-entropy random string (>= 50 chars). Never commit to Git. |
| `ALLOWED_HOSTS` | string | `localhost,127.0.0.1` | Comma-separated list of domain names/IP addresses the application will serve. | Set strictly to platform domain (e.g. `examai.yourdomain.com`). |
| `CORS_ALLOWED_ORIGINS` | string | `http://localhost:3000` | Comma-separated list of allowed frontend origins for Cross-Origin Resource Sharing. | Strict HTTPS URL of the frontend SPA. |
| `CSRF_TRUSTED_ORIGINS` | string | `http://localhost:3000` | Comma-separated list of trusted origins for unsafe HTTP methods (POST, PUT, DELETE). | Must include `https://examai.yourdomain.com`. |

---

## 2. Super Admin & Security Variables

| Variable | Type | Default | Description | Security Implication |
| :--- | :--- | :--- | :--- | :--- |
| `SUPER_ADMIN_PATH` | string | *Generated* | Secret hexadecimal slug (32–64 characters) where the Super Admin endpoints and console are mounted. | Keeps Super Admin invisible to scanners. Never share or log this slug. |
| `SUPERADMIN_AUDIT_SALT` | string | Auto-derived from `SECRET_KEY` | Cryptographic salt used for computing HMAC-SHA256 hash chains on `SuperAdminAuditLog`. | Changing this invalidates verification of previous audit logs unless preserved. |
| `ACCESS_TOKEN_LIFETIME_MINUTES` | integer | `15` | Super Admin JWT access token validity period. | Short-lived tokens minimize window of exposure if intercepted. |
| `REFRESH_TOKEN_LIFETIME_DAYS` | integer | `1` | Refresh token duration for re-authenticating sessions. | Invalidation enforced server-side upon logout via `active_session_id`. |
| `SESSION_INACTIVITY_TIMEOUT_MINUTES` | integer | `15` | Inactivity threshold for Super Admin console sliding session. | Auto-revokes session when operator is idle. |

---

## 3. Database Settings

| Variable | Type | Default | Description | Notes |
| :--- | :--- | :--- | :--- | :--- |
| `DB_ENGINE` | string | `django.db.backends.sqlite3` | Database engine backend (`django.db.backends.postgresql` or `sqlite3`). | PostgreSQL 14+ recommended for concurrent loads. |
| `DB_NAME` | string | `db.sqlite3` | Name of the database or path to SQLite file. | In production, use managed DB name. |
| `DB_USER` | string | *empty* | Database username. | Use least-privilege database user. |
| `DB_PASSWORD` | string | *empty* | Database password. | Encrypted or loaded via secret manager. |
| `DB_HOST` | string | *empty* | Database host address. | Use private VPC host or localhost socket. |
| `DB_PORT` | string | *empty* | Database port (e.g., 5432 for Postgres, 3306 for MySQL). | Defaults to engine standard. |

---

## 4. Local Ollama AI Integration

| Variable | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `OLLAMA_API_URL` | string | `http://127.0.0.1:11434` | Endpoint of the local or VPC Ollama inference service. |
| `OLLAMA_MODEL` | string | `deepseek-r1:8b` | Default LLM model identifier for paper generation and automated grading. |
| `OLLAMA_TIMEOUT_SECONDS` | integer | `180` | Network timeout for AI generation requests before triggering retry/fallback. |

---

## 5. Operations, Backups & Alerting

| Variable | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `EXAMAI_BACKUP_DIR` | string | `../backups` | Absolute directory path where encrypted database snapshots and metadata are saved. |
| `EXAMAI_BACKUP_RETENTION_DAYS` | integer | `14` | Automatic pruning threshold: backup files older than this count are safely unlinked. |
| `ALERT_EMAIL_RECIPIENTS` | string | *empty* | Comma-separated list of platform administrator email addresses receiving deduplicated critical alerts. |
| `ALERT_COOLDOWN_MINUTES` | integer | `60` | Deduplication window: duplicate alerts for the same issue are suppressed during this window. |
| `LOG_DIR` | string | `logs/` | Directory path for rotating file logs (`examai_app.log`, `examai_error.log`). |
| `LOG_LEVEL` | string | `INFO` | Root logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`). |

---

## 6. Email Delivery Configuration

| Variable | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `EMAIL_BACKEND` | string | `django.core.mail.backends.console.EmailBackend` | Mail backend (`smtp.EmailBackend` in production). |
| `EMAIL_HOST` | string | `smtp.gmail.com` | SMTP relay server host. |
| `EMAIL_PORT` | integer | `587` | SMTP port (587 for TLS, 465 for SSL). |
| `EMAIL_USE_TLS` | boolean | `True` | Enforce TLS encryption for outbound emails. |
| `EMAIL_HOST_USER` | string | *empty* | SMTP username / sender account. |
| `EMAIL_HOST_PASSWORD` | string | *empty* | App password or SMTP credentials (never commit!). |
| `DEFAULT_FROM_EMAIL` | string | `ExamAI Security <no-reply@examai.com>` | Default envelope from address. |

---

## 7. Security Rules for Env Files

1. **Never commit `.env` or `.env.prod` to version control.** Verify `.gitignore` contains all `.env*` files.
2. In production, protect environment files with restrictive operating system permissions:
   ```bash
   chmod 600 /etc/examai/.env
   chown www-data:www-data /etc/examai/.env
   ```
3. Use automated secrets rotation policies every 90 days for `SECRET_KEY`, database passwords, and SMTP credentials.

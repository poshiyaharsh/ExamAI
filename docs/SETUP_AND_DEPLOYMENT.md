# ExamAI Production Setup & Deployment Guide

This guide details the steps required to deploy ExamAI with Super Admin Stage 2 in a secure, hardened production environment.

---

## 1. Architecture Overview

ExamAI production topology:
```
[ Client Browser / Mobile ]
            │ HTTPS (443)
            ▼
     [ Nginx / Caddy Reverse Proxy ]
      │ (SSL termination, rate limiting, static assets)
      ├────────────────────────┬────────────────────────┐
      │ /                      │ /api/, /health/,       │ /{SUPER_ADMIN_PATH}/
      ▼                        ▼ /{SUPER_ADMIN_PATH}/api│
[ Frontend Static Dist ] [ Gunicorn / WSGI Backend ]    ▼
(Built via Vite)        (Django 6.0, settings_prod.py) [ Super Admin Console ]
                               │
            ┌──────────────────┼──────────────────┐
            ▼                  ▼                  ▼
      [ PostgreSQL DB ]  [ Local Ollama ]   [ Backup Storage ]
     (Pooled connections) (Port 11434)      (Encrypted offsite/volume)
```

---

## 2. Pre-Deployment Checklist

Before deploying to production, verify:
- [ ] `DEBUG=False` is strictly set (enforced by `backend/settings_prod.py`).
- [ ] `SECRET_KEY` is cryptographically strong (at least 50 random characters) and not committed to Git.
- [ ] `SUPER_ADMIN_PATH` is set to a 32-64 character hexadecimal random string (e.g. generated via `openssl rand -hex 32`).
- [ ] `ALLOWED_HOSTS` includes only your fully-qualified domain names.
- [ ] Database credentials point to a production-grade managed database (PostgreSQL 14+ recommended).
- [ ] Local Ollama is running and model `deepseek-r1:8b` (or configured model) is pulled and responding at `http://127.0.0.1:11434`.
- [ ] Backup directory `EXAMAI_BACKUP_DIR` exists with restricted OS-level permissions (`chmod 700`).

---

## 3. Production Environment Configuration

1. Create a production environment file (e.g., `/etc/examai/.env` or `.env.prod`):
   ```env
   DJANGO_SETTINGS_MODULE=backend.settings_prod
   SECRET_KEY=your-securely-generated-production-secret-key-min-50-chars
   DEBUG=False
   ALLOWED_HOSTS=examai.yourdomain.com
   CORS_ALLOWED_ORIGINS=https://examai.yourdomain.com
   CSRF_TRUSTED_ORIGINS=https://examai.yourdomain.com

   # Database (PostgreSQL recommended for production)
   DB_ENGINE=django.db.backends.postgresql
   DB_NAME=examai_prod
   DB_USER=examai_user
   DB_PASSWORD=your_strong_db_password
   DB_HOST=127.0.0.1
   DB_PORT=5432

   # Cloaked Super Admin Slug (32-64 hex chars)
   SUPER_ADMIN_PATH=e4b789123456789abcdef0123456789abcdef0123456789abcdef0123456789a

   # Operations & Monitoring
   ALERT_EMAIL_RECIPIENTS=harshposhiya92@gmail.com
   EXAMAI_BACKUP_DIR=/var/backups/examai
   EXAMAI_BACKUP_RETENTION_DAYS=14
   OLLAMA_API_URL=http://127.0.0.1:11434
   OLLAMA_MODEL=deepseek-r1:8b
   ```

---

## 4. Backend Deployment Steps

### Step 4.1: Python Environment & Dependencies
```bash
python3 -m venv /opt/examai/venv
source /opt/examai/venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install gunicorn psycopg2-binary
```

### Step 4.2: Run Migrations
```bash
python manage.py migrate --settings=backend.settings_prod
```

### Step 4.3: Collect Static Files
```bash
python manage.py collectstatic --noinput --settings=backend.settings_prod
```

### Step 4.4: System Readiness Check
```bash
python manage.py check --deploy --settings=backend.settings_prod
```

### Step 4.5: Gunicorn Service (`/etc/systemd/system/examai.service`)
```ini
[Unit]
Description=ExamAI Django Application Server
After=network.target postgresql.service

[Service]
User=www-data
Group=www-data
WorkingDirectory=/opt/examai
EnvironmentFile=/etc/examai/.env
ExecStart=/opt/examai/venv/bin/gunicorn \
    --workers 4 \
    --threads 2 \
    --bind 127.0.0.1:8000 \
    --access-logfile /var/log/examai/access.log \
    --error-logfile /var/log/examai/error.log \
    backend.wsgi:application
Restart=always

[Install]
WantedBy=multi-user.target
```

---

## 5. Frontend Build & Serving

1. Install frontend dependencies and build production artifacts:
   ```bash
   cd Front-End
   npm ci
   npm run build
   ```
2. The output in `Front-End/dist/` contains optimized static HTML, JavaScript, and CSS assets to be served by Nginx.

---

## 6. Nginx Reverse Proxy Configuration

Create `/etc/nginx/sites-available/examai.conf`:
```nginx
server {
    listen 80;
    server_name examai.yourdomain.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name examai.yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/examai.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/examai.yourdomain.com/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    # Security Headers
    add_header X-Frame-Options "DENY" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains; preload" always;

    # Static Assets & Frontend SPA
    root /opt/examai/Front-End/dist;
    index index.html;

    location /static/ {
        alias /opt/examai/staticfiles/;
        expires 30d;
        add_header Cache-Control "public, max-age=2592000, immutable";
    }

    location /media/ {
        alias /opt/examai/media/;
        expires 7d;
        add_header Cache-Control "private, max-age=604800";
    }

    # API and Health Check reverse proxy to Gunicorn
    location ~ ^/(api|health|[a-f0-9]{32,64})/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 180s;
        proxy_connect_timeout 10s;
    }

    # Client-side SPA routing fallback
    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

---

## 7. Verification: Smoke Testing

Run the included smoke test suite after service startup:
```bash
python scripts/smoke_test.py --url https://examai.yourdomain.com
```

Expected output:
```
============================================================
ExamAI Post-Deployment Smoke Test Suite
Target: https://examai.yourdomain.com
============================================================

  [PASS] Public Health Check (/health/)
  [PASS] Database Connectivity Status
  [PASS] Public Institutions List (/api/institutions/)
  [PASS] 404 Contains No Server Version Leaks
  [PASS] Cloaked Secret Path Probe Protection (Uniform 404)
  [PASS] Probe Does Not Reveal SuperAdmin Header
  [PASS] Local Ollama Engine Reachability (:11434)

------------------------------------------------------------
Smoke Test Results: 7 PASSED, 0 FAILED
------------------------------------------------------------
```

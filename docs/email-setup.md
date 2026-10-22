# ExamAI - Free Email Provider Setup Guide

ExamAI includes real-time transactional and broadcast email delivery for:
- Super Admin broadcast campaigns (with opt-in toggle and recipient tracking)
- Security notifications and 2FA recovery alerts
- Password reset OTPs

If SMTP environment variables are unset or incomplete, ExamAI **automatically and safely falls back to local console output** (`django.core.mail.backends.console.EmailBackend`). No crash or unhandled exception will ever occur.

---

## 1. Provider Option A: Brevo (Recommended)
**Free Tier:** 300 emails/day (~9,000/month) forever with zero credit card required.
**Best For:** Educational platforms, transactional alerts, and broadcast campaigns.

### Step-by-Step Setup:
1. Create a free account at [brevo.com](https://www.brevo.com/).
2. Verify your sender email address (e.g., `admin@your-college.edu` or your personal email) in **Senders & IP**.
3. Go to **SMTP & API** &rarr; **SMTP** tab.
4. Note your SMTP key details and add to your `.env` file:
   ```env
   EMAIL_HOST=smtp-relay.brevo.com
   EMAIL_PORT=587
   EMAIL_HOST_USER=your_brevo_login_email@example.com
   EMAIL_HOST_PASSWORD=your_brevo_smtp_master_key
   EMAIL_USE_TLS=true
   EMAIL_USE_SSL=false
   DEFAULT_FROM_EMAIL=your_verified_sender@example.com
   ```
5. Test the connection:
   ```bash
   python manage.py test_email --to your_email@example.com
   ```

---

## 2. Provider Option B: Gmail (App Password)
**Free Tier:** 500 emails/day free.
**Best For:** Fast testing and local development using an existing Google account.

### Step-by-Step Setup:
1. Go to your [Google Account Security Settings](https://myaccount.google.com/security).
2. Ensure **2-Step Verification** is turned **ON**.
3. Under *How you sign in to Google*, select **App passwords** (or search "App passwords" in the search bar).
4. Enter an app name like `ExamAI Platform` and click **Create**.
5. Copy the 16-character password generated (spaces are ignored).
6. Configure in `.env`:
   ```env
   EMAIL_HOST=smtp.gmail.com
   EMAIL_PORT=587
   EMAIL_HOST_USER=your_actual_gmail@gmail.com
   EMAIL_HOST_PASSWORD=xxxx-xxxx-xxxx-xxxx
   EMAIL_USE_TLS=true
   EMAIL_USE_SSL=false
   DEFAULT_FROM_EMAIL=your_actual_gmail@gmail.com
   ```
7. Run test:
   ```bash
   python manage.py test_email --to your_email@gmail.com
   ```

---

## 3. Provider Option C: Mailjet
**Free Tier:** 200 emails/day (6,000 emails/month) forever.
**Best For:** Strict SPF/DKIM verification and deliverability.

### Step-by-Step Setup:
1. Register at [mailjet.com](https://www.mailjet.com/).
2. Verify your sender email under **Account Settings** &rarr; **Sender Domains & Addresses**.
3. Go to **Transactional** &rarr; **SMTP Settings**.
4. Configure in `.env`:
   ```env
   EMAIL_HOST=in-v3.mailjet.com
   EMAIL_PORT=587
   EMAIL_HOST_USER=your_mailjet_api_key
   EMAIL_HOST_PASSWORD=your_mailjet_secret_key
   EMAIL_USE_TLS=true
   EMAIL_USE_SSL=false
   DEFAULT_FROM_EMAIL=your_verified_sender@example.com
   ```

---

## 4. Console Fallback Mode (Development & Offline)
When `EMAIL_HOST` or `EMAIL_HOST_USER` or `EMAIL_HOST_PASSWORD` is omitted or left blank in `.env`:
- ExamAI logs an informational notice.
- Outbound emails are printed directly to the terminal running `runserver`.
- No network socket or third-party API is contacted.
- All delivery records in Super Admin are marked with status `sent` (via console) or `skipped`.

---

## 5. Quota & Rate-Limiting Controls
To prevent provider account suspension or IP throttling:
```env
EMAIL_MAX_PER_MINUTE=30       # Max emails per 60-second window
EMAIL_MAX_PER_DAY=300         # Daily hard ceiling
EMAIL_BATCH_SIZE=20           # Group size per dispatch loop
EMAIL_BATCH_DELAY_SECONDS=1.0 # Pause between consecutive chunks
```

---

## 6. Testing Email Delivery
Run the Super Admin CLI command to verify dispatch end-to-end:
```bash
python manage.py test_email --to recipient@example.com
```
You can also run a test directly from the Super Admin Console under **Notifications & Campaigns** &rarr; **Email Delivery & Diagnostics**.

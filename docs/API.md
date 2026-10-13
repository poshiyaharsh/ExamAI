# ExamAI REST API Reference

All requests must provide valid JSON payloads (`Content-Type: application/json`) unless uploading files (`multipart/form-data`).

Authenticated endpoints require a valid JWT Bearer token:
```http
Authorization: Bearer <access_token>
```

---

## Standard Error Response Format

```json
{
  "status": "error",
  "message": "Human-readable description of error.",
  "errors": {
    "field_name": ["Specific validation error message."]
  }
}
```

---

## 1. Authentication & Account Endpoints

| Method | Path | Description | Auth Required |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/admins/login/` | Admin credentials login, returns JWT access & refresh tokens | No |
| `POST` | `/api/admins/signup/` | Initial institute administrator registration | No |
| `POST` | `/api/faculty/login/` | Faculty credentials login | No |
| `POST` | `/api/faculty/signup/` | Faculty registration under specific institution & department | No |
| `POST` | `/api/students/login/` | Student credentials login | No |
| `POST` | `/api/students/signup/` | Student registration under specific institution & department | No |
| `POST` | `/api/token/refresh/` | Refresh expired access token with valid refresh token | No |
| `GET` | `/api/auth/me/` | Fetch authenticated user profile, active role, and institution | Yes |
| `POST` | `/api/auth/change-password/` | Change password with current password verification | Yes |
| `POST` | `/api/auth/forgot-password/` | Request 6-digit password reset OTP sent to registered email | No |
| `POST` | `/api/auth/verify-otp/` | Verify OTP code and obtain single-use reset token | No |
| `POST` | `/api/auth/reset-password/` | Reset password using verified single-use token | No |

---

## 2. Administrator Endpoints (`/api/admin/*`)

| Method | Path | Description | Role Required |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/admin/dashboard/` | Full KPI dashboard (students, faculty, active live exams top 6, department pass rates) | Admin |
| `GET` | `/api/admin/institution/` | Get current institution profile and settings | Admin |
| `PUT` | `/api/admin/institution/` | Update institution profile (name, address, phone) | Admin |
| `GET` | `/api/admin/students/` | List students with search, department filtering, and pagination | Admin |
| `GET` | `/api/admin/students/<id>/` | View detailed student profile | Admin |
| `PUT` | `/api/admin/students/<id>/` | Update student profile, status, or department | Admin |
| `DELETE`| `/api/admin/students/<id>/` | Remove student account | Admin |
| `GET` | `/api/admin/students/<id>/results/` | Audit complete exam attempt history for specific student | Admin |
| `GET` | `/api/admin/faculty/` | List faculty with department breakdown and statistics | Admin |
| `POST` | `/api/admin/faculty/` | Create new faculty account under current institution | Admin |
| `GET` | `/api/admin/faculty/<id>/` | View faculty member details | Admin |
| `PUT` | `/api/admin/faculty/<id>/` | Update faculty details, designation, or department | Admin |
| `DELETE`| `/api/admin/faculty/<id>/` | Deactivate/remove faculty member | Admin |
| `GET` | `/api/admin/exams/` | List all exams across institution with live status indicators | Admin |
| `GET` | `/api/admin/exams/<id>/` | View detailed exam configuration and questions | Admin |
| `GET` | `/api/admin/exams/<id>/live-roster/` | Real-time proctor roster of eligible students and live statuses | Admin |
| `GET` | `/api/admin/exams/audit/` | Audit exams for department or isolation discrepancies | Admin |

---

## 3. Question Bank Endpoints (`/api/admin/question-bank/*`)

| Method | Path | Description | Role Required |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/admin/question-bank/questions/` | List questions with search, filters (subject, topic, difficulty, type, status) | Admin / Faculty |
| `POST` | `/api/admin/question-bank/questions/` | Create a new question with options and model answer | Admin / Faculty |
| `GET` | `/api/admin/question-bank/questions/<id>/` | Retrieve single question details and audit log | Admin / Faculty |
| `PUT` | `/api/admin/question-bank/questions/<id>/` | Update question text, difficulty, marks, or options | Admin / Faculty |
| `DELETE`| `/api/admin/question-bank/questions/<id>/` | Soft-delete question (clears `active_hash` to avoid collisions) | Admin / Faculty |
| `POST` | `/api/admin/question-bank/questions/<id>/restore/` | Restore previously soft-deleted question | Admin / Faculty |
| `POST` | `/api/admin/question-bank/questions/<id>/duplicate/` | Clone existing question for rapid variations | Admin / Faculty |
| `POST` | `/api/admin/question-bank/questions/bulk-action/` | Perform bulk status change, bulk delete, or bulk restore | Admin / Faculty |
| `POST` | `/api/admin/question-bank/questions/bulk-import/` | Import questions via CSV, JSON, or Excel (`.xlsx`) | Admin / Faculty |
| `GET` | `/api/admin/question-bank/questions/export/` | Export questions to CSV, JSON, or Excel formats | Admin / Faculty |
| `GET` | `/api/admin/question-bank/questions/template/` | Download sample import templates (CSV, XLSX, JSON) | Admin / Faculty |
| `GET` | `/api/admin/question-bank/subjects/` | List subjects for current institution | Admin / Faculty |
| `POST` | `/api/admin/question-bank/subjects/` | Create subject with code, department, and title | Admin / Faculty |
| `GET` | `/api/admin/question-bank/topics/` | List topics scoped to subject | Admin / Faculty |
| `POST` | `/api/admin/question-bank/topics/` | Create topic under subject | Admin / Faculty |
| `GET` | `/api/admin/question-bank/stats/` | Question bank metrics (total active, per difficulty, per type) | Admin / Faculty |

---

## 4. Faculty Endpoints (`/api/faculty/*`)

| Method | Path | Description | Role Required |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/faculty/dashboard/` | Faculty overview (generated papers, published exams, average marks) | Faculty |
| `POST` | `/api/faculty/exams/generate/` | Automated blueprint-driven paper generation | Faculty |
| `DELETE`| `/api/faculty/exams/cache/` | Clear paper generation cache for current faculty member | Faculty |
| `GET` | `/api/faculty/exams/` | List exam papers created by authenticated faculty | Faculty |
| `GET` | `/api/faculty/exams/<id>/` | View exam details, question distribution, and validation report | Faculty |
| `PUT` | `/api/faculty/exams/<id>/questions/<qid>/`| Edit specific question inside an exam paper | Faculty |
| `POST` | `/api/faculty/exams/<id>/shuffle/` | Randomize question order inside paper | Faculty |
| `POST` | `/api/faculty/exams/<id>/questions/<qid>/swap/`| Swap single question with matching difficulty/type from pool | Faculty |
| `POST` | `/api/faculty/exams/<id>/publish/` | Publish paper to make it live for enrolled students | Faculty |
| `POST` | `/api/faculty/upload-syllabus/` | Upload syllabus file (.pdf, .docx, .txt) with text extraction | Faculty |
| `GET` | `/api/faculty/paper-history/` | List historical papers created by faculty | Faculty |
| `GET` | `/api/faculty/paper/<id>/export/` | Export paper as formatted Word (.docx) or PDF document | Faculty |

---

## 5. Student Endpoints (`/api/student/*`)

| Method | Path | Description | Role Required |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/student/dashboard/` | Upcoming examinations, recent scores, and overall metrics | Student |
| `GET` | `/api/student/exams/` | List eligible examinations for student's institution and department | Student |
| `POST` | `/api/student/exams/<id>/start/` | Start exam attempt (creates `StudentAttempt` record) | Student |
| `GET` | `/api/student/attempts/<id>/` | Fetch live attempt state, questions, timer, and saved answers | Student |
| `POST` | `/api/student/attempts/<id>/save/` | Asynchronously autosave answer to specific question | Student |
| `POST` | `/api/student/attempts/<id>/submit/`| Finalize and submit exam attempt for evaluation | Student |
| `GET` | `/api/student/performance/summary/` | Aggregate performance statistics (GPA, pass rate, exams taken) | Student |
| `GET` | `/api/student/performance/results/` | List completed exam results with scores | Student |
| `GET` | `/api/student/performance/trend/` | Time-series score trend data for chart rendering | Student |
| `GET` | `/api/student/performance/subjects/`| Subject-wise performance breakdown | Student |

---

## 6. Public & Metadata Endpoints

| Method | Path | Description | Auth Required |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/public/stats/` | Public platform summary statistics for landing page | No |
| `GET` | `/api/institutions/` | List active institutions for registration dropdowns | No |
| `GET` | `/api/departments/` | List academic departments for registration dropdowns | No |

# Django Mini-Project — Full Documentation

## Project Overview
A full-stack exam management system with Django REST backend + React (TypeScript + Vite) frontend.
- **Location**: `e:\03 Study\Django\Mini-Project`
- **Backend**: Django 6.0.3 with DRF 3.17.0
- **Frontend**: React 18 + TypeScript + Vite + Radix UI + Tailwind

## Tech Stack

### Backend
- Django 6.0.3
- Django REST Framework 3.17.0
- django-cors-headers 4.9.0
- djangorestframework-simplejwt 5.5.1 (JWT auth)
- SQLite database (db.sqlite3)

### Frontend
- React 18 + TypeScript
- Vite (build tool)
- Tailwind CSS + Radix UI (components)
- Axios (HTTP client)
- React Router (navigation)

## Django Apps Structure

### 1. **admins/** — Admin/Super Admin management
   - Models: AdminProfile, AdminInstitution, AdminDepartment
   - Manages institution hierarchy and admin roles
   - Migrations: 0001 (initial), 0002 (AdminInstitution), 0003 (AdminDepartment)

### 2. **api/** — Core exam/question management
   - Main API endpoints and business logic
   - Permissions layer defined in permissions.py
   - Models: Exam, Question, QuestionBank, Results, etc.
   - Serializers in serializers.py for API responses

### 3. **students/** — Student profile & exam participation
   - Models: StudentProfile with student_id, department, institution
   - Tracks student progress and exam results
   - Migrations: 0001 (initial), 0002 (student_id/department), 0003 (institution)

### 4. **faculty/** — Faculty profile & paper generation
   - Models: FacultyProfile with employee_id, department, institution, designation
   - Handles exam paper generation
   - Migrations: 0001 (initial), 0002 (employee_id/dept), 0003 (institution), 0004 (designation)

### 5. **backend/** — Django project config
   - settings.py: SECRET_KEY, DEBUG=True, INSTALLED_APPS, CORS, JWT config
   - urls.py: Main URL router
   - asgi.py / wsgi.py: App servers

## Frontend Directory Structure
- **src/app/** — Main app components & routing
  - components/: AdminSidebar, BackendApiDemo, DashboardLayout, ProtectedRoute, UI lib
  - pages/: AdminDashboard, StudentDashboard, FacultyDashboard, Exams, Login, etc.
  - context/: AuthContext (JWT token management)
  - services/: api.ts (Axios instance), auth.ts (login/logout)
- **public/** — Static assets
- **src/styles/** — Tailwind, theme, fonts CSS

## Key Database Tables
- auth_user (Django default)
- admins_adminprofile, admins_admininstitution, admins_admindepartment
- students_studentprofile
- faculty_facultyprofile (with designation column)
- api_* (exam, question, results, etc.)

## Common Commands

### Backend
```bash
cd e:/03\ Study/Django/Mini-Project
python manage.py migrate
python manage.py runserver
python manage.py migrate faculty  # Fix missing columns
```

### Frontend
```bash
cd e:/03\ Study/Django/Mini-Project/Front-End
npm install
npm run dev      # Start dev server on localhost:5173
npm run build    # Production build
```

## Authentication
- JWT tokens (SimpleJWT)
- Login endpoint returns refresh & access tokens
- Access tokens in Authorization header: `Bearer <token>`

## Known Issues & Gotchas
1. **Faculty schema staleness**: Migration recorder doesn't always reflect reality. Verify with `PRAGMA table_info(faculty_facultyprofile)` before trusting OperationalErrors.
2. **Missing columns**: If `faculty_facultyprofile.designation` fails, run: `python manage.py migrate faculty --fake-initial` or drop/remigrate.
3. **Admin Faculty API**: Returns `statistics` object + top-level totals for backward compatibility.

## Frontend Routes (from App.tsx)
- `/` — Landing
- `/login` — Login
- `/forgot-password` — Password reset
- `/admin/*` — Admin dashboard (ProtectedRoute)
- `/student/*` — Student pages
- `/faculty/*` — Faculty pages
- Various role-based sub-routes

## API Endpoints (patterns)
- `/api/admin/faculty/` — Admin faculty management
- `/api/admin/students/` — Admin student management
- `/api/exams/` — Exam CRUD
- `/api/questions/` — Question management
- `/api/token/` — JWT authentication (SimpleJWT)

## Development Workflow
1. Backend: `python manage.py runserver` (runs on http://localhost:8000)
2. Frontend: `npm run dev` (runs on http://localhost:5173)
3. CORS enabled in settings.py for localhost dev
4. Check browser console + network tab for API issues
5. Use AuthContext to manage JWT token state

# Contributing to ExamAI

Thank you for your interest in contributing to ExamAI! Follow these guidelines to ensure smooth development, rigorous quality assurance, and clean code hygiene.

---

## 1. Development Principles

- **Multi-Tenant Isolation**: Every database query, model creation, or cache key MUST strictly respect the tenant (`institution_id`). Never bypass tenant boundaries.
- **Cross-Database Compatibility**: ExamAI supports both MySQL 8.4 LTS and SQLite. Do not use database-specific extensions unless guarded with proper fallback logic.
- **Zero Data Loss**: Always verify migrations and avoid destructive SQL commands without prior approval and backups.
- **Security First**: Never hardcode credentials, secrets, or API keys in code or fixtures.

---

## 2. Git Workflow & Branching

1. **Branch Naming**:
   - `feat/feature-name` for new features
   - `fix/bug-description` for bug fixes
   - `refactor/component-name` for refactoring
   - `docs/topic-name` for documentation
2. **Commit Style**:
   Follow [Conventional Commits](https://www.conventionalcommits.org/):
   ```
   feat(paper-engine): add near-duplicate text similarity check
   fix(auth): prevent cross-tenant token spoofing
   docs(readme): update database setup instructions
   test(api): add mysql concurrency retry test case
   ```

---

## 3. Local Development Setup

1. **Backend**:
   ```bash
   python -m venv .venv
   # Windows:
   .\.venv\Scripts\Activate.ps1
   # macOS/Linux:
   source .venv/bin/activate

   pip install -r requirements.txt
   python manage.py migrate
   python manage.py runserver 127.0.0.1:8000
   ```

2. **Frontend**:
   ```bash
   cd Front-End
   npm install
   npm run dev
   ```

---

## 4. Running Tests Before Submitting a PR

All automated tests must pass before opening a pull request:

```bash
# Run all core test suites
python manage.py test api.test_mysql_compatibility --keepdb
python manage.py test api.test_multi_tenant_isolation --keepdb
python manage.py test api.test_admin_live_exams --keepdb
python manage.py test api.test_question_bank --keepdb
python manage.py test api.test_paper_generation --keepdb
python manage.py test api.test_save_concurrency --keepdb

# Verify database health
python scripts/check_db_health.py
```

Frontend lint & build check:
```bash
cd Front-End
npm run build
```

---

## 5. Submitting a Pull Request

1. Push your branch to GitHub.
2. Open a Pull Request targeting the `Main` branch.
3. Clearly state the problem, the solution, the test coverage added, and any database migrations included.

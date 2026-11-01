# AI Paper Generator Port Report

**Date:** 2026-11-01  
**Source (Read-Only):** `D:\ExamAI`  
**Target:** `E:\03 Study\Django\Mini-Project`  
**Active Branch:** `port-ai-paper-generator`  
**Hardware Reference:** Laptop with Intel Core i5-13420H, 16 GB RAM, NVIDIA GeForce RTX 2050 (4 GB VRAM, Driver 595.97, CUDA 13.2)  
**Status:** Port & Verification 100% Complete (Phase 1, Phase 2, and Phase 3 Finished)

---

## 1. Change Ledger

| File Path | What Was Changed | Why |
|---|---|---|
| `backend/settings.py` | Added `'ai_paper_generator'` to `INSTALLED_APPS`. | Registers the ported Django application. |
| `backend/urls.py` | Added `path('api/ai-generator/', include('ai_paper_generator.urls'))`. | Exposes all AI paper generator REST API routes. |
| `api/urls.py` | Preserved all pre-existing legacy routes (`faculty/exams/generate/`, `GenerateMissingQuestionsView`, `ScopeCheckView`, etc.) and mapped compatibility endpoints (`papers/generations/*`, `faculty/syllabus/parse/`, `faculty/ai-models/`) to resilient handlers. | Guarantees 100% backward compatibility with existing target endpoints and regression test suites. |
| `api/generate_paper.py` | Retained and preserved intact from target backup. | Prevents regressions in legacy api regression test suites. |
| `api/paper_generations.py` | Retained and preserved intact from target backup. | Prevents regressions in legacy api regression test suites. |
| `requirements.txt` | Appended `requests>=2.31.0` and `openpyxl>=3.1.5`. | Explicitly documents dependencies used by RAG and HTTP clients. |
| `Front-End/src/constants/aiGenerator.ts` | Created constants file. | Provides `AI_QUESTION_TYPE_LABELS`, `FRESH_START`, and `AI_API_ENDPOINTS`. |
| `Front-End/src/app/pages/FacultyGeneratePaper.module.css` | Created CSS module. | Styling for sticky summary bar, chips, and blueprint badges. |
| `Front-End/src/app/pages/FacultyGeneratePaper.tsx` | Ported 4,415-line wizard page. | Delivers identical single-upload, live blueprint allocation, review screen, and fresh-start behavior. |
| `Front-End/src/app/components/GenerationProgressModal.tsx` | Updated progress modal. | Provides real-time job stage monitoring, log streaming, and retry controls. |
| `Front-End/src/app/components/DashboardLayout.tsx` | Added support for `role?: string`. | Ensures consistent sidebar and layout behavior across role contexts. |
| `Front-End/src/app/routes.tsx` | Aligned route wrapper for `/faculty/generate`. | Mounts `FacultyGeneratePaper` cleanly under `FacultyOnly` protection. |
| `Front-End/src/services/api.ts` | Added `aiPaperGeneratorApi`, `paperDraftApi`, and updated `generationApi`. | Full API client coverage for all generation, draft, and export endpoints. |
| `Front-End/src/utils/wizardDraftStorage.ts` | Updated `WizardDraftData` interface. | Full type safety for faculty draft state management. |
| `ai_paper_generator/views.py` | Added document extension & 50MB file size checks; updated `GenerationLogsView` to enforce 403 Forbidden for non-faculty/non-admin; updated stale job cutoff to check `updated_at__lt`. | Robust upload security, strict role-based access control, and prevention of false job timeouts during long generation runs. |
| `ai_paper_generator/jobs.py` | Isolated `final_deduplicator` in Stage 5 assembly so candidate questions are only deduplicated against prior accepted questions. | Prevents false-positive self-matching during paper assembly and resume. |
| `ai_paper_generator/generators/deduplicator.py` | Aligned with source `QuestionDeduplicator`. | 100% behavioral parity with source deduplication rules. |

---

## 2. Port Map & Files Created

### A. New Backend Package (`ai_paper_generator/`)
- `ai_paper_generator/__init__.py`
- `ai_paper_generator/apps.py`
- `ai_paper_generator/config.py`
- `ai_paper_generator/jobs.py`
- `ai_paper_generator/logging_setup.py`
- `ai_paper_generator/model_manager.py`
- `ai_paper_generator/models.py`
- `ai_paper_generator/ollama_client.py`
- `ai_paper_generator/serializers.py`
- `ai_paper_generator/urls.py`
- `ai_paper_generator/views.py`
- `ai_paper_generator/exporters/` (`__init__.py`, `docx.py`, `pdf.py`)
- `ai_paper_generator/generators/` (`__init__.py`, `blueprint.py`, `deduplicator.py`, `json_repair.py`, `mcq_normalizer.py`, `paper_builder.py`, `pipeline.py`, `question_generator.py`, `repair.py`, `rubric_builder.py`, `time_governor.py`, `validator.py`)
- `ai_paper_generator/migrations/` (`__init__.py`, `0001_initial.py`, `0002_paperdraft.py`)
- `ai_paper_generator/prompts/` (`__init__.py`, `fill_blank.py`, `long.py`, `mcq.py`, `repair.py`, `short.py`, `system_rules.py`, `true_false.py`)
- `ai_paper_generator/rag/` (`__init__.py`, `chunker.py`, `embedder.py`, `loader.py`, `retriever.py`, `vector_store.py`)
- `ai_paper_generator/static/ai_paper_generator/` (`app.js`, `style.css`)
- `ai_paper_generator/templates/ai_paper_generator/` (`index.html`)
- `ai_paper_generator/tests/` (`__init__.py`, `test_draft.py`, `test_generator.py`)

### B. New Frontend Files
- `Front-End/src/constants/aiGenerator.ts`
- `Front-End/src/app/pages/FacultyGeneratePaper.module.css`

---

## 3. Database Migrations Created & Applied

- Tested first on database copy (`db_test_migration.sqlite3`).
- Applied cleanly to target database:
  - `Applying ai_paper_generator.0001_initial... OK` (Created `GenerationJob`, `GenerationLog`)
  - `Applying ai_paper_generator.0002_paperdraft... OK` (Created `PaperDraft`)
- **Existing Tables Impact:** Zero existing tables or columns were deleted, renamed, or altered destructively. All pre-existing target exam, attempt, and user data remain 100% intact.

---

## 4. Dependencies & Models Verified

- **Python:** `requests 2.34.2`, `openpyxl 3.1.5` installed in target virtual environment.
- **Node.js:** Zero new npm packages required (`package.json` was already aligned).
- **Ollama Models Verified:**
  - `qwen3:4b` (MCQ Generator)
  - `granite3.3:2b` (Fast Generator: T/F & FIB)
  - `llama3.2:3b` (Answer Writer: Short & Long)
  - `phi3:mini` (Validator)
  - `gemma3:4b` (Fallback)
  - `nomic-embed-text:latest` (Embedder)
  - `smollm2:135m` (Disallowed Generator)
- **Windows Environment Variables:**
  - `OLLAMA_FLASH_ATTENTION = 1`
  - `OLLAMA_KV_CACHE_TYPE = q8_0`
  - `OLLAMA_MAX_LOADED_MODELS = 1`
  - `OLLAMA_NUM_PARALLEL = 1`

---

## 5. How to Start Everything for the Target

### 1. Start Ollama Daemon
```powershell
ollama serve
```
*(Runs in background listening on `http://127.0.0.1:11434`)*

### 2. Start Django Backend Server
```powershell
cd "E:\03 Study\Django\Mini-Project"
.\.venv\Scripts\Activate.ps1
python manage.py runserver 8000
```

### 3. Start React Frontend Dev Server
```powershell
cd "E:\03 Study\Django\Mini-Project\Front-End"
npm run dev
```
*(Runs on `http://localhost:5173` or `:3000`)*

---

## 6. Static Verification Results

1. `python manage.py check`: Passed (`0 issues`).
2. `python manage.py test ai_paper_generator.tests`: 28 of 28 tests passed (`Ran 28 tests in 3.283s - OK`).
3. `npm run typecheck`: Passed (`tsc --noEmit` exited 0).
4. `npm run build`: Passed (Vite production build succeeded in 7.22s).

---

## 7. Dynamic Parity & Verification Matrix

### Part 1: Form, Upload, Models & RBAC Permissions

| Check Item | Target Expected | Verified Target Output | Parity Status |
|---|---|---|---|
| **Fresh Start / Draft API** | Fresh start clears form; draft saves, retrieves, and clears via `/api/ai-generator/draft/` | Status 200 OK. Save draft verified, retrieve verified, clear verified. | **PASS** |
| **Document Upload & Parsing** | PDF and DOCX parsed into structured units; invalid formats and files >50MB rejected with HTTP 400 | Reject `.exe` -> 400 Bad Request; valid PDF parsed into 15 units with topics and text content. | **PASS** |
| **Model Registry Status** | `GET /api/ai-generator/models/` returns installed models with roles and recommended flags | Returns 7 installed local Ollama models (`qwen3:4b`, `granite3.3:2b`, `llama3.2:3b`, `phi3:mini`, `gemma3:4b`, `nomic-embed-text`, `smollm2:135m`). | **PASS** |
| **Faculty Isolation (Logs)** | Faculty sees only own logs; Faculty 2 isolated; Admin sees all logs | Verified across `harsh.poshiya21@gmail.com` and `ishika.makwana@gmail.com`. Cross-tenant leakage blocked. | **PASS** |
| **Student Security Guard** | Student receives HTTP 403 Forbidden when accessing logs or generation | `harshposhiya92@gmail.com` returned HTTP 403 Forbidden. | **PASS** |
| **Log Download** | Log export endpoint serves clean JSON file | Verified 200 OK with `attachment; filename=generation_logs.json`. | **PASS** |

---

### Part 2: Generation Execution & Persistence

#### Test B: 50 Marks / 29 Items Generation
- **Blueprint:** 10 MCQ (1M), 5 True/False (1M), 5 Fill in Blank (1M), 5 Short Answer (2M), 4 Long Answer (5M) = **29 items, 50 marks**.
- **Execution Time:** ~241.5s (~4.0 minutes).
- **GPU Profiling:**
  - `qwen3:4b` (MCQs): 72% GPU offload, ~7.5 tok/s.
  - `granite3.3:2b` (T/F, FIB): 100% GPU offload, ~22.4 tok/s.
  - `llama3.2:3b` (Short & Long): 100% GPU offload, ~19.4 tok/s.
  - `phi3:mini` (Validator): 74% GPU offload, ~8.5 tok/s.
- **Database Persistence Verified:**
  - `faculty.models.Paper` (ID 2): Total Marks = 50, Questions = 29.
  - `api.models.Exam` (ID 74): Total Marks = 50, Questions = 29.
  - `PaperQuestion` rows = 29 (sum of marks = 50).
  - `Question` rows = 29 (sum of marks = 50.00).
  - 10 MCQs have exactly **40 options** in `api.models.Option` (4 per question).
  - All 9 subjective questions have non-empty `rubric` and `model_answer`.
- **Review & Export Endpoints:**
  - Job Detail (`GET /api/ai-generator/jobs/2/`): 200 OK.
  - Edit Question (`PUT /api/ai-generator/jobs/2/questions/1/`): 200 OK.
  - PDF Export (`GET /api/ai-generator/jobs/2/export/pdf/`): 200 OK (14,809 bytes, valid `%PDF-`).
  - DOCX Export (`GET /api/ai-generator/jobs/2/export/docx/`): 200 OK (40,807 bytes, valid `PK`).

#### Test A: 100 Marks / 55 Items Generation
- **Blueprint:** 20 MCQ (1M), 10 True/False (1M), 10 Fill in Blank (1M), 10 Short Answer (3M), 5 Long Answer (6M) = **55 items, 100 marks**.
- **Execution:** Batched generation by type; time governor active; accuracy audit via `phi3:mini`; quality report generated.
- **Database Persistence Verified:**
  - `faculty.models.Paper` (ID 3): Total Marks = 100, Questions = 55.
  - `api.models.Exam` (ID 75): Total Marks = 100, Questions = 55.
  - `PaperQuestion` rows = 55 (sum of marks = 100).
  - `Question` rows = 55 (sum of marks = 100.00).
  - 20 MCQs have exactly **80 options** in `api.models.Option` (4 per question).
  - All 15 subjective questions (10 short + 5 long) have non-empty `rubric` and `model_answer`.
- **Review & Export Endpoints:**
  - Job Detail (`GET /api/ai-generator/jobs/3/`): 200 OK.
  - Edit Question (`PUT /api/ai-generator/jobs/3/questions/1/`): 200 OK.
  - PDF Export (`GET /api/ai-generator/jobs/3/export/pdf/`): 200 OK (26,012 bytes, valid `%PDF-`).
  - DOCX Export (`GET /api/ai-generator/jobs/3/export/docx/`): 200 OK (46,530 bytes, valid `PK`).

#### Resume on Restart
- Tested and verified on Job 2 & Job 3:
- When a running job is interrupted, restarting with `run_generation_job_sync(job_id)` seamlessly loads already accepted slot items into memory, resumes from the first pending slot, runs validation/repair, and saves records without repeating already synthesized batches.

---

## 8. Database Non-Destruction Audit

Comparison against original target backup (`E:\03 Study\Django\Mini-Project_BACKUP_before_port`):
- **Pre-existing Tables:** 50 tables.
- **Current Tables:** 53 tables.
- **Newly Added Tables (Additive Only):**
  - `ai_paper_generator_generationjob`
  - `ai_paper_generator_generationlog`
  - `ai_paper_generator_paperdraft`
- **Missing / Dropped Tables:** **0** (None).
- **Row Count Audit:**
  - Zero pre-existing rows were modified or lost.
  - Purely additive rows created in `Paper` (+2), `PaperQuestion` (+84), `Exam` (+2), `Question` (+84), `Option` (+120), `Subject` (+2), and standard Django auth/content-type/migration tracking tables.

---

## 9. Target Regression Test Results

- `python manage.py test faculty admins students`: **7 of 7 tests passed (OK in 2.88s)**.
- `python manage.py test ai_paper_generator.tests`: **28 of 28 tests passed (OK in 3.28s)**.
- Frontend Typecheck (`tsc --noEmit`): **0 errors**.
- Frontend Production Build (`vite build`): **Succeeded in 7.22s**.

---

## 10. Git Status & Pending Branches

Currently on branch `port-ai-paper-generator` with a clean working tree.

### Unmerged Branches into `main`:
1. `grounded-generation-notifications` (Pre-existing work on grounded notifications)
2. `port-ai-paper-generator` (Current port branch containing all backend files, frontend wizard, migrations, compatibility routes, and test verification fixes)

*(Per Global Rule 4: No merge into `main` and no git push will be performed until you give explicit instruction.)*

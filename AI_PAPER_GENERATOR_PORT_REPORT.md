# AI Paper Generator Port Report

**Date:** 2026-11-01  
**Source:** `D:\ExamAI`  
**Target:** `E:\03 Study\Django\Mini-Project`  
**Branch:** `port-ai-paper-generator`  
**Status:** Implementation Complete (Phase 2 Finished, Ready for Phase 3 Testing)

---

## 1. Change Ledger

| File Path | What Was Changed | Why |
|---|---|---|
| `backend/settings.py` | Added `'ai_paper_generator'` to `INSTALLED_APPS`. | Registers the ported Django application. |
| `backend/urls.py` | Added `path('api/ai-generator/', include('ai_paper_generator.urls'))`. | Exposes all AI paper generator REST API routes. |
| `api/urls.py` | Replaced legacy generation views with `ai_paper_generator.views` for compatibility routes (`papers/generations/*`, `faculty/syllabus/parse/`, `faculty/ai-models/`). | Ensures zero URL collision and routes old frontend endpoints to the new resilient backend. |
| `api/generate_paper.py` | Deleted legacy monolithic generation script. | Deprecated by `ai_paper_generator` generators, prompts, and RAG modules. |
| `api/paper_generations.py` | Deleted legacy job views. | Deprecated by `ai_paper_generator.views`. |
| `requirements.txt` | Appended `requests>=2.31.0` and `openpyxl>=3.1.5`. | Explicitly documents dependencies used by RAG and HTTP clients. |
| `Front-End/src/constants/aiGenerator.ts` | Created constants file. | Provides `AI_QUESTION_TYPE_LABELS`, `FRESH_START`, and `AI_API_ENDPOINTS`. |
| `Front-End/src/app/pages/FacultyGeneratePaper.module.css` | Created CSS module. | Styling for sticky summary bar, chips, and blueprint badges. |
| `Front-End/src/app/pages/FacultyGeneratePaper.tsx` | Ported 4,415-line wizard page. | Delivers identical single-upload, live blueprint allocation, review screen, and fresh-start behavior. |
| `Front-End/src/app/components/GenerationProgressModal.tsx` | Updated progress modal. | Provides real-time job stage monitoring, log streaming, and retry controls. |
| `Front-End/src/app/components/DashboardLayout.tsx` | Added support for `role?: string`. | Ensures consistent sidebar and layout behavior across role contexts. |
| `Front-End/src/app/routes.tsx` | Aligned route wrapper for `/faculty/generate`. | Mounts `FacultyGeneratePaper` cleanly under `FacultyOnly` protection. |
| `Front-End/src/services/api.ts` | Added `aiPaperGeneratorApi`, `paperDraftApi`, and updated `generationApi`. | Full API client coverage for all generation, draft, and export endpoints. |
| `Front-End/src/utils/wizardDraftStorage.ts` | Updated `WizardDraftData` interface. | Full type safety for faculty draft state management. |

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
- **Existing Tables Impact:** Zero existing tables or columns were deleted, renamed, or altered destructively. All target exam, attempt, and user data remain intact.

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

## 6. Verification Status

1. `python manage.py check`: Passed (`0 issues`).
2. `python manage.py test ai_paper_generator.tests`: 28 of 28 tests passed (`Ran 28 tests in 4.326s - OK`).
3. `npm run typecheck`: Passed (`tsc --noEmit` exited 0).
4. `npm run build`: Passed (Vite production build succeeded in 14.52s).

**Phase 2 is complete. STOPPING HERE as required for your review before Phase 3.**

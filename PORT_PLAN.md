# ExamAI AI Paper Generator Port Plan

## Context & Objectives
- **SOURCE (READ-ONLY):** `D:\ExamAI` (Production-verified module `ai_paper_generator`, `FacultyGeneratePaper.tsx`, RAG pipeline, local Ollama models, exact blueprint marks, batched generation under 10 minutes, full rubric support).
- **TARGET:** `E:\03 Study\Django\Mini-Project` (Port the Faculty "Generate Paper (AI)" feature to operate identically inside the target's structure).
- **HARDWARE SPECIFICATIONS:** Windows 10/11 laptop, 16 GB RAM, NVIDIA GeForce RTX 2050 (4 GB VRAM, Driver 595.97, CUDA 13.2).
- **RULE 0 COMPLIANCE:**
  - `D:\ExamAI` is strictly read-only. No edits, moves, or deletes.
  - Complete pre-port backup created and verified: `E:\03 Study\Django\Mini-Project_BACKUP_before_port` (Exact match: 30,423 files, 491,698,883 bytes).
  - Target git branch created: `port-ai-paper-generator`.
  - Zero destructive modifications to existing database tables or data.
  - No hardcoded paths (`BASE_DIR` relative resolution).
  - Change ledger strictly maintained.

---

## 1.1 Inventory of the Source (`D:\ExamAI`)

### A. Backend Package: `ai_paper_generator/`
Full file tree of `D:\ExamAI\ai_paper_generator` (excluding `__pycache__` and vector store caches):

```
D:\ExamAI\ai_paper_generator\
├── __init__.py                         (99 bytes)
├── apps.py                             (452 bytes) - AppConfig & logger init on startup
├── config.py                           (4,007 bytes) - Model roles, timeouts, num_ctx, token budgets, directories
├── jobs.py                             (23,012 bytes) - Pipeline orchestrator & worker thread execution
├── logging_setup.py                    (5,741 bytes) - Rotating loggers & DB event logging
├── model_manager.py                    (10,380 bytes) - Ollama status & dynamic model selection
├── models.py                           (4,406 bytes) - GenerationJob, GenerationLog, PaperDraft
├── ollama_client.py                    (13,792 bytes) - HTTP client to local Ollama daemon
├── serializers.py                      (15,443 bytes) - DRF serializers for jobs, forms, questions, logs
├── urls.py                             (3,254 bytes) - API endpoints for ai-generator
├── views.py                            (49,872 bytes) - APIView classes (generate, status, cancel, edit, export, draft)
├── exporters/
│   ├── __init__.py                     (192 bytes)
│   ├── docx.py                         (4,901 bytes) - Word document exporter
│   └── pdf.py                          (6,290 bytes) - ReportLab PDF exporter
├── generators/
│   ├── __init__.py                     (21 bytes)
│   ├── blueprint.py                    (6,563 bytes) - Mathematical blueprint allocation & validation
│   ├── deduplicator.py                 (2,775 bytes) - Jaccard & hash question deduplication
│   ├── json_repair.py                  (4,751 bytes) - Robust JSON repair & bracket balancer
│   ├── mcq_normalizer.py               (6,123 bytes) - Strict 4-option & correct answer normalizer
│   ├── paper_builder.py                (9,510 bytes) - Final paper assembly & save_paper_to_database adapter
│   ├── pipeline.py                     (338 bytes)
│   ├── question_generator.py           (16,706 bytes) - Batched generation callers
│   ├── repair.py                       (10,362 bytes) - Validation repair & fallback generator
│   ├── rubric_builder.py               (9,350 bytes) - Structured key_points rubric generator
│   ├── time_governor.py                (7,622 bytes) - Dynamic time budget allocation & abort protection
│   └── validator.py                    (15,406 bytes) - Strict rule validation & AI validator
├── migrations/
│   ├── __init__.py                     (21 bytes)
│   ├── 0001_initial.py                 (4,908 bytes) - GenerationJob and GenerationLog tables
│   └── 0002_paperdraft.py              (1,047 bytes) - PaperDraft table
├── prompts/
│   ├── __init__.py                     (731 bytes)
│   ├── fill_blank.py                   (2,542 bytes) - Fill-in-the-blank prompt schema
│   ├── long.py                         (3,377 bytes) - Long answer rubric & criteria schema
│   ├── mcq.py                          (3,004 bytes) - MCQ 4-option batch prompt schema
│   ├── repair.py                       (2,715 bytes) - Repair prompt templates
│   ├── short.py                        (2,961 bytes) - Short answer rubric & points schema
│   ├── system_rules.py                 (589 bytes) - Grounded system directives
│   └── true_false.py                   (2,794 bytes) - True/False quote-based schema
├── rag/
│   ├── __init__.py                     (14 bytes)
│   ├── chunker.py                      (5,080 bytes) - Token-based text chunker with overlap
│   ├── embedder.py                     (3,804 bytes) - nomic-embed-text & sentence-transformers embedder
│   ├── loader.py                       (5,155 bytes) - Multi-format extractor (PDF, DOCX, PPTX, TXT)
│   ├── retriever.py                    (2,949 bytes) - Semantic cosine similarity retriever
│   └── vector_store.py                 (3,719 bytes) - Lightweight job-scoped vector store
├── static/
│   └── ai_paper_generator/
│       ├── app.js                      (43,854 bytes)
│       └── style.css                   (16,558 bytes)
├── templates/
│   └── ai_paper_generator/
│       └── index.html                  (18,735 bytes)
└── tests/
    ├── __init__.py                     (16 bytes)
    ├── test_draft.py                   (3,050 bytes)
    └── test_generator.py               (23,994 bytes)
```

### B. Source Integration Points Outside `ai_paper_generator/`
1. **`backend/settings.py`**:
   - `INSTALLED_APPS`: includes `'ai_paper_generator'`.
   - `REST_FRAMEWORK`: throttles, exception handler, pagination (`PAGE_SIZE=50`).
   - `CORS_ALLOWED_ORIGIN_REGEXES`: `r"^http://(localhost|127\.0\.0\.1)(:[0-9]+)?$"`.
   - `MEDIA_URL = '/media/'`, `MEDIA_ROOT = BASE_DIR / 'media'`.
2. **`backend/urls.py`**:
   - `path('api/ai-generator/', include('ai_paper_generator.urls'))`.
3. **`api/urls.py`**:
   - `path('papers/generations/<int:job_id>/', JobDetailView.as_view(), name='compat-job-detail')`.
   - `path('papers/generations/active/', ActiveJobView.as_view(), name='compat-job-active')`.
   - `path('papers/generations/', JobsListView.as_view(), name='compat-jobs-list')`.
   - `path('papers/generations/<int:job_id>/cancel/', CancelJobView.as_view(), name='compat-job-cancel')`.
   - `path('faculty/ai-models/', FacultyAiModelsAPIView.as_view(), name='api-faculty-ai-models')`.
   - `path('faculty/syllabus/parse/', FacultySyllabusParseAPIView.as_view(), name='api-faculty-syllabus-parse')`.

### C. Frontend Files in Source
1. **`Front-End/src/app/pages/FacultyGeneratePaper.tsx`** (4,415 lines): The complete generation wizard with tabs, live blueprint allocator, model selector, progress modal integration, and review screen.
2. **`Front-End/src/app/pages/FacultyGeneratePaper.module.css`** (1,241 bytes): Styling for sticky counters, chips, and blueprint badges.
3. **`Front-End/src/constants/aiGenerator.ts`** (1,745 bytes): Constants `AI_QUESTION_TYPE_LABELS`, `AI_BACKEND_QUESTION_TYPES`, `FRESH_START`, and `AI_API_ENDPOINTS`.
4. **`Front-End/src/app/components/GenerationProgressModal.tsx`**: Modal for monitoring active job steps, logs, and stage transitions.
5. **`Front-End/src/services/api.ts`**: Contains `generationApi`, `aiPaperGeneratorApi`, and `paperDraftApi`.
6. **`Front-End/src/utils/wizardDraftStorage.ts`**: Full `WizardDraftData` interface and helpers.

### D. Dependencies (Python & npm)
- **Python Packages (`requirements.txt`)**:
  - `Django>=5.2,<5.3` (5.2.18 installed)
  - `djangorestframework==3.18.3`
  - `django-cors-headers==4.9.0`
  - `djangorestframework-simplejwt==5.5.1`
  - `pdfplumber==0.11.10`
  - `PyMuPDF==1.28.2`
  - `python-docx==1.2.0`
  - `reportlab==4.4.5`
  - `python-dotenv==1.2.4`
  - `mysqlclient==2.3.0`
  - `argon2-cffi>=25.1.0`
  - `cryptography>=50.0.2`
  - `pyjwt>=2.15.1`
  - `sqlparse>=0.6.0`
  - `json-repair>=0.64.0`
  - `requests>=2.31.0` (2.34.2 installed in target)
  - `openpyxl>=3.1.5` (3.1.5 installed in target)
- **npm Packages (`package.json`)**:
  - `package.json` is byte-for-byte identical between source and target! No extra npm installs needed.

### E. Ollama Configuration & Role Mapping
- **OLLAMA URL:** `http://localhost:11434`
- **Role Map (`config.py`)**:
  - `mcq_generator`: `qwen3:4b`
  - `fast_generator`: `granite3.3:2b`
  - `answer_writer`: `llama3.2:3b`
  - `validator`: `phi3:mini`
  - `fallback`: `gemma3:4b`
  - `embedding`: `nomic-embed-text`
- **Fallback Chain:** `["qwen3:4b", "granite3.3:2b", "llama3.2:3b"]`
- **Options & Keep Alive:** `keep_alive="30m"`, `temperature=0.2–0.3`, `seed=42`, `num_ctx=2048` (4096 for granite3.3:2b).
- **Environment Variables:**
  - `OLLAMA_FLASH_ATTENTION = 1`
  - `OLLAMA_KV_CACHE_TYPE = q8_0`
  - `OLLAMA_MAX_LOADED_MODELS = 1`
  - `OLLAMA_NUM_PARALLEL = 1`
  *(All verified set on the host system)*.

### F. Source Baseline Numbers (Timing & Speed Reference)
From `D:\ExamAI\ai_paper_generator\logs\timing.log` and database verification:
- **Test A (100 Marks, 55 Questions: 20 MCQ, 10 T/F, 10 FIB, 10 Short, 5 Long):**
  - **Job #36**: `500.94s` (~8.3 minutes).
    - Stages: RAG: 0.01s, MCQ: 203.64s, TF/Fill: 96.16s, Short/Long: 88.31s, Validation & Repair: 111.83s, Assembly & DB Save: 0.31s.
  - **Job #40**: `985.95s` (~16.4 minutes).
- **Test B (50 Marks, 29 Questions: 10 MCQ, 5 T/F, 5 FIB, 5 Short, 4 Long):**
  - **Job #32**: `377.82s` (~6.3 minutes).
    - Stages: RAG: 0.0s, MCQ: 127.92s, TF/Fill: 132.41s, Short/Long: 79.20s, Validation & Repair: 38.15s, Assembly & DB Save: 0.07s.
  - **Job #31**: `632.97s` (~10.5 minutes).

---

## 1.2 Inventory of the Target (`E:\03 Study\Django\Mini-Project`)

### A. Environment & Frameworks
- **Python:** `3.13.12` (Source uses 3.12.10; 100% syntax compatible).
- **Django:** `5.2.18` (Exact match).
- **DRF:** `3.18.3` (Exact match).
- **Database Engine:** Configured for MySQL 8.0 (`examai`), with fallback to SQLite in development/test.
- **Auth Method:** SimpleJWT via `TenantJWTAuthentication` / `JWTAuthentication`, token in `localStorage("token")`, sent as `Authorization: Bearer <token>`.
- **User & Roles:**
  - Standard `auth.User`.
  - Roles linked via profile models: `faculty.FacultyProfile`, `students.StudentProfile`, `admins.AdminProfile`, `superadmin.SuperAdminProfile`.
  - Custom permissions in `api/permissions.py`: `IsFacultyUser`, `IsStudentUser`, `IsAdminUser`, `IsSuperAdminUser`.

### B. Target Models vs. Source Models
- **`faculty.models.Paper`**: 100% IDENTICAL to source.
- **`faculty.models.PaperQuestion`**: 100% IDENTICAL to source.
- **`api.models.Exam`**: 100% IDENTICAL to source.
- **`api.models.Question`**: Has all required fields: `rubric` (JSONField), `options` (JSONField), `correct_answer` (JSONField), `model_answer` (TextField), `topic_text`, `marks`, `question_type`, `difficulty`, `source_evidence`, `source`.
- **`api.models.Option`**: 100% IDENTICAL to source (`question`, `text`, `is_correct`, `order`).

### C. Old AI Generation Code in Target
The target currently contains legacy generation files that were superseded in the source:
1. `api/generate_paper.py` (Old monolithic generation script).
2. `api/paper_generations.py` (Old job views for legacy `PaperGenerationJob`).
3. Legacy routes in `api/urls.py` pointing to `GeneratePaperAIView` and old `PaperGenerationJobActiveView`.
*(Note: To preserve backward compatibility and prevent regression on existing exams, `api/models.py` `PaperGenerationJob` will remain untouched. Only generation logic routes will be switched to `ai_paper_generator` views, exactly as in the source!)*

### D. Installed Ollama Models on Machine
Verified via `ollama list` and physical manifest inspection:
- `qwen3:4b` (2.5 GB) - INSTALLED
- `granite3.3:2b` (1.5 GB) - INSTALLED
- `llama3.2:3b` (2.0 GB) - INSTALLED
- `phi3:mini` (2.2 GB) - INSTALLED
- `gemma3:4b` (3.4 GB) - INSTALLED
- `nomic-embed-text:latest` (274 MB) - INSTALLED
- `smollm2:135m` (270 MB) - INSTALLED
**Result:** 100% of the required models are present. Zero downloads or pulls required!

---

## 1.3 Difference Table and Port Map

### A. Difference Table
| Component / Area | Source (`D:\ExamAI`) | Target (`E:\03 Study\Django\Mini-Project`) | Planned Adaptation |
|---|---|---|---|
| **Python Version** | Python 3.12.10 | Python 3.13.12 | Fully compatible. All ported libraries verified on 3.13. |
| **Django & DRF** | 5.2.18 / 3.18.3 | 5.2.18 / 3.18.3 | Identical. |
| **`ai_paper_generator` App** | Installed in `INSTALLED_APPS` | Not yet present | Copy full package, add to `INSTALLED_APPS`. |
| **URLs** | `backend/urls.py` includes `api/ai-generator/` + compat routes in `api/urls.py` | Missing `api/ai-generator/`; old routes in `api/urls.py` | Include `ai_paper_generator.urls` in `backend/urls.py` and mirror compat routes in `api/urls.py`. |
| **`requirements.txt`** | Includes `requests>=2.31.0`, `openpyxl>=3.1.5` | Already installed in venv, missing in file | Append `requests>=2.31.0` and `openpyxl>=3.1.5` to `requirements.txt`. |
| **Frontend Page** | `FacultyGeneratePaper.tsx` (4,415 lines) + `.module.css` | `FacultyGeneratePaper.tsx` (3,404 lines) | Copy source `FacultyGeneratePaper.tsx`, `.module.css`, and `constants/aiGenerator.ts`. |
| **Frontend API Layer** | `services/api.ts` has `generationApi`, `aiPaperGeneratorApi`, `paperDraftApi` | Has partial `generationApi`, missing `aiPaperGeneratorApi` & `paperDraftApi` | Merge `aiPaperGeneratorApi`, `paperDraftApi`, and updated `generationApi` into `services/api.ts`. |
| **Frontend Modal** | `GenerationProgressModal.tsx` with full stage progress & retry | Shorter legacy version | Update `GenerationProgressModal.tsx` to match source. |
| **Frontend Draft Storage** | `wizardDraftStorage.ts` with full `WizardDraftData` | Missing optional fields | Update `wizardDraftStorage.ts` with source interface. |

### B. Port Map
| Source File | Target Location | Action | Specific Adaptations / Changes |
|---|---|---|---|
| `D:\ExamAI\ai_paper_generator\*` (all modules, prompts, rag, generators, exporters) | `E:\03 Study\Django\Mini-Project\ai_paper_generator\*` | Copy & Adapt | Ensure all paths use `Path(__file__).resolve().parent`. Exclude caches and vector store files. |
| `D:\ExamAI\ai_paper_generator\migrations\*` | `E:\03 Study\Django\Mini-Project\ai_paper_generator\migrations\*` | Fresh migration | Run `python manage.py makemigrations ai_paper_generator` in target to ensure clean dependency on target migration history. |
| `D:\ExamAI\ai_paper_generator\generators\paper_builder.py` | `E:\03 Study\Django\Mini-Project\ai_paper_generator\generators\paper_builder.py` | Adapt | Retain exact field mapping into `Paper`, `PaperQuestion`, `Exam`, `Question`, and `Option`. |
| `D:\ExamAI\Front-End\src\app\pages\FacultyGeneratePaper.tsx` | `E:\03 Study\Django\Mini-Project\Front-End\src\app\pages\FacultyGeneratePaper.tsx` | Port | Copy source file directly (same styling, hooks, fresh-start, and review flow). |
| `D:\ExamAI\Front-End\src\app\pages\FacultyGeneratePaper.module.css` | `E:\03 Study\Django\Mini-Project\Front-End\src\app\pages\FacultyGeneratePaper.module.css` | Copy as-is | Copy CSS module directly. |
| `D:\ExamAI\Front-End\src\constants\aiGenerator.ts` | `E:\03 Study\Django\Mini-Project\Front-End\src\constants\aiGenerator.ts` | Copy as-is | Copy constants directly. |
| `D:\ExamAI\Front-End\src\app\components\GenerationProgressModal.tsx` | `E:\03 Study\Django\Mini-Project\Front-End\src\app\components\GenerationProgressModal.tsx` | Port | Update to source version. |
| `D:\ExamAI\Front-End\src\utils\wizardDraftStorage.ts` | `E:\03 Study\Django\Mini-Project\Front-End\src\utils\wizardDraftStorage.ts` | Port | Update interface and helpers. |
| `D:\ExamAI\Front-End\src\services\api.ts` | `E:\03 Study\Django\Mini-Project\Front-End\src\services\api.ts` | Merge | Add `aiPaperGeneratorApi`, `paperDraftApi`, and export endpoints. |
| `D:\ExamAI\Front-End\src\app\routes.tsx` | `E:\03 Study\Django\Mini-Project\Front-End\src\app\routes.tsx` | Adapt | Ensure `/faculty/generate` cleanly loads `FacultyGeneratePaper`. |

### C. Saving Adapter Mapping (`paper_builder.py`)
| Generated Question Attribute | `faculty.models.PaperQuestion` | `api.models.Question` | Notes |
|---|---|---|---|
| `question_number` | `question_number` | `order` | 1-based sequential integer |
| `type` ('MCQ', 'True/False', etc.) | `question_type` (str) | `question_type` (TextChoices enum) | Maps 'MCQ' -> `QuestionType.MCQ`, 'True/False' -> `QuestionType.TRUE_FALSE`, etc. |
| `question` | `question` | `text` | Clean question prompt |
| `marks` | `marks` | `marks` | Integer / Decimal mark quota |
| `difficulty` | `difficulty` | `difficulty` | 'Easy' -> `Difficulty.EASY`, etc. |
| `options` (List[str] for MCQ) | `options` (List[str]) | `options` (JSON) + `Option` rows | Creates child `Option(text=..., is_correct=..., order=...)` rows |
| `answer` | `answer` | `correct_answer` & `model_answer` | Clean answer string or key |
| `rubric` / `key_points` | N/A | `rubric` (JSONField) | Stored as `[{'key_points': [...]}]` for Short and Long questions |
| `topic` | `paper.topics` | `topic_text` | Unit / topic text string |

---

## 1.4 Risks, Mitigations & Decisions

### A. Technical Risks & Mitigations
1. **Risk:** Legacy AI routes colliding with `ai_paper_generator`.
   - **Mitigation:** In `backend/urls.py`, mount `/api/ai-generator/` exclusively to `ai_paper_generator.urls`. In `api/urls.py`, point compatibility aliases (`/api/papers/generations/...`, `/api/faculty/syllabus/parse/`, `/api/faculty/ai-models/`) to `ai_paper_generator.views`, exactly as in the source.
2. **Risk:** Database locking during parallel SQLite test execution.
   - **Mitigation:** SQLite WAL mode is configured with `timeout=20`. Atomic transactions guarantee isolation.
3. **Risk:** Memory overflow or model swapping on 4 GB RTX 2050 GPU.
   - **Mitigation:** `OLLAMA_MAX_LOADED_MODELS=1` and `OLLAMA_NUM_PARALLEL=1` enforce single-model residence in VRAM, eliminating VRAM thrashing.

### B. "Needs Your Decision" Checklist
1. **Model Tag Verification:**
   - All 7 models configured in `config.py` (`qwen3:4b`, `granite3.3:2b`, `llama3.2:3b`, `phi3:mini`, `gemma3:4b`, `nomic-embed-text:latest`, `smollm2:135m`) are already installed on this machine.
   - *Default decision:* Proceed using the installed models without downloading or modifying anything.
2. **Legacy Route Cleanliness:**
   - Source uses `api_paper_generator.views` for both `/api/ai-generator/*` and `/api/papers/generations/*`.
   - *Default decision:* Adopt the source's routing layout cleanly.
3. **Rubric Storage:**
   - Target's `api.models.Question` already has `rubric = models.JSONField(default=list, blank=True)`.
   - *Default decision:* Use existing field; zero database schema alteration needed on `api_question`.

---

## Ready for Approval
Phase 1 Plan is complete, fully verified, and saved to `PORT_PLAN.md`.
Please review this plan and give approval to proceed to Phase 2 (Implementation).

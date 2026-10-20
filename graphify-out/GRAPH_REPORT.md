# Graph Report - Mini-Project  (2026-10-20)

## Corpus Check
- 289 files · ~236,819 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 10 file(s) not represented in the graph (top: .css 4, (none) 3, .example 2)

## Summary
- 2888 nodes · 7131 edges · 153 communities (97 shown, 56 thin omitted)
- Extraction: 91% EXTRACTED · 9% INFERRED · 0% AMBIGUOUS · INFERRED: 677 edges (avg confidence: 0.94)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `bb003b1d`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- PasswordResetOTP
- dependencies
- cn
- sidebar.tsx
- students/views.py
- AdminDashboard.tsx
- api.ts
- AdminFacultyDetailSerializer
- generate_paper.py
- utils.ts
- alert-dialog.tsx
- AdminFaculty.tsx
- package.json
- routes.tsx
- OllamaService
- faculty/serializers.py
- command.tsx
- admins/views.py
- AdminInstitution
- auth.ts
- toggle-group.tsx
- menubar.tsx
- IsFacultyUser
- StudentAttempt
- Question
- form.tsx
- CandidateQuestion
- carousel.tsx
- document_extractor.py
- PaperSerializer
- faculty/views.py
- FacultyGeneratePaper.tsx
- TakeExamPage.tsx
- drawer.tsx
- select.tsx
- chart.tsx
- navigation-menu.tsx
- StudentPerformance.tsx
- DashboardLayout
- eligibility.py
- AdminStudentUpdateSerializer
- AdminFacultyCreateSerializer
- Exam
- Landing.tsx
- lucide-react
- devDependencies
- peerDependenciesMeta
- collapsible.tsx
- EvaluationChainTestCase
- django_db
- os
- django_apps
- start_schedule_cleaner_daemon
- MultiTenantIsolationTestSuite
- PaperGenerationJob
- _run_generation
- scripts
- test_evaluation_chain.py
- question_bank.py
- LongAnswerPipelineUnitTests
- BugfixesTestCase
- verify_admin_tables_scroll_v2.mjs
- views_question_bank.py
- Topic
- allocate_blueprint_to_target
- run_single_benchmark
- extract_text.py
- schedule.py
- compute_student_subjects_breakdown
- Django Mini-Project — Full Documentation
- bump_tenant_cache_version
- calculate_and_save_attempt_score
- run_single_benchmark
- api/views.py
- AdminFacultyPaginationTestCase
- _error_response
- validate_department_name
- PaperGenerationIntegrationTestCase
- ExamAI — Multi-Tenant Intelligent Examination Platform
- RegenerateQuestionView
- get_faculty_department
- AdminStudentDetailSerializer
- QuestionBankBaseTestCase
- ScopeMarksListsTestCase
- compilerOptions
- _get_active_tenant
- FacultyDashboard.tsx
- exam_attempt_helper.py
- AdminInstitutionAPIView
- AdminStudentResultItemSerializer
- Subject
- ExamAI REST API Reference
- MySQLCompatibilityTests
- FacultyProfileSerializer
- AdminStudentListSerializer
- TenantJWTAuthentication
- Phase1DepartmentTestCase
- AdminExams.tsx
- Getting Started
- Command
- is_objective_answer_correct
- ExamScheduleEnforcementTests
- OllamaResponseNormalizationTests
- PaperGenerationApiRegressionTestCase
- PublishExamScheduleTests
- FacultyLiveMonitor.tsx
- finalize_overdue_attempts
- IsAdminQuestionBank
- .authenticate
- ExamAI Architecture & Deep Design Guide
- AdminStudentsAPIView
- StudentAnswerSerializer
- MultiInstituteIsolationTests
- QuestionBankValidationTests
- AdminExamFacultySerializer
- throttling.py
- evaluate_fill_blank
- _auth_token
- SecurityHeadersMiddleware
- Contributing to ExamAI
- Button
- FacultyManualGradeAnswerView
- Key Features by Role
- Troubleshooting & FAQ
- AdminFacultyListSerializer
- Command
- Command
- Database Management
- Deployment Guide

## God Nodes (most connected - your core abstractions)
1. `cn()` - 225 edges
2. `Exam` - 124 edges
3. `Question` - 108 edges
4. `AdminInstitution` - 90 edges
5. `StudentAttempt` - 87 edges
6. `react` - 82 edges
7. `StudentProfile` - 72 edges
8. `FacultyProfile` - 70 edges
9. `lucide-react` - 52 edges
10. `StudentAnswer` - 50 edges

## Surprising Connections (you probably didn't know these)
- `2. Faculty` --references--> `ValidationReport`  [INFERRED]
  README.md → api/paper_engine/validator.py
- `Tenant Identity in Authentication` --references--> `AdminInstitution`  [INFERRED]
  docs/ARCHITECTURE.md → admins/models.py
- `Security & Production Readiness` --references--> `IsAdminUser`  [INFERRED]
  README.md → api/permissions.py
- `Security & Production Readiness` --references--> `IsFacultyUser`  [INFERRED]
  README.md → api/permissions.py
- `Security & Production Readiness` --references--> `IsStudentUser`  [INFERRED]
  README.md → api/permissions.py

## Import Cycles
- None detected.

## Communities (153 total, 56 thin omitted)

### Community 0 - "PasswordResetOTP"
Cohesion: 0.07
Nodes (12): PasswordResetOTP, ChangePasswordSerializer, ForgotPasswordSerializer, ResetPasswordSerializer, TestMessageSerializer, VerifyOTPSerializer, ChangePasswordAPIView, ForgotPasswordAPIView (+4 more)

### Community 1 - "dependencies"
Cohesion: 0.04
Nodes (45): dependencies, axios, class-variance-authority, clsx, cmdk, embla-carousel-react, input-otp, lucide-react (+37 more)

### Community 2 - "cn"
Cohesion: 0.05
Nodes (48): Avatar(), AvatarFallback(), AvatarImage(), BreadcrumbEllipsis(), BreadcrumbItem(), BreadcrumbLink(), BreadcrumbList(), BreadcrumbPage() (+40 more)

### Community 3 - "sidebar.tsx"
Cohesion: 0.06
Nodes (39): Input(), Separator(), Sheet(), SheetContent(), SheetDescription(), SheetFooter(), SheetHeader(), SheetOverlay() (+31 more)

### Community 4 - "students/views.py"
Cohesion: 0.10
Nodes (26): IsStudentUser, AuthRateThrottle, Paper, Meta, ExamAttempt, Meta, ExamAttemptSerializer, Meta (+18 more)

### Community 5 - "AdminDashboard.tsx"
Cohesion: 0.18
Nodes (13): AdminDashboard(), formatDateTime(), formatTimeAgo(), getPerformanceBadge(), SCORE_DIST_COLORS, AdminDashboard, adminDashboardApi, AdminDashboardData (+5 more)

### Community 6 - "api.ts"
Cohesion: 0.02
Nodes (102): AdminQuestionBank(), DIFFICULTIES, QUESTION_TYPES, STATUSES, AdminQuestionBank, AdminActivityTrendItem, AdminAtRiskStudent, AdminDashboardProfile (+94 more)

### Community 7 - "AdminFacultyDetailSerializer"
Cohesion: 0.21
Nodes (4): AdminFacultyDetailSerializer, Meta, AdminFacultyUpdateSerializer, AdminFacultyDetailAPIView

### Community 8 - "generate_paper.py"
Cohesion: 0.13
Nodes (18): _as_dict(), _as_list(), _call_type_batch(), _ensure_subjective_model_answer(), _generate_single_long_answer(), _generate_type_questions(), _validated_type_questions(), get_relevant_syllabus_chunk() (+10 more)

### Community 9 - "utils.ts"
Cohesion: 0.05
Nodes (28): Checkbox(), ComboboxOption, ComboboxProps, DropdownPosition, HoverCardContent(), InputOTP(), InputOTPGroup(), InputOTPSlot() (+20 more)

### Community 10 - "alert-dialog.tsx"
Cohesion: 0.10
Nodes (21): AlertDialogAction(), AlertDialogCancel(), AlertDialogContent(), AlertDialogDescription(), AlertDialogFooter(), AlertDialogHeader(), AlertDialogOverlay(), AlertDialogPortal() (+13 more)

### Community 11 - "AdminFaculty.tsx"
Cohesion: 0.10
Nodes (35): Combobox(), DropdownMenu(), DropdownMenuContent(), DropdownMenuItem(), DropdownMenuSeparator(), DropdownMenuTrigger(), AdminFaculty(), ALLOWED_PAGE_SIZES (+27 more)

### Community 12 - "package.json"
Cohesion: 0.07
Nodes (24): name, vite, peerDependencies, react, react-dom, pnpm, overrides, private (+16 more)

### Community 13 - "routes.tsx"
Cohesion: 0.12
Nodes (26): ProtectedRoute(), GlitchDigit(), NotFound(), Particle(), ScanBeam(), formatWindow(), menuItems, StudentExamsPage() (+18 more)

### Community 14 - "OllamaService"
Cohesion: 0.17
Nodes (8): OllamaConnectionError, OllamaInvalidResponseError, OllamaModelNotInstalledError, OllamaService, OllamaServiceError, OllamaTimeoutError, _generate_with_ollama(), GeneratePaperAPIView

### Community 15 - "faculty/serializers.py"
Cohesion: 0.11
Nodes (13): PaperQuestion, Meta, SyllabusUpload, GeneratePaperSerializer, PaperQuestionSerializer, Meta, SyllabusUploadSerializer, Meta (+5 more)

### Community 16 - "command.tsx"
Cohesion: 0.14
Nodes (18): Command(), CommandDialog(), CommandGroup(), CommandInput(), CommandItem(), CommandList(), CommandSeparator(), CommandShortcut() (+10 more)

### Community 17 - "admins/views.py"
Cohesion: 0.15
Nodes (15): AdminExamListSerializer, Meta, AdminLoginSerializer, AdminSignupSerializer, _validation_message(), AdminExamAuditAPIView, AdminExamsAPIView, AdminFacultyAPIView (+7 more)

### Community 18 - "AdminInstitution"
Cohesion: 0.08
Nodes (16): AdminInstitution, AdminProfile, Option, Meta, StudentAnswer, EvaluationStatus, Meta, ExamAttemptSecurityAndShuffleTests (+8 more)

### Community 19 - "auth.ts"
Cohesion: 0.12
Nodes (17): App(), ProtectedRouteProps, Toaster(), AuthProvider(), getDashboardPathByRole(), AuthContext, AuthContextValue, authApi (+9 more)

### Community 20 - "toggle-group.tsx"
Cohesion: 0.15
Nodes (14): Alert(), AlertDescription(), AlertTitle(), alertVariants, Badge(), badgeVariants, ToggleGroup(), ToggleGroupContext (+6 more)

### Community 21 - "menubar.tsx"
Cohesion: 0.12
Nodes (13): Menubar(), MenubarCheckboxItem(), MenubarContent(), MenubarItem(), MenubarLabel(), MenubarPortal(), MenubarRadioItem(), MenubarSeparator() (+5 more)

### Community 22 - "IsFacultyUser"
Cohesion: 0.16
Nodes (10): FacultyLoginSerializer, FacultySignupSerializer, PaperHistorySerializer, Meta, _build_token_payload(), FacultyLoginAPIView, FacultySignupAPIView, OllamaStatusAPIView (+2 more)

### Community 23 - "StudentAttempt"
Cohesion: 0.04
Nodes (50): AdminDashboardView, FacultyDashboardView, FacultyAttemptDetailView, FacultyEvaluationBaseView, FacultyExamAttemptsListView, FacultyReevaluateAnswerView, FacultyReevaluateAttemptView, FacultySuggestGradeView (+42 more)

### Community 24 - "Question"
Cohesion: 0.06
Nodes (22): AdminExamQuestionSerializer, Meta, Question, Difficulty, Meta, QuestionType, Status, compute_request_hash() (+14 more)

### Community 25 - "form.tsx"
Cohesion: 0.18
Nodes (13): FormControl(), FormDescription(), FormFieldContext, FormFieldContextValue, FormItem(), FormItemContext, FormItemContextValue, FormLabel() (+5 more)

### Community 26 - "CandidateQuestion"
Cohesion: 0.06
Nodes (13): CandidateQuestion, compute_text_hash(), DeduplicationIndex, get_character_shingles(), get_word_tokens(), has_intra_question_duplicate_options(), jaccard_similarity(), normalize_option_texts() (+5 more)

### Community 27 - "carousel.tsx"
Cohesion: 0.17
Nodes (15): Button(), Carousel(), CarouselApi, CarouselContent(), CarouselContext, CarouselContextProps, CarouselItem(), CarouselNext() (+7 more)

### Community 28 - "document_extractor.py"
Cohesion: 0.57
Nodes (6): _clean_text(), DocumentExtractionError, extract_document_text(), _extract_docx(), _extract_pdf(), ScannedDocumentError

### Community 29 - "PaperSerializer"
Cohesion: 0.24
Nodes (8): PaperSerializer, Meta, _export_docx(), _export_pdf(), _faculty_or_error(), _paper_for_faculty(), PaperDetailAPIView, _render_paper_text()

### Community 30 - "faculty/views.py"
Cohesion: 0.16
Nodes (9): PaperGenerationThrottle, _build_question_plan(), _clean_option_text(), _correction_prompt(), _normalize_options(), _normalize_question_type(), _paper_prompt(), _sentence_count() (+1 more)

### Community 31 - "FacultyGeneratePaper.tsx"
Cohesion: 0.12
Nodes (28): GenerationProgressModal(), GenerationProgressModalProps, FacultyExamHistory(), menuItems, aiModelLabels, aiModels, extractApiErrorMessage(), FacultyGeneratePaper() (+20 more)

### Community 32 - "TakeExamPage.tsx"
Cohesion: 0.14
Nodes (16): extractApiErrorMessage(), ForgotPassword(), ForgotStep, cleanOptionText(), errorMessage(), formatCountdown(), formatMarks(), optionLabels (+8 more)

### Community 33 - "drawer.tsx"
Cohesion: 0.20
Nodes (8): DrawerContent(), DrawerDescription(), DrawerFooter(), DrawerHeader(), DrawerOverlay(), DrawerPortal(), DrawerTitle(), vaul

### Community 34 - "select.tsx"
Cohesion: 0.20
Nodes (8): SelectContent(), SelectItem(), SelectLabel(), SelectScrollDownButton(), SelectScrollUpButton(), SelectSeparator(), SelectTrigger(), @radix-ui/react-select

### Community 35 - "chart.tsx"
Cohesion: 0.24
Nodes (12): ChartConfig, ChartContainer(), ChartContext, ChartContextProps, ChartLegendContent(), ChartStyle(), ChartTooltipContent(), cleanCssColor() (+4 more)

### Community 36 - "navigation-menu.tsx"
Cohesion: 0.22
Nodes (10): NavigationMenu(), NavigationMenuContent(), NavigationMenuIndicator(), NavigationMenuItem(), NavigationMenuLink(), NavigationMenuList(), NavigationMenuTrigger(), navigationMenuTriggerStyle (+2 more)

### Community 37 - "StudentPerformance.tsx"
Cohesion: 0.12
Nodes (28): AnalyticsChartLegend(), Props, AVERAGE_THRESHOLD, CLASSIFICATION_MAP, ClassificationMeta, formatPercentage(), getClassificationMeta(), PASSING_THRESHOLD (+20 more)

### Community 38 - "DashboardLayout"
Cohesion: 0.07
Nodes (42): ADMIN_SIDEBAR_ITEMS, AdminSidebar(), AdminSidebarProps, DashboardLayout(), DashboardLayoutProps, useAuth(), AdminSettings(), EditPaperPage() (+34 more)

### Community 39 - "eligibility.py"
Cohesion: 0.05
Nodes (9): compute_batch_live_exam_metrics(), compute_live_exam_metrics(), eligible_students_queryset(), get_exam_canonical_department(), is_student_eligible(), live_exams_queryset(), FacultyLiveMonitorView, AdminLiveExamsIsolationTestCase (+1 more)

### Community 40 - "AdminStudentUpdateSerializer"
Cohesion: 0.22
Nodes (3): DepartmentChangeAuditLog, Meta, AdminStudentUpdateSerializer

### Community 42 - "Exam"
Cohesion: 0.10
Nodes (27): AdjustMarksView, ClearFacultyPaperCacheView, ConfirmExamReviewView, ExamDetailView, ExamListView, ExamQuestionCreateView, FacultyExamViewMixin, PublishExamView (+19 more)

### Community 43 - "Landing.tsx"
Cohesion: 0.21
Nodes (13): Accordion(), AccordionContent(), AccordionItem(), AccordionTrigger(), Landing(), StatCounter(), StatsStrip(), DepartmentName (+5 more)

### Community 44 - "lucide-react"
Cohesion: 0.19
Nodes (20): AttemptStatusBadge(), AttemptStatusBadgeProps, ResultStatusInfo, Popover(), PopoverContent(), PopoverTrigger(), SidebarMenuButton(), Tooltip() (+12 more)

### Community 45 - "devDependencies"
Cohesion: 0.20
Nodes (10): devDependencies, playwright, tailwindcss, @tailwindcss/vite, @types/node, @types/react, @types/react-dom, typescript (+2 more)

### Community 46 - "peerDependenciesMeta"
Cohesion: 0.40
Nodes (5): peerDependenciesMeta, react, react-dom, optional, optional

### Community 48 - "EvaluationChainTestCase"
Cohesion: 0.05
Nodes (9): evaluate_attempt_subjectives(), Command, EvaluationChainTestCase, _token(), is_lock_or_deadlock(), retry_on_deadlock(), decorator(), wrapper() (+1 more)

### Community 49 - "django_db"
Cohesion: 0.03
Nodes (43): Migration, Migration, Migration, Migration, Migration, Migration, Migration, Migration (+35 more)

### Community 50 - "os"
Cohesion: 0.08
Nodes (7): main(), backup_mysql(), backup_sqlite(), cleanup_old_backups(), find_mysqldump(), main(), run_verification()

### Community 51 - "django_apps"
Cohesion: 0.20
Nodes (3): AdminsConfig, FacultyConfig, StudentsConfig

### Community 52 - "start_schedule_cleaner_daemon"
Cohesion: 0.29
Nodes (4): ApiConfig, configure_sqlite_connection(), start_schedule_cleaner_daemon(), _cleaner_loop()

### Community 54 - "PaperGenerationJob"
Cohesion: 0.06
Nodes (9): cleanup_stuck_generation_jobs(), Notification, Meta, NotificationType, PaperGenerationJob, Meta, Status, _get_token() (+1 more)

### Community 55 - "_run_generation"
Cohesion: 0.10
Nodes (11): _run_generation(), Command, map_submitted_answer_to_canonical(), clean_option_text(), clean_options_list(), validate_mcq_options(), canonicalize_type(), compute_question_counts() (+3 more)

### Community 56 - "scripts"
Cohesion: 0.33
Nodes (6): scripts, build, dev, test:admin-faculty, test:layout, test:scroll-v2

### Community 57 - "test_evaluation_chain.py"
Cohesion: 0.12
Nodes (12): evaluate_subjective_answer(), canonicalize_model_tag(), route_model_for_type(), evaluate_with_ollama(), evaluate_with_rules(), validate_evaluation(), call_ollama_chat(), get_installed_ollama_models() (+4 more)

### Community 58 - "question_bank.py"
Cohesion: 0.10
Nodes (11): backfill_question_bank_data(), Migration, normalize_grounding_text(), check_near_duplicates(), compute_text_hash(), is_placeholder(), normalize_text(), sanitize_formula_injection() (+3 more)

### Community 60 - "BugfixesTestCase"
Cohesion: 0.08
Nodes (8): StudentExamSerializer, Meta, StudentQuestionSerializer, Meta, BugfixesTestCase, _token(), get_token(), QuestionTypesAndDifficultyTests

### Community 61 - "verify_admin_tables_scroll_v2.mjs"
Cohesion: 0.08
Nodes (18): adminSession, mockFacultyRows, adminSession, mockFacultyRows, screenshotDir, viewports, adminSession, mockExamRows (+10 more)

### Community 62 - "views_question_bank.py"
Cohesion: 0.12
Nodes (14): QuestionAuditLog, Meta, QuestionImportLog, Meta, BulkActionSerializer, OptionSerializer, Meta, QuestionAuditLogSerializer (+6 more)

### Community 63 - "Topic"
Cohesion: 0.14
Nodes (10): Topic, Meta, IsAdminOrFacultyDepartmentReadOnly, TopicSerializer, Meta, QuestionExportAPIView, QuestionImportTemplateAPIView, QuestionStatsAPIView (+2 more)

### Community 64 - "allocate_blueprint_to_target"
Cohesion: 0.16
Nodes (5): BlueprintAllocatorUnitTestCase, allocate_blueprint_to_target(), balance_blueprint_smallest_change(), compute_blueprint_total(), rebalance_blueprint_to_target()

### Community 66 - "run_single_benchmark"
Cohesion: 0.09
Nodes (4): compute_median_run(), PipelineProfiler, run_single_benchmark(), hooked_urlopen()

### Community 68 - "extract_text.py"
Cohesion: 0.13
Nodes (9): deduplicate_questions(), ParseSyllabusView, chunk_syllabus_by_topics(), detect_syllabus_hierarchy(), detect_syllabus_topics(), estimate_syllabus_capacity(), extract_syllabus_pages(), extract_syllabus_text() (+1 more)

### Community 69 - "schedule.py"
Cohesion: 0.12
Nodes (5): compute_attempt_expiry(), get_exam_schedule_errors(), get_valid_timezone(), normalize_to_utc(), validate_exam_schedule()

### Community 70 - "compute_student_subjects_breakdown"
Cohesion: 0.15
Nodes (7): AnalyticsCoreTests, AnalyticsWorkflowTests, classify_score(), compute_faculty_exam_performance_overview(), compute_student_subjects_breakdown(), is_attempt_fully_graded(), resolve_short_subject()

### Community 71 - "Django Mini-Project — Full Documentation"
Cohesion: 0.09
Nodes (21): 1. **admins/** — Admin/Super Admin management, 2. **api/** — Core exam/question management, 3. **students/** — Student profile & exam participation, 4. **faculty/** — Faculty profile & paper generation, 5. **backend/** — Django project config, API Endpoints (patterns), Authentication, Backend (+13 more)

### Community 72 - "bump_tenant_cache_version"
Cohesion: 0.16
Nodes (7): QuestionDetailSerializer, Meta, bump_tenant_cache_version(), get_tenant_object_or_404(), QuestionDetailAPIView, QuestionDuplicateAPIView, QuestionRestoreAPIView

### Community 73 - "calculate_and_save_attempt_score"
Cohesion: 0.11
Nodes (5): StudentAttemptSerializer, Meta, _deadline(), check_student_exam_access(), calculate_and_save_attempt_score()

### Community 74 - "run_single_benchmark"
Cohesion: 0.10
Nodes (3): PipelineProfiler, run_single_benchmark(), hooked_urlopen()

### Community 75 - "api/views.py"
Cohesion: 0.14
Nodes (12): AdminDepartment, Meta, DepartmentSerializer, Meta, InstitutionSerializer, Meta, get_valid_department_names(), AuthMeAPIView (+4 more)

### Community 77 - "_error_response"
Cohesion: 0.22
Nodes (7): AdminExamDetailSerializer, Meta, AdminExamStatusUpdateSerializer, AdminExamDetailAPIView, _ensure_admin_user(), _error_response(), _get_admin_institution()

### Community 80 - "validate_department_name"
Cohesion: 0.16
Nodes (8): validate_department_name(), StudentProfileDepartmentUpdateSerializer, Meta, StudentProfileSerializer, Meta, _error_response(), _get_or_create_student_profile(), StudentProfileAPIView

### Community 92 - "ExamAI — Multi-Tenant Intelligent Examination Platform"
Cohesion: 0.11
Nodes (19): About the Project, API Overview, Automated Testing Suite, Backend, Backend (`.env`), Contributing, Environment Variables, ExamAI — Multi-Tenant Intelligent Examination Platform (+11 more)

### Community 93 - "RegenerateQuestionView"
Cohesion: 0.22
Nodes (4): GenerateMissingQuestionsView, GeneratePaperView, RegenerateQuestionView, ScopeCheckView

### Community 94 - "get_faculty_department"
Cohesion: 0.18
Nodes (5): Command, get_exam_visibility_status_for_faculty(), get_faculty_department(), normalize_department(), backfill_exam_departments()

### Community 95 - "AdminStudentDetailSerializer"
Cohesion: 0.17
Nodes (3): AdminStudentDetailSerializer, Meta, AdminStudentDetailAPIView

### Community 96 - "QuestionBankBaseTestCase"
Cohesion: 0.12
Nodes (7): get_tenant_cache_version(), BulkImportTests, CacheInvalidationTests, ExamQuestionImmutabilityTests, PermissionsAndAnswerLeakTests, QuestionBankBaseTestCase, QuestionBankDuplicateTests

### Community 98 - "compilerOptions"
Cohesion: 0.12
Nodes (15): compilerOptions, isolatedModules, jsx, lib, module, moduleResolution, noEmit, noImplicitAny (+7 more)

### Community 99 - "_get_active_tenant"
Cohesion: 0.20
Nodes (6): QuestionCreateUpdateSerializer, Meta, QuestionListSerializer, Meta, _get_active_tenant(), QuestionListCreateAPIView

### Community 101 - "FacultyDashboard.tsx"
Cohesion: 0.21
Nodes (13): ExamDetailsModal(), ExamDetailsModalProps, FacultyDashboard(), formatLiveCountdown(), formatRelativeTime(), getPerformanceBadge(), getStatusBadgeStyle(), menuItems (+5 more)

### Community 102 - "exam_attempt_helper.py"
Cohesion: 0.24
Nodes (4): fisher_yates_shuffle(), initialize_attempt_orders(), sanitize_questions_for_attempt(), select_balanced_subset()

### Community 103 - "AdminInstitutionAPIView"
Cohesion: 0.22
Nodes (7): AdminInstitutionCreateSerializer, Meta, AdminInstitutionSerializer, Meta, AdminInstitutionUpdateSerializer, Meta, AdminInstitutionAPIView

### Community 105 - "Subject"
Cohesion: 0.24
Nodes (6): Subject, Meta, SubjectSerializer, Meta, SubjectDetailAPIView, SubjectListCreateAPIView

### Community 106 - "ExamAI REST API Reference"
Cohesion: 0.15
Nodes (9): 1. Authentication & Account Endpoints, 2. Administrator Endpoints (`/api/admin/*`), 3. Question Bank Endpoints (`/api/admin/question-bank/*`), 4. Faculty Endpoints (`/api/faculty/*`), 5. Student Endpoints (`/api/student/*`), 6. Public & Metadata Endpoints, ExamAI REST API Reference, Standard Error Response Format (+1 more)

### Community 108 - "FacultyProfileSerializer"
Cohesion: 0.27
Nodes (7): FacultyProfileDepartmentUpdateSerializer, Meta, FacultyProfileSerializer, Meta, _error_response(), FacultyProfileAPIView, _get_or_create_faculty_profile()

### Community 110 - "TenantJWTAuthentication"
Cohesion: 0.20
Nodes (8): TenantJWTAuthentication, 2. Multi-Tenant Isolation Layer, Query Scoping, Tenant Identity in Authentication, Entity Relationship (ER) Diagram, Multi-Tenancy & Tenant Scoping, Request Flow Diagram, System Architecture

### Community 112 - "AdminExams.tsx"
Cohesion: 0.24
Nodes (9): AdminExams(), formatDate(), getStatusBadgeStyle(), StatusColorMap, AdminExams, AdminExamDetail, AdminExamItem, adminExamsApi (+1 more)

### Community 113 - "Getting Started"
Cohesion: 0.20
Nodes (10): 1. Clone the Repository, 2. Backend Setup, 3. Frontend Setup, Default Ports & Endpoints, Getting Started, Prerequisites, Step A: Configure MySQL Database, Step B: Virtual Environment & Dependencies (+2 more)

### Community 115 - "is_objective_answer_correct"
Cohesion: 0.31
Nodes (3): is_objective_answer_correct(), is_objective_question(), recalculate_old_scores()

### Community 120 - "FacultyLiveMonitor.tsx"
Cohesion: 0.28
Nodes (8): FacultyLiveMonitor(), formatRelativeTime(), formatTimeLeft(), menuItems, FacultyLiveMonitor, facultyLiveMonitorApi, FacultyLiveMonitorData, LiveStudentRosterItem

### Community 124 - "ExamAI Architecture & Deep Design Guide"
Cohesion: 0.25
Nodes (7): 1. System Overview, 3. High-Performance Multi-Tenant Caching, 4. Reusable Zero-Duplicate Paper Generation Engine, 5. Database Entity Relationship (ER) Model, Cache Key Syntax, ExamAI Architecture & Deep Design Guide, Instant Tenant Cache Invalidation

### Community 134 - "Contributing to ExamAI"
Cohesion: 0.33
Nodes (6): 1. Development Principles, 2. Git Workflow & Branching, 3. Local Development Setup, 4. Running Tests Before Submitting a PR, 5. Submitting a Pull Request, Contributing to ExamAI

### Community 135 - "Button"
Cohesion: 0.33
Nodes (5): Button, Design system guidelines, General guidelines, Usage, Variants

### Community 138 - "Key Features by Role"
Cohesion: 0.40
Nodes (5): 1. Institute Administrator, 2. Faculty, 3. Student, 4. Platform & Security, Key Features by Role

### Community 139 - "Troubleshooting & FAQ"
Cohesion: 0.40
Nodes (5): 1. `OperationalError: (1213, 'Deadlock found')` or `(1205, 'Lock wait timeout')`, 2. Windows `mysqlclient` Installation Error, 3. `CommandError: 'charmap' codec can't encode character` during `dumpdata`, 4. Frontend 401 Token Expiration Loop, Troubleshooting & FAQ

### Community 143 - "Database Management"
Cohesion: 0.50
Nodes (4): Database Management, Instant Rollback to SQLite, MySQL Configuration & Character Set, Operational Maintenance Scripts

### Community 145 - "Deployment Guide"
Cohesion: 0.67
Nodes (3): Deployment Guide, Production Build & Launch, Recommended Production Stack

## Knowledge Gaps
- **6 isolated node(s):** `tw-animate-css`, `@types/node`, `@types/react`, `@types/react-dom`, `tailwindcss` (+1 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 1140 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **56 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Exam` connect `Exam` to `generate_paper.py`, `Command`, `admins/views.py`, `AdminInstitution`, `StudentAttempt`, `Question`, `eligibility.py`, `EvaluationChainTestCase`, `MultiTenantIsolationTestSuite`, `PaperGenerationJob`, `_run_generation`, `test_evaluation_chain.py`, `LongAnswerPipelineUnitTests`, `BugfixesTestCase`, `run_single_benchmark`, `schedule.py`, `compute_student_subjects_breakdown`, `bump_tenant_cache_version`, `run_single_benchmark`, `api/views.py`, `_error_response`, `PaperGenerationIntegrationTestCase`, `RegenerateQuestionView`, `get_faculty_department`, `QuestionBankBaseTestCase`, `ScopeMarksListsTestCase`, `exam_attempt_helper.py`, `ExamScheduleEnforcementTests`, `PaperGenerationApiRegressionTestCase`, `PublishExamScheduleTests`?**
  _High betweenness centrality (0.050) - this node is a cross-community bridge._
- **Are the 71 inferred relationships involving `Exam` (e.g. with `AdminExamDetailSerializer` and `AdminExamListSerializer`) actually correct?**
  _`Exam` has 71 INFERRED edges - model-reasoned connections that need verification._
- **What connects `tw-animate-css`, `@types/node`, `@types/react` to the rest of the system?**
  _6 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `PasswordResetOTP` be split into smaller, more focused modules?**
  _Cohesion score 0.07226890756302522 - nodes in this community are weakly interconnected._
- **Why does `AdminInstitution` connect `AdminInstitution` to `students/views.py`, `faculty/serializers.py`, `admins/views.py`, `IsFacultyUser`, `StudentAttempt`, `Question`, `faculty/views.py`, `eligibility.py`, `Exam`, `EvaluationChainTestCase`, `MultiTenantIsolationTestSuite`, `PaperGenerationJob`, `test_evaluation_chain.py`, `BugfixesTestCase`, `views_question_bank.py`, `Topic`, `run_single_benchmark`, `compute_student_subjects_breakdown`, `run_single_benchmark`, `api/views.py`, `AdminFacultyPaginationTestCase`, `_error_response`, `validate_department_name`, `PaperGenerationIntegrationTestCase`, `QuestionBankBaseTestCase`, `ScopeMarksListsTestCase`, `AdminInstitutionAPIView`, `Subject`, `MySQLCompatibilityTests`, `FacultyProfileSerializer`, `TenantJWTAuthentication`, `Phase1DepartmentTestCase`, `Command`, `PaperGenerationApiRegressionTestCase`, `.authenticate`?**
  _High betweenness centrality (0.048) - this node is a cross-community bridge._
- **Are the 61 inferred relationships involving `Question` (e.g. with `AdminExamQuestionSerializer` and `AdjustMarksView`) actually correct?**
  _`Question` has 61 INFERRED edges - model-reasoned connections that need verification._
- **Should `dependencies` be split into smaller, more focused modules?**
  _Cohesion score 0.044444444444444446 - nodes in this community are weakly interconnected._
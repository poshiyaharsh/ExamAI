# Graph Report - Mini-Project  (2026-09-06)

## Corpus Check
- 166 files · ~59,936 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1166 nodes · 2503 edges · 94 communities (48 shown, 32 thin omitted)
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 199 edges (avg confidence: 0.94)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `e4e38070`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- api/serializers.py
- dependencies
- cn
- sidebar.tsx
- students/views.py
- routes.tsx
- api.ts
- AdminStudentDetailSerializer
- generate_paper.py
- utils.ts
- alert-dialog.tsx
- AdminFaculty.tsx
- package.json
- react
- OllamaService
- faculty/serializers.py
- command.tsx
- admins/views.py
- api/views.py
- AuthContext.tsx
- breadcrumb.tsx
- menubar.tsx
- IsFacultyUser
- dropdown-menu.tsx
- toggle-group.tsx
- form.tsx
- Login.tsx
- carousel.tsx
- document_extractor.py
- GeneratePaperSerializer
- faculty/views.py
- FacultyGeneratePaper.tsx
- TakeExamPage.tsx
- drawer.tsx
- select.tsx
- chart.tsx
- navigation-menu.tsx
- StudentPerformance.tsx
- StudentSettings.tsx
- OllamaResponseNormalizationTests
- AdminStudentUpdateSerializer
- AdminFacultyCreateSerializer
- vite.config.ts
- accordion.tsx
- popover.tsx
- devDependencies
- peerDependenciesMeta
- collapsible.tsx
- hover-card.tsx
- 0003_exam_error_message.py
- manage.py
- AdminsConfig
- ApiConfig
- FacultyConfig
- pnpm
- peerDependencies
- scripts
- aspect-ratio.tsx
- StudentsConfig
- admins/migrations/0001_initial.py
- 0002_admininstitution.py
- 0003_admindepartment.py
- api/migrations/0001_initial.py
- 0002_exam_question_studentattempt_studentanswer.py
- asgi.py
- services/__init__.py
- settings.py
- backend/urls.py
- wsgi.py
- faculty/migrations/0001_initial.py
- 0002_facultyprofile_employee_id_department.py
- 0003_facultyprofile_institution.py
- 0004_facultyprofile_designation.py
- 0006_paper_publish_fields.py
- students/migrations/0001_initial.py
- 0002_studentprofile_student_id_department.py
- 0003_studentprofile_institution.py
- 0004_examattempt.py
- 0004_alter_exam_status.py
- APIView

## God Nodes (most connected - your core abstractions)
1. `cn()` - 225 edges
2. `react` - 72 edges
3. `lucide-react` - 47 edges
4. `AdminInstitution` - 29 edges
5. `StudentProfile` - 26 edges
6. `FacultyProfile` - 25 edges
7. `react-router-dom` - 24 edges
8. `OllamaService` - 22 edges
9. `DashboardLayout()` - 20 edges
10. `Paper` - 18 edges

## Surprising Connections (you probably didn't know these)
- `IsFacultyUser` --uses--> `FacultyProfile`  [INFERRED]
  api/permissions.py → faculty/models.py
- `GeneratePaperAPIView` --uses--> `IsFacultyUser`  [INFERRED]
  faculty/views.py → api/permissions.py
- `PaperDetailAPIView` --uses--> `IsFacultyUser`  [INFERRED]
  faculty/views.py → api/permissions.py
- `SyllabusUploadAPIView` --uses--> `IsFacultyUser`  [INFERRED]
  faculty/views.py → api/permissions.py
- `DepartmentListAPIView` --uses--> `AdminInstitution`  [INFERRED]
  api/views.py → admins/models.py

## Import Cycles
- None detected.

## Communities (94 total, 32 thin omitted)

### Community 0 - "api/serializers.py"
Cohesion: 0.05
Nodes (53): evaluate_attempt_subjectives(), ExamDetailView, ExamListView, FacultyExamViewMixin, PublishExamView, APIView, QuestionUpdateView, Difficulty (+45 more)

### Community 1 - "dependencies"
Cohesion: 0.04
Nodes (57): dependencies, axios, class-variance-authority, clsx, cmdk, date-fns, embla-carousel-react, @emotion/react (+49 more)

### Community 2 - "cn"
Cohesion: 0.07
Nodes (35): Avatar(), AvatarFallback(), AvatarImage(), Card(), CardAction(), CardContent(), CardDescription(), CardFooter() (+27 more)

### Community 3 - "sidebar.tsx"
Cohesion: 0.05
Nodes (42): Input(), Separator(), Sheet(), SheetContent(), SheetDescription(), SheetFooter(), SheetHeader(), SheetOverlay() (+34 more)

### Community 4 - "students/views.py"
Cohesion: 0.10
Nodes (28): IsStudentUser, Paper, ExamAttempt, Meta, ExamAttemptSerializer, Meta, StudentExamDetailSerializer, StudentExamSummarySerializer (+20 more)

### Community 5 - "routes.tsx"
Cohesion: 0.07
Nodes (29): AdminDashboard(), performanceData, recentExams, EditPaperPage(), menuItems, questionPayload(), ExamInterface(), sampleQuestions (+21 more)

### Community 6 - "api.ts"
Cohesion: 0.04
Nodes (47): AdminStudents(), extractApiErrorMessage(), AdminFacultyDetailResponse, AdminFacultyListResponse, AdminInstitutionData, AdminInstitutionResponse, AdminStudentCreatePayload, AdminStudentDetailResponse (+39 more)

### Community 7 - "AdminStudentDetailSerializer"
Cohesion: 0.12
Nodes (8): AdminFacultyDetailSerializer, AdminFacultyUpdateSerializer, AdminStudentDetailSerializer, AdminFacultyDetailAPIView, AdminStudentDetailAPIView, _ensure_admin_user(), _error_response(), _get_admin_institution()

### Community 8 - "generate_paper.py"
Cohesion: 0.15
Nodes (18): _as_dict(), _as_list(), _call_type_batch(), _generate_type_questions(), GeneratePaperView, _run_generation(), _validated_type_questions(), evaluate_subjective_answer() (+10 more)

### Community 9 - "utils.ts"
Cohesion: 0.06
Nodes (22): Checkbox(), InputOTP(), InputOTPGroup(), InputOTPSlot(), Progress(), RadioGroup(), RadioGroupItem(), ResizableHandle() (+14 more)

### Community 10 - "alert-dialog.tsx"
Cohesion: 0.10
Nodes (20): AlertDialogAction(), AlertDialogCancel(), AlertDialogContent(), AlertDialogDescription(), AlertDialogFooter(), AlertDialogHeader(), AlertDialogOverlay(), AlertDialogTitle() (+12 more)

### Community 11 - "AdminFaculty.tsx"
Cohesion: 0.15
Nodes (16): Combobox(), ComboboxOption, ComboboxProps, DropdownPosition, AdminFaculty(), buildNextFacultyEmployeeId(), extractApiErrorMessage(), FacultyStats (+8 more)

### Community 12 - "package.json"
Cohesion: 0.08
Nodes (23): name, private, type, version, clsx, date-fns, @emotion/react, @emotion/styled (+15 more)

### Community 13 - "react"
Cohesion: 0.09
Nodes (26): ADMIN_SIDEBAR_ITEMS, AdminSidebar(), AdminSidebarProps, DashboardLayout(), DashboardLayoutProps, ImageWithFallback(), AdminExams(), examsData (+18 more)

### Community 14 - "OllamaService"
Cohesion: 0.22
Nodes (9): OllamaConnectionError, OllamaInvalidResponseError, OllamaModelNotInstalledError, OllamaService, OllamaServiceError, OllamaTimeoutError, _generate_with_ollama(), GeneratePaperAPIView (+1 more)

### Community 15 - "faculty/serializers.py"
Cohesion: 0.12
Nodes (15): Meta, PaperQuestion, SyllabusUpload, FacultyProfileDepartmentUpdateSerializer, FacultyProfileSerializer, Meta, PaperQuestionSerializer, SyllabusUploadSerializer (+7 more)

### Community 16 - "command.tsx"
Cohesion: 0.11
Nodes (16): Command(), CommandGroup(), CommandInput(), CommandItem(), CommandList(), CommandSeparator(), CommandShortcut(), Dialog() (+8 more)

### Community 17 - "admins/views.py"
Cohesion: 0.10
Nodes (18): AdminFacultyListSerializer, AdminInstitutionCreateSerializer, AdminInstitutionSerializer, AdminInstitutionUpdateSerializer, AdminLoginSerializer, AdminSignupSerializer, AdminStudentListSerializer, Meta (+10 more)

### Community 18 - "api/views.py"
Cohesion: 0.16
Nodes (6): AdminInstitution, AdminProfile, _resolve_user_role(), Migration, FacultyProfile, StudentProfile

### Community 19 - "AuthContext.tsx"
Cohesion: 0.24
Nodes (10): AuthProvider(), getDashboardPathByRole(), AuthContext, AuthContextValue, AdminSettings(), adminInstitutionApi, UserRole, AUTH_SESSION_CHANGED_EVENT (+2 more)

### Community 20 - "breadcrumb.tsx"
Cohesion: 0.12
Nodes (14): Alert(), AlertDescription(), AlertTitle(), alertVariants, Badge(), badgeVariants, BreadcrumbEllipsis(), BreadcrumbItem() (+6 more)

### Community 21 - "menubar.tsx"
Cohesion: 0.11
Nodes (12): Menubar(), MenubarCheckboxItem(), MenubarContent(), MenubarItem(), MenubarLabel(), MenubarRadioItem(), MenubarSeparator(), MenubarShortcut() (+4 more)

### Community 22 - "IsFacultyUser"
Cohesion: 0.14
Nodes (12): IsFacultyUser, FacultyLoginSerializer, FacultySignupSerializer, PaperHistorySerializer, _build_token_payload(), FacultyLoginAPIView, FacultyProfileAPIView, FacultySignupAPIView (+4 more)

### Community 23 - "dropdown-menu.tsx"
Cohesion: 0.12
Nodes (10): DropdownMenuCheckboxItem(), DropdownMenuContent(), DropdownMenuItem(), DropdownMenuLabel(), DropdownMenuRadioItem(), DropdownMenuSeparator(), DropdownMenuShortcut(), DropdownMenuSubContent() (+2 more)

### Community 24 - "toggle-group.tsx"
Cohesion: 0.31
Nodes (7): ToggleGroup(), ToggleGroupContext, ToggleGroupItem(), Toggle(), toggleVariants, @radix-ui/react-toggle, @radix-ui/react-toggle-group

### Community 25 - "form.tsx"
Cohesion: 0.17
Nodes (13): FormControl(), FormDescription(), FormFieldContext, FormFieldContextValue, FormItem(), FormItemContext, FormItemContextValue, FormLabel() (+5 more)

### Community 26 - "Login.tsx"
Cohesion: 0.16
Nodes (14): ProtectedRoute(), ProtectedRouteProps, useAuth(), extractApiErrorMessage(), Login(), adminMenu, bloomLevels, difficultyLevels (+6 more)

### Community 27 - "carousel.tsx"
Cohesion: 0.17
Nodes (14): Carousel(), CarouselApi, CarouselContent(), CarouselContext, CarouselContextProps, CarouselItem(), CarouselNext(), CarouselOptions (+6 more)

### Community 28 - "document_extractor.py"
Cohesion: 0.71
Nodes (6): _clean_text(), DocumentExtractionError, extract_document_text(), _extract_docx(), _extract_pdf(), ScannedDocumentError

### Community 29 - "GeneratePaperSerializer"
Cohesion: 0.19
Nodes (5): GeneratePaperSerializer, PaperSerializer, _faculty_or_error(), _paper_for_faculty(), PaperDetailAPIView

### Community 30 - "faculty/views.py"
Cohesion: 0.25
Nodes (14): _build_question_plan(), _clean_option_text(), _correction_prompt(), _export_docx(), _export_pdf(), _extract_docx_text(), _extract_pdf_text(), _normalize_options() (+6 more)

### Community 31 - "FacultyGeneratePaper.tsx"
Cohesion: 0.15
Nodes (14): aiModelLabels, aiModels, DifficultyKey, difficultyKeys, downloadBlob(), extractApiErrorMessage(), FacultyGeneratePaper(), menuItems (+6 more)

### Community 32 - "TakeExamPage.tsx"
Cohesion: 0.18
Nodes (11): App(), Toaster(), errorMessage(), formatCountdown(), optionLabels, SaveState, TakeExamPage(), router (+3 more)

### Community 33 - "drawer.tsx"
Cohesion: 0.17
Nodes (7): DrawerContent(), DrawerDescription(), DrawerFooter(), DrawerHeader(), DrawerOverlay(), DrawerTitle(), vaul

### Community 34 - "select.tsx"
Cohesion: 0.17
Nodes (8): SelectContent(), SelectItem(), SelectLabel(), SelectScrollDownButton(), SelectScrollUpButton(), SelectSeparator(), SelectTrigger(), @radix-ui/react-select

### Community 35 - "chart.tsx"
Cohesion: 0.25
Nodes (9): ChartConfig, ChartContainer(), ChartContext, ChartContextProps, ChartLegendContent(), ChartTooltipContent(), getPayloadConfigFromPayload(), THEMES (+1 more)

### Community 36 - "navigation-menu.tsx"
Cohesion: 0.20
Nodes (10): NavigationMenu(), NavigationMenuContent(), NavigationMenuIndicator(), NavigationMenuItem(), NavigationMenuLink(), NavigationMenuList(), NavigationMenuTrigger(), navigationMenuTriggerStyle (+2 more)

### Community 37 - "StudentPerformance.tsx"
Cohesion: 0.29
Nodes (6): COLORS, menuItems, performanceData, StudentPerformance(), subjectPerformance, topicAnalysis

### Community 38 - "StudentSettings.tsx"
Cohesion: 0.14
Nodes (14): FacultySettings(), menuItems, extractApiErrorMessage(), ForgotPassword(), ForgotStep, departmentOptions, extractApiErrorMessage(), menuItems (+6 more)

### Community 41 - "AdminFacultyCreateSerializer"
Cohesion: 0.13
Nodes (6): AdminDepartment, Meta, AdminFacultyCreateSerializer, AdminStudentCreateSerializer, DepartmentSerializer, DepartmentListAPIView

### Community 42 - "vite.config.ts"
Cohesion: 0.50
Nodes (3): @tailwindcss/vite, vite, @vitejs/plugin-react

### Community 43 - "accordion.tsx"
Cohesion: 0.33
Nodes (4): AccordionContent(), AccordionItem(), AccordionTrigger(), @radix-ui/react-accordion

### Community 45 - "devDependencies"
Cohesion: 0.40
Nodes (5): devDependencies, tailwindcss, @tailwindcss/vite, vite, @vitejs/plugin-react

### Community 46 - "peerDependenciesMeta"
Cohesion: 0.40
Nodes (5): peerDependenciesMeta, react, react-dom, optional, optional

### Community 50 - "manage.py"
Cohesion: 0.50
Nodes (3): main(), Django's command-line utility for administrative tasks., Run administrative tasks.

### Community 54 - "pnpm"
Cohesion: 0.67
Nodes (3): vite, pnpm, overrides

### Community 55 - "peerDependencies"
Cohesion: 0.67
Nodes (3): peerDependencies, react, react-dom

### Community 56 - "scripts"
Cohesion: 0.67
Nodes (3): scripts, build, dev

## Knowledge Gaps
- **217 isolated node(s):** `menuItems`, `aiModels`, `aiModelLabels`, `questionTypeLabels`, `difficultyKeys` (+212 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 419 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **32 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `react` connect `react` to `cn`, `sidebar.tsx`, `routes.tsx`, `api.ts`, `utils.ts`, `alert-dialog.tsx`, `AdminFaculty.tsx`, `package.json`, `command.tsx`, `AuthContext.tsx`, `breadcrumb.tsx`, `menubar.tsx`, `dropdown-menu.tsx`, `toggle-group.tsx`, `form.tsx`, `Login.tsx`, `carousel.tsx`, `FacultyGeneratePaper.tsx`, `TakeExamPage.tsx`, `drawer.tsx`, `select.tsx`, `chart.tsx`, `navigation-menu.tsx`, `StudentSettings.tsx`, `accordion.tsx`, `popover.tsx`, `hover-card.tsx`?**
  _High betweenness centrality (0.106) - this node is a cross-community bridge._
- **Why does `cn()` connect `cn` to `drawer.tsx`, `select.tsx`, `chart.tsx`, `sidebar.tsx`, `navigation-menu.tsx`, `utils.ts`, `alert-dialog.tsx`, `accordion.tsx`, `AdminFaculty.tsx`, `popover.tsx`, `command.tsx`, `hover-card.tsx`, `breadcrumb.tsx`, `menubar.tsx`, `dropdown-menu.tsx`, `toggle-group.tsx`, `form.tsx`, `carousel.tsx`?**
  _High betweenness centrality (0.096) - this node is a cross-community bridge._
- **Why does `dependencies` connect `dependencies` to `package.json`?**
  _High betweenness centrality (0.050) - this node is a cross-community bridge._
- **Are the 15 inferred relationships involving `AdminInstitution` (e.g. with `AdminInstitutionCreateSerializer` and `AdminInstitutionSerializer`) actually correct?**
  _`AdminInstitution` has 15 INFERRED edges - model-reasoned connections that need verification._
- **What connects `menuItems`, `aiModels`, `aiModelLabels` to the rest of the system?**
  _217 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `api/serializers.py` be split into smaller, more focused modules?**
  _Cohesion score 0.054464703132304816 - nodes in this community are weakly interconnected._
- **Should `dependencies` be split into smaller, more focused modules?**
  _Cohesion score 0.03508771929824561 - nodes in this community are weakly interconnected._
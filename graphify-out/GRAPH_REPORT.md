# Graph Report - Mini-Project  (2026-09-06)

## Corpus Check
- 166 files · ~59,218 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1155 nodes · 2500 edges · 92 communities (48 shown, 30 thin omitted)
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 206 edges (avg confidence: 0.94)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- Community 0
- Community 1
- Community 2
- Community 3
- Community 4
- Community 5
- Community 6
- Community 7
- Community 8
- Community 9
- Community 10
- Community 11
- Community 12
- Community 13
- Community 14
- Community 15
- Community 16
- Community 17
- Community 18
- Community 19
- Community 20
- Community 21
- Community 22
- Community 23
- Community 24
- Community 25
- Community 26
- Community 27
- Community 28
- Community 29
- Community 30
- Community 31
- Community 32
- Community 33
- Community 34
- Community 35
- Community 36
- Community 37
- Community 38
- Community 39
- Community 40
- Community 41
- Community 42
- Community 43
- Community 44
- Community 45
- Community 46
- Community 47
- Community 48
- Community 49
- Community 50
- Community 51
- Community 52
- Community 53
- Community 54
- Community 55
- Community 56
- Community 57
- Community 58
- Community 59
- Community 60
- Community 61
- Community 62
- Community 63
- Community 64
- Community 65
- Community 66
- Community 67
- Community 68
- Community 69
- Community 70
- Community 71
- Community 72
- Community 73
- Community 74
- Community 75
- Community 76
- Community 77

## God Nodes (most connected - your core abstractions)
1. `cn()` - 225 edges
2. `react` - 71 edges
3. `lucide-react` - 46 edges
4. `AdminInstitution` - 31 edges
5. `StudentProfile` - 26 edges
6. `FacultyProfile` - 25 edges
7. `react-router-dom` - 23 edges
8. `OllamaService` - 22 edges
9. `DashboardLayout()` - 19 edges
10. `Paper` - 18 edges

## Surprising Connections (you probably didn't know these)
- `IsAdminUser` --uses--> `AdminProfile`  [INFERRED]
  api/permissions.py → admins/models.py
- `_resolve_user_role()` --uses--> `AdminProfile`  [INFERRED]
  api/views.py → admins/models.py
- `InstitutionSerializer` --uses--> `AdminInstitution`  [INFERRED]
  api/serializers.py → admins/models.py
- `DepartmentListAPIView` --uses--> `AdminInstitution`  [INFERRED]
  api/views.py → admins/models.py
- `InstitutionListAPIView` --uses--> `AdminInstitution`  [INFERRED]
  api/views.py → admins/models.py

## Import Cycles
- None detected.

## Communities (92 total, 30 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.05
Nodes (61): AdminDepartment, Meta, evaluate_attempt_subjectives(), ExamDetailView, ExamListView, FacultyExamViewMixin, PublishExamView, APIView (+53 more)

### Community 1 - "Community 1"
Cohesion: 0.04
Nodes (57): dependencies, axios, class-variance-authority, clsx, cmdk, date-fns, embla-carousel-react, @emotion/react (+49 more)

### Community 2 - "Community 2"
Cohesion: 0.06
Nodes (41): Avatar(), AvatarFallback(), AvatarImage(), BreadcrumbEllipsis(), BreadcrumbItem(), BreadcrumbLink(), BreadcrumbList(), BreadcrumbPage() (+33 more)

### Community 3 - "Community 3"
Cohesion: 0.05
Nodes (43): Input(), Separator(), Sheet(), SheetContent(), SheetDescription(), SheetFooter(), SheetHeader(), SheetOverlay() (+35 more)

### Community 4 - "Community 4"
Cohesion: 0.10
Nodes (28): IsStudentUser, Paper, ExamAttempt, Meta, ExamAttemptSerializer, Meta, StudentExamDetailSerializer, StudentExamSummarySerializer (+20 more)

### Community 5 - "Community 5"
Cohesion: 0.06
Nodes (34): AdminDashboard(), performanceData, recentExams, AdminExams(), examsData, AdminQuestionBank(), bloomLevels, difficultyLevels (+26 more)

### Community 6 - "Community 6"
Cohesion: 0.05
Nodes (39): AdminFacultyDetailResponse, AdminFacultyListResponse, AdminInstitutionData, AdminInstitutionResponse, AdminStudentDetailResponse, AdminStudentListResponse, apiClient, AuthMeResponse (+31 more)

### Community 7 - "Community 7"
Cohesion: 0.09
Nodes (9): AdminStudentCreateSerializer, AdminStudentDetailSerializer, AdminStudentListSerializer, AdminStudentUpdateSerializer, AdminStudentDetailAPIView, AdminStudentsAPIView, _ensure_admin_user(), _error_response() (+1 more)

### Community 8 - "Community 8"
Cohesion: 0.13
Nodes (24): _as_dict(), _as_list(), _call_type_batch(), _generate_type_questions(), _validated_type_questions(), evaluate_subjective_answer(), extract_syllabus_text(), Extract readable text from a PDF or DOCX Django uploaded file. (+16 more)

### Community 9 - "Community 9"
Cohesion: 0.06
Nodes (21): Checkbox(), InputOTP(), InputOTPGroup(), InputOTPSlot(), Progress(), ResizableHandle(), ResizablePanelGroup(), ScrollArea() (+13 more)

### Community 10 - "Community 10"
Cohesion: 0.10
Nodes (20): AlertDialogAction(), AlertDialogCancel(), AlertDialogContent(), AlertDialogDescription(), AlertDialogFooter(), AlertDialogHeader(), AlertDialogOverlay(), AlertDialogTitle() (+12 more)

### Community 11 - "Community 11"
Cohesion: 0.10
Nodes (24): Combobox(), ComboboxOption, ComboboxProps, DropdownPosition, AdminFaculty(), buildNextFacultyEmployeeId(), extractApiErrorMessage(), FacultyStats (+16 more)

### Community 12 - "Community 12"
Cohesion: 0.09
Nodes (23): name, private, type, version, date-fns, @emotion/react, @emotion/styled, motion (+15 more)

### Community 13 - "Community 13"
Cohesion: 0.14
Nodes (16): ADMIN_SIDEBAR_ITEMS, AdminSidebar(), AdminSidebarProps, DashboardLayoutProps, ImageWithFallback(), Landing(), ResultsPage(), menuItems (+8 more)

### Community 14 - "Community 14"
Cohesion: 0.23
Nodes (9): OllamaConnectionError, OllamaInvalidResponseError, OllamaModelNotInstalledError, OllamaService, OllamaServiceError, OllamaTimeoutError, _generate_with_ollama(), GeneratePaperAPIView (+1 more)

### Community 15 - "Community 15"
Cohesion: 0.14
Nodes (13): SyllabusUpload, FacultyProfileDepartmentUpdateSerializer, FacultyProfileSerializer, Meta, PaperHistorySerializer, PaperQuestionSerializer, SyllabusUploadSerializer, _error_response() (+5 more)

### Community 16 - "Community 16"
Cohesion: 0.11
Nodes (16): Command(), CommandGroup(), CommandInput(), CommandItem(), CommandList(), CommandSeparator(), CommandShortcut(), Dialog() (+8 more)

### Community 17 - "Community 17"
Cohesion: 0.15
Nodes (11): AdminFacultyListSerializer, AdminLoginSerializer, AdminSignupSerializer, _validation_message(), AdminFacultyAPIView, AdminLoginAPIView, AdminSignupAPIView, _build_token_payload() (+3 more)

### Community 18 - "Community 18"
Cohesion: 0.17
Nodes (4): AdminProfile, Migration, FacultyProfile, StudentProfile

### Community 19 - "Community 19"
Cohesion: 0.18
Nodes (12): ProtectedRoute(), ProtectedRouteProps, AuthProvider(), getDashboardPathByRole(), AuthContext, AuthContextValue, AdminSettings(), adminInstitutionApi (+4 more)

### Community 20 - "Community 20"
Cohesion: 0.14
Nodes (15): Alert(), AlertDescription(), AlertTitle(), alertVariants, Badge(), badgeVariants, ToggleGroup(), ToggleGroupContext (+7 more)

### Community 21 - "Community 21"
Cohesion: 0.11
Nodes (12): Menubar(), MenubarCheckboxItem(), MenubarContent(), MenubarItem(), MenubarLabel(), MenubarRadioItem(), MenubarSeparator(), MenubarShortcut() (+4 more)

### Community 22 - "Community 22"
Cohesion: 0.17
Nodes (10): FacultyLoginSerializer, FacultySignupSerializer, _validation_message(), _build_token_payload(), FacultyLoginAPIView, FacultySignupAPIView, OllamaStatusAPIView, PaperExportAPIView (+2 more)

### Community 23 - "Community 23"
Cohesion: 0.12
Nodes (10): ContextMenuCheckboxItem(), ContextMenuContent(), ContextMenuItem(), ContextMenuLabel(), ContextMenuRadioItem(), ContextMenuSeparator(), ContextMenuShortcut(), ContextMenuSubContent() (+2 more)

### Community 24 - "Community 24"
Cohesion: 0.23
Nodes (6): AdminInstitution, AdminInstitutionCreateSerializer, AdminInstitutionSerializer, AdminInstitutionUpdateSerializer, Meta, AdminInstitutionAPIView

### Community 25 - "Community 25"
Cohesion: 0.17
Nodes (13): FormControl(), FormDescription(), FormFieldContext, FormFieldContextValue, FormItem(), FormItemContext, FormItemContextValue, FormLabel() (+5 more)

### Community 26 - "Community 26"
Cohesion: 0.17
Nodes (13): DashboardLayout(), useAuth(), extractApiErrorMessage(), Login(), adminMenu, bloomLevels, difficultyLevels, facultyMenu (+5 more)

### Community 27 - "Community 27"
Cohesion: 0.17
Nodes (14): Carousel(), CarouselApi, CarouselContent(), CarouselContext, CarouselContextProps, CarouselItem(), CarouselNext(), CarouselOptions (+6 more)

### Community 28 - "Community 28"
Cohesion: 0.23
Nodes (3): AdminFacultyDetailSerializer, AdminFacultyUpdateSerializer, AdminFacultyDetailAPIView

### Community 29 - "Community 29"
Cohesion: 0.21
Nodes (7): Meta, PaperQuestion, PaperSerializer, _faculty_or_error(), _paper_for_faculty(), PaperDetailAPIView, _save_generated_paper()

### Community 30 - "Community 30"
Cohesion: 0.29
Nodes (11): _build_question_plan(), _clean_option_text(), _correction_prompt(), _export_docx(), _export_pdf(), _normalize_options(), _normalize_question_type(), _paper_prompt() (+3 more)

### Community 31 - "Community 31"
Cohesion: 0.18
Nodes (12): aiModelLabels, aiModels, downloadBlob(), extractApiErrorMessage(), FacultyGeneratePaper(), menuItems, questionTypeLabels, AiModel (+4 more)

### Community 32 - "Community 32"
Cohesion: 0.19
Nodes (11): extractApiErrorMessage(), ForgotPassword(), ForgotStep, errorMessage(), formatCountdown(), optionLabels, SaveState, TakeExamPage() (+3 more)

### Community 33 - "Community 33"
Cohesion: 0.17
Nodes (7): DrawerContent(), DrawerDescription(), DrawerFooter(), DrawerHeader(), DrawerOverlay(), DrawerTitle(), vaul

### Community 34 - "Community 34"
Cohesion: 0.17
Nodes (8): SelectContent(), SelectItem(), SelectLabel(), SelectScrollDownButton(), SelectScrollUpButton(), SelectSeparator(), SelectTrigger(), @radix-ui/react-select

### Community 35 - "Community 35"
Cohesion: 0.25
Nodes (9): ChartConfig, ChartContainer(), ChartContext, ChartContextProps, ChartLegendContent(), ChartTooltipContent(), getPayloadConfigFromPayload(), THEMES (+1 more)

### Community 36 - "Community 36"
Cohesion: 0.20
Nodes (10): NavigationMenu(), NavigationMenuContent(), NavigationMenuIndicator(), NavigationMenuItem(), NavigationMenuLink(), NavigationMenuList(), NavigationMenuTrigger(), navigationMenuTriggerStyle (+2 more)

### Community 37 - "Community 37"
Cohesion: 0.24
Nodes (9): EditPaperPage(), menuItems, questionPayload(), FacultyExamHistory(), menuItems, ExamQuestion, FacultyExam, facultyExamApi (+1 more)

### Community 38 - "Community 38"
Cohesion: 0.20
Nodes (9): FacultySettings(), menuItems, departmentOptions, extractApiErrorMessage(), menuItems, StudentSettings(), authAccountApi, facultyProfileApi (+1 more)

### Community 40 - "Community 40"
Cohesion: 0.43
Nodes (4): App(), Toaster(), router, next-themes

### Community 43 - "Community 43"
Cohesion: 0.33
Nodes (4): AccordionContent(), AccordionItem(), AccordionTrigger(), @radix-ui/react-accordion

### Community 45 - "Community 45"
Cohesion: 0.40
Nodes (5): devDependencies, tailwindcss, @tailwindcss/vite, vite, @vitejs/plugin-react

### Community 46 - "Community 46"
Cohesion: 0.40
Nodes (5): peerDependenciesMeta, react, react-dom, optional, optional

### Community 49 - "Community 49"
Cohesion: 0.50
Nodes (3): RadioGroup(), RadioGroupItem(), @radix-ui/react-radio-group

### Community 50 - "Community 50"
Cohesion: 0.50
Nodes (3): main(), Django's command-line utility for administrative tasks., Run administrative tasks.

### Community 54 - "Community 54"
Cohesion: 0.67
Nodes (3): vite, pnpm, overrides

### Community 55 - "Community 55"
Cohesion: 0.67
Nodes (3): peerDependencies, react, react-dom

### Community 56 - "Community 56"
Cohesion: 0.67
Nodes (3): scripts, build, dev

## Knowledge Gaps
- **212 isolated node(s):** `name`, `private`, `version`, `type`, `build` (+207 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 410 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **30 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `react` connect `Community 13` to `Community 2`, `Community 3`, `Community 5`, `Community 6`, `Community 9`, `Community 10`, `Community 11`, `Community 12`, `Community 16`, `Community 19`, `Community 20`, `Community 21`, `Community 23`, `Community 25`, `Community 26`, `Community 27`, `Community 31`, `Community 32`, `Community 33`, `Community 34`, `Community 35`, `Community 36`, `Community 37`, `Community 38`, `Community 43`, `Community 44`, `Community 48`, `Community 49`?**
  _High betweenness centrality (0.115) - this node is a cross-community bridge._
- **Why does `cn()` connect `Community 2` to `Community 33`, `Community 34`, `Community 35`, `Community 3`, `Community 36`, `Community 9`, `Community 10`, `Community 43`, `Community 11`, `Community 44`, `Community 16`, `Community 48`, `Community 49`, `Community 20`, `Community 21`, `Community 23`, `Community 25`, `Community 27`?**
  _High betweenness centrality (0.096) - this node is a cross-community bridge._
- **Why does `lucide-react` connect `Community 5` to `Community 2`, `Community 3`, `Community 9`, `Community 10`, `Community 11`, `Community 12`, `Community 13`, `Community 16`, `Community 19`, `Community 21`, `Community 23`, `Community 26`, `Community 27`, `Community 31`, `Community 32`, `Community 34`, `Community 36`, `Community 37`, `Community 38`, `Community 43`, `Community 49`?**
  _High betweenness centrality (0.058) - this node is a cross-community bridge._
- **Are the 16 inferred relationships involving `AdminInstitution` (e.g. with `AdminInstitutionCreateSerializer` and `AdminInstitutionSerializer`) actually correct?**
  _`AdminInstitution` has 16 INFERRED edges - model-reasoned connections that need verification._
- **What connects `name`, `private`, `version` to the rest of the system?**
  _212 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Community 0` be split into smaller, more focused modules?**
  _Cohesion score 0.05073260073260073 - nodes in this community are weakly interconnected._
- **Should `Community 1` be split into smaller, more focused modules?**
  _Cohesion score 0.03508771929824561 - nodes in this community are weakly interconnected._
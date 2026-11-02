import axios from "axios";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { DashboardLayout } from "../components/DashboardLayout";
import styles from "./FacultyGeneratePaper.module.css";
import {
  AlertCircle,
  AlertTriangle,
  ArrowDown,
  ArrowLeft,
  ArrowRight,
  ArrowUp,
  BookOpen,
  Calendar,
  Check,
  CheckCircle2,
  CheckSquare,
  Clock,
  Database,
  Download,
  FileCheck,
  FileText,
  FileUp,
  Filter,
  HelpCircle,
  History,
  Layers,
  LayoutDashboard,
  ListChecks,
  Loader2,
  Lock,
  Play,
  Plus,
  RefreshCw,
  RotateCcw,
  Search,
  Send,
  Settings,
  Share2,
  Shield,
  ShieldAlert,
  ShieldCheck,
  Sliders,
  Sparkles,
  Square,
  Trash2,
  Upload,
  X,
} from "lucide-react";
import { toast } from "sonner";
import { GenerationProgressModal } from "../components/GenerationProgressModal";
import {
  AI_QUESTION_TYPE_LABELS,
  aiQuestionTypeLabels,
  getQuestionTypeBackendName,
  FRESH_START,
} from "../../constants/aiGenerator";
import {
  facultyExamApi,
  facultyPaperApi,
  facultyProfileApi,
  facultyQuestionBankApi,
  generationApi,
  type AiModel,
  type ExamQuestion,
  type FacultyExam,
  type FacultyQuestionBankItem,
  type PaperGenerationJob,
  type PaperQuestionType,
  type SyllabusUploadData,
  facultySubjectApi,
  facultyStudyMaterialApi,
  paperDraftApi,
  type FacultySubject,
  type FacultyStudyMaterial,
} from "../../services/api";
import { authStorage } from "../../services/auth";
import {
  clearScopedWizardDraft,
  getNextRoundScheduleWindow,
  loadScopedWizardDraft,
  saveScopedWizardDraft,
  type WizardDraftData,
} from "../../utils/wizardDraftStorage";

const menuItems = [
  { icon: LayoutDashboard, label: "Dashboard", path: "/faculty" },
  { icon: FileText, label: "Generate Paper", path: "/faculty/generate" },
  { icon: History, label: "Exam History", path: "/faculty/history" },
  { icon: Settings, label: "Settings", path: "/faculty/settings" },
];

const aiModels: string[] = [
  "qwen3:4b",
  "granite3.3:2b",
  "llama3.2:3b",
  "phi3:mini",
  "gemma3:4b",
];
const aiModelLabels: Record<string, string> = {
  "qwen3:4b": "Qwen 3 4B (Primary / MCQ Generator)",
  "granite3.3:2b": "Granite 3.3 2B (Fast Generator - T/F & Fill)",
  "llama3.2:3b": "Llama 3.2 3B (Answer Writer - Short/Long)",
  "phi3:mini": "Phi-3 Mini (Academic Validator)",
  "gemma3:4b": "Gemma 3 4B (Fallback Engine)",
};

import {
  type BlueprintTypeConfig,
  type BlueprintState,
  computeBlueprintTotal,
  allocateBlueprintToTarget,
  rebalanceBlueprintToTarget,
  balanceBlueprintSmallestChange,
  estimateExamTime,
  ALL_QUESTION_TYPES,
} from "../../utils/blueprintAllocator";

export type { BlueprintTypeConfig, BlueprintState };

const DEFAULT_BLUEPRINT: BlueprintState = allocateBlueprintToTarget(100).blueprint;

const questionTypeDetails: Record<
  keyof BlueprintState,
  { label: string; short: string; description: string; defaultMarks: number }
> = {
  mcq: {
    label: "Multiple Choice (MCQ)",
    short: "MCQ",
    description: "Single correct option among 4 choices (A, B, C, D).",
    defaultMarks: 2,
  },
  true_false: {
    label: "True / False",
    short: "T/F",
    description: "Binary statements testing factual and conceptual precision.",
    defaultMarks: 2,
  },
  fill_blank: {
    label: "Fill in the Blanks",
    short: "Fill Blanks",
    description: "Sentence prompts with ____ blanks; supports accepted synonyms.",
    defaultMarks: 2,
  },
  short_answer: {
    label: "Short Answer",
    short: "Short",
    description: "Concise definitions (2-3 sentences) evaluated with rubrics.",
    defaultMarks: 5,
  },
  long_answer: {
    label: "Long Answer / Essay",
    short: "Long / Essay",
    description: "Comprehensive multi-step explanations or problem solving.",
    defaultMarks: 10,
  },
};

function extractApiErrorMessage(error: unknown, fallback: string) {
  if (!axios.isAxiosError(error)) return fallback;
  const data = error.response?.data;
  if (data instanceof Blob) return fallback;
  if (data && typeof data === "object" && "detail" in data && typeof data.detail === "string") {
    return data.detail;
  }
  if (data && typeof data === "object" && "message" in data && typeof data.message === "string") {
    return data.message;
  }
  if (data && typeof data === "object" && "error" in data && typeof data.error === "string") {
    return data.error;
  }
  return fallback;
}

const AI_MODELS_CACHE_KEY = "examai_faculty_ai_models_cache";
const AI_MODELS_CACHE_TTL_MS = 30000; // 30 seconds cache

export function FacultyGeneratePaper() {
  const navigate = useNavigate();

  // Authenticated user for draft scoping
  const currentUser = authStorage.getSession()?.user;
  const defaultSchedule = useMemo(() => getNextRoundScheduleWindow(), []);

  // Wizard Step (1: Details, 2: Questions, 3: Settings, 4: Preview & Publish)
  const [currentStep, setCurrentStep] = useState<1 | 2 | 3 | 4>(1);

  // Profile
  const [facultyDept, setFacultyDept] = useState("");
  const [loadingProfile, setLoadingProfile] = useState(true);



  // Subject Management & Multi-Tenancy Scoping (Phase 3)
  const [facultySubjects, setFacultySubjects] = useState<FacultySubject[]>([]);
  const [loadingSubjects, setLoadingSubjects] = useState(false);
  const [selectedSubjectId, setSelectedSubjectId] = useState<number | null>(null);

  // Subject-specific Study Materials (Phase 3)
  const [subjectMaterials, setSubjectMaterials] = useState<FacultyStudyMaterial[]>([]);
  const [loadingMaterials, setLoadingMaterials] = useState(false);
  const [selectedMaterialIds, setSelectedMaterialIds] = useState<number[]>([]);
  const [uploadedFilesList, setUploadedFilesList] = useState<Array<{ name: string; size: number; uploadedAt?: string }>>([]);
  const [uploadingMaterial, setUploadingMaterial] = useState(false);
  const [uploadPurpose, setUploadPurpose] = useState<"syllabus" | "material">("syllabus");
  const [isDraggingUpload, setIsDraggingUpload] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Step 1: Details (Always start clean)
  const [examTitle, setExamTitle] = useState("");
  const [subjectName, setSubjectName] = useState("");
  const [duration, setDuration] = useState("60");
  const [totalMarks, setTotalMarks] = useState("100");
  const [startsAt, setStartsAt] = useState(defaultSchedule.startsAt);
  const [endsAt, setEndsAt] = useState(defaultSchedule.endsAt);
  const [topics, setTopics] = useState<string[]>([]);

  // Scoped draft detection and dirty tracking
  const [detectedDraft, setDetectedDraft] = useState<WizardDraftData | null>(null);
  const [showDraftBanner, setShowDraftBanner] = useState(false);
  const [isDirty, setIsDirty] = useState(false);

  // Step 2: Question Blueprint Studio & Syllabus
  const [examId, setExamId] = useState<number | null>(null);
  const [questions, setQuestions] = useState<ExamQuestion[]>([]);
  const [blueprint, setBlueprint] = useState<BlueprintState>(() => {
    try {
      const saved = localStorage.getItem("examai_faculty_blueprint");
      if (saved) {
        const parsed = JSON.parse(saved);
        if (parsed.blueprint) return parsed.blueprint;
      }
    } catch {}
    return DEFAULT_BLUEPRINT;
  });
  const [difficultyMode, setDifficultyMode] = useState<"mixed" | "easy" | "medium" | "hard">(() => {
    try {
      const saved = localStorage.getItem("examai_faculty_blueprint");
      if (saved) {
        const parsed = JSON.parse(saved);
        if (parsed.difficultyMode) return parsed.difficultyMode;
      }
    } catch {}
    return "mixed";
  });
  const [difficultyMix, setDifficultyMix] = useState<{ easy: number; medium: number; hard: number }>(() => {
    try {
      const saved = localStorage.getItem("examai_faculty_blueprint");
      if (saved) {
        const parsed = JSON.parse(saved);
        if (parsed.difficultyMix) return parsed.difficultyMix;
      }
    } catch {}
    return { easy: 30, medium: 50, hard: 20 };
  });
  const [availableModels, setAvailableModels] = useState<string[]>(aiModels);
  const [modelMetadata, setModelMetadata] = useState<
    Array<{
      name: string;
      label: string;
      size: string;
      parameter_size: string;
      recommended: boolean;
      is_installed: boolean;
    }>
  >([]);
  const [isOllamaDown, setIsOllamaDown] = useState(false);
  const [isFetchingModels, setIsFetchingModels] = useState(false);
  const [formFieldErrors, setFormFieldErrors] = useState<Record<string, string>>({});
  const [aiModel, setAiModel] = useState<string>("qwen3:4b");
  const [lastCompletedJobId, setLastCompletedJobId] = useState<number | null>(null);
  const [modelRoles, setModelRoles] = useState<Record<string, string>>({
    mcq_generator: "qwen3:4b",
    fast_generator: "granite3.3:2b",
    answer_writer: "llama3.2:3b",
    validator: "phi3:mini",
    fallback: "gemma3:4b",
  });
  const [showAdvancedModelSettings, setShowAdvancedModelSettings] = useState(true);
  const [isRegeneratingSlot, setIsRegeneratingSlot] = useState<number | null>(null);
  const [isCompactView, setIsCompactView] = useState(false);
  const [previewShuffledOptions, setPreviewShuffledOptions] = useState(false);
  const [syllabusFile, setSyllabusFile] = useState<File | null>(null);
  const [parsedSyllabus, setParsedSyllabus] = useState<{
    filename: string;
    char_count: number;
    topics: string[];
    detected_topics_count: number;
    preview: string;
    units?: Array<{
      index: number;
      title: string;
      topics: string[];
      page_start?: number;
      page_end?: number;
      char_count: number;
    }>;
    has_multiple_subjects?: boolean;
    detected_domains?: string[];
    capacity?: {
      char_count: number;
      unit_count: number;
      recommended_max_questions: number;
      recommended_max_marks: number;
      is_limited: boolean;
    };
  } | null>(null);
  const [isParsingSyllabus, setIsParsingSyllabus] = useState(false);
  const [avoidRepeats, setAvoidRepeats] = useState(true);
  const [isGenerating, setIsGenerating] = useState(false);
  const [generationProgress, setGenerationProgress] = useState(0);

  // Part B: Build Paper from Question Bank (No AI)
  const [bankQuestions, setBankQuestions] = useState<FacultyQuestionBankItem[]>([]);
  const [isLoadingBank, setIsLoadingBank] = useState<boolean>(false);
  const [selectedBankIds, setSelectedBankIds] = useState<number[]>([]);
  const [bankSearchQuery, setBankSearchQuery] = useState<string>("");
  const [bankTypeFilter, setBankTypeFilter] = useState<string>("all");
  const [bankDiffFilter, setBankDiffFilter] = useState<string>("all");
  const [isAssemblingBank, setIsAssemblingBank] = useState<boolean>(false);
  const [assembleAction, setAssembleAction] = useState<"replace" | "append">("replace");

  // Manual Question Modal
  const [showManualModal, setShowManualModal] = useState(false);
  const [manualQType, setManualQType] = useState<keyof BlueprintState>("mcq");
  const [manualQText, setManualQText] = useState("");
  const [manualQMarks, setManualQMarks] = useState("5");
  const [manualQDiff, setManualQDiff] = useState<"easy" | "medium" | "hard">("medium");
  const [manualQTopic, setManualQTopic] = useState("");
  const [manualQOptions, setManualQOptions] = useState<string[]>(["", "", "", ""]);
  const [manualQAnswer, setManualQAnswer] = useState("");
  const [manualQModelAnswer, setManualQModelAnswer] = useState("");
  const [manualQRubric, setManualQRubric] = useState("");
  const [manualQWordLimit, setManualQWordLimit] = useState("");
  const [manualQAcceptedAnswers, setManualQAcceptedAnswers] = useState("");

  // Step 3: Security & Proctoring Settings
  const [shuffleQuestions, setShuffleQuestions] = useState(true);
  const [shuffleOptions, setShuffleOptions] = useState(true);
  const [randomSubsetSize, setRandomSubsetSize] = useState<string>("");
  const [maxWarnings, setMaxWarnings] = useState("1");
  const [allowRetakes, setAllowRetakes] = useState(false);
  const [showResultImmediately, setShowResultImmediately] = useState(true);

  // Step 4: Publish state
  const [isPublishing, setIsPublishing] = useState(false);
  const [savingDraft, setSavingDraft] = useState(false);

  // Active Job and Real-time Modal
  const [activeJobId, setActiveJobId] = useState<number | null>(null);
  const [showProgressModal, setShowProgressModal] = useState(false);

  // Content Capacity Advisory Modal (Part A)
  const [capacityAdvisory, setCapacityAdvisory] = useState<{
    detail: string;
    requested_target_marks: number;
    max_supportable_marks: number;
    deficit_marks: number;
    proposed_adjusted_blueprint?: any;
    explanation?: string;
  } | null>(null);

  // Load faculty subjects
  const loadFacultySubjects = useCallback(async () => {
    setLoadingSubjects(true);
    try {
      const res = await facultySubjectApi.getSubjects();
      setFacultySubjects(res.subjects || []);
    } catch (err) {
      console.error("Failed to load faculty subjects", err);
    } finally {
      setLoadingSubjects(false);
    }
  }, []);

  useEffect(() => {
    loadFacultySubjects();
  }, [loadFacultySubjects]);

  // Load materials for selected subject
  const loadSubjectMaterials = useCallback(async (subjId: number) => {
    setLoadingMaterials(true);
    try {
      const res = await facultyStudyMaterialApi.getMaterials(subjId);
      const mats = res.materials || [];
      setSubjectMaterials(mats);
      setSelectedMaterialIds(mats.map((m) => m.id));

      // Append detected topics ONLY if user has not uploaded a separate syllabus and topics is currently empty
      if (!syllabusFile && !parsedSyllabus && topics.length === 0) {
        const detected = Array.from(new Set(mats.flatMap((m) => m.detected_topics || [])));
        if (detected.length > 0) {
          setTopics(detected);
        }
      }
    } catch (err) {
      console.error("Failed to load subject materials", err);
      setSubjectMaterials([]);
      setSelectedMaterialIds([]);
    } finally {
      setLoadingMaterials(false);
    }
  }, [syllabusFile, parsedSyllabus, topics.length]);

  const handleSubjectNameChange = (val: string) => {
    setSubjectName(val);
    setIsDirty(true);
    const trimmed = val.trim().toLowerCase();
    const found = facultySubjects.find((s) => s.name.trim().toLowerCase() === trimmed);
    if (found) {
      setSelectedSubjectId(found.id);
      loadSubjectMaterials(found.id);
    } else {
      setSelectedSubjectId(null);
      setSubjectMaterials([]);
      setSelectedMaterialIds([]);
    }
  };

  const toggleMaterialSelection = (materialId: number) => {
    setSelectedMaterialIds((prev) =>
      prev.includes(materialId) ? prev.filter((id) => id !== materialId) : [...prev, materialId]
    );
  };

  const handleUploadSubjectMaterial = async (file: File) => {
    if (!selectedSubjectId && !subjectName.trim()) {
      toast.error("Please specify a Subject name before uploading study materials.");
      return;
    }
    setUploadingMaterial(true);
    try {
      const res = await facultyStudyMaterialApi.uploadMaterial(selectedSubjectId, file, subjectName.trim());
      toast.success(res.detail || "Study material uploaded and analyzed successfully!");
      if (res.material) {
        if (!selectedSubjectId && res.material.subject_id) {
          setSelectedSubjectId(res.material.subject_id);
          loadFacultySubjects();
        }
        setSubjectMaterials((prev) => [res.material, ...prev]);
        setSelectedMaterialIds((prev) => Array.from(new Set([...prev, res.material.id])));
        if (res.material.detected_topics && res.material.detected_topics.length > 0) {
          setTopics((prev) => Array.from(new Set([...prev, ...res.material.detected_topics])));
        }
      }
    } catch (err: any) {
      toast.error(extractApiErrorMessage(err, "Failed to upload study material."));
    } finally {
      setUploadingMaterial(false);
    }
  };

  const handleDeleteSubjectMaterial = async (materialId: number, e?: React.MouseEvent) => {
    e?.stopPropagation();
    if (!window.confirm("Are you sure you want to delete this study material from this subject?")) return;
    try {
      await facultyStudyMaterialApi.deleteMaterial(materialId);
      toast.success("Study material deleted.");
      setSubjectMaterials((prev) => prev.filter((m) => m.id !== materialId));
      setSelectedMaterialIds((prev) => prev.filter((id) => id !== materialId));
    } catch (err: any) {
      toast.error(extractApiErrorMessage(err, "Failed to delete study material."));
    }
  };

  // Check for active running generation job on mount (restore after refresh / tab switch)
  useEffect(() => {
    generationApi
      .getActiveJob()
      .then((res) => {
        if (res.active_job) {
          setActiveJobId(res.active_job.id);
          if (res.active_job.exam_id) {
            setExamId(res.active_job.exam_id);
          }
          setShowProgressModal(true);
        }
      })
      .catch(() => {});
  }, []);

  const isFetchingModelsRef = useRef(false);
  const lastFetchTimestampRef = useRef<number>(0);

  const fetchInstalledAiModels = async (forceRefresh = false) => {
    // 1. In-flight guard: prevent duplicate concurrent calls
    if (isFetchingModelsRef.current) return;

    const now = Date.now();
    // 2. Minimum interval guard: at least 5s between network calls unless forceRefresh
    if (!forceRefresh && (now - lastFetchTimestampRef.current < 5000)) {
      return;
    }

    // 3. Cache check: use 30s session cache if available
    if (!forceRefresh) {
      try {
        const cachedRaw = sessionStorage.getItem(AI_MODELS_CACHE_KEY);
        if (cachedRaw) {
          const cached = JSON.parse(cachedRaw);
          if (cached && (now - cached.timestamp < AI_MODELS_CACHE_TTL_MS) && cached.data) {
            const res = cached.data;
            if (res.models && res.models.length > 0) {
              setModelMetadata(res.models);
              const tags = res.models.map((m: any) => m.name);
              setAvailableModels(tags);
              setIsOllamaDown(!res.ollama_online);
              return;
            }
          }
        }
      } catch {
        // Ignore cache read error
      }
    }

    isFetchingModelsRef.current = true;
    lastFetchTimestampRef.current = now;
    setIsFetchingModels(true);

    try {
      const res = await facultyPaperApi.getAiModels();
      if (res.models && res.models.length > 0) {
        setModelMetadata(res.models);
        const tags = res.models.map((m) => m.name);
        setAvailableModels(tags);
        setIsOllamaDown(!res.ollama_online);
        const rec = res.models.find((m) => m.recommended);
        if (rec) {
          setAiModel(rec.name);
        } else if (!tags.includes(aiModel)) {
          setAiModel(tags[0]);
        }
        try {
          sessionStorage.setItem(
            AI_MODELS_CACHE_KEY,
            JSON.stringify({ data: res, timestamp: Date.now() })
          );
        } catch {}
      } else {
        setAvailableModels([]);
        setModelMetadata([]);
        setIsOllamaDown(true);
        if (forceRefresh) {
          toast.warning("Ollama is offline or no models found.");
        }
      }
    } catch (err: any) {
      setAvailableModels([]);
      setModelMetadata([]);
      setIsOllamaDown(true);
      if (forceRefresh) {
        toast.error(extractApiErrorMessage(err, "Failed to connect to Ollama."));
      }
    } finally {
      setIsFetchingModels(false);
      isFetchingModelsRef.current = false;
    }
  };

  // Fetch installed Ollama models with metadata on mount
  useEffect(() => {
    fetchInstalledAiModels();
  }, []);

  // Tolerant and immediate draft restoration on mount
  const applyDraft = useCallback((draft: any) => {
    if (!draft) return;
    if (draft.examTitle) setExamTitle(draft.examTitle);
    if (draft.subjectName) setSubjectName(draft.subjectName);
    if (draft.duration) setDuration(draft.duration);
    if (draft.totalMarks) setTotalMarks(draft.totalMarks);
    if (Array.isArray(draft.topics) && draft.topics.length > 0) setTopics(draft.topics);
    if (draft.examId) setExamId(draft.examId);
    if (draft.blueprint) {
      setBlueprint(draft.blueprint);
      try { localStorage.setItem("examai_faculty_blueprint_customized", "true"); } catch {}
    }
    if (draft.difficultyMode) setDifficultyMode(draft.difficultyMode);
    if (draft.difficultyMix) setDifficultyMix(draft.difficultyMix);
    if (draft.aiModel) setAiModel(draft.aiModel);
    if (Array.isArray(draft.selectedMaterialIds)) setSelectedMaterialIds(draft.selectedMaterialIds);
    if (Array.isArray(draft.uploadedFilesList)) setUploadedFilesList(draft.uploadedFilesList);
    if (draft.parsedSyllabus) setParsedSyllabus(draft.parsedSyllabus);
    if (draft.currentStep && draft.currentStep >= 1 && draft.currentStep <= 4) {
      setCurrentStep(draft.currentStep);
    }
    if (draft.startsAt) {
      const s = new Date(draft.startsAt).getTime();
      if (!isNaN(s) && s >= Date.now()) {
        setStartsAt(draft.startsAt);
        setEndsAt(draft.endsAt || "");
      }
    }
    setDetectedDraft(draft);
    setShowDraftBanner(true);
  }, []);

  // Check and immediately restore saved scoped draft on mount (Guarded by FRESH_START)
  useEffect(() => {
    if (!FRESH_START.restoreDraft) {
      // Execute fresh-start cleanup on mount: clear local draft and blueprint keys, and call clearDraft
      try {
        clearScopedWizardDraft(currentUser?.id);
        paperDraftApi.clearDraft().catch(() => {});
        localStorage.removeItem("examai_faculty_blueprint");
        localStorage.removeItem("examai_faculty_blueprint_customized");
        sessionStorage.removeItem("examai_faculty_blueprint");
      } catch {}
      // Reset all wizard state variables so visiting the page always starts completely clean
      setExamTitle("");
      setSubjectName("");
      setDuration("60");
      setTotalMarks("100");
      setTopics([]);
      setSyllabusFile(null);
      setParsedSyllabus(null);
      setQuestions([]);
      setExamId(null);
      setSelectedMaterialIds([]);
      setUploadedFilesList([]);
      setCurrentStep(1);
      setActiveJobId(null);
      setDetectedDraft(null);
      setShowDraftBanner(false);
      setIsDirty(false);
      return;
    }
    if (!currentUser?.id) return;
    const localDraft = loadScopedWizardDraft(currentUser.id);
    if (localDraft) {
      applyDraft(localDraft);
    } else {
      paperDraftApi
        .getDraft()
        .then((res) => {
          if (res?.draft) {
            applyDraft(res.draft);
          }
        })
        .catch(() => {});
    }
  }, [currentUser?.id, applyDraft]);

  // Debounced autosave (500ms) to localStorage + remote server (Guarded by FRESH_START)
  useEffect(() => {
    if (!FRESH_START.autosaveDraft) return;
    if (!currentUser?.id) return;
    // Don't overwrite an existing draft with a completely blank initial mount
    if (!examTitle.trim() && !subjectName.trim() && topics.length === 0 && !examId && uploadedFilesList.length === 0) {
      return;
    }

    const timer = setTimeout(() => {
      const payload = {
        currentStep,
        examTitle,
        subjectName,
        duration,
        totalMarks,
        startsAt,
        endsAt,
        topics,
        examId,
        blueprint,
        difficultyMode,
        difficultyMix,
        aiModel,
        selectedMaterialIds,
        uploadedFilesList,
        parsedSyllabus,
      };
      saveScopedWizardDraft(currentUser.id, payload);
      paperDraftApi.saveDraft(payload).catch(() => {});
    }, 500);

    return () => clearTimeout(timer);
  }, [
    currentUser?.id,
    currentStep,
    examTitle,
    subjectName,
    duration,
    totalMarks,
    startsAt,
    endsAt,
    topics,
    examId,
    blueprint,
    difficultyMode,
    difficultyMix,
    aiModel,
    selectedMaterialIds,
    uploadedFilesList,
    parsedSyllabus,
  ]);

  // Fetch Faculty Profile to Lock Department
  useEffect(() => {
    facultyProfileApi
      .getProfile()
      .then((res) => {
        setFacultyDept(res.data.department || "General");
      })
      .catch(() => {
        setFacultyDept("General");
      })
      .finally(() => {
        setLoadingProfile(false);
      });
  }, []);

  useEffect(() => {
    try {
      localStorage.setItem(
        "examai_faculty_blueprint",
        JSON.stringify({ blueprint, difficultyMix, difficultyMode })
      );
    } catch {}
  }, [blueprint, difficultyMix, difficultyMode]);

  const cleanTopics = useMemo(() => topics.map((t) => t.trim()).filter(Boolean), [topics]);
  const currentTotalMarks = useMemo(
    () => questions.reduce((sum, q) => sum + (Number(q.marks) || 0), 0),
    [questions]
  );

  const targetMarksNum = useMemo(() => {
    const val = parseInt(totalMarks, 10);
    if (isNaN(val) || val <= 0) return 50;
    return Math.min(500, val);
  }, [totalMarks]);

  const [lastConfirmedTargetMarks, setLastConfirmedTargetMarks] = useState<number>(() => {
    const val = parseInt(totalMarks, 10);
    return isNaN(val) || val <= 0 ? 50 : val;
  });
  const [rebalancePrompt, setRebalancePrompt] = useState<{ open: boolean; oldTarget: number; newTarget: number } | null>(null);
  const [previousBlueprint, setPreviousBlueprint] = useState<BlueprintState | null>(null);
  const [balanceModal, setBalanceModal] = useState<{
    open: boolean;
    proposal: BlueprintState | null;
    explanation: string;
  }>({
    open: false,
    proposal: null,
    explanation: "",
  });

  const blueprintSummary = useMemo(() => {
    let totalQuestions = 0;
    const blueprintMarks = computeBlueprintTotal(blueprint);
    const typeEntries = Object.entries(blueprint) as [keyof BlueprintState, BlueprintTypeConfig][];
    for (const [, cfg] of typeEntries) {
      if (cfg.enabled && cfg.count > 0) {
        totalQuestions += cfg.count;
      }
    }
    return { totalQuestions, blueprintMarks };
  }, [blueprint]);

  const projectedDifficultyCounts = useMemo(() => {
    const totalQ = blueprintSummary.totalQuestions;
    if (totalQ === 0) return { easy: 0, medium: 0, hard: 0 };
    if (difficultyMode === "easy") return { easy: totalQ, medium: 0, hard: 0 };
    if (difficultyMode === "medium") return { easy: 0, medium: totalQ, hard: 0 };
    if (difficultyMode === "hard") return { easy: 0, medium: 0, hard: totalQ };
    const e = Math.round((totalQ * difficultyMix.easy) / 100);
    const m = Math.round((totalQ * difficultyMix.medium) / 100);
    const h = Math.max(0, totalQ - e - m);
    return { easy: e, medium: m, hard: h };
  }, [blueprintSummary.totalQuestions, difficultyMode, difficultyMix]);

  const timeFitEstimate = useMemo(() => {
    return estimateExamTime(blueprint);
  }, [blueprint]);

  const timeFitWarning = useMemo(() => {
    const durMin = Number(duration) || 60;
    if (timeFitEstimate > durMin) {
      return `Estimated completion time (${timeFitEstimate} mins) exceeds exam duration (${durMin} mins). Consider reducing question counts or increasing duration.`;
    }
    return null;
  }, [timeFitEstimate, duration]);

  const handleDifficultySliderChange = (changed: "easy" | "medium" | "hard", val: number) => {
    const clamped = Math.max(0, Math.min(100, Math.round(val)));
    const remaining = 100 - clamped;
    const others = (["easy", "medium", "hard"] as const).filter((k) => k !== changed);
    const sumOthers = difficultyMix[others[0]] + difficultyMix[others[1]];
    if (sumOthers === 0) {
      const half = Math.floor(remaining / 2);
      setDifficultyMix({ ...difficultyMix, [changed]: clamped, [others[0]]: half, [others[1]]: remaining - half });
    } else {
      const share0 = Math.round((difficultyMix[others[0]] / sumOthers) * remaining);
      const share1 = remaining - share0;
      setDifficultyMix({ ...difficultyMix, [changed]: clamped, [others[0]]: share0, [others[1]]: share1 });
    }
  };

  const applyPreset = (preset: "objective" | "mixed" | "subjective") => {
    setPreviousBlueprint(JSON.parse(JSON.stringify(blueprint)));
    const { blueprint: newBp, notes } = allocateBlueprintToTarget(targetMarksNum, undefined, preset);
    setBlueprint(newBp);
    try {
      localStorage.setItem("examai_faculty_blueprint_customized", "true");
    } catch {}
    const label = preset === "objective" ? "Objective Only" : preset === "mixed" ? "Balanced Mix" : "Subjective Focus";
    toast.success(`Applied ${label} preset (${targetMarksNum} marks).`, {
      action: {
        label: "Undo",
        onClick: () => {
          if (previousBlueprint) {
            setBlueprint(previousBlueprint);
            toast.info("Reverted to previous blueprint.");
          }
        },
      },
    });
    if (notes.length > 0) {
      toast.info(notes.join(" • "));
    }
  };

  const handleProposeBalance = () => {
    const current = blueprintSummary.blueprintMarks;
    if (current === targetMarksNum) {
      toast.info("Blueprint marks already match the target marks exactly!");
      return;
    }
    const { blueprint: proposal, explanation } = balanceBlueprintSmallestChange(blueprint, targetMarksNum);
    setBalanceModal({ open: true, proposal, explanation });
  };

  const handleConfirmBalance = () => {
    if (balanceModal.proposal) {
      setPreviousBlueprint(JSON.parse(JSON.stringify(blueprint)));
      setBlueprint(balanceModal.proposal);
      try {
        localStorage.setItem("examai_faculty_blueprint_customized", "true");
      } catch {}
      toast.success(`Blueprint balanced to ${targetMarksNum} marks!`, {
        action: {
          label: "Undo",
          onClick: () => {
            if (previousBlueprint) {
              setBlueprint(previousBlueprint);
              toast.info("Reverted to previous blueprint.");
            }
          },
        },
      });
    }
    setBalanceModal({ open: false, proposal: null, explanation: "" });
  };

  const handleAutoAlignMarks = handleProposeBalance;

  const checkTopicExistsInPreview = (topic: string, previewText?: string) => {
    if (!previewText || !topic) return true;
    const tClean = topic.toLowerCase().trim();
    const tokens = tClean.split(/\s+/).filter((w) => w.length >= 3 && !["unit", "chapter", "module", "section", "part", "ch"].includes(w));
    if (tokens.length === 0) return true;
    const pLower = previewText.toLowerCase();
    return tokens.some((w) => pLower.includes(w));
  };

  const handleFileDispatch = async (files: FileList | File[] | null, forcedPurpose?: "syllabus" | "material") => {
    if (!files) return;
    const targetPurpose = forcedPurpose || uploadPurpose;
    const fileArray = Array.from(files);
    if (fileArray.length === 0) return;

    const allowedExtensions = [".pdf", ".docx", ".doc", ".txt", ".pptx"];
    const maxSizeBytes = 25 * 1024 * 1024; // 25 MB

    try {
      for (const file of fileArray) {
        const ext = "." + (file.name.split(".").pop() || "").toLowerCase();
        if (!allowedExtensions.includes(ext)) {
          toast.error(`"${file.name}" is not supported. Please upload PDF, DOCX, PPTX, or TXT.`);
          continue;
        }
        if (file.size > maxSizeBytes) {
          toast.error(`"${file.name}" exceeds the 25 MB file size limit.`);
          continue;
        }

        if (targetPurpose === "syllabus") {
          await handleSyllabusFileSelected(file);
          break; // Syllabus accepts one file
        } else {
          await handleUploadSubjectMaterial(file);
        }
      }
    } catch (err: any) {
      toast.error(extractApiErrorMessage(err, "File upload encountered an issue."));
    } finally {
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    }
  };

  const handleRemoveSyllabusFile = () => {
    setSyllabusFile(null);
    setParsedSyllabus(null);
    setUploadedFilesList([]);
    setTopics([]);
    setIsDirty(true);
    toast.info("Syllabus document removed and scope topics cleared.");
  };

  const handleSyllabusFileSelected = async (file: File) => {
    setSyllabusFile(file);
    setUploadedFilesList(prev => {
      const filtered = prev.filter(f => f.name !== file.name);
      return [...filtered, { name: file.name, size: file.size, uploadedAt: new Date().toLocaleTimeString() }];
    });
    setIsParsingSyllabus(true);
    try {
      const res = await facultyPaperApi.parseSyllabus(file);
      setParsedSyllabus(res);
      // Clean replacement: strictly populate topics with newly uploaded document's detected units
      // Never merges with previous exam or old topics
      if (res.topics && res.topics.length > 0) {
        setTopics([...res.topics]);
      } else {
        setTopics([]);
      }
      setIsDirty(true);
      if (res.has_multiple_subjects) {
        toast.warning(
          `Multiple subjects detected (${res.detected_domains?.join(", ") || "Mixed subjects"}). Please uncheck units that do NOT belong to this exam!`,
          { duration: 8000 }
        );
      } else {
        toast.success(
          `Syllabus analyzed: ${res.char_count.toLocaleString()} characters extracted, ${res.detected_topics_count} units detected!`
        );
      }
    } catch (err: any) {
      toast.error(extractApiErrorMessage(err, "Failed to extract syllabus content."));
      setParsedSyllabus(null);
      setTopics([]);
    } finally {
      setIsParsingSyllabus(false);
    }
  };

  const handleAddTopic = () => {
    setTopics([...topics, ""]);
    setIsDirty(true);
  };
  const handleRemoveTopic = (idx: number) => {
    setTopics(topics.filter((_, i) => i !== idx));
    setIsDirty(true);
  };
  const handleTopicChange = (idx: number, val: string) => {
    const next = [...topics];
    next[idx] = val;
    setTopics(next);
    setIsDirty(true);
  };

  const scheduleAnalysis = useMemo(() => {
    if (!startsAt && !endsAt) {
      return { status: "empty", message: "Schedule not set (Start and End times required before publishing)." };
    }
    if (!startsAt || !endsAt) {
      return { status: "incomplete", message: "Both Start Time and Deadline must be set." };
    }
    const s = new Date(startsAt).getTime();
    const e = new Date(endsAt).getTime();
    if (isNaN(s) || isNaN(e)) {
      return { status: "error", message: "Invalid date format." };
    }
    if (s < Date.now() - 60000) {
      return {
        status: "error",
        message: "Exam start time cannot be in the past. Please select a future time.",
      };
    }
    if (e <= s) {
      return { status: "error", message: "Deadline must be after start time." };
    }
    const durMin = Number(duration) || 60;
    const windowMin = Math.round((e - s) / 60000);
    if (windowMin < durMin) {
      return {
        status: "error",
        message: `Exam window (${windowMin}m) is less than exam duration (${durMin}m). Students need at least full duration.`,
      };
    }
    const hours = Math.floor(windowMin / 60);
    const mins = windowMin % 60;
    const windowStr = hours > 0 ? `${hours}h ${mins > 0 ? `${mins}m` : ""}` : `${mins}m`;
    return {
      status: "valid",
      message: `Valid exam window: ${windowStr} (Students have ${durMin} min to complete within this window).`,
    };
  }, [startsAt, endsAt, duration]);

  // Draft Actions
  const handleResumeDraft = () => {
    if (!detectedDraft) return;
    setExamTitle(detectedDraft.examTitle || "");
    setSubjectName(detectedDraft.subjectName || "");
    setDuration(detectedDraft.duration || "60");
    setTotalMarks(detectedDraft.totalMarks || "100");
    setTopics(detectedDraft.topics && detectedDraft.topics.length ? detectedDraft.topics : []);
    if (detectedDraft.examId) setExamId(detectedDraft.examId);
    if (detectedDraft.currentStep) setCurrentStep(detectedDraft.currentStep);
    if (detectedDraft.blueprint) {
      setBlueprint(detectedDraft.blueprint);
      try {
        localStorage.setItem("examai_faculty_blueprint_customized", "true");
      } catch {}
    }
    if (detectedDraft.difficultyMode) setDifficultyMode(detectedDraft.difficultyMode);
    if (detectedDraft.difficultyMix) setDifficultyMix(detectedDraft.difficultyMix);

    // Validate if saved start time is in past
    const s = new Date(detectedDraft.startsAt).getTime();
    if (isNaN(s) || s < Date.now()) {
      const nextSched = getNextRoundScheduleWindow();
      setStartsAt(nextSched.startsAt);
      setEndsAt(nextSched.endsAt);
      toast.info("Draft resumed. Start time was in the past and has been automatically updated to the next upcoming window.");
    } else {
      setStartsAt(detectedDraft.startsAt);
      setEndsAt(detectedDraft.endsAt);
      toast.success("Draft resumed successfully.");
    }
    setIsDirty(true);
    setShowDraftBanner(false);
  };

  const handleDiscardDraft = () => {
    if (window.confirm("Are you sure you want to discard this saved draft and reset all fields?")) {
      clearScopedWizardDraft(currentUser?.id);
      paperDraftApi.clearDraft().catch(() => {});
      setDetectedDraft(null);
      setShowDraftBanner(false);
      const nextSched = getNextRoundScheduleWindow();
      setExamTitle("");
      setSubjectName("");
      setDuration("60");
      setTotalMarks("50");
      setStartsAt(nextSched.startsAt);
      setEndsAt(nextSched.endsAt);
      setTopics([]);
      setSyllabusFile(null);
      setParsedSyllabus(null);
      setUploadedFilesList([]);
      setSelectedMaterialIds([]);
      setQuestions([]);
      setExamId(null);
      setCurrentStep(1);
      setIsDirty(false);
      toast.success("Draft discarded. Started fresh exam form.");
    }
  };

  const handleResetStep1Form = () => {
    if (window.confirm("Reset this form to clean defaults? All entered information will be cleared.")) {
      const nextSched = getNextRoundScheduleWindow();
      setExamTitle("");
      setSubjectName("");
      setDuration("60");
      setTotalMarks("50");
      setStartsAt(nextSched.startsAt);
      setEndsAt(nextSched.endsAt);
      setTopics([]);
      setSyllabusFile(null);
      setParsedSyllabus(null);
      setUploadedFilesList([]);
      setSelectedMaterialIds([]);
      setQuestions([]);
      setExamId(null);
      clearScopedWizardDraft(currentUser?.id);
      paperDraftApi.clearDraft().catch(() => {});
      setDetectedDraft(null);
      setShowDraftBanner(false);
      setIsDirty(false);
      toast.success("Form reset to clean defaults.");
    }
  };

  // Step 1 Validation
  const validateStep1 = () => {
    if (!examTitle.trim()) return "Exam Title is required.";
    if (!subjectName.trim()) return "Subject / Course is required.";
    const dur = Number(duration);
    if (isNaN(dur) || dur <= 0) return "Duration must be greater than 0.";
    const tm = Number(totalMarks);
    if (isNaN(tm) || tm < 1 || tm > 500) return "Target Total Marks must be an integer between 1 and 500.";
    if (scheduleAnalysis.status === "error") {
      return scheduleAnalysis.message;
    }
    return "";
  };

  // Step 1 Next
  const handleNextFromStep1 = () => {
    const error = validateStep1();
    if (error) {
      toast.error(error);
      return;
    }
    const currentTarget = targetMarksNum;
    const bpTotal = blueprintSummary.blueprintMarks;
    const isCustomized = localStorage.getItem("examai_faculty_blueprint_customized") === "true";

    if (!isCustomized && bpTotal !== currentTarget) {
      const { blueprint: autoBp, notes } = allocateBlueprintToTarget(currentTarget);
      setBlueprint(autoBp);
      setLastConfirmedTargetMarks(currentTarget);
      if (notes.length > 0) {
        toast.info(notes.join(" • "));
      }
    } else if (lastConfirmedTargetMarks !== currentTarget && bpTotal !== currentTarget) {
      setRebalancePrompt({ open: true, oldTarget: lastConfirmedTargetMarks, newTarget: currentTarget });
    }
    setCurrentStep(2);
  };

  // Central Generate Button State & Validation
  const activeSectionsCount = useMemo(() => {
    return (Object.keys(blueprint) as (keyof BlueprintState)[]).filter(
      (k) => blueprint[k].enabled && Number(blueprint[k].count) > 0
    ).length;
  }, [blueprint]);

  const generateButtonStatus = useMemo(() => {
    const isSubjectSelected = Boolean(subjectName?.trim());
    const hasSyllabusOrMaterial = Boolean(
      syllabusFile ||
      uploadedFilesList.length > 0 ||
      (parsedSyllabus && parsedSyllabus.filename) ||
      cleanTopics.length > 0 ||
      selectedMaterialIds.length > 0
    );
    const hasSections = activeSectionsCount > 0;
    const marksMatch = blueprintSummary.blueprintMarks === targetMarksNum && targetMarksNum > 0;
    const notRunning = !isGenerating && !activeJobId;

    const canClick = isSubjectSelected && hasSyllabusOrMaterial && hasSections && marksMatch && notRunning;

    let hint = "";
    if (!isSubjectSelected) {
      hint = "Please enter or select a Subject / Course name in Step 1";
    } else if (!hasSyllabusOrMaterial) {
      hint = "Upload a syllabus or reference material";
    } else if (!hasSections) {
      hint = "Enable at least one question section in the blueprint";
    } else if (!marksMatch) {
      hint = `Allocated ${blueprintSummary.blueprintMarks} / ${targetMarksNum} marks (must match target exactly)`;
    } else if (!notRunning) {
      hint = "Generation is currently in progress...";
    }

    return {
      canClick,
      hint,
      isSubjectSelected,
      hasSyllabusOrMaterial,
      hasSections,
      marksMatch,
      notRunning,
    };
  }, [
    subjectName,
    syllabusFile,
    uploadedFilesList.length,
    parsedSyllabus,
    cleanTopics.length,
    selectedMaterialIds.length,
    activeSectionsCount,
    blueprintSummary.blueprintMarks,
    targetMarksNum,
    isGenerating,
    activeJobId,
  ]);

  // AI Generation in Step 2
  const handleAiGenerate = async (overrideCapacity = false) => {
    if (!examTitle.trim()) {
      toast.error("Please enter an exam title in Step 1.");
      return;
    }
    if (!subjectName.trim()) {
      toast.error("Please enter a subject / course name in Step 1.");
      return;
    }

    if (blueprintSummary.blueprintMarks !== targetMarksNum) {
      toast.error(
        `Blueprint total marks (${blueprintSummary.blueprintMarks}) do not match target marks (${targetMarksNum}). Please balance your blueprint before generating.`
      );
      return;
    }

    const activeBlueprint: Record<string, { count: number; marks: number; marksPerQuestion: number; enabled: boolean }> = {};
    const activeTypes: string[] = [];
    (Object.keys(blueprint) as (keyof BlueprintState)[]).forEach((typeKey) => {
      if (blueprint[typeKey].enabled && blueprint[typeKey].count > 0) {
        activeBlueprint[typeKey] = {
          count: blueprint[typeKey].count,
          marks: blueprint[typeKey].marks,
          marksPerQuestion: blueprint[typeKey].marks,
          enabled: true,
        };
        activeTypes.push(typeKey);
      }
    });

    const sectionsArray = Object.entries(activeBlueprint).map(([typeKey, cfg]) => ({
      type: getQuestionTypeBackendName(typeKey),
      count: cfg.count,
      marks_per_question: cfg.marks,
      section_name: AI_QUESTION_TYPE_LABELS[typeKey] || typeKey,
    }));

    if (sectionsArray.length === 0) {
      toast.error("Please enable and configure at least one question section with count > 0 in the blueprint.");
      return;
    }

    const diffDistribution =
      difficultyMode === "mixed"
        ? difficultyMix
        : {
            easy: difficultyMode === "easy" ? 100 : 0,
            medium: difficultyMode === "medium" ? 100 : 0,
            hard: difficultyMode === "hard" ? 100 : 0,
          };

    if (cleanTopics.length === 0) {
      toast.error("Please upload a syllabus or select at least one topic for this exam.");
      return;
    }

    setIsGenerating(true);
    setGenerationProgress(25);

    try {
      setGenerationProgress(50);
      setFormFieldErrors({});
      const res = await facultyPaperApi.generateExam({
        title: examTitle.trim(),
        durationMinutes: Number(duration),
        totalMarks: Number(totalMarks),
        topics: cleanTopics,
        questionTypes: activeTypes,
        difficultyDistribution: diffDistribution,
        blueprint: activeBlueprint,
        sections: sectionsArray,
        aiModel,
        model_roles: modelRoles,
        syllabus: syllabusFile,
        avoidRepeats,
        subject: subjectName.trim() || undefined,
        subjectId: selectedSubjectId || undefined,
        material_ids: selectedMaterialIds.length > 0 ? selectedMaterialIds : undefined,
        selectedTopics: cleanTopics,
        starts_at: startsAt ? new Date(startsAt).toISOString() : null,
        ends_at: endsAt ? new Date(endsAt).toISOString() : null,
        display_timezone: "Asia/Kolkata",
        accept_capacity_override: overrideCapacity,
      });

      setGenerationProgress(100);
      setExamId(res.exam_id);

      if (res.job_id) {
        setActiveJobId(res.job_id);
        setShowProgressModal(true);
      } else if (res.exam_id) {
        const fullExam = await facultyExamApi.getExam(res.exam_id);
        if (fullExam.questions && fullExam.questions.length > 0) {
          setQuestions(fullExam.questions);
          toast.success(`Generated ${fullExam.questions.length} questions from question bank!`);
        } else {
          toast.info("Exam initialized. You can now author or customize questions.");
        }
      }
    } catch (err: any) {
      if (err?.response?.status === 400 && err?.response?.data?.fields) {
        const rawFields = err.response.data.fields;
        const normalizedFields: Record<string, string> = {};
        for (const [k, v] of Object.entries(rawFields)) {
          if (Array.isArray(v) && v.length > 0) {
            normalizedFields[k] = String(v[0]);
          } else if (typeof v === "string") {
            normalizedFields[k] = v;
          }
        }
        setFormFieldErrors(normalizedFields);
      }
      if (err?.response?.status === 409 && err?.response?.data?.error_code === 'CONTENT_CAPACITY_EXCEEDED') {
        setCapacityAdvisory(err.response.data);
      } else if (err?.response?.status === 409 && err?.response?.data?.active_job_id) {
        toast.info("A paper generation job is already running.");
        setActiveJobId(err.response.data.active_job_id);
        setShowProgressModal(true);
      } else {
        toast.error(extractApiErrorMessage(err, "Failed to initiate question generation."));
      }
    } finally {
      setIsGenerating(false);
    }
  };

  const handleRegenerateQuestion = async (index: number) => {
    const targetJobId = activeJobId || lastCompletedJobId;
    if (!targetJobId) {
      toast.info("Regeneration is available after AI generation starts.");
      return;
    }
    const qNumber = index + 1;
    setIsRegeneratingSlot(index);
    try {
      const res = await generationApi.regenerateQuestion(targetJobId, qNumber);
      if (res && res.question) {
        setQuestions((prev) => {
          const updated = [...prev];
          updated[index] = {
            ...updated[index],
            text: res.question.text,
            options: res.question.options || updated[index].options,
            correct_answer: res.question.correct_answer || updated[index].correct_answer,
            model_answer: res.question.explanation || res.question.model_answer || (updated[index] as any).model_answer,
            rubric: res.question.rubric || updated[index].rubric,
          };
          return updated;
        });
        toast.success(`Question #${qNumber} regenerated successfully!`);
      }
    } catch (err: any) {
      toast.error(extractApiErrorMessage(err, "Failed to regenerate question."));
    } finally {
      setIsRegeneratingSlot(null);
    }
  };

  const handleExportPdf = () => {
    const jobId = activeJobId || lastCompletedJobId;
    if (jobId) {
      window.open(`/api/ai-generator/jobs/${jobId}/export/pdf/`, "_blank");
    } else if (examId) {
      window.open(`/api/faculty/exams/${examId}/export/pdf/`, "_blank");
    } else {
      toast.error("Please generate or save an exam first before exporting.");
    }
  };

  const handleExportDocx = () => {
    const jobId = activeJobId || lastCompletedJobId;
    if (jobId) {
      window.open(`/api/ai-generator/jobs/${jobId}/export/docx/`, "_blank");
    } else if (examId) {
      window.open(`/api/faculty/exams/${examId}/export/docx/`, "_blank");
    } else {
      toast.error("Please generate or save an exam first before exporting.");
    }
  };

  const handleGenerationSuccess = useCallback(async (job: PaperGenerationJob) => {
    if (job.id) setLastCompletedJobId(job.id);
    if (!job.exam_id) return;
    try {
      setExamId(job.exam_id);
      const fullExam = await facultyExamApi.getExam(job.exam_id);
      if (fullExam.questions && fullExam.questions.length > 0) {
        setQuestions(fullExam.questions);
      }
    } catch (err) {
      console.error("Failed to load completed exam:", err);
    }
  }, []);

  // Load Question Bank items
  const fetchBankQuestions = useCallback(async () => {
    setIsLoadingBank(true);
    try {
      const res = await facultyQuestionBankApi.getQuestions({ limit: 100 });
      setBankQuestions(res.questions || []);
    } catch (err: any) {
      toast.error(extractApiErrorMessage(err, "Failed to load question bank items."));
    } finally {
      setIsLoadingBank(false);
    }
  }, []);


  // Selected Bank Questions Running Marks
  const selectedBankMarks = useMemo(() => {
    const idSet = new Set(selectedBankIds);
    return bankQuestions
      .filter((q) => idSet.has(q.id))
      .reduce((sum, q) => sum + Number(q.marks || 0), 0);
  }, [bankQuestions, selectedBankIds]);

  // Filtered Bank Questions
  const filteredBankQuestions = useMemo(() => {
    return bankQuestions.filter((q) => {
      if (bankSearchQuery.trim()) {
        const query = bankSearchQuery.toLowerCase();
        const matchesText = q.question_text?.toLowerCase().includes(query);
        const matchesTopic = q.topic?.toLowerCase().includes(query);
        if (!matchesText && !matchesTopic) return false;
      }
      if (bankTypeFilter !== "all" && q.question_type?.toLowerCase() !== bankTypeFilter.toLowerCase()) {
        return false;
      }
      if (bankDiffFilter !== "all" && q.difficulty?.toLowerCase() !== bankDiffFilter.toLowerCase()) {
        return false;
      }
      return true;
    });
  }, [bankQuestions, bankSearchQuery, bankTypeFilter, bankDiffFilter]);

  // Auto-assemble paper from Question Bank (deterministic Knapsack matching target marks exactly)
  const handleAutoAssembleFromBank = async () => {
    if (!examTitle.trim()) {
      toast.error("Please enter an exam title in Step 1.");
      return;
    }
    setIsAssemblingBank(true);
    try {
      const res = await facultyQuestionBankApi.assemblePaperFromBank(examId, {
        auto_assemble: true,
        target_marks: targetMarksNum,
        title: examTitle.trim(),
        subject: subjectName.trim() || undefined,
        duration_minutes: Number(duration),
        starts_at: startsAt ? new Date(startsAt).toISOString() : null,
        ends_at: endsAt ? new Date(endsAt).toISOString() : null,
        topics: cleanTopics,
        action: assembleAction,
      });

      setExamId(res.exam_id);
      const fullExam = await facultyExamApi.getExam(res.exam_id);
      if (fullExam.questions && fullExam.questions.length > 0) {
        setQuestions(fullExam.questions);
      }
      toast.success(res.detail || `Auto-assembled ${res.question_count} questions matching ${res.total_marks} marks directly from bank!`);
      if (res.marks_shortfall > 0) {
        toast.warning(`Note: Bank had a shortfall of ${res.marks_shortfall} marks against target ${targetMarksNum}.`);
      }
    } catch (err: any) {
      toast.error(extractApiErrorMessage(err, "Failed to assemble paper from question bank."));
    } finally {
      setIsAssemblingBank(false);
    }
  };

  // Manual assemble selected items from Question Bank
  const handleManualAssembleFromBank = async () => {
    if (!examTitle.trim()) {
      toast.error("Please enter an exam title in Step 1.");
      return;
    }
    if (selectedBankIds.length === 0) {
      toast.error("Please select at least one question from the bank.");
      return;
    }
    setIsAssemblingBank(true);
    try {
      const res = await facultyQuestionBankApi.assemblePaperFromBank(examId, {
        auto_assemble: false,
        question_ids: selectedBankIds,
        target_marks: targetMarksNum,
        title: examTitle.trim(),
        subject: subjectName.trim() || undefined,
        duration_minutes: Number(duration),
        starts_at: startsAt ? new Date(startsAt).toISOString() : null,
        ends_at: endsAt ? new Date(endsAt).toISOString() : null,
        topics: cleanTopics,
        action: assembleAction,
      });

      setExamId(res.exam_id);
      const fullExam = await facultyExamApi.getExam(res.exam_id);
      if (fullExam.questions && fullExam.questions.length > 0) {
        setQuestions(fullExam.questions);
      }
      toast.success(res.detail || `Assembled ${res.question_count} questions (${res.total_marks} marks) into your exam!`);
      setSelectedBankIds([]);
    } catch (err: any) {
      toast.error(extractApiErrorMessage(err, "Failed to assemble selected questions."));
    } finally {
      setIsAssemblingBank(false);
    }
  };

  // Add Manual Question
  const handleSaveManualQuestion = async () => {
    if (!manualQText.trim()) {
      toast.error("Question text is required.");
      return;
    }
    const marksNum = Number(manualQMarks) || 1;

    let targetExamId = examId;
    if (!targetExamId) {
      try {
        const initRes = await facultyPaperApi.generateExam({
          title: examTitle.trim() || "Untitled Exam",
          durationMinutes: Number(duration) || 60,
          totalMarks: Number(totalMarks) || 100,
          topics: cleanTopics.length ? cleanTopics : ["General"],
          questionTypes: ["mcq"],
          difficultyDistribution: { easy: 30, medium: 50, hard: 20 },
        });
        targetExamId = initRes.exam_id;
        setExamId(initRes.exam_id);
      } catch (err) {
        toast.error("Failed to initialize draft exam.");
        return;
      }
    }

    try {
      let accepted: any = undefined;
      if (manualQType === "fill_blank") {
        if (manualQAcceptedAnswers.trim()) {
          accepted = manualQAcceptedAnswers.split(",").map((s) => s.trim()).filter(Boolean);
        }
      }

      const createdQ = await facultyExamApi.addQuestion(targetExamId, {
        text: manualQText.trim(),
        question_type: manualQType,
        marks: marksNum,
        difficulty: manualQDiff,
        topic: manualQTopic.trim() || cleanTopics[0] || "General",
        options: manualQType === "mcq" ? manualQOptions.filter((opt) => opt.trim()) : [],
        correct_answer: manualQType === "true_false" ? manualQAnswer || "True" : manualQAnswer.trim(),
        model_answer: manualQModelAnswer.trim() || undefined,
        rubric: manualQRubric.trim() || undefined,
        word_limit: manualQWordLimit ? Number(manualQWordLimit) : undefined,
        accepted_answers: accepted,
      });

      setQuestions((prev) => [...prev, createdQ]);
      toast.success("Question added successfully!");
      setShowManualModal(false);
      // Reset form
      setManualQText("");
      setManualQOptions(["", "", "", ""]);
      setManualQAnswer("");
      setManualQModelAnswer("");
      setManualQRubric("");
      setManualQWordLimit("");
      setManualQAcceptedAnswers("");
    } catch (err) {
      toast.error(extractApiErrorMessage(err, "Failed to save question."));
    }
  };

  // Reordering Questions
  const handleMoveQuestion = async (index: number, direction: "up" | "down") => {
    const targetIndex = direction === "up" ? index - 1 : index + 1;
    if (targetIndex < 0 || targetIndex >= questions.length) return;

    const nextList = [...questions];
    const [moved] = nextList.splice(index, 1);
    nextList.splice(targetIndex, 0, moved);
    setQuestions(nextList);

    if (examId) {
      try {
        await facultyExamApi.reorderQuestions(
          examId,
          nextList.map((q) => q.id)
        );
      } catch {
        // Silently tolerate
      }
    }
  };

  // Delete Question
  const handleDeleteQuestion = async (questionId: number) => {
    if (!examId) {
      setQuestions((prev) => prev.filter((q) => q.id !== questionId));
      return;
    }
    try {
      await facultyExamApi.deleteQuestion(examId, questionId);
      setQuestions((prev) => prev.filter((q) => q.id !== questionId));
      toast.success("Question removed.");
    } catch (err) {
      toast.error(extractApiErrorMessage(err, "Failed to delete question."));
    }
  };

  // Step 2 Next
  const handleNextFromStep2 = () => {
    if (questions.length === 0) {
      toast.warning("Please add or generate at least one question before proceeding.");
      return;
    }
    setCurrentStep(3);
  };

  // Step 3 Next
  const handleNextFromStep3 = async () => {
    // If exam is already created, persist settings to it via PATCH
    if (examId) {
      try {
        await facultyExamApi.updateExam(examId, {
          shuffle_questions: shuffleQuestions,
          shuffle_options: shuffleOptions,
          random_subset_size: randomSubsetSize ? Number(randomSubsetSize) : null,
          max_warnings: Number(maxWarnings) || 1,
          allow_retakes: allowRetakes,
          show_result_immediately: showResultImmediately,
          starts_at: startsAt ? new Date(startsAt).toISOString() : null,
          ends_at: endsAt ? new Date(endsAt).toISOString() : null,
        });
      } catch (err) {
        toast.error("Failed to update exam settings.");
        return;
      }
    }
    setCurrentStep(4);
  };

  // Step 4 Validation Checks
  const validationChecks = useMemo(() => {
    const target = targetMarksNum;
    const subset = randomSubsetSize ? Number(randomSubsetSize) : null;
    const marksValid = subset ? questions.length >= subset : currentTotalMarks === target;
    const durMin = Number(duration) || 60;
    const now = Date.now();
    const graceMs = 5 * 60 * 1000;

    let scheduleError: string | null = null;
    if (!startsAt || !endsAt) {
      scheduleError = "Both Start Time and Deadline are required before publishing.";
    } else {
      const startMs = new Date(startsAt).getTime();
      const endMs = new Date(endsAt).getTime();
      if (isNaN(startMs) || isNaN(endMs)) {
        scheduleError = "Invalid start or end date.";
      } else if (endMs <= startMs) {
        scheduleError = "Deadline must be strictly after the start time.";
      } else if ((endMs - startMs) < durMin * 60 * 1000) {
        scheduleError = `Exam window (${Math.round((endMs - startMs) / 60000)} min) cannot be less than duration (${durMin} min).`;
      } else if (startMs < (now - graceMs)) {
        scheduleError = "Start time cannot be in the past.";
      }
    }

    const scheduleValid = scheduleError === null;
    const hasQuestions = questions.length > 0;
    const hasDept = Boolean(facultyDept);

    return {
      marksValid,
      scheduleValid,
      scheduleError,
      hasQuestions,
      hasDept,
      canPublish: marksValid && scheduleValid && hasQuestions && hasDept,
    };
  }, [targetMarksNum, randomSubsetSize, questions.length, currentTotalMarks, startsAt, endsAt, duration, facultyDept]);

  // Publish Exam
  const handlePublishExam = async () => {
    if (!examId) {
      toast.error("Please generate or save the draft exam first.");
      return;
    }
    if (!validationChecks.canPublish) {
      if (validationChecks.scheduleError) {
        toast.error(validationChecks.scheduleError);
      } else {
        toast.error("Please resolve validation errors before publishing.");
      }
      return;
    }

    setIsPublishing(true);
    try {
      // First ensure all settings are up to date
      await facultyExamApi.updateExam(examId, {
        shuffle_questions: shuffleQuestions,
        shuffle_options: shuffleOptions,
        random_subset_size: randomSubsetSize ? Number(randomSubsetSize) : null,
        max_warnings: Number(maxWarnings) || 1,
        allow_retakes: allowRetakes,
        show_result_immediately: showResultImmediately,
        starts_at: startsAt ? new Date(startsAt).toISOString() : null,
        ends_at: endsAt ? new Date(endsAt).toISOString() : null,
        display_timezone: "Asia/Kolkata",
      });

      const published = await facultyExamApi.publishExam(examId);
      clearScopedWizardDraft(currentUser?.id);
      paperDraftApi.clearDraft().catch(() => {});
      setIsDirty(false);
      toast.success(published.visibility?.status_summary || "Exam published successfully!");
      navigate("/faculty/history");
    } catch (err) {
      toast.error(extractApiErrorMessage(err, "Failed to publish exam."));
    } finally {
      setIsPublishing(false);
    }
  };

  const handleSaveAsDraft = () => {
    toast.success("Exam draft saved successfully!");
    navigate("/faculty/history");
  };

  return (
    <DashboardLayout menuItems={menuItems} userRole="Faculty">
      <div className={`aipg-wrapper ${styles["aipg-wrapper"] || ""} mx-auto max-w-7xl space-y-6 pb-36`}>
        {/* Title & Subtitle */}
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl sm:text-3xl font-bold text-slate-900">Faculty Paper Generation Wizard</h1>
            <p className="text-xs sm:text-sm text-slate-500">
              Design, curate, proctor, and publish exams with intelligent assistance
            </p>
          </div>
          <div className="flex items-center gap-2.5">
            <button
              type="button"
              onClick={handleDiscardDraft}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-slate-200 bg-white hover:bg-rose-50 hover:text-rose-600 hover:border-rose-200 text-xs font-semibold text-slate-700 shadow-xs transition-colors"
              title="Clear all inputs and start a fresh exam draft"
            >
              <RotateCcw className="h-3.5 w-3.5" />
              Clear Form / Start New
            </button>
            <button
              type="button"
              onClick={() => window.open("/api/ai-generator/logs/", "_blank")}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-slate-200 bg-white hover:bg-slate-50 text-xs font-semibold text-slate-700 shadow-xs transition-colors"
            >
              <FileText className="h-3.5 w-3.5 text-slate-500" />
              Generation Logs
            </button>
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-slate-50 border border-slate-200 text-xs font-medium text-slate-700">
              <span className={`w-2 h-2 rounded-full ${isOllamaDown ? "bg-rose-500" : "bg-emerald-500 animate-pulse"}`} />
              <span>{isOllamaDown ? "Ollama Offline" : `Ollama Online (${modelMetadata.length || availableModels.length} Models)`}</span>
            </div>
          </div>
        </div>



        {/* Continue to Review Card if questions exist and currentStep < 3 */}
        {FRESH_START.showContinueReviewCard && questions.length > 0 && currentStep < 3 && (
          <div className="rounded-2xl border border-emerald-200 bg-emerald-50/90 p-4 flex flex-col sm:flex-row items-center justify-between gap-3 shadow-xs animate-in fade-in duration-200">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-xl bg-emerald-100 text-emerald-800">
                <CheckCircle2 className="h-5 w-5" />
              </div>
              <div>
                <h4 className="font-bold text-sm text-emerald-950">Draft Paper Waiting for Review</h4>
                <p className="text-xs text-emerald-800">You have {questions.length} synthesized questions ready for inspection and refinement.</p>
              </div>
            </div>
            <button
              type="button"
              onClick={() => setCurrentStep(3)}
              className="inline-flex items-center gap-2 rounded-xl bg-emerald-700 px-4 py-2 text-xs font-bold text-white shadow-xs hover:bg-emerald-800 transition-all cursor-pointer"
            >
              Continue to Review <ArrowRight className="h-4 w-4" />
            </button>
          </div>
        )}

        {/* 4-Step Progress Stepper Header */}
        <div className="rounded-2xl border border-slate-200 bg-white p-4 sm:p-5 shadow-xs">
          <div className="grid grid-cols-4 gap-2 sm:gap-4">
            {[
              { num: 1, label: "Details", desc: "Title, Dept & Schedule" },
              { num: 2, label: "Questions", desc: "AI, Bank & Manual" },
              { num: 3, label: "Settings", desc: "Shuffle & Proctoring" },
              { num: 4, label: "Publish", desc: "Preview & Validation" },
            ].map((step) => {
              const isActive = currentStep === step.num;
              const isPast = currentStep > step.num;

              return (
                <div
                  key={step.num}
                  onClick={() => isPast && setCurrentStep(step.num as any)}
                  className={`flex flex-col sm:flex-row items-center gap-2 sm:gap-3 rounded-xl p-2 sm:p-3 transition-all ${
                    isActive
                      ? "bg-blue-50/80 border border-blue-200"
                      : isPast
                      ? "cursor-pointer hover:bg-slate-50"
                      : "opacity-60"
                  }`}
                >
                  <div
                    className={`flex h-8 w-8 sm:h-9 sm:w-9 shrink-0 items-center justify-center rounded-xl text-xs sm:text-sm font-bold transition-all ${
                      isActive
                        ? "bg-blue-600 text-white shadow-xs"
                        : isPast
                        ? "bg-emerald-500 text-white"
                        : "bg-slate-100 text-slate-600"
                    }`}
                  >
                    {isPast ? <Check className="h-4 w-4" /> : step.num}
                  </div>
                  <div className="text-center sm:text-left min-w-0">
                    <p className={`text-xs sm:text-sm font-bold truncate ${isActive ? "text-blue-900" : "text-slate-900"}`}>
                      {step.label}
                    </p>
                    <p className="hidden md:block text-[11px] text-slate-400 truncate">{step.desc}</p>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* ================= STEP 1: DETAILS ================= */}
        {currentStep === 1 && (
          <div className="space-y-4">
            {/* Ollama Offline Warning Banner */}
            {isOllamaDown && (
              <div
                data-testid="ollama-offline-banner"
                className="rounded-2xl border border-rose-200 bg-rose-50/80 p-4 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 shadow-xs"
              >
                <div className="flex items-center gap-3">
                  <div className="rounded-xl bg-rose-100 p-2 text-rose-600 shrink-0">
                    <AlertCircle className="h-5 w-5" />
                  </div>
                  <div>
                    <h3 className="text-xs font-bold text-rose-900">
                      Ollama is offline
                    </h3>
                    <p className="text-xs text-rose-700">
                      Ollama is offline. Start Ollama to generate papers. You can continue configuring your exam details in the meantime.
                    </p>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => fetchInstalledAiModels(true)}
                  disabled={isFetchingModels}
                  className="inline-flex items-center gap-1.5 rounded-xl bg-rose-600 px-3.5 py-1.5 text-xs font-semibold text-white shadow-xs hover:bg-rose-700 disabled:opacity-50 transition-all shrink-0 cursor-pointer"
                >
                  <RefreshCw className={`h-3.5 w-3.5 ${isFetchingModels ? "animate-spin" : ""}`} />
                  {isFetchingModels ? "Checking..." : "Retry Connection"}
                </button>
              </div>
            )}

            {/* Unfinished Draft Resume Banner */}
            {FRESH_START.restoreDraft && detectedDraft && showDraftBanner && (
              <div
                data-testid="draft-resume-banner"
                className="rounded-2xl border border-blue-200 bg-gradient-to-r from-blue-50/90 to-indigo-50/90 p-4 sm:p-5 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 shadow-xs"
              >
                <div className="flex items-start gap-3.5">
                  <div className="rounded-xl bg-blue-600/10 p-2.5 text-blue-700 shrink-0">
                    <FileText className="h-5 w-5" />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <h3 className="text-sm font-bold text-slate-900">
                        Unfinished Draft Available
                      </h3>
                      <span className="rounded-full bg-blue-100 px-2 py-0.5 text-[10px] font-semibold text-blue-700">
                        Saved Draft
                      </span>
                    </div>
                    <p className="text-xs text-slate-600 mt-1">
                      You have an unsaved paper draft:{" "}
                      <strong className="text-slate-900 font-semibold">
                        "{detectedDraft.examTitle || "Untitled Exam"}"
                      </strong>
                      {detectedDraft.subjectName ? ` (${detectedDraft.subjectName})` : ""}. Would you like to resume where you left off?
                    </p>
                  </div>
                </div>
                <div className="flex flex-wrap items-center gap-2 w-full sm:w-auto justify-end">
                  <button
                    type="button"
                    onClick={handleResumeDraft}
                    className="inline-flex items-center gap-1.5 rounded-xl bg-blue-600 px-4 py-2 text-xs font-semibold text-white shadow-xs hover:bg-blue-700 active:scale-95 transition-all"
                  >
                    <Play className="h-3.5 w-3.5 fill-current" />
                    Resume Draft
                  </button>
                  <button
                    type="button"
                    onClick={() => setShowDraftBanner(false)}
                    className="rounded-xl border border-slate-200 bg-white px-3.5 py-2 text-xs font-medium text-slate-700 hover:bg-slate-50 transition-all"
                  >
                    Start Fresh
                  </button>
                  <button
                    type="button"
                    onClick={handleDiscardDraft}
                    className="inline-flex items-center gap-1 rounded-xl p-2 text-slate-400 hover:bg-rose-50 hover:text-rose-600 transition-all"
                    title="Discard saved draft"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              </div>
            )}

            <div className="rounded-2xl border border-slate-200 bg-white p-6 sm:p-8 shadow-xs space-y-6">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-4 border-b border-slate-100 gap-3">
                <div>
                  <h2 className="text-lg font-bold text-slate-900">Step 1: Exam Details & Schedule</h2>
                  <p className="text-xs text-slate-500">Provide basic assessment parameters and scheduling window</p>
                </div>
                <button
                  type="button"
                  onClick={handleResetStep1Form}
                  className="inline-flex items-center gap-1.5 rounded-xl border border-slate-200 bg-slate-50/80 px-3 py-1.5 text-xs font-semibold text-slate-600 hover:bg-rose-50 hover:border-rose-200 hover:text-rose-600 transition-all self-start sm:self-center"
                >
                  <RotateCcw className="h-3.5 w-3.5" />
                  Reset Form
                </button>
              </div>

              <div className="grid gap-5 sm:grid-cols-2">
                {/* Exam Title */}
                <div className="sm:col-span-2">
                  <label className="block text-xs font-semibold text-slate-700 mb-1.5">Exam Title *</label>
                  <input
                    type="text"
                    autoComplete="off"
                    value={examTitle}
                    onChange={(e) => {
                      setExamTitle(e.target.value);
                      setIsDirty(true);
                    }}
                    placeholder="e.g., Computer Networks Midterm Assessment"
                    className="w-full rounded-xl border border-slate-200 bg-slate-50/50 px-4 py-2.5 text-sm focus:border-blue-500 focus:bg-white focus:outline-hidden focus:ring-2 focus:ring-blue-500/20 transition-all"
                  />
                </div>

              {/* Locked Department */}
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1.5">Department (Locked)</label>
                <div className="relative">
                  <input
                    type="text"
                    disabled
                    value={facultyDept}
                    className="w-full rounded-xl border border-slate-200 bg-slate-100/70 px-4 py-2.5 text-sm font-medium text-slate-700 cursor-not-allowed pl-10"
                  />
                  <Lock className="absolute left-3.5 top-3 h-4 w-4 text-slate-400" />
                </div>
                <p className="mt-1 text-[11px] text-slate-500">
                  Automatically assigned from your faculty profile. Only students in this department can access the exam.
                </p>
              </div>

              {/* Subject / Course Input */}
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                  Subject / Course *
                </label>
                <div className="relative">
                  <input
                    type="text"
                    autoComplete="off"
                    value={subjectName}
                    onChange={(e) => handleSubjectNameChange(e.target.value)}
                    placeholder="Enter subject or course name"
                    className="w-full rounded-xl border border-slate-200 bg-slate-50/50 px-4 py-2.5 text-sm focus:border-blue-500 focus:bg-white focus:outline-hidden focus:ring-2 focus:ring-blue-500/20 transition-all font-medium text-slate-800"
                  />
                </div>
              </div>

              {/* Duration */}
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1.5">Duration (Minutes) *</label>
                <div className="relative">
                  <input
                    type="number"
                    min="1"
                    value={duration}
                    onChange={(e) => {
                      setDuration(e.target.value);
                      setIsDirty(true);
                    }}
                    className="w-full rounded-xl border border-slate-200 bg-slate-50/50 px-4 py-2.5 text-sm focus:border-blue-500 focus:bg-white focus:outline-hidden focus:ring-2 focus:ring-blue-500/20 transition-all pl-10"
                  />
                  <Clock className="absolute left-3.5 top-3 h-4 w-4 text-slate-400" />
                </div>
              </div>

              {/* Total Marks */}
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1.5">Target Total Marks *</label>
                <input
                  type="number"
                  min="1"
                  value={totalMarks}
                  onChange={(e) => {
                    setTotalMarks(e.target.value);
                    setFormFieldErrors((prev) => {
                      const next = { ...prev };
                      delete next.total_marks;
                      delete next.totalMarks;
                      return next;
                    });
                    setIsDirty(true);
                  }}
                  className={`w-full rounded-xl border px-4 py-2.5 text-sm transition-all focus:outline-hidden focus:ring-2 ${
                    formFieldErrors.total_marks || formFieldErrors.totalMarks
                      ? "border-rose-400 bg-rose-50/30 text-rose-900 focus:border-rose-500 focus:ring-rose-500/20"
                      : "border-slate-200 bg-slate-50/50 focus:border-blue-500 focus:bg-white focus:ring-blue-500/20"
                  }`}
                />
                {(formFieldErrors.total_marks || formFieldErrors.totalMarks) && (
                  <p className="mt-1.5 text-xs font-semibold text-rose-600 flex items-center gap-1">
                    <AlertCircle className="h-3.5 w-3.5 shrink-0" />
                    <span>{formFieldErrors.total_marks || formFieldErrors.totalMarks}</span>
                  </p>
                )}
              </div>

              {/* Starts At */}
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1.5">Available From (Start Time) *</label>
                <div className="relative">
                  <input
                    type="datetime-local"
                    value={startsAt}
                    onChange={(e) => {
                      setStartsAt(e.target.value);
                      setIsDirty(true);
                    }}
                    className="w-full rounded-xl border border-slate-200 bg-slate-50/50 px-4 py-2.5 text-sm focus:border-blue-500 focus:bg-white focus:outline-hidden focus:ring-2 focus:ring-blue-500/20 transition-all"
                  />
                </div>
              </div>

              {/* Ends At */}
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1.5">Deadline (End Time) *</label>
                <div className="relative">
                  <input
                    type="datetime-local"
                    value={endsAt}
                    onChange={(e) => {
                      setEndsAt(e.target.value);
                      setIsDirty(true);
                    }}
                    className="w-full rounded-xl border border-slate-200 bg-slate-50/50 px-4 py-2.5 text-sm focus:border-blue-500 focus:bg-white focus:outline-hidden focus:ring-2 focus:ring-blue-500/20 transition-all"
                  />
                </div>
              </div>

              {/* Schedule Feedback & Timezone Notice */}
              <div className="sm:col-span-2 -mt-1 mb-1">
                <div className="flex items-center justify-between text-[11px] text-slate-500 mb-1.5">
                  <span>Server & Exam Timezone: <strong>India Standard Time (IST, UTC+5:30)</strong></span>
                  <span className="text-slate-400">Enforced strictly by server</span>
                </div>
                {scheduleAnalysis.status !== "empty" && (
                  <div
                    className={`rounded-xl px-3.5 py-2 text-xs font-medium flex items-center gap-2 border ${
                      scheduleAnalysis.status === "valid"
                        ? "bg-emerald-50 text-emerald-800 border-emerald-200"
                        : "bg-rose-50 text-rose-800 border-rose-200"
                    }`}
                  >
                    {scheduleAnalysis.status === "valid" ? (
                      <CheckCircle2 className="h-4 w-4 text-emerald-600 shrink-0" />
                    ) : (
                      <AlertCircle className="h-4 w-4 text-rose-600 shrink-0" />
                    )}
                    <span>{scheduleAnalysis.message}</span>
                  </div>
                )}
              </div>

              {/* Topics */}
              <div className="sm:col-span-2">
                <div className="flex items-center justify-between mb-2">
                  <div>
                    <label className="block text-xs font-semibold text-slate-700">Syllabus Topics (Optional here)</label>
                    <span className="text-[11px] text-slate-500">You can add topics manually now, or upload your syllabus in Step 2 to detect them automatically.</span>
                  </div>
                  <button
                    type="button"
                    onClick={handleAddTopic}
                    className="inline-flex items-center gap-1 text-xs font-semibold text-blue-600 hover:text-blue-700"
                  >
                    <Plus className="h-3.5 w-3.5" /> Add Topic
                  </button>
                </div>
                {topics.length === 0 ? (
                  <div className="rounded-xl border border-dashed border-slate-200 bg-slate-50/70 p-4 text-center">
                    <p className="text-xs text-slate-500">
                      No topics added yet. Upload a syllabus document in Step 2 to auto-extract units, or click <strong>Add Topic</strong> above to specify manual topics.
                    </p>
                  </div>
                ) : (
                  <div className="space-y-2">
                    {topics.map((t, idx) => (
                      <div key={idx} className="flex items-center gap-2">
                        <input
                          type="text"
                          autoComplete="off"
                          value={t}
                          onChange={(e) => handleTopicChange(idx, e.target.value)}
                          placeholder={`Topic ${idx + 1} (e.g., OSI Layer 4 Transport Protocols)`}
                          className="w-full rounded-xl border border-slate-200 bg-slate-50/50 px-4 py-2 text-sm focus:border-blue-500 focus:bg-white focus:outline-hidden focus:ring-2 focus:ring-blue-500/20 transition-all"
                        />
                        <button
                          type="button"
                          onClick={() => handleRemoveTopic(idx)}
                          className="rounded-lg p-2 text-slate-400 hover:text-rose-600 hover:bg-rose-50"
                        >
                          <Trash2 className="h-4 w-4" />
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>

            {/* Step 1 Actions */}
            <div className="flex justify-end pt-4 border-t border-slate-100">
              <button
                type="button"
                onClick={handleNextFromStep1}
                className="inline-flex items-center gap-2 rounded-xl bg-blue-600 px-6 py-2.5 text-sm font-bold text-white shadow-md hover:bg-blue-700 transition-all"
              >
                Proceed to Questions <ArrowRight className="h-4 w-4" />
              </button>
            </div>
          </div>
        </div>
      )}

        {/* ================= STEP 2: QUESTIONS ================= */}
        {currentStep === 2 && (
          <div className="space-y-6">
            {/* Rebalance Prompt Banner if Target Changed */}
            {rebalancePrompt && (
              <div className="rounded-2xl border border-blue-200 bg-blue-50/95 p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3 shadow-xs">
                <div className="flex items-start sm:items-center gap-3">
                  <AlertCircle className="h-5 w-5 text-blue-600 shrink-0 mt-0.5 sm:mt-0" />
                  <div>
                    <p className="text-xs sm:text-sm font-bold text-blue-950">
                      Target marks changed from {rebalancePrompt.oldTarget} to {rebalancePrompt.newTarget} marks.
                    </p>
                    <p className="text-[11px] text-blue-700">
                      Would you like to automatically rebalance your blueprint to match {rebalancePrompt.newTarget} marks?
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-2 self-end sm:self-auto shrink-0">
                  <button
                    type="button"
                    onClick={() => {
                      setPreviousBlueprint(JSON.parse(JSON.stringify(blueprint)));
                      const { blueprint: reb, notes } = rebalanceBlueprintToTarget(blueprint, rebalancePrompt.newTarget);
                      setBlueprint(reb);
                      setLastConfirmedTargetMarks(rebalancePrompt.newTarget);
                      setRebalancePrompt(null);
                      toast.success(`Rebalanced blueprint to ${rebalancePrompt.newTarget} marks.`, {
                        action: {
                          label: "Undo",
                          onClick: () => {
                            if (previousBlueprint) {
                              setBlueprint(previousBlueprint);
                              toast.info("Reverted to previous blueprint.");
                            }
                          },
                        },
                      });
                      if (notes.length > 0) toast.info(notes.join(" • "));
                    }}
                    className="px-3.5 py-1.5 rounded-lg bg-blue-600 text-white text-xs font-bold hover:bg-blue-700 shadow-2xs"
                  >
                    Rebalance to {rebalancePrompt.newTarget}
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setLastConfirmedTargetMarks(rebalancePrompt.newTarget);
                      setRebalancePrompt(null);
                    }}
                    className="px-3 py-1.5 rounded-lg border border-slate-300 bg-white text-slate-700 text-xs font-semibold hover:bg-slate-50"
                  >
                    Keep my numbers
                  </button>
                </div>
              </div>
            )}

            {/* Sticky Blueprint vs Target Status Banner */}
            <div
              role="region"
              aria-live="polite"
              aria-atomic="true"
              className={`sticky top-3 z-30 rounded-2xl border p-4 shadow-sm backdrop-blur-md transition-all ${
                blueprintSummary.blueprintMarks === targetMarksNum
                  ? "border-emerald-200 bg-emerald-50/95 text-emerald-950"
                  : blueprintSummary.blueprintMarks > targetMarksNum
                  ? "border-amber-200 bg-amber-50/95 text-amber-950"
                  : "border-blue-200 bg-blue-50/95 text-blue-950"
              }`}
            >
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <div className="flex items-center gap-3">
                  {blueprintSummary.blueprintMarks === targetMarksNum ? (
                    <CheckCircle2 className="h-5 w-5 text-emerald-600 shrink-0" aria-hidden="true" />
                  ) : (
                    <AlertCircle
                      className={`h-5 w-5 shrink-0 ${
                        blueprintSummary.blueprintMarks > targetMarksNum ? "text-amber-600" : "text-blue-600"
                      }`}
                      aria-hidden="true"
                    />
                  )}
                  <div>
                    <div className="flex items-center gap-2 flex-wrap text-xs sm:text-sm">
                      <span>Target: <strong>{targetMarksNum}</strong> marks</span>
                      <span className="text-slate-300">|</span>
                      <span>Blueprint: <strong>{blueprintSummary.blueprintMarks}</strong> marks</span>
                      <span className="text-slate-300">|</span>
                      <span>
                        Difference:{" "}
                        <strong>
                          {blueprintSummary.blueprintMarks - targetMarksNum >= 0 ? "+" : ""}
                          {blueprintSummary.blueprintMarks - targetMarksNum}
                        </strong>
                      </span>
                    </div>
                    <p className="text-[11px] font-medium opacity-90 mt-0.5">
                      Status:{" "}
                      {blueprintSummary.blueprintMarks === targetMarksNum
                        ? "Matches target (Ready for generation)"
                        : blueprintSummary.blueprintMarks > targetMarksNum
                        ? `Blueprint is ${blueprintSummary.blueprintMarks - targetMarksNum} marks over target`
                        : `Blueprint is ${targetMarksNum - blueprintSummary.blueprintMarks} marks under target`}
                    </p>
                  </div>
                </div>

                {blueprintSummary.blueprintMarks !== targetMarksNum && (
                  <div className="flex items-center gap-2 self-start sm:self-auto shrink-0">
                    <button
                      type="button"
                      onClick={handleProposeBalance}
                      className="inline-flex items-center gap-1.5 rounded-xl bg-amber-600 px-3.5 py-1.5 text-xs font-bold text-white shadow-2xs hover:bg-amber-700 transition-colors"
                    >
                      <RefreshCw className="h-3.5 w-3.5" /> Balance to target
                    </button>
                  </div>
                )}
              </div>
            </div>

            {/* Balance Proposal Modal */}
            {balanceModal.open && balanceModal.proposal && (
              <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4 backdrop-blur-xs">
                <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-xl border border-slate-200 space-y-4">
                  <div className="flex items-center justify-between">
                    <h4 className="font-bold text-slate-900 text-base">Propose Blueprint Balance</h4>
                    <button
                      type="button"
                      onClick={() => setBalanceModal({ open: false, proposal: null, explanation: "" })}
                      className="text-slate-400 hover:text-slate-600"
                    >
                      <X className="h-4 w-4" />
                    </button>
                  </div>
                  <p className="text-xs text-slate-600">
                    To match target marks (<strong>{targetMarksNum}</strong>), the following smallest adjustment is proposed:
                  </p>
                  <div className="rounded-xl border border-blue-200 bg-blue-50/70 p-3.5 text-xs text-blue-900 font-medium">
                    {balanceModal.explanation}
                  </div>
                  <div className="rounded-xl border border-slate-100 bg-slate-50 p-3 text-xs space-y-1">
                    <div className="flex justify-between text-slate-500">
                      <span>Current blueprint total:</span>
                      <span className="font-bold text-slate-800">{blueprintSummary.blueprintMarks} marks</span>
                    </div>
                    <div className="flex justify-between text-emerald-700 font-bold">
                      <span>New blueprint total:</span>
                      <span>{computeBlueprintTotal(balanceModal.proposal)} marks</span>
                    </div>
                  </div>
                  <div className="flex items-center justify-end gap-2.5 pt-2">
                    <button
                      type="button"
                      onClick={() => setBalanceModal({ open: false, proposal: null, explanation: "" })}
                      className="rounded-xl border border-slate-200 px-4 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50"
                    >
                      Cancel
                    </button>
                    <button
                      type="button"
                      onClick={handleConfirmBalance}
                      className="rounded-xl bg-blue-600 px-4 py-2 text-xs font-bold text-white hover:bg-blue-700 shadow-sm"
                    >
                      Apply Balance
                    </button>
                  </div>
                </div>
              </div>
            )}

            {/* 2-Column Responsive Layout */}
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
              {/* Main Column */}
              <div className="lg:col-span-8 space-y-6 min-w-0">
                {/* Top Bar for Questions */}
                <div className="rounded-2xl border border-slate-200 bg-white p-5 sm:p-6 shadow-xs flex flex-col md:flex-row md:items-center justify-between gap-4">
                  <div>
                    <h2 className="text-lg font-bold text-slate-900">Step 2: Question Blueprint & Content Studio</h2>
                    <p className="text-xs text-slate-500">
                      Set up question types, marks and difficulty, then add your study material
                    </p>
                  </div>

                  <div className="flex items-center gap-3 shrink-0">
                    <button
                      type="button"
                      onClick={() => setShowManualModal(true)}
                      className="h-[44px] px-4 rounded-[10px] border border-slate-200 bg-white hover:bg-slate-50 text-slate-700 text-sm font-semibold inline-flex items-center gap-2 shadow-xs transition-colors cursor-pointer focus:ring-2 focus:ring-slate-300/40"
                    >
                      <Plus className="h-4 w-4 shrink-0" />
                      <span>Add question manually</span>
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        if (!generateButtonStatus.canClick) {
                          toast.error(generateButtonStatus.hint || "Please complete all required fields before generating.");
                          if (!generateButtonStatus.isSubjectSelected || !generateButtonStatus.hasSyllabusOrMaterial) {
                            setCurrentStep(1);
                          }
                          return;
                        }
                        void handleAiGenerate(false);
                      }}
                      className={`h-[44px] px-5 rounded-[10px] bg-blue-600 hover:bg-blue-700 text-white text-sm font-bold inline-flex items-center gap-2 shadow-md transition-all active:scale-[0.98] cursor-pointer focus:ring-2 focus:ring-blue-500/30 ${
                        !generateButtonStatus.canClick ? 'opacity-80' : ''
                      }`}
                    >
                      {isGenerating ? (
                        <>
                          <Loader2 className="h-4 w-4 animate-spin shrink-0" />
                          <span>Generating Paper...</span>
                        </>
                      ) : (
                        <>
                          <Sparkles className="h-4 w-4 shrink-0" />
                          <span>Generate with AI</span>
                        </>
                      )}
                    </button>
                  </div>
                </div>

                {/* Neutral Helper Row Directly Under Header for Hint */}
                {!generateButtonStatus.canClick && generateButtonStatus.hint && (
                  <div className="flex items-center gap-2.5 px-4 py-2.5 rounded-xl border border-amber-200/80 bg-amber-50/60 text-xs text-slate-700 animate-in fade-in duration-200">
                    <AlertCircle className="h-4 w-4 text-amber-600 shrink-0" />
                    <span>{generateButtonStatus.hint}</span>
                  </div>
                )}

            {/* 1. Subject Study Materials & Syllabus Context */}
            <div className="rounded-2xl border border-slate-200 bg-white p-5 sm:p-6 shadow-xs space-y-5">
              {/* Card Header */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-100 pb-3">
                <div className="flex items-center gap-2 flex-wrap">
                  <BookOpen className="h-4 w-4 text-blue-600" />
                  <h3 className="text-sm font-bold text-slate-900">
                    Study Material and Syllabus
                  </h3>
                  {subjectName ? (
                    <span className="text-xs px-2.5 py-0.5 rounded-full font-semibold bg-slate-100 text-slate-700 border border-slate-200">
                      Subject: {subjectName}
                    </span>
                  ) : null}
                </div>
                <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-emerald-700 bg-emerald-50 border border-emerald-200 px-2.5 py-0.5 rounded-full self-start sm:self-auto whitespace-nowrap">
                  <ShieldCheck className="h-3 w-3" /> Questions synthesized strictly from verified materials
                </span>
              </div>

              {/* Top: Segmented Purpose Selector */}
              <div className="space-y-2">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-bold text-slate-700">This file is a:</span>
                    <div className="inline-flex p-1 rounded-xl bg-slate-100 border border-slate-200/80">
                      <button
                        type="button"
                        onClick={() => setUploadPurpose("syllabus")}
                        className={`px-3 py-1.5 rounded-lg text-xs transition-all cursor-pointer ${
                          uploadPurpose === "syllabus"
                            ? "bg-white text-indigo-700 font-bold shadow-2xs"
                            : "text-slate-600 hover:text-slate-900 font-medium"
                        }`}
                      >
                        Syllabus
                      </button>
                      <button
                        type="button"
                        onClick={() => setUploadPurpose("material")}
                        className={`px-3 py-1.5 rounded-lg text-xs transition-all cursor-pointer ${
                          uploadPurpose === "material"
                            ? "bg-white text-blue-700 font-bold shadow-2xs"
                            : "text-slate-600 hover:text-slate-900 font-medium"
                        }`}
                      >
                        Study material
                      </button>
                    </div>
                  </div>

                  <p className="text-[11px] text-slate-500 italic">
                    {uploadPurpose === "syllabus"
                      ? "We extract units and topics from it"
                      : "Textbooks, notes and question banks the AI uses to write questions"}
                  </p>
                </div>
              </div>

              {/* Middle: Unified Drop Zone */}
              <div
                onDragOver={(e) => {
                  e.preventDefault();
                  setIsDraggingUpload(true);
                }}
                onDragLeave={(e) => {
                  e.preventDefault();
                  setIsDraggingUpload(false);
                }}
                onDrop={(e) => {
                  e.preventDefault();
                  setIsDraggingUpload(false);
                  if (e.dataTransfer?.files) {
                    void handleFileDispatch(e.dataTransfer.files);
                  }
                }}
                onClick={() => fileInputRef.current?.click()}
                className={`rounded-2xl border-2 border-dashed p-6 sm:p-8 text-center transition-all cursor-pointer flex flex-col items-center justify-center min-h-[170px] ${
                  isDraggingUpload
                    ? "border-blue-500 bg-blue-50/50 ring-2 ring-blue-500/20"
                    : "border-slate-200 hover:border-blue-400 bg-slate-50/40 hover:bg-slate-50/80"
                }`}
              >
                <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-blue-50 text-blue-600 mb-2.5 shadow-2xs">
                  {isParsingSyllabus || uploadingMaterial ? (
                    <Loader2 className="h-6 w-6 animate-spin" />
                  ) : (
                    <FileUp className="h-6 w-6" />
                  )}
                </div>
                <h4 className="text-sm font-semibold text-slate-800">
                  {isParsingSyllabus
                    ? "Extracting units and analyzing syllabus topics..."
                    : uploadingMaterial
                    ? "Uploading and indexing study material..."
                    : "Drag and drop files here or Browse"}
                </h4>
                <p className="text-xs text-slate-500 mt-1 max-w-sm mx-auto leading-relaxed">
                  PDF, DOCX, PPTX or TXT, up to 25 MB
                </p>

                <div className="mt-3 flex items-center gap-2">
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      fileInputRef.current?.click();
                    }}
                    className="inline-flex items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-4 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50 shadow-2xs cursor-pointer"
                  >
                    <Upload className="h-3.5 w-3.5" /> Browse Files
                  </button>
                  <input
                    ref={fileInputRef}
                    type="file"
                    multiple={uploadPurpose === "material"}
                    accept=".pdf,.docx,.doc,.txt,.pptx"
                    className="sr-only"
                    onChange={(e) => {
                      if (e.target.files) {
                        void handleFileDispatch(e.target.files);
                      }
                    }}
                  />
                </div>
              </div>

              {/* Bottom: Combined Uploaded Files List */}
              <div className="rounded-xl border border-slate-200 bg-slate-50/30 p-4 space-y-3">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-200/60 pb-2.5">
                  <div className="flex items-center gap-2">
                    <FileCheck className="h-4 w-4 text-blue-600 shrink-0" />
                    <h4 className="text-xs font-bold text-slate-900 uppercase tracking-wider">
                      Uploaded Files
                    </h4>
                    {subjectMaterials.length > 0 && (
                      <span className="text-[10px] font-semibold text-slate-600 bg-slate-200/70 px-2 py-0.5 rounded-full">
                        {selectedMaterialIds.length} of {subjectMaterials.length} selected
                      </span>
                    )}
                  </div>

                  {subjectMaterials.length > 0 && (
                    <div className="flex items-center gap-2 text-xs shrink-0 self-end sm:self-auto">
                      <button
                        type="button"
                        onClick={() => setSelectedMaterialIds(subjectMaterials.map((m) => m.id))}
                        className="font-semibold text-blue-600 hover:underline"
                      >
                        Select All
                      </button>
                      <span className="text-slate-300">|</span>
                      <button
                        type="button"
                        onClick={() => setSelectedMaterialIds([])}
                        className="font-semibold text-slate-500 hover:underline"
                      >
                        Clear All
                      </button>
                    </div>
                  )}
                </div>

                {/* Items Container */}
                <div className="space-y-2">
                  {/* Active Syllabus File Row */}
                  {(parsedSyllabus || syllabusFile || uploadedFilesList.length > 0) && (
                    <div className="flex items-center justify-between p-3 rounded-xl border border-indigo-200 bg-indigo-50/40 text-xs">
                      <div className="flex items-center gap-2.5 min-w-0">
                        <FileText className="h-4 w-4 text-indigo-600 shrink-0" />
                        <div className="min-w-0">
                          <div className="flex items-center gap-2">
                            <span className="font-bold text-slate-900 truncate">
                              {parsedSyllabus?.filename || syllabusFile?.name || uploadedFilesList[0]?.name || "Syllabus Document"}
                            </span>
                            <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-indigo-100 text-indigo-800 border border-indigo-200 shrink-0">
                              Syllabus
                            </span>
                          </div>
                          <span className="text-[10px] text-slate-500 block">
                            {parsedSyllabus?.char_count
                              ? `${parsedSyllabus.char_count.toLocaleString()} characters extracted • ${parsedSyllabus.detected_topics_count} units`
                              : isParsingSyllabus
                              ? "Analyzing units & topics..."
                              : "Parsed"}
                          </span>
                        </div>
                      </div>

                      <button
                        type="button"
                        onClick={handleRemoveSyllabusFile}
                        className="p-1 rounded-lg text-slate-400 hover:text-rose-600 hover:bg-rose-50 transition-colors ml-2 shrink-0"
                        title="Remove syllabus document"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  )}

                  {/* Study Materials Rows */}
                  {loadingMaterials ? (
                    <div className="py-4 text-center text-xs text-slate-500 flex items-center justify-center gap-2">
                      <Loader2 className="h-4 w-4 animate-spin text-blue-600" />
                      <span>Loading subject materials...</span>
                    </div>
                  ) : subjectMaterials.length > 0 ? (
                    <div className="grid gap-2 sm:grid-cols-1 max-h-[300px] overflow-y-auto pr-1">
                      {subjectMaterials.map((m) => {
                        const isChecked = selectedMaterialIds.includes(m.id);
                        return (
                          <div
                            key={m.id}
                            onClick={() => toggleMaterialSelection(m.id)}
                            className={`flex items-start justify-between p-3 rounded-xl border transition-all cursor-pointer ${
                              isChecked
                                ? "border-blue-400 bg-blue-50/50 shadow-2xs ring-1 ring-blue-500/20"
                                : "border-slate-200 bg-white hover:bg-slate-50 opacity-70"
                            }`}
                          >
                            <div className="flex items-start gap-2.5 min-w-0">
                              <input
                                type="checkbox"
                                checked={isChecked}
                                onChange={() => toggleMaterialSelection(m.id)}
                                onClick={(e) => e.stopPropagation()}
                                className="mt-0.5 h-4 w-4 rounded border-slate-300 text-blue-600 focus:ring-blue-500 cursor-pointer"
                              />
                              <div className="min-w-0">
                                <div className="flex items-center gap-2">
                                  <span className="text-xs font-bold text-slate-800 block truncate" title={m.original_filename}>
                                    {m.original_filename}
                                  </span>
                                  <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-blue-100 text-blue-800 border border-blue-200 shrink-0">
                                    Study material
                                  </span>
                                </div>
                                <span className="text-[10px] text-slate-500 block">
                                  {m.char_count?.toLocaleString()} characters
                                </span>
                                {m.detected_topics && m.detected_topics.length > 0 && (
                                  <div className="flex flex-wrap gap-1 mt-1">
                                    {m.detected_topics.slice(0, 3).map((t, tIdx) => (
                                      <span
                                        key={tIdx}
                                        className="text-[9px] font-medium bg-white border border-slate-200 px-1.5 py-0.5 rounded text-slate-600 truncate max-w-[140px]"
                                      >
                                        {t}
                                      </span>
                                    ))}
                                    {m.detected_topics.length > 3 && (
                                      <span className="text-[9px] text-slate-400 font-medium self-center">
                                        +{m.detected_topics.length - 3} more
                                      </span>
                                    )}
                                  </div>
                                )}
                              </div>
                            </div>

                            <button
                              type="button"
                              onClick={(e) => handleDeleteSubjectMaterial(m.id, e)}
                              className="p-1 rounded-lg text-slate-400 hover:text-rose-600 hover:bg-rose-50 transition-colors ml-2 shrink-0"
                              title="Delete this material"
                            >
                              <Trash2 className="h-3.5 w-3.5" />
                            </button>
                          </div>
                        );
                      })}
                    </div>
                  ) : null}

                  {/* Empty state if nothing uploaded */}
                  {!parsedSyllabus && !syllabusFile && uploadedFilesList.length === 0 && subjectMaterials.length === 0 && !loadingMaterials && (
                    <div className="py-6 px-4 rounded-xl bg-white border border-dashed border-slate-200 text-center text-xs text-slate-500">
                      No files uploaded yet. Select Syllabus or Study Material above to add documents.
                    </div>
                  )}
                </div>
              </div>

              {/* Parsed Syllabus Scope & Units (Intact with all topics, domains, and capacity) */}
              {parsedSyllabus && (
                <div className="rounded-xl border border-emerald-200 bg-emerald-50/40 p-4 space-y-3">
                  <div className="flex items-start justify-between gap-3">
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <FileCheck className="h-4 w-4 text-emerald-600" />
                        <span className="text-sm font-bold text-slate-800">{parsedSyllabus.filename}</span>
                        <span className="text-xs text-slate-500">
                          ({parsedSyllabus.char_count.toLocaleString()} characters)
                        </span>
                      </div>
                      <p className="text-xs text-slate-600">
                        {parsedSyllabus.detected_topics_count} syllabus units/topics automatically identified.
                      </p>
                    </div>
                    <div className="flex items-center gap-2">
                      <label className="cursor-pointer text-xs font-semibold text-blue-600 hover:underline">
                        Replace File
                        <input
                          type="file"
                          accept=".pdf,.docx,.doc,.txt"
                          className="sr-only"
                          onChange={(e) => {
                            const file = e.target.files?.[0];
                            if (file) handleSyllabusFileSelected(file);
                          }}
                        />
                      </label>
                      <span className="text-slate-300">|</span>
                      <button
                        type="button"
                        onClick={handleRemoveSyllabusFile}
                        className="text-xs font-semibold text-rose-600 hover:underline inline-flex items-center gap-1"
                      >
                        <Trash2 className="h-3 w-3" /> Remove
                      </button>
                    </div>
                  </div>

                  {/* Multi-subject warning banner */}
                  {parsedSyllabus.has_multiple_subjects && (
                    <div className="flex items-start gap-2.5 rounded-lg border border-amber-300 bg-amber-50 p-3 text-xs text-amber-900">
                      <AlertCircle className="h-4 w-4 text-amber-600 shrink-0 mt-0.5" />
                      <div>
                        <strong className="font-bold">Multiple Subjects Detected:</strong> Unrelated domains found (
                        {parsedSyllabus.detected_domains?.join(", ") || "mixed"}). Please uncheck any units outside the scope of this exam. Questions are strictly scoped to the selected units only.
                      </div>
                    </div>
                  )}

                  {/* Capacity indicator */}
                  {parsedSyllabus.capacity && (
                    <div className="flex items-center justify-between rounded-lg border border-blue-200 bg-blue-50/60 px-3 py-2 text-xs text-blue-900">
                      <div className="flex items-center gap-2">
                        <span className="font-semibold">Content Depth:</span>
                        <span>
                          Supports ~{parsedSyllabus.capacity.recommended_max_questions} questions (~{parsedSyllabus.capacity.recommended_max_marks} marks)
                        </span>
                      </div>
                      {blueprintSummary.blueprintMarks > parsedSyllabus.capacity.recommended_max_marks && (
                        <span className="text-[11px] font-bold text-amber-700 bg-amber-100/80 px-2 py-0.5 rounded-md">
                          Target exceeds estimated depth
                        </span>
                      )}
                    </div>
                  )}

                  {parsedSyllabus.topics && parsedSyllabus.topics.length > 0 && (
                    <div className="pt-2 border-t border-emerald-200/60">
                      <div className="flex items-center justify-between mb-2">
                        <label className="block text-[11px] font-semibold text-slate-600 uppercase">
                          Scope Units / Chapters ({cleanTopics.length} of {parsedSyllabus.topics.length} selected)
                        </label>
                        <div className="flex items-center gap-2">
                          <button
                            type="button"
                            onClick={() => setTopics([...parsedSyllabus.topics])}
                            className="text-[11px] font-semibold text-blue-600 hover:underline"
                          >
                            Select All
                          </button>
                          <span className="text-slate-300">|</span>
                          <button
                            type="button"
                            onClick={() => setTopics([])}
                            className="text-[11px] font-semibold text-slate-500 hover:underline"
                          >
                            Clear All
                          </button>
                        </div>
                      </div>
                      <div className="flex flex-wrap gap-1.5">
                        {parsedSyllabus.topics.map((t, tIdx) => {
                          const isIncluded = cleanTopics.some((ct) => ct.toLowerCase() === t.toLowerCase());
                          return (
                            <button
                              key={tIdx}
                              type="button"
                              onClick={() => {
                                if (isIncluded) {
                                  setTopics((prev) => prev.filter((item) => item.toLowerCase() !== t.toLowerCase()));
                                } else {
                                  setTopics((prev) => [...prev.filter(Boolean), t]);
                                }
                              }}
                              className={`inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-xs font-medium border transition-all ${
                                isIncluded
                                  ? "bg-blue-600 text-white border-blue-600 shadow-2xs"
                                  : "bg-white text-slate-600 border-slate-200 hover:border-slate-300"
                              }`}
                            >
                              {isIncluded ? <CheckSquare className="h-3.5 w-3.5" /> : <Square className="h-3.5 w-3.5" />}
                              <span>{t}</span>
                            </button>
                          );
                        })}
                      </div>

                      {/* Manual topics labeled with badge and validated against document preview */}
                      {cleanTopics.filter((t) => !parsedSyllabus.topics.some((st) => st.toLowerCase() === t.toLowerCase())).length > 0 && (
                        <div className="mt-3 pt-2.5 border-t border-slate-200">
                          <label className="block text-[11px] font-semibold text-slate-600 uppercase mb-1.5">
                            Custom / Manual Topics
                          </label>
                          <div className="flex flex-wrap gap-1.5">
                            {cleanTopics
                              .filter((t) => !parsedSyllabus.topics.some((st) => st.toLowerCase() === t.toLowerCase()))
                              .map((mt, mtIdx) => {
                                const existsInDoc = checkTopicExistsInPreview(mt, parsedSyllabus.preview);
                                return (
                                  <div
                                    key={mtIdx}
                                    className={`inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-xs font-medium border ${
                                      existsInDoc
                                        ? "bg-purple-50 text-purple-800 border-purple-200"
                                        : "bg-amber-50 text-amber-800 border-amber-300"
                                    }`}
                                  >
                                    <span className="text-[10px] uppercase font-bold px-1 py-0.2 rounded bg-purple-200/60 text-purple-900">
                                      Manual
                                    </span>
                                    <span>{mt}</span>
                                    {!existsInDoc && (
                                      <span
                                        title="Warning: Not detected in uploaded document. Server validates topics strictly belong to syllabus."
                                        className="text-amber-600"
                                      >
                                        <AlertCircle className="h-3.5 w-3.5" />
                                      </span>
                                    )}
                                    <button
                                      type="button"
                                      onClick={() => setTopics((prev) => prev.filter((item) => item !== mt))}
                                      className="ml-1 text-slate-400 hover:text-rose-600"
                                    >
                                      <X className="h-3 w-3" />
                                    </button>
                                  </div>
                                );
                              })}
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )}
            

            {/* 2. Question Types Blueprint Studio */}
            <div className="rounded-2xl border border-slate-200 bg-white p-5 sm:p-6 shadow-xs space-y-5">
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 border-b border-slate-100 pb-3">
                <div className="flex items-center gap-2">
                  <Layers className="h-4 w-4 text-blue-600" />
                  <h3 className="text-sm font-bold text-slate-900">Question Types & Counts Blueprint</h3>
                </div>

                {/* Presets */}
                <div className="flex items-center gap-1.5 flex-wrap">
                  <span className="text-xs font-semibold text-slate-500 mr-1">Presets:</span>
                  <button
                    type="button"
                    onClick={() => applyPreset("objective")}
                    className="rounded-lg border border-slate-200 bg-slate-50 px-2.5 py-1 text-xs font-semibold text-slate-700 hover:bg-slate-100"
                  >
                    Objective Only
                  </button>
                  <button
                    type="button"
                    onClick={() => applyPreset("mixed")}
                    className="rounded-lg border border-slate-200 bg-slate-50 px-2.5 py-1 text-xs font-semibold text-slate-700 hover:bg-slate-100"
                  >
                    Balanced Mix
                  </button>
                  <button
                    type="button"
                    onClick={() => applyPreset("subjective")}
                    className="rounded-lg border border-slate-200 bg-slate-50 px-2.5 py-1 text-xs font-semibold text-slate-700 hover:bg-slate-100"
                  >
                    Subjective Focus
                  </button>
                </div>
              </div>

              {/* 5 Canonical Question Types Grid / Rows */}
              <div className="space-y-3">
                {(Object.keys(blueprint) as (keyof BlueprintState)[]).map((typeKey) => {
                  const cfg = blueprint[typeKey];
                  const info = questionTypeDetails[typeKey];
                  const subtotal = (cfg.enabled ? cfg.count : 0) * cfg.marks;

                  return (
                    <div
                      key={typeKey}
                      className={`aipg-blueprint-row ${styles["aipg-blueprint-row"] || ""} flex flex-col sm:flex-row sm:items-center justify-between gap-4 rounded-xl border p-4 transition-all ${
                        cfg.enabled
                          ? "border-slate-300 bg-slate-50/60 shadow-xs"
                          : "border-slate-200 bg-white opacity-60"
                      }`}
                    >
                      {/* Left: Toggle & Info */}
                      <div className="flex items-start gap-3 min-w-0">
                        <input
                          type="checkbox"
                          checked={cfg.enabled}
                          onChange={(e) => {
                            setBlueprint({
                              ...blueprint,
                              [typeKey]: { ...cfg, enabled: e.target.checked },
                            });
                            try {
                              localStorage.setItem("examai_faculty_blueprint_customized", "true");
                            } catch {}
                          }}
                          className="mt-1 h-4 w-4 rounded border-slate-300 text-blue-600 focus:ring-blue-500 cursor-pointer"
                        />
                        <div className="min-w-0">
                          <div className="flex items-center gap-2">
                            <span className="text-sm font-bold text-slate-900">{info.label}</span>
                            <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-semibold text-slate-600 uppercase">
                              {info.short}
                            </span>
                          </div>
                          <p className="text-xs text-slate-500 mt-0.5">{info.description}</p>
                        </div>
                      </div>

                      {/* Right: Steppers & Subtotal */}
                      <div className="flex items-center gap-4 shrink-0 justify-between sm:justify-end">
                        {/* Count Stepper */}
                        <div className="flex flex-col items-center">
                          <span className="text-[10px] font-semibold text-slate-400 uppercase mb-1">Questions</span>
                          <div className="flex items-center border border-slate-200 rounded-lg bg-white overflow-hidden shadow-2xs">
                            <button
                              type="button"
                              disabled={!cfg.enabled || cfg.count <= 0}
                              onClick={() => {
                                setBlueprint({
                                  ...blueprint,
                                  [typeKey]: { ...cfg, count: Math.max(0, cfg.count - 1) },
                                });
                                try {
                                  localStorage.setItem("examai_faculty_blueprint_customized", "true");
                                } catch {}
                              }}
                              className="px-2.5 py-1 text-slate-600 hover:bg-slate-100 disabled:opacity-30 font-bold"
                            >
                              -
                            </button>
                            <input
                              type="number"
                              min="0"
                              disabled={!cfg.enabled}
                              value={cfg.count}
                              onChange={(e) => {
                                setBlueprint({
                                  ...blueprint,
                                  [typeKey]: { ...cfg, count: Math.max(0, Number(e.target.value) || 0) },
                                });
                                try {
                                  localStorage.setItem("examai_faculty_blueprint_customized", "true");
                                } catch {}
                              }}
                              className="w-12 text-center text-xs font-bold text-slate-800 border-x border-slate-100 py-1 focus:outline-hidden"
                            />
                            <button
                              type="button"
                              disabled={!cfg.enabled}
                              onClick={() => {
                                setBlueprint({
                                  ...blueprint,
                                  [typeKey]: { ...cfg, count: cfg.count + 1 },
                                });
                                try {
                                  localStorage.setItem("examai_faculty_blueprint_customized", "true");
                                } catch {}
                              }}
                              className="px-2.5 py-1 text-slate-600 hover:bg-slate-100 disabled:opacity-30 font-bold"
                            >
                              +
                            </button>
                          </div>
                        </div>

                        {/* Marks Per Question Stepper */}
                        <div className="flex flex-col items-center">
                          <span className="text-[10px] font-semibold text-slate-400 uppercase mb-1">Marks / Q</span>
                          <div className="flex items-center border border-slate-200 rounded-lg bg-white overflow-hidden shadow-2xs">
                            <button
                              type="button"
                              disabled={!cfg.enabled || cfg.marks <= 1}
                              onClick={() => {
                                setBlueprint({
                                  ...blueprint,
                                  [typeKey]: { ...cfg, marks: Math.max(1, cfg.marks - 1) },
                                });
                                try {
                                  localStorage.setItem("examai_faculty_blueprint_customized", "true");
                                } catch {}
                              }}
                              className="px-2.5 py-1 text-slate-600 hover:bg-slate-100 disabled:opacity-30 font-bold"
                            >
                              -
                            </button>
                            <input
                              type="number"
                              min="1"
                              disabled={!cfg.enabled}
                              value={cfg.marks}
                              onChange={(e) => {
                                setBlueprint({
                                  ...blueprint,
                                  [typeKey]: { ...cfg, marks: Math.max(1, Number(e.target.value) || 1) },
                                });
                                try {
                                  localStorage.setItem("examai_faculty_blueprint_customized", "true");
                                } catch {}
                              }}
                              className="w-12 text-center text-xs font-bold text-slate-800 border-x border-slate-100 py-1 focus:outline-hidden"
                            />
                            <button
                              type="button"
                              disabled={!cfg.enabled}
                              onClick={() => {
                                setBlueprint({
                                  ...blueprint,
                                  [typeKey]: { ...cfg, marks: cfg.marks + 1 },
                                });
                                try {
                                  localStorage.setItem("examai_faculty_blueprint_customized", "true");
                                } catch {}
                              }}
                              className="px-2.5 py-1 text-slate-600 hover:bg-slate-100 disabled:opacity-30 font-bold"
                            >
                              +
                            </button>
                          </div>
                        </div>

                        {/* Subtotal */}
                        <div className="w-20 text-right">
                          <span className="text-[10px] font-semibold text-slate-400 uppercase block mb-1">Subtotal</span>
                          <span className={`text-xs font-bold ${cfg.enabled ? "text-blue-700" : "text-slate-400"}`}>
                            {subtotal} {subtotal === 1 ? "Mark" : "Marks"}
                          </span>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* 3. Difficulty Level Controls */}
            <div className="rounded-2xl border border-slate-200 bg-white p-5 sm:p-6 shadow-xs space-y-4">
              <div className="flex items-center justify-between flex-wrap gap-2 border-b border-slate-100 pb-3">
                <div className="flex items-center gap-2">
                  <Sliders className="h-4 w-4 text-blue-600" />
                  <h3 className="text-sm font-bold text-slate-900">Difficulty Level Distribution</h3>
                </div>

                {/* Difficulty Mode Tabs */}
                <div className="flex items-center rounded-xl bg-slate-100 p-1">
                  {(["easy", "medium", "hard", "mixed"] as const).map((mode) => (
                    <button
                      key={mode}
                      type="button"
                      onClick={() => setDifficultyMode(mode)}
                      className={`px-3 py-1 rounded-lg text-xs font-bold capitalize transition-all ${
                        difficultyMode === mode
                          ? "bg-white text-blue-700 shadow-2xs"
                          : "text-slate-600 hover:text-slate-900"
                      }`}
                    >
                      {mode}
                    </button>
                  ))}
                </div>
              </div>

              {difficultyMode === "mixed" ? (
                <div className="space-y-4">
                  <div className="grid gap-4 sm:grid-cols-3">
                    {/* Easy Slider */}
                    <div className="rounded-xl border border-emerald-200 bg-emerald-50/30 p-3.5 space-y-2">
                      <div className="flex items-center justify-between text-xs font-semibold">
                        <span className="text-emerald-800">Easy ({difficultyMix.easy}%)</span>
                        <span className="rounded-md bg-emerald-100 px-2 py-0.5 text-[11px] font-bold text-emerald-800">
                          ~{projectedDifficultyCounts.easy} Qs
                        </span>
                      </div>
                      <input
                        type="range"
                        min="0"
                        max="100"
                        value={difficultyMix.easy}
                        onChange={(e) => handleDifficultySliderChange("easy", Number(e.target.value))}
                        className="w-full accent-emerald-600 cursor-pointer"
                      />
                    </div>

                    {/* Medium Slider */}
                    <div className="rounded-xl border border-blue-200 bg-blue-50/30 p-3.5 space-y-2">
                      <div className="flex items-center justify-between text-xs font-semibold">
                        <span className="text-blue-800">Medium ({difficultyMix.medium}%)</span>
                        <span className="rounded-md bg-blue-100 px-2 py-0.5 text-[11px] font-bold text-blue-800">
                          ~{projectedDifficultyCounts.medium} Qs
                        </span>
                      </div>
                      <input
                        type="range"
                        min="0"
                        max="100"
                        value={difficultyMix.medium}
                        onChange={(e) => handleDifficultySliderChange("medium", Number(e.target.value))}
                        className="w-full accent-blue-600 cursor-pointer"
                      />
                    </div>

                    {/* Hard Slider */}
                    <div className="rounded-xl border border-rose-200 bg-rose-50/30 p-3.5 space-y-2">
                      <div className="flex items-center justify-between text-xs font-semibold">
                        <span className="text-rose-800">Hard ({difficultyMix.hard}%)</span>
                        <span className="rounded-md bg-rose-100 px-2 py-0.5 text-[11px] font-bold text-rose-800">
                          ~{projectedDifficultyCounts.hard} Qs
                        </span>
                      </div>
                      <input
                        type="range"
                        min="0"
                        max="100"
                        value={difficultyMix.hard}
                        onChange={(e) => handleDifficultySliderChange("hard", Number(e.target.value))}
                        className="w-full accent-rose-600 cursor-pointer"
                      />
                    </div>
                  </div>
                  <p className="text-[11px] text-slate-500">
                    Sliders auto-balance to 100%. Total questions will be partitioned according to these target percentages.
                  </p>
                </div>
              ) : (
                <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 text-xs font-medium text-slate-700 flex items-center justify-between">
                  <span>
                    <strong>100%</strong> of generated questions will be created at{" "}
                    <strong className="uppercase text-blue-700">{difficultyMode}</strong> difficulty level.
                  </span>
                  <span className="rounded-md bg-white border border-slate-200 px-2.5 py-1 text-xs font-bold text-slate-800">
                    {blueprintSummary.totalQuestions} Questions Total
                  </span>
                </div>
              )}
            </div>

            {/* 4. Target Marks Alignment & Model Panel */}
            <div className="rounded-2xl border border-slate-200 bg-white p-5 sm:p-6 shadow-xs space-y-4">
              {/* 3-Column Responsive Stats Row */}
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 items-stretch">
                {/* 1. Total Questions */}
                <div className="rounded-xl border border-slate-200 bg-slate-50/70 p-3.5 flex flex-col justify-between">
                  <span className="text-xs text-slate-500 font-medium">Total Questions Planned</span>
                  <div className="my-1">
                    <strong className="text-lg text-slate-900 font-bold">{blueprintSummary.totalQuestions} Questions</strong>
                  </div>
                  <span className="text-[11px] text-slate-400">{activeSectionsCount} active question types</span>
                </div>

                {/* 2. Target Marks vs Blueprint Marks */}
                <div className="rounded-xl border border-slate-200 bg-slate-50/70 p-3.5 flex flex-col justify-between">
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-slate-500 font-medium">Marks Status</span>
                    {blueprintSummary.blueprintMarks === targetMarksNum ? (
                      <span className="inline-flex items-center gap-1 text-[11px] font-bold text-emerald-700 bg-emerald-50 border border-emerald-200 px-2 py-0.5 rounded-full">
                        <CheckCircle2 className="h-3.5 w-3.5" /> Perfect Match
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 text-[11px] font-bold text-amber-700 bg-amber-50 border border-amber-200 px-2 py-0.5 rounded-full">
                        <AlertCircle className="h-3.5 w-3.5" /> Mismatch
                      </span>
                    )}
                  </div>
                  <div className="flex items-baseline gap-2 my-1">
                    <strong className={`text-lg font-bold ${blueprintSummary.blueprintMarks === targetMarksNum ? "text-emerald-700" : "text-amber-700"}`}>
                      {blueprintSummary.blueprintMarks}
                    </strong>
                    <span className="text-xs text-slate-500">/ {targetMarksNum} Target Marks</span>
                  </div>
                  <span className="text-[11px] text-slate-400">
                    {blueprintSummary.blueprintMarks === targetMarksNum
                      ? "Exact allocation match"
                      : `Difference: ${blueprintSummary.blueprintMarks - targetMarksNum >= 0 ? "+" : ""}${blueprintSummary.blueprintMarks - targetMarksNum} marks`}
                  </span>
                </div>

                {/* 3. Local AI Model Dropdown / Status */}
                <div className="rounded-xl border border-slate-200 bg-slate-50/70 p-3.5 flex flex-col justify-between md:col-span-2 lg:col-span-1">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-xs text-slate-500 font-medium">Local AI Model</span>
                    {isFetchingModels && <RefreshCw className="h-3.5 w-3.5 animate-spin text-blue-600" />}
                  </div>
                  {isOllamaDown ? (
                    <div className="space-y-1.5 my-1">
                      <div className="flex items-center gap-1.5 text-xs font-semibold text-rose-700 bg-rose-50 border border-rose-200 rounded-lg p-2">
                        <AlertCircle className="h-4 w-4 shrink-0 text-rose-600" />
                        <span>Ollama Offline</span>
                      </div>
                      <button
                        type="button"
                        onClick={() => fetchInstalledAiModels(true)}
                        className="w-full text-[11px] font-bold text-white bg-rose-600 hover:bg-rose-700 rounded-md py-1 transition-all"
                      >
                        Retry Connection
                      </button>
                    </div>
                  ) : (
                    <select
                      value={aiModel}
                      onChange={(e) => setAiModel(e.target.value)}
                      className="w-full min-w-0 text-xs font-semibold bg-white border border-slate-200 rounded-lg px-2.5 py-2 focus:outline-hidden my-1"
                    >
                      {modelMetadata.length > 0 ? (
                        modelMetadata.map((m) => (
                          <option key={m.name} value={m.name}>
                            {m.label} {m.size ? `(${m.size})` : ""} {m.recommended ? "★ Primary" : ""}
                          </option>
                        ))
                      ) : (
                        availableModels.map((m) => (
                          <option key={m} value={m}>
                            {aiModelLabels[m] || m}
                          </option>
                        ))
                      )}
                    </select>
                  )}
                  <span className="text-[11px] text-slate-400">Primary generator for questions</span>
                </div>
              </div>

              {/* Advanced Multi-Model Architecture Panel (Separate Full-Width Block) */}
              <div className="rounded-xl border border-slate-200 bg-white shadow-2xs overflow-hidden mt-4">
                <button
                  type="button"
                  onClick={() => setShowAdvancedModelSettings((prev) => !prev)}
                  className="w-full flex flex-col sm:flex-row sm:items-center justify-between gap-2.5 px-4 py-3 bg-slate-50 hover:bg-slate-100/80 text-xs font-bold text-slate-700 transition-colors cursor-pointer"
                >
                  <div className="flex items-center gap-2.5 flex-wrap">
                    <Sliders className="h-5 w-5 text-blue-600 shrink-0" />
                    <span className="text-sm font-bold text-slate-900">Advanced Multi-Model Pipeline Roles</span>
                    <span className="text-[10px] font-semibold text-emerald-700 bg-emerald-50 border border-emerald-200 px-2.5 py-0.5 rounded-full whitespace-nowrap">
                      Low-VRAM & GPU Optimized (4GB+)
                    </span>
                  </div>
                  <span className="text-xs text-blue-600 font-semibold self-start sm:self-auto shrink-0">
                    {showAdvancedModelSettings ? "Hide Pipeline Roles ▲" : "Configure Pipeline Roles ▼"}
                  </span>
                </button>

                {showAdvancedModelSettings && (
                  <div className="p-4 sm:p-5 space-y-4 border-t border-slate-100 bg-white">
                    <p className="text-xs text-slate-500 leading-relaxed max-w-4xl">
                      Grouped sequential execution prevents GPU VRAM thrashing on 4 GB cards. Disables internal model thinking tokens for sub-10 minute generation.
                    </p>
                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-3.5">
                      {/* Role 1: MCQ Generator */}
                      <div className="rounded-xl border border-slate-200 p-3 bg-slate-50/50 flex flex-col justify-between min-w-0">
                        <div className="mb-2">
                          <span className="text-xs font-bold text-slate-800 block">MCQ Generator</span>
                          <span className="text-[11px] text-slate-400 block mt-0.5">Batch of 10</span>
                        </div>
                        <select
                          value={modelRoles.mcq_generator}
                          onChange={(e) => setModelRoles({ ...modelRoles, mcq_generator: e.target.value })}
                          className="w-full min-w-0 text-xs font-semibold bg-white border border-slate-200 rounded-lg px-2.5 py-1.5 truncate"
                        >
                          <option value="qwen3:4b">qwen3:4b (Recommended Primary)</option>
                          <option value="granite3.3:2b">granite3.3:2b</option>
                          <option value="llama3.2:3b">llama3.2:3b</option>
                          <option value="gemma3:4b">gemma3:4b</option>
                        </select>
                      </div>

                      {/* Role 2: Fast Generator */}
                      <div className="rounded-xl border border-slate-200 p-3 bg-slate-50/50 flex flex-col justify-between min-w-0">
                        <div className="mb-2">
                          <span className="text-xs font-bold text-slate-800 block">Fast Generator</span>
                          <span className="text-[11px] text-slate-400 block mt-0.5">True/False & Fill</span>
                        </div>
                        <select
                          value={modelRoles.fast_generator}
                          onChange={(e) => setModelRoles({ ...modelRoles, fast_generator: e.target.value })}
                          className="w-full min-w-0 text-xs font-semibold bg-white border border-slate-200 rounded-lg px-2.5 py-1.5 truncate"
                        >
                          <option value="granite3.3:2b">granite3.3:2b (Recommended Fast)</option>
                          <option value="qwen3:4b">qwen3:4b</option>
                          <option value="llama3.2:3b">llama3.2:3b</option>
                          <option value="gemma3:4b">gemma3:4b</option>
                        </select>
                      </div>

                      {/* Role 3: Answer Writer */}
                      <div className="rounded-xl border border-slate-200 p-3 bg-slate-50/50 flex flex-col justify-between min-w-0">
                        <div className="mb-2">
                          <span className="text-xs font-bold text-slate-800 block">Answer Writer</span>
                          <span className="text-[11px] text-slate-400 block mt-0.5">Short & Long Questions</span>
                        </div>
                        <select
                          value={modelRoles.answer_writer}
                          onChange={(e) => setModelRoles({ ...modelRoles, answer_writer: e.target.value })}
                          className="w-full min-w-0 text-xs font-semibold bg-white border border-slate-200 rounded-lg px-2.5 py-1.5 truncate"
                        >
                          <option value="llama3.2:3b">llama3.2:3b (Recommended Writer)</option>
                          <option value="qwen3:4b">qwen3:4b</option>
                          <option value="gemma3:4b">gemma3:4b</option>
                          <option value="phi3:mini">phi3:mini</option>
                        </select>
                      </div>

                      {/* Role 4: Academic Validator */}
                      <div className="rounded-xl border border-slate-200 p-3 bg-slate-50/50 flex flex-col justify-between min-w-0">
                        <div className="mb-2">
                          <span className="text-xs font-bold text-slate-800 block">Academic Validator</span>
                          <span className="text-[11px] text-slate-400 block mt-0.5">Audit & Quality Guard</span>
                        </div>
                        <select
                          value={modelRoles.validator}
                          onChange={(e) => setModelRoles({ ...modelRoles, validator: e.target.value })}
                          className="w-full min-w-0 text-xs font-semibold bg-white border border-slate-200 rounded-lg px-2.5 py-1.5 truncate"
                        >
                          <option value="phi3:mini">phi3:mini (Recommended Validator)</option>
                          <option value="llama3.2:3b">llama3.2:3b</option>
                          <option value="qwen3:4b">qwen3:4b</option>
                          <option value="gemma3:4b">gemma3:4b</option>
                        </select>
                      </div>

                      {/* Role 5: Fallback Engine */}
                      <div className="rounded-xl border border-slate-200 p-3 bg-slate-50/50 flex flex-col justify-between min-w-0 sm:col-span-2 lg:col-span-1 xl:col-span-1">
                        <div className="mb-2">
                          <span className="text-xs font-bold text-slate-800 block">Fallback Engine</span>
                          <span className="text-[11px] text-slate-400 block mt-0.5">Zero-Downtime Failover</span>
                        </div>
                        <select
                          value={modelRoles.fallback}
                          onChange={(e) => setModelRoles({ ...modelRoles, fallback: e.target.value })}
                          className="w-full min-w-0 text-xs font-semibold bg-white border border-slate-200 rounded-lg px-2.5 py-1.5 truncate"
                        >
                          <option value="gemma3:4b">gemma3:4b (Recommended Fallback)</option>
                          <option value="llama3.2:3b">llama3.2:3b</option>
                          <option value="qwen3:4b">qwen3:4b</option>
                        </select>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Plan Preview Table */}
              <div className="space-y-2 pt-1">
                <div className="flex items-center justify-between text-xs font-bold text-slate-800">
                  <span>Generation Blueprint & Question Plan</span>
                  <span className="text-[11px] font-medium text-slate-500">Target: {targetMarksNum} Marks</span>
                </div>
                <div className="overflow-x-auto rounded-xl border border-slate-200 shadow-2xs">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-slate-50 border-b border-slate-200 text-slate-600 font-semibold uppercase tracking-wider text-[11px]">
                      <tr>
                        <th className="py-2.5 px-3">Question Type</th>
                        <th className="py-2.5 px-3 text-center">Target Count</th>
                        <th className="py-2.5 px-3 text-center">Marks / Question</th>
                        <th className="py-2.5 px-3 text-right">Total Marks</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 bg-white">
                      {(Object.keys(blueprint) as (keyof BlueprintState)[])
                        .filter((typeKey) => blueprint[typeKey].enabled && blueprint[typeKey].count > 0)
                        .map((typeKey) => {
                          const cfg = blueprint[typeKey];
                          const typeInfo = questionTypeDetails[typeKey];
                          const totalForType = cfg.count * cfg.marks;
                          return (
                            <tr key={typeKey} className="hover:bg-slate-50/50">
                              <td className="py-2.5 px-3 font-medium text-slate-800">
                                {typeInfo?.label || typeKey}
                              </td>
                              <td className="py-2.5 px-3 text-center font-semibold text-slate-700">
                                {cfg.count}
                              </td>
                              <td className="py-2.5 px-3 text-center text-slate-600">
                                {cfg.marks}M
                              </td>
                              <td className="py-2.5 px-3 text-right font-bold text-slate-900">
                                {totalForType}M
                              </td>
                            </tr>
                          );
                        })}
                    </tbody>
                    <tfoot className="bg-slate-50/80 border-t border-slate-200 font-bold text-slate-900">
                      <tr>
                        <td className="py-2.5 px-3">Total Planned</td>
                        <td className="py-2.5 px-3 text-center">{blueprintSummary.totalQuestions} Qs</td>
                        <td className="py-2.5 px-3 text-center">-</td>
                        <td className={`py-2.5 px-3 text-right ${blueprintSummary.blueprintMarks === targetMarksNum ? "text-emerald-700" : "text-amber-700 font-extrabold"}`}>
                          {blueprintSummary.blueprintMarks} / {targetMarksNum}M
                        </td>
                      </tr>
                    </tfoot>
                  </table>
                </div>
              </div>

              {/* Mismatch Warning Alert + Auto Align Button */}
              {blueprintSummary.blueprintMarks !== targetMarksNum && (
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 rounded-xl border border-amber-200 bg-amber-50/70 p-3.5 text-xs text-amber-900">
                  <div className="flex items-center gap-2">
                    <AlertCircle className="h-4 w-4 text-amber-600 shrink-0" />
                    <span>
                      Blueprint total marks (<strong>{blueprintSummary.blueprintMarks}</strong>) does not equal target total marks (<strong>{targetMarksNum}</strong>).
                    </span>
                  </div>
                  <button
                    type="button"
                    onClick={handleProposeBalance}
                    className="inline-flex items-center gap-1 rounded-lg bg-amber-600 px-3 py-1.5 text-xs font-bold text-white shadow-2xs hover:bg-amber-700 shrink-0 self-start sm:self-auto cursor-pointer"
                  >
                    <RefreshCw className="h-3 w-3" /> Auto-Align to {targetMarksNum} Marks
                  </button>
                </div>
              )}

              {/* Time Fit Warning Alert */}
              {timeFitWarning && (
                <div className="flex items-center gap-2 rounded-xl border border-amber-300 bg-amber-50/80 p-3.5 text-xs text-amber-900">
                  <AlertCircle className="h-4 w-4 text-amber-600 shrink-0" />
                  <span>
                    <strong>Time-Fit Alert:</strong> {timeFitWarning}
                  </span>
                </div>
              )}
            </div>

            {/* 5. Generated Questions List (if any exist) */}
            {questions.length > 0 && (
              <div className="space-y-3">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-100 pb-2">
                  <div>
                    <h3 className="text-base font-bold text-slate-900">
                      Active Questions ({questions.length}) · Total Marks: {currentTotalMarks}
                    </h3>
                    <p className="text-xs text-slate-500">Review, reorder or modify generated questions below</p>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={() => setIsCompactView((prev) => !prev)}
                      className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold border transition-all cursor-pointer ${
                        isCompactView
                          ? "bg-blue-50 border-blue-200 text-blue-700 shadow-2xs"
                          : "bg-white border-slate-200 text-slate-600 hover:bg-slate-50"
                      }`}
                    >
                      <Layers className="h-3.5 w-3.5" />
                      {isCompactView ? "Expanded View" : "Compact View"}
                    </button>
                    <button
                      type="button"
                      onClick={() => setPreviewShuffledOptions((prev) => !prev)}
                      className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold border transition-all cursor-pointer ${
                        previewShuffledOptions
                          ? "bg-indigo-50 border-indigo-200 text-indigo-700 shadow-2xs"
                          : "bg-white border-slate-200 text-slate-600 hover:bg-slate-50"
                      }`}
                      title="Preview how MCQ options appear when randomized"
                    >
                      <RotateCcw className="h-3.5 w-3.5" />
                      {previewShuffledOptions ? "Standard Order" : "Shuffle Preview"}
                    </button>
                  </div>
                </div>

                {questions.map((q, idx) => (
                  <div
                    key={q.id || idx}
                    className="group rounded-2xl border border-slate-200 bg-white p-5 shadow-xs hover:border-slate-300 transition-all flex flex-wrap items-start justify-between gap-4"
                  >
                    <div className="flex items-start gap-3.5 min-w-0 flex-1">
                      <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-slate-100 text-xs font-bold text-slate-700">
                        {idx + 1}
                      </span>
                      <div className="space-y-1.5 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="rounded-full bg-blue-50 px-2.5 py-0.5 text-[11px] font-bold text-blue-700">
                            {q.question_type.toUpperCase()}
                          </span>
                          <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-[11px] font-semibold text-slate-600">
                            {q.marks} {Number(q.marks) === 1 ? "Mark" : "Marks"}
                          </span>
                          <span className="rounded-full bg-slate-50 px-2.5 py-0.5 text-[11px] font-medium text-slate-500 uppercase">
                            {q.difficulty}
                          </span>
                        </div>
                        <p className={`text-sm font-medium text-slate-800 leading-snug ${isCompactView ? "truncate" : ""}`}>{q.text || (q as any).question}</p>
                        {!isCompactView && q.options && q.options.length > 0 && (
                          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 pt-2 text-xs">
                            {(previewShuffledOptions ? [...q.options].reverse() : q.options).map((opt, oIdx) => {
                              const isCorrect = (q.correct_answer != null && String(q.correct_answer).trim().toLowerCase() === String(opt).trim().toLowerCase()) ||
                                                ((q as any).answer != null && String((q as any).answer).trim().toLowerCase() === String(opt).trim().toLowerCase());
                              return (
                                <div
                                  key={oIdx}
                                  className={`flex items-center gap-2 rounded-xl px-3 py-2 border transition-all ${
                                    isCorrect
                                      ? "bg-emerald-50/90 border-emerald-300 text-emerald-900 font-semibold shadow-2xs"
                                      : "bg-slate-50/80 border-slate-200/70 text-slate-700"
                                  }`}
                                >
                                  <span className={`flex h-5 w-5 shrink-0 items-center justify-center rounded-md text-[10px] font-bold ${
                                    isCorrect ? "bg-emerald-600 text-white" : "bg-slate-200 text-slate-600"
                                  }`}>
                                    {isCorrect ? <Check className="h-3 w-3" /> : String.fromCharCode(65 + oIdx)}
                                  </span>
                                  <span className="truncate flex-1">{opt}</span>
                                  {isCorrect && (
                                    <span className="text-[10px] font-bold text-emerald-700 uppercase tracking-wider shrink-0 bg-emerald-100/80 px-1.5 py-0.5 rounded-sm">
                                      Correct
                                    </span>
                                  )}
                                </div>
                              );
                            })}
                          </div>
                        )}
                        {!isCompactView && (q.model_answer || (q as any).answer) && q.question_type?.toLowerCase() !== "mcq" && (
                          <div className="mt-2.5 rounded-xl border border-slate-200/90 bg-slate-50/80 p-3 text-xs space-y-1">
                            <div className="flex items-center gap-1.5 font-bold text-slate-700">
                              <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600" />
                              <span>Model Answer / Key Points:</span>
                            </div>
                            <p className="text-slate-600 leading-relaxed whitespace-pre-wrap">{q.model_answer || (q as any).answer}</p>
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Actions: Regenerate, Move Up, Move Down, Delete */}
                    <div className="flex items-center gap-1.5 shrink-0">
                      <button
                        type="button"
                        disabled={isRegeneratingSlot === idx}
                        onClick={() => handleRegenerateQuestion(idx)}
                        className="rounded-lg p-1.5 text-blue-600 hover:text-blue-800 hover:bg-blue-50 disabled:opacity-50 transition-colors"
                        title="Regenerate this question with AI"
                      >
                        <Sparkles className={`h-4 w-4 ${isRegeneratingSlot === idx ? "animate-spin text-blue-600" : ""}`} />
                      </button>
                      <button
                        type="button"
                        disabled={idx === 0}
                        onClick={() => handleMoveQuestion(idx, "up")}
                        className="rounded-lg p-1.5 text-slate-400 hover:text-slate-700 hover:bg-slate-100 disabled:opacity-30"
                        title="Move Up"
                      >
                        <ArrowUp className="h-4 w-4" />
                      </button>
                      <button
                        type="button"
                        disabled={idx === questions.length - 1}
                        onClick={() => handleMoveQuestion(idx, "down")}
                        className="rounded-lg p-1.5 text-slate-400 hover:text-slate-700 hover:bg-slate-100 disabled:opacity-30"
                        title="Move Down"
                      >
                        <ArrowDown className="h-4 w-4" />
                      </button>
                      <button
                        type="button"
                        onClick={() => handleDeleteQuestion(q.id)}
                        className="rounded-lg p-1.5 text-slate-400 hover:text-rose-600 hover:bg-rose-50"
                        title="Delete Question"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* Step 2 Navigation */}
            <div className="flex justify-between pt-4 border-t border-slate-100">
              <button
                type="button"
                onClick={() => setCurrentStep(1)}
                className="inline-flex items-center gap-2 rounded-xl border border-slate-200 px-5 py-2.5 text-sm font-semibold text-slate-700 hover:bg-slate-50"
              >
                <ArrowLeft className="h-4 w-4" /> Back to Details
              </button>
              <button
                type="button"
                onClick={handleNextFromStep2}
                className="inline-flex items-center gap-2 rounded-xl bg-blue-600 px-6 py-2.5 text-sm font-bold text-white shadow-md hover:bg-blue-700"
              >
                Configure Settings <ArrowRight className="h-4 w-4" />
              </button>
            </div>
              </div>
              {/* Right Column: Sticky Blueprint Summary Panel (Desktop Only) */}
              <div className="hidden lg:block lg:col-span-4 sticky top-6 space-y-4">
                <div className={`aipg-summary-panel ${styles["aipg-summary-panel"] || ""} rounded-2xl border border-slate-200/80 bg-white p-5 shadow-sm space-y-5`}>
                  <div className="flex items-center justify-between border-b border-slate-100 pb-3">
                    <div>
                      <h3 className="text-sm font-bold text-slate-900">Blueprint Summary</h3>
                      <p className="text-[11px] text-slate-500 truncate max-w-[180px]">{subjectName || "Subject Not Selected"}</p>
                    </div>
                    <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                      generateButtonStatus.marksMatch
                        ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                        : "bg-amber-50 text-amber-700 border border-amber-200"
                    }`}>
                      {generateButtonStatus.marksMatch ? "Balanced" : `${Math.abs(blueprintSummary.blueprintMarks - targetMarksNum)}M Difference`}
                    </span>
                  </div>

                  {/* Marks Allocation Bar */}
                  <div className="space-y-1.5">
                    <div className="flex items-center justify-between text-xs">
                      <span className="font-semibold text-slate-600">Marks Allocation</span>
                      <span className="font-bold text-slate-900">{blueprintSummary.blueprintMarks} / {targetMarksNum}M</span>
                    </div>
                    <div className="w-full h-2 bg-slate-100 rounded-full overflow-hidden">
                      <div
                        className={`h-full transition-all duration-300 rounded-full ${
                          generateButtonStatus.marksMatch ? "bg-emerald-500" : blueprintSummary.blueprintMarks > targetMarksNum ? "bg-amber-500" : "bg-blue-500"
                        }`}
                        style={{ width: `${Math.min(100, Math.round((blueprintSummary.blueprintMarks / (targetMarksNum || 1)) * 100))}%` }}
                      />
                    </div>
                    <p className="text-[10px] text-slate-400">
                      {blueprintSummary.blueprintMarks === targetMarksNum
                        ? "Blueprint marks exactly match target."
                        : blueprintSummary.blueprintMarks > targetMarksNum
                        ? `${blueprintSummary.blueprintMarks - targetMarksNum} marks over target`
                        : `${targetMarksNum - blueprintSummary.blueprintMarks} marks needed`}
                    </p>
                  </div>

                  {/* Question Count by Type */}
                  <div className="space-y-2 border-t border-slate-100 pt-3">
                    <div className="flex items-center justify-between text-xs font-semibold text-slate-700">
                      <span>Planned Questions</span>
                      <span className="text-blue-600 font-bold">{blueprintSummary.totalQuestions} Qs</span>
                    </div>
                    <div className="space-y-1.5 text-[11px]">
                      {(Object.keys(blueprint) as (keyof BlueprintState)[])
                        .filter((k) => blueprint[k].enabled && blueprint[k].count > 0)
                        .map((k) => (
                          <div key={k} className="flex items-center justify-between text-slate-600">
                            <span>{questionTypeDetails[k]?.label || k}</span>
                            <span className="font-semibold">{blueprint[k].count} × {blueprint[k].marks}M ({blueprint[k].count * blueprint[k].marks}M)</span>
                          </div>
                        ))}
                    </div>
                  </div>

                  {/* Selected Model & Pipeline Status */}
                  <div className="space-y-2 border-t border-slate-100 pt-3 text-xs">
                    <div className="flex items-center justify-between">
                      <span className="font-semibold text-slate-600">Pipeline Engine</span>
                      <div className="flex items-center gap-1.5">
                        <span className={`w-2 h-2 rounded-full ${isOllamaDown ? "bg-rose-500" : "bg-emerald-500 animate-pulse"}`} />
                        <span className="text-[11px] font-medium text-slate-700">{isOllamaDown ? "Offline" : "Ready"}</span>
                      </div>
                    </div>
                    <div className="rounded-lg bg-slate-50 p-2 text-[11px] text-slate-600 space-y-1">
                      <div className="flex justify-between">
                        <span>MCQ Model:</span>
                        <span className="font-mono font-semibold">{modelRoles.mcq_generator}</span>
                      </div>
                      <div className="flex justify-between">
                        <span>Fast Model:</span>
                        <span className="font-mono font-semibold">{modelRoles.fast_generator}</span>
                      </div>
                    </div>
                  </div>

                  {/* Estimated Duration */}
                  <div className="flex items-center justify-between text-[11px] text-slate-500 bg-blue-50/60 rounded-lg px-2.5 py-1.5 border border-blue-100">
                    <span className="flex items-center gap-1">
                      <Clock className="h-3 w-3 text-blue-600" /> Est. Generation:
                    </span>
                    <span className="font-bold text-blue-900">
                      ~{Math.max(1, Math.round(blueprintSummary.totalQuestions * 0.35))} - {Math.max(2, Math.round(blueprintSummary.totalQuestions * 0.65))} mins
                    </span>
                  </div>

                  {/* Desktop Unblockable Generate Button */}
                  <div className="space-y-1.5 pt-1">
                    <button
                      type="button"
                      onClick={() => {
                        if (!generateButtonStatus.canClick) {
                          toast.error(generateButtonStatus.hint || "Please complete all required fields before generating.");
                          if (!generateButtonStatus.isSubjectSelected || !generateButtonStatus.hasSyllabusOrMaterial) {
                            setCurrentStep(1);
                          }
                          return;
                        }
                        void handleAiGenerate(false);
                      }}
                      className={`w-full inline-flex items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-blue-600 to-indigo-600 px-5 py-3 text-sm font-bold text-white shadow-md hover:from-blue-700 hover:to-indigo-700 cursor-pointer transition-all duration-200 active:scale-98 ${
                        !generateButtonStatus.canClick ? "opacity-85" : ""
                      }`}
                    >
                      {isGenerating ? (
                        <>
                          <Loader2 className="h-4 w-4 animate-spin" /> Generating Paper...
                        </>
                      ) : (
                        <>
                          <Sparkles className="h-4 w-4" /> Generate with AI
                        </>
                      )}
                    </button>
                    {!generateButtonStatus.canClick && generateButtonStatus.hint && (
                      <p className="text-[11px] font-medium text-amber-700 text-center leading-tight">
                        {generateButtonStatus.hint}
                      </p>
                    )}
                  </div>
                </div>
              </div>
            </div>

            {/* Sticky Bottom Summary Bar in Step 2 */}
            <div className="lg:hidden sticky bottom-0 z-30 -mx-4 sm:-mx-6 -mb-6 mt-8 bg-white/95 backdrop-blur-md border border-slate-200/80 shadow-2xl px-5 py-3.5 sm:px-6 transition-all duration-200 rounded-2xl">
              <div className="flex flex-col sm:flex-row items-center justify-between gap-3">
                <div className="flex items-center gap-3 flex-wrap">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-semibold text-slate-500">Allocation:</span>
                    <span
                      className={`text-xs sm:text-sm font-bold px-2.5 py-0.5 rounded-full ${
                        generateButtonStatus.marksMatch
                          ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                          : "bg-amber-50 text-amber-700 border border-amber-200"
                      }`}
                    >
                      {blueprintSummary.blueprintMarks} / {targetMarksNum} Marks
                    </span>
                  </div>
                  <span className="text-xs text-slate-500 hidden sm:inline">
                    <strong className="text-slate-800">{blueprintSummary.totalQuestions}</strong> questions planned
                  </span>
                </div>

                <div className="flex items-center gap-3 w-full sm:w-auto justify-end">
                  {!generateButtonStatus.canClick && generateButtonStatus.hint && (
                    <span className="text-xs font-medium text-amber-700 truncate max-w-xs text-right hidden md:inline">
                      {generateButtonStatus.hint}
                    </span>
                  )}
                  <button
                    type="button"
                    onClick={() => {
                      if (!generateButtonStatus.canClick) {
                        toast.error(generateButtonStatus.hint || "Please complete all required fields before generating.");
                        if (!generateButtonStatus.isSubjectSelected || !generateButtonStatus.hasSyllabusOrMaterial) {
                          setCurrentStep(1);
                        }
                        return;
                      }
                      void handleAiGenerate(false);
                    }}
                    className={`w-full sm:w-auto inline-flex items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-blue-600 to-indigo-600 px-6 py-2.5 text-xs sm:text-sm font-bold text-white shadow-md hover:from-blue-700 hover:to-indigo-700 cursor-pointer transition-all duration-200 active:scale-98 ${!generateButtonStatus.canClick ? 'opacity-80' : ''}`}
                  >
                    {isGenerating ? (
                      <>
                        <Loader2 className="h-4 w-4 animate-spin" /> Generating...
                      </>
                    ) : (
                      <>
                        <Sparkles className="h-4 w-4" /> Generate with AI
                      </>
                    )}
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ================= STEP 3: SETTINGS ================= */}
        {currentStep === 3 && (
          <div className="rounded-2xl border border-slate-200 bg-white p-6 sm:p-8 shadow-xs space-y-6">
            <div className="border-b border-slate-100 pb-4">
              <h2 className="text-lg font-bold text-slate-900">Step 3: Security & Proctoring Controls</h2>
              <p className="text-xs text-slate-500">Configure question randomization, anti-cheat deterrents, and exam integrity</p>
            </div>

            <div className="grid gap-6 sm:grid-cols-2">
              {/* Shuffle Questions Toggle */}
              <div className="flex items-start justify-between gap-4 rounded-2xl border border-slate-200 p-4 bg-slate-50/50">
                <div>
                  <h3 className="text-sm font-bold text-slate-900">Shuffle Questions (Fisher-Yates)</h3>
                  <p className="text-xs text-slate-500 mt-1">
                    Randomizes the sequence of questions for each student. Shuffled order is securely persisted on attempt start.
                  </p>
                </div>
                <input
                  type="checkbox"
                  checked={shuffleQuestions}
                  onChange={(e) => setShuffleQuestions(e.target.checked)}
                  className="mt-1 h-5 w-5 rounded border-slate-300 text-blue-600 focus:ring-blue-500 cursor-pointer"
                />
              </div>

              {/* Shuffle Options Toggle */}
              <div className="flex items-start justify-between gap-4 rounded-2xl border border-slate-200 p-4 bg-slate-50/50">
                <div>
                  <h3 className="text-sm font-bold text-slate-900">Shuffle Options (MCQ Choices)</h3>
                  <p className="text-xs text-slate-500 mt-1">
                    Permutes A, B, C, D choices differently for each student while automatically mapping answers back for grading.
                  </p>
                </div>
                <input
                  type="checkbox"
                  checked={shuffleOptions}
                  onChange={(e) => setShuffleOptions(e.target.checked)}
                  className="mt-1 h-5 w-5 rounded border-slate-300 text-blue-600 focus:ring-blue-500 cursor-pointer"
                />
              </div>

              {/* Random Subset Size */}
              <div className="rounded-2xl border border-slate-200 p-4 bg-slate-50/50">
                <label className="block text-sm font-bold text-slate-900">Random Subset Size (Optional)</label>
                <p className="text-xs text-slate-500 mt-0.5 mb-2.5">
                  Select a randomized balanced subset for each attempt (e.g., 20 questions out of a bank of 50). Leave blank to use all questions.
                </p>
                <input
                  type="number"
                  min="1"
                  max={questions.length || undefined}
                  value={randomSubsetSize}
                  onChange={(e) => setRandomSubsetSize(e.target.value)}
                  placeholder={`Optional (Bank has ${questions.length} questions)`}
                  className="w-full rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm focus:border-blue-500 focus:outline-hidden"
                />
              </div>

              {/* Max Warnings Threshold */}
              <div className="rounded-2xl border border-slate-200 p-4 bg-slate-50/50">
                <label className="block text-sm font-bold text-slate-900">Max Proctoring Warnings Threshold</label>
                <p className="text-xs text-slate-500 mt-0.5 mb-2.5">
                  Allowed proctoring infractions before auto-submit (default is 1 warning, next violation submits automatically).
                </p>
                <div className="relative">
                  <input
                    type="number"
                    min="0"
                    max="10"
                    value={maxWarnings}
                    onChange={(e) => setMaxWarnings(e.target.value)}
                    className="w-full rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm focus:border-blue-500 focus:outline-hidden pl-10"
                  />
                  <ShieldAlert className="absolute left-3.5 top-2.5 h-4 w-4 text-slate-400" />
                </div>
              </div>

              {/* Allow Retakes Toggle */}
              <div className="flex items-start justify-between gap-4 rounded-2xl border border-slate-200 p-4 bg-slate-50/50">
                <div>
                  <h3 className="text-sm font-bold text-slate-900">Allow Exam Retakes</h3>
                  <p className="text-xs text-slate-500 mt-1">
                    Permit students to take multiple attempts. Each attempt receives an independent randomized set of questions.
                  </p>
                </div>
                <input
                  type="checkbox"
                  checked={allowRetakes}
                  onChange={(e) => setAllowRetakes(e.target.checked)}
                  className="mt-1 h-5 w-5 rounded border-slate-300 text-blue-600 focus:ring-blue-500 cursor-pointer"
                />
              </div>

              {/* Show Result Immediately */}
              <div className="flex items-start justify-between gap-4 rounded-2xl border border-slate-200 p-4 bg-slate-50/50">
                <div>
                  <h3 className="text-sm font-bold text-slate-900">Show Results Immediately</h3>
                  <p className="text-xs text-slate-500 mt-1">
                    Disclose objective question scores and solutions right after student submission. Turn off to keep answers secret until review.
                  </p>
                </div>
                <input
                  type="checkbox"
                  checked={showResultImmediately}
                  onChange={(e) => setShowResultImmediately(e.target.checked)}
                  className="mt-1 h-5 w-5 rounded border-slate-300 text-blue-600 focus:ring-blue-500 cursor-pointer"
                />
              </div>
            </div>

            {/* Step 3 Navigation */}
            <div className="flex justify-between pt-4 border-t border-slate-100">
              <button
                type="button"
                onClick={() => setCurrentStep(2)}
                className="inline-flex items-center gap-2 rounded-xl border border-slate-200 px-5 py-2.5 text-sm font-semibold text-slate-700 hover:bg-slate-50"
              >
                <ArrowLeft className="h-4 w-4" /> Back to Questions
              </button>
              <button
                type="button"
                onClick={handleNextFromStep3}
                className="inline-flex items-center gap-2 rounded-xl bg-blue-600 px-6 py-2.5 text-sm font-bold text-white shadow-md hover:bg-blue-700"
              >
                Preview & Validate <ArrowRight className="h-4 w-4" />
              </button>
            </div>
          </div>
        )}

        {/* ================= STEP 4: PREVIEW & PUBLISH ================= */}
        {currentStep === 4 && (
          <div className="space-y-6">
            {/* Live Validation Report Card */}
            <div className="rounded-2xl border border-slate-200 bg-white p-5 sm:p-6 shadow-xs space-y-4">
              <div className="flex items-center justify-between border-b border-slate-100 pb-3">
                <h2 className="text-base font-bold text-slate-900 flex items-center gap-2">
                  <ShieldCheck className="h-5 w-5 text-blue-600" /> Pre-Publish Validation Report
                </h2>
                <span
                  className={`rounded-full px-3 py-1 text-xs font-bold ${
                    validationChecks.canPublish ? "bg-emerald-100 text-emerald-800" : "bg-amber-100 text-amber-800"
                  }`}
                >
                  {validationChecks.canPublish ? "All Checks Passed" : "Action Required"}
                </span>
              </div>

              <div className="grid gap-3 sm:grid-cols-2 text-xs sm:text-sm">
                <div className="flex items-center gap-2.5">
                  {validationChecks.hasDept ? (
                    <CheckCircle2 className="h-4 w-4 text-emerald-600 shrink-0" />
                  ) : (
                    <AlertCircle className="h-4 w-4 text-rose-600 shrink-0" />
                  )}
                  <span>
                    Department Assignment: <strong>{facultyDept || "Unassigned"}</strong>
                  </span>
                </div>

                <div className="flex items-center gap-2.5">
                  {validationChecks.hasQuestions ? (
                    <CheckCircle2 className="h-4 w-4 text-emerald-600 shrink-0" />
                  ) : (
                    <AlertCircle className="h-4 w-4 text-rose-600 shrink-0" />
                  )}
                  <span>
                    Question Pool: <strong>{questions.length} questions ready</strong>
                  </span>
                </div>

                <div className="flex items-center gap-2.5">
                  {validationChecks.marksValid ? (
                    <CheckCircle2 className="h-4 w-4 text-emerald-600 shrink-0" />
                  ) : (
                    <AlertCircle className="h-4 w-4 text-rose-600 shrink-0" />
                  )}
                  <span>
                    Marks Matching: Current{" "}
                    <strong>
                      {currentTotalMarks} / {targetMarksNum} Total
                    </strong>
                  </span>
                </div>

                <div className="flex items-center gap-2.5">
                  {validationChecks.scheduleValid ? (
                    <CheckCircle2 className="h-4 w-4 text-emerald-600 shrink-0" />
                  ) : (
                    <AlertCircle className="h-4 w-4 text-rose-600 shrink-0" />
                  )}
                  <span>
                    Schedule:{" "}
                    {startsAt && endsAt ? (
                      validationChecks.scheduleValid ? (
                        <strong>Valid Exam Window</strong>
                      ) : (
                        <strong className="text-rose-600">{validationChecks.scheduleError || "Invalid Window"}</strong>
                      )
                    ) : (
                      <strong className="text-rose-600">Start & Deadline required to publish</strong>
                    )}
                  </span>
                </div>
              </div>
            </div>

            {/* Paper Preview Card */}
            <div className="rounded-2xl border border-slate-200 bg-white p-6 sm:p-8 shadow-xs space-y-6">
              {/* Paper Header Banner */}
              <div className="text-center border-b border-slate-100 pb-6 space-y-2">
                <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-700">
                  {facultyDept} Department
                </span>
                <h1 className="text-2xl font-bold text-slate-900">{examTitle || "Untitled Exam"}</h1>
                <p className="text-xs text-slate-500">
                  Duration: {duration} Minutes · Total Marks: {targetMarksNum} · Warnings Threshold: {maxWarnings}
                </p>
                <div className="flex items-center justify-center gap-4 text-xs font-medium text-slate-600 pt-2">
                  <span>Questions Shuffle: {shuffleQuestions ? "Enabled" : "Disabled"}</span>
                  <span>•</span>
                  <span>Options Shuffle: {shuffleOptions ? "Enabled" : "Disabled"}</span>
                  <span>•</span>
                  <span>Retakes: {allowRetakes ? "Allowed" : "Single Attempt"}</span>
                </div>
              </div>

              {/* Questions Preview */}
              <div className="space-y-6">
                {questions.map((q, idx) => (
                  <div key={q.id || idx} className="rounded-xl border border-slate-100 bg-slate-50/50 p-4 space-y-2">
                    <div className="flex items-center justify-between text-xs">
                      <span className="font-bold text-slate-900">Question {idx + 1}</span>
                      <span className="font-semibold text-slate-600">[{q.marks} Marks]</span>
                    </div>
                    <p className="text-sm text-slate-800">{q.text || (q as any).question}</p>
                    {q.options && q.options.length > 0 && (
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 pt-2 text-xs">
                        {q.options.map((opt, oIdx) => {
                          const isCorrect = (q.correct_answer != null && String(q.correct_answer).trim().toLowerCase() === String(opt).trim().toLowerCase()) ||
                                            ((q as any).answer != null && String((q as any).answer).trim().toLowerCase() === String(opt).trim().toLowerCase());
                          return (
                            <div
                              key={oIdx}
                              className={`flex items-center gap-2 rounded-xl px-3 py-2 border transition-all ${
                                isCorrect
                                  ? "bg-emerald-50/90 border-emerald-300 text-emerald-900 font-semibold shadow-2xs"
                                  : "bg-white border-slate-200 text-slate-700"
                              }`}
                            >
                              <span className={`flex h-5 w-5 shrink-0 items-center justify-center rounded-md text-[10px] font-bold ${
                                isCorrect ? "bg-emerald-600 text-white" : "bg-slate-100 text-slate-600"
                              }`}>
                                {isCorrect ? <Check className="h-3 w-3" /> : String.fromCharCode(65 + oIdx)}
                              </span>
                              <span className="truncate flex-1">{opt}</span>
                              {isCorrect && (
                                <span className="text-[10px] font-bold text-emerald-700 uppercase tracking-wider shrink-0 bg-emerald-100/80 px-1.5 py-0.5 rounded-sm">
                                  Answer
                                </span>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    )}
                    {(q.model_answer || (q as any).answer) && q.question_type?.toLowerCase() !== "mcq" && (
                      <div className="mt-2.5 rounded-xl border border-slate-200/90 bg-slate-50/80 p-3 text-xs space-y-1">
                        <div className="flex items-center gap-1.5 font-bold text-slate-700">
                          <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600" />
                          <span>Evaluation Guide / Model Answer:</span>
                        </div>
                        <p className="text-slate-600 leading-relaxed whitespace-pre-wrap">{q.model_answer || (q as any).answer}</p>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>

            {/* Step 4 Actions */}
            <div className="flex flex-wrap items-center justify-between gap-3 pt-4 border-t border-slate-100">
              <button
                type="button"
                onClick={() => setCurrentStep(3)}
                className="inline-flex items-center gap-2 rounded-xl border border-slate-200 px-5 py-2.5 text-sm font-semibold text-slate-700 hover:bg-slate-50"
              >
                <ArrowLeft className="h-4 w-4" /> Back to Settings
              </button>

              <div className="flex items-center gap-2 flex-wrap">
                <button
                  type="button"
                  onClick={handleExportPdf}
                  className="inline-flex items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-3.5 py-2.5 text-xs font-semibold text-slate-700 hover:bg-slate-50 shadow-2xs transition-colors"
                  title="Download Question Paper and Answer Key as PDF"
                >
                  <Download className="h-3.5 w-3.5 text-blue-600" />
                  Export PDF
                </button>
                <button
                  type="button"
                  onClick={handleExportDocx}
                  className="inline-flex items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-3.5 py-2.5 text-xs font-semibold text-slate-700 hover:bg-slate-50 shadow-2xs transition-colors"
                  title="Download Question Paper and Answer Key as Word Document"
                >
                  <FileText className="h-3.5 w-3.5 text-indigo-600" />
                  Export DOCX
                </button>
                <button
                  type="button"
                  onClick={handleSaveAsDraft}
                  className="rounded-xl border border-slate-200 bg-white px-5 py-2.5 text-sm font-semibold text-slate-700 hover:bg-slate-50 shadow-2xs"
                >
                  Save as Draft
                </button>
                <button
                  type="button"
                  disabled={!validationChecks.canPublish || isPublishing}
                  onClick={handlePublishExam}
                  className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-emerald-600 to-teal-600 px-6 py-2.5 text-sm font-bold text-white shadow-md hover:from-emerald-700 hover:to-teal-700 disabled:opacity-50 transition-all"
                >
                  <Send className="h-4 w-4" /> {isPublishing ? "Publishing..." : "Publish Exam"}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Modal: Author Question Manually */}
        {showManualModal && (
          <div className="fixed inset-0 z-50 grid place-items-center bg-slate-950/60 p-4 backdrop-blur-xs">
            <div className="w-full max-w-lg rounded-3xl bg-white p-6 sm:p-7 shadow-2xl border border-slate-200 space-y-4 max-h-[90vh] overflow-y-auto">
              <div className="flex items-center justify-between border-b border-slate-100 pb-3">
                <h3 className="text-base font-bold text-slate-900">Add Question Manually</h3>
                <button
                  type="button"
                  onClick={() => setShowManualModal(false)}
                  className="rounded-lg p-1 text-slate-400 hover:text-slate-600"
                >
                  <X className="h-5 w-5" />
                </button>
              </div>

              <div className="space-y-4 text-xs sm:text-sm">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Question Type</label>
                  <select
                    value={manualQType}
                    onChange={(e) => setManualQType(e.target.value as keyof BlueprintState)}
                    className="w-full rounded-xl border border-slate-200 bg-white px-3.5 py-2 text-sm font-medium"
                  >
                    <option value="mcq">Multiple Choice (Single Option)</option>
                    <option value="true_false">True / False</option>
                    <option value="fill_blank">Fill in the Blank</option>
                    <option value="short_answer">Short Answer (2-3 sentences)</option>
                    <option value="long_answer">Long Answer / Essay</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Question Text * {manualQType === "fill_blank" && <span className="text-blue-600 font-normal">(use ____ with 4 underscores for blanks)</span>}
                  </label>
                  <textarea
                    rows={3}
                    value={manualQText}
                    onChange={(e) => setManualQText(e.target.value)}
                    placeholder={manualQType === "fill_blank" ? "e.g., Photosynthesis converts light energy into ____ energy." : "Enter the question prompt..."}
                    className="w-full rounded-xl border border-slate-200 bg-slate-50/50 p-3 text-sm focus:bg-white"
                  />
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-semibold text-slate-700 mb-1">Marks</label>
                    <input
                      type="number"
                      min="0.5"
                      step="0.5"
                      value={manualQMarks}
                      onChange={(e) => setManualQMarks(e.target.value)}
                      className="w-full rounded-xl border border-slate-200 bg-white px-3.5 py-2 text-sm"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-slate-700 mb-1">Difficulty</label>
                    <select
                      value={manualQDiff}
                      onChange={(e) => setManualQDiff(e.target.value as any)}
                      className="w-full rounded-xl border border-slate-200 bg-white px-3.5 py-2 text-sm"
                    >
                      <option value="easy">Easy</option>
                      <option value="medium">Medium</option>
                      <option value="hard">Hard</option>
                    </select>
                  </div>
                </div>

                {manualQType === "mcq" && (
                  <div className="space-y-2">
                    <label className="block text-xs font-semibold text-slate-700">Options (A, B, C, D)</label>
                    {manualQOptions.map((opt, oIdx) => (
                      <div key={oIdx} className="flex items-center gap-2">
                        <span className="w-5 text-xs font-bold text-slate-400">{String.fromCharCode(65 + oIdx)}.</span>
                        <input
                          type="text"
                          value={opt}
                          onChange={(e) => {
                            const next = [...manualQOptions];
                            next[oIdx] = e.target.value;
                            setManualQOptions(next);
                          }}
                          placeholder={`Option ${String.fromCharCode(65 + oIdx)} text`}
                          className="w-full rounded-xl border border-slate-200 bg-white px-3 py-1.5 text-sm"
                        />
                      </div>
                    ))}
                    <div className="pt-2">
                      <label className="block text-xs font-semibold text-slate-700 mb-1">Correct Option (Letter or Exact Text)</label>
                      <input
                        type="text"
                        value={manualQAnswer}
                        onChange={(e) => setManualQAnswer(e.target.value)}
                        placeholder="e.g., A"
                        className="w-full rounded-xl border border-slate-200 bg-white px-3.5 py-2 text-sm"
                      />
                    </div>
                  </div>
                )}

                {manualQType === "true_false" && (
                  <div>
                    <label className="block text-xs font-semibold text-slate-700 mb-2">Correct Answer</label>
                    <div className="flex gap-4">
                      {["True", "False"].map((opt) => (
                        <label key={opt} className={`flex items-center gap-2 px-4 py-2 rounded-xl border cursor-pointer ${manualQAnswer === opt || (!manualQAnswer && opt === "True") ? "border-blue-600 bg-blue-50 text-blue-800 font-bold" : "border-slate-200 text-slate-700"}`}>
                          <input
                            type="radio"
                            name="tfAnswer"
                            value={opt}
                            checked={manualQAnswer === opt || (!manualQAnswer && opt === "True")}
                            onChange={() => setManualQAnswer(opt)}
                            className="sr-only"
                          />
                          <span>{opt}</span>
                        </label>
                      ))}
                    </div>
                  </div>
                )}

                {manualQType === "fill_blank" && (
                  <div>
                    <label className="block text-xs font-semibold text-slate-700 mb-1">Accepted Answers (Synonyms comma-separated)</label>
                    <input
                      type="text"
                      value={manualQAcceptedAnswers}
                      onChange={(e) => {
                        setManualQAcceptedAnswers(e.target.value);
                        setManualQAnswer(e.target.value);
                      }}
                      placeholder="e.g., chemical, chemical energy"
                      className="w-full rounded-xl border border-slate-200 bg-white px-3.5 py-2 text-sm"
                    />
                    <p className="text-[11px] text-slate-400 mt-1">Student entries will be trimmed and evaluated case-insensitively.</p>
                  </div>
                )}

                {(manualQType === "short_answer" || manualQType === "long_answer") && (
                  <div className="space-y-3">
                    <div>
                      <label className="block text-xs font-semibold text-slate-700 mb-1">Expected Model Answer *</label>
                      <textarea
                        rows={3}
                        value={manualQModelAnswer}
                        onChange={(e) => setManualQModelAnswer(e.target.value)}
                        placeholder="Core concepts, key formulas, or expected explanations..."
                        className="w-full rounded-xl border border-slate-200 bg-slate-50/50 p-3 text-sm focus:bg-white"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-semibold text-slate-700 mb-1">Grading Rubric / Criteria</label>
                      <textarea
                        rows={2}
                        value={manualQRubric}
                        onChange={(e) => setManualQRubric(e.target.value)}
                        placeholder="e.g. 2 marks for naming mechanism, 3 marks for diagram/steps"
                        className="w-full rounded-xl border border-slate-200 bg-slate-50/50 p-3 text-sm focus:bg-white"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-semibold text-slate-700 mb-1">Word Limit (Optional)</label>
                      <input
                        type="number"
                        min="10"
                        value={manualQWordLimit}
                        onChange={(e) => setManualQWordLimit(e.target.value)}
                        placeholder={manualQType === "short_answer" ? "e.g., 50 words" : "e.g., 250 words"}
                        className="w-full rounded-xl border border-slate-200 bg-white px-3.5 py-2 text-sm"
                      />
                    </div>
                  </div>
                )}
              </div>

              <div className="flex justify-end gap-2.5 pt-3 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setShowManualModal(false)}
                  className="rounded-xl border border-slate-200 px-4 py-2 text-xs sm:text-sm font-semibold text-slate-700 hover:bg-slate-50"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={handleSaveManualQuestion}
                  className="rounded-xl bg-blue-600 px-5 py-2 text-xs sm:text-sm font-bold text-white shadow-sm hover:bg-blue-700"
                >
                  Add Question
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Content Capacity Advisory Modal */}
        {capacityAdvisory && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4 animate-in fade-in duration-150">
            <div className="bg-white rounded-3xl border border-border shadow-2xl w-full max-w-lg p-6 space-y-5 animate-in zoom-in-95 duration-150">
              <div className="flex items-center justify-between border-b border-border pb-3">
                <div className="flex items-center gap-2.5">
                  <div className="p-2.5 rounded-2xl bg-amber-100 text-amber-800">
                    <AlertTriangle className="h-5 w-5" />
                  </div>
                  <div>
                    <h3 className="font-bold text-base text-foreground">Content Capacity Advisory</h3>
                    <p className="text-xs text-muted-foreground">Source syllabus cannot support requested marks without duplication</p>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => setCapacityAdvisory(null)}
                  className="rounded-lg p-1 text-muted-foreground hover:text-foreground"
                >
                  <X className="h-5 w-5" />
                </button>
              </div>

              <div className="rounded-2xl bg-amber-50/80 border border-amber-200 p-4 space-y-3 text-xs">
                <p className="text-amber-950 leading-relaxed font-medium">
                  {capacityAdvisory.detail}
                </p>
                <div className="grid grid-cols-3 gap-2 pt-2 border-t border-amber-200/80 text-center">
                  <div className="rounded-xl bg-white/80 p-2 border border-amber-200/60">
                    <div className="text-[10px] text-muted-foreground font-semibold">Requested</div>
                    <div className="text-sm font-bold text-foreground">{capacityAdvisory.requested_target_marks} M</div>
                  </div>
                  <div className="rounded-xl bg-white/80 p-2 border border-amber-200/60">
                    <div className="text-[10px] text-muted-foreground font-semibold">Max Supportable</div>
                    <div className="text-sm font-bold text-emerald-700">{capacityAdvisory.max_supportable_marks} M</div>
                  </div>
                  <div className="rounded-xl bg-white/80 p-2 border border-amber-200/60">
                    <div className="text-[10px] text-muted-foreground font-semibold">Deficit</div>
                    <div className="text-sm font-bold text-amber-800">{capacityAdvisory.deficit_marks} M</div>
                  </div>
                </div>
              </div>

              <div className="space-y-2 pt-1">
                <button
                  type="button"
                  onClick={() => {
                    const proposedMarks = capacityAdvisory.max_supportable_marks;
                    const proposedBp = capacityAdvisory.proposed_adjusted_blueprint;
                    setTotalMarks(String(proposedMarks));
                    if (proposedBp) {
                      setBlueprint((prev: any) => {
                        const updated = { ...prev };
                        Object.keys(proposedBp).forEach((k) => {
                          if (updated[k]) {
                            updated[k] = { ...updated[k], ...proposedBp[k] };
                          }
                        });
                        return updated;
                      });
                    }
                    setCapacityAdvisory(null);
                    toast.info(`Adjusted blueprint target to ${proposedMarks} marks. Click Generate to proceed.`);
                  }}
                  className="w-full flex items-center justify-center gap-2 rounded-xl bg-emerald-700 px-4 py-2.5 text-xs font-bold text-white shadow-xs hover:bg-emerald-800 transition-all"
                >
                  <Check className="h-4 w-4" />
                  Accept Proposed Blueprint ({capacityAdvisory.max_supportable_marks} Marks)
                </button>
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => {
                      setCapacityAdvisory(null);
                      handleAiGenerate(true);
                    }}
                    className="flex-1 rounded-xl border border-border bg-slate-100 px-3.5 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-200 transition-all"
                  >
                    Proceed Anyway (Override)
                  </button>
                  <button
                    type="button"
                    onClick={() => setCapacityAdvisory(null)}
                    className="flex-1 rounded-xl border border-border bg-white px-3.5 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50 transition-all"
                  >
                    Edit Syllabus Material
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Real-time Generation Progress / Status Modal */}
        <GenerationProgressModal
          jobId={activeJobId}
          isOpen={showProgressModal}
          onClose={() => {
            setShowProgressModal(false);
            setActiveJobId(null);
          }}
          onSuccess={handleGenerationSuccess}
          onReset={() => {
            clearScopedWizardDraft(currentUser?.id);
            const nextSched = getNextRoundScheduleWindow();
            setExamTitle("");
            setSubjectName("");
            setDuration("60");
            setTotalMarks("100");
            setStartsAt(nextSched.startsAt);
            setEndsAt(nextSched.endsAt);
            setTopics([]);
            setSyllabusFile(null);
            setParsedSyllabus(null);
            setQuestions([]);
            setExamId(null);
            setActiveJobId(null);
            setCurrentStep(1);
            setDetectedDraft(null);
            setShowDraftBanner(false);
            setIsDirty(false);
          }}
          onChangeModel={() => {
            setShowProgressModal(false);
            setCurrentStep(1);
          }}
        />
      </div>
    </DashboardLayout>
  );
}

import axios from "axios";
import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { DashboardLayout } from "../components/DashboardLayout";
import {
  AlertCircle,
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
  Download,
  FileCheck,
  FileText,
  FileUp,
  HelpCircle,
  History,
  Layers,
  LayoutDashboard,
  ListChecks,
  Lock,
  Plus,
  RefreshCw,
  Send,
  Settings,
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
  facultyExamApi,
  facultyPaperApi,
  facultyProfileApi,
  generationApi,
  type AiModel,
  type ExamQuestion,
  type FacultyExam,
  type PaperGenerationJob,
  type PaperQuestionType,
  type SyllabusUploadData,
} from "../../services/api";

const menuItems = [
  { icon: LayoutDashboard, label: "Dashboard", path: "/faculty" },
  { icon: FileText, label: "Generate Paper", path: "/faculty/generate" },
  { icon: History, label: "Exam History", path: "/faculty/history" },
  { icon: Settings, label: "Settings", path: "/faculty/settings" },
];

const aiModels: AiModel[] = ["qwen2.5-3b", "llama3.2-3b", "phi3-mini"];
const aiModelLabels: Record<AiModel, string> = {
  "qwen2.5-3b": "Qwen 2.5 3B (Recommended - Local)",
  "llama3.2-3b": "Llama 3.2 3B (Local)",
  "phi3-mini": "Phi-3 Mini (Local)",
};

import {
  type BlueprintTypeConfig,
  type BlueprintState,
  computeBlueprintTotal,
  allocateBlueprintToTarget,
  rebalanceBlueprintToTarget,
  balanceBlueprintSmallestChange,
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
  return fallback;
}

export function FacultyGeneratePaper() {
  const navigate = useNavigate();

  // Load persisted wizard draft from localStorage if available
  const savedWizardDraft = useMemo(() => {
    try {
      const raw = localStorage.getItem("examai_faculty_wizard_draft");
      return raw ? JSON.parse(raw) : null;
    } catch {
      return null;
    }
  }, []);

  // Wizard Step (1: Details, 2: Questions, 3: Settings, 4: Preview & Publish)
  const [currentStep, setCurrentStep] = useState<1 | 2 | 3 | 4>(() => {
    const s = savedWizardDraft?.currentStep;
    return s && s >= 1 && s <= 4 ? (s as 1 | 2 | 3 | 4) : 1;
  });

  // Profile
  const [facultyDept, setFacultyDept] = useState("");
  const [loadingProfile, setLoadingProfile] = useState(true);

  // Step 1: Details
  const [examTitle, setExamTitle] = useState(() => savedWizardDraft?.examTitle || "");
  const [subjectName, setSubjectName] = useState(() => savedWizardDraft?.subjectName || "");
  const [duration, setDuration] = useState(() => savedWizardDraft?.duration || "60");
  const [totalMarks, setTotalMarks] = useState(() => savedWizardDraft?.totalMarks || "100");
  const [startsAt, setStartsAt] = useState(() => savedWizardDraft?.startsAt || "");
  const [endsAt, setEndsAt] = useState(() => savedWizardDraft?.endsAt || "");
  const [topics, setTopics] = useState<string[]>(() => savedWizardDraft?.topics || [""]);

  // Step 2: Question Blueprint Studio & Syllabus
  const [examId, setExamId] = useState<number | null>(() => savedWizardDraft?.examId || null);
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
  const [aiModel, setAiModel] = useState<AiModel>("qwen2.5-3b");
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
  const [maxWarnings, setMaxWarnings] = useState("3");
  const [allowRetakes, setAllowRetakes] = useState(false);
  const [showResultImmediately, setShowResultImmediately] = useState(true);

  // Step 4: Publish state
  const [isPublishing, setIsPublishing] = useState(false);
  const [savingDraft, setSavingDraft] = useState(false);

  // Active Job and Real-time Modal
  const [activeJobId, setActiveJobId] = useState<number | null>(null);
  const [showProgressModal, setShowProgressModal] = useState(false);

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

  // Autosave wizard inputs to localStorage so refresh or back/forward does not lose schedule
  useEffect(() => {
    try {
      localStorage.setItem(
        "examai_faculty_wizard_draft",
        JSON.stringify({
          currentStep,
          examTitle,
          subjectName,
          duration,
          totalMarks,
          startsAt,
          endsAt,
          topics,
          examId,
        })
      );
    } catch {}
  }, [currentStep, examTitle, subjectName, duration, totalMarks, startsAt, endsAt, topics, examId]);

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
      notes.forEach((n) => toast.info(n));
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

  const handleSyllabusFileSelected = async (file: File) => {
    setSyllabusFile(file);
    setIsParsingSyllabus(true);
    try {
      const res = await facultyPaperApi.parseSyllabus(file);
      setParsedSyllabus(res);
      // Clean reset: populate topics strictly with newly uploaded document's detected units
      // This prevents cross-exam state pollution (e.g., mixing Java and OS topics)
      if (res.topics && res.topics.length > 0) {
        setTopics(res.topics);
      }
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
    } finally {
      setIsParsingSyllabus(false);
    }
  };

  const handleAddTopic = () => setTopics([...topics, ""]);
  const handleRemoveTopic = (idx: number) => setTopics(topics.filter((_, i) => i !== idx));
  const handleTopicChange = (idx: number, val: string) => {
    const next = [...topics];
    next[idx] = val;
    setTopics(next);
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

  // Step 1 Validation
  const validateStep1 = () => {
    if (!examTitle.trim()) return "Exam Title is required.";
    const dur = Number(duration);
    if (isNaN(dur) || dur <= 0) return "Duration must be greater than 0.";
    const tm = Number(totalMarks);
    if (isNaN(tm) || tm < 1 || tm > 500) return "Target Total Marks must be an integer between 1 and 500.";
    if (cleanTopics.length === 0) return "At least one topic is required.";
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
        notes.forEach((n) => toast.info(n));
      }
    } else if (lastConfirmedTargetMarks !== currentTarget && bpTotal !== currentTarget) {
      setRebalancePrompt({ open: true, oldTarget: lastConfirmedTargetMarks, newTarget: currentTarget });
    }
    setCurrentStep(2);
  };

  // AI Generation in Step 2
  const handleAiGenerate = async () => {
    if (!examTitle.trim()) {
      toast.error("Please enter an exam title in Step 1.");
      return;
    }

    if (blueprintSummary.blueprintMarks !== targetMarksNum) {
      toast.error(
        `Blueprint total marks (${blueprintSummary.blueprintMarks}) do not match target marks (${targetMarksNum}). Please balance your blueprint before generating.`
      );
      return;
    }

    const activeBlueprint: Record<string, { count: number; marks: number }> = {};
    const activeTypes: string[] = [];
    (Object.keys(blueprint) as (keyof BlueprintState)[]).forEach((typeKey) => {
      if (blueprint[typeKey].enabled && blueprint[typeKey].count > 0) {
        activeBlueprint[typeKey] = {
          count: blueprint[typeKey].count,
          marks: blueprint[typeKey].marks,
        };
        activeTypes.push(typeKey);
      }
    });

    if (activeTypes.length === 0) {
      toast.error("Please enable and configure at least one question type in the blueprint.");
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

    setIsGenerating(true);
    setGenerationProgress(25);

    try {
      setGenerationProgress(50);
      const res = await facultyPaperApi.generateExam({
        title: examTitle.trim(),
        durationMinutes: Number(duration),
        totalMarks: Number(totalMarks),
        topics: cleanTopics.length ? cleanTopics : (parsedSyllabus?.topics?.length ? parsedSyllabus.topics : ["Core Syllabus"]),
        questionTypes: activeTypes,
        difficultyDistribution: diffDistribution,
        blueprint: activeBlueprint,
        aiModel,
        syllabus: syllabusFile,
        avoidRepeats,
        subject: subjectName.trim() || undefined,
        selectedTopics: cleanTopics.length ? cleanTopics : undefined,
        starts_at: startsAt ? new Date(startsAt).toISOString() : null,
        ends_at: endsAt ? new Date(endsAt).toISOString() : null,
        display_timezone: "Asia/Kolkata",
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
      if (err?.response?.status === 409 && err?.response?.data?.active_job_id) {
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

  const handleGenerationSuccess = async (job: PaperGenerationJob) => {
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
          max_warnings: Number(maxWarnings) || 3,
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
        max_warnings: Number(maxWarnings) || 3,
        allow_retakes: allowRetakes,
        show_result_immediately: showResultImmediately,
        starts_at: startsAt ? new Date(startsAt).toISOString() : null,
        ends_at: endsAt ? new Date(endsAt).toISOString() : null,
        display_timezone: "Asia/Kolkata",
      });

      const published = await facultyExamApi.publishExam(examId);
      try {
        localStorage.removeItem("examai_faculty_wizard_draft");
      } catch {}
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
      <div className="mx-auto max-w-6xl space-y-6 pb-20">
        {/* Title & Subtitle */}
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold text-slate-900">Faculty Paper Generation Wizard</h1>
          <p className="text-xs sm:text-sm text-slate-500">
            Design, curate, proctor, and publish exams with intelligent assistance
          </p>
        </div>

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
          <div className="rounded-2xl border border-slate-200 bg-white p-6 sm:p-8 shadow-xs space-y-6">
            <div className="border-b border-slate-100 pb-4">
              <h2 className="text-lg font-bold text-slate-900">Step 1: Exam Details & Schedule</h2>
              <p className="text-xs text-slate-500">Provide basic assessment parameters and scheduling window</p>
            </div>

            <div className="grid gap-5 sm:grid-cols-2">
              {/* Exam Title */}
              <div className="sm:col-span-2">
                <label className="block text-xs font-semibold text-slate-700 mb-1.5">Exam Title *</label>
                <input
                  type="text"
                  value={examTitle}
                  onChange={(e) => setExamTitle(e.target.value)}
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

              {/* Subject */}
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1.5">Subject / Course Name</label>
                <input
                  type="text"
                  value={subjectName}
                  onChange={(e) => setSubjectName(e.target.value)}
                  placeholder="e.g., CS-402 Network Protocols"
                  className="w-full rounded-xl border border-slate-200 bg-slate-50/50 px-4 py-2.5 text-sm focus:border-blue-500 focus:bg-white focus:outline-hidden focus:ring-2 focus:ring-blue-500/20 transition-all"
                />
              </div>

              {/* Duration */}
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1.5">Duration (Minutes) *</label>
                <div className="relative">
                  <input
                    type="number"
                    min="1"
                    value={duration}
                    onChange={(e) => setDuration(e.target.value)}
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
                  onChange={(e) => setTotalMarks(e.target.value)}
                  className="w-full rounded-xl border border-slate-200 bg-slate-50/50 px-4 py-2.5 text-sm focus:border-blue-500 focus:bg-white focus:outline-hidden focus:ring-2 focus:ring-blue-500/20 transition-all"
                />
              </div>

              {/* Starts At */}
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1.5">Available From (Start Time) *</label>
                <div className="relative">
                  <input
                    type="datetime-local"
                    value={startsAt}
                    onChange={(e) => setStartsAt(e.target.value)}
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
                    onChange={(e) => setEndsAt(e.target.value)}
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
                  <label className="block text-xs font-semibold text-slate-700">Syllabus Topics *</label>
                  <button
                    type="button"
                    onClick={handleAddTopic}
                    className="inline-flex items-center gap-1 text-xs font-semibold text-blue-600 hover:text-blue-700"
                  >
                    <Plus className="h-3.5 w-3.5" /> Add Topic
                  </button>
                </div>
                <div className="space-y-2">
                  {topics.map((t, idx) => (
                    <div key={idx} className="flex items-center gap-2">
                      <input
                        type="text"
                        value={t}
                        onChange={(e) => handleTopicChange(idx, e.target.value)}
                        placeholder={`Topic ${idx + 1} (e.g., OSI Layer 4 Transport Protocols)`}
                        className="w-full rounded-xl border border-slate-200 bg-slate-50/50 px-4 py-2 text-sm focus:border-blue-500 focus:bg-white focus:outline-hidden focus:ring-2 focus:ring-blue-500/20 transition-all"
                      />
                      {topics.length > 1 && (
                        <button
                          type="button"
                          onClick={() => handleRemoveTopic(idx)}
                          className="rounded-lg p-2 text-slate-400 hover:text-rose-600 hover:bg-rose-50"
                        >
                          <Trash2 className="h-4 w-4" />
                        </button>
                      )}
                    </div>
                  ))}
                </div>
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
                      if (notes.length > 0) notes.forEach((n) => toast.info(n));
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

            {/* Top Bar for Questions */}
            <div className="rounded-2xl border border-slate-200 bg-white p-5 sm:p-6 shadow-xs flex flex-wrap items-center justify-between gap-4">
              <div>
                <h2 className="text-lg font-bold text-slate-900">Step 2: Question Blueprint & Content Studio</h2>
                <p className="text-xs text-slate-500">
                  Configure question types, difficulty split, and upload syllabus source of truth
                </p>
              </div>

              <div className="flex items-center gap-3 flex-wrap">
                <button
                  type="button"
                  onClick={() => setShowManualModal(true)}
                  className="inline-flex items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-4 py-2 text-xs sm:text-sm font-semibold text-slate-700 hover:bg-slate-50 shadow-2xs"
                >
                  <Plus className="h-4 w-4" /> Add Manually
                </button>
                <div className="flex flex-col items-end gap-1">
                  <button
                    type="button"
                    disabled={isGenerating || blueprintSummary.blueprintMarks !== targetMarksNum}
                    onClick={handleAiGenerate}
                    className="inline-flex items-center gap-1.5 rounded-xl bg-gradient-to-r from-blue-600 to-indigo-600 px-5 py-2 text-xs sm:text-sm font-bold text-white shadow-md hover:from-blue-700 hover:to-indigo-700 disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer transition-all"
                  >
                    <Sparkles className="h-4 w-4" /> {isGenerating ? "Generating Paper..." : "Generate with AI"}
                  </button>
                  {blueprintSummary.blueprintMarks !== targetMarksNum && (
                    <span className="text-[11px] font-semibold text-amber-700 text-right">
                      Disabled: Blueprint ({blueprintSummary.blueprintMarks}m) does not match target ({targetMarksNum}m)
                    </span>
                  )}
                </div>
              </div>
            </div>

            {/* 1. Syllabus Source-of-Truth Box */}
            <div className="rounded-2xl border border-slate-200 bg-white p-5 sm:p-6 shadow-xs space-y-4">
              <div className="flex items-center justify-between flex-wrap gap-2 border-b border-slate-100 pb-3">
                <div className="flex items-center gap-2">
                  <FileText className="h-4 w-4 text-blue-600" />
                  <h3 className="text-sm font-bold text-slate-900">Syllabus Context (Source of Truth)</h3>
                </div>
                <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-emerald-700 bg-emerald-50 border border-emerald-200 px-2.5 py-0.5 rounded-full">
                  <Shield className="h-3 w-3" /> Questions synthesized strictly from syllabus
                </span>
              </div>

              {parsedSyllabus ? (
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
                            onClick={() => setTopics(parsedSyllabus.topics)}
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
                    </div>
                  )}
                </div>
              ) : (
                <div className="rounded-xl border-2 border-dashed border-slate-200 p-6 text-center hover:border-blue-400 transition-colors">
                  <div className="mx-auto flex h-10 w-10 items-center justify-center rounded-xl bg-blue-50 text-blue-600 mb-2">
                    {isParsingSyllabus ? <RefreshCw className="h-5 w-5 animate-spin" /> : <FileUp className="h-5 w-5" />}
                  </div>
                  <h4 className="text-sm font-semibold text-slate-800">
                    {isParsingSyllabus ? "Extracting and analyzing syllabus topics..." : "Upload Syllabus Document"}
                  </h4>
                  <p className="text-xs text-slate-500 mt-1 max-w-md mx-auto">
                    Drag and drop your syllabus PDF, DOCX, or text file. The AI model extracts core units and guarantees questions strictly align with the syllabus.
                  </p>
                  <label className="mt-4 inline-flex items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-4 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50 cursor-pointer shadow-2xs">
                    <Upload className="h-3.5 w-3.5" /> Browse File
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
                </div>
              )}
            </div>

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
                      className={`flex flex-col sm:flex-row sm:items-center justify-between gap-4 rounded-xl border p-4 transition-all ${
                        cfg.enabled
                          ? "border-slate-300 bg-slate-50/50 shadow-2xs"
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
              <div className="grid gap-4 sm:grid-cols-4 items-center">
                {/* Total Questions */}
                <div className="rounded-xl border border-slate-200 bg-slate-50 p-3">
                  <span className="text-[11px] text-slate-500 font-medium block">Total Questions</span>
                  <strong className="text-base text-slate-900 font-bold">{blueprintSummary.totalQuestions} Questions</strong>
                </div>

                {/* Target Marks vs Blueprint Marks */}
                <div className="rounded-xl border border-slate-200 bg-slate-50 p-3 sm:col-span-2">
                  <div className="flex items-center justify-between">
                    <span className="text-[11px] text-slate-500 font-medium">Marks Status</span>
                    {blueprintSummary.blueprintMarks === targetMarksNum ? (
                      <span className="inline-flex items-center gap-1 text-[11px] font-bold text-emerald-700">
                        <CheckCircle2 className="h-3.5 w-3.5" /> Perfect Match
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 text-[11px] font-bold text-amber-700">
                        <AlertCircle className="h-3.5 w-3.5" /> Mismatch
                      </span>
                    )}
                  </div>
                  <div className="flex items-baseline gap-2 mt-0.5">
                    <strong className={`text-base font-bold ${blueprintSummary.blueprintMarks === targetMarksNum ? "text-emerald-700" : "text-amber-700"}`}>
                      {blueprintSummary.blueprintMarks}
                    </strong>
                    <span className="text-xs text-slate-500">/ {targetMarksNum} Target Marks</span>
                  </div>
                </div>

                {/* Local AI Model Dropdown */}
                <div className="rounded-xl border border-slate-200 bg-slate-50 p-3">
                  <span className="text-[11px] text-slate-500 font-medium block mb-1">Local AI Engine</span>
                  <select
                    value={aiModel}
                    onChange={(e) => setAiModel(e.target.value as AiModel)}
                    className="w-full text-xs font-semibold bg-white border border-slate-200 rounded-lg px-2 py-1 focus:outline-hidden"
                  >
                    {aiModels.map((m) => (
                      <option key={m} value={m}>
                        {m}
                      </option>
                    ))}
                  </select>
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
                    <RefreshCw className="h-3 w-3" /> Balance to {targetMarksNum} Marks
                  </button>
                </div>
              )}
            </div>

            {/* 5. Generated Questions List (if any exist) */}
            {questions.length > 0 && (
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <h3 className="text-base font-bold text-slate-900">
                    Active Questions ({questions.length}) · Total Marks: {currentTotalMarks}
                  </h3>
                  <span className="text-xs text-slate-500">Review, reorder or modify generated questions below</span>
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
                        <p className="text-sm font-medium text-slate-800 leading-snug">{q.text}</p>
                        {q.options && q.options.length > 0 && (
                          <div className="grid grid-cols-2 gap-1.5 pt-1 text-xs text-slate-600">
                            {q.options.map((opt, oIdx) => (
                              <div key={oIdx} className="truncate">
                                <span className="font-semibold text-slate-400 mr-1.5">{String.fromCharCode(65 + oIdx)}.</span>
                                {opt}
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Actions: Move Up, Move Down, Delete */}
                    <div className="flex items-center gap-1.5 shrink-0">
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
                  Allowed proctoring infractions (fullscreen exit, tab switch). Exceeding this limit immediately terminates and auto-submits.
                </p>
                <div className="relative">
                  <input
                    type="number"
                    min="1"
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
                    <p className="text-sm text-slate-800">{q.text}</p>
                    {q.options && q.options.length > 0 && (
                      <div className="grid grid-cols-2 gap-2 pt-2 text-xs text-slate-600">
                        {q.options.map((opt, oIdx) => (
                          <div key={oIdx} className="rounded-lg bg-white p-2 border border-slate-200">
                            <span className="font-bold text-slate-400 mr-2">{String.fromCharCode(65 + oIdx)}.</span>
                            {opt}
                          </div>
                        ))}
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

              <div className="flex items-center gap-3">
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

        {/* Real-time Generation Progress / Status Modal */}
        <GenerationProgressModal
          jobId={activeJobId}
          isOpen={showProgressModal}
          onClose={() => setShowProgressModal(false)}
          onSuccess={handleGenerationSuccess}
          onReset={() => {
            try {
              localStorage.removeItem("examai_faculty_wizard_draft");
            } catch {}
            setQuestions([]);
            setExamId(null);
            setActiveJobId(null);
            setCurrentStep(1);
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

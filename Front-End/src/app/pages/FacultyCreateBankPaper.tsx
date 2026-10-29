import React, { useState, useEffect, useMemo, useCallback } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import {
  AlertCircle,
  ArrowLeft,
  ArrowRight,
  Check,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Clock,
  Calendar,
  Database,
  Download,
  ExternalLink,
  FileCheck2,
  FileText,
  FileUp,
  FolderOpen,
  HelpCircle,
  Layers,
  Loader2,
  Minus,
  Plus,
  RefreshCw,
  RotateCcw,
  Search,
  Send,
  Sparkles,
  UploadCloud,
} from "lucide-react";
import { toast } from "sonner";
import { DashboardLayout } from "../components/DashboardLayout";
import {
  facultyExamApi,
  facultyQuestionBankApi,
  facultySubjectApi,
  type FacultyQuestionBankItem,
  type FacultySubject,
  type QuestionBankUploadResponse,
} from "../../services/api";

type Step = 1 | 2 | 3 | 4;

interface TypeBlueprint {
  type: string;
  label: string;
  availableCount: number;
  selectedCount: number;
  marksPerQuestion: number;
}

interface QuestionBankSummary {
  id: number | string;
  name: string;
  code?: string;
  department?: string;
  question_count: number;
}

export interface FacultyCreateBankPaperProps {
  hideLayout?: boolean;
}

export function FacultyCreateBankPaper({ hideLayout = false }: FacultyCreateBankPaperProps = {}) {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const draftIdParam = searchParams.get("draft_id") || searchParams.get("exam_id");

  // Current Stepper Step
  const [currentStep, setCurrentStep] = useState<Step>(1);

  // Step 1: Exam Details & Schedule (Starts empty for new papers)
  const [title, setTitle] = useState("");
  const [subject, setSubject] = useState("");
  const [durationMinutes, setDurationMinutes] = useState<string>("60");
  const [targetMarks, setTargetMarks] = useState(50);
  const [startsAt, setStartsAt] = useState("");
  const [endsAt, setEndsAt] = useState("");
  const [shuffleQuestions, setShuffleQuestions] = useState(true);
  const [shuffleOptions, setShuffleOptions] = useState(true);

  // Subject Management
  const [subjectsList, setSubjectsList] = useState<FacultySubject[]>([]);
  const [loadingSubjects, setLoadingSubjects] = useState(false);
  const [selectedSubjectId, setSelectedSubjectId] = useState<number | string>("");
  const [uploadTargetSubjectId, setUploadTargetSubjectId] = useState<number | string>("");
  const [isCreatingSubject, setIsCreatingSubject] = useState(false);
  const [newSubjectName, setNewSubjectName] = useState("");
  const [newSubjectCode, setNewSubjectCode] = useState("");
  const [creatingSubjectLoading, setCreatingSubjectLoading] = useState(false);

  // Step 2: Question Bank Selection & Upload
  const [availableBanks, setAvailableBanks] = useState<QuestionBankSummary[]>([]);
  const [loadingBanksList, setLoadingBanksList] = useState(false);
  const [selectedBankId, setSelectedBankId] = useState<number | string | null>(null);

  const [bankQuestions, setBankQuestions] = useState<FacultyQuestionBankItem[]>([]);
  const [loadingBank, setLoadingBank] = useState(false);
  const [uploadingFile, setUploadingFile] = useState(false);
  const [uploadProgress, setUploadProgress] = useState<string | null>(null);

  // Step 3: Blueprint & Question Selection
  const [typeBlueprints, setTypeBlueprints] = useState<Record<string, TypeBlueprint>>({});
  const [selectionMode, setSelectionMode] = useState<"blueprint" | "manual">("blueprint");
  const [selectedQuestionIds, setSelectedQuestionIds] = useState<Set<number>>(new Set());
  const [manualSearch, setManualSearch] = useState("");
  const [manualTypeFilter, setManualTypeFilter] = useState("all");
  const [manualPage, setManualPage] = useState(1);
  const manualPageSize = 10;

  // Step 4: Assembled Paper & Publishing
  const [assembling, setAssembling] = useState(false);
  const [assembledExamId, setAssembledExamId] = useState<number | null>(null);
  const [assembledSummary, setAssembledSummary] = useState<any | null>(null);
  const [publishing, setPublishing] = useState(false);
  const [showPublishModal, setShowPublishModal] = useState(false);

  // Load subjects list for department
  const loadSubjects = useCallback(async () => {
    setLoadingSubjects(true);
    try {
      const res = await facultySubjectApi.getSubjects();
      const list = res.subjects || [];
      setSubjectsList(list);
      return list;
    } catch (err) {
      console.error("Failed to load subjects", err);
      return [];
    } finally {
      setLoadingSubjects(false);
    }
  }, []);

  useEffect(() => {
    loadSubjects();
  }, [loadSubjects]);

  const handleCreateSubject = async () => {
    const trimmedName = newSubjectName.trim();
    if (!trimmedName) {
      toast.error("Subject name is required.");
      return;
    }
    setCreatingSubjectLoading(true);
    try {
      const newSub = await facultySubjectApi.createSubject({
        name: trimmedName,
        code: newSubjectCode.trim() || undefined,
      });
      toast.success(`Subject "${newSub.name}" created successfully!`);
      await loadSubjects();
      setSelectedSubjectId(newSub.id);
      setUploadTargetSubjectId(newSub.id);
      setSubject(newSub.name);
      setIsCreatingSubject(false);
      setNewSubjectName("");
      setNewSubjectCode("");
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || "Failed to create subject.");
    } finally {
      setCreatingSubjectLoading(false);
    }
  };

  // Load available banks list on mount
  const loadAvailableBanks = useCallback(async () => {
    setLoadingBanksList(true);
    try {
      const res = await facultyQuestionBankApi.getBanks();
      setAvailableBanks(res.banks || []);
    } catch (err: any) {
      console.error("Failed to load question banks", err);
    } finally {
      setLoadingBanksList(false);
    }
  }, []);

  useEffect(() => {
    loadAvailableBanks();
  }, [loadAvailableBanks]);

  // Load existing draft if draft_id query parameter is present (preserves saved title)
  useEffect(() => {
    if (draftIdParam) {
      const loadDraft = async () => {
        try {
          const exam = await facultyExamApi.getExam(Number(draftIdParam));
          if (exam) {
            setTitle(exam.title || "");
            setSubject(exam.subject || "");
            if (exam.duration_minutes) setDurationMinutes(String(exam.duration_minutes));
            if (exam.target_total_marks || exam.total_marks) {
              setTargetMarks(exam.target_total_marks || exam.total_marks);
            }
            if (exam.starts_at) setStartsAt(exam.starts_at);
            if (exam.ends_at) setEndsAt(exam.ends_at);
            setAssembledExamId(exam.id);
          }
        } catch (err) {
          console.error("Failed to load draft exam", err);
        }
      };
      loadDraft();
    }
  }, [draftIdParam]);

  // Handle bank selection: loads questions strictly for that bank and resets previous selections
  const handleSelectBank = useCallback(
    async (bankId: number | string) => {
      setSelectedBankId(bankId);
      // Clean slate for questions & blueprints when picking or switching bank
      setSelectedQuestionIds(new Set());
      setTypeBlueprints({});
      setManualPage(1);
      setLoadingBank(true);

      // Auto-populate subject in Step 1 if currently empty
      const bankObj = availableBanks.find((b) => String(b.id) === String(bankId));
      if (bankObj && (!subject || subject.trim() === "") && bankObj.id !== "general") {
        setSubject(bankObj.name);
      }

      try {
        const res = await facultyQuestionBankApi.getQuestions({
          subject_id: bankId,
          limit: 200,
        });
        const questions = res.questions || [];
        setBankQuestions(questions);

        // Analyze question types available in this specific bank
        const typeMap: Record<string, { count: number; defaultMarks: number; label: string }> = {
          mcq: { count: 0, defaultMarks: 1, label: "Multiple Choice (MCQ)" },
          true_false: { count: 0, defaultMarks: 1, label: "True / False" },
          short: { count: 0, defaultMarks: 5, label: "Short Answer" },
          long: { count: 0, defaultMarks: 10, label: "Long Answer" },
          fill_blank: { count: 0, defaultMarks: 1, label: "Fill in Blank" },
        };

        questions.forEach((q) => {
          const rawT = (q.question_type || "mcq").toLowerCase();
          const t =
            rawT === "multiple_choice"
              ? "mcq"
              : rawT === "truefalse" || rawT === "tf"
              ? "true_false"
              : rawT === "short_answer"
              ? "short"
              : rawT === "long_answer"
              ? "long"
              : rawT;

          if (!typeMap[t]) {
            typeMap[t] = {
              count: 0,
              defaultMarks: Number(q.marks) || 1,
              label: t.replace("_", " ").toUpperCase(),
            };
          }
          typeMap[t].count += 1;
        });

        // Initialize blueprints with 0 selected
        const initialBlueprints: Record<string, TypeBlueprint> = {};
        Object.entries(typeMap).forEach(([k, v]) => {
          if (v.count > 0) {
            initialBlueprints[k] = {
              type: k,
              label: v.label,
              availableCount: v.count,
              selectedCount: 0,
              marksPerQuestion: v.defaultMarks,
            };
          }
        });
        setTypeBlueprints(initialBlueprints);
      } catch (err: any) {
        toast.error(err?.response?.data?.detail || "Failed to load question bank items.");
      } finally {
        setLoadingBank(false);
      }
    },
    [availableBanks, subject]
  );

  // Reset entire wizard state cleanly
  const handleResetWizard = useCallback(() => {
    setTitle("");
    setSubject("");
    setSelectedSubjectId("");
    setUploadTargetSubjectId("");
    setDurationMinutes("60");
    setTargetMarks(50);
    setStartsAt("");
    setEndsAt("");
    setShuffleQuestions(true);
    setShuffleOptions(true);
    setSelectedBankId(null);
    setBankQuestions([]);
    setSelectedQuestionIds(new Set());
    setTypeBlueprints({});
    setManualSearch("");
    setManualTypeFilter("all");
    setManualPage(1);
    setAssembledExamId(null);
    setAssembledSummary(null);
    setCurrentStep(1);
    toast.info("Wizard reset. Ready to create a new exam paper.");
  }, []);

  // Handle Bank File Upload
  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const targetSubId = uploadTargetSubjectId || selectedSubjectId;
    if (!targetSubId) {
      toast.error("Please select a Target Subject before uploading question bank files.");
      e.target.value = "";
      return;
    }

    setUploadingFile(true);
    setUploadProgress(`Uploading and parsing ${file.name}...`);
    try {
      const formData = new FormData();
      formData.append("file", file);
      formData.append("dry_run", "false");
      formData.append("is_shared", "true");
      formData.append("subject_id", String(targetSubId));

      const res = await facultyQuestionBankApi.uploadFile(formData);
      toast.success(res.detail || `Successfully imported ${res.imported_count || res.valid_count} question(s)!`);
      await loadAvailableBanks();
      await loadSubjects();
      if (selectedBankId) {
        await handleSelectBank(selectedBankId);
      } else {
        await handleSelectBank(targetSubId);
      }
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || "Failed to upload question bank file.");
    } finally {
      setUploadingFile(false);
      setUploadProgress(null);
      e.target.value = "";
    }
  };

  // Handle Template Download
  const handleDownloadTemplate = async (format: "csv" | "xlsx" | "docx" | "json") => {
    try {
      const blob = await facultyQuestionBankApi.downloadTemplate(format);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `question_bank_template.${format}`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
      toast.success(`Downloaded ${format.toUpperCase()} template`);
    } catch {
      toast.error("Failed to download question bank template.");
    }
  };

  // Blueprint Count Updater
  const updateBlueprintCount = (type: string, delta: number) => {
    setTypeBlueprints((prev) => {
      const current = prev[type];
      if (!current) return prev;
      const nextCount = Math.max(0, Math.min(current.availableCount, current.selectedCount + delta));
      return {
        ...prev,
        [type]: { ...current, selectedCount: nextCount },
      };
    });
  };

  const setBlueprintCountDirect = (type: string, count: number) => {
    setTypeBlueprints((prev) => {
      const current = prev[type];
      if (!current) return prev;
      const nextCount = Math.max(0, Math.min(current.availableCount, count || 0));
      return {
        ...prev,
        [type]: { ...current, selectedCount: nextCount },
      };
    });
  };

  // Calculate live marks from blueprint
  const blueprintSummary = useMemo(() => {
    let totalQuestions = 0;
    let totalMarks = 0;
    Object.values(typeBlueprints).forEach((bp) => {
      totalQuestions += bp.selectedCount;
      totalMarks += bp.selectedCount * bp.marksPerQuestion;
    });
    return {
      totalQuestions,
      totalMarks,
      matchesTarget: totalMarks === targetMarks,
      shortfall: Math.max(0, targetMarks - totalMarks),
      excess: Math.max(0, totalMarks - targetMarks),
    };
  }, [typeBlueprints, targetMarks]);

  // Calculate manual selection marks
  const manualSummary = useMemo(() => {
    const selected = bankQuestions.filter((q) => selectedQuestionIds.has(q.id));
    const totalQuestions = selected.length;
    const totalMarks = selected.reduce((sum, q) => sum + (Number(q.marks) || 1), 0);
    return {
      totalQuestions,
      totalMarks,
      matchesTarget: totalMarks === targetMarks,
      shortfall: Math.max(0, targetMarks - totalMarks),
      excess: Math.max(0, totalMarks - targetMarks),
    };
  }, [bankQuestions, selectedQuestionIds, targetMarks]);

  // Active Summary based on selection mode
  const activeSummary = selectionMode === "blueprint" ? blueprintSummary : manualSummary;

  // Toggle individual question selection
  const toggleQuestionSelection = (id: number) => {
    setSelectedQuestionIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  // Filtered Questions for Manual Mode
  const filteredManualQuestions = useMemo(() => {
    return bankQuestions.filter((q) => {
      if (manualTypeFilter !== "all" && (q.question_type || "").toLowerCase() !== manualTypeFilter)
        return false;
      if (manualSearch.trim()) {
        const s = manualSearch.toLowerCase();
        return (
          (q.question_text || "").toLowerCase().includes(s) ||
          (q.topic || "").toLowerCase().includes(s)
        );
      }
      return true;
    });
  }, [bankQuestions, manualTypeFilter, manualSearch]);

  const totalManualPages = Math.max(1, Math.ceil(filteredManualQuestions.length / manualPageSize));
  const paginatedManualQuestions = useMemo(() => {
    const start = (manualPage - 1) * manualPageSize;
    return filteredManualQuestions.slice(start, start + manualPageSize);
  }, [filteredManualQuestions, manualPage, manualPageSize]);

  // Currently active bank object
  const activeBankObj = useMemo(() => {
    return availableBanks.find((b) => String(b.id) === String(selectedBankId));
  }, [availableBanks, selectedBankId]);

  // Assemble Paper Submission
  const handleAssemblePaper = async () => {
    const trimmedTitle = title.trim();
    if (!trimmedTitle) {
      toast.error("Exam Title is required and cannot be empty or whitespace.");
      setCurrentStep(1);
      return;
    }
    if (trimmedTitle.length > 255) {
      toast.error("Exam Title cannot exceed 255 characters.");
      setCurrentStep(1);
      return;
    }

    if (activeSummary.totalQuestions === 0) {
      toast.error("Please select at least one question for the paper.");
      return;
    }

    setAssembling(true);
    try {
      const blueprintPayload: Record<string, number> = {};
      Object.values(typeBlueprints).forEach((bp) => {
        if (bp.selectedCount > 0) {
          blueprintPayload[bp.type] = bp.selectedCount;
        }
      });

      const payload = {
        title: trimmedTitle,
        subject: subject.trim(),
        subject_id: selectedBankId !== "general" ? selectedBankId : undefined,
        duration_minutes: Number(durationMinutes) || 60,
        target_marks: Number(targetMarks) || activeSummary.totalMarks,
        starts_at: startsAt || null,
        ends_at: endsAt || null,
        auto_assemble: selectionMode === "blueprint",
        blueprint: selectionMode === "blueprint" ? blueprintPayload : undefined,
        question_ids: selectionMode === "manual" ? Array.from(selectedQuestionIds) : undefined,
      };

      const res = await facultyQuestionBankApi.assemblePaperFromBank(assembledExamId, payload);
      setAssembledExamId(res.exam_id);
      setAssembledSummary(res);
      toast.success(res.detail || "Paper successfully assembled from question bank!");
      setCurrentStep(4);
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || "Failed to assemble paper from bank.");
    } finally {
      setAssembling(false);
    }
  };

  // Direct Publish Action
  const handleDirectPublish = async () => {
    if (!assembledExamId) return;

    // Pre-flight schedule verification
    if (!startsAt) {
      toast.error("Please configure a schedule start time in Step 1 before publishing.");
      return;
    }

    setPublishing(true);
    try {
      const schedulePayload = {
        starts_at: startsAt,
        ends_at: endsAt || undefined,
        duration_minutes: durationMinutes,
      };

      await facultyExamApi.publishExam(assembledExamId, false, schedulePayload);
      toast.success("Exam published successfully! Students can now access it during the scheduled window.");
      setShowPublishModal(false);
      navigate("/faculty/history");
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || "Failed to publish exam.");
    } finally {
      setPublishing(false);
    }
  };

  const pageContent = (
    <div className="space-y-6 max-w-6xl mx-auto pb-12">
        {/* Header Breadcrumbs */}
        <div className="flex items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 text-xs text-muted-foreground mb-1">
              <span className="hover:text-foreground cursor-pointer" onClick={() => navigate("/faculty")}>
                Dashboard
              </span>
              <span>/</span>
              <span className="text-foreground font-semibold">Question Bank Paper</span>
            </div>
            <h1 className="text-2xl sm:text-3xl font-bold text-foreground">
              Create Paper from Question Bank
            </h1>
            <p className="text-xs sm:text-sm text-muted-foreground mt-0.5">
              Assemble and publish verified exams directly from your question bank without AI hallucination risk.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={handleResetWizard}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-border text-xs font-semibold text-muted-foreground hover:text-foreground hover:bg-slate-50 transition-colors shadow-2xs"
              title="Reset all wizard fields and start fresh"
            >
              <RotateCcw className="h-3.5 w-3.5" /> Start Over
            </button>
            <button
              type="button"
              onClick={() => navigate("/faculty/history")}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-border text-xs font-semibold text-muted-foreground hover:text-foreground transition-colors"
            >
              <ArrowLeft className="h-3.5 w-3.5" /> Back to Exams
            </button>
          </div>
        </div>

        {/* Stepper Progress Bar */}
        <div className="grid grid-cols-4 gap-2 sm:gap-4 p-3 bg-muted/30 rounded-2xl border border-border">
          {[
            { step: 1, label: "Exam Details", desc: "Title & Schedule" },
            { step: 2, label: "Bank Selection", desc: "Select / Upload Bank" },
            { step: 3, label: "Blueprint Counts", desc: "Choose by Type" },
            { step: 4, label: "Paper & Publish", desc: "Review & Deploy" },
          ].map((s) => {
            const isCompleted = currentStep > s.step;
            const isCurrent = currentStep === s.step;
            return (
              <div
                key={s.step}
                className={`flex items-center gap-2.5 p-2 rounded-xl transition-all ${
                  isCurrent
                    ? "bg-white shadow-xs border border-primary/30"
                    : isCompleted
                    ? "text-foreground"
                    : "text-muted-foreground opacity-60"
                }`}
              >
                <div
                  className={`h-7 w-7 rounded-lg flex items-center justify-center text-xs font-bold shrink-0 transition-colors ${
                    isCurrent
                      ? "bg-primary text-primary-foreground"
                      : isCompleted
                      ? "bg-emerald-500 text-white"
                      : "bg-muted text-muted-foreground"
                  }`}
                >
                  {isCompleted ? <Check className="h-4 w-4" /> : s.step}
                </div>
                <div className="hidden sm:block min-w-0">
                  <div className="text-xs font-bold truncate leading-tight">{s.label}</div>
                  <div className="text-[10px] text-muted-foreground truncate">{s.desc}</div>
                </div>
              </div>
            );
          })}
        </div>

        {/* STEP 1: Exam Details & Schedule */}
        {currentStep === 1 && (
          <section className="bg-white rounded-2xl border border-border p-6 shadow-xs space-y-6">
            <div className="flex items-center justify-between border-b border-border/80 pb-4">
              <div>
                <h2 className="text-lg font-bold text-foreground">Step 1: Exam Configuration & Schedule</h2>
                <p className="text-xs text-muted-foreground">
                  Enter your exam title, target marks, duration, and scheduling parameters.
                </p>
              </div>
              <span className="text-xs font-semibold px-2.5 py-1 rounded-full bg-primary/10 text-primary">
                Step 1 of 4
              </span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="space-y-1.5 sm:col-span-2">
                <label className="text-xs font-semibold text-foreground">
                  Exam Title * <span className="text-[11px] font-normal text-muted-foreground">(Required, max 255 chars)</span>
                </label>
                <input
                  type="text"
                  maxLength={255}
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  placeholder="e.g. MCA Semester 2 Internal Examination"
                  className="w-full px-3.5 py-2.5 rounded-xl border border-border text-sm focus:outline-hidden focus:ring-2 focus:ring-primary/20"
                />
              </div>

              <div className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <label className="text-xs font-semibold text-foreground">Subject / Course *</label>
                  {!isCreatingSubject && (
                    <button
                      type="button"
                      onClick={() => setIsCreatingSubject(true)}
                      className="text-[11px] font-semibold text-primary hover:underline flex items-center gap-0.5"
                    >
                      <Plus className="h-3 w-3" /> New Subject
                    </button>
                  )}
                </div>

                {!isCreatingSubject ? (
                  <select
                    value={selectedSubjectId}
                    onChange={(e) => {
                      const val = e.target.value;
                      if (val === "__new__") {
                        setIsCreatingSubject(true);
                      } else {
                        setSelectedSubjectId(val);
                        setUploadTargetSubjectId(val);
                        const found = subjectsList.find((s) => String(s.id) === String(val));
                        setSubject(found ? found.name : "");
                      }
                    }}
                    className="w-full px-3.5 py-2.5 rounded-xl border border-border text-sm focus:outline-hidden focus:ring-2 focus:ring-primary/20 bg-white"
                  >
                    <option value="">-- Select Subject ({subjectsList.length} available) --</option>
                    {subjectsList.map((s) => (
                      <option key={s.id} value={s.id}>
                        {s.code ? `[${s.code}] ` : ""}{s.name} ({s.question_count ?? 0} questions)
                      </option>
                    ))}
                    <option value="__new__">+ Create New Subject...</option>
                  </select>
                ) : (
                  <div className="p-3 rounded-xl border border-primary/20 bg-primary/5 space-y-2.5">
                    <div className="text-xs font-bold text-foreground">Create New Subject</div>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                      <input
                        type="text"
                        placeholder="Subject Name (e.g. Cloud Computing)"
                        value={newSubjectName}
                        onChange={(e) => setNewSubjectName(e.target.value)}
                        className="px-3 py-1.5 text-xs rounded-lg border border-border bg-white"
                      />
                      <input
                        type="text"
                        placeholder="Subject Code (e.g. CS302)"
                        value={newSubjectCode}
                        onChange={(e) => setNewSubjectCode(e.target.value)}
                        className="px-3 py-1.5 text-xs rounded-lg border border-border bg-white"
                      />
                    </div>
                    <div className="flex items-center gap-2 justify-end">
                      <button
                        type="button"
                        onClick={() => {
                          setIsCreatingSubject(false);
                          setNewSubjectName("");
                          setNewSubjectCode("");
                        }}
                        className="px-2.5 py-1 text-xs rounded-lg border border-border bg-white text-muted-foreground hover:text-foreground"
                      >
                        Cancel
                      </button>
                      <button
                        type="button"
                        disabled={creatingSubjectLoading}
                        onClick={handleCreateSubject}
                        className="px-3 py-1 text-xs rounded-lg bg-primary text-primary-foreground font-semibold hover:bg-primary/90 flex items-center gap-1"
                      >
                        {creatingSubjectLoading && <Loader2 className="h-3 w-3 animate-spin" />}
                        Save Subject
                      </button>
                    </div>
                  </div>
                )}
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-foreground">Target Total Marks *</label>
                <input
                  type="number"
                  min="1"
                  max="1000"
                  value={targetMarks}
                  onChange={(e) => setTargetMarks(Number(e.target.value) || 0)}
                  className="w-full px-3.5 py-2.5 rounded-xl border border-border text-sm focus:outline-hidden focus:ring-2 focus:ring-primary/20"
                />
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-foreground">
                  Duration (Minutes) * <span className="text-[11px] font-normal text-muted-foreground">(1 - 600)</span>
                </label>
                <input
                  type="number"
                  min="1"
                  max="600"
                  value={durationMinutes}
                  onChange={(e) => setDurationMinutes(e.target.value)}
                  onBlur={() => {
                    const val = parseInt(durationMinutes, 10);
                    if (isNaN(val) || val < 1) setDurationMinutes("60");
                    else if (val > 600) setDurationMinutes("600");
                    else setDurationMinutes(String(val));
                  }}
                  placeholder="e.g. 60"
                  className="w-full px-3.5 py-2.5 rounded-xl border border-border text-sm focus:outline-hidden focus:ring-2 focus:ring-primary/20"
                />
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-foreground">Starts At (Scheduled Window)</label>
                <input
                  type="datetime-local"
                  value={startsAt}
                  onChange={(e) => setStartsAt(e.target.value)}
                  className="w-full px-3.5 py-2.5 rounded-xl border border-border text-sm focus:outline-hidden focus:ring-2 focus:ring-primary/20"
                />
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-foreground">Ends At (Optional Closing Window)</label>
                <input
                  type="datetime-local"
                  value={endsAt}
                  onChange={(e) => setEndsAt(e.target.value)}
                  className="w-full px-3.5 py-2.5 rounded-xl border border-border text-sm focus:outline-hidden focus:ring-2 focus:ring-primary/20"
                />
              </div>
            </div>

            <div className="flex items-center gap-6 pt-2 border-t border-border/80">
              <label className="flex items-center gap-2 cursor-pointer text-xs font-medium text-foreground">
                <input
                  type="checkbox"
                  checked={shuffleQuestions}
                  onChange={(e) => setShuffleQuestions(e.target.checked)}
                  className="rounded text-primary focus:ring-primary"
                />
                Shuffle Questions per Student
              </label>
              <label className="flex items-center gap-2 cursor-pointer text-xs font-medium text-foreground">
                <input
                  type="checkbox"
                  checked={shuffleOptions}
                  onChange={(e) => setShuffleOptions(e.target.checked)}
                  className="rounded text-primary focus:ring-primary"
                />
                Shuffle MCQ Options per Student
              </label>
            </div>

            <div className="flex justify-end pt-4 border-t border-border/80">
              <button
                type="button"
                onClick={() => {
                  const trimmed = title.trim();
                  if (!trimmed) {
                    toast.error("Please enter an exam title before proceeding.");
                    return;
                  }
                  if (trimmed.length > 255) {
                    toast.error("Exam title cannot exceed 255 characters.");
                    return;
                  }
                  const dur = parseInt(durationMinutes, 10);
                  if (isNaN(dur) || dur < 1 || dur > 600) {
                    toast.error("Duration must be a valid whole number between 1 and 600 minutes.");
                    return;
                  }
                  if (!selectedSubjectId && !subject.trim()) {
                    toast.error("Please select or create a subject before proceeding.");
                    return;
                  }
                  setCurrentStep(2);
                }}
                className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-primary text-primary-foreground text-sm font-semibold hover:bg-primary/90 transition-all shadow-xs"
              >
                Proceed to Bank Selection <ArrowRight className="h-4 w-4" />
              </button>
            </div>
          </section>
        )}

        {/* STEP 2: Choose / Upload Question Bank */}
        {currentStep === 2 && (
          <section className="bg-white rounded-2xl border border-border p-6 shadow-xs space-y-6">
            <div className="flex items-center justify-between border-b border-border/80 pb-4">
              <div>
                <h2 className="text-lg font-bold text-foreground">Step 2: Choose or Upload Question Bank</h2>
                <p className="text-xs text-muted-foreground">
                  Select a specific question bank from your department repository or upload a new bank file.
                </p>
              </div>
              <span className="text-xs font-semibold px-2.5 py-1 rounded-full bg-primary/10 text-primary">
                Step 2 of 4
              </span>
            </div>

            {/* Upload Area */}
            <div className="rounded-2xl border-2 border-dashed border-border bg-slate-50/50 p-6 flex flex-col items-center justify-center text-center space-y-3">
              <div className="h-12 w-12 rounded-2xl bg-primary/10 text-primary flex items-center justify-center">
                <UploadCloud className="h-6 w-6" />
              </div>
              <div>
                <h3 className="text-sm font-bold text-foreground">Upload Question Bank File</h3>
                <p className="text-xs text-muted-foreground max-w-md mt-1">
                  Supports CSV, XLSX, DOCX, and JSON files. Questions will be validated and added to the selected subject question bank.
                </p>
              </div>

              {/* Target Subject Selector */}
              <div className="w-full max-w-md text-left space-y-1.5 pt-1">
                <label className="text-xs font-semibold text-foreground flex items-center justify-between">
                  <span>Import Questions into Subject: *</span>
                  {!isCreatingSubject && (
                    <button
                      type="button"
                      onClick={() => setIsCreatingSubject(true)}
                      className="text-[11px] text-primary hover:underline font-normal flex items-center gap-0.5"
                    >
                      <Plus className="h-3 w-3" /> New Subject
                    </button>
                  )}
                </label>
                <select
                  value={uploadTargetSubjectId || selectedSubjectId}
                  onChange={(e) => {
                    const val = e.target.value;
                    setUploadTargetSubjectId(val);
                    if (!selectedSubjectId) setSelectedSubjectId(val);
                    const found = subjectsList.find((s) => String(s.id) === String(val));
                    if (found && !subject) setSubject(found.name);
                  }}
                  className="w-full px-3 py-2 rounded-xl border border-border text-xs sm:text-sm bg-white focus:outline-hidden focus:ring-2 focus:ring-primary/20"
                >
                  <option value="">-- Choose Target Subject (Required) --</option>
                  {subjectsList.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.code ? `[${s.code}] ` : ""}{s.name} ({s.question_count ?? 0} questions)
                    </option>
                  ))}
                </select>
                {!(uploadTargetSubjectId || selectedSubjectId) && (
                  <p className="text-[11px] text-amber-600 font-medium">
                    ⚠️ Please select a Subject before uploading question bank files.
                  </p>
                )}
              </div>

              {uploadProgress && (
                <div className="flex items-center gap-2 text-xs font-semibold text-primary">
                  <Loader2 className="h-4 w-4 animate-spin" /> {uploadProgress}
                </div>
              )}

              <div className="flex items-center gap-3 pt-2">
                <label
                  className={`inline-flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold transition-colors cursor-pointer shadow-xs ${
                    !(uploadTargetSubjectId || selectedSubjectId)
                      ? "bg-slate-200 text-slate-400 cursor-not-allowed"
                      : "bg-primary text-primary-foreground hover:bg-primary/90"
                  }`}
                >
                  <FileUp className="h-4 w-4" /> Select File to Upload
                  <input
                    type="file"
                    accept=".csv,.xlsx,.docx,.json"
                    onChange={handleFileUpload}
                    disabled={uploadingFile || !(uploadTargetSubjectId || selectedSubjectId)}
                    className="hidden"
                  />
                </label>
              </div>

              <div className="flex items-center gap-2 pt-2 text-[11px] text-muted-foreground">
                <span>Download Sample Templates:</span>
                {(["csv", "xlsx", "docx", "json"] as const).map((fmt) => (
                  <button
                    key={fmt}
                    type="button"
                    onClick={() => handleDownloadTemplate(fmt)}
                    className="underline hover:text-foreground uppercase font-bold"
                  >
                    .{fmt}
                  </button>
                ))}
              </div>
            </div>

            {/* Question Bank Selection State */}
            {!selectedBankId ? (
              /* EMPTY STATE: Prompt to choose a bank before questions appear */
              <div className="p-8 rounded-2xl border border-dashed border-border bg-slate-50/60 text-center space-y-4">
                <div className="h-12 w-12 rounded-2xl bg-primary/10 text-primary flex items-center justify-center mx-auto">
                  <Database className="h-6 w-6" />
                </div>
                <div>
                  <h3 className="text-base font-bold text-foreground">
                    Select a question bank to view its available questions.
                  </h3>
                  <p className="text-xs text-muted-foreground max-w-md mx-auto mt-1">
                    Choose one of your department question banks below to inspect its pool and draw questions for this exam.
                  </p>
                </div>

                {loadingBanksList ? (
                  <div className="flex items-center justify-center gap-2 py-6 text-xs text-muted-foreground">
                    <Loader2 className="h-4 w-4 animate-spin text-primary" /> Loading available banks...
                  </div>
                ) : availableBanks.length === 0 ? (
                  <div className="p-4 rounded-xl bg-amber-50 border border-amber-200 text-xs text-amber-800 max-w-md mx-auto">
                    No question banks found for your department. Please upload a bank file above to get started.
                  </div>
                ) : (
                  <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3 text-left max-w-3xl mx-auto pt-2">
                    {availableBanks.map((b) => (
                      <button
                        key={b.id}
                        type="button"
                        onClick={() => handleSelectBank(b.id)}
                        className="p-4 rounded-xl border border-border bg-white hover:border-primary/50 hover:bg-primary/5 transition-all text-left shadow-2xs group flex flex-col justify-between"
                      >
                        <div>
                          <div className="flex items-center justify-between mb-1.5">
                            <span className="text-[10px] font-bold px-2 py-0.5 rounded-md bg-slate-100 text-slate-700 uppercase">
                              {b.code || "BANK"}
                            </span>
                            <span className="text-xs font-bold text-primary">
                              {b.question_count} Questions
                            </span>
                          </div>
                          <h4 className="text-sm font-bold text-foreground group-hover:text-primary transition-colors line-clamp-1">
                            {b.name}
                          </h4>
                          {b.department && (
                            <p className="text-[11px] text-muted-foreground mt-0.5 truncate">{b.department}</p>
                          )}
                        </div>
                        <div className="mt-3 pt-2 border-t border-border/60 flex items-center justify-between text-xs font-semibold text-primary">
                          <span>Select Bank</span>
                          <ArrowRight className="h-3.5 w-3.5 group-hover:translate-x-0.5 transition-transform" />
                        </div>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            ) : (
              /* SELECTED BANK VIEW */
              <div className="space-y-4">
                {/* Active Bank Header Bar */}
                <div className="p-4 rounded-2xl border border-primary/30 bg-primary/5 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                  <div className="flex items-center gap-3">
                    <div className="h-10 w-10 rounded-xl bg-primary/10 text-primary flex items-center justify-center font-bold">
                      <Database className="h-5 w-5" />
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <h3 className="text-sm font-bold text-foreground">
                          {activeBankObj?.name || "Selected Question Bank"}
                        </h3>
                        <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-primary/10 text-primary">
                          Active Bank
                        </span>
                      </div>
                      <p className="text-xs text-muted-foreground mt-0.5">
                        {bankQuestions.length} verified questions loaded from this bank
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      disabled={loadingBank}
                      onClick={() => handleSelectBank(selectedBankId)}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-border bg-white text-xs font-semibold text-muted-foreground hover:text-foreground hover:bg-slate-50 transition-colors shadow-2xs"
                    >
                      <RefreshCw className={`h-3.5 w-3.5 ${loadingBank ? "animate-spin" : ""}`} /> Refresh
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        setSelectedBankId(null);
                        setBankQuestions([]);
                        setSelectedQuestionIds(new Set());
                        setTypeBlueprints({});
                      }}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-border bg-white text-xs font-semibold text-primary hover:bg-primary/5 transition-colors shadow-2xs"
                    >
                      <RotateCcw className="h-3.5 w-3.5" /> Switch Bank
                    </button>
                  </div>
                </div>

                {/* Pool Overview Cards */}
                {loadingBank ? (
                  <div className="py-8 flex flex-col items-center justify-center text-muted-foreground gap-2">
                    <Loader2 className="h-6 w-6 animate-spin text-primary" />
                    <p className="text-xs font-medium">Loading bank questions...</p>
                  </div>
                ) : bankQuestions.length === 0 ? (
                  <div className="p-8 rounded-xl border border-dashed border-border text-center text-xs text-muted-foreground space-y-2">
                    <p>This question bank currently has 0 questions.</p>
                    <p>Upload a CSV, XLSX, or DOCX above to import questions into this bank.</p>
                  </div>
                ) : (
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                    <div className="p-3.5 rounded-xl border border-border bg-slate-50/50">
                      <div className="text-[11px] font-semibold text-muted-foreground uppercase">Total In Bank</div>
                      <div className="text-2xl font-bold text-foreground mt-0.5">{bankQuestions.length}</div>
                      <div className="text-[10px] text-muted-foreground">verified questions</div>
                    </div>
                    {Object.values(typeBlueprints).map((bp) => (
                      <div key={bp.type} className="p-3.5 rounded-xl border border-border bg-slate-50/50">
                        <div className="text-[11px] font-semibold text-muted-foreground uppercase truncate">
                          {bp.label}
                        </div>
                        <div className="text-2xl font-bold text-primary mt-0.5">{bp.availableCount}</div>
                        <div className="text-[10px] text-muted-foreground">available to draw</div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            <div className="flex items-center justify-between pt-4 border-t border-border/80">
              <button
                type="button"
                onClick={() => setCurrentStep(1)}
                className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl border border-border text-xs font-semibold text-muted-foreground hover:text-foreground transition-colors"
              >
                <ArrowLeft className="h-3.5 w-3.5" /> Back to Exam Details
              </button>
              <button
                type="button"
                disabled={!selectedBankId || bankQuestions.length === 0}
                onClick={() => setCurrentStep(3)}
                className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-primary text-primary-foreground text-sm font-semibold hover:bg-primary/90 transition-all shadow-xs disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Configure Questions <ArrowRight className="h-4 w-4" />
              </button>
            </div>
          </section>
        )}

        {/* STEP 3: Question Selection & Blueprint */}
        {currentStep === 3 && (
          <section className="bg-white rounded-2xl border border-border p-6 shadow-xs space-y-6">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-border/80 pb-4">
              <div>
                <h2 className="text-lg font-bold text-foreground">Step 3: Question Selection & Type Blueprint</h2>
                <p className="text-xs text-muted-foreground">
                  Specify quotas by type or pick individual verified questions from{" "}
                  <strong className="text-foreground">{activeBankObj?.name || "your bank"}</strong>.
                </p>
              </div>

              {/* Mode Toggle */}
              <div className="flex items-center p-1 bg-muted/50 rounded-xl border border-border text-xs">
                <button
                  type="button"
                  onClick={() => setSelectionMode("blueprint")}
                  className={`px-3 py-1.5 rounded-lg font-semibold transition-all ${
                    selectionMode === "blueprint"
                      ? "bg-white text-foreground shadow-xs"
                      : "text-muted-foreground hover:text-foreground"
                  }`}
                >
                  Type Blueprint Mode
                </button>
                <button
                  type="button"
                  onClick={() => setSelectionMode("manual")}
                  className={`px-3 py-1.5 rounded-lg font-semibold transition-all ${
                    selectionMode === "manual"
                      ? "bg-white text-foreground shadow-xs"
                      : "text-muted-foreground hover:text-foreground"
                  }`}
                >
                  Manual Pick Mode
                </button>
              </div>
            </div>

            {/* Live Marks & Target Counter Bar */}
            <div className="p-4 rounded-xl border border-border bg-slate-50/70 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div className="flex items-center gap-4 flex-wrap">
                <div>
                  <div className="text-[11px] font-semibold text-muted-foreground uppercase">Target Exam Marks</div>
                  <div className="text-xl font-bold text-foreground">{targetMarks} Marks</div>
                </div>
                <div className="h-8 w-px bg-border/80 hidden sm:block" />
                <div>
                  <div className="text-[11px] font-semibold text-muted-foreground uppercase">Selected Questions</div>
                  <div className="text-xl font-bold text-primary">{activeSummary.totalQuestions} Questions</div>
                </div>
                <div className="h-8 w-px bg-border/80 hidden sm:block" />
                <div>
                  <div className="text-[11px] font-semibold text-muted-foreground uppercase">Calculated Total Marks</div>
                  <div className="text-xl font-bold text-foreground">{activeSummary.totalMarks} Marks</div>
                </div>
              </div>

              <div>
                {activeSummary.matchesTarget ? (
                  <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-emerald-50 border border-emerald-300 text-emerald-800 text-xs font-bold shadow-2xs">
                    <CheckCircle2 className="h-4 w-4 text-emerald-600" /> Exact Marks Match ({targetMarks})
                  </span>
                ) : activeSummary.shortfall > 0 ? (
                  <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-amber-50 border border-amber-300 text-amber-800 text-xs font-bold">
                    <AlertCircle className="h-4 w-4 text-amber-600" /> Shortfall of {activeSummary.shortfall} Marks
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-rose-50 border border-rose-300 text-rose-800 text-xs font-bold">
                    <AlertCircle className="h-4 w-4 text-rose-600" /> Exceeds Target by {activeSummary.excess} Marks
                  </span>
                )}
              </div>
            </div>

            {/* BLUEPRINT MODE */}
            {selectionMode === "blueprint" ? (
              <div className="space-y-4">
                <div className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                  Question Type Quotas ({activeBankObj?.name || "Selected Bank"})
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {Object.values(typeBlueprints).map((bp) => {
                    const subtotal = bp.selectedCount * bp.marksPerQuestion;
                    return (
                      <div
                        key={bp.type}
                        className={`rounded-2xl border p-4.5 transition-all ${
                          bp.selectedCount > 0
                            ? "border-primary/40 bg-primary/5 shadow-xs"
                            : "border-border bg-slate-50/40"
                        }`}
                      >
                        <div className="flex items-center justify-between mb-3">
                          <div>
                            <div className="text-sm font-bold text-foreground">{bp.label}</div>
                            <div className="text-xs text-muted-foreground">
                              {bp.availableCount} questions available in bank
                            </div>
                          </div>
                          <span className="text-xs font-bold px-2.5 py-0.5 rounded-full bg-slate-100 text-slate-700">
                            {bp.marksPerQuestion} {bp.marksPerQuestion === 1 ? "Mark" : "Marks"} each
                          </span>
                        </div>

                        <div className="flex items-center justify-between gap-4">
                          <div className="flex items-center gap-2">
                            <button
                              type="button"
                              onClick={() => updateBlueprintCount(bp.type, -1)}
                              disabled={bp.selectedCount <= 0}
                              className="h-8 w-8 rounded-lg border border-border bg-white flex items-center justify-center text-foreground hover:bg-muted transition-colors disabled:opacity-40"
                            >
                              <Minus className="h-3.5 w-3.5" />
                            </button>
                            <input
                              type="number"
                              min="0"
                              max={bp.availableCount}
                              value={bp.selectedCount}
                              onChange={(e) => setBlueprintCountDirect(bp.type, parseInt(e.target.value) || 0)}
                              className="w-16 text-center py-1 rounded-lg border border-border text-sm font-bold"
                            />
                            <button
                              type="button"
                              onClick={() => updateBlueprintCount(bp.type, 1)}
                              disabled={bp.selectedCount >= bp.availableCount}
                              className="h-8 w-8 rounded-lg border border-border bg-white flex items-center justify-center text-foreground hover:bg-muted transition-colors disabled:opacity-40"
                            >
                              <Plus className="h-3.5 w-3.5" />
                            </button>
                          </div>

                          <div className="text-right">
                            <div className="text-[11px] font-semibold text-muted-foreground">Subtotal</div>
                            <div className="text-sm font-bold text-primary">{subtotal} Marks</div>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            ) : (
              /* MANUAL PICK MODE WITH SEARCH, FILTER, AND PAGINATION */
              <div className="space-y-4">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                  <div className="relative flex-1">
                    <Search className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
                    <input
                      type="text"
                      placeholder="Search questions by text or topic..."
                      value={manualSearch}
                      onChange={(e) => {
                        setManualSearch(e.target.value);
                        setManualPage(1);
                      }}
                      className="w-full pl-9 pr-4 py-2 rounded-xl border border-border text-xs focus:outline-hidden focus:ring-2 focus:ring-primary/20"
                    />
                  </div>
                  <select
                    value={manualTypeFilter}
                    onChange={(e) => {
                      setManualTypeFilter(e.target.value);
                      setManualPage(1);
                    }}
                    className="px-3 py-2 rounded-xl border border-border text-xs bg-white focus:outline-hidden"
                  >
                    <option value="all">All Types</option>
                    <option value="mcq">MCQ</option>
                    <option value="true_false">True / False</option>
                    <option value="short">Short Answer</option>
                    <option value="long">Long Answer</option>
                    <option value="fill_blank">Fill in Blank</option>
                  </select>
                </div>

                <div className="space-y-2 border border-border rounded-xl p-3 bg-slate-50/30">
                  {paginatedManualQuestions.length === 0 ? (
                    <div className="p-8 text-center text-xs text-muted-foreground">
                      No questions matched your search and filter criteria.
                    </div>
                  ) : (
                    paginatedManualQuestions.map((q) => {
                      const isSelected = selectedQuestionIds.has(q.id);
                      return (
                        <div
                          key={q.id}
                          onClick={() => toggleQuestionSelection(q.id)}
                          className={`flex items-start gap-3 p-3 rounded-xl border cursor-pointer transition-all ${
                            isSelected
                              ? "border-primary bg-primary/5 ring-1 ring-primary/30"
                              : "border-border/80 bg-white hover:bg-slate-50"
                          }`}
                        >
                          <input
                            type="checkbox"
                            checked={isSelected}
                            onChange={() => {}}
                            className="mt-0.5 rounded text-primary focus:ring-primary"
                          />
                          <div className="flex-1 min-w-0">
                            <div className="text-xs font-semibold text-foreground leading-snug line-clamp-2">
                              {q.question_text || (q as any).text}
                            </div>
                            <div className="flex items-center gap-2 mt-1.5 flex-wrap">
                              <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-slate-100 text-slate-700 uppercase">
                                {q.question_type}
                              </span>
                              <span className="text-[10px] font-semibold text-primary">
                                {q.marks} {Number(q.marks) === 1 ? "Mark" : "Marks"}
                              </span>
                              {q.topic && (
                                <span className="text-[10px] text-muted-foreground">Topic: {q.topic}</span>
                              )}
                            </div>
                          </div>
                        </div>
                      );
                    })
                  )}
                </div>

                {/* Pagination Controls */}
                {totalManualPages > 1 && (
                  <div className="flex items-center justify-between px-2 pt-2 text-xs text-muted-foreground">
                    <div>
                      Showing {(manualPage - 1) * manualPageSize + 1} -{" "}
                      {Math.min(manualPage * manualPageSize, filteredManualQuestions.length)} of{" "}
                      {filteredManualQuestions.length} questions
                    </div>
                    <div className="flex items-center gap-1.5">
                      <button
                        type="button"
                        disabled={manualPage <= 1}
                        onClick={() => setManualPage((p) => Math.max(1, p - 1))}
                        className="p-1.5 rounded-lg border border-border bg-white text-foreground hover:bg-slate-50 disabled:opacity-40 transition-colors"
                      >
                        <ChevronLeft className="h-4 w-4" />
                      </button>
                      <span className="px-2 font-semibold text-foreground">
                        {manualPage} / {totalManualPages}
                      </span>
                      <button
                        type="button"
                        disabled={manualPage >= totalManualPages}
                        onClick={() => setManualPage((p) => Math.min(totalManualPages, p + 1))}
                        className="p-1.5 rounded-lg border border-border bg-white text-foreground hover:bg-slate-50 disabled:opacity-40 transition-colors"
                      >
                        <ChevronRight className="h-4 w-4" />
                      </button>
                    </div>
                  </div>
                )}
              </div>
            )}

            <div className="flex items-center justify-between pt-4 border-t border-border/80">
              <button
                type="button"
                onClick={() => setCurrentStep(2)}
                className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl border border-border text-xs font-semibold text-muted-foreground hover:text-foreground transition-colors"
              >
                <ArrowLeft className="h-3.5 w-3.5" /> Back to Bank Selection
              </button>

              <button
                type="button"
                disabled={activeSummary.totalQuestions === 0 || assembling}
                onClick={handleAssemblePaper}
                className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-primary text-primary-foreground text-sm font-semibold hover:bg-primary/90 transition-all shadow-xs disabled:opacity-50"
              >
                {assembling ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" /> Assembling Paper...
                  </>
                ) : (
                  <>
                    Assemble Paper <ArrowRight className="h-4 w-4" />
                  </>
                )}
              </button>
            </div>
          </section>
        )}

        {/* STEP 4: Assembled Paper Summary & Direct Publish */}
        {currentStep === 4 && assembledSummary && (
          <section className="bg-white rounded-2xl border border-border p-6 shadow-xs space-y-6">
            <div className="flex items-center justify-between border-b border-border/80 pb-4">
              <div className="flex items-center gap-3">
                <div className="h-10 w-10 rounded-xl bg-emerald-500/10 text-emerald-600 flex items-center justify-center">
                  <CheckCircle2 className="h-6 w-6" />
                </div>
                <div>
                  <h2 className="text-lg font-bold text-foreground">Paper Successfully Created!</h2>
                  <p className="text-xs text-muted-foreground">
                    Your paper has been generated and saved to your repository. You can publish directly or open in Review & Edit.
                  </p>
                </div>
              </div>
              <span className="text-xs font-bold px-3 py-1 rounded-full bg-emerald-50 border border-emerald-300 text-emerald-800">
                Draft Ready
              </span>
            </div>

            {/* Exam Summary Details Card */}
            <div className="rounded-2xl border border-border bg-slate-50/50 p-5 space-y-4">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-border/80 pb-3">
                <div>
                  <h3 className="text-base font-bold text-foreground">{title}</h3>
                  <p className="text-xs text-muted-foreground">{subject || activeBankObj?.name || "General Subject"}</p>
                </div>
                <div className="text-xs text-muted-foreground">Exam ID #{assembledExamId}</div>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                <div>
                  <div className="text-[11px] font-semibold text-muted-foreground uppercase">Total Marks</div>
                  <div className="text-xl font-bold text-foreground mt-0.5">
                    {assembledSummary.actual_total_marks || assembledSummary.total_marks} Marks
                  </div>
                </div>
                <div>
                  <div className="text-[11px] font-semibold text-muted-foreground uppercase">Questions</div>
                  <div className="text-xl font-bold text-primary mt-0.5">
                    {assembledSummary.question_count} Questions
                  </div>
                </div>
                <div>
                  <div className="text-[11px] font-semibold text-muted-foreground uppercase">Duration</div>
                  <div className="text-xl font-bold text-foreground mt-0.5">{durationMinutes} Mins</div>
                </div>
                <div>
                  <div className="text-[11px] font-semibold text-muted-foreground uppercase">Schedule Window</div>
                  <div className="text-xs font-medium text-foreground mt-1">
                    {startsAt ? new Date(startsAt).toLocaleString() : "Unscheduled"}
                  </div>
                </div>
              </div>
            </div>

            {/* Action Buttons: Direct Publish vs Review & Edit vs Create Another */}
            <div className="p-5 rounded-2xl border border-primary/20 bg-primary/5 space-y-4">
              <div>
                <h4 className="text-sm font-bold text-foreground">Next Actions</h4>
                <p className="text-xs text-muted-foreground mt-0.5">
                  Choose whether to immediately publish this exam to your students, inspect questions in the editor, or create another paper.
                </p>
              </div>

              <div className="flex flex-col sm:flex-row items-center gap-3 flex-wrap">
                <button
                  type="button"
                  onClick={() => setShowPublishModal(true)}
                  className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-6 py-3 rounded-xl bg-emerald-600 text-white text-sm font-bold hover:bg-emerald-700 transition-all shadow-xs"
                >
                  <Send className="h-4 w-4" /> Publish Exam Now
                </button>

                <button
                  type="button"
                  onClick={() => navigate(`/faculty/exams/${assembledExamId}/edit`)}
                  className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-6 py-3 rounded-xl border border-border bg-white text-foreground text-sm font-bold hover:bg-slate-50 transition-colors shadow-2xs"
                >
                  <FileText className="h-4 w-4" /> Open in Review & Edit
                </button>

                <button
                  type="button"
                  onClick={handleResetWizard}
                  className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-6 py-3 rounded-xl border border-primary/30 bg-white text-primary text-sm font-bold hover:bg-primary/5 transition-colors shadow-2xs"
                >
                  <RotateCcw className="h-4 w-4" /> Create Another Paper
                </button>

                <button
                  type="button"
                  onClick={() => navigate("/faculty/history")}
                  className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-4 py-3 rounded-xl text-xs font-semibold text-muted-foreground hover:text-foreground transition-colors"
                >
                  View in Exam History
                </button>
              </div>
            </div>
          </section>
        )}

        {/* Publish Confirmation Modal */}
        {showPublishModal && (
          <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-xs flex items-center justify-center p-4">
            <div className="bg-white rounded-2xl border border-border max-w-md w-full p-6 shadow-xl space-y-4 animate-in fade-in zoom-in-95">
              <div className="flex items-center gap-3">
                <div className="h-10 w-10 rounded-xl bg-emerald-100 text-emerald-700 flex items-center justify-center">
                  <Send className="h-5 w-5" />
                </div>
                <div>
                  <h3 className="text-base font-bold text-foreground">Confirm Direct Publishing</h3>
                  <p className="text-xs text-muted-foreground">This exam will be scheduled and released to students.</p>
                </div>
              </div>

              <div className="p-3.5 rounded-xl border border-border bg-slate-50 text-xs space-y-2">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Title:</span>
                  <span className="font-semibold">{title}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Total Marks:</span>
                  <span className="font-semibold">{assembledSummary?.total_marks} Marks</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Start Window:</span>
                  <span className="font-semibold">{startsAt ? new Date(startsAt).toLocaleString() : "Immediate"}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Duration:</span>
                  <span className="font-semibold">{durationMinutes} Minutes</span>
                </div>
              </div>

              <p className="text-xs text-muted-foreground">
                Once published, questions cannot be removed. Students can start attempts when the start window begins.
              </p>

              <div className="flex items-center justify-end gap-3 pt-2">
                <button
                  type="button"
                  disabled={publishing}
                  onClick={() => setShowPublishModal(false)}
                  className="px-4 py-2 rounded-xl border border-border text-xs font-semibold text-muted-foreground hover:text-foreground transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  disabled={publishing}
                  onClick={handleDirectPublish}
                  className="inline-flex items-center gap-1.5 px-5 py-2 rounded-xl bg-emerald-600 text-white text-xs font-bold hover:bg-emerald-700 transition-all shadow-xs disabled:opacity-50"
                >
                  {publishing ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Check className="h-3.5 w-3.5" />}
                  Confirm & Publish
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
  );

  if (hideLayout) {
    return pageContent;
  }

  return (
    <DashboardLayout userRole="Faculty">
      {pageContent}
    </DashboardLayout>
  );
}

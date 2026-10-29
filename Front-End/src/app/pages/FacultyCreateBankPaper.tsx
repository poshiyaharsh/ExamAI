import React, { useState, useEffect, useMemo, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import {
  AlertCircle,
  ArrowLeft,
  ArrowRight,
  Check,
  CheckCircle2,
  Clock,
  Calendar,
  Database,
  Download,
  ExternalLink,
  FileCheck2,
  FileText,
  FileUp,
  HelpCircle,
  Loader2,
  Minus,
  Plus,
  RefreshCw,
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
  type FacultyQuestionBankItem,
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

export function FacultyCreateBankPaper() {
  const navigate = useNavigate();

  // Current Stepper Step
  const [currentStep, setCurrentStep] = useState<Step>(1);

  // Step 1: Exam Details & Schedule
  const [title, setTitle] = useState("Question Bank Exam");
  const [subject, setSubject] = useState("");
  const [durationMinutes, setDurationMinutes] = useState(60);
  const [targetMarks, setTargetMarks] = useState(50);
  const [startsAt, setStartsAt] = useState("");
  const [endsAt, setEndsAt] = useState("");
  const [shuffleQuestions, setShuffleQuestions] = useState(true);
  const [shuffleOptions, setShuffleOptions] = useState(true);

  // Step 2: Question Bank Pool & Upload
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

  // Step 4: Assembled Paper & Publishing
  const [assembling, setAssembling] = useState(false);
  const [assembledExamId, setAssembledExamId] = useState<number | null>(null);
  const [assembledSummary, setAssembledSummary] = useState<any | null>(null);
  const [publishing, setPublishing] = useState(false);
  const [showPublishModal, setShowPublishModal] = useState(false);

  // Fetch accessible bank questions
  const loadBankQuestions = useCallback(async () => {
    setLoadingBank(true);
    try {
      const res = await facultyQuestionBankApi.getQuestions({ page_size: 200 });
      const questions = res.questions || [];
      setBankQuestions(questions);

      // Analyze question types available
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

      // Initialize blueprints
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
  }, []);

  useEffect(() => {
    loadBankQuestions();
  }, [loadBankQuestions]);

  // Handle Bank File Upload
  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploadingFile(true);
    setUploadProgress(`Uploading and parsing ${file.name}...`);
    try {
      const formData = new FormData();
      formData.append("file", file);
      formData.append("dry_run", "false");
      formData.append("is_shared", "true");

      const res = await facultyQuestionBankApi.uploadFile(formData);
      toast.success(res.detail || `Successfully imported ${res.imported_count || res.valid_count} question(s)!`);
      await loadBankQuestions();
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

  // Assemble Paper Submission
  const handleAssemblePaper = async () => {
    if (!title.trim()) {
      toast.error("Please provide an exam title.");
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
        title: title.trim(),
        subject: subject.trim(),
        duration_minutes: Number(durationMinutes) || 60,
        target_marks: Number(targetMarks) || activeSummary.totalMarks,
        starts_at: startsAt || null,
        ends_at: endsAt || null,
        auto_assemble: selectionMode === "blueprint",
        blueprint: selectionMode === "blueprint" ? blueprintPayload : undefined,
        question_ids: selectionMode === "manual" ? Array.from(selectedQuestionIds) : undefined,
      };

      const res = await facultyQuestionBankApi.assemblePaperFromBank(null, payload);
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

  return (
    <DashboardLayout userRole="Faculty">
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
          <button
            type="button"
            onClick={() => navigate("/faculty/history")}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-border text-xs font-semibold text-muted-foreground hover:text-foreground transition-colors"
          >
            <ArrowLeft className="h-3.5 w-3.5" /> Back to Exams
          </button>
        </div>

        {/* Stepper Progress Bar */}
        <div className="grid grid-cols-4 gap-2 sm:gap-4 p-3 bg-muted/30 rounded-2xl border border-border">
          {[
            { step: 1, label: "Exam Details", desc: "Title & Schedule" },
            { step: 2, label: "Bank Selection", desc: "Review / Upload" },
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
                  Set target marks, duration, and scheduling parameters for this paper.
                </p>
              </div>
              <span className="text-xs font-semibold px-2.5 py-1 rounded-full bg-primary/10 text-primary">
                Step 1 of 4
              </span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="space-y-1.5 sm:col-span-2">
                <label className="text-xs font-semibold text-foreground">Exam Title *</label>
                <input
                  type="text"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  placeholder="e.g. Midterm Examination - Data Structures"
                  className="w-full px-3.5 py-2.5 rounded-xl border border-border text-sm focus:outline-hidden focus:ring-2 focus:ring-primary/20"
                />
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-foreground">Subject / Course</label>
                <input
                  type="text"
                  value={subject}
                  onChange={(e) => setSubject(e.target.value)}
                  placeholder="e.g. Computer Science / Algorithms"
                  className="w-full px-3.5 py-2.5 rounded-xl border border-border text-sm focus:outline-hidden focus:ring-2 focus:ring-primary/20"
                />
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
                <label className="text-xs font-semibold text-foreground">Duration (Minutes) *</label>
                <input
                  type="number"
                  min="5"
                  max="600"
                  value={durationMinutes}
                  onChange={(e) => setDurationMinutes(Number(e.target.value) || 60)}
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
                  if (!title.trim()) {
                    toast.error("Please enter an exam title.");
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
                  Select existing questions from your institution repository or upload a new question bank file.
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
                  Supports CSV, XLSX, DOCX, and JSON files. Questions will be validated and added to your bank.
                </p>
              </div>

              {uploadProgress && (
                <div className="flex items-center gap-2 text-xs font-semibold text-primary">
                  <Loader2 className="h-4 w-4 animate-spin" /> {uploadProgress}
                </div>
              )}

              <div className="flex items-center gap-3 pt-2">
                <label className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-primary text-primary-foreground text-xs font-semibold hover:bg-primary/90 transition-colors cursor-pointer shadow-xs">
                  <FileUp className="h-4 w-4" /> Select File to Upload
                  <input
                    type="file"
                    accept=".csv,.xlsx,.docx,.json"
                    onChange={handleFileUpload}
                    disabled={uploadingFile}
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

            {/* Current Bank Overview */}
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-bold text-foreground flex items-center gap-2">
                  <Database className="h-4 w-4 text-primary" /> Available Bank Pool Overview
                </h3>
                <button
                  type="button"
                  onClick={loadBankQuestions}
                  disabled={loadingBank}
                  className="inline-flex items-center gap-1.5 text-xs font-semibold text-primary hover:underline"
                >
                  <RefreshCw className={`h-3.5 w-3.5 ${loadingBank ? "animate-spin" : ""}`} /> Refresh Pool
                </button>
              </div>

              {loadingBank ? (
                <div className="py-8 flex flex-col items-center justify-center text-muted-foreground gap-2">
                  <Loader2 className="h-6 w-6 animate-spin text-primary" />
                  <p className="text-xs font-medium">Loading question bank items...</p>
                </div>
              ) : bankQuestions.length === 0 ? (
                <div className="p-8 rounded-xl border border-dashed border-border text-center text-xs text-muted-foreground space-y-2">
                  <p>Your question bank currently has 0 questions.</p>
                  <p>Upload a CSV, XLSX, or DOCX above to import your questions.</p>
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
                disabled={bankQuestions.length === 0}
                onClick={() => setCurrentStep(3)}
                className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-primary text-primary-foreground text-sm font-semibold hover:bg-primary/90 transition-all shadow-xs disabled:opacity-50"
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
                  Specify how many questions of each type to draw (e.g. 50 MCQ, 20 TF, 15 Short, 10 Long).
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
                  Question Type Quotas
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
              /* MANUAL PICK MODE */
              <div className="space-y-4">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                  <div className="relative flex-1">
                    <Search className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
                    <input
                      type="text"
                      placeholder="Search questions by text or topic..."
                      value={manualSearch}
                      onChange={(e) => setManualSearch(e.target.value)}
                      className="w-full pl-9 pr-4 py-2 rounded-xl border border-border text-xs focus:outline-hidden focus:ring-2 focus:ring-primary/20"
                    />
                  </div>
                  <select
                    value={manualTypeFilter}
                    onChange={(e) => setManualTypeFilter(e.target.value)}
                    className="px-3 py-2 rounded-xl border border-border text-xs bg-white focus:outline-hidden"
                  >
                    <option value="all">All Types</option>
                    <option value="mcq">MCQ</option>
                    <option value="true_false">True / False</option>
                    <option value="short">Short Answer</option>
                    <option value="long">Long Answer</option>
                  </select>
                </div>

                <div className="max-h-96 overflow-y-auto space-y-2 border border-border rounded-xl p-3 bg-slate-50/30">
                  {bankQuestions
                    .filter((q) => {
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
                    })
                    .map((q) => {
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
                              {q.question_text}
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
                    })}
                </div>
              </div>
            )}

            <div className="flex items-center justify-between pt-4 border-t border-border/80">
              <button
                type="button"
                onClick={() => setCurrentStep(2)}
                className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl border border-border text-xs font-semibold text-muted-foreground hover:text-foreground transition-colors"
              >
                <ArrowLeft className="h-3.5 w-3.5" /> Back to Bank
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
                  <p className="text-xs text-muted-foreground">{subject || "General Subject"}</p>
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

            {/* Action Buttons: Direct Publish vs Review & Edit */}
            <div className="p-5 rounded-2xl border border-primary/20 bg-primary/5 space-y-4">
              <div>
                <h4 className="text-sm font-bold text-foreground">Next Actions</h4>
                <p className="text-xs text-muted-foreground mt-0.5">
                  Choose whether to immediately publish this exam to your students, or inspect questions in the editor.
                </p>
              </div>

              <div className="flex flex-col sm:flex-row items-center gap-3">
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
    </DashboardLayout>
  );
}

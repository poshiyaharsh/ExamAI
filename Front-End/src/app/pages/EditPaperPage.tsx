import React, { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import {
  AlertCircle,
  AlertTriangle,
  ArrowLeft,
  Calendar,
  Check,
  CheckCircle2,
  Clock,
  Cpu,
  FileCheck2,
  FileText,
  Loader2,
  Plus,
  RefreshCw,
  Save,
  Scale,
  ShieldAlert,
  ShieldCheck,
  Shuffle,
  Sparkles,
  Trash2,
  X,
} from "lucide-react";
import { toast } from "sonner";
import { DashboardLayout } from "../components/DashboardLayout";
import { facultyExamApi, type ExamQuestion, type FacultyExam } from "../../services/api";

const menuItems = [
  { icon: Save, label: "Generate Paper", path: "/faculty/generate" },
  { icon: Check, label: "Exam History", path: "/faculty/history" },
];

export function canonicalizeQuestionType(raw: string | undefined | null): string {
  if (!raw) return "mcq";
  const s = String(raw).trim().toLowerCase();
  if (s === "mcq" || s === "multiple_choice") return "mcq";
  if (s === "true_false" || s === "truefalse" || s === "tf") return "true_false";
  if (s === "fill_blank" || s === "fillblank" || s === "fill_in_the_blank") return "fill_blank";
  if (s === "short_answer" || s === "short") return "short_answer";
  if (s === "long_answer" || s === "subjective" || s === "long") return "long_answer";
  return s;
}

export function canonicalizeDifficulty(raw: string | undefined | null): string {
  if (!raw) return "medium";
  const s = String(raw).trim().toLowerCase();
  if (s === "easy") return "easy";
  if (s === "medium" || s === "med") return "medium";
  if (s === "hard") return "hard";
  return s;
}

function toDatetimeLocal(isoStr: string | null | undefined): string {
  if (!isoStr) return "";
  try {
    const d = new Date(isoStr);
    if (isNaN(d.getTime())) return "";
    const pad = (n: number) => String(n).padStart(2, "0");
    const year = d.getFullYear();
    const month = pad(d.getMonth() + 1);
    const day = pad(d.getDate());
    const hours = pad(d.getHours());
    const mins = pad(d.getMinutes());
    return `${year}-${month}-${day}T${hours}:${mins}`;
  } catch {
    return "";
  }
}

function formatScheduleSummary(startStr: string, endStr: string, durationMin: number): string {
  if (!startStr || !endStr) return "";
  const s = new Date(startStr);
  const e = new Date(endStr);
  if (isNaN(s.getTime()) || isNaN(e.getTime())) return "";
  const dateOpts: Intl.DateTimeFormatOptions = {
    weekday: "short",
    day: "numeric",
    month: "short",
    hour: "numeric",
    minute: "numeric",
  };
  const sFmt = s.toLocaleDateString("en-US", dateOpts);
  const eFmt = e.toLocaleDateString("en-US", dateOpts);
  return `Opens ${sFmt} and closes ${eFmt}. Each student gets ${durationMin} minutes.`;
}

function questionPayload(question: ExamQuestion) {
  const canonType = canonicalizeQuestionType(question.question_type);
  const correctAnswer =
    canonType === "mcq" && /^\d+$/.test(String(question.correct_answer ?? ""))
      ? Number(question.correct_answer)
      : question.correct_answer;
  return {
    question_type: canonType,
    difficulty: canonicalizeDifficulty(question.difficulty),
    text: question.text,
    options: question.options,
    correct_answer: correctAnswer,
    model_answer: question.model_answer,
    accepted_answers: question.accepted_answers,
    rubric: question.rubric,
    word_limit: question.word_limit ? Number(question.word_limit) : undefined,
    marks: Number(question.marks),
    topic: question.topic,
  };
}

export function EditPaperPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const [exam, setExam] = useState<FacultyExam | null>(null);
  const [loading, setLoading] = useState(true);

  // Question action states
  const [savingId, setSavingId] = useState<number | null>(null);
  const [swappingId, setSwappingId] = useState<number | null>(null);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [shuffling, setShuffling] = useState(false);
  const [confirmingReview, setConfirmingReview] = useState(false);
  const [generatingMissing, setGeneratingMissing] = useState(false);

  // Scope Audit state
  const [checkingScope, setCheckingScope] = useState(false);
  const [scopeAudit, setScopeAudit] = useState<{
    exam_id: number;
    total_questions: number;
    in_scope_count: number;
    off_scope_count: number;
    questions: any[];
  } | null>(null);
  const [regeneratingId, setRegeneratingId] = useState<number | null>(null);
  const [regeneratingAnswerId, setRegeneratingAnswerId] = useState<number | null>(null);

  // Adjust Marks state
  const [showAdjustMarksModal, setShowAdjustMarksModal] = useState(false);
  const [adjustingMarks, setAdjustingMarks] = useState(false);
  const [scalePreview, setScalePreview] = useState<{
    target_marks: number;
    current_marks: number;
    scaling_factor: number;
    question_previews: Array<{
      id: number;
      current_marks: number;
      scaled_marks: number;
      question_type: string;
      text: string;
    }>;
  } | null>(null);

  // Filters synced to URL Search Params
  const filterType = searchParams.get("type") || "all";
  const filterDifficulty = searchParams.get("difficulty") || "all";

  const setFilterType = (t: string) => {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      if (t === "all") next.delete("type");
      else next.set("type", t);
      return next;
    }, { replace: true });
  };

  const setFilterDifficulty = (d: string) => {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      if (d === "all") next.delete("difficulty");
      else next.set("difficulty", d);
      return next;
    }, { replace: true });
  };

  // Publish Confirmation Modal & Schedule State
  const [showPublishModal, setShowPublishModal] = useState(false);
  const [publishing, setPublishing] = useState(false);
  const [scheduleStartsAt, setScheduleStartsAt] = useState("");
  const [scheduleEndsAt, setScheduleEndsAt] = useState("");
  const [scheduleTimezone, setScheduleTimezone] = useState("Asia/Kolkata");
  const [showScheduleEditor, setShowScheduleEditor] = useState(false);
  const [fieldErrors, setFieldErrors] = useState<{ starts_at?: string; ends_at?: string }>({});
  const isPublishingRef = useRef(false);

  // Add Question Modal
  const [showAddModal, setShowAddModal] = useState(false);
  const [newQType, setNewQType] = useState<"mcq" | "true_false" | "fill_blank" | "short_answer" | "long_answer">("mcq");
  const [newQText, setNewQText] = useState("");
  const [newQMarks, setNewQMarks] = useState("2");
  const [newQDiff, setNewQDiff] = useState<"easy" | "medium" | "hard">("medium");
  const [newQTopic, setNewQTopic] = useState("");
  const [newQOptions, setNewQOptions] = useState<string[]>(["", "", "", ""]);
  const [newQAnswer, setNewQAnswer] = useState("");
  const [newQModelAnswer, setNewQModelAnswer] = useState("");
  const [newQRubric, setNewQRubric] = useState("");
  const [newQWordLimit, setNewQWordLimit] = useState("");
  const [newQAcceptedAnswers, setNewQAcceptedAnswers] = useState("");
  const [addingQuestion, setAddingQuestion] = useState(false);

  // Live client-side validation for schedule inputs
  const scheduleValidation = useMemo(() => {
    const sStr = scheduleStartsAt;
    const eStr = scheduleEndsAt;
    const durMin = exam?.duration_minutes || 60;

    if (!sStr && !eStr) {
      return { valid: false, message: "Start time ('Available From') and deadline ('Deadline') are required to publish." };
    }
    if (!sStr) {
      return { valid: false, message: "Start time ('Available From') is required to publish an exam." };
    }
    if (!eStr) {
      return { valid: false, message: "End time ('Deadline') is required to publish an exam." };
    }

    const s = new Date(sStr).getTime();
    const e = new Date(eStr).getTime();
    if (isNaN(s) || isNaN(e)) {
      return { valid: false, message: "Please enter valid date and time values." };
    }
    if (e <= s) {
      return { valid: false, message: "Deadline (end time) must be after the start time." };
    }

    const windowMin = Math.floor((e - s) / 60000);
    if (windowMin < durMin) {
      return { valid: false, message: `Exam window (${windowMin} minutes) must be at least as long as exam duration (${durMin} minutes).` };
    }
    if (windowMin > 30 * 24 * 60) {
      return { valid: false, message: "Exam window cannot exceed 30 days." };
    }

    const now = Date.now();
    const graceMs = 5 * 60 * 1000;
    if (s < now - graceMs) {
      return { valid: false, message: "Start time cannot be in the past (allowed grace: 5 minutes)." };
    }

    return { valid: true, message: "" };
  }, [scheduleStartsAt, scheduleEndsAt, exam?.duration_minutes]);

  const handleOpenPublishModal = () => {
    setFieldErrors({});
    const existingStart = toDatetimeLocal(exam?.starts_at);
    const existingEnd = toDatetimeLocal(exam?.ends_at);
    setScheduleStartsAt(existingStart);
    setScheduleEndsAt(existingEnd);
    setScheduleTimezone(exam?.display_timezone || "Asia/Kolkata");
    setShowScheduleEditor(!existingStart || !existingEnd);
    setShowPublishModal(true);
  };

  useEffect(() => {
    if (!id) return;
    facultyExamApi
      .getExam(Number(id))
      .then(setExam)
      .catch(() => toast.error("Unable to load the generated paper."))
      .finally(() => setLoading(false));
  }, [id]);

  const updateQuestion = (questionId: number, update: Partial<ExamQuestion>) => {
    setExam((current) =>
      current
        ? {
            ...current,
            questions: current.questions?.map((q) => (q.id === questionId ? { ...q, ...update } : q)),
          }
        : current
    );
  };

  const saveQuestion = async (question: ExamQuestion) => {
    if (!id) return;
    setSavingId(question.id);
    try {
      const saved = await facultyExamApi.updateQuestion(Number(id), question.id, questionPayload(question));
      updateQuestion(question.id, saved);
      toast.success(`Question ${question.order} saved.`);
    } catch {
      toast.error("Unable to save this question.");
    } finally {
      setSavingId(null);
    }
  };

  const handleDeleteQuestion = async (questionId: number) => {
    if (!id || !window.confirm("Are you sure you want to delete this question?")) return;
    setDeletingId(questionId);
    try {
      await facultyExamApi.deleteQuestion(Number(id), questionId);
      setExam((current) =>
        current
          ? {
              ...current,
              questions: current.questions?.filter((q) => q.id !== questionId),
            }
          : current
      );
      toast.success("Question deleted.");
    } catch {
      toast.error("Failed to delete question.");
    } finally {
      setDeletingId(null);
    }
  };

  const handleShuffle = async () => {
    if (!id) return;
    setShuffling(true);
    try {
      const shuffled = await facultyExamApi.shuffleExam(Number(id));
      setExam(shuffled);
      toast.success("Questions & options reshuffled into a new variant!");
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || "Failed to reshuffle.");
    } finally {
      setShuffling(false);
    }
  };

  const handleSwap = async (questionId: number) => {
    if (!id) return;
    setSwappingId(questionId);
    try {
      const res = await facultyExamApi.swapQuestion(Number(id), questionId);
      updateQuestion(questionId, res.question);
      toast.success("Question replaced with a fresh candidate!");
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || "Failed to swap question.");
    } finally {
      setSwappingId(null);
    }
  };

  const handleConfirmReview = async () => {
    if (!id) return;
    setConfirmingReview(true);
    try {
      const res = await facultyExamApi.confirmReview(Number(id));
      setExam(res.exam);
      toast.success("Paper review confirmed! You can now publish this exam.");
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || "Failed to confirm review.");
    } finally {
      setConfirmingReview(false);
    }
  };

  const handleAddQuestionSubmit = async () => {
    if (!id || !newQText.trim()) {
      toast.error("Question text is required.");
      return;
    }
    setAddingQuestion(true);
    try {
      let accepted: any = undefined;
      if (newQType === "fill_blank" && newQAcceptedAnswers.trim()) {
        accepted = newQAcceptedAnswers.split(",").map((s) => s.trim()).filter(Boolean);
      }
      const created = await facultyExamApi.addQuestion(Number(id), {
        text: newQText.trim(),
        question_type: newQType,
        difficulty: newQDiff,
        marks: Number(newQMarks) || 1,
        topic: newQTopic.trim() || "General",
        options: newQType === "mcq" ? newQOptions.map((o) => o.trim()).filter(Boolean) : undefined,
        correct_answer: newQType === "true_false" ? newQAnswer || "True" : newQAnswer.trim(),
        model_answer: newQModelAnswer.trim() || undefined,
        rubric: newQRubric.trim() || undefined,
        word_limit: newQWordLimit ? Number(newQWordLimit) : undefined,
        accepted_answers: accepted,
      });
      setExam((current) =>
        current
          ? {
              ...current,
              questions: [...(current.questions || []), created],
            }
          : current
      );
      toast.success("Question added successfully!");
      setShowAddModal(false);
      setNewQText("");
      setNewQAnswer("");
      setNewQOptions(["", "", "", ""]);
      setNewQModelAnswer("");
      setNewQRubric("");
      setNewQWordLimit("");
      setNewQAcceptedAnswers("");
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || "Failed to add question.");
    } finally {
      setAddingQuestion(false);
    }
  };

  const handlePublishConfirmed = async () => {
    if (!id || isPublishingRef.current) return;

    if (!scheduleValidation.valid) {
      toast.error(scheduleValidation.message || "Please provide a valid exam schedule.", {
        id: "publish-schedule-error",
      });
      setShowScheduleEditor(true);
      return;
    }

    isPublishingRef.current = true;
    setPublishing(true);
    setFieldErrors({});

    try {
      const target = exam?.target_total_marks || exam?.total_marks || 0;
      const shortfallAmt = exam?.marks_shortfall || Math.max(0, target - computedTotalMarks);
      const isShortfall = shortfallAmt > 0;

      const schedulePayload = {
        starts_at: scheduleStartsAt ? new Date(scheduleStartsAt).toISOString() : null,
        ends_at: scheduleEndsAt ? new Date(scheduleEndsAt).toISOString() : null,
        display_timezone: scheduleTimezone || "Asia/Kolkata",
      };

      const published = await facultyExamApi.publishExam(Number(id), isShortfall, schedulePayload);
      setExam(published);
      setShowPublishModal(false);
      toast.success("Exam published successfully! Students can now access it during the scheduled window.");
      navigate("/faculty/history");
    } catch (err: any) {
      const respData = err?.response?.data;
      if (respData?.errors && Array.isArray(respData.errors)) {
        const errMap: Record<string, string> = {};
        for (const e of respData.errors) {
          if (e.field && e.message) {
            errMap[e.field] = e.message;
          }
        }
        setFieldErrors(errMap);
        setShowScheduleEditor(true);
        const firstMsg = respData.errors[0]?.message || respData.detail || "Please fix schedule errors.";
        toast.error(firstMsg, { id: "publish-schedule-error" });
      } else {
        const detail = respData?.detail || "Publishing failed.";
        const cleanMsg = detail.includes("; ") ? detail.split("; ")[0] : detail;
        toast.error(cleanMsg, { id: "publish-schedule-error" });
      }
    } finally {
      setPublishing(false);
      isPublishingRef.current = false;
    }
  };

  const handleGenerateMissing = async () => {
    if (!id) return;
    setGeneratingMissing(true);
    try {
      const res = await facultyExamApi.generateMissingQuestions(Number(id));
      toast.success(res.detail || "Successfully generated missing question(s)!");
      const refreshed = await facultyExamApi.getExam(Number(id));
      setExam(refreshed);
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || "Failed to generate missing questions.");
    } finally {
      setGeneratingMissing(false);
    }
  };

  const handleScopeAudit = async () => {
    if (!id) return;
    setCheckingScope(true);
    try {
      const res = await facultyExamApi.checkScope(Number(id));
      setScopeAudit(res);
      const scopeMap = new Map(res.questions.map((q) => [q.id, q]));
      setExam((current) =>
        current
          ? {
              ...current,
              questions: current.questions?.map((q) => {
                const audited = scopeMap.get(q.id);
                if (audited) {
                  return {
                    ...q,
                    is_off_scope: audited.is_off_scope,
                    scope_status: audited.scope_status as any,
                    scope_reason: audited.scope_reason,
                  };
                }
                return q;
              }),
            }
          : current
      );
      if (res.off_scope_count > 0) {
        toast.warning(
          `Scope Audit: ${res.off_scope_count} of ${res.total_questions} questions are off-scope. You can regenerate or delete them.`,
          { duration: 6000 }
        );
      } else {
        toast.success(`Scope Audit: All ${res.total_questions} questions verified strictly in-scope!`);
      }
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || "Failed to audit scope.");
    } finally {
      setCheckingScope(false);
    }
  };

  const handleRegenerateInScope = async (questionId: number) => {
    if (!id) return;
    setRegeneratingId(questionId);
    try {
      const res = await facultyExamApi.regenerateQuestion(Number(id), questionId);
      updateQuestion(questionId, res.question);
      toast.success("Question regenerated strictly from syllabus content!");
      if (scopeAudit) {
        handleScopeAudit();
      }
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || "Failed to regenerate question.");
    } finally {
      setRegeneratingId(null);
    }
  };

  const handleRegenerateAnswerOnly = async (questionId: number) => {
    if (!id) return;
    setRegeneratingAnswerId(questionId);
    try {
      const res = await facultyExamApi.regenerateQuestion(Number(id), questionId, undefined, "answer_only");
      updateQuestion(questionId, res.question);
      toast.success("Model answer and grading rubric regenerated!");
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || "Failed to regenerate model answer and rubric.");
    } finally {
      setRegeneratingAnswerId(null);
    }
  };

  const handleSetActualMarks = async () => {
    if (!id) return;
    setAdjustingMarks(true);
    try {
      const res = await facultyExamApi.adjustMarks(Number(id), "set_actual");
      setExam(res.exam);
      setShowAdjustMarksModal(false);
      setScalePreview(null);
      toast.success(res.detail || `Total marks updated to actual sum (${res.exam.total_marks}).`);
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || "Failed to adjust marks.");
    } finally {
      setAdjustingMarks(false);
    }
  };

  const handlePreviewScale = async () => {
    if (!id) return;
    setAdjustingMarks(true);
    try {
      const target = exam?.target_total_marks || exam?.total_marks || 100;
      const res = await facultyExamApi.adjustMarks(Number(id), "preview_scale", target);
      setScalePreview(res.preview || null);
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || "Failed to preview scaling.");
    } finally {
      setAdjustingMarks(false);
    }
  };

  const handleApplyScale = async () => {
    if (!id) return;
    setAdjustingMarks(true);
    try {
      const target = exam?.target_total_marks || exam?.total_marks || 100;
      const res = await facultyExamApi.adjustMarks(Number(id), "scale_target", target);
      setExam(res.exam);
      setShowAdjustMarksModal(false);
      setScalePreview(null);
      toast.success(res.detail || "Question marks scaled to meet target total!");
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || "Failed to scale marks.");
    } finally {
      setAdjustingMarks(false);
    }
  };

  const isPublished = exam?.status === "published" || exam?.is_immutable;
  const isReviewed = Boolean(exam?.is_reviewed);

  const typeCounts = useMemo(() => {
    const counts: Record<string, number> = {
      all: 0,
      mcq: 0,
      true_false: 0,
      fill_blank: 0,
      short_answer: 0,
      long_answer: 0,
    };
    (exam?.questions || []).forEach((q) => {
      const t = canonicalizeQuestionType(q.question_type);
      counts.all++;
      if (counts[t] !== undefined) {
        counts[t]++;
      }
    });
    return counts;
  }, [exam?.questions]);

  const diffCounts = useMemo(() => {
    const counts: Record<string, number> = {
      all: 0,
      easy: 0,
      medium: 0,
      hard: 0,
    };
    (exam?.questions || []).forEach((q) => {
      const d = canonicalizeDifficulty(q.difficulty);
      counts.all++;
      if (counts[d] !== undefined) {
        counts[d]++;
      }
    });
    return counts;
  }, [exam?.questions]);

  // Computations & Validation Checks
  const computedTotalMarks = useMemo(
    () => (exam?.questions || []).reduce((sum, q) => sum + (Number(q.marks) || 0), 0),
    [exam?.questions]
  );

  const targetTotalMarks = exam?.target_total_marks || exam?.total_marks || 0;
  const marksShortfall =
    exam?.marks_shortfall !== undefined && exam?.marks_shortfall > 0
      ? exam.marks_shortfall
      : Math.max(0, targetTotalMarks - computedTotalMarks);
  const hasShortfall = marksShortfall > 0;
  const marksMatch = computedTotalMarks === (exam?.total_marks || 0);

  const filteredQuestions = useMemo(() => {
    if (!exam?.questions) return [];
    return exam.questions.filter((q) => {
      if (filterType !== "all" && canonicalizeQuestionType(q.question_type) !== filterType) return false;
      if (filterDifficulty !== "all" && canonicalizeDifficulty(q.difficulty) !== filterDifficulty) return false;
      return true;
    });
  }, [exam?.questions, filterType, filterDifficulty]);

  const validationWarnings = useMemo(() => {
    if (!exam?.questions) return [];
    const warnings: string[] = [];

    // Check duplicate texts
    const seenTexts = new Set<string>();
    exam.questions.forEach((q, idx) => {
      const normalized = q.text.trim().toLowerCase();
      if (seenTexts.has(normalized)) {
        warnings.push(`Question ${q.order || idx + 1} has duplicate or near-duplicate text.`);
      }
      seenTexts.add(normalized);

      // Check MCQ answer in options
      const canonType = canonicalizeQuestionType(q.question_type);
      if (canonType === "mcq" && q.options && q.options.length > 0) {
        const correctStr = String(q.correct_answer ?? "").trim().toLowerCase();
        const cleanOpts = q.options.map((o) => o.trim().toLowerCase());
        const isLetter = ["a", "b", "c", "d"].includes(correctStr);
        const isNum = ["0", "1", "2", "3"].includes(correctStr);
        const isInList = cleanOpts.includes(correctStr);
        if (!isLetter && !isNum && !isInList && correctStr) {
          warnings.push(`Question ${q.order || idx + 1} ("${q.text.slice(0, 35)}..."): Correct answer does not match any listed option.`);
        }
      }
    });

    if (!marksMatch) {
      warnings.push(`Marks mismatch: Exam target is ${exam.total_marks} marks, but current question sum is ${computedTotalMarks} marks.`);
    }

    return warnings;
  }, [exam?.questions, exam?.total_marks, computedTotalMarks, marksMatch]);

  return (
    <DashboardLayout menuItems={menuItems} userRole="Faculty">
      <div className="space-y-6">
        {/* Navigation & Header */}
        <div className="flex items-center justify-between">
          <button
            type="button"
            onClick={() => navigate("/faculty/history")}
            className="inline-flex items-center gap-2 text-sm font-semibold text-muted-foreground hover:text-foreground transition-colors"
          >
            <ArrowLeft className="h-4 w-4" /> Back to My Papers
          </button>
        </div>

        {loading ? (
          <div className="py-16 flex flex-col items-center justify-center gap-3 text-muted-foreground">
            <Loader2 className="h-8 w-8 animate-spin text-primary" />
            <p className="text-sm font-medium">Loading paper details...</p>
          </div>
        ) : !exam ? (
          <div className="rounded-2xl border border-destructive/20 bg-rose-50 p-8 text-center text-sm text-destructive">
            Exam not found.
          </div>
        ) : (
          <>
            {/* Top Review Required Alert Banner */}
            {!isReviewed && !isPublished && (
              <div className="rounded-2xl border border-amber-300 bg-amber-50 p-5 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 shadow-xs animate-in fade-in">
                <div className="flex items-start gap-3">
                  <AlertTriangle className="h-5 w-5 text-amber-600 shrink-0 mt-0.5" />
                  <div>
                    <h3 className="font-bold text-sm text-amber-900">Review Required Before Publishing</h3>
                    <p className="text-xs text-amber-800 mt-0.5 leading-relaxed">
                      This AI synthesized draft requires faculty confirmation. Review questions and verify correct answers below, then click confirm to unlock publishing.
                    </p>
                  </div>
                </div>
                <button
                  type="button"
                  disabled={confirmingReview}
                  onClick={handleConfirmReview}
                  className="inline-flex items-center gap-1.5 rounded-xl bg-amber-600 px-4 py-2 text-xs font-bold text-white shadow-sm hover:bg-amber-700 disabled:opacity-50 shrink-0 transition-all"
                >
                  {confirmingReview ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <FileCheck2 className="h-3.5 w-3.5" />}
                  Confirm Review & Approve
                </button>
              </div>
            )}

            {/* Exam Meta Card */}
            <div className="rounded-2xl border border-border bg-white p-5 sm:p-6 shadow-sm space-y-4">
              <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
                <div className="space-y-1.5 min-w-0 flex-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    <h1 className="text-xl sm:text-2xl font-bold text-foreground">{exam.title}</h1>
                    <span
                      className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-bold border ${
                        isPublished
                          ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                          : isReviewed
                          ? "bg-sky-50 text-sky-700 border-sky-200"
                          : "bg-amber-50 text-amber-800 border-amber-200"
                      }`}
                    >
                      {isPublished ? <Check className="h-3 w-3" /> : isReviewed ? <CheckCircle2 className="h-3 w-3" /> : <AlertTriangle className="h-3 w-3" />}
                      {isPublished ? "Published" : isReviewed ? "Draft · Reviewed" : "Draft · Review Required"}
                    </span>
                    {!isPublished && (!exam.starts_at || !exam.ends_at) && (
                      <span className="inline-flex items-center gap-1 rounded-full bg-amber-50 text-amber-800 border border-amber-300 px-2.5 py-0.5 text-xs font-bold">
                        <Clock className="h-3 w-3 text-amber-600" /> Schedule Missing
                      </span>
                    )}
                    {isPublished && (
                      <span className="inline-flex items-center gap-1 rounded-full bg-blue-50 text-blue-700 border border-blue-200 px-2 py-0.5 text-xs font-medium">
                        <ShieldCheck className="h-3 w-3" /> Immutable
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-muted-foreground flex items-center gap-1 flex-wrap">
                    Department: <strong className="text-slate-800">{exam.department || "General"}</strong> · Created {new Date(exam.created_at).toLocaleDateString()}
                    {!isPublished && (!exam.starts_at || !exam.ends_at) ? (
                      <button
                        type="button"
                        onClick={handleOpenPublishModal}
                        className="inline-flex items-center gap-1 text-xs font-semibold text-blue-600 hover:text-blue-700 underline underline-offset-2 ml-1"
                      >
                        Add schedule
                      </button>
                    ) : exam.starts_at && exam.ends_at ? (
                      <span className="text-slate-600 ml-1">
                        · Schedule: <strong>{typeof exam.schedule_display === "object" && exam.schedule_display !== null ? (exam.schedule_display as any).summary : (typeof exam.schedule_display === "string" ? exam.schedule_display : "Configured")}</strong>
                      </span>
                    ) : null}
                  </p>
                </div>

                {/* Primary Action Buttons */}
                <div className="flex flex-wrap items-center gap-2 shrink-0">
                  {!isPublished && (
                    <>
                      <button
                        type="button"
                        onClick={() => setShowAddModal(true)}
                        className="inline-flex items-center gap-1.5 rounded-xl border border-border bg-white px-3.5 py-2 text-xs font-semibold text-foreground hover:bg-muted/50 transition-colors"
                      >
                        <Plus className="h-4 w-4" /> Add Question
                      </button>
                      <button
                        type="button"
                        disabled={checkingScope}
                        onClick={handleScopeAudit}
                        className="inline-flex items-center gap-1.5 rounded-xl border border-border bg-white px-3.5 py-2 text-xs font-semibold text-foreground hover:bg-muted/50 transition-colors disabled:opacity-50"
                        title="Audit question scope against syllabus content"
                      >
                        {checkingScope ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <ShieldAlert className="h-3.5 w-3.5 text-blue-600" />}
                        {checkingScope ? "Auditing..." : "Audit Scope"}
                      </button>
                      <button
                        type="button"
                        disabled={shuffling}
                        onClick={handleShuffle}
                        className="inline-flex items-center gap-1.5 rounded-xl border border-border bg-white px-3.5 py-2 text-xs font-semibold text-foreground hover:bg-muted/50 transition-colors disabled:opacity-50"
                        title="Reshuffle question and option order into a fresh variant"
                      >
                        <Shuffle className="h-3.5 w-3.5" /> {shuffling ? "Shuffling..." : "Reshuffle"}
                      </button>
                    </>
                  )}

                  {!isPublished && (
                    <button
                      type="button"
                      onClick={() => {
                        if (!isReviewed) {
                          toast.error("Please confirm review of the draft paper before publishing.", {
                            action: { label: "Confirm Review", onClick: handleConfirmReview },
                          });
                          return;
                        }
                        handleOpenPublishModal();
                      }}
                      className="inline-flex items-center gap-1.5 rounded-xl bg-gradient-to-r from-emerald-600 to-teal-600 px-4 py-2 text-xs font-bold text-white shadow-sm hover:opacity-95 transition-all"
                    >
                      <Check className="h-4 w-4" /> Publish Exam
                    </button>
                  )}
                </div>
              </div>

              {/* Summary Stats Grid */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-3 border-t border-border/60 text-xs">
                <div className="bg-slate-50 rounded-xl p-3 border border-slate-100">
                  <span className="text-muted-foreground block text-[11px] font-medium">Questions</span>
                  <strong className="text-base text-foreground font-bold">{exam.questions?.length ?? 0} Questions</strong>
                </div>
                <div className="bg-slate-50 rounded-xl p-3 border border-slate-100">
                  <span className="text-muted-foreground block text-[11px] font-medium">Total Marks</span>
                  <strong className={`text-base font-bold ${!hasShortfall && marksMatch ? "text-emerald-700" : "text-amber-700"}`}>
                    {computedTotalMarks} / {targetTotalMarks} Marks
                  </strong>
                  {hasShortfall && (
                    <span className="text-[10px] text-amber-700 font-bold block mt-0.5">
                      {marksShortfall} Marks Shortfall
                    </span>
                  )}
                </div>
                <div className="bg-slate-50 rounded-xl p-3 border border-slate-100">
                  <span className="text-muted-foreground block text-[11px] font-medium">Duration</span>
                  <strong className="text-base text-foreground font-bold">{exam.duration_minutes} Minutes</strong>
                </div>
                <div className="bg-slate-50 rounded-xl p-3 border border-slate-100">
                  <span className="text-muted-foreground block text-[11px] font-medium">AI Model</span>
                  <strong className="text-xs font-mono text-slate-800 truncate block mt-0.5">{exam.ai_model_used || "Standard"}</strong>
                </div>
              </div>
            </div>

            {/* Prominent Marks Shortfall Banner */}
            {hasShortfall && !isPublished && (
              <div className="rounded-2xl border-2 border-amber-400 bg-amber-50/90 p-5 space-y-4 shadow-sm animate-in fade-in">
                <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3">
                  <div className="flex items-start gap-3">
                    <div className="p-2 rounded-xl bg-amber-100 text-amber-800 shrink-0 mt-0.5">
                      <AlertTriangle className="h-5 w-5" />
                    </div>
                    <div>
                      <h3 className="font-bold text-sm text-amber-950 flex items-center gap-2">
                        Marks Shortfall Detected ({marksShortfall} Marks Missing)
                      </h3>
                      <p className="text-xs text-amber-900 mt-1 leading-relaxed">
                        The requested paper target is <strong>{targetTotalMarks} marks</strong>, but currently only <strong>{computedTotalMarks} marks</strong> across <strong>{exam.questions?.length ?? 0} questions</strong> are generated.
                        Please resolve the shortfall using one of the actions below before publishing.
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2 shrink-0 self-start sm:self-auto">
                    <span className="rounded-full bg-amber-200/80 px-3 py-1 text-xs font-bold text-amber-950">
                      {computedTotalMarks} / {targetTotalMarks} Marks
                    </span>
                  </div>
                </div>

                {/* 3 Shortfall Action Options */}
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5 pt-1 border-t border-amber-200/80">
                  <button
                    type="button"
                    disabled={generatingMissing}
                    onClick={handleGenerateMissing}
                    className="flex items-center justify-center gap-1.5 rounded-xl bg-amber-600 px-3.5 py-2 text-xs font-bold text-white shadow-2xs hover:bg-amber-700 disabled:opacity-50 transition-all"
                  >
                    {generatingMissing ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Sparkles className="h-3.5 w-3.5" />}
                    {generatingMissing ? "Generating..." : "1. Generate Missing Questions"}
                  </button>
                  <button
                    type="button"
                    onClick={() => setShowAddModal(true)}
                    className="flex items-center justify-center gap-1.5 rounded-xl border border-amber-300 bg-white px-3.5 py-2 text-xs font-bold text-amber-900 shadow-2xs hover:bg-amber-100/60 transition-all"
                  >
                    <Plus className="h-3.5 w-3.5" />
                    2. Add Questions Manually
                  </button>
                  <button
                    type="button"
                    onClick={() => setShowAdjustMarksModal(true)}
                    className="flex items-center justify-center gap-1.5 rounded-xl border border-amber-300 bg-white px-3.5 py-2 text-xs font-bold text-amber-900 shadow-2xs hover:bg-amber-100/60 transition-all"
                  >
                    <Scale className="h-3.5 w-3.5" />
                    3. Adjust Marks (Set Actual / Scale)
                  </button>
                </div>
              </div>
            )}

            {/* Validation Warnings & Question Type Breakdown */}
            {(validationWarnings.length > 0 || !marksMatch) && (
              <div className="rounded-2xl border border-amber-200 bg-amber-50/70 p-4 space-y-3">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                  <div className="flex items-center gap-2 text-amber-900 font-bold text-xs">
                    <AlertTriangle className="h-4 w-4 text-amber-600 shrink-0" />
                    Validation Audit & Breakdown
                  </div>
                  {!isPublished && (
                    <button
                      type="button"
                      disabled={generatingMissing}
                      onClick={handleGenerateMissing}
                      className="inline-flex items-center gap-1.5 rounded-xl bg-amber-600 px-3.5 py-1.5 text-xs font-bold text-white shadow-xs hover:bg-amber-700 disabled:opacity-50 transition-all shrink-0 self-start sm:self-auto"
                    >
                      {generatingMissing ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Sparkles className="h-3.5 w-3.5" />}
                      {generatingMissing ? "Generating Missing Questions..." : "Generate Missing Questions"}
                    </button>
                  )}
                </div>

                {/* Question Type Breakdown Pills */}
                <div className="flex flex-wrap items-center gap-2 pt-1">
                  <span className="text-[11px] font-semibold text-amber-900">Current Distribution:</span>
                  <span className="inline-flex items-center px-2 py-0.5 rounded-md text-[11px] font-medium bg-amber-100 text-amber-900 border border-amber-200">
                    MCQ: {typeCounts.mcq}
                  </span>
                  <span className="inline-flex items-center px-2 py-0.5 rounded-md text-[11px] font-medium bg-amber-100 text-amber-900 border border-amber-200">
                    True/False: {typeCounts.true_false}
                  </span>
                  <span className="inline-flex items-center px-2 py-0.5 rounded-md text-[11px] font-medium bg-amber-100 text-amber-900 border border-amber-200">
                    Fill Blank: {typeCounts.fill_blank}
                  </span>
                  <span className="inline-flex items-center px-2 py-0.5 rounded-md text-[11px] font-medium bg-amber-100 text-amber-900 border border-amber-200">
                    Short Answer: {typeCounts.short_answer}
                  </span>
                  <span className={`inline-flex items-center px-2 py-0.5 rounded-md text-[11px] font-bold border ${
                    typeCounts.long_answer > 0 ? "bg-amber-100 text-amber-900 border-amber-200" : "bg-rose-100 text-rose-800 border-rose-300"
                  }`}>
                    Long Answer: {typeCounts.long_answer}
                  </span>
                </div>

                <ul className="list-disc list-inside space-y-1 text-xs text-amber-800 pt-1 border-t border-amber-200/60">
                  {validationWarnings.map((w, idx) => (
                    <li key={idx}>{w}</li>
                  ))}
                </ul>
              </div>
            )}

            {/* Questions List & Filter Controls */}
            <div className="space-y-4">
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
                <div>
                  <h3 className="font-bold text-base text-foreground">
                    Questions ({exam.questions?.length ?? 0})
                    {(filterType !== "all" || filterDifficulty !== "all") && (
                      <span className="ml-2 text-xs font-normal text-muted-foreground">
                        · Showing {filteredQuestions.length} of {exam.questions?.length ?? 0}
                      </span>
                    )}
                  </h3>
                  <p className="text-xs text-muted-foreground">
                    Review and calibrate questions, accepted answers, and grading rubrics before publishing.
                  </p>
                </div>

                {/* Filter Pills */}
                <div className="flex flex-wrap items-center gap-2">
                  <div className="flex items-center gap-1 bg-slate-100 p-1 rounded-xl text-xs font-semibold">
                    {[
                      { key: "all", label: `All (${typeCounts.all})` },
                      { key: "mcq", label: `MCQ (${typeCounts.mcq})` },
                      { key: "true_false", label: `True/False (${typeCounts.true_false})` },
                      { key: "fill_blank", label: `Fill Blank (${typeCounts.fill_blank})` },
                      { key: "short_answer", label: `Short (${typeCounts.short_answer})` },
                      { key: "long_answer", label: `Long (${typeCounts.long_answer})` },
                    ].map((t) => (
                      <button
                        key={t.key}
                        type="button"
                        role="button"
                        aria-pressed={filterType === t.key}
                        onClick={() => setFilterType(t.key)}
                        className={`px-2.5 py-1 rounded-lg transition-all ${
                          filterType === t.key
                            ? "bg-white text-primary shadow-xs font-bold"
                            : "text-slate-600 hover:text-slate-900"
                        }`}
                      >
                        {t.label}
                      </button>
                    ))}
                  </div>

                  <div className="flex items-center gap-1 bg-slate-100 p-1 rounded-xl text-xs font-semibold">
                    {[
                      { key: "all", label: `All Diff (${diffCounts.all})` },
                      { key: "easy", label: `Easy (${diffCounts.easy})` },
                      { key: "medium", label: `Med (${diffCounts.medium})` },
                      { key: "hard", label: `Hard (${diffCounts.hard})` },
                    ].map((d) => (
                      <button
                        key={d.key}
                        type="button"
                        role="button"
                        aria-pressed={filterDifficulty === d.key}
                        onClick={() => setFilterDifficulty(d.key)}
                        className={`px-2 py-1 rounded-lg transition-all ${
                          filterDifficulty === d.key
                            ? "bg-white text-slate-900 shadow-xs font-bold"
                            : "text-slate-500 hover:text-slate-900"
                        }`}
                      >
                        {d.label}
                      </button>
                    ))}
                  </div>
                </div>
              </div>

              {filteredQuestions.length === 0 ? (
                <div className="rounded-2xl border border-dashed border-border bg-slate-50/50 p-8 text-center text-sm text-muted-foreground space-y-3">
                  <p>No questions match your current type/difficulty filter.</p>
                  <button
                    type="button"
                    onClick={() => {
                      setFilterType("all");
                      setFilterDifficulty("all");
                    }}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-primary text-primary-foreground hover:bg-primary/90 transition-all"
                  >
                    Clear Filters
                  </button>
                </div>
              ) : (
                filteredQuestions.map((question, qIdx) => {
                  const qType = canonicalizeQuestionType(question.question_type);
                  const qDiff = canonicalizeDifficulty(question.difficulty);
                  const typeBadgeColor =
                    qType === "mcq"
                      ? "bg-blue-50 text-blue-700 border-blue-200"
                      : qType === "true_false"
                      ? "bg-amber-50 text-amber-700 border-amber-200"
                      : qType === "fill_blank"
                      ? "bg-purple-50 text-purple-700 border-purple-200"
                      : qType === "short_answer"
                      ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                      : "bg-indigo-50 text-indigo-700 border-indigo-200";

                  const diffBadgeColor =
                    qDiff === "easy"
                      ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                      : qDiff === "hard"
                      ? "bg-rose-50 text-rose-700 border-rose-200"
                      : "bg-amber-50 text-amber-700 border-amber-200";

                  return (
                    <section
                      key={question.id}
                      className="rounded-2xl border border-border bg-white p-5 sm:p-6 shadow-xs hover:shadow-md transition-all space-y-4"
                    >
                      <div className="flex items-center justify-between gap-4">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="flex h-7 px-2.5 items-center justify-center rounded-lg bg-slate-100 text-xs font-bold text-slate-700">
                            #{question.order || qIdx + 1}
                          </span>
                          <span className={`rounded-full px-2.5 py-0.5 text-xs font-bold border ${typeBadgeColor} uppercase`}>
                            {qType.replace("_", " ")}
                          </span>
                          <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-semibold text-slate-600">
                            {question.marks} {Number(question.marks) === 1 ? "Mark" : "Marks"}
                          </span>
                          <span className={`rounded-full px-2 py-0.5 text-xs font-semibold border ${diffBadgeColor} uppercase`}>
                            {qDiff}
                          </span>
                          {question.topic && (
                            <span className="rounded-full bg-slate-50 border border-slate-200 px-2.5 py-0.5 text-xs text-slate-600">
                              Unit: {question.topic}
                            </span>
                          )}
                          {(question.is_off_scope || question.scope_status === "off_scope") && (
                            <span
                              className="rounded-full bg-rose-50 border border-rose-300 text-rose-800 px-2.5 py-0.5 text-xs font-bold flex items-center gap-1"
                              title={question.scope_reason || "Topic or content not found in uploaded syllabus"}
                            >
                              <AlertCircle className="h-3 w-3 text-rose-600" />
                              Off-Scope
                            </span>
                          )}
                        </div>

                        {!isPublished && (
                          <div className="flex items-center gap-1.5">
                            {(question.is_off_scope || question.scope_status === "off_scope") && (
                              <button
                                type="button"
                                disabled={regeneratingId === question.id}
                                onClick={() => handleRegenerateInScope(question.id)}
                                className="inline-flex items-center gap-1 rounded-lg border border-rose-300 bg-rose-50 px-2.5 py-1.5 text-xs font-bold text-rose-800 hover:bg-rose-100 transition-colors disabled:opacity-50"
                                title="Regenerate this question strictly within syllabus scope"
                              >
                                {regeneratingId === question.id ? (
                                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                                ) : (
                                  <RefreshCw className="h-3.5 w-3.5" />
                                )}
                                <span className="hidden sm:inline">Regenerate In-Scope</span>
                              </button>
                            )}
                            <button
                              type="button"
                              disabled={swappingId === question.id}
                              onClick={() => handleSwap(question.id)}
                              className="inline-flex items-center gap-1 rounded-lg border border-border px-2.5 py-1.5 text-xs font-medium text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors disabled:opacity-50"
                              title="Regenerate / swap with a fresh alternative"
                            >
                              <RefreshCw className={`h-3.5 w-3.5 ${swappingId === question.id ? "animate-spin" : ""}`} />
                              <span className="hidden sm:inline">Swap</span>
                            </button>
                            <button
                              type="button"
                              disabled={savingId === question.id}
                              onClick={() => saveQuestion(question)}
                              className="inline-flex items-center gap-1 rounded-lg bg-primary/10 text-primary px-3 py-1.5 text-xs font-semibold hover:bg-primary/20 transition-colors disabled:opacity-50"
                            >
                              <Save className="h-3.5 w-3.5" />
                              {savingId === question.id ? "Saving..." : "Save"}
                            </button>
                            <button
                              type="button"
                              disabled={deletingId === question.id}
                              onClick={() => handleDeleteQuestion(question.id)}
                              className="p-1.5 rounded-lg text-rose-500 hover:bg-rose-50 hover:text-rose-700 transition-colors"
                              title="Delete question"
                            >
                              <Trash2 className="h-4 w-4" />
                            </button>
                          </div>
                        )}
                      </div>

                      {/* Question Text */}
                      <div>
                        <label className="block text-[11px] font-semibold text-muted-foreground uppercase mb-1">
                          Question Prompt {qType === "fill_blank" && "(Use ____ for blanks)"}
                        </label>
                        <textarea
                          value={question.text}
                          disabled={isPublished}
                          onChange={(e) => updateQuestion(question.id, { text: e.target.value })}
                          rows={3}
                          className="w-full rounded-xl border border-border bg-muted/15 p-3 text-sm focus:outline-hidden focus:ring-2 focus:ring-primary/20 focus:border-primary transition-all disabled:opacity-75"
                        />
                      </div>

                      {/* MCQ Options Rendering */}
                      {qType === "mcq" && question.options && question.options.length > 0 && (
                        <div className="space-y-2 pt-1">
                          <label className="block text-[11px] font-semibold text-muted-foreground uppercase">
                            Options & Correct Choice
                          </label>
                          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                            {question.options.map((opt, oIdx) => {
                              const letter = String.fromCharCode(65 + oIdx);
                              const isSelected =
                                String(question.correct_answer).toUpperCase() === letter ||
                                String(question.correct_answer).trim().toLowerCase() === opt.trim().toLowerCase();
                              return (
                                <div
                                  key={oIdx}
                                  className={`flex items-center gap-2 rounded-xl border p-2 transition-all ${
                                    isSelected
                                      ? "border-emerald-500 bg-emerald-50/40 ring-1 ring-emerald-500/30"
                                      : "border-border/80 bg-muted/10"
                                  }`}
                                >
                                  <button
                                    type="button"
                                    disabled={isPublished}
                                    onClick={() => updateQuestion(question.id, { correct_answer: letter })}
                                    className={`h-6 w-6 rounded-lg text-xs font-bold transition-all shrink-0 ${
                                      isSelected ? "bg-emerald-600 text-white" : "bg-slate-200 text-slate-700 hover:bg-primary/20"
                                    }`}
                                    title={`Click to set ${letter} as correct`}
                                  >
                                    {letter}
                                  </button>
                                  <input
                                    type="text"
                                    disabled={isPublished}
                                    value={opt}
                                    onChange={(e) => {
                                      const next = [...question.options!];
                                      next[oIdx] = e.target.value;
                                      updateQuestion(question.id, { options: next });
                                    }}
                                    className="w-full bg-transparent text-xs text-foreground focus:outline-hidden"
                                    placeholder={`Option ${letter}`}
                                  />
                                </div>
                              );
                            })}
                          </div>
                        </div>
                      )}

                      {/* True/False Buttons */}
                      {qType === "true_false" && (
                        <div className="space-y-1.5 pt-1">
                          <label className="block text-[11px] font-semibold text-muted-foreground uppercase">
                            Correct Answer Key
                          </label>
                          <div className="flex items-center gap-3">
                            {["True", "False"].map((tf) => {
                              const isMatch = String(question.correct_answer).trim().toLowerCase() === tf.toLowerCase();
                              return (
                                <button
                                  key={tf}
                                  type="button"
                                  disabled={isPublished}
                                  onClick={() => updateQuestion(question.id, { correct_answer: tf })}
                                  className={`px-5 py-2 rounded-xl text-xs font-bold border transition-all ${
                                    isMatch
                                      ? "bg-amber-600 text-white border-amber-600 shadow-xs"
                                      : "bg-muted/10 text-muted-foreground border-border hover:bg-muted/30"
                                  }`}
                                >
                                  {tf}
                                </button>
                              );
                            })}
                          </div>
                        </div>
                      )}

                      {/* Fill in the Blank Preview & Accepted Answers */}
                      {qType === "fill_blank" && (
                        <div className="space-y-3 pt-1">
                          <div className="rounded-xl border border-purple-200 bg-purple-50/40 p-3">
                            <span className="text-[11px] font-bold text-purple-900 uppercase block mb-1">
                              Student View Preview:
                            </span>
                            <p className="text-xs text-purple-950 font-medium">
                              {question.text.split(/_{3,}/).map((chunk, cIdx, arr) => (
                                <React.Fragment key={cIdx}>
                                  {chunk}
                                  {cIdx < arr.length - 1 && (
                                    <span className="inline-block mx-1.5 px-3 py-0.5 rounded-md bg-white border border-purple-300 font-mono text-[11px] text-purple-700 font-bold shadow-2xs">
                                      [ Blank #{cIdx + 1} ]
                                    </span>
                                  )}
                                </React.Fragment>
                              ))}
                            </p>
                          </div>

                          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                            <div>
                              <label className="block text-[11px] font-semibold text-muted-foreground uppercase mb-1">
                                Primary Correct Answer(s)
                              </label>
                              <input
                                type="text"
                                disabled={isPublished}
                                value={String(question.correct_answer ?? "")}
                                onChange={(e) => updateQuestion(question.id, { correct_answer: e.target.value })}
                                className="w-full rounded-xl border border-border bg-muted/15 px-3 py-1.5 text-xs focus:outline-hidden focus:border-primary"
                                placeholder="e.g. oxygen (or comma-separated for multi-blanks)"
                              />
                            </div>
                            <div>
                              <label className="block text-[11px] font-semibold text-muted-foreground uppercase mb-1">
                                Accepted Synonyms / Alternatives (JSON or comma-separated)
                              </label>
                              <input
                                type="text"
                                disabled={isPublished}
                                value={
                                  Array.isArray(question.accepted_answers)
                                    ? JSON.stringify(question.accepted_answers)
                                    : String(question.accepted_answers ?? "")
                                }
                                onChange={(e) => {
                                  let val: any = e.target.value;
                                  try {
                                    val = JSON.parse(e.target.value);
                                  } catch {
                                    // keep string
                                  }
                                  updateQuestion(question.id, { accepted_answers: val });
                                }}
                                className="w-full rounded-xl border border-border bg-muted/15 px-3 py-1.5 text-xs focus:outline-hidden focus:border-primary font-mono"
                                placeholder='e.g. [["O2", "oxygen"]]'
                              />
                            </div>
                          </div>
                        </div>
                      )}

                      {/* Short Answer & Long Answer: Model Answer, Rubric, Word Limit */}
                      {(qType === "short_answer" || qType === "long_answer") && (
                        <div className="space-y-3 pt-1">
                          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                            <div>
                              <div className="flex items-center justify-between mb-1">
                                <label className="block text-[11px] font-semibold text-muted-foreground uppercase">
                                  Model Answer / Expected Concepts
                                </label>
                                {!isPublished && (
                                  <button
                                    type="button"
                                    disabled={regeneratingAnswerId === question.id}
                                    onClick={() => handleRegenerateAnswerOnly(question.id)}
                                    className="inline-flex items-center gap-1 text-[11px] font-semibold text-primary hover:underline disabled:opacity-50"
                                    title="Regenerate only model answer and rubric without changing question text"
                                  >
                                    {regeneratingAnswerId === question.id ? (
                                      <Loader2 className="h-3 w-3 animate-spin" />
                                    ) : (
                                      <Sparkles className="h-3 w-3" />
                                    )}
                                    Regenerate Answer & Rubric
                                  </button>
                                )}
                              </div>
                              <textarea
                                value={question.model_answer || ""}
                                disabled={isPublished}
                                onChange={(e) => updateQuestion(question.id, { model_answer: e.target.value })}
                                rows={4}
                                className="w-full rounded-xl border border-border bg-muted/15 p-2.5 text-xs focus:outline-hidden focus:border-primary disabled:opacity-75"
                                placeholder="Key points and terms required in student response..."
                              />
                            </div>
                            <div>
                              <label className="block text-[11px] font-semibold text-muted-foreground uppercase mb-1">
                                Grading Rubric / Criteria
                              </label>
                              <textarea
                                value={
                                  typeof question.rubric === "string"
                                    ? question.rubric
                                    : Array.isArray(question.rubric)
                                    ? JSON.stringify(question.rubric, null, 2)
                                    : ""
                                }
                                disabled={isPublished}
                                onChange={(e) => {
                                  const rawVal = e.target.value;
                                  try {
                                    const parsed = JSON.parse(rawVal);
                                    updateQuestion(question.id, { rubric: parsed });
                                  } catch {
                                    updateQuestion(question.id, { rubric: rawVal as any });
                                  }
                                }}
                                rows={4}
                                className="w-full rounded-xl border border-border bg-muted/15 p-2.5 text-xs font-mono focus:outline-hidden focus:border-primary disabled:opacity-75"
                                placeholder='[{"criterion": "...", "marks": 2}]'
                              />
                            </div>
                          </div>
                          <div className="w-48">
                            <label className="block text-[11px] font-semibold text-muted-foreground uppercase mb-1">
                              Word Limit (Optional)
                            </label>
                            <input
                              type="number"
                              min={10}
                              max={1000}
                              disabled={isPublished}
                              value={question.word_limit || ""}
                              onChange={(e) =>
                                updateQuestion(question.id, {
                                  word_limit: e.target.value ? Number(e.target.value) : undefined,
                                })
                              }
                              className="w-full rounded-xl border border-border bg-muted/15 px-3 py-1.5 text-xs focus:outline-hidden focus:border-primary"
                              placeholder="e.g. 50 (short) or 250 (long)"
                            />
                          </div>
                        </div>
                      )}

                      {/* Topic, Marks, and Difficulty Inline Calibrator */}
                      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-2 border-t border-border/50">
                        <div>
                          <label className="block text-[11px] font-semibold text-muted-foreground uppercase mb-1">
                            Topic / Unit
                          </label>
                          <input
                            type="text"
                            disabled={isPublished}
                            value={question.topic || ""}
                            onChange={(e) => updateQuestion(question.id, { topic: e.target.value })}
                            className="w-full rounded-xl border border-border bg-muted/15 px-3 py-1.5 text-xs focus:outline-hidden focus:border-primary"
                            placeholder="Unit / Topic title"
                          />
                        </div>
                        <div>
                          <label className="block text-[11px] font-semibold text-muted-foreground uppercase mb-1">
                            Difficulty Level
                          </label>
                          <select
                            disabled={isPublished}
                            value={question.difficulty}
                            onChange={(e: any) => updateQuestion(question.id, { difficulty: e.target.value })}
                            className="w-full rounded-xl border border-border bg-muted/15 px-3 py-1.5 text-xs capitalize focus:outline-hidden focus:border-primary"
                          >
                            <option value="easy">Easy</option>
                            <option value="medium">Medium</option>
                            <option value="hard">Hard</option>
                          </select>
                        </div>
                        <div>
                          <label className="block text-[11px] font-semibold text-muted-foreground uppercase mb-1">
                            Marks
                          </label>
                          <input
                            type="number"
                            min={1}
                            max={50}
                            disabled={isPublished}
                            value={question.marks}
                            onChange={(e) => updateQuestion(question.id, { marks: Number(e.target.value) })}
                            className="w-full rounded-xl border border-border bg-muted/15 px-3 py-1.5 text-xs focus:outline-hidden focus:border-primary"
                          />
                        </div>
                      </div>
                    </section>
                  );
                })
              )}
            </div>
          </>
        )}

        {/* Add Question Modal (All 5 Types Supported) */}
        {showAddModal && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4 animate-in fade-in duration-150">
            <div className="bg-white rounded-2xl border border-border shadow-2xl w-full max-w-lg p-6 space-y-4 animate-in zoom-in-95 duration-150 max-h-[90vh] overflow-y-auto">
              <div className="flex items-center justify-between border-b border-border pb-3">
                <div>
                  <h3 className="font-bold text-base text-foreground">Add Custom Question</h3>
                  <p className="text-xs text-muted-foreground">Add a new calibrated question of any supported format.</p>
                </div>
                <button type="button" onClick={() => setShowAddModal(false)} className="p-1.5 text-muted-foreground hover:text-foreground">
                  <X className="h-5 w-5" />
                </button>
              </div>

              <div className="space-y-3">
                <div className="grid grid-cols-3 gap-2.5">
                  <div>
                    <label className="block text-xs font-semibold text-slate-700 mb-1">Question Type</label>
                    <select
                      value={newQType}
                      onChange={(e: any) => setNewQType(e.target.value)}
                      className="w-full rounded-xl border border-border bg-muted/10 px-3 py-2 text-xs"
                    >
                      <option value="mcq">MCQ</option>
                      <option value="true_false">True / False</option>
                      <option value="fill_blank">Fill in Blanks</option>
                      <option value="short_answer">Short Answer</option>
                      <option value="long_answer">Long Answer</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-slate-700 mb-1">Difficulty</label>
                    <select
                      value={newQDiff}
                      onChange={(e: any) => setNewQDiff(e.target.value)}
                      className="w-full rounded-xl border border-border bg-muted/10 px-3 py-2 text-xs capitalize"
                    >
                      <option value="easy">Easy</option>
                      <option value="medium">Medium</option>
                      <option value="hard">Hard</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-slate-700 mb-1">Marks</label>
                    <input
                      type="number"
                      min={1}
                      max={50}
                      value={newQMarks}
                      onChange={(e) => setNewQMarks(e.target.value)}
                      className="w-full rounded-xl border border-border bg-muted/10 px-3 py-2 text-xs"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Question Text * {newQType === "fill_blank" && <span className="text-purple-600">(Use ____ for blanks)</span>}
                  </label>
                  <textarea
                    value={newQText}
                    onChange={(e) => setNewQText(e.target.value)}
                    rows={3}
                    placeholder={
                      newQType === "fill_blank"
                        ? "e.g. Photosynthesis converts ____ and water into glucose and ____."
                        : "Enter question prompt..."
                    }
                    className="w-full rounded-xl border border-border bg-muted/10 p-2.5 text-xs focus:outline-hidden"
                  />
                </div>

                {/* MCQ Options */}
                {newQType === "mcq" && (
                  <div className="space-y-2">
                    <label className="block text-xs font-semibold text-slate-700">Answer Options</label>
                    {newQOptions.map((opt, i) => (
                      <div key={i} className="flex items-center gap-2">
                        <span className="text-xs font-bold text-primary w-4">{String.fromCharCode(65 + i)}</span>
                        <input
                          type="text"
                          value={opt}
                          onChange={(e) => {
                            const next = [...newQOptions];
                            next[i] = e.target.value;
                            setNewQOptions(next);
                          }}
                          placeholder={`Option ${String.fromCharCode(65 + i)}`}
                          className="flex-1 rounded-xl border border-border bg-muted/10 px-3 py-1.5 text-xs"
                        />
                      </div>
                    ))}
                    <div>
                      <label className="block text-xs font-semibold text-slate-700 mt-2 mb-1">Correct Option</label>
                      <select
                        value={newQAnswer}
                        onChange={(e) => setNewQAnswer(e.target.value)}
                        className="w-full rounded-xl border border-border bg-muted/10 px-3 py-2 text-xs"
                      >
                        <option value="">Select correct option...</option>
                        {newQOptions.map((opt, i) => (
                          <option key={i} value={String.fromCharCode(65 + i)}>
                            Option {String.fromCharCode(65 + i)} ({opt || "Empty"})
                          </option>
                        ))}
                      </select>
                    </div>
                  </div>
                )}

                {/* True / False */}
                {newQType === "true_false" && (
                  <div>
                    <label className="block text-xs font-semibold text-slate-700 mb-1">Correct Answer *</label>
                    <div className="flex items-center gap-3">
                      {["True", "False"].map((tf) => (
                        <button
                          key={tf}
                          type="button"
                          onClick={() => setNewQAnswer(tf)}
                          className={`flex-1 py-2 rounded-xl text-xs font-bold border transition-all ${
                            newQAnswer === tf
                              ? "bg-amber-600 text-white border-amber-600"
                              : "border-border bg-muted/10 text-muted-foreground hover:bg-muted/30"
                          }`}
                        >
                          {tf}
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                {/* Fill Blanks */}
                {newQType === "fill_blank" && (
                  <div className="space-y-2">
                    <div>
                      <label className="block text-xs font-semibold text-slate-700 mb-1">
                        Primary Answer(s) * (comma-separated if multiple blanks)
                      </label>
                      <input
                        type="text"
                        value={newQAnswer}
                        onChange={(e) => setNewQAnswer(e.target.value)}
                        placeholder="e.g. sunlight, oxygen"
                        className="w-full rounded-xl border border-border bg-muted/10 px-3 py-1.5 text-xs"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-semibold text-slate-700 mb-1">
                        Accepted Synonyms (Optional JSON e.g. [["light", "sunlight"], ["O2", "oxygen"]])
                      </label>
                      <input
                        type="text"
                        value={newQAcceptedAnswers}
                        onChange={(e) => setNewQAcceptedAnswers(e.target.value)}
                        placeholder='[["light", "sunlight"], ["O2", "oxygen"]]'
                        className="w-full rounded-xl border border-border bg-muted/10 px-3 py-1.5 text-xs font-mono"
                      />
                    </div>
                  </div>
                )}

                {/* Short & Long Answer */}
                {(newQType === "short_answer" || newQType === "long_answer") && (
                  <div className="space-y-2">
                    <div>
                      <label className="block text-xs font-semibold text-slate-700 mb-1">Model Answer / Key Points</label>
                      <textarea
                        value={newQModelAnswer}
                        onChange={(e) => setNewQModelAnswer(e.target.value)}
                        rows={2}
                        placeholder="Expected answer and key concepts..."
                        className="w-full rounded-xl border border-border bg-muted/10 p-2.5 text-xs"
                      />
                    </div>
                    <div className="grid grid-cols-2 gap-2">
                      <div>
                        <label className="block text-xs font-semibold text-slate-700 mb-1">Rubric Criteria</label>
                        <input
                          type="text"
                          value={newQRubric}
                          onChange={(e) => setNewQRubric(e.target.value)}
                          placeholder="e.g. 1 mark per point"
                          className="w-full rounded-xl border border-border bg-muted/10 px-3 py-1.5 text-xs"
                        />
                      </div>
                      <div>
                        <label className="block text-xs font-semibold text-slate-700 mb-1">Word Limit</label>
                        <input
                          type="number"
                          value={newQWordLimit}
                          onChange={(e) => setNewQWordLimit(e.target.value)}
                          placeholder={newQType === "short_answer" ? "50" : "250"}
                          className="w-full rounded-xl border border-border bg-muted/10 px-3 py-1.5 text-xs"
                        />
                      </div>
                    </div>
                  </div>
                )}

                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Topic / Syllabus Unit</label>
                  <input
                    type="text"
                    value={newQTopic}
                    onChange={(e) => setNewQTopic(e.target.value)}
                    placeholder="e.g. Unit 3 Cloud Architecture"
                    className="w-full rounded-xl border border-border bg-muted/10 px-3 py-1.5 text-xs"
                  />
                </div>
              </div>

              <div className="flex justify-end gap-2.5 pt-3 border-t border-border">
                <button
                  type="button"
                  onClick={() => setShowAddModal(false)}
                  className="rounded-xl border border-border px-4 py-2 text-xs font-semibold text-muted-foreground hover:bg-muted/50"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  disabled={addingQuestion}
                  onClick={handleAddQuestionSubmit}
                  className="rounded-xl bg-primary px-4 py-2 text-xs font-bold text-white hover:opacity-90 disabled:opacity-50"
                >
                  {addingQuestion ? "Adding..." : "Add Question"}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Publish Confirmation Modal */}
        {showPublishModal && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4 animate-in fade-in duration-150">
            <div className="bg-white rounded-2xl border border-border shadow-2xl w-full max-w-lg p-6 space-y-4 animate-in zoom-in-95 duration-150 max-h-[90vh] overflow-y-auto">
              <div className="flex items-center gap-3">
                <div className="p-2.5 rounded-xl bg-emerald-50 text-emerald-600 shrink-0">
                  <CheckCircle2 className="h-6 w-6" />
                </div>
                <div>
                  <h3 className="font-bold text-foreground text-base">Publish Exam Paper</h3>
                  <p className="text-xs text-muted-foreground">Confirm schedule & publish to students.</p>
                </div>
              </div>

              {hasShortfall && (
                <div className="rounded-xl border border-amber-300 bg-amber-50 p-3 text-xs text-amber-900 space-y-1">
                  <div className="flex items-center gap-1.5 font-bold text-amber-950">
                    <AlertTriangle className="h-4 w-4 text-amber-600 shrink-0" />
                    Publishing with Marks Shortfall
                  </div>
                  <p>
                    Target marks was <strong>{targetTotalMarks}</strong>, but this paper only has <strong>{computedTotalMarks} marks</strong> ({marksShortfall} marks short).
                  </p>
                  <p className="text-[11px] text-amber-800">
                    If you confirm, students will take the exam scored out of {computedTotalMarks} marks.
                  </p>
                </div>
              )}

              {/* Schedule Section */}
              <div className="rounded-xl border border-border bg-muted/20 p-4 space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Calendar className="h-4 w-4 text-primary" />
                    <span className="text-xs font-bold text-foreground uppercase tracking-wider">Exam Schedule</span>
                  </div>
                  {exam.starts_at && exam.ends_at && !showScheduleEditor && (
                    <button
                      type="button"
                      onClick={() => setShowScheduleEditor(true)}
                      className="text-xs text-primary font-medium hover:underline"
                    >
                      Change Schedule
                    </button>
                  )}
                </div>

                {exam.starts_at && exam.ends_at && !showScheduleEditor ? (
                  <div className="space-y-1 text-xs">
                    <div className="flex items-center justify-between text-muted-foreground">
                      <span>Available Window:</span>
                      <span className="font-medium text-foreground">
                        {formatScheduleSummary(exam.starts_at, exam.ends_at, exam.duration_minutes)}
                      </span>
                    </div>
                    <div className="flex items-center justify-between text-muted-foreground">
                      <span>Timezone:</span>
                      <span className="font-medium text-foreground">{scheduleTimezone}</span>
                    </div>
                  </div>
                ) : (
                  <div className="space-y-3">
                    {(!exam.starts_at || !exam.ends_at) && (
                      <div className="flex items-center gap-2 text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg p-2.5">
                        <AlertCircle className="h-4 w-4 shrink-0 text-amber-600" />
                        <span>Schedule is missing. Please set the exam window before publishing.</span>
                      </div>
                    )}

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                      <div>
                        <label className="block text-xs font-medium text-foreground mb-1">
                          Available From (Start Time) <span className="text-destructive">*</span>
                        </label>
                        <input
                          type="datetime-local"
                          value={scheduleStartsAt}
                          onChange={(e) => {
                            setScheduleStartsAt(e.target.value);
                            setFieldErrors((prev) => ({ ...prev, starts_at: undefined }));
                          }}
                          className={`w-full text-xs rounded-xl border ${
                            fieldErrors.starts_at ? "border-destructive bg-destructive/5" : "border-border"
                          } px-3 py-2 bg-background focus:outline-none focus:ring-2 focus:ring-primary`}
                        />
                        {fieldErrors.starts_at && (
                          <p role="alert" className="text-[11px] text-destructive mt-1">
                            {fieldErrors.starts_at}
                          </p>
                        )}
                      </div>

                      <div>
                        <label className="block text-xs font-medium text-foreground mb-1">
                          Deadline (End Time) <span className="text-destructive">*</span>
                        </label>
                        <input
                          type="datetime-local"
                          value={scheduleEndsAt}
                          onChange={(e) => {
                            setScheduleEndsAt(e.target.value);
                            setFieldErrors((prev) => ({ ...prev, ends_at: undefined }));
                          }}
                          className={`w-full text-xs rounded-xl border ${
                            fieldErrors.ends_at ? "border-destructive bg-destructive/5" : "border-border"
                          } px-3 py-2 bg-background focus:outline-none focus:ring-2 focus:ring-primary`}
                        />
                        {fieldErrors.ends_at && (
                          <p role="alert" className="text-[11px] text-destructive mt-1">
                            {fieldErrors.ends_at}
                          </p>
                        )}
                      </div>
                    </div>

                    <div className="flex items-center justify-between text-[11px] text-muted-foreground pt-1">
                      <span className="flex items-center gap-1">
                        <Clock className="h-3 w-3" />
                        Exam Duration: <strong className="text-foreground">{exam.duration_minutes} mins</strong>
                      </span>
                      <span>Timezone: <strong>{scheduleTimezone}</strong></span>
                    </div>

                    {/* Live validation feedback banner */}
                    {!scheduleValidation.valid && (
                      <div
                        role="alert"
                        aria-live="polite"
                        className="rounded-lg bg-amber-50 border border-amber-200/80 p-2.5 text-xs text-amber-800 flex items-start gap-2"
                      >
                        <AlertCircle className="h-4 w-4 text-amber-600 shrink-0 mt-0.5" />
                        <span>{scheduleValidation.message}</span>
                      </div>
                    )}
                  </div>
                )}
              </div>

              <div className="rounded-xl bg-muted/40 p-3 text-xs space-y-1.5">
                <p className="font-semibold text-foreground">{exam.title}</p>
                <p className="text-muted-foreground">
                  {exam.questions?.length} Questions · {computedTotalMarks} Marks · {exam.duration_minutes} Mins
                </p>
                <p className="text-emerald-700 font-medium pt-1">
                  Once published, questions become immutable to ensure academic integrity for all student attempts.
                </p>
              </div>

              <div className="flex justify-end gap-2.5 pt-2">
                <button
                  type="button"
                  disabled={publishing}
                  onClick={() => setShowPublishModal(false)}
                  className="rounded-xl border border-border px-4 py-2 text-xs font-semibold text-foreground hover:bg-muted/50"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  disabled={publishing || !scheduleValidation.valid}
                  onClick={handlePublishConfirmed}
                  className="inline-flex items-center gap-1.5 rounded-xl bg-gradient-to-r from-emerald-600 to-teal-600 px-5 py-2 text-xs font-bold text-white shadow-sm hover:opacity-95 disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
                >
                  {publishing ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Check className="h-3.5 w-3.5" />}
                  {publishing
                    ? "Publishing..."
                    : hasShortfall
                    ? `Confirm & Publish (${computedTotalMarks} Marks)`
                    : "Confirm & Publish"}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Adjust Marks Modal */}
        {showAdjustMarksModal && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4 animate-in fade-in duration-150">
            <div className="bg-white rounded-3xl border border-border shadow-2xl w-full max-w-lg p-6 space-y-5 animate-in zoom-in-95 duration-150 max-h-[90vh] overflow-y-auto">
              <div className="flex items-center justify-between border-b border-border pb-3">
                <div className="flex items-center gap-2">
                  <div className="p-2 rounded-xl bg-blue-50 text-blue-600">
                    <Scale className="h-5 w-5" />
                  </div>
                  <div>
                    <h3 className="font-bold text-base text-foreground">Adjust Paper Marks</h3>
                    <p className="text-xs text-muted-foreground">Resolve shortfall between target and generated questions</p>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => {
                    setShowAdjustMarksModal(false);
                    setScalePreview(null);
                  }}
                  className="rounded-lg p-1 text-muted-foreground hover:text-foreground"
                >
                  <X className="h-5 w-5" />
                </button>
              </div>

              <div className="rounded-xl bg-slate-50 border border-slate-200 p-3.5 text-xs space-y-1">
                <div className="flex justify-between font-semibold text-slate-700">
                  <span>Target Marks:</span>
                  <span className="font-bold text-slate-900">{targetTotalMarks} Marks</span>
                </div>
                <div className="flex justify-between font-semibold text-slate-700">
                  <span>Actual Questions Sum:</span>
                  <span className="font-bold text-slate-900">{computedTotalMarks} Marks</span>
                </div>
                <div className="flex justify-between font-semibold text-amber-700 pt-1 border-t border-slate-200">
                  <span>Shortfall:</span>
                  <span className="font-bold text-amber-800">{marksShortfall} Marks</span>
                </div>
              </div>

              {/* Option A: Set to Actual */}
              <div className="rounded-2xl border border-border p-4 space-y-2 hover:border-blue-300 transition-colors">
                <h4 className="text-xs font-bold text-foreground">Option A: Set Exam Total to Actual ({computedTotalMarks} Marks)</h4>
                <p className="text-xs text-muted-foreground">
                  Update the official exam total marks to match the generated questions. Shortfall will be cleared to 0.
                </p>
                <button
                  type="button"
                  disabled={adjustingMarks}
                  onClick={handleSetActualMarks}
                  className="rounded-xl bg-slate-900 px-4 py-2 text-xs font-bold text-white hover:bg-slate-800 disabled:opacity-50 transition-all"
                >
                  {adjustingMarks ? "Updating..." : `Set Total Marks to ${computedTotalMarks}`}
                </button>
              </div>

              {/* Option B: Scale Question Marks */}
              <div className="rounded-2xl border border-border p-4 space-y-3 hover:border-blue-300 transition-colors">
                <h4 className="text-xs font-bold text-foreground">Option B: Scale Questions to Reach Target ({targetTotalMarks} Marks)</h4>
                <p className="text-xs text-muted-foreground">
                  Proportionally increase marks across all existing questions so their sum equals {targetTotalMarks}.
                </p>

                {scalePreview ? (
                  <div className="space-y-3 pt-2 border-t border-border">
                    <div className="text-xs font-semibold text-slate-800 flex items-center justify-between">
                      <span>Scaling Preview ({scalePreview.question_previews?.length} questions):</span>
                      <span className="text-[11px] text-muted-foreground">Factor: {scalePreview.scaling_factor}x</span>
                    </div>
                    <div className="max-h-40 overflow-y-auto space-y-1.5 rounded-xl bg-slate-50 p-2.5 border border-slate-200 text-xs">
                      {scalePreview.question_previews?.map((qp: any, i: number) => (
                        <div key={qp.id} className="flex items-center justify-between text-[11px] text-slate-700">
                          <span className="truncate max-w-[240px]">Q{i + 1}: {qp.text}</span>
                          <span className="font-mono font-bold shrink-0 ml-2">
                            {qp.current_marks}m → <span className="text-emerald-700">{qp.scaled_marks}m</span>
                          </span>
                        </div>
                      ))}
                    </div>
                    <div className="flex items-center gap-2">
                      <button
                        type="button"
                        disabled={adjustingMarks}
                        onClick={handleApplyScale}
                        className="inline-flex items-center gap-1.5 rounded-xl bg-emerald-600 px-4 py-2 text-xs font-bold text-white hover:bg-emerald-700 disabled:opacity-50 transition-all"
                      >
                        {adjustingMarks ? "Applying..." : `Apply Scaling (${targetTotalMarks} Marks)`}
                      </button>
                      <button
                        type="button"
                        onClick={() => setScalePreview(null)}
                        className="rounded-xl border border-border px-3 py-2 text-xs font-semibold text-muted-foreground hover:bg-muted/50"
                      >
                        Reset Preview
                      </button>
                    </div>
                  </div>
                ) : (
                  <button
                    type="button"
                    disabled={adjustingMarks}
                    onClick={handlePreviewScale}
                    className="rounded-xl border border-border bg-white px-4 py-2 text-xs font-bold text-foreground hover:bg-muted/50 disabled:opacity-50 transition-all"
                  >
                    {adjustingMarks ? "Calculating..." : "Preview Scaled Marks"}
                  </button>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}

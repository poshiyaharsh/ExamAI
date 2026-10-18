import React, { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  AlertCircle,
  AlertTriangle,
  ArrowLeft,
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
  ShieldCheck,
  Shuffle,
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

function questionPayload(question: ExamQuestion) {
  const correctAnswer =
    question.question_type === "mcq" && /^\d+$/.test(String(question.correct_answer ?? ""))
      ? Number(question.correct_answer)
      : question.correct_answer;
  return {
    question_type: question.question_type,
    difficulty: question.difficulty,
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
  const [exam, setExam] = useState<FacultyExam | null>(null);
  const [loading, setLoading] = useState(true);

  // Question action states
  const [savingId, setSavingId] = useState<number | null>(null);
  const [swappingId, setSwappingId] = useState<number | null>(null);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [shuffling, setShuffling] = useState(false);
  const [confirmingReview, setConfirmingReview] = useState(false);

  // Filters
  const [filterType, setFilterType] = useState<string>("all");
  const [filterDifficulty, setFilterDifficulty] = useState<string>("all");

  // Publish Confirmation Modal
  const [showPublishModal, setShowPublishModal] = useState(false);
  const [publishing, setPublishing] = useState(false);

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
    if (!id) return;
    setPublishing(true);
    try {
      const published = await facultyExamApi.publishExam(Number(id));
      setExam(published);
      setShowPublishModal(false);
      toast.success("Exam published successfully! Students can now access it during the scheduled window.");
      navigate("/faculty/history");
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || "Publishing failed. Ensure total marks match question marks.");
    } finally {
      setPublishing(false);
    }
  };

  const isPublished = exam?.status === "published" || exam?.is_immutable;
  const isReviewed = Boolean(exam?.is_reviewed);

  // Computations & Validation Checks
  const computedTotalMarks = useMemo(
    () => (exam?.questions || []).reduce((sum, q) => sum + (Number(q.marks) || 0), 0),
    [exam?.questions]
  );

  const marksMatch = computedTotalMarks === (exam?.total_marks || 0);

  const filteredQuestions = useMemo(() => {
    if (!exam?.questions) return [];
    return exam.questions.filter((q) => {
      if (filterType !== "all" && q.question_type !== filterType) return false;
      if (filterDifficulty !== "all" && q.difficulty !== filterDifficulty) return false;
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
        warnings.push(`Question ${idx + 1} has duplicate or near-duplicate text.`);
      }
      seenTexts.add(normalized);

      // Check MCQ answer in options
      if (q.question_type === "mcq" && q.options && q.options.length > 0) {
        const correctStr = String(q.correct_answer ?? "").trim().toLowerCase();
        const cleanOpts = q.options.map((o) => o.trim().toLowerCase());
        const isLetter = ["a", "b", "c", "d"].includes(correctStr);
        const isNum = ["0", "1", "2", "3"].includes(correctStr);
        const isInList = cleanOpts.includes(correctStr);
        if (!isLetter && !isNum && !isInList && correctStr) {
          warnings.push(`Question ${idx + 1} ("${q.text.slice(0, 35)}..."): Correct answer does not match any listed option.`);
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
                    {isPublished && (
                      <span className="inline-flex items-center gap-1 rounded-full bg-blue-50 text-blue-700 border border-blue-200 px-2 py-0.5 text-xs font-medium">
                        <ShieldCheck className="h-3 w-3" /> Immutable
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-muted-foreground">
                    Department: <strong className="text-slate-800">{exam.department || "General"}</strong> · Created {new Date(exam.created_at).toLocaleDateString()}
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
                        if (!marksMatch) {
                          toast.error(`Question marks (${computedTotalMarks}) must equal exam total marks (${exam.total_marks}).`);
                          return;
                        }
                        setShowPublishModal(true);
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
                  <strong className={`text-base font-bold ${marksMatch ? "text-emerald-700" : "text-amber-700"}`}>
                    {computedTotalMarks} / {exam.total_marks} Marks
                  </strong>
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

            {/* Validation Warnings Box */}
            {validationWarnings.length > 0 && (
              <div className="rounded-2xl border border-amber-200 bg-amber-50/70 p-4 space-y-2">
                <div className="flex items-center gap-2 text-amber-900 font-bold text-xs">
                  <AlertTriangle className="h-4 w-4 text-amber-600" />
                  Validation Audit & Recommendations ({validationWarnings.length})
                </div>
                <ul className="list-disc list-inside space-y-1 text-xs text-amber-800">
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
                  </h3>
                  <p className="text-xs text-muted-foreground">
                    Review and calibrate questions, accepted answers, and grading rubrics before publishing.
                  </p>
                </div>

                {/* Filter Pills */}
                <div className="flex flex-wrap items-center gap-2">
                  <div className="flex items-center gap-1 bg-slate-100 p-1 rounded-xl text-xs font-semibold">
                    {[
                      { key: "all", label: "All Types" },
                      { key: "mcq", label: "MCQ" },
                      { key: "true_false", label: "True/False" },
                      { key: "fill_blank", label: "Fill Blank" },
                      { key: "short_answer", label: "Short" },
                      { key: "long_answer", label: "Long" },
                    ].map((t) => (
                      <button
                        key={t.key}
                        type="button"
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
                      { key: "all", label: "All Diff" },
                      { key: "easy", label: "Easy" },
                      { key: "medium", label: "Med" },
                      { key: "hard", label: "Hard" },
                    ].map((d) => (
                      <button
                        key={d.key}
                        type="button"
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
                <div className="rounded-2xl border border-dashed border-border bg-slate-50/50 p-8 text-center text-sm text-muted-foreground">
                  No questions match your current type/difficulty filter.
                </div>
              ) : (
                filteredQuestions.map((question, qIdx) => {
                  const qType = question.question_type;
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
                    question.difficulty === "easy"
                      ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                      : question.difficulty === "hard"
                      ? "bg-rose-50 text-rose-700 border-rose-200"
                      : "bg-amber-50 text-amber-700 border-amber-200";

                  return (
                    <section
                      key={question.id}
                      className="rounded-2xl border border-border bg-white p-5 sm:p-6 shadow-xs hover:shadow-md transition-all space-y-4"
                    >
                      <div className="flex items-center justify-between gap-4">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-slate-100 text-xs font-bold text-slate-700">
                            {qIdx + 1}
                          </span>
                          <span className={`rounded-full px-2.5 py-0.5 text-xs font-bold border ${typeBadgeColor} uppercase`}>
                            {qType.replace("_", " ")}
                          </span>
                          <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-semibold text-slate-600">
                            {question.marks} {Number(question.marks) === 1 ? "Mark" : "Marks"}
                          </span>
                          <span className={`rounded-full px-2 py-0.5 text-xs font-semibold border ${diffBadgeColor} uppercase`}>
                            {question.difficulty}
                          </span>
                          {question.topic && (
                            <span className="rounded-full bg-slate-50 border border-slate-200 px-2.5 py-0.5 text-xs text-slate-600">
                              Unit: {question.topic}
                            </span>
                          )}
                        </div>

                        {!isPublished && (
                          <div className="flex items-center gap-1.5">
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

                      {/* Short Answer & Long Answer & Subjective: Model Answer, Rubric, Word Limit */}
                      {(qType === "short_answer" || qType === "long_answer" || qType === "subjective") && (
                        <div className="space-y-3 pt-1">
                          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                            <div>
                              <label className="block text-[11px] font-semibold text-muted-foreground uppercase mb-1">
                                Model Answer / Expected Concepts
                              </label>
                              <textarea
                                value={question.model_answer || ""}
                                disabled={isPublished}
                                onChange={(e) => updateQuestion(question.id, { model_answer: e.target.value })}
                                rows={3}
                                className="w-full rounded-xl border border-border bg-muted/15 p-2.5 text-xs focus:outline-hidden focus:border-primary disabled:opacity-75"
                                placeholder="Key points and terms required in student response..."
                              />
                            </div>
                            <div>
                              <label className="block text-[11px] font-semibold text-muted-foreground uppercase mb-1">
                                Grading Rubric / Criteria
                              </label>
                              <textarea
                                value={question.rubric || ""}
                                disabled={isPublished}
                                onChange={(e) => updateQuestion(question.id, { rubric: e.target.value })}
                                rows={3}
                                className="w-full rounded-xl border border-border bg-muted/15 p-2.5 text-xs focus:outline-hidden focus:border-primary disabled:opacity-75"
                                placeholder="Marks allocation guidelines for faculty / AI suggestion..."
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
            <div className="bg-white rounded-2xl border border-border shadow-2xl w-full max-w-md p-6 space-y-4 animate-in zoom-in-95 duration-150">
              <div className="flex items-center gap-3">
                <div className="p-2.5 rounded-xl bg-emerald-50 text-emerald-600 shrink-0">
                  <CheckCircle2 className="h-6 w-6" />
                </div>
                <div>
                  <h3 className="font-bold text-foreground text-base">Publish Exam Paper</h3>
                  <p className="text-xs text-muted-foreground">Confirm publishing to students.</p>
                </div>
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
                  disabled={publishing}
                  onClick={handlePublishConfirmed}
                  className="inline-flex items-center gap-1.5 rounded-xl bg-gradient-to-r from-emerald-600 to-teal-600 px-5 py-2 text-xs font-bold text-white shadow-sm hover:opacity-95 disabled:opacity-50"
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

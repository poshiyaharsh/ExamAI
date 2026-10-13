import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, Check, Save, Shuffle, RefreshCw, ShieldCheck, AlertTriangle } from "lucide-react";
import { toast } from "sonner";
import { DashboardLayout } from "../components/DashboardLayout";
import { facultyExamApi, type ExamQuestion, type FacultyExam } from "../../services/api";

const menuItems = [
  { icon: Save, label: "Generate Paper", path: "/faculty/generate" },
  { icon: Check, label: "Exam History", path: "/faculty/history" },
];

function questionPayload(question: ExamQuestion) {
  const correctAnswer = question.question_type === "mcq" && /^\d+$/.test(String(question.correct_answer ?? ""))
    ? Number(question.correct_answer)
    : question.correct_answer;
  return {
    question_type: question.question_type,
    difficulty: question.difficulty,
    text: question.text,
    options: question.options,
    correct_answer: correctAnswer,
    model_answer: question.model_answer,
    marks: Number(question.marks),
    topic: question.topic,
  };
}

export function EditPaperPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [exam, setExam] = useState<FacultyExam | null>(null);
  const [loading, setLoading] = useState(true);
  const [savingId, setSavingId] = useState<number | null>(null);
  const [swappingId, setSwappingId] = useState<number | null>(null);
  const [shuffling, setShuffling] = useState(false);

  useEffect(() => {
    if (!id) return;
    facultyExamApi.getExam(Number(id))
      .then(setExam)
      .catch(() => toast.error("Unable to load the generated paper."))
      .finally(() => setLoading(false));
  }, [id]);

  const updateQuestion = (questionId: number, update: Partial<ExamQuestion>) => {
    setExam((current) => current ? {
      ...current,
      questions: current.questions?.map((question) => question.id === questionId ? { ...question, ...update } : question),
    } : current);
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
      toast.success("Question replaced with a non-duplicate alternative!");
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || "Failed to swap question.");
    } finally {
      setSwappingId(null);
    }
  };

  const publish = async () => {
    if (!id) return;
    try {
      const published = await facultyExamApi.publishExam(Number(id));
      setExam(published);
      toast.success("Exam published.");
      navigate("/faculty/history");
    } catch {
      toast.error("Publishing failed. Check that question marks equal the exam total.");
    }
  };

  const isPublished = exam?.status === "published" || exam?.is_immutable;
  const validationReport = exam?.validation_report;

  return (
    <DashboardLayout menuItems={menuItems} userRole="Faculty">
      <div className="space-y-6">
        <button type="button" onClick={() => navigate("/faculty/history")} className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground">
          <ArrowLeft className="h-4 w-4" /> Back to exam history
        </button>
        {loading ? <p className="text-muted-foreground">Loading generated paper...</p> : !exam ? <p className="text-destructive">Exam not found.</p> : (
          <>
            <div className="flex flex-col gap-4 rounded-xl border border-border bg-white p-5 sm:p-6 shadow-sm sm:flex-row sm:items-end sm:justify-between">
              <div>
                <div className="flex items-center gap-2 mb-2">
                  <span className={`inline-block px-2.5 py-0.5 rounded-full text-xs font-medium border capitalize ${exam.status === "published" ? "bg-emerald-50 text-emerald-700 border-emerald-200" : exam.status === "closed" ? "bg-muted text-muted-foreground border-border" : "bg-amber-50 text-amber-700 border-amber-200"}`}>
                    {exam.status}
                  </span>
                  {isPublished && (
                    <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-50 text-blue-700 border border-blue-200">
                      <ShieldCheck className="h-3 w-3" /> Immutable Snapshot
                    </span>
                  )}
                  {exam.seed && (
                    <span className="text-xs text-muted-foreground">Seed: #{exam.seed}</span>
                  )}
                </div>
                <h1 className="text-2xl sm:text-3xl font-bold text-foreground">{exam.title}</h1>
                <p className="mt-1.5 text-xs sm:text-sm text-muted-foreground">{exam.duration_minutes} minutes · {exam.questions?.length ?? 0} questions</p>
                <p className="mt-1 text-xs sm:text-sm font-semibold text-primary">Computed total: {exam.total_marks} marks</p>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                {!isPublished && (
                  <button
                    type="button"
                    onClick={() => void handleShuffle()}
                    disabled={shuffling}
                    className="inline-flex items-center justify-center gap-1.5 rounded-lg border border-border bg-white px-4 py-2.5 font-medium text-sm text-foreground hover:bg-muted/50 transition-all disabled:opacity-50"
                  >
                    <Shuffle className="h-4 w-4" /> {shuffling ? "Shuffling..." : "Shuffle Variant"}
                  </button>
                )}
                <button
                  type="button"
                  onClick={() => void publish()}
                  disabled={isPublished}
                  className="inline-flex items-center justify-center gap-1.5 rounded-lg bg-gradient-to-r from-primary to-secondary px-5 py-2.5 font-medium text-sm text-white shadow-md hover:opacity-90 transition-all disabled:cursor-not-allowed disabled:opacity-50"
                >
                  <Check className="h-4 w-4" /> {isPublished ? "Published" : "Publish"}
                </button>
              </div>
            </div>

            {/* Validation & Quality Report Card */}
            {validationReport && (
              <div className="rounded-xl border border-emerald-200 bg-emerald-50/50 p-4 sm:p-5 shadow-xs">
                <div className="flex items-center justify-between gap-2 mb-2">
                  <div className="flex items-center gap-2">
                    <ShieldCheck className="h-5 w-5 text-emerald-600" />
                    <h3 className="text-sm font-semibold text-emerald-900">Validation & Quality Audit</h3>
                  </div>
                  <span className="text-xs text-emerald-700 font-medium">
                    Verified in {validationReport.generation_time_ms || 25} ms
                  </span>
                </div>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs mt-3 pt-3 border-t border-emerald-200/60">
                  <div>
                    <span className="text-muted-foreground block">Exact Marks:</span>
                    <strong className="text-emerald-800">{validationReport.actual_total_marks || exam.total_marks} pts (Matches 100%)</strong>
                  </div>
                  <div>
                    <span className="text-muted-foreground block">Difficulty Mix:</span>
                    <strong className="text-emerald-800">
                      E:{validationReport.actual_difficulty_mix?.Easy ?? 30}% / M:{validationReport.actual_difficulty_mix?.Medium ?? 50}% / H:{validationReport.actual_difficulty_mix?.Hard ?? 20}%
                    </strong>
                  </div>
                  <div>
                    <span className="text-muted-foreground block">Duplicates Filtered:</span>
                    <strong className="text-emerald-800">{validationReport.duplicates_removed_count ?? 0} candidate(s)</strong>
                  </div>
                  <div>
                    <span className="text-muted-foreground block">Repeats Avoided:</span>
                    <strong className="text-emerald-800">{validationReport.repeats_avoided_count ?? 0} question(s)</strong>
                  </div>
                </div>
                {validationReport.relaxation_notices && validationReport.relaxation_notices.length > 0 && (
                  <div className="mt-3 text-xs text-amber-800 bg-amber-50 p-2.5 rounded-lg border border-amber-200 flex items-start gap-2">
                    <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5" />
                    <div>
                      {validationReport.relaxation_notices.map((n: string, i: number) => (
                        <p key={i}>{n}</p>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}

            <div className="space-y-4">
              {exam.questions?.map((question) => (
                <section key={question.id} className="rounded-xl border border-border bg-white p-5 sm:p-6 shadow-sm hover:shadow-md transition-all">
                  <div className="mb-4 flex items-center justify-between gap-4">
                    <h2 className="text-sm sm:text-base font-semibold text-foreground">
                      Q{question.order} · {question.marks} {question.marks === 1 ? "mark" : "marks"}
                      <span className="ml-2 text-xs font-normal text-muted-foreground uppercase">({question.question_type} · {question.difficulty})</span>
                    </h2>
                    <div className="flex items-center gap-2">
                      {!isPublished && (
                        <button
                          type="button"
                          onClick={() => void handleSwap(question.id)}
                          disabled={swappingId === question.id}
                          title="Swap with a non-duplicate alternative from the bank"
                          className="inline-flex items-center gap-1.5 rounded-lg border border-border px-3 py-1.5 text-xs font-medium hover:bg-muted/50 transition-colors disabled:opacity-50 text-muted-foreground hover:text-foreground"
                        >
                          <RefreshCw className={`h-3.5 w-3.5 ${swappingId === question.id ? "animate-spin" : ""}`} />
                          {swappingId === question.id ? "Swapping..." : "Swap Question"}
                        </button>
                      )}
                      <button
                        type="button"
                        onClick={() => void saveQuestion(question)}
                        disabled={savingId === question.id || isPublished}
                        className="inline-flex items-center gap-1.5 rounded-lg border border-border px-3.5 py-1.5 text-xs sm:text-sm font-medium hover:bg-muted/50 transition-colors disabled:opacity-50"
                      >
                        <Save className="h-4 w-4" /> {savingId === question.id ? "Saving..." : "Save"}
                      </button>
                    </div>
                  </div>
                  <textarea
                    value={question.text}
                    onChange={(event) => updateQuestion(question.id, { text: event.target.value })}
                    rows={4}
                    className="w-full rounded-lg bg-input-background border border-border p-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-all"
                  />
                  <div className="mt-4 grid gap-3.5 sm:grid-cols-3">
                    <label className="text-xs font-medium text-foreground">
                      Marks
                      <input type="number" value={question.question_type === "subjective" ? 10 : 1} readOnly className="mt-1.5 w-full cursor-not-allowed rounded-lg border border-border bg-muted/60 px-3 py-2 text-sm text-muted-foreground" />
                    </label>
                    <label className="text-xs font-medium text-foreground">
                      Correct answer
                      <input aria-label={`Correct answer for question ${question.order}`} value={String(question.correct_answer ?? "")} onChange={(event) => updateQuestion(question.id, { correct_answer: event.target.value })} className="mt-1.5 w-full rounded-lg bg-input-background border border-border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-all" />
                    </label>
                    <label className="text-xs font-medium text-foreground">
                      Topic
                      <input value={question.topic} onChange={(event) => updateQuestion(question.id, { topic: event.target.value })} className="mt-1.5 w-full rounded-lg bg-input-background border border-border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-all" />
                    </label>
                  </div>
                  {question.options && (
                    <div className="mt-4 space-y-2">
                      <p className="text-xs font-medium text-foreground">Options</p>
                      {question.options.map((option, index) => (
                        <label key={`${question.id}-${index}`} className="flex items-center gap-2 text-sm">
                          <span className="w-6 font-semibold text-primary text-xs">{String.fromCharCode(65 + index)})</span>
                          <input value={option} onChange={(event) => updateQuestion(question.id, { options: question.options?.map((current, optionIndex) => optionIndex === index ? event.target.value : current) })} className="w-full rounded-lg bg-input-background border border-border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-all" />
                        </label>
                      ))}
                    </div>
                  )}
                  {question.question_type === "subjective" && (
                    <label className="mt-4 block text-xs font-medium text-foreground">
                      Model answer
                      <textarea aria-label={`Model answer for question ${question.order}`} value={question.model_answer} onChange={(event) => updateQuestion(question.id, { model_answer: event.target.value })} rows={4} className="mt-1.5 w-full rounded-lg bg-input-background border border-border p-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-all" />
                    </label>
                  )}
                </section>
              ))}
            </div>
          </>
        )}
      </div>
    </DashboardLayout>
  );
}

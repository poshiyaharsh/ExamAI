import { useEffect, useState } from "react";
import {
  AlertCircle,
  ArrowLeft,
  Bot,
  CheckCircle,
  Edit3,
  Eye,
  FileText,
  History,
  LayoutDashboard,
  Loader2,
  RefreshCw,
  Save,
  Settings,
  X,
  XCircle,
} from "lucide-react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { DashboardLayout } from "../components/DashboardLayout";
import { facultyExamApi, type FacultyExam } from "../../services/api";

const menuItems = [
  { icon: LayoutDashboard, label: "Dashboard", path: "/faculty" },
  { icon: FileText, label: "Generate Paper", path: "/faculty/generate" },
  { icon: History, label: "Exam History", path: "/faculty/history" },
  { icon: Settings, label: "Settings", path: "/faculty/settings" },
];

export function FacultyExamHistory() {
  const navigate = useNavigate();
  const [exams, setExams] = useState<FacultyExam[]>([]);
  const [loading, setLoading] = useState(true);

  // Attempts Modal State
  const [selectedExam, setSelectedExam] = useState<FacultyExam | null>(null);
  const [attempts, setAttempts] = useState<any[]>([]);
  const [loadingAttempts, setLoadingAttempts] = useState(false);

  // Attempt Detail State
  const [selectedAttemptId, setSelectedAttemptId] = useState<number | null>(null);
  const [attemptDetail, setAttemptDetail] = useState<any | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);

  // Loading States for Actions
  const [reevaluatingAttempt, setReevaluatingAttempt] = useState(false);
  const [reevaluatingAnswerId, setReevaluatingAnswerId] = useState<number | null>(null);

  // Manual Edit State
  const [editingAnswerId, setEditingAnswerId] = useState<number | null>(null);
  const [manualScore, setManualScore] = useState<string>("");
  const [manualFeedback, setManualFeedback] = useState<string>("");
  const [savingGrade, setSavingGrade] = useState(false);

  const loadExams = async () => {
    try {
      const response = await facultyExamApi.getExams();
      const loaded = Array.isArray(response) ? response : response.results ?? [];
      setExams(loaded);
    } catch {
      toast.error("Unable to load exams.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadExams();
  }, []);

  const publish = async (examId: number) => {
    try {
      const published = await facultyExamApi.publishExam(examId);
      setExams((current) => current.map((exam) => (exam.id === examId ? published : exam)));
      toast.success("Exam published.");
    } catch {
      toast.error("Publishing failed. Check the question marks first.");
    }
  };

  const handleOpenAttempts = async (exam: FacultyExam) => {
    setSelectedExam(exam);
    setSelectedAttemptId(null);
    setAttemptDetail(null);
    setLoadingAttempts(true);
    try {
      const res = await facultyExamApi.getExamAttempts(exam.id);
      setAttempts(res.attempts || []);
    } catch {
      toast.error("Failed to load student attempts.");
    } finally {
      setLoadingAttempts(false);
    }
  };

  const handleOpenAttemptDetail = async (attemptId: number) => {
    setSelectedAttemptId(attemptId);
    setLoadingDetail(true);
    try {
      const detail = await facultyExamApi.getAttemptDetail(attemptId);
      setAttemptDetail(detail);
    } catch {
      toast.error("Failed to load attempt details.");
    } finally {
      setLoadingDetail(false);
    }
  };

  const handleReevaluateAttempt = async (attemptId: number) => {
    setReevaluatingAttempt(true);
    try {
      await facultyExamApi.reevaluateAttempt(attemptId, true);
      toast.success("Attempt subjective evaluation completed!");
      await handleOpenAttemptDetail(attemptId);
      if (selectedExam) {
        const res = await facultyExamApi.getExamAttempts(selectedExam.id);
        setAttempts(res.attempts || []);
      }
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || "Re-evaluation failed.");
    } finally {
      setReevaluatingAttempt(false);
    }
  };

  const handleReevaluateAnswer = async (answerId: number) => {
    setReevaluatingAnswerId(answerId);
    try {
      const res = await facultyExamApi.reevaluateAnswer(answerId, true);
      toast.success(`Answer re-evaluated: awarded ${res.score_awarded} marks.`);
      if (selectedAttemptId) {
        await handleOpenAttemptDetail(selectedAttemptId);
      }
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || "Answer re-evaluation failed.");
    } finally {
      setReevaluatingAnswerId(null);
    }
  };

  const startManualGrade = (answer: any) => {
    setEditingAnswerId(answer.id);
    setManualScore(answer.score_awarded !== null ? String(answer.score_awarded) : "0");
    setManualFeedback(answer.ai_feedback || "");
  };

  const saveManualGrade = async (answerId: number) => {
    const num = parseFloat(manualScore);
    if (isNaN(num)) {
      toast.error("Please enter a valid numeric score.");
      return;
    }
    setSavingGrade(true);
    try {
      await facultyExamApi.manualGradeAnswer(answerId, num, manualFeedback);
      toast.success("Manual grade saved! Marked as reviewed.");
      setEditingAnswerId(null);
      if (selectedAttemptId) {
        await handleOpenAttemptDetail(selectedAttemptId);
      }
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || "Failed to save manual grade.");
    } finally {
      setSavingGrade(false);
    }
  };

  return (
    <DashboardLayout menuItems={menuItems} userRole="Faculty">
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold text-foreground mb-1">Exam History</h1>
          <p className="text-xs sm:text-sm text-muted-foreground">Review generated papers and manage publication.</p>
        </div>
        {loading ? (
          <p className="text-sm text-muted-foreground">Loading exams...</p>
        ) : exams.length === 0 ? (
          <div className="rounded-xl border border-border bg-white p-8 text-center text-sm text-muted-foreground shadow-sm">
            No exams generated yet.
          </div>
        ) : (
          <div className="space-y-4">
            {exams.map((exam) => (
              <div key={exam.id} className="rounded-xl border border-border bg-white p-5 sm:p-6 shadow-sm hover:shadow-md transition-all">
                <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
                  <div>
                    <div className="flex items-center gap-3">
                      <h2 className="text-base sm:text-lg font-semibold text-foreground">{exam.title}</h2>
                      <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium border ${exam.status === "published" ? "bg-emerald-50 text-emerald-700 border-emerald-200" : exam.status === "closed" ? "bg-muted text-muted-foreground border-border" : "bg-amber-50 text-amber-700 border-amber-200"}`}>
                        {exam.status}
                      </span>
                    </div>
                    <p className="mt-1.5 text-xs sm:text-sm text-muted-foreground">
                      {exam.question_count ?? exam.questions?.length ?? 0} questions · {exam.total_marks} marks · {exam.duration_minutes} minutes
                    </p>
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <button
                      type="button"
                      onClick={() => navigate(`/faculty/exams/${exam.id}/edit`)}
                      className="inline-flex items-center gap-1.5 rounded-lg border border-border px-3.5 py-2 text-xs sm:text-sm font-medium text-foreground hover:bg-muted/50 transition-colors"
                    >
                      <Edit3 className="h-4 w-4" /> Edit
                    </button>
                    {exam.status !== "published" && (
                      <button
                        type="button"
                        onClick={() => void publish(exam.id)}
                        className="inline-flex items-center gap-1.5 rounded-lg bg-gradient-to-r from-primary to-secondary px-3.5 py-2 text-xs sm:text-sm font-medium text-white shadow-sm hover:opacity-90 transition-all"
                      >
                        Publish
                      </button>
                    )}
                    <button
                      type="button"
                      onClick={() => void handleOpenAttempts(exam)}
                      className="inline-flex items-center gap-1.5 rounded-lg border border-border px-3.5 py-2 text-xs sm:text-sm font-medium text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors"
                    >
                      <Eye className="h-4 w-4" /> View attempts ({exam.attempts_count ?? 0})
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Modal: Student Attempts List & Answer Review */}
        {selectedExam && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4 overflow-y-auto">
            <div className="bg-white rounded-2xl border border-border shadow-2xl w-full max-w-4xl max-h-[90vh] flex flex-col overflow-hidden animate-in fade-in zoom-in-95 duration-200">
              {/* Header */}
              <div className="px-6 py-4 border-b border-border flex items-center justify-between bg-muted/20">
                <div className="flex items-center gap-3">
                  {selectedAttemptId && (
                    <button
                      type="button"
                      onClick={() => setSelectedAttemptId(null)}
                      className="rounded-lg p-1.5 text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
                      title="Back to attempts list"
                    >
                      <ArrowLeft className="h-5 w-5" />
                    </button>
                  )}
                  <div>
                    <h3 className="font-semibold text-lg text-foreground">
                      {selectedAttemptId ? `Review Attempt #${selectedAttemptId}` : `Student Attempts: ${selectedExam.title}`}
                    </h3>
                    <p className="text-xs text-muted-foreground">
                      {selectedAttemptId
                        ? `Student: ${attemptDetail?.student_name ?? "Loading..."} · Total Score: ${attemptDetail?.total_score ?? 0}/${selectedExam.total_marks}`
                        : `Total ${attempts.length} attempt(s) recorded`}
                    </p>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => {
                    setSelectedExam(null);
                    setSelectedAttemptId(null);
                    setAttemptDetail(null);
                  }}
                  className="rounded-lg p-1.5 text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
                >
                  <X className="h-5 w-5" />
                </button>
              </div>

              {/* Body */}
              <div className="p-6 overflow-y-auto flex-1 space-y-4">
                {selectedAttemptId === null ? (
                  /* Attempts List View */
                  loadingAttempts ? (
                    <div className="py-12 flex flex-col items-center justify-center gap-3 text-muted-foreground">
                      <Loader2 className="h-6 w-6 animate-spin text-primary" />
                      <p className="text-sm">Loading student attempts...</p>
                    </div>
                  ) : attempts.length === 0 ? (
                    <div className="py-12 text-center text-sm text-muted-foreground">
                      No students have attempted this exam yet.
                    </div>
                  ) : (
                    <div className="divide-y divide-border rounded-xl border border-border overflow-hidden">
                      {attempts.map((att) => (
                        <div key={att.id} className="p-4 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 hover:bg-muted/30 transition-colors">
                          <div>
                            <div className="flex items-center gap-2">
                              <span className="font-semibold text-sm text-foreground">{att.student_name}</span>
                              <span className="text-xs text-muted-foreground">({att.student_email})</span>
                              <span className={`px-2 py-0.5 rounded-full text-[11px] font-medium border ${att.status === "evaluated" ? "bg-emerald-50 text-emerald-700 border-emerald-200" : att.status === "submitted" ? "bg-amber-50 text-amber-700 border-amber-200" : "bg-muted text-muted-foreground border-border"}`}>
                                {att.status}
                              </span>
                            </div>
                            <p className="text-xs text-muted-foreground mt-1">
                              Submitted: {att.submitted_at ? new Date(att.submitted_at).toLocaleString() : "In progress"}
                            </p>
                          </div>
                          <div className="flex items-center gap-3 w-full sm:w-auto justify-between sm:justify-end">
                            <span className="text-sm font-semibold text-primary">
                              {att.total_score} / {selectedExam.total_marks}
                            </span>
                            <button
                              type="button"
                              onClick={() => void handleOpenAttemptDetail(att.id)}
                              className="inline-flex items-center gap-1.5 rounded-lg bg-primary/10 text-primary hover:bg-primary/20 px-3 py-1.5 text-xs font-medium transition-colors"
                            >
                              Review Answers <Eye className="h-3.5 w-3.5" />
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  )
                ) : (
                  /* Single Attempt Drill-down Review */
                  loadingDetail ? (
                    <div className="py-12 flex flex-col items-center justify-center gap-3 text-muted-foreground">
                      <Loader2 className="h-6 w-6 animate-spin text-primary" />
                      <p className="text-sm">Loading attempt questions and evaluation breakdown...</p>
                    </div>
                  ) : !attemptDetail ? (
                    <div className="py-12 text-center text-sm text-rose-600">
                      Failed to load attempt details.
                    </div>
                  ) : (
                    <div className="space-y-4">
                      {/* Top Action Bar */}
                      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 p-4 rounded-xl bg-muted/40 border border-border">
                        <div>
                          <div className="text-sm font-medium text-foreground">
                            Status: <span className="font-semibold uppercase tracking-wider">{attemptDetail.status}</span>
                          </div>
                          <div className="text-xs text-muted-foreground mt-0.5">
                            Total Score: <strong className="text-primary">{attemptDetail.total_score}</strong> / {attemptDetail.exam_total_marks} marks
                          </div>
                        </div>
                        <button
                          type="button"
                          disabled={reevaluatingAttempt}
                          onClick={() => void handleReevaluateAttempt(attemptDetail.attempt_id)}
                          className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-3.5 py-2 text-xs font-medium text-white shadow-sm hover:opacity-95 disabled:opacity-50 transition-all"
                        >
                          {reevaluatingAttempt ? (
                            <>
                              <Loader2 className="h-4 w-4 animate-spin" /> Re-evaluating All...
                            </>
                          ) : (
                            <>
                              <RefreshCw className="h-4 w-4" /> Re-evaluate Attempt
                            </>
                          )}
                        </button>
                      </div>

                      {/* Answers Breakdown */}
                      <div className="space-y-3">
                        {attemptDetail.answers?.map((ans: any, idx: number) => (
                          <div key={ans.id} className="rounded-xl border border-border bg-white p-4 shadow-sm space-y-3">
                            <div className="flex items-start justify-between gap-3">
                              <div>
                                <span className="text-xs font-semibold uppercase text-muted-foreground tracking-wider">
                                  Q{idx + 1} · {ans.question_type} ({ans.marks} Marks)
                                </span>
                                <p className="text-sm font-medium text-foreground mt-0.5">{ans.question_text}</p>
                              </div>
                              <div className="flex items-center gap-1 shrink-0">
                                {ans.is_correct === true && <CheckCircle className="h-5 w-5 text-emerald-600" />}
                                {ans.is_correct === false && <XCircle className="h-5 w-5 text-rose-600" />}
                              </div>
                            </div>

                            {/* Student Answer */}
                            <div className="rounded-lg bg-muted/30 p-3 text-xs sm:text-sm">
                              <span className="font-medium text-muted-foreground block mb-1">Student Answer:</span>
                              <p className="text-foreground whitespace-pre-wrap">{ans.student_answer || "(No answer was submitted)"}</p>
                            </div>

                            {/* Evaluation Info for Subjective */}
                            {ans.question_type === "subjective" && (
                              <div className="space-y-2">
                                <div className="flex flex-wrap items-center justify-between gap-2 pt-2 border-t border-border">
                                  <div className="flex items-center gap-2">
                                    <span className="text-xs font-semibold text-muted-foreground">Score:</span>
                                    <strong className="text-sm font-bold text-primary">{ans.score_awarded ?? 0} / {ans.marks}</strong>
                                    <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase border ${ans.evaluation_status === "reviewed" ? "bg-purple-50 text-purple-700 border-purple-200" : ans.evaluation_status === "evaluated_ai" ? "bg-emerald-50 text-emerald-700 border-emerald-200" : ans.evaluation_status === "evaluated_rules" ? "bg-sky-50 text-sky-700 border-sky-200" : "bg-amber-50 text-amber-700 border-amber-200"}`}>
                                      {ans.evaluation_status}
                                    </span>
                                    {ans.evaluation_model && (
                                      <span className="text-[11px] text-muted-foreground font-mono">
                                        ({ans.evaluation_provider}: {ans.evaluation_model})
                                      </span>
                                    )}
                                  </div>

                                  <div className="flex items-center gap-2">
                                    <button
                                      type="button"
                                      disabled={reevaluatingAnswerId === ans.id}
                                      onClick={() => void handleReevaluateAnswer(ans.id)}
                                      className="inline-flex items-center gap-1 rounded-md border border-border px-2.5 py-1 text-xs font-medium text-foreground hover:bg-muted/50 disabled:opacity-50 transition-colors"
                                      title="Re-run AI / fallback evaluation"
                                    >
                                      {reevaluatingAnswerId === ans.id ? (
                                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                                      ) : (
                                        <Bot className="h-3.5 w-3.5" />
                                      )}
                                      Re-evaluate AI
                                    </button>
                                    <button
                                      type="button"
                                      onClick={() => startManualGrade(ans)}
                                      className="inline-flex items-center gap-1 rounded-md border border-border px-2.5 py-1 text-xs font-medium text-foreground hover:bg-muted/50 transition-colors"
                                    >
                                      <Edit3 className="h-3.5 w-3.5" /> Manual Grade
                                    </button>
                                  </div>
                                </div>

                                {ans.ai_feedback && (
                                  <div className="rounded-lg bg-primary/5 border border-primary/10 p-2.5 text-xs text-muted-foreground">
                                    <strong className="text-foreground font-medium">Feedback:</strong> {ans.ai_feedback}
                                  </div>
                                )}

                                {/* Technical error warning for teacher view */}
                                {ans.technical_error && (
                                  <div className="rounded-lg bg-rose-50 border border-rose-200 p-2.5 text-xs text-rose-700 flex items-start gap-2">
                                    <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
                                    <div>
                                      <strong>Teacher Technical Log:</strong> {ans.technical_error}
                                    </div>
                                  </div>
                                )}

                                {/* Inline Manual Grade Editor */}
                                {editingAnswerId === ans.id && (
                                  <div className="mt-2 p-3 rounded-lg border border-primary/30 bg-primary/5 space-y-2 animate-in fade-in">
                                    <div className="flex items-center justify-between">
                                      <span className="text-xs font-semibold text-primary">Override / Edit Grade</span>
                                      <button
                                        type="button"
                                        onClick={() => setEditingAnswerId(null)}
                                        className="text-muted-foreground hover:text-foreground text-xs"
                                      >
                                        Cancel
                                      </button>
                                    </div>
                                    <div className="flex items-center gap-3">
                                      <label className="text-xs text-muted-foreground">Score (0-{ans.marks}):</label>
                                      <input
                                        type="number"
                                        step="0.5"
                                        min="0"
                                        max={ans.marks}
                                        value={manualScore}
                                        onChange={(e) => setManualScore(e.target.value)}
                                        className="w-24 rounded border border-border px-2 py-1 text-xs text-foreground bg-white"
                                      />
                                    </div>
                                    <div>
                                      <label className="text-xs text-muted-foreground block mb-1">Teacher Feedback:</label>
                                      <textarea
                                        rows={2}
                                        value={manualFeedback}
                                        onChange={(e) => setManualFeedback(e.target.value)}
                                        className="w-full rounded border border-border p-2 text-xs text-foreground bg-white"
                                        placeholder="Enter constructive feedback for the student..."
                                      />
                                    </div>
                                    <div className="flex justify-end gap-2">
                                      <button
                                        type="button"
                                        disabled={savingGrade}
                                        onClick={() => void saveManualGrade(ans.id)}
                                        className="inline-flex items-center gap-1.5 rounded bg-primary px-3 py-1 text-xs font-medium text-white shadow-sm hover:opacity-90 disabled:opacity-50"
                                      >
                                        {savingGrade ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Save className="h-3.5 w-3.5" />}
                                        Save & Mark Reviewed
                                      </button>
                                    </div>
                                  </div>
                                )}
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  )
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}


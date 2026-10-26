import { useEffect, useState } from "react";
import { CheckCircle, Clock, XCircle } from "lucide-react";
import { useNavigate, useParams } from "react-router-dom";
import { studentExamApi, type StudentAttempt } from "../../services/api";

export function ResultsPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [attempt, setAttempt] = useState<StudentAttempt | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!id) return;
    let active = true;
    const load = async () => {
      try {
        const next = await studentExamApi.getAttempt(Number(id));
        if (active) setAttempt(next);
      } catch {
        if (active) setError("Unable to load this result.");
      }
    };
    void load();
    const poller = window.setInterval(() => {
      if (attempt?.status !== "evaluated") void load();
    }, 3000);
    return () => {
      active = false;
      window.clearInterval(poller);
    };
  }, [id, attempt?.status]);

  if (error) return <div className="flex min-h-screen items-center justify-center text-destructive">{error}</div>;
  if (!attempt) return <div className="flex min-h-screen items-center justify-center text-muted-foreground">Loading result...</div>;
  
  const isProvisional = attempt.is_provisional ?? (attempt.review_status !== "finalized");
  const pendingSubjectives = attempt.status === "submitted" || attempt.status === "in_progress";

  return (
    <main className="min-h-screen bg-muted/30 p-4 sm:p-6">
      <div className="mx-auto max-w-4xl space-y-6">
        <button
          type="button"
          onClick={() => navigate("/student/exams")}
          className="inline-flex items-center gap-1.5 text-xs sm:text-sm font-medium text-muted-foreground hover:text-foreground transition-colors"
        >
          ← Back to exams
        </button>
        <section className="rounded-xl border border-border bg-white p-5 sm:p-6 shadow-sm space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <span className={`inline-block px-3 py-1 rounded-full text-xs font-bold border uppercase tracking-wider ${
              isProvisional
                ? "bg-amber-50 text-amber-700 border-amber-300"
                : "bg-emerald-50 text-emerald-700 border-emerald-300"
            }`}>
              {isProvisional ? "Provisional Result" : "Evaluation Finalized"}
            </span>
            {attempt.finalized_at && !isProvisional && (
              <span className="text-xs text-muted-foreground">
                Reviewed on {new Date(attempt.finalized_at).toLocaleDateString()}
              </span>
            )}
          </div>
          <h1 className="text-2xl sm:text-3xl font-bold text-foreground">{attempt.exam_title}</h1>
          <p className="mt-2 text-3xl sm:text-4xl font-bold text-primary">
            {attempt.total_score} <span className="text-xl font-normal text-muted-foreground">/ {attempt.exam_total_marks} marks</span>
          </p>
          {isProvisional && (
            <div className="mt-3 p-3 rounded-lg bg-amber-50/70 border border-amber-200 text-xs sm:text-sm text-amber-900 flex items-start gap-2">
              <Clock className="h-4 w-4 text-amber-600 mt-0.5 shrink-0" />
              <div>
                <strong>Provisional Result:</strong> Evaluated automatically by system and AI. Your faculty may review and adjust marks before final publication.
              </div>
            </div>
          )}
          {pendingSubjectives && (
            <p className="mt-2 inline-flex items-center gap-2 text-xs sm:text-sm text-indigo-600">
              <Clock className="h-4 w-4" /> AI evaluation for subjective answers is running in the background.
            </p>
          )}
        </section>
        <div className="space-y-3.5">
          {attempt.answers.map((answer, index) => (
            <section key={answer.question} className={`rounded-xl border bg-white p-5 shadow-sm hover:shadow-md transition-all ${
              answer.is_overridden ? "border-purple-200" : "border-border"
            }`}>
              <div className="flex items-start justify-between gap-4">
                <div className="space-y-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <h2 className="font-semibold text-sm sm:text-base text-foreground">Question {index + 1}</h2>
                    {answer.is_overridden && (
                      <span className="px-2 py-0.5 rounded-full text-[11px] font-bold bg-purple-50 text-purple-700 border border-purple-200">
                        Marks updated by faculty
                      </span>
                    )}
                  </div>
                  <p className="text-xs sm:text-sm text-muted-foreground">{answer.question_text}</p>
                </div>
                {answer.is_correct === true ? (
                  <CheckCircle className="h-5 w-5 text-emerald-600 shrink-0" />
                ) : answer.is_correct === false ? (
                  <XCircle className="h-5 w-5 text-rose-600 shrink-0" />
                ) : null}
              </div>
              <div className="mt-4 pt-3 border-t border-border/60 space-y-1.5 text-xs sm:text-sm">
                <p><span className="text-muted-foreground font-medium">Answer:</span> <span className="text-foreground">{answer.answer_text || "No answer"}</span></p>
                {answer.question_type !== "subjective" && (
                  <p><span className="text-muted-foreground font-medium">Correct answer:</span> <span className="text-emerald-700 font-medium">{String(answer.correct_answer ?? "Not available")}</span></p>
                )}
                <p><span className="text-muted-foreground font-medium">Score:</span> <strong className="text-primary font-semibold">{answer.score_awarded ?? 0}</strong> {answer.marks ? `/ ${answer.marks}` : ""}</p>
                {answer.is_overridden && answer.faculty_comment && (
                  <div className="mt-2.5 rounded-lg bg-purple-50/70 border border-purple-200 p-3 text-xs sm:text-sm text-purple-950">
                    <strong className="text-purple-900 font-semibold block mb-0.5">Faculty Comment:</strong> {answer.faculty_comment}
                  </div>
                )}
                {answer.ai_feedback && !answer.is_overridden && (
                  <div className="mt-2.5 rounded-lg bg-primary/5 border border-primary/10 p-3 text-xs sm:text-sm text-muted-foreground">
                    <strong className="text-foreground font-medium">Evaluation feedback:</strong> {answer.ai_feedback}
                  </div>
                )}
              </div>
            </section>
          ))}
        </div>
      </div>
    </main>
  );
}

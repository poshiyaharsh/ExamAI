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
  const pending = attempt.status !== "evaluated";

  return <main className="min-h-screen bg-muted/30 p-6"><div className="mx-auto max-w-4xl space-y-6"><button type="button" onClick={() => navigate("/student/exams")} className="text-sm text-muted-foreground hover:text-foreground">Back to exams</button><section className="rounded-xl border border-border bg-white p-6"><p className="text-sm text-muted-foreground">{pending ? "Evaluation in progress" : "Evaluation complete"}</p><h1 className="mt-2 text-3xl font-bold">{attempt.exam_title}</h1><p className="mt-3 text-4xl font-bold text-primary">{attempt.total_score} / {attempt.exam_total_marks}</p>{pending && <p className="mt-2 inline-flex items-center gap-2 text-sm text-muted-foreground"><Clock className="h-4 w-4" /> Subjective answers are being evaluated. This page checks every few seconds.</p>}</section><div className="space-y-3">{attempt.answers.map((answer, index) => <section key={answer.question} className="rounded-xl border border-border bg-white p-5"><div className="flex items-start justify-between gap-4"><div><h2 className="font-medium">Question {index + 1}</h2><p className="mt-1 text-sm text-muted-foreground">{answer.question_text}</p></div>{answer.is_correct === true ? <CheckCircle className="h-5 w-5 text-emerald-600" /> : answer.is_correct === false ? <XCircle className="h-5 w-5 text-red-600" /> : null}</div><p className="mt-4 text-sm">Answer: {answer.answer_text || "No answer"}</p>{answer.question_type !== "subjective" && <p className="mt-2 text-sm">Correct answer: {String(answer.correct_answer ?? "Not available")}</p>}<p className="mt-2 text-sm font-medium">Score: {answer.score_awarded ?? 0}</p>{answer.ai_feedback && <p className="mt-2 rounded-lg bg-accent/40 p-3 text-sm text-muted-foreground">AI feedback: {answer.ai_feedback}</p>}</section>)}</div></div></main>;
}

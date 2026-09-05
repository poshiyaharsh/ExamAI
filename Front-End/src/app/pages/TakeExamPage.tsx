import axios from "axios";
import { useEffect, useMemo, useRef, useState } from "react";
import { Check, Clock, Send } from "lucide-react";
import { useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";
import { studentExamApi, type StudentExamStartResponse } from "../../services/api";

const optionLabels = ["A", "B", "C", "D"];

type SaveState = "idle" | "saving" | "saved" | "error";

function formatCountdown(seconds: number) {
  const minutes = Math.floor(seconds / 60);
  const remainder = seconds % 60;
  return `${String(minutes).padStart(2, "0")}:${String(remainder).padStart(2, "0")}`;
}

function errorMessage(error: unknown) {
  if (axios.isAxiosError(error)) {
    const data = error.response?.data;
    if (data && typeof data === "object") {
      const detail = "detail" in data ? data.detail : "error" in data ? data.error : undefined;
      if (typeof detail === "string") return detail;
    }
    return `Request failed (${error.response?.status ?? "unknown status"}).`;
  }
  return error instanceof Error ? error.message : "Unable to submit the exam.";
}

export function TakeExamPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [session, setSession] = useState<StudentExamStartResponse | null>(null);
  const [answers, setAnswers] = useState<Record<number, string>>({});
  const [secondsLeft, setSecondsLeft] = useState(0);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [submitting, setSubmitting] = useState(false);
  const [saveState, setSaveState] = useState<SaveState>("idle");
  const [showSubmitDialog, setShowSubmitDialog] = useState(false);
  const submitLock = useRef(false);

  useEffect(() => {
    if (!id) return;
    studentExamApi.startExam(Number(id))
      .then((response) => {
        setSession(response);
        setSecondsLeft(Math.max(0, Math.floor((new Date(response.deadline).getTime() - Date.now()) / 1000)));
      })
      .catch((error) => {
        toast.error(errorMessage(error));
        navigate("/student/exams");
      });
  }, [id, navigate]);

  const questions = session?.exam.questions ?? [];
  const currentQuestion = questions[currentIndex];
  const answeredCount = questions.filter((question) => Boolean(answers[question.id]?.trim())).length;
  const answeredMarks = questions.reduce((total, question) => total + (answers[question.id]?.trim() ? question.marks : 0), 0);
  const currentOptions = currentQuestion?.question_type === "truefalse"
    ? ["True", "False"]
    : currentQuestion?.options ?? [];

  useEffect(() => {
    if (!session) return;
    const timer = window.setInterval(() => setSecondsLeft((current) => Math.max(0, current - 1)), 1000);
    return () => window.clearInterval(timer);
  }, [session]);

  useEffect(() => {
    if (secondsLeft === 0 && session && !submitLock.current) setShowSubmitDialog(true);
  }, [secondsLeft, session]);

  useEffect(() => {
    if (!session || !Object.keys(answers).length) return;
    setSaveState("saving");
    const timer = window.setTimeout(async () => {
      const results = await Promise.allSettled(
        Object.entries(answers).map(([questionId, answer]) => studentExamApi.saveAnswer(session.attempt_id, Number(questionId), answer)),
      );
      setSaveState(results.every((result) => result.status === "fulfilled") ? "saved" : "error");
    }, 15000);
    return () => window.clearTimeout(timer);
  }, [answers, session]);

  const setAnswer = (questionId: number, value: string) => {
    setAnswers((current) => ({ ...current, [questionId]: value }));
    setSaveState("idle");
  };

  const submitAttempt = async () => {
    if (!session || submitLock.current) return;
    submitLock.current = true;
    setSubmitting(true);
    try {
      await Promise.allSettled(Object.entries(answers).map(([questionId, answer]) => studentExamApi.saveAnswer(session.attempt_id, Number(questionId), answer)));
      await studentExamApi.submitAttempt(session.attempt_id);
      navigate(`/student/results/${session.attempt_id}`);
    } catch (error) {
      submitLock.current = false;
      setSubmitting(false);
      toast.error(errorMessage(error));
    }
  };

  const typeLabel = useMemo(() => ({
    mcq: "MCQ",
    truefalse: "True / False",
    fillblank: "Fill in the Blank",
    subjective: "Subjective",
  } as const), []);

  if (!session || !currentQuestion) return <div className="flex min-h-screen items-center justify-center text-muted-foreground">Preparing exam...</div>;
  const isWarning = secondsLeft < 300;

  return (
    <div className="min-h-screen bg-muted/30 pb-24">
      <header className="sticky top-0 z-20 border-b border-border bg-white shadow-sm">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-4 py-3 sm:px-6">
          <div className="min-w-0"><h1 className="truncate font-semibold">{session.exam.title}</h1><p className="text-sm text-muted-foreground">Answered {answeredCount}/{questions.length} · {answeredMarks}/{session.exam.total_marks} marks</p></div>
          <div className="flex items-center gap-3"><span className="text-xs text-muted-foreground">{saveState === "saving" ? "Saving..." : saveState === "saved" ? <span className="inline-flex items-center gap-1 text-emerald-600"><Check className="h-3 w-3" /> Saved</span> : saveState === "error" ? <span className="text-red-600">Save failed</span> : "Autosave in 15s"}</span><span className={`inline-flex items-center gap-2 rounded-lg px-3 py-2 font-semibold ${isWarning ? "bg-red-100 text-red-700" : "bg-accent text-accent-foreground"}`}><Clock className="h-4 w-4" />{formatCountdown(secondsLeft)}</span></div>
        </div>
      </header>

      <main className="mx-auto grid max-w-6xl gap-5 p-4 sm:p-6 lg:grid-cols-[220px_minmax(0,1fr)]">
        <aside className="h-fit rounded-xl border border-border bg-white p-4 lg:sticky lg:top-24"><p className="mb-3 text-sm font-semibold">Questions</p><div className="grid grid-cols-6 gap-2 lg:grid-cols-4">{questions.map((question, index) => <button key={question.id} type="button" onClick={() => setCurrentIndex(index)} className={`aspect-square rounded-lg border text-sm font-medium transition-colors ${index === currentIndex ? "border-primary bg-primary text-white" : answers[question.id]?.trim() ? "border-emerald-300 bg-emerald-100 text-emerald-700" : "border-border bg-white text-muted-foreground hover:border-primary"}`}>{index + 1}</button>)}</div><div className="mt-4 space-y-2 text-xs text-muted-foreground"><p><span className="mr-2 inline-block h-3 w-3 rounded bg-primary align-middle" />Current</p><p><span className="mr-2 inline-block h-3 w-3 rounded bg-emerald-100 align-middle" />Answered</p><p><span className="mr-2 inline-block h-3 w-3 rounded border border-border align-middle" />Unanswered</p></div></aside>

        <section className="rounded-xl border border-border bg-white p-5 sm:p-8"><div className="mb-6 flex flex-wrap items-center justify-between gap-3"><div className="flex items-center gap-2"><span className="rounded-full bg-accent px-3 py-1 text-xs font-semibold text-accent-foreground">{typeLabel[currentQuestion.question_type]}</span><span className="rounded-full border border-border px-3 py-1 text-xs font-semibold">Q{currentQuestion.order} · {currentQuestion.marks} {currentQuestion.marks === 1 ? "mark" : "marks"}</span></div><span className="text-sm text-muted-foreground">{currentIndex + 1} of {questions.length}</span></div><h2 className="text-lg font-medium leading-relaxed">{currentQuestion.text}</h2>
          {currentQuestion.question_type === "mcq" || currentQuestion.question_type === "truefalse" || currentQuestion.question_type === "fillblank" ? <div className="mt-7 space-y-3">{currentOptions.map((option, index) => <label key={option} className={`flex cursor-pointer items-center gap-3 rounded-xl border-2 p-4 transition-colors ${answers[currentQuestion.id] === option ? "border-primary bg-accent" : "border-border hover:border-primary/50"}`}><input type="radio" name={`question-${currentQuestion.id}`} checked={answers[currentQuestion.id] === option} onChange={() => setAnswer(currentQuestion.id, option)} className="sr-only" /><span className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-md font-semibold ${answers[currentQuestion.id] === option ? "bg-primary text-white" : "bg-muted text-muted-foreground"}`}>{optionLabels[index]})</span><span>{option}</span></label>)}</div> : <div className="mt-7"><textarea rows={12} value={answers[currentQuestion.id] ?? ""} onChange={(event) => setAnswer(currentQuestion.id, event.target.value)} className="w-full resize-none rounded-xl border border-border p-4 focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20" placeholder="Write your answer here..." /><p className="mt-2 text-right text-xs text-muted-foreground">{(answers[currentQuestion.id] ?? "").length} characters · {(answers[currentQuestion.id] ?? "").trim() ? (answers[currentQuestion.id] ?? "").trim().split(/\s+/).length : 0} words</p></div>}
          <div className="mt-8 flex items-center justify-between gap-3 border-t border-border pt-5"><button type="button" disabled={currentIndex === 0} onClick={() => setCurrentIndex((index) => index - 1)} className="rounded-lg border border-border px-4 py-2 text-sm disabled:opacity-40">Previous</button><button type="button" disabled={currentIndex === questions.length - 1} onClick={() => setCurrentIndex((index) => index + 1)} className="rounded-lg bg-primary px-4 py-2 text-sm text-white disabled:opacity-40">Next</button></div>
        </section>
      </main>

      <footer className="fixed bottom-0 left-0 right-0 z-20 border-t border-border bg-white/95 px-4 py-3 shadow-lg backdrop-blur"><div className="mx-auto flex max-w-6xl items-center justify-between gap-3"><span className="text-sm text-muted-foreground">{answeredCount} of {questions.length} answered</span><button type="button" disabled={submitting} onClick={() => setShowSubmitDialog(true)} className="inline-flex items-center gap-2 rounded-lg bg-primary px-5 py-2.5 font-medium text-white disabled:opacity-50"><Send className="h-4 w-4" />{submitting ? "Submitting..." : "Submit Exam"}</button></div></footer>

      {showSubmitDialog && <div className="fixed inset-0 z-30 grid place-items-center bg-black/40 p-4"><div role="dialog" aria-modal="true" className="w-full max-w-md rounded-xl bg-white p-6 shadow-xl"><h2 className="text-lg font-semibold">Submit exam?</h2><p className="mt-2 text-sm text-muted-foreground">You've answered {answeredCount} of {questions.length} questions. Submit now?</p><div className="mt-6 flex justify-end gap-3"><button type="button" disabled={submitting} onClick={() => setShowSubmitDialog(false)} className="rounded-lg border border-border px-4 py-2 text-sm">Continue exam</button><button type="button" disabled={submitting} onClick={() => { setShowSubmitDialog(false); void submitAttempt(); }} className="rounded-lg bg-primary px-4 py-2 text-sm text-white">Submit now</button></div></div></div>}
    </div>
  );
}

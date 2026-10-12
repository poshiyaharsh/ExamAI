import axios from "axios";
import { useEffect, useMemo, useRef, useState } from "react";
import { Check, Clock, Send } from "lucide-react";
import { useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";
import { studentExamApi, type StudentExamStartResponse } from "../../services/api";

const optionLabels = ["A", "B", "C", "D"];

type SaveState = "idle" | "saving" | "saved" | "retrying" | "error";

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

  // Serial save queue & debouncing
  const pendingAnswersRef = useRef<Record<number, string>>({});
  const isSavingRef = useRef(false);
  const debounceTimerRef = useRef<number | null>(null);
  const retryTimerRef = useRef<number | null>(null);
  const retryCountRef = useRef(0);
  const unmountedRef = useRef(false);

  const flushPendingAnswers = async (): Promise<boolean> => {
    if (!session || isSavingRef.current) return true;
    const batch = { ...pendingAnswersRef.current };
    const questionIds = Object.keys(batch).map(Number);
    if (!questionIds.length) {
      if (!unmountedRef.current) setSaveState("saved");
      return true;
    }

    isSavingRef.current = true;
    if (!unmountedRef.current) setSaveState("saving");

    const payload = questionIds.map((qid) => ({
      question_id: qid,
      answer_text: batch[qid],
    }));

    try {
      await studentExamApi.saveAnswersBatch(session.attempt_id, payload);
      // Remove successfully saved answers from pendingAnswersRef
      for (const qid of questionIds) {
        if (pendingAnswersRef.current[qid] === batch[qid]) {
          delete pendingAnswersRef.current[qid];
        }
      }
      retryCountRef.current = 0;
      isSavingRef.current = false;

      // If more changes arrived during in-flight request, process them
      if (Object.keys(pendingAnswersRef.current).length > 0) {
        return flushPendingAnswers();
      } else {
        if (!unmountedRef.current) setSaveState("saved");
        return true;
      }
    } catch {
      isSavingRef.current = false;
      const retryCount = retryCountRef.current;
      if (retryCount < 5) {
        retryCountRef.current += 1;
        const delay = Math.min(1000 * Math.pow(2, retryCount), 10000);
        if (!unmountedRef.current) setSaveState("retrying");
        if (retryTimerRef.current) window.clearTimeout(retryTimerRef.current);
        retryTimerRef.current = window.setTimeout(() => {
          if (!unmountedRef.current) flushPendingAnswers();
        }, delay);
        return false;
      } else {
        if (!unmountedRef.current) setSaveState("error");
        return false;
      }
    }
  };

  useEffect(() => {
    unmountedRef.current = false;
    const handleBeforeUnload = () => {
      if (Object.keys(pendingAnswersRef.current).length > 0 && session) {
        flushPendingAnswers();
      }
    };
    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => {
      unmountedRef.current = true;
      window.removeEventListener("beforeunload", handleBeforeUnload);
      if (debounceTimerRef.current) window.clearTimeout(debounceTimerRef.current);
      if (retryTimerRef.current) window.clearTimeout(retryTimerRef.current);
    };
  }, [session]);

  const setAnswer = (questionId: number, value: string) => {
    setAnswers((current) => ({ ...current, [questionId]: value }));
    pendingAnswersRef.current[questionId] = value;
    setSaveState("saving");

    if (debounceTimerRef.current) {
      window.clearTimeout(debounceTimerRef.current);
    }
    debounceTimerRef.current = window.setTimeout(() => {
      flushPendingAnswers();
    }, 600);
  };

  const submitAttempt = async () => {
    if (!session || submitLock.current) return;
    submitLock.current = true;
    setSubmitting(true);
    try {
      if (debounceTimerRef.current) window.clearTimeout(debounceTimerRef.current);
      await flushPendingAnswers();
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
          <div className="flex items-center gap-3">
            <span className="text-xs text-muted-foreground">
              {saveState === "saving" ? (
                <span className="inline-flex items-center gap-1 text-amber-600 font-medium">Saving...</span>
              ) : saveState === "saved" ? (
                <span className="inline-flex items-center gap-1 text-emerald-600 font-medium"><Check className="h-3 w-3" /> Saved</span>
              ) : saveState === "retrying" ? (
                <span className="inline-flex items-center gap-1 text-amber-600 font-medium">Offline, will retry</span>
              ) : saveState === "error" ? (
                <span className="inline-flex items-center gap-1 text-rose-600 font-medium" role="button" onClick={() => flushPendingAnswers()}>Save failed (retry)</span>
              ) : (
                <span className="inline-flex items-center gap-1 text-muted-foreground">All changes saved</span>
              )}
            </span>
            <span className={`inline-flex items-center gap-2 rounded-lg px-3 py-1.5 text-xs sm:text-sm font-semibold border ${isWarning ? "bg-rose-50 text-rose-700 border-rose-200" : "bg-primary/10 text-primary border-primary/20"}`}>
              <Clock className="h-4 w-4" />{formatCountdown(secondsLeft)}
            </span>
          </div>
        </div>
      </header>

      <main className="mx-auto grid max-w-6xl gap-5 p-4 sm:p-6 lg:grid-cols-[220px_minmax(0,1fr)]">
        <aside className="h-fit rounded-xl border border-border bg-white p-4 lg:sticky lg:top-24 shadow-sm">
          <p className="mb-3 text-sm font-semibold text-foreground">Questions</p>
          <div className="grid grid-cols-6 gap-2 lg:grid-cols-4">
            {questions.map((question, index) => (
              <button
                key={question.id}
                type="button"
                onClick={() => setCurrentIndex(index)}
                className={`aspect-square rounded-lg border text-xs sm:text-sm transition-all ${
                  index === currentIndex
                    ? "border-primary bg-gradient-to-r from-primary to-secondary text-white font-bold shadow-xs"
                    : answers[question.id]?.trim()
                    ? "border-emerald-300 bg-emerald-50 text-emerald-700 font-medium"
                    : "border-border bg-white text-muted-foreground hover:border-primary/50"
                }`}
              >
                {index + 1}
              </button>
            ))}
          </div>
          <div className="mt-4 space-y-2 text-xs text-muted-foreground pt-3 border-t border-border">
            <p><span className="mr-2 inline-block h-2.5 w-2.5 rounded bg-gradient-to-r from-primary to-secondary align-middle" />Current</p>
            <p><span className="mr-2 inline-block h-2.5 w-2.5 rounded bg-emerald-100 border border-emerald-300 align-middle" />Answered</p>
            <p><span className="mr-2 inline-block h-2.5 w-2.5 rounded border border-border align-middle" />Unanswered</p>
          </div>
        </aside>

        <section className="rounded-xl border border-border bg-white p-5 sm:p-8 shadow-sm">
          <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <span className="rounded-full bg-primary/10 text-primary border border-primary/20 px-3 py-0.5 text-xs font-semibold">{typeLabel[currentQuestion.question_type]}</span>
              <span className="rounded-full border border-border bg-muted/30 px-3 py-0.5 text-xs font-semibold text-foreground">Q{currentQuestion.order} · {currentQuestion.marks} {currentQuestion.marks === 1 ? "mark" : "marks"}</span>
            </div>
            <span className="text-xs sm:text-sm text-muted-foreground">{currentIndex + 1} of {questions.length}</span>
          </div>
          <h2 className="text-base sm:text-lg font-medium leading-relaxed text-foreground">{currentQuestion.text}</h2>
          {currentQuestion.question_type === "mcq" || currentQuestion.question_type === "truefalse" || currentQuestion.question_type === "fillblank" ? (
            <div className="mt-7 space-y-3">
              {currentOptions.map((option, index) => (
                <label
                  key={option}
                  className={`flex cursor-pointer items-center gap-3.5 rounded-xl border-2 p-3.5 sm:p-4 transition-all ${
                    answers[currentQuestion.id] === option ? "border-primary bg-primary/5 ring-1 ring-primary shadow-xs" : "border-border hover:border-primary/40 bg-white"
                  }`}
                >
                  <input
                    type="radio"
                    name={`question-${currentQuestion.id}`}
                    checked={answers[currentQuestion.id] === option}
                    onChange={() => setAnswer(currentQuestion.id, option)}
                    className="sr-only"
                  />
                  <span className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-xs font-semibold transition-all ${answers[currentQuestion.id] === option ? "bg-gradient-to-r from-primary to-secondary text-white" : "bg-muted text-muted-foreground"}`}>
                    {optionLabels[index]})
                  </span>
                  <span className="text-sm font-medium text-foreground">{option}</span>
                </label>
              ))}
            </div>
          ) : (
            <div className="mt-7">
              <textarea
                rows={12}
                value={answers[currentQuestion.id] ?? ""}
                onChange={(event) => setAnswer(currentQuestion.id, event.target.value)}
                className="w-full resize-none rounded-xl border border-border bg-input-background p-4 text-sm focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-all"
                placeholder="Write your answer here..."
              />
              <p className="mt-2 text-right text-xs text-muted-foreground">
                {(answers[currentQuestion.id] ?? "").length} characters · {(answers[currentQuestion.id] ?? "").trim() ? (answers[currentQuestion.id] ?? "").trim().split(/\s+/).length : 0} words
              </p>
            </div>
          )}
          <div className="mt-8 flex items-center justify-between gap-3 border-t border-border pt-5">
            <button
              type="button"
              disabled={currentIndex === 0}
              onClick={() => setCurrentIndex((index) => index - 1)}
              className="rounded-lg border border-border px-4 py-2 text-xs sm:text-sm font-medium text-foreground hover:bg-muted/50 transition-colors disabled:opacity-40"
            >
              Previous
            </button>
            <button
              type="button"
              disabled={currentIndex === questions.length - 1}
              onClick={() => setCurrentIndex((index) => index + 1)}
              className="rounded-lg bg-gradient-to-r from-primary to-secondary px-4 py-2 text-xs sm:text-sm font-medium text-white shadow-sm hover:opacity-90 transition-all disabled:opacity-40"
            >
              Next
            </button>
          </div>
        </section>
      </main>

      <footer className="fixed bottom-0 left-0 right-0 z-20 border-t border-border bg-white/95 px-4 py-3 shadow-lg backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-3">
          <span className="text-xs sm:text-sm text-muted-foreground">{answeredCount} of {questions.length} answered</span>
          <button
            type="button"
            disabled={submitting}
            onClick={() => setShowSubmitDialog(true)}
            className="inline-flex items-center gap-2 rounded-lg bg-gradient-to-r from-primary to-secondary px-5 py-2.5 font-medium text-sm text-white shadow-md hover:opacity-90 transition-all disabled:opacity-50"
          >
            <Send className="h-4 w-4" />{submitting ? "Submitting..." : "Submit Exam"}
          </button>
        </div>
      </footer>

      {showSubmitDialog && (
        <div className="fixed inset-0 z-30 grid place-items-center bg-black/40 backdrop-blur-xs p-4">
          <div role="dialog" aria-modal="true" className="w-full max-w-md rounded-2xl bg-white p-6 shadow-xl border border-border">
            <h2 className="text-lg font-semibold text-foreground">Submit exam?</h2>
            <p className="mt-2 text-xs sm:text-sm text-muted-foreground">You've answered {answeredCount} of {questions.length} questions. Are you sure you want to submit?</p>
            <div className="mt-6 flex justify-end gap-3">
              <button
                type="button"
                disabled={submitting}
                onClick={() => setShowSubmitDialog(false)}
                className="rounded-lg border border-border px-4 py-2 text-xs sm:text-sm font-medium text-foreground hover:bg-muted/50 transition-colors"
              >
                Continue exam
              </button>
              <button
                type="button"
                disabled={submitting}
                onClick={() => { setShowSubmitDialog(false); void submitAttempt(); }}
                className="rounded-lg bg-gradient-to-r from-primary to-secondary px-4 py-2 text-xs sm:text-sm font-medium text-white shadow-md hover:opacity-90 transition-all"
              >
                Submit now
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

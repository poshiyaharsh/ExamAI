import axios from "axios";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  AlertCircle,
  AlertTriangle,
  Bookmark,
  Check,
  ChevronLeft,
  ChevronRight,
  Clock,
  EyeOff,
  Flag,
  HelpCircle,
  Lock,
  Maximize2,
  Minimize2,
  RefreshCw,
  RotateCcw,
  Send,
  ShieldAlert,
  ShieldCheck,
  WifiOff,
  X,
} from "lucide-react";
import { useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";
import { studentExamApi, type StudentExamStartResponse } from "../../services/api";

const optionLabels = ["A", "B", "C", "D", "E", "F"];

type SaveState = "idle" | "saving" | "saved" | "retrying" | "error";

function formatCountdown(seconds: number) {
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const remainder = seconds % 60;
  if (hours > 0) {
    return `${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}:${String(remainder).padStart(2, "0")}`;
  }
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

function cleanOptionText(text: string | null | undefined): string {
  if (!text) return "";
  return String(text).replace(/^\s*(?:\(?[A-Da-d0-9]\)?[\.\)\:\-]\s*|\(?[A-Da-d0-9]\)\s*)/, "").trim() || String(text).trim();
}

function formatMarks(val: number | string | undefined | null): string {
  const num = Number(val) || 0;
  return Number.isInteger(num) ? num.toString() : num.toFixed(2).replace(/\.?0+$/, "");
}

export function TakeExamPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  // Session & core state
  const [session, setSession] = useState<StudentExamStartResponse | null>(null);
  const [examStarted, setExamStarted] = useState(false);
  const [answers, setAnswers] = useState<Record<number, string>>({});
  const [flagged, setFlagged] = useState<Record<number, boolean>>({});
  const [secondsLeft, setSecondsLeft] = useState(0);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [submitting, setSubmitting] = useState(false);
  const [saveState, setSaveState] = useState<SaveState>("idle");
  const [lastSavedAt, setLastSavedAt] = useState<string | null>(null);

  // Proctoring & Modals
  const [rulesAccepted, setRulesAccepted] = useState(false);
  const [fullscreenSupported, setFullscreenSupported] = useState(true);
  const [showRulesModal, setShowRulesModal] = useState(true);
  const [showSubmitDialog, setShowSubmitDialog] = useState(false);
  const [violationModal, setViolationModal] = useState<{
    open: boolean;
    eventType: string;
    violationCount: number;
    maxWarnings: number;
    autoSubmitted: boolean;
    message: string;
  } | null>(null);
  const [concurrentModal, setConcurrentModal] = useState(false);

  // References & Locks
  const submitLock = useRef(false);
  const isArmedRef = useRef(false);
  const blurDebounceRef = useRef<number | null>(null);
  const lastViolationTimeRef = useRef<number>(0);
  const pendingAnswersRef = useRef<Record<number, string>>({});
  const isSavingRef = useRef(false);
  const debounceTimerRef = useRef<number | null>(null);
  const retryTimerRef = useRef<number | null>(null);
  const retryCountRef = useRef(0);
  const unmountedRef = useRef(false);

  // Load Exam Session
  useEffect(() => {
    if (!id) return;
    studentExamApi.startExam(Number(id))
      .then((response) => {
        setSession(response);
        const deadlineMs = new Date(response.deadline).getTime();
        const initialSeconds = Math.max(0, Math.floor((deadlineMs - Date.now()) / 1000));
        setSecondsLeft(initialSeconds);

        // Check fullscreen support
        const doc = document as unknown as { fullscreenEnabled?: boolean; webkitFullscreenEnabled?: boolean };
        if (!doc.fullscreenEnabled && !doc.webkitFullscreenEnabled) {
          setFullscreenSupported(false);
        }
      })
      .catch((error) => {
        toast.error(errorMessage(error));
        navigate("/student/exams");
      });
  }, [id, navigate]);

  const questions = session?.exam.questions ?? [];
  const currentQuestion = questions[currentIndex];
  const answeredCount = questions.filter((question) => Boolean(answers[question.id]?.trim())).length;
  const answeredMarks = questions.reduce(
    (total, question) => total + (answers[question.id]?.trim() ? (Number(question.marks) || 0) : 0),
    0
  );
  const flaggedCount = Object.values(flagged).filter(Boolean).length;

  const currentOptions = useMemo(() => {
    if (!currentQuestion) return [];
    if (currentQuestion.question_type === "truefalse") {
      return ["True", "False"];
    }
    return (currentQuestion.options ?? []).map((opt) => cleanOptionText(opt));
  }, [currentQuestion]);

  // Timer Tick
  useEffect(() => {
    if (!session || !examStarted) return;
    const timer = window.setInterval(() => {
      setSecondsLeft((current) => {
        if (current <= 1) {
          window.clearInterval(timer);
          if (!submitLock.current) {
            void submitAttempt("time_up");
          }
          return 0;
        }
        return current - 1;
      });
    }, 1000);
    return () => window.clearInterval(timer);
  }, [session, examStarted]);

  // Periodic Heartbeat
  useEffect(() => {
    if (!session || !examStarted) return;
    const interval = window.setInterval(async () => {
      if (submitLock.current) return;
      try {
        const hb = await studentExamApi.sendHeartbeat(session.attempt_id, session.session_token);
        if (hb.concurrent_session) {
          setConcurrentModal(true);
          submitLock.current = true;
          return;
        }
        if (hb.expired || hb.auto_submitted) {
          submitLock.current = true;
          toast.warning("Exam time expired on server.");
          navigate(`/student/results/${session.attempt_id}`);
          return;
        }
        if (typeof hb.seconds_left === "number") {
          // Adjust timer drift
          setSecondsLeft(hb.seconds_left);
        }
      } catch {
        // Silently tolerate network hiccup in heartbeat
      }
    }, 15000);
    return () => window.clearInterval(interval);
  }, [session, examStarted, navigate]);

  // Background Save Queue & Retry
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
      for (const qid of questionIds) {
        if (pendingAnswersRef.current[qid] === batch[qid]) {
          delete pendingAnswersRef.current[qid];
        }
      }
      retryCountRef.current = 0;
      isSavingRef.current = false;
      if (!unmountedRef.current) {
        setSaveState("saved");
        setLastSavedAt(new Date().toLocaleTimeString());
      }
      if (Object.keys(pendingAnswersRef.current).length > 0) {
        return flushPendingAnswers();
      }
      return true;
    } catch {
      isSavingRef.current = false;
      const retryCount = retryCountRef.current;
      if (retryCount < 5) {
        retryCountRef.current += 1;
        const delay = Math.min(1000 * Math.pow(2, retryCount), 8000);
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

  const setAnswer = (questionId: number, value: string) => {
    setAnswers((current) => ({ ...current, [questionId]: value }));
    pendingAnswersRef.current[questionId] = value;
    setSaveState("saving");

    if (debounceTimerRef.current) {
      window.clearTimeout(debounceTimerRef.current);
    }
    debounceTimerRef.current = window.setTimeout(() => {
      flushPendingAnswers();
    }, 450);
  };

  const toggleFlag = (questionId: number) => {
    setFlagged((prev) => ({ ...prev, [questionId]: !prev[questionId] }));
  };

  const clearAnswer = (questionId: number) => {
    setAnswer(questionId, "");
  };

  // Submit Exam
  const submitAttempt = async (reason: string = "manual") => {
    if (!session || submitLock.current) return;
    submitLock.current = true;
    setSubmitting(true);
    try {
      if (debounceTimerRef.current) window.clearTimeout(debounceTimerRef.current);
      await flushPendingAnswers();
      await studentExamApi.submitAttempt(session.attempt_id, reason);
      // Exit fullscreen if still active
      if (document.fullscreenElement) {
        try {
          await document.exitFullscreen();
        } catch {
          // ignore
        }
      }
      toast.success("Exam submitted successfully!");
      navigate(`/student/results/${session.attempt_id}`);
    } catch (error) {
      submitLock.current = false;
      setSubmitting(false);
      toast.error(errorMessage(error));
    }
  };

  // Record Violation Helper
  const reportViolation = async (eventType: string, meta: Record<string, unknown> = {}) => {
    if (!session || !isArmedRef.current || submitLock.current) return;

    // Debounce rapid bursts (at least 1.5 seconds between recorded violations)
    const now = Date.now();
    if (now - lastViolationTimeRef.current < 1500) {
      return;
    }
    lastViolationTimeRef.current = now;

    try {
      const res = await studentExamApi.recordViolation(session.attempt_id, eventType, meta);
      setViolationModal({
        open: true,
        eventType,
        violationCount: res.violation_count,
        maxWarnings: res.max_warnings,
        autoSubmitted: res.auto_submitted,
        message: res.message,
      });

      if (res.auto_submitted) {
        submitLock.current = true;
        // Exam terminated due to violations
      }
    } catch (err) {
      toast.error(errorMessage(err));
    }
  };

  // Fullscreen Management
  const requestFullscreen = async () => {
    const elem = document.documentElement as unknown as {
      requestFullscreen?: () => Promise<void>;
      webkitRequestFullscreen?: () => Promise<void>;
    };
    try {
      if (elem.requestFullscreen) {
        await elem.requestFullscreen();
      } else if (elem.webkitRequestFullscreen) {
        await elem.webkitRequestFullscreen();
      }
      return true;
    } catch {
      return false;
    }
  };

  const handleStartExam = async () => {
    if (!rulesAccepted) {
      toast.warning("Please check the box to acknowledge exam rules.");
      return;
    }
    await requestFullscreen();
    setShowRulesModal(false);
    setExamStarted(true);
    isArmedRef.current = true;
  };

  const handleResumeFromViolation = async () => {
    if (violationModal?.autoSubmitted) {
      if (session) navigate(`/student/results/${session.attempt_id}`);
      return;
    }
    await requestFullscreen();
    setViolationModal(null);
  };

  // Proctoring Event Listeners (Armed only once exam started)
  useEffect(() => {
    if (!examStarted) return;

    const handleFullscreenChange = () => {
      const isFs = Boolean(document.fullscreenElement);
      if (!isFs && isArmedRef.current && !submitLock.current) {
        reportViolation("fullscreen_exit", { details: "Student exited fullscreen mode." });
      }
    };

    const handleVisibilityChange = () => {
      if (document.hidden && isArmedRef.current && !submitLock.current) {
        reportViolation("tab_hidden", { details: "Student switched tabs or minimized browser." });
      }
    };

    const handleWindowBlur = () => {
      // Debounce blur to avoid double firing with fullscreen change
      if (blurDebounceRef.current) window.clearTimeout(blurDebounceRef.current);
      blurDebounceRef.current = window.setTimeout(() => {
        if (!document.fullscreenElement && isArmedRef.current && !submitLock.current) {
          reportViolation("window_blur", { details: "Browser window lost focus." });
        }
      }, 400);
    };

    // Deterrents
    const handleContextMenu = (e: MouseEvent) => {
      e.preventDefault();
      toast.error("Right-click context menu is disabled during the exam.");
    };

    const handleCopyCutPaste = (e: ClipboardEvent) => {
      e.preventDefault();
      toast.error("Clipboard operations are prohibited during the exam.");
    };

    const handleKeyDown = (e: KeyboardEvent) => {
      // Prohibit F12, Ctrl+Shift+I, Ctrl+U, Ctrl+C, Ctrl+V, Ctrl+P, Ctrl+S
      if (
        e.key === "F12" ||
        (e.ctrlKey && e.shiftKey && (e.key === "I" || e.key === "i" || e.key === "J" || e.key === "j" || e.key === "C" || e.key === "c")) ||
        (e.ctrlKey && (e.key === "u" || e.key === "U" || e.key === "c" || e.key === "C" || e.key === "v" || e.key === "V" || e.key === "p" || e.key === "P" || e.key === "s" || e.key === "S"))
      ) {
        e.preventDefault();
        toast.warning("Keyboard shortcuts are disabled during proctoring.");
      }
    };

    const handleBeforeUnload = (e: BeforeUnloadEvent) => {
      if (Object.keys(pendingAnswersRef.current).length > 0 && session) {
        flushPendingAnswers();
      }
      e.preventDefault();
      e.returnValue = "Leaving this page may invalidate your exam attempt.";
    };

    document.addEventListener("fullscreenchange", handleFullscreenChange);
    document.addEventListener("webkitfullscreenchange", handleFullscreenChange);
    document.addEventListener("visibilitychange", handleVisibilityChange);
    window.addEventListener("blur", handleWindowBlur);
    document.addEventListener("contextmenu", handleContextMenu);
    document.addEventListener("copy", handleCopyCutPaste);
    document.addEventListener("cut", handleCopyCutPaste);
    document.addEventListener("paste", handleCopyCutPaste);
    document.addEventListener("keydown", handleKeyDown);
    window.addEventListener("beforeunload", handleBeforeUnload);

    return () => {
      document.removeEventListener("fullscreenchange", handleFullscreenChange);
      document.removeEventListener("webkitfullscreenchange", handleFullscreenChange);
      document.removeEventListener("visibilitychange", handleVisibilityChange);
      window.removeEventListener("blur", handleWindowBlur);
      document.removeEventListener("contextmenu", handleContextMenu);
      document.removeEventListener("copy", handleCopyCutPaste);
      document.removeEventListener("cut", handleCopyCutPaste);
      document.removeEventListener("paste", handleCopyCutPaste);
      document.removeEventListener("keydown", handleKeyDown);
      window.removeEventListener("beforeunload", handleBeforeUnload);
    };
  }, [examStarted, session]);

  const typeLabel = useMemo(() => ({
    mcq: "Multiple Choice",
    MCQ_SINGLE: "Multiple Choice",
    MCQ_MULTIPLE: "Multi-Select MCQ",
    truefalse: "True / False",
    TRUE_FALSE: "True / False",
    fillblank: "Fill in the Blank",
    subjective: "Subjective / Long Answer",
    SHORT_ANSWER: "Short Answer",
    LONG_ANSWER: "Long Answer",
  } as Record<string, string>), []);

  if (!session) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-3 bg-muted/40">
        <RefreshCw className="h-8 w-8 animate-spin text-primary" />
        <p className="text-sm font-medium text-muted-foreground">Initializing secure exam environment...</p>
      </div>
    );
  }

  const isWarningTimer = secondsLeft <= 600;
  const isCriticalTimer = secondsLeft <= 120;
  const maxWarnings = session.max_warnings ?? session.exam.max_warnings ?? 3;
  const currentViolations = violationModal?.violationCount ?? session.violation_count ?? 0;

  return (
    <div className="min-h-screen select-none bg-slate-50 text-slate-900 pb-28">
      {/* Fallback Banner for Devices with No Fullscreen API */}
      {!fullscreenSupported && (
        <div className="bg-amber-500/10 border-b border-amber-500/20 px-4 py-2 text-center text-xs font-medium text-amber-800">
          ⚠️ Note: Fullscreen is not supported by your browser/device. Tab switches and focus changes are still monitored.
        </div>
      )}

      {/* Top Bar Header */}
      <header className="sticky top-0 z-30 border-b border-slate-200 bg-white/95 shadow-xs backdrop-blur">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4 px-4 py-3 sm:px-6">
          {/* Title & Department */}
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <h1 className="truncate font-semibold text-slate-900 sm:text-lg">{session.exam.title}</h1>
              {session.exam.department && (
                <span className="hidden sm:inline-flex rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-medium text-slate-700">
                  {session.exam.department}
                </span>
              )}
            </div>
            <p className="text-xs text-slate-500">
              Answered {answeredCount} of {questions.length} questions · {formatMarks(answeredMarks)} of {formatMarks(session.exam.total_marks)} marks
            </p>
          </div>

          {/* Indicators & Actions */}
          <div className="flex items-center gap-3 sm:gap-4">
            {/* Auto-Save Status */}
            <div className="hidden sm:flex items-center gap-1.5 text-xs">
              {saveState === "saving" ? (
                <span className="inline-flex items-center gap-1 text-amber-600 font-medium">
                  <RefreshCw className="h-3.5 w-3.5 animate-spin" /> Saving...
                </span>
              ) : saveState === "saved" ? (
                <span className="inline-flex items-center gap-1 text-emerald-600 font-medium">
                  <Check className="h-3.5 w-3.5" /> Saved {lastSavedAt && `(${lastSavedAt})`}
                </span>
              ) : saveState === "retrying" ? (
                <span className="inline-flex items-center gap-1 text-amber-700 font-medium">
                  <WifiOff className="h-3.5 w-3.5" /> Re-connecting...
                </span>
              ) : saveState === "error" ? (
                <button
                  type="button"
                  onClick={() => flushPendingAnswers()}
                  className="inline-flex items-center gap-1 text-rose-600 font-medium hover:underline"
                >
                  <AlertCircle className="h-3.5 w-3.5" /> Retry Save
                </button>
              ) : (
                <span className="inline-flex items-center gap-1 text-slate-400">
                  <Check className="h-3.5 w-3.5" /> Ready
                </span>
              )}
            </div>

            {/* Warning Counter Badge */}
            <div
              className={`inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-xs font-semibold border ${
                currentViolations === 0
                  ? "bg-slate-50 text-slate-600 border-slate-200"
                  : currentViolations < maxWarnings
                  ? "bg-amber-50 text-amber-700 border-amber-200"
                  : "bg-rose-50 text-rose-700 border-rose-200 animate-pulse"
              }`}
              title="Proctoring Warnings"
            >
              <ShieldAlert className="h-3.5 w-3.5" />
              <span>Warnings: {currentViolations} / {maxWarnings}</span>
            </div>

            {/* Countdown Timer with color-shifting & pulsing */}
            <div
              className={`inline-flex items-center gap-2 rounded-xl px-3.5 py-1.5 text-sm font-bold border transition-all ${
                isCriticalTimer
                  ? "bg-rose-600 text-white border-rose-700 animate-pulse shadow-md"
                  : isWarningTimer
                  ? "bg-amber-50 text-amber-700 border-amber-300"
                  : "bg-slate-100 text-slate-800 border-slate-200"
              }`}
            >
              <Clock className="h-4 w-4" />
              <span className="tracking-wider">{formatCountdown(secondsLeft)}</span>
            </div>

            {/* Fullscreen Toggle Button */}
            {fullscreenSupported && (
              <button
                type="button"
                onClick={requestFullscreen}
                className="hidden md:inline-flex items-center justify-center rounded-lg border border-slate-200 p-2 text-slate-600 hover:bg-slate-100 transition-colors"
                title="Fullscreen"
              >
                <Maximize2 className="h-4 w-4" />
              </button>
            )}

            {/* Submit Top Action */}
            <button
              type="button"
              disabled={submitting}
              onClick={() => setShowSubmitDialog(true)}
              className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-3.5 py-1.5 text-xs sm:text-sm font-semibold text-white shadow-xs hover:bg-primary/90 transition-all disabled:opacity-50"
            >
              <Send className="h-3.5 w-3.5" />
              <span>Finish</span>
            </button>
          </div>
        </div>
      </header>

      {/* Main Container: Question Palette Sidebar + Active Question Canvas */}
      <main className="mx-auto grid max-w-7xl gap-6 p-4 sm:p-6 lg:grid-cols-[260px_minmax(0,1fr)]">
        {/* Left Aside: Question Palette & Overview */}
        <aside className="h-fit rounded-2xl border border-slate-200 bg-white p-5 shadow-xs lg:sticky lg:top-24">
          <div className="flex items-center justify-between border-b border-slate-100 pb-3 mb-4">
            <h2 className="text-sm font-bold text-slate-900 uppercase tracking-wide">Question Palette</h2>
            <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-semibold text-slate-600">
              {questions.length} Total
            </span>
          </div>

          {/* Palette Grid */}
          <div className="grid grid-cols-5 gap-2">
            {questions.map((question, index) => {
              const isCurrent = index === currentIndex;
              const isAnswered = Boolean(answers[question.id]?.trim());
              const isFlagged = Boolean(flagged[question.id]);

              return (
                <button
                  key={question.id}
                  type="button"
                  onClick={() => setCurrentIndex(index)}
                  className={`relative flex aspect-square flex-col items-center justify-center rounded-xl text-xs font-bold transition-all ${
                    isCurrent
                      ? "bg-blue-600 text-white shadow-sm ring-2 ring-blue-600 ring-offset-2"
                      : isFlagged
                      ? "bg-amber-100 border-2 border-amber-400 text-amber-900"
                      : isAnswered
                      ? "bg-emerald-500 text-white"
                      : "border border-slate-200 bg-white text-slate-700 hover:border-blue-400 hover:bg-slate-50"
                  }`}
                >
                  <span>{index + 1}</span>
                  {isFlagged && (
                    <span className="absolute top-1 right-1 h-2 w-2 rounded-full bg-amber-500" />
                  )}
                </button>
              );
            })}
          </div>

          {/* Legend */}
          <div className="mt-6 space-y-2 border-t border-slate-100 pt-4 text-xs font-medium text-slate-600">
            <div className="flex items-center justify-between">
              <span className="flex items-center gap-2">
                <span className="h-3 w-3 rounded bg-blue-600" /> Current
              </span>
              <span className="font-semibold text-slate-900">Q{currentIndex + 1}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="flex items-center gap-2">
                <span className="h-3 w-3 rounded bg-emerald-500" /> Answered
              </span>
              <span className="font-semibold text-slate-900">{answeredCount}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="flex items-center gap-2">
                <span className="h-3 w-3 rounded bg-amber-100 border border-amber-400" /> Flagged for Review
              </span>
              <span className="font-semibold text-slate-900">{flaggedCount}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="flex items-center gap-2">
                <span className="h-3 w-3 rounded border border-slate-200 bg-white" /> Unanswered
              </span>
              <span className="font-semibold text-slate-900">{questions.length - answeredCount}</span>
            </div>
          </div>
        </aside>

        {/* Right Section: Active Question Display */}
        {currentQuestion && (
          <section className="rounded-2xl border border-slate-200 bg-white p-6 sm:p-8 shadow-xs">
            {/* Question Header & Meta */}
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 pb-4">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="rounded-full bg-blue-50 px-3 py-1 text-xs font-bold text-blue-700 border border-blue-200">
                  {typeLabel[currentQuestion.question_type] ?? "Question"}
                </span>
                <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-700">
                  {formatMarks(currentQuestion.marks)} {Number(currentQuestion.marks) === 1 ? "Mark" : "Marks"}
                </span>
                {currentQuestion.topic && (
                  <span className="rounded-full bg-slate-50 px-3 py-1 text-xs text-slate-500 border border-slate-100">
                    Topic: {currentQuestion.topic}
                  </span>
                )}
              </div>

              {/* Flag for Review Toggle Button */}
              <button
                type="button"
                onClick={() => toggleFlag(currentQuestion.id)}
                className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-1 text-xs font-semibold transition-all ${
                  flagged[currentQuestion.id]
                    ? "bg-amber-500 text-white shadow-xs"
                    : "border border-slate-200 bg-white text-slate-600 hover:bg-slate-50"
                }`}
              >
                <Bookmark className={`h-3.5 w-3.5 ${flagged[currentQuestion.id] ? "fill-white" : ""}`} />
                <span>{flagged[currentQuestion.id] ? "Flagged for Review" : "Flag Question"}</span>
              </button>
            </div>

            {/* Question Text Body */}
            <div className="mt-6">
              <div className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">
                Question {currentIndex + 1} of {questions.length}
              </div>
              <h3 className="text-base sm:text-lg font-medium leading-relaxed text-slate-900">
                {currentQuestion.text}
              </h3>
            </div>

            {/* Answer Input Area */}
            {currentOptions.length > 0 ? (
              <div className="mt-8 space-y-3">
                {currentOptions.map((option, idx) => {
                  const isSelected = cleanOptionText(answers[currentQuestion.id] ?? "") === option;
                  const labelLetter = optionLabels[idx] || String(idx + 1);

                  return (
                    <label
                      key={`${idx}-${option}`}
                      className={`flex cursor-pointer items-center gap-4 rounded-xl border-2 p-4 transition-all ${
                        isSelected
                          ? "border-blue-600 bg-blue-50/50 shadow-xs ring-1 ring-blue-600"
                          : "border-slate-200 bg-white hover:border-slate-300 hover:bg-slate-50/50"
                      }`}
                    >
                      <input
                        type="radio"
                        name={`question-${currentQuestion.id}`}
                        checked={isSelected}
                        onChange={() => setAnswer(currentQuestion.id, option)}
                        className="sr-only"
                      />
                      <span
                        className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-sm font-bold transition-all ${
                          isSelected ? "bg-blue-600 text-white shadow-xs" : "bg-slate-100 text-slate-600"
                        }`}
                      >
                        {labelLetter}
                      </span>
                      <span className="text-sm sm:text-base font-normal text-slate-800 leading-normal">
                        {option}
                      </span>
                    </label>
                  );
                })}
              </div>
            ) : (
              <div className="mt-8">
                <textarea
                  rows={10}
                  value={answers[currentQuestion.id] ?? ""}
                  onChange={(e) => setAnswer(currentQuestion.id, e.target.value)}
                  placeholder="Type your response here..."
                  className="w-full rounded-xl border border-slate-200 bg-slate-50/50 p-4 text-sm text-slate-900 placeholder-slate-400 focus:border-blue-500 focus:bg-white focus:outline-hidden focus:ring-2 focus:ring-blue-500/20 transition-all resize-y"
                />
                <div className="mt-2 flex items-center justify-between text-xs text-slate-400">
                  <span>{(answers[currentQuestion.id] ?? "").length} characters</span>
                  <span>{(answers[currentQuestion.id] ?? "").trim() ? (answers[currentQuestion.id] ?? "").trim().split(/\s+/).length : 0} words</span>
                </div>
              </div>
            )}

            {/* Bottom Actions Row */}
            <div className="mt-8 flex flex-wrap items-center justify-between gap-3 border-t border-slate-100 pt-6">
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  disabled={currentIndex === 0}
                  onClick={() => setCurrentIndex((idx) => idx - 1)}
                  className="inline-flex items-center gap-1 rounded-xl border border-slate-200 bg-white px-4 py-2 text-xs sm:text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-40 transition-colors"
                >
                  <ChevronLeft className="h-4 w-4" /> Previous
                </button>
                <button
                  type="button"
                  disabled={currentIndex === questions.length - 1}
                  onClick={() => setCurrentIndex((idx) => idx + 1)}
                  className="inline-flex items-center gap-1 rounded-xl bg-slate-900 px-4 py-2 text-xs sm:text-sm font-semibold text-white hover:bg-slate-800 disabled:opacity-40 transition-colors"
                >
                  Next <ChevronRight className="h-4 w-4" />
                </button>
              </div>

              {Boolean(answers[currentQuestion.id]?.trim()) && (
                <button
                  type="button"
                  onClick={() => clearAnswer(currentQuestion.id)}
                  className="inline-flex items-center gap-1 text-xs font-semibold text-slate-500 hover:text-rose-600 transition-colors"
                >
                  <RotateCcw className="h-3.5 w-3.5" /> Clear Answer
                </button>
              )}
            </div>
          </section>
        )}
      </main>

      {/* Fixed Bottom Bar */}
      <footer className="fixed bottom-0 left-0 right-0 z-20 border-t border-slate-200 bg-white/95 px-4 py-3 shadow-lg backdrop-blur">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-3">
          <div className="text-xs sm:text-sm text-slate-600">
            <span className="font-semibold text-slate-900">{answeredCount}</span> of {questions.length} answered
            {flaggedCount > 0 && <span className="ml-2 text-amber-700 font-medium">({flaggedCount} flagged)</span>}
          </div>
          <button
            type="button"
            disabled={submitting}
            onClick={() => setShowSubmitDialog(true)}
            className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-blue-600 to-indigo-600 px-5 py-2.5 text-xs sm:text-sm font-bold text-white shadow-md hover:from-blue-700 hover:to-indigo-700 transition-all disabled:opacity-50"
          >
            <Send className="h-4 w-4" /> {submitting ? "Submitting..." : "Submit Exam"}
          </button>
        </div>
      </footer>

      {/* 1. Pre-Exam Rules Modal (Requires explicit start gesture for Fullscreen) */}
      {showRulesModal && (
        <div className="fixed inset-0 z-50 grid place-items-center bg-slate-950/80 p-4 backdrop-blur-sm">
          <div className="w-full max-w-lg rounded-3xl bg-white p-6 sm:p-8 shadow-2xl border border-slate-200">
            <div className="flex items-center gap-3">
              <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-blue-50 text-blue-600">
                <ShieldCheck className="h-6 w-6" />
              </div>
              <div>
                <h2 className="text-xl font-bold text-slate-900">{session.exam.title}</h2>
                <p className="text-xs text-slate-500">Proctored Online Assessment Environment</p>
              </div>
            </div>

            <div className="mt-5 space-y-3 rounded-2xl bg-slate-50 p-4 text-xs sm:text-sm text-slate-700">
              <p className="font-semibold text-slate-900">Assessment Integrity Rules:</p>
              <ul className="space-y-2 text-slate-600 list-disc pl-4">
                <li>
                  <strong className="text-slate-800">Fullscreen Required:</strong> This exam must be taken in full-screen mode throughout its entire duration.
                </li>
                <li>
                  <strong className="text-slate-800">Proctoring Enforcement:</strong> Switching tabs, minimizing the window, or exiting fullscreen records a proctoring violation.
                </li>
                <li>
                  <strong className="text-slate-800">Strict Warning Limit:</strong> You have a maximum of{" "}
                  <span className="font-bold text-rose-600">{maxWarnings} warnings</span>. The{" "}
                  {maxWarnings + 1}th violation will immediately and permanently auto-submit your exam.
                </li>
                <li>
                  <strong className="text-slate-800">Server-Side Timer:</strong> The countdown timer ({session.exam.duration_minutes} minutes) runs on the server and cannot be paused.
                </li>
                <li>
                  <strong className="text-slate-800">Auto-Save:</strong> All responses are automatically saved in the background.
                </li>
              </ul>
            </div>

            <label className="mt-5 flex cursor-pointer items-start gap-3 rounded-xl border border-slate-200 p-3 hover:bg-slate-50">
              <input
                type="checkbox"
                checked={rulesAccepted}
                onChange={(e) => setRulesAccepted(e.target.checked)}
                className="mt-0.5 h-4 w-4 rounded border-slate-300 text-blue-600 focus:ring-blue-500"
              />
              <span className="text-xs text-slate-700 leading-normal">
                I understand and agree to adhere strictly to all integrity rules, proctoring guidelines, and time constraints.
              </span>
            </label>

            <div className="mt-6 flex justify-end gap-3">
              <button
                type="button"
                onClick={() => navigate("/student/exams")}
                className="rounded-xl border border-slate-200 px-4 py-2.5 text-xs sm:text-sm font-semibold text-slate-700 hover:bg-slate-100 transition-colors"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleStartExam}
                className="inline-flex items-center gap-2 rounded-xl bg-blue-600 px-5 py-2.5 text-xs sm:text-sm font-bold text-white shadow-md hover:bg-blue-700 transition-all"
              >
                <Maximize2 className="h-4 w-4" /> Enter Fullscreen & Start Exam
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 2. Warning Modal (Proctoring Violation Alert) */}
      {violationModal?.open && (
        <div className="fixed inset-0 z-50 grid place-items-center bg-slate-950/85 p-4 backdrop-blur-md">
          <div className="w-full max-w-md rounded-3xl bg-white p-6 shadow-2xl border-2 border-rose-500">
            <div className="flex items-center gap-3 text-rose-600">
              <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-rose-50">
                <AlertTriangle className="h-6 w-6 text-rose-600 animate-bounce" />
              </div>
              <div>
                <h3 className="text-lg font-bold text-slate-900">
                  {violationModal.autoSubmitted ? "Exam Terminated" : "Proctoring Alert"}
                </h3>
                <p className="text-xs font-semibold text-rose-600">
                  Warning {violationModal.violationCount} of {violationModal.maxWarnings}
                </p>
              </div>
            </div>

            <div className="mt-4 rounded-xl bg-rose-50/60 p-4 text-xs sm:text-sm text-slate-700">
              <p className="font-medium text-slate-900">{violationModal.message}</p>
              {!violationModal.autoSubmitted && (
                <p className="mt-2 text-rose-700">
                  ⚠️ Further violations will cause your exam to be automatically submitted with your current score.
                </p>
              )}
            </div>

            {/* Countdown continues during warning modal */}
            <div className="mt-4 flex items-center justify-between rounded-xl bg-slate-100 px-4 py-2 text-xs font-semibold text-slate-700">
              <span className="flex items-center gap-1.5">
                <Clock className="h-4 w-4 text-slate-500" /> Timer Running:
              </span>
              <span className="font-mono text-sm font-bold text-slate-900">
                {formatCountdown(secondsLeft)}
              </span>
            </div>

            <div className="mt-6 flex justify-end">
              <button
                type="button"
                onClick={handleResumeFromViolation}
                className="w-full rounded-xl bg-rose-600 py-3 text-xs sm:text-sm font-bold text-white shadow-md hover:bg-rose-700 transition-all"
              >
                {violationModal.autoSubmitted ? "View Results" : "Re-enter Fullscreen & Continue"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 3. Concurrent Session Detected Modal */}
      {concurrentModal && (
        <div className="fixed inset-0 z-50 grid place-items-center bg-slate-950/90 p-4 backdrop-blur-md">
          <div className="w-full max-w-md rounded-3xl bg-white p-6 shadow-2xl border border-slate-200 text-center">
            <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-amber-100 text-amber-700 mb-4">
              <Lock className="h-7 w-7" />
            </div>
            <h3 className="text-lg font-bold text-slate-900">Session Terminated</h3>
            <p className="mt-2 text-xs sm:text-sm text-slate-600">
              A newer exam session was initiated in another browser tab or window. Only one active window is permitted at a time to ensure academic honesty.
            </p>
            <div className="mt-6">
              <button
                type="button"
                onClick={() => navigate("/student/exams")}
                className="w-full rounded-xl bg-slate-900 py-2.5 text-xs sm:text-sm font-semibold text-white shadow-md hover:bg-slate-800"
              >
                Return to Exam Portal
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 4. Submit Confirmation Dialog */}
      {showSubmitDialog && (
        <div className="fixed inset-0 z-40 grid place-items-center bg-slate-950/60 p-4 backdrop-blur-xs">
          <div role="dialog" aria-modal="true" className="w-full max-w-md rounded-3xl bg-white p-6 sm:p-7 shadow-2xl border border-slate-200">
            <h3 className="text-lg font-bold text-slate-900">Confirm Exam Submission</h3>
            <p className="mt-2 text-xs sm:text-sm text-slate-600">
              Are you sure you want to finish and submit your exam? Once submitted, your answers cannot be altered.
            </p>

            <div className="my-5 grid grid-cols-3 gap-2 rounded-2xl bg-slate-50 p-3 text-center">
              <div className="rounded-xl bg-white p-2 shadow-2xs">
                <span className="block text-lg font-bold text-emerald-600">{answeredCount}</span>
                <span className="text-[11px] text-slate-500">Answered</span>
              </div>
              <div className="rounded-xl bg-white p-2 shadow-2xs">
                <span className="block text-lg font-bold text-slate-500">{questions.length - answeredCount}</span>
                <span className="text-[11px] text-slate-500">Unanswered</span>
              </div>
              <div className="rounded-xl bg-white p-2 shadow-2xs">
                <span className="block text-lg font-bold text-amber-600">{flaggedCount}</span>
                <span className="text-[11px] text-slate-500">Flagged</span>
              </div>
            </div>

            <div className="flex justify-end gap-3">
              <button
                type="button"
                disabled={submitting}
                onClick={() => setShowSubmitDialog(false)}
                className="rounded-xl border border-slate-200 px-4 py-2.5 text-xs sm:text-sm font-semibold text-slate-700 hover:bg-slate-50 transition-colors"
              >
                Return to Exam
              </button>
              <button
                type="button"
                disabled={submitting}
                onClick={() => {
                  setShowSubmitDialog(false);
                  void submitAttempt("manual");
                }}
                className="inline-flex items-center gap-1.5 rounded-xl bg-blue-600 px-5 py-2.5 text-xs sm:text-sm font-bold text-white shadow-md hover:bg-blue-700 transition-all"
              >
                {submitting ? "Submitting..." : "Yes, Submit Now"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

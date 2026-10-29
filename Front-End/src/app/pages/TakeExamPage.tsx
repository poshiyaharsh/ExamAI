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

const typeLabels: Record<string, string> = {
  mcq: "Multiple Choice",
  true_false: "True / False",
  truefalse: "True / False",
  fill_blank: "Fill in the Blanks",
  fillblank: "Fill in the Blanks",
  short_answer: "Short Answer",
  long_answer: "Long Answer",
  subjective: "Subjective",
};

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
  const [blankAnswers, setBlankAnswers] = useState<Record<number, string[]>>({});
  const [flagged, setFlagged] = useState<Record<number, boolean>>({});
  const [secondsLeft, setSecondsLeft] = useState(0);
  const [clockDriftMs, setClockDriftMs] = useState(0);
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
  const pendingBlankAnswersRef = useRef<Record<number, string[]>>({});
  const isSavingRef = useRef(false);
  const debounceTimerRef = useRef<number | null>(null);
  const retryTimerRef = useRef<number | null>(null);
  const retryCountRef = useRef(0);
  const unmountedRef = useRef(false);
  const warned10mRef = useRef(false);
  const warned2mRef = useRef(false);

  // Load Exam Session
  useEffect(() => {
    if (!id) return;
    studentExamApi.startExam(Number(id))
      .then((response) => {
        setSession(response);
        const serverNowMs = response.server_now ? new Date(response.server_now).getTime() : Date.now();
        const drift = serverNowMs - Date.now();
        setClockDriftMs(drift);

        const deadlineMs = new Date(response.deadline).getTime();
        const initialSeconds = response.duration_seconds !== undefined
          ? response.duration_seconds
          : Math.max(0, Math.floor((deadlineMs - (Date.now() + drift)) / 1000));
        setSecondsLeft(initialSeconds);

        // Check fullscreen support
        const doc = document as unknown as { fullscreenEnabled?: boolean; webkitFullscreenEnabled?: boolean };
        if (!doc.fullscreenEnabled && !doc.webkitFullscreenEnabled) {
          setFullscreenSupported(false);
        }
      })
      .catch((error) => {
        if (axios.isAxiosError(error) && error.response?.data?.redirect_url) {
          const detail = error.response.data.detail || "This exam attempt has already been submitted.";
          if (error.response.data.submit_reason === "violations" || error.response.data.error_code === "EXAM_SUBMITTED_VIOLATIONS") {
            toast.error("Your exam was submitted automatically because of repeated rule violations.");
          } else {
            toast.info(detail);
          }
          navigate(error.response.data.redirect_url);
          return;
        }
        toast.error(errorMessage(error));
        navigate("/student/exams");
      });
  }, [id, navigate]);

  const questions = session?.exam.questions ?? [];
  const currentQuestion = questions[currentIndex];

  const isQuestionAnswered = (question: any) => {
    if (!question) return false;
    const qType = question.question_type;
    if (qType === "fill_blank" || qType === "fillblank") {
      const blankMatches = question.text.match(/_{3,}/g);
      const totalBlanks = blankMatches ? blankMatches.length : 1;
      const studentBlanks = blankAnswers[question.id] || [];
      if (studentBlanks.length < totalBlanks) return false;
      return studentBlanks.slice(0, totalBlanks).every((b: string) => Boolean(b && b.trim().length > 0));
    }
    return Boolean(answers[question.id]?.trim());
  };

  const answeredCount = questions.filter(isQuestionAnswered).length;
  const answeredMarks = questions.reduce(
    (total, question) => total + (isQuestionAnswered(question) ? (Number(question.marks) || 0) : 0),
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
        // Warning alerts at 10m and 2m thresholds
        if (current <= 600 && current > 598 && !warned10mRef.current) {
          warned10mRef.current = true;
          toast.warning("10 minutes remaining in this exam.");
        }
        if (current <= 120 && current > 118 && !warned2mRef.current) {
          warned2mRef.current = true;
          toast.error("2 minutes remaining! Finalize and verify your answers.");
        }

        if (current <= 1) {
          window.clearInterval(timer);
          if (!submitLock.current) {
            const isWindowClosed = session.exam.ends_at
              ? (Date.now() + clockDriftMs >= new Date(session.exam.ends_at).getTime())
              : false;
            void submitAttempt(isWindowClosed ? "window_closed" : "time_up");
          }
          return 0;
        }
        return current - 1;
      });
    }, 1000);
    return () => window.clearInterval(timer);
  }, [session, examStarted, clockDriftMs]);

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
        if (hb.server_now) {
          const drift = new Date(hb.server_now).getTime() - Date.now();
          setClockDriftMs(drift);
        }
        if (hb.expired || hb.auto_submitted || hb.already_submitted || hb.active === false) {
          submitLock.current = true;
          isArmedRef.current = false;
          if (hb.submit_reason === "violations") {
            toast.error("Your exam was submitted automatically because of repeated rule violations.");
          } else if (hb.submit_reason === "window_closed") {
            toast.warning("The exam window has closed on the server.");
          } else {
            toast.warning("Exam time expired on server.");
          }
          navigate(hb.redirect_url || `/student/results/${session.attempt_id}`);
          return;
        }
        if (typeof hb.seconds_left === "number") {
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
      blank_answers: pendingBlankAnswersRef.current[qid] || undefined,
    }));

    try {
      const saveRes = await studentExamApi.saveAnswersBatch(session.attempt_id, payload);
      if ((saveRes as any)?.already_submitted || (saveRes as any)?.auto_submitted) {
        submitLock.current = true;
        isArmedRef.current = false;
        if ((saveRes as any)?.submit_reason === "violations") {
          toast.error("Your exam was submitted automatically because of repeated rule violations.");
        } else {
          toast.warning("This exam attempt has already been submitted.");
        }
        navigate((saveRes as any)?.redirect_url || `/student/results/${session.attempt_id}`);
        return false;
      }
      for (const qid of questionIds) {
        if (pendingAnswersRef.current[qid] === batch[qid]) {
          delete pendingAnswersRef.current[qid];
          delete pendingBlankAnswersRef.current[qid];
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
    } catch (err: any) {
      isSavingRef.current = false;
      if (axios.isAxiosError(err)) {
        const errData = err.response?.data;
        if (
          err.response?.status === 403 ||
          errData?.already_submitted ||
          errData?.auto_submitted ||
          errData?.error_code === "EXAM_EXPIRED" ||
          errData?.error_code === "EXAM_SUBMITTED_VIOLATIONS"
        ) {
          submitLock.current = true;
          isArmedRef.current = false;
          if (errData?.submit_reason === "violations" || errData?.error_code === "EXAM_SUBMITTED_VIOLATIONS") {
            toast.error("Your exam was submitted automatically because of repeated rule violations.");
          } else {
            toast.warning(errData?.detail || "The exam deadline has passed. Your attempt has been finalized.");
          }
          navigate(errData?.redirect_url || `/student/results/${session.attempt_id}`);
          return false;
        }
      }
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

  const setBlankValue = (questionId: number, index: number, value: string, totalBlanks: number) => {
    const existing = blankAnswers[questionId]
      ? [...blankAnswers[questionId]]
      : Array(totalBlanks).fill("");
    while (existing.length < totalBlanks) existing.push("");
    existing[index] = value;

    setBlankAnswers((prev) => ({ ...prev, [questionId]: existing }));
    pendingBlankAnswersRef.current[questionId] = existing;

    const joined = existing.join(", ");
    setAnswers((prev) => ({ ...prev, [questionId]: joined }));
    pendingAnswersRef.current[questionId] = joined;

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
    setBlankAnswers((prev) => ({ ...prev, [questionId]: [] }));
    delete pendingBlankAnswersRef.current[questionId];
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

    // Debounce fullscreen exit, tab hidden, and window blur firing together for the same action (1-second window)
    const now = Date.now();
    if (now - lastViolationTimeRef.current < 1000) {
      return;
    }
    lastViolationTimeRef.current = now;

    // Capture un-flushed buffered answers to guarantee student work is saved upon auto-submit
    const buffered = Object.keys(pendingAnswersRef.current).map((qidStr) => {
      const qid = Number(qidStr);
      return {
        question_id: qid,
        answer_text: pendingAnswersRef.current[qid],
        blank_answers: pendingBlankAnswersRef.current[qid] || undefined,
      };
    });

    const eventId = `viol_${session.attempt_id}_${eventType}_${now}_${Math.random().toString(36).substring(2, 7)}`;

    // Retry on network failure with idempotent eventId
    let res: ProctoringViolationResponse | null = null;
    let lastErr: any = null;
    for (let attempt = 0; attempt < 3; attempt++) {
      try {
        res = await studentExamApi.recordViolation(
          session.attempt_id,
          eventType,
          meta,
          eventId,
          buffered.length > 0 ? buffered : undefined
        );
        break;
      } catch (err: any) {
        lastErr = err;
        if (axios.isAxiosError(err) && (err.response?.data?.auto_submitted || err.response?.data?.already_submitted)) {
          res = err.response.data as ProctoringViolationResponse;
          break;
        }
        await new Promise((r) => window.setTimeout(r, 250));
      }
    }

    if (!res && lastErr) {
      toast.error(errorMessage(lastErr));
      return;
    }
    if (!res) return;

    if (res.auto_submitted || res.already_submitted) {
      submitLock.current = true;
      isArmedRef.current = false;
      setViolationModal(null);
      toast.error("Your exam was submitted automatically because of repeated rule violations.", { duration: 6000 });
      navigate(res.redirect_url || `/student/results/${session.attempt_id}`);
      return;
    }

    setViolationModal({
      open: true,
      eventType,
      violationCount: res.violation_count,
      maxWarnings: res.max_warnings,
      autoSubmitted: false,
      message: res.message,
    });
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
      if (!document.fullscreenElement && isArmedRef.current && !submitLock.current) {
        reportViolation("window_blur", { details: "Browser window lost focus." });
      }
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
  const maxWarnings = session.max_warnings ?? session.exam.max_warnings ?? 1;
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
              <span>Warnings {currentViolations}/{maxWarnings}</span>
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

      {session.is_window_capped && (
        <div className="mx-auto max-w-7xl px-4 pt-4 sm:px-6">
          <div className="flex items-center gap-3 rounded-2xl border border-amber-300 bg-amber-50/95 p-4 text-amber-900 shadow-xs">
            <AlertTriangle className="h-5 w-5 text-amber-600 shrink-0" />
            <div className="text-xs sm:text-sm">
              <span className="font-bold">Window-Capped Attempt:</span>{" "}
              This exam window closes at{" "}
              <strong>
                {session.exam.ends_at
                  ? new Date(session.exam.ends_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
                  : "the scheduled deadline"}
              </strong>
              . Your personal timer is capped by the exam end time to ensure all answers are submitted before the exam closes.
            </div>
          </div>
        </div>
      )}

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
              const isAnswered = isQuestionAnswered(question);
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
        {currentQuestion && (() => {
          const qType = currentQuestion.question_type;
          const isFillBlank = qType === "fill_blank" || qType === "fillblank";
          const isTrueFalse = qType === "true_false" || qType === "truefalse";
          const isMcq = qType === "mcq";
          const isSubjective = qType === "short_answer" || qType === "long_answer" || qType === "subjective";

          const blankMatches = currentQuestion.text.match(/_{3,}/g);
          const totalBlanks = isFillBlank ? (blankMatches ? blankMatches.length : 1) : 0;
          const currentBlanks = blankAnswers[currentQuestion.id] || Array(totalBlanks).fill("");

          const textAnswer = answers[currentQuestion.id] ?? "";
          const wordCount = textAnswer.trim() ? textAnswer.trim().split(/\s+/).length : 0;
          const wordLimitExceeded = Boolean(currentQuestion.word_limit && wordCount > currentQuestion.word_limit);

          const hasAnsweredCurrent = isFillBlank
            ? currentBlanks.some((b) => Boolean(b && b.trim()))
            : Boolean(textAnswer.trim());

          return (
            <section className="rounded-2xl border border-slate-200 bg-white p-6 sm:p-8 shadow-xs space-y-6">
              {/* Question Header & Meta */}
              <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 pb-4">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="rounded-full bg-blue-50 px-3 py-1 text-xs font-bold text-blue-700 border border-blue-200">
                    {typeLabels[qType] ?? "Question"}
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

              {/* Question Prompt */}
              <div>
                <div className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">
                  Question {currentIndex + 1} of {questions.length}
                </div>
                {isFillBlank ? (
                  <h3 className="text-base sm:text-lg font-medium leading-relaxed text-slate-900">
                    {currentQuestion.text.split(/_{3,}/).map((chunk, cIdx, arr) => (
                      <span key={cIdx}>
                        {chunk}
                        {cIdx < arr.length - 1 && (
                          <span className="inline-flex items-center px-2 py-0.5 rounded-md bg-purple-50 text-purple-700 border border-purple-200 font-mono text-xs font-bold mx-1 shadow-2xs">
                            [ Blank #{cIdx + 1} ]
                          </span>
                        )}
                      </span>
                    ))}
                  </h3>
                ) : (
                  <h3 className="text-base sm:text-lg font-medium leading-relaxed text-slate-900">
                    {currentQuestion.text}
                  </h3>
                )}
              </div>

              {/* Type-Specific Answer Inputs */}

              {/* 1. MCQ Option Cards */}
              {isMcq && currentOptions.length > 0 && (
                <div className="space-y-3">
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
              )}

              {/* 2. True / False Choice Cards */}
              {isTrueFalse && (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  {["True", "False"].map((tf) => {
                    const isSelected = (answers[currentQuestion.id] ?? "").toLowerCase() === tf.toLowerCase();
                    return (
                      <button
                        key={tf}
                        type="button"
                        onClick={() => setAnswer(currentQuestion.id, tf)}
                        className={`flex items-center justify-center gap-3 p-5 rounded-2xl border-2 text-base font-bold transition-all ${
                          isSelected
                            ? "border-amber-600 bg-amber-50 text-amber-900 ring-2 ring-amber-500 shadow-xs"
                            : "border-slate-200 bg-white text-slate-700 hover:border-slate-300 hover:bg-slate-50"
                        }`}
                      >
                        <span className={`h-4 w-4 rounded-full border-2 flex items-center justify-center ${isSelected ? "border-amber-600" : "border-slate-300"}`}>
                          {isSelected && <span className="h-2 w-2 rounded-full bg-amber-600" />}
                        </span>
                        <span>{tf}</span>
                      </button>
                    );
                  })}
                </div>
              )}

              {/* 3. Fill in the Blanks Dedicated Inputs */}
              {isFillBlank && (
                <div className="space-y-4">
                  <div className="flex items-center justify-between text-xs font-semibold text-slate-500 border-b border-slate-100 pb-2">
                    <span>Fill in the {totalBlanks} blank{totalBlanks > 1 ? "s" : ""}:</span>
                    <span>
                      {currentBlanks.filter((b) => Boolean(b && b.trim())).length} of {totalBlanks} filled
                    </span>
                  </div>
                  <div className="space-y-3">
                    {Array.from({ length: totalBlanks }).map((_, bIdx) => (
                      <div key={bIdx} className="flex items-center gap-3 p-3 rounded-xl border border-slate-200 bg-slate-50/40 focus-within:border-purple-500 focus-within:bg-white focus-within:ring-2 focus-within:ring-purple-500/20 transition-all">
                        <span className="flex items-center justify-center px-3 py-1 rounded-lg bg-purple-100 text-purple-800 font-bold text-xs shrink-0 font-mono">
                          Blank #{bIdx + 1}
                        </span>
                        <input
                          type="text"
                          value={currentBlanks[bIdx] || ""}
                          onChange={(e) => setBlankValue(currentQuestion.id, bIdx, e.target.value, totalBlanks)}
                          placeholder={`Enter answer for Blank #${bIdx + 1}...`}
                          className="w-full bg-transparent text-sm text-slate-900 focus:outline-hidden"
                        />
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* 4. Short / Long Answer / Subjective Textarea with Word Limits */}
              {isSubjective && (
                <div className="space-y-2">
                  <textarea
                    rows={qType === "short_answer" ? 6 : 10}
                    value={textAnswer}
                    onChange={(e) => setAnswer(currentQuestion.id, e.target.value)}
                    placeholder={
                      qType === "short_answer"
                        ? "Write a concise response (bullet points or brief paragraph)..."
                        : "Write your complete, structured response here..."
                    }
                    className={`w-full rounded-xl border p-4 text-sm text-slate-900 placeholder-slate-400 focus:bg-white focus:outline-hidden focus:ring-2 transition-all resize-y ${
                      wordLimitExceeded
                        ? "border-rose-400 bg-rose-50/20 focus:ring-rose-500/20 focus:border-rose-500"
                        : "border-slate-200 bg-slate-50/50 focus:border-blue-500 focus:ring-blue-500/20"
                    }`}
                  />
                  <div className="flex items-center justify-between text-xs text-slate-500">
                    <div className="flex items-center gap-2">
                      <span>{textAnswer.length} characters</span>
                      <span>·</span>
                      <span className={wordLimitExceeded ? "text-rose-600 font-bold" : ""}>
                        {wordCount} words
                      </span>
                      {currentQuestion.word_limit && (
                        <span className={`px-2 py-0.5 rounded-full text-[11px] font-semibold ${
                          wordLimitExceeded
                            ? "bg-rose-100 text-rose-700 border border-rose-200"
                            : "bg-slate-100 text-slate-600"
                        }`}>
                          Limit: {currentQuestion.word_limit} words
                          {wordLimitExceeded && " (Exceeded)"}
                        </span>
                      )}
                    </div>
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

                {hasAnsweredCurrent && (
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
          );
        })()}
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
                  <strong className="text-slate-800">Strict Warning Limit:</strong>{" "}
                  {maxWarnings === 1 ? (
                    <>
                      <span className="font-bold text-rose-600">1 warning, then automatic submission</span>. Any further violation beyond 1 warning will immediately and permanently auto-submit your exam.
                    </>
                  ) : (
                    <>
                      You have a maximum of{" "}
                      <span className="font-bold text-rose-600">{maxWarnings} warnings</span>. The{" "}
                      {maxWarnings + 1}th violation will immediately and permanently auto-submit your exam.
                    </>
                  )}
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
                  {violationModal.maxWarnings === 1
                    ? "Final Warning"
                    : `Warning ${violationModal.violationCount} of ${violationModal.maxWarnings}`}
                </p>
              </div>
            </div>

            <div className="mt-4 rounded-xl bg-rose-50/60 p-4 text-xs sm:text-sm text-slate-700">
              <p className="font-semibold text-slate-900">
                {violationModal.violationCount === 1
                  ? "Final warning: you left the exam screen. Another violation will submit your exam automatically."
                  : violationModal.message}
              </p>
              {!violationModal.autoSubmitted && violationModal.maxWarnings > 1 && (
                <p className="mt-2 font-semibold text-rose-700">
                  {violationModal.violationCount >= violationModal.maxWarnings
                    ? "⚠️ FINAL WARNING: Any further violation will automatically submit your exam immediately."
                    : `⚠️ Warning ${violationModal.violationCount} of ${violationModal.maxWarnings}. Any further violation beyond ${violationModal.maxWarnings} warnings will automatically submit your exam.`}
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
                {violationModal.autoSubmitted ? "View Results" : "Return to fullscreen"}
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

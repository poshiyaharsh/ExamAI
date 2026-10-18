import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  AlertCircle,
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  Clock,
  Cpu,
  FileCheck2,
  HelpCircle,
  Loader2,
  PlusCircle,
  RefreshCw,
  X,
  XCircle,
} from "lucide-react";
import { toast } from "sonner";
import { generationApi, type PaperGenerationJob } from "../../services/api";

interface GenerationProgressModalProps {
  jobId: number | null;
  isOpen: boolean;
  onClose: () => void;
  onSuccess?: (job: PaperGenerationJob) => void;
  onReset?: () => void;
  onChangeModel?: () => void;
}

export const GenerationProgressModal: React.FC<GenerationProgressModalProps> = ({
  jobId,
  isOpen,
  onClose,
  onSuccess,
  onReset,
  onChangeModel,
}) => {
  const navigate = useNavigate();
  const [job, setJob] = useState<PaperGenerationJob | null>(null);
  const [cancelling, setCancelling] = useState(false);
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    if (!isOpen || !jobId) return;

    let cancelled = false;
    let timer: number | undefined;

    // Local elapsed ticker
    const interval = window.setInterval(() => {
      setElapsed((prev) => prev + 1);
    }, 1000);

    const poll = async () => {
      try {
        const data = await generationApi.getJob(jobId);
        if (cancelled) return;
        setJob(data);
        if (data.elapsed_seconds) {
          setElapsed(data.elapsed_seconds);
        }

        if (data.status === "completed" || data.status === "completed_with_warnings") {
          toast.success("Paper generated successfully!");
          onSuccess?.(data);
          return; // stop polling
        }

        if (data.status === "failed") {
          toast.error(data.error_message || "Generation failed.");
          return; // stop polling
        }

        if (data.status === "cancelled") {
          return;
        }

        // Keep polling every 2.5 seconds
        timer = window.setTimeout(poll, 2500);
      } catch (err: any) {
        if (!cancelled) {
          console.error("Poll error:", err);
          timer = window.setTimeout(poll, 4000);
        }
      }
    };

    void poll();

    return () => {
      cancelled = true;
      clearInterval(interval);
      if (timer) clearTimeout(timer);
    };
  }, [jobId, isOpen, onSuccess]);

  if (!isOpen) return null;

  const handleCancel = async () => {
    if (!jobId || cancelling) return;
    setCancelling(true);
    try {
      const res = await generationApi.cancelJob(jobId);
      setJob(res.job);
      toast.info("Generation cancelled.");
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || "Could not cancel generation.");
    } finally {
      setCancelling(false);
    }
  };

  const formatSeconds = (sec: number) => {
    const m = Math.floor(sec / 60);
    const s = sec % 60;
    return m > 0 ? `${m}m ${s < 10 ? "0" : ""}${s}s` : `${s}s`;
  };

  const isFinished = job?.status === "completed" || job?.status === "completed_with_warnings";
  const isFailed = job?.status === "failed";
  const isCancelled = job?.status === "cancelled";
  const isRunning = !isFinished && !isFailed && !isCancelled;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4 animate-in fade-in duration-200">
      <div className="bg-white rounded-2xl border border-slate-200 shadow-2xl w-full max-w-lg overflow-hidden animate-in zoom-in-95 duration-200">
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between bg-slate-50/60">
          <div className="flex items-center gap-2.5">
            <div className={`p-2 rounded-xl ${isFinished ? "bg-emerald-50 text-emerald-600" : isFailed ? "bg-rose-50 text-rose-600" : "bg-blue-50 text-blue-600"}`}>
              {isFinished ? (
                <CheckCircle2 className="h-5 w-5" />
              ) : isFailed ? (
                <XCircle className="h-5 w-5" />
              ) : (
                <Cpu className="h-5 w-5 animate-pulse" />
              )}
            </div>
            <div>
              <h3 className="font-bold text-slate-900 text-sm sm:text-base">
                {isFinished
                  ? "Paper Generated Successfully"
                  : isFailed
                  ? "Generation Failed"
                  : isCancelled
                  ? "Generation Cancelled"
                  : "Generating Exam Paper"}
              </h3>
              <p className="text-xs text-slate-500">
                {isRunning ? "Server is synthesizing questions with Ollama" : "Status confirmed by server"}
              </p>
            </div>
          </div>
          {(isFinished || isFailed || isCancelled) && (
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg p-1.5 text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-colors"
            >
              <X className="h-5 w-5" />
            </button>
          )}
        </div>

        {/* Body */}
        <div className="p-6 space-y-5">
          {/* Running State */}
          {isRunning && (
            <div className="space-y-4">
              {/* Progress Bar */}
              <div>
                <div className="flex justify-between text-xs font-semibold text-slate-600 mb-1.5">
                  <span className="truncate pr-2">{job?.current_step || "Initializing..."}</span>
                  <span className="text-blue-600 font-bold">{job?.progress || 10}%</span>
                </div>
                <div className="w-full bg-slate-100 rounded-full h-3 overflow-hidden p-0.5 border border-slate-200/60">
                  <div
                    className="bg-gradient-to-r from-blue-600 to-indigo-600 h-full rounded-full transition-all duration-500 ease-out shadow-xs"
                    style={{ width: `${Math.max(job?.progress || 10, 8)}%` }}
                  />
                </div>
              </div>

              {/* Step indicator pipeline */}
              <div className="grid grid-cols-4 gap-1.5 text-center pt-2">
                {[
                  { label: "Syllabus", active: (job?.progress || 0) >= 10 },
                  { label: "AI Contact", active: (job?.progress || 0) >= 25 },
                  { label: "Synthesis", active: (job?.progress || 0) >= 50 },
                  { label: "Validation", active: (job?.progress || 0) >= 85 },
                ].map((s, idx) => (
                  <div
                    key={idx}
                    className={`rounded-lg py-1.5 px-1 text-[11px] font-semibold border transition-all ${
                      s.active
                        ? "bg-blue-50/70 border-blue-200 text-blue-700 font-bold"
                        : "bg-slate-50 border-slate-200 text-slate-400"
                    }`}
                  >
                    {s.label}
                  </div>
                ))}
              </div>

              {/* Time and Info */}
              <div className="rounded-xl bg-blue-50/60 border border-blue-100 p-3.5 space-y-2">
                <div className="flex items-center justify-between text-xs text-blue-900 font-medium">
                  <span className="flex items-center gap-1.5">
                    <Clock className="h-4 w-4 text-blue-600" /> Elapsed Time:
                  </span>
                  <span className="font-mono font-bold">{formatSeconds(elapsed)}</span>
                </div>
                {job?.model && (
                  <div className="flex items-center justify-between text-xs text-blue-900 font-medium">
                    <span className="flex items-center gap-1.5">
                      <Cpu className="h-4 w-4 text-blue-600" /> Model:
                    </span>
                    <span className="font-mono text-[11px] bg-white px-2 py-0.5 rounded-md border border-blue-200">
                      {job.model}
                    </span>
                  </div>
                )}
                <p className="text-[11px] text-blue-700 leading-relaxed pt-1 border-t border-blue-100">
                  Local AI models take 20–60 seconds to synthesize questions. You can freely leave this tab; the server continues working in the background.
                </p>
              </div>

              {/* Cancel Button */}
              <div className="pt-2 flex justify-end">
                <button
                  type="button"
                  disabled={cancelling}
                  onClick={handleCancel}
                  className="inline-flex items-center gap-1.5 rounded-xl border border-rose-200 bg-rose-50 px-4 py-2 text-xs font-semibold text-rose-700 hover:bg-rose-100 disabled:opacity-50 transition-colors"
                >
                  {cancelling ? (
                    <>
                      <Loader2 className="h-3.5 w-3.5 animate-spin" /> Cancelling...
                    </>
                  ) : (
                    <>
                      <X className="h-3.5 w-3.5" /> Cancel Generation
                    </>
                  )}
                </button>
              </div>
            </div>
          )}

          {/* Success State */}
          {isFinished && (
            <div className="space-y-4">
              <div className="rounded-2xl bg-emerald-50/80 border border-emerald-200 p-4 space-y-3">
                <div className="flex items-center gap-3">
                  <div className="h-10 w-10 rounded-xl bg-emerald-500 text-white flex items-center justify-center shrink-0 shadow-sm">
                    <FileCheck2 className="h-6 w-6" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <h4 className="font-bold text-emerald-950 text-sm truncate">{job?.exam_title || "Draft Paper Ready"}</h4>
                    <p className="text-xs text-emerald-700">Created as a draft paper. Review required before publishing.</p>
                  </div>
                </div>

                <div className="grid grid-cols-3 gap-2 pt-2 border-t border-emerald-200/60 text-center">
                  <div className="bg-white/80 rounded-lg p-2 border border-emerald-100">
                    <div className="text-[10px] uppercase font-semibold text-slate-500">Questions</div>
                    <div className="text-sm font-bold text-slate-900">{job?.question_count_generated || 0}</div>
                  </div>
                  <div className="bg-white/80 rounded-lg p-2 border border-emerald-100">
                    <div className="text-[10px] uppercase font-semibold text-slate-500">Duration</div>
                    <div className="text-sm font-bold text-slate-900">{formatSeconds(job?.elapsed_seconds || elapsed)}</div>
                  </div>
                  <div className="bg-white/80 rounded-lg p-2 border border-emerald-100">
                    <div className="text-[10px] uppercase font-semibold text-slate-500">Model</div>
                    <div className="text-xs font-bold text-slate-900 truncate">{job?.model || "AI"}</div>
                  </div>
                </div>
              </div>

              {/* Warnings if any */}
              {job?.warnings && job.warnings.length > 0 && (
                <div className="rounded-xl bg-amber-50 border border-amber-200 p-3 space-y-1 text-xs text-amber-800">
                  <div className="font-semibold flex items-center gap-1.5 text-amber-900">
                    <AlertTriangle className="h-4 w-4 shrink-0 text-amber-600" /> Generation Notices
                  </div>
                  <ul className="list-disc list-inside space-y-0.5 text-[11px] text-amber-700">
                    {job.warnings.map((w, i) => (
                      <li key={i}>{w}</li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Primary Actions */}
              <div className="flex flex-col sm:flex-row gap-2 pt-2">
                {job?.exam_id && (
                  <button
                    type="button"
                    onClick={() => {
                      onClose();
                      navigate(`/faculty/exams/${job.exam_id}/edit`);
                    }}
                    className="flex-1 inline-flex items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-blue-600 to-indigo-600 px-4 py-2.5 text-sm font-bold text-white shadow-md hover:opacity-95 transition-all"
                  >
                    Review & Edit Paper <ArrowRight className="h-4 w-4" />
                  </button>
                )}
                <button
                  type="button"
                  onClick={() => {
                    onClose();
                    onReset?.();
                  }}
                  className="inline-flex items-center justify-center gap-1.5 rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-xs font-semibold text-slate-700 hover:bg-slate-50 transition-colors"
                >
                  <PlusCircle className="h-4 w-4" /> Generate Another
                </button>
                <button
                  type="button"
                  onClick={() => {
                    onClose();
                    navigate("/faculty/history");
                  }}
                  className="inline-flex items-center justify-center gap-1.5 rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-xs font-semibold text-slate-700 hover:bg-slate-50 transition-colors"
                >
                  My Papers
                </button>
              </div>
            </div>
          )}

          {/* Failure State */}
          {isFailed && (
            <div className="space-y-4">
              <div className="rounded-xl bg-rose-50 border border-rose-200 p-4 space-y-2">
                <div className="flex items-center gap-2 text-rose-800 font-semibold text-sm">
                  <AlertCircle className="h-5 w-5 text-rose-600 shrink-0" />
                  Unable to complete paper generation
                </div>
                <p className="text-xs text-rose-700 leading-relaxed">
                  {job?.error_message || "The model was unable to generate questions from the syllabus."}
                </p>
                <p className="text-[11px] text-slate-500 pt-1">
                  Next Step: Check that local Ollama is active or select a lighter model like Phi-3 Mini.
                </p>
              </div>

              <div className="flex flex-wrap gap-2 pt-2 justify-end">
                {onChangeModel && (
                  <button
                    type="button"
                    onClick={() => {
                      onClose();
                      onChangeModel();
                    }}
                    className="inline-flex items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-4 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50"
                  >
                    Change Model
                  </button>
                )}
                <button
                  type="button"
                  onClick={() => {
                    onClose();
                    onReset?.();
                  }}
                  className="inline-flex items-center gap-1.5 rounded-xl bg-blue-600 px-4 py-2 text-xs font-bold text-white shadow-sm hover:bg-blue-700"
                >
                  <RefreshCw className="h-3.5 w-3.5" /> Try Again
                </button>
              </div>
            </div>
          )}

          {/* Cancelled State */}
          {isCancelled && (
            <div className="space-y-4 text-center py-2">
              <p className="text-xs text-slate-600">Generation was cancelled. No draft paper was saved.</p>
              <button
                type="button"
                onClick={onClose}
                className="inline-flex items-center gap-1.5 rounded-xl bg-slate-800 px-4 py-2 text-xs font-semibold text-white hover:bg-slate-900"
              >
                Close
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

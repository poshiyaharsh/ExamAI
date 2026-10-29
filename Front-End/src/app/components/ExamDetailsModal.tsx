import React from "react";
import { Link } from "react-router-dom";
import {
  X,
  Calendar,
  Clock,
  Award,
  BookOpen,
  Shuffle,
  ShieldAlert,
  Edit3,
  FileText,
  BarChart2,
  Users,
  CheckCircle,
  AlertTriangle,
} from "lucide-react";
import { type FacultyOngoingExamItem } from "../../services/api";

interface ExamDetailsModalProps {
  exam: FacultyOngoingExamItem | null;
  isOpen: boolean;
  onClose: () => void;
}

export function ExamDetailsModal({ exam, isOpen, onClose }: ExamDetailsModalProps) {
  React.useEffect(() => {
    if (!isOpen) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen || !exam) return null;

  const topicsList = exam.all_topics || exam.topics || [];
  const isEditable = false; // Live/published exams are immutable

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-xs animate-in fade-in-0"
      role="dialog"
      aria-modal="true"
      aria-labelledby="exam-details-title"
      onClick={(e) => {
        if (e.target === e.currentTarget) {
          onClose();
        }
      }}
    >
      <div className="bg-card w-full max-w-2xl rounded-2xl border border-border shadow-xl overflow-hidden flex flex-col max-h-[90vh]">
        {/* Modal Header */}
        <div className="p-5 border-b border-border flex items-start justify-between gap-4 bg-muted/20">
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2 mb-1.5 flex-wrap">
              <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-primary/10 text-primary border border-primary/20">
                {exam.department || "All Departments"}
              </span>
              <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-800 border border-emerald-300 flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-600 animate-pulse" />
                Live Exam
              </span>
            </div>
            <h3 id="exam-details-title" className="text-lg font-bold text-foreground">
              {exam.title}
            </h3>
            <p className="text-xs text-muted-foreground mt-0.5 font-medium">
              Subject: <strong className="text-foreground">{exam.subject}</strong>
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
            aria-label="Close dialog"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Modal Content (Scrollable) */}
        <div className="p-5 overflow-y-auto space-y-5 text-xs sm:text-sm">
          {/* 3 KPI Grid */}
          <div className="grid grid-cols-3 gap-3">
            <div className="bg-muted/40 p-3 rounded-xl border border-border/50 text-center">
              <p className="text-[11px] text-muted-foreground font-medium uppercase tracking-wider">Duration</p>
              <p className="text-base font-bold text-foreground mt-0.5">{exam.duration_minutes} mins</p>
            </div>
            <div className="bg-muted/40 p-3 rounded-xl border border-border/50 text-center">
              <p className="text-[11px] text-muted-foreground font-medium uppercase tracking-wider">Total Marks</p>
              <p className="text-base font-bold text-primary mt-0.5">{exam.total_marks} pts</p>
            </div>
            <div className="bg-muted/40 p-3 rounded-xl border border-border/50 text-center">
              <p className="text-[11px] text-muted-foreground font-medium uppercase tracking-wider">Passing Mark</p>
              <p className="text-base font-bold text-emerald-600 mt-0.5">40% ({Math.round(exam.total_marks * 0.4)} pts)</p>
            </div>
          </div>

          {/* Schedule & Window */}
          <div className="bg-card p-4 rounded-xl border border-border space-y-2.5">
            <h4 className="font-semibold text-foreground text-xs uppercase tracking-wider flex items-center gap-1.5">
              <Calendar className="w-3.5 h-3.5 text-primary" /> Schedule & Testing Window
            </h4>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs">
              <div className="flex justify-between py-1 border-b border-border/40">
                <span className="text-muted-foreground">Start Time:</span>
                <span className="font-medium text-foreground">
                  {exam.starts_at ? new Date(exam.starts_at).toLocaleString() : "Open schedule (Always available)"}
                </span>
              </div>
              <div className="flex justify-between py-1 border-b border-border/40">
                <span className="text-muted-foreground">End Time:</span>
                <span className="font-medium text-foreground">
                  {exam.ends_at ? new Date(exam.ends_at).toLocaleString() : "No closing deadline"}
                </span>
              </div>
              <div className="flex justify-between py-1 border-b border-border/40">
                <span className="text-muted-foreground">Department:</span>
                <span className="font-medium text-foreground">{exam.department}</span>
              </div>
              <div className="flex justify-between py-1 border-b border-border/40">
                <span className="text-muted-foreground">Questions Count:</span>
                <span className="font-medium text-foreground">{exam.question_count || "Configured in paper"}</span>
              </div>
            </div>
          </div>

          {/* Topics Covered */}
          <div className="bg-card p-4 rounded-xl border border-border space-y-2.5">
            <h4 className="font-semibold text-foreground text-xs uppercase tracking-wider flex items-center gap-1.5">
              <BookOpen className="w-3.5 h-3.5 text-primary" /> Topics Covered ({topicsList.length})
            </h4>
            {topicsList.length === 0 ? (
              <p className="text-xs text-muted-foreground">General subject coverage</p>
            ) : (
              <div className="flex flex-wrap gap-1.5 max-h-32 overflow-y-auto pr-1">
                {topicsList.map((topic, i) => (
                  <span
                    key={i}
                    className="px-2.5 py-1 bg-muted/60 text-foreground text-xs rounded-lg border border-border/60"
                  >
                    {topic}
                  </span>
                ))}
              </div>
            )}
          </div>

          {/* Proctoring & Security Settings */}
          <div className="bg-card p-4 rounded-xl border border-border space-y-2.5">
            <h4 className="font-semibold text-foreground text-xs uppercase tracking-wider flex items-center gap-1.5">
              <ShieldAlert className="w-3.5 h-3.5 text-primary" /> Proctoring & Security Rules
            </h4>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs">
              <div className="flex items-center gap-2 p-2 rounded-lg bg-muted/20 border border-border/30">
                <CheckCircle className="w-4 h-4 text-emerald-600 shrink-0" />
                <span>Fullscreen enforcement & Tab switch tracking</span>
              </div>
              <div className="flex items-center gap-2 p-2 rounded-lg bg-muted/20 border border-border/30">
                <Shuffle className="w-4 h-4 text-primary shrink-0" />
                <span>Questions & Options randomized per student</span>
              </div>
              <div className="flex items-center gap-2 p-2 rounded-lg bg-muted/20 border border-border/30 sm:col-span-2">
                <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0" />
                <span>
                  {exam.max_warnings === 1
                    ? "1 warning allowed, automatic submission on next violation"
                    : `${exam.max_warnings ?? 1} warnings allowed before auto-submit`}
                </span>
              </div>
            </div>
          </div>

          {/* Participation Summary */}
          <div className="bg-muted/30 p-4 rounded-xl border border-border space-y-2">
            <h4 className="font-semibold text-foreground text-xs uppercase tracking-wider flex items-center gap-1.5">
              <Users className="w-3.5 h-3.5 text-primary" /> Live Participation Summary
            </h4>
            <div className="grid grid-cols-4 gap-2 text-center text-xs">
              <div className="p-2 bg-card rounded-lg border border-border/40">
                <p className="text-[10px] text-muted-foreground uppercase font-medium">Assigned</p>
                <p className="text-sm font-bold text-foreground mt-0.5">{exam.assigned_total || exam.eligible_students || 0}</p>
              </div>
              <div className="p-2 bg-card rounded-lg border border-border/40">
                <p className="text-[10px] text-muted-foreground uppercase font-medium">In Progress</p>
                <p className="text-sm font-bold text-blue-600 mt-0.5">{exam.in_progress_count || 0}</p>
              </div>
              <div className="p-2 bg-card rounded-lg border border-border/40">
                <p className="text-[10px] text-muted-foreground uppercase font-medium">Submitted</p>
                <p className="text-sm font-bold text-emerald-600 mt-0.5">{exam.submitted_count || 0}</p>
              </div>
              <div className="p-2 bg-card rounded-lg border border-border/40">
                <p className="text-[10px] text-muted-foreground uppercase font-medium">Flagged</p>
                <p className="text-sm font-bold text-rose-600 mt-0.5">{exam.flagged_students || 0}</p>
              </div>
            </div>
          </div>
        </div>

        {/* Modal Footer */}
        <div className="p-4 border-t border-border bg-muted/10 flex items-center justify-between gap-3">
          <Link
            to={`/faculty/exams/${exam.id}/monitor`}
            className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-primary text-white text-xs font-semibold hover:opacity-90 transition-opacity"
            onClick={onClose}
          >
            <BarChart2 className="w-3.5 h-3.5" />
            Open Live Monitor
          </Link>

          <div className="flex items-center gap-2">
            <Link
              to="/faculty/history"
              className="px-3.5 py-2 rounded-lg border border-border text-foreground hover:bg-muted text-xs font-medium transition-colors"
              onClick={onClose}
            >
              Attempts & Results
            </Link>
            <button
              onClick={onClose}
              className="px-4 py-2 rounded-lg bg-muted text-foreground hover:bg-muted/80 text-xs font-medium transition-colors"
            >
              Close
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

import { useEffect, useMemo, useState } from "react";
import {
  ArrowRight,
  Award,
  BookOpen,
  Calendar,
  CheckCircle2,
  Clock,
  FileText,
  HelpCircle,
  LayoutDashboard,
  Lock,
  Search,
  Settings,
  Shield,
  TrendingUp,
  X,
} from "lucide-react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { DashboardLayout } from "../components/DashboardLayout";
import { studentExamApi, type StudentExam, type StudentExamSummary } from "../../services/api";

const menuItems = [
  { icon: LayoutDashboard, label: "Dashboard", path: "/student" },
  { icon: FileText, label: "Exams", path: "/student/exams" },
  { icon: TrendingUp, label: "Performance", path: "/student/performance" },
  { icon: Settings, label: "Settings", path: "/student/settings" },
];

function formatWindow(exam: StudentExam) {
  const now = new Date();
  if (exam.ends_at && new Date(exam.ends_at) < now) {
    return "Window closed";
  }
  if (exam.starts_at && new Date(exam.starts_at) > now) {
    return `Opens ${new Date(exam.starts_at).toLocaleDateString([], {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    })}`;
  }
  if (exam.ends_at) {
    return `Closes ${new Date(exam.ends_at).toLocaleDateString([], {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    })}`;
  }
  return "Open now";
}

export function StudentExamsPage() {
  const navigate = useNavigate();
  const [exams, setExams] = useState<StudentExamSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState("");
  const [statusFilter, setStatusFilter] = useState<"all" | "ready" | "completed">("all");
  const [selectedExamTopics, setSelectedExamTopics] = useState<StudentExam | null>(null);

  useEffect(() => {
    studentExamApi
      .getExams()
      .then(setExams)
      .catch(() => toast.error("Unable to load exams."))
      .finally(() => setLoading(false));
  }, []);

  const filteredExams = useMemo(() => {
    return exams.filter(({ exam, completed, available }) => {
      if (statusFilter === "ready" && (!available || completed)) return false;
      if (statusFilter === "completed" && !completed) return false;

      if (searchTerm.trim()) {
        const q = searchTerm.toLowerCase();
        const titleMatch = exam.title.toLowerCase().includes(q);
        const subjectMatch = exam.subject?.toLowerCase().includes(q) ?? false;
        const topicMatch = exam.topics.some((t) => t.toLowerCase().includes(q));
        if (!titleMatch && !subjectMatch && !topicMatch) return false;
      }
      return true;
    });
  }, [exams, statusFilter, searchTerm]);

  return (
    <DashboardLayout menuItems={menuItems} userRole="Student">
      <div className="space-y-6 max-w-7xl mx-auto pb-12">
        {/* Header Section */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl sm:text-3xl font-bold text-foreground tracking-tight">Available Exams</h1>
            <p className="text-xs sm:text-sm text-muted-foreground mt-0.5">
              Access scheduled assessments, review course topics, and launch live exams during active windows.
            </p>
          </div>

          {/* Quick Filters & Search */}
          <div className="flex flex-wrap items-center gap-2.5">
            <div className="relative">
              <Search className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
              <input
                type="text"
                placeholder="Search exams or topics..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="pl-9 pr-4 py-2 rounded-xl border border-border bg-white text-xs sm:text-sm focus:outline-hidden focus:ring-2 focus:ring-primary/20 focus:border-primary transition-all w-52 sm:w-64"
              />
            </div>

            <div className="flex items-center rounded-xl bg-slate-100 p-1 text-xs font-semibold">
              <button
                type="button"
                onClick={() => setStatusFilter("all")}
                className={`px-3 py-1.5 rounded-lg transition-all ${
                  statusFilter === "all" ? "bg-white text-primary shadow-xs font-bold" : "text-slate-600 hover:text-slate-900"
                }`}
              >
                All ({exams.length})
              </button>
              <button
                type="button"
                onClick={() => setStatusFilter("ready")}
                className={`px-3 py-1.5 rounded-lg transition-all ${
                  statusFilter === "ready" ? "bg-white text-primary shadow-xs font-bold" : "text-slate-600 hover:text-slate-900"
                }`}
              >
                Ready
              </button>
              <button
                type="button"
                onClick={() => setStatusFilter("completed")}
                className={`px-3 py-1.5 rounded-lg transition-all ${
                  statusFilter === "completed" ? "bg-white text-primary shadow-xs font-bold" : "text-slate-600 hover:text-slate-900"
                }`}
              >
                Completed
              </button>
            </div>
          </div>
        </div>

        {/* Loading State */}
        {loading ? (
          <div className="grid gap-5 md:grid-cols-2">
            {[1, 2, 3, 4].map((n) => (
              <div key={n} className="rounded-2xl border border-border bg-white p-6 shadow-xs animate-pulse space-y-4">
                <div className="h-4 bg-slate-200 rounded w-1/3" />
                <div className="h-6 bg-slate-200 rounded w-3/4" />
                <div className="h-16 bg-slate-100 rounded-xl" />
              </div>
            ))}
          </div>
        ) : filteredExams.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-border bg-white p-12 text-center shadow-xs space-y-3">
            <BookOpen className="w-12 h-12 text-muted-foreground/40 mx-auto" />
            <h3 className="text-base font-bold text-foreground">No matching exams found</h3>
            <p className="text-xs sm:text-sm text-muted-foreground max-w-md mx-auto">
              {searchTerm || statusFilter !== "all"
                ? "Try clearing your search query or switching filter tabs."
                : "No assessments are currently scheduled for your department. Check back later."}
            </p>
          </div>
        ) : (
          /* Cards Grid */
          <div className="grid gap-5 md:grid-cols-2">
            {filteredExams.map(({ exam, completed, attempt_id: attemptId, available }) => {
              const questionCount = exam.question_count || exam.questions?.length || 0;
              const hasMoreTopics = exam.topics && exam.topics.length > 3;

              return (
                <article
                  key={exam.id}
                  className="group rounded-2xl border border-border bg-white p-5 sm:p-6 shadow-xs hover:shadow-md transition-all flex flex-col justify-between space-y-5"
                >
                  <div className="space-y-3">
                    {/* Top Badges Row */}
                    <div className="flex items-center justify-between gap-2 flex-wrap">
                      <div className="flex items-center gap-1.5 flex-wrap">
                        {exam.subject && (
                          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-bold bg-blue-50 text-blue-700 border border-blue-200">
                            {exam.subject}
                          </span>
                        )}
                        {exam.department && (
                          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-slate-100 text-slate-700 border border-slate-200">
                            {exam.department}
                          </span>
                        )}
                      </div>

                      {/* Status Badge */}
                      <span
                        className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-bold border ${
                          completed
                            ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                            : available
                            ? "bg-sky-50 text-sky-700 border-sky-200 animate-pulse"
                            : "bg-slate-100 text-slate-600 border-slate-200"
                        }`}
                      >
                        {completed ? (
                          <>
                            <CheckCircle2 className="h-3 w-3" /> Completed
                          </>
                        ) : available ? (
                          <>
                            <Shield className="h-3 w-3 text-sky-600" /> Ready to Start
                          </>
                        ) : (
                          <>
                            <Lock className="h-3 w-3" /> Scheduled
                          </>
                        )}
                      </span>
                    </div>

                    {/* Title */}
                    <div>
                      <h2 className="text-base sm:text-lg font-bold text-foreground leading-snug group-hover:text-primary transition-colors">
                        {exam.title}
                      </h2>
                    </div>

                    {/* Clean Topics Chips (Max 3 + More button) */}
                    {Array.isArray(exam.topics) && exam.topics.length > 0 && (
                      <div className="flex flex-wrap items-center gap-1.5 pt-0.5">
                        {exam.topics.slice(0, 3).map((topic, tIdx) => (
                          <span
                            key={tIdx}
                            className="inline-block px-2.5 py-0.5 rounded-lg bg-slate-50 border border-slate-200 text-[11px] font-medium text-slate-700 max-w-[160px] truncate"
                            title={topic}
                          >
                            {topic}
                          </span>
                        ))}
                        {hasMoreTopics && (
                          <button
                            type="button"
                            onClick={() => setSelectedExamTopics(exam)}
                            className="text-[11px] font-bold text-primary hover:underline px-1 py-0.5 transition-colors"
                          >
                            +{exam.topics.length - 3} more
                          </button>
                        )}
                      </div>
                    )}

                    {/* Exam Specs Grid */}
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 pt-2 text-xs">
                      <div className="rounded-xl bg-slate-50 border border-slate-100 p-2.5">
                        <span className="text-[10px] text-muted-foreground block font-medium">Duration</span>
                        <span className="font-bold text-foreground flex items-center gap-1 mt-0.5">
                          <Clock className="w-3.5 h-3.5 text-blue-500" />
                          {exam.duration_minutes}m
                        </span>
                      </div>
                      <div className="rounded-xl bg-slate-50 border border-slate-100 p-2.5">
                        <span className="text-[10px] text-muted-foreground block font-medium">Total Marks</span>
                        <span className="font-bold text-foreground flex items-center gap-1 mt-0.5">
                          <Award className="w-3.5 h-3.5 text-amber-500" />
                          {exam.total_marks} pts
                        </span>
                      </div>
                      <div className="rounded-xl bg-slate-50 border border-slate-100 p-2.5">
                        <span className="text-[10px] text-muted-foreground block font-medium">Questions</span>
                        <span className="font-bold text-foreground flex items-center gap-1 mt-0.5">
                          <HelpCircle className="w-3.5 h-3.5 text-purple-500" />
                          {questionCount}
                        </span>
                      </div>
                      <div className="rounded-xl bg-slate-50 border border-slate-100 p-2.5">
                        <span className="text-[10px] text-muted-foreground block font-medium">Schedule</span>
                        <span className="font-bold text-foreground flex items-center gap-1 mt-0.5 truncate" title={formatWindow(exam)}>
                          <Calendar className="w-3.5 h-3.5 text-emerald-500 shrink-0" />
                          <span className="truncate">{formatWindow(exam)}</span>
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Footer & Action Button */}
                  <div className="flex items-center justify-between gap-3 pt-3 border-t border-border/60">
                    <span className="text-xs text-muted-foreground">
                      {completed
                        ? "Exam submitted & evaluated."
                        : available
                        ? "Exam is currently open for submission."
                        : "Assessment not currently unlocked."}
                    </span>

                    {completed && attemptId ? (
                      <button
                        type="button"
                        onClick={() => navigate(`/student/results/${attemptId}`)}
                        className="inline-flex items-center gap-1.5 rounded-xl border border-border bg-white px-4 py-2 text-xs font-bold text-foreground hover:bg-slate-50 transition-all shadow-2xs"
                      >
                        <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600" />
                        View Result
                      </button>
                    ) : (
                      <button
                        type="button"
                        disabled={!available}
                        onClick={() => navigate(`/student/exams/${exam.id}/take`)}
                        className="inline-flex items-center gap-1.5 rounded-xl bg-gradient-to-r from-primary to-secondary px-5 py-2 text-xs font-bold text-white shadow-sm hover:opacity-95 transition-all disabled:cursor-not-allowed disabled:opacity-40"
                      >
                        Start Exam <ArrowRight className="h-3.5 w-3.5" />
                      </button>
                    )}
                  </div>
                </article>
              );
            })}
          </div>
        )}

        {/* Modal: Full Exam Topics */}
        {selectedExamTopics && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4 animate-in fade-in duration-150">
            <div className="bg-white rounded-3xl border border-border shadow-2xl w-full max-w-lg p-6 space-y-4 animate-in zoom-in-95 duration-150 max-h-[85vh] overflow-y-auto">
              <div className="flex items-center justify-between border-b border-border pb-3">
                <div className="flex items-center gap-2.5">
                  <div className="p-2 rounded-xl bg-primary/10 text-primary">
                    <BookOpen className="h-5 w-5" />
                  </div>
                  <div>
                    <h3 className="font-bold text-base text-foreground">Syllabus Units & Topics</h3>
                    <p className="text-xs text-muted-foreground">{selectedExamTopics.title}</p>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => setSelectedExamTopics(null)}
                  className="rounded-lg p-1 text-muted-foreground hover:text-foreground"
                >
                  <X className="h-5 w-5" />
                </button>
              </div>

              <div className="space-y-2">
                <p className="text-xs text-muted-foreground">
                  The questions for this exam are scoped strictly from the following {selectedExamTopics.topics.length} topics:
                </p>
                <div className="grid gap-2 max-h-60 overflow-y-auto p-1">
                  {selectedExamTopics.topics.map((t, idx) => (
                    <div
                      key={idx}
                      className="flex items-center gap-2.5 rounded-xl border border-border bg-slate-50/70 p-3 text-xs text-slate-800"
                    >
                      <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-md bg-white border border-slate-200 text-[10px] font-bold text-primary">
                        {idx + 1}
                      </span>
                      <span className="font-medium leading-relaxed">{t}</span>
                    </div>
                  ))}
                </div>
              </div>

              <div className="flex justify-end pt-3 border-t border-border">
                <button
                  type="button"
                  onClick={() => setSelectedExamTopics(null)}
                  className="rounded-xl bg-slate-900 px-4 py-2 text-xs font-bold text-white hover:bg-slate-800 transition-all"
                >
                  Close
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}

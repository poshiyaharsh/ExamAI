import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ExamDetailsModal } from "../components/ExamDetailsModal";
import {
  Activity,
  AlertCircle,
  AlertTriangle,
  ArrowRight,
  Award,
  BookOpen,
  Calendar,
  CheckCircle,
  CheckCircle2,
  Clock,
  Eye,
  FileText,
  History,
  Hourglass,
  LayoutDashboard,
  PlayCircle,
  PlusCircle,
  Radio,
  RefreshCw,
  Settings,
  ShieldAlert,
  TrendingDown,
  TrendingUp,
  Users,
  XCircle,
} from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { DashboardLayout } from "../components/DashboardLayout";
import { ExamPerformanceOverviewChart } from "../components/analytics/ExamPerformanceOverviewChart";
import {
  facultyDashboardApi,
  type FacultyDashboardData,
  type FacultyOngoingExamItem,
} from "../../services/api";

const menuItems = [
  { icon: LayoutDashboard, label: "Dashboard", path: "/faculty" },
  { icon: FileText, label: "Generate Paper", path: "/faculty/generate" },
  { icon: History, label: "Exam History", path: "/faculty/history" },
  { icon: Settings, label: "Settings", path: "/faculty/settings" },
];

const SCORE_COLORS = ["#EF4444", "#F59E0B", "#3B82F6", "#10B981"];

function getStatusBadgeStyle(status: string) {
  switch (status?.toLowerCase()) {
    case "live":
      return { bg: "bg-emerald-100 text-emerald-800", text: "text-emerald-800", border: "border-emerald-300" };
    case "published":
      return { bg: "bg-emerald-50 text-emerald-700", text: "text-emerald-700", border: "border-emerald-200" };
    case "draft":
      return { bg: "bg-amber-50 text-amber-700", text: "text-amber-700", border: "border-amber-200" };
    case "generating":
      return { bg: "bg-blue-50 text-blue-700", text: "text-blue-700", border: "border-blue-200" };
    case "closed":
      return { bg: "bg-slate-100 text-slate-700", text: "text-slate-700", border: "border-slate-200" };
    case "failed":
      return { bg: "bg-rose-50 text-rose-700", text: "text-rose-700", border: "border-rose-200" };
    default:
      return { bg: "bg-gray-100 text-gray-700", text: "text-gray-700", border: "border-gray-200" };
  }
}

function formatRelativeTime(dateStr: string): string {
  try {
    const d = new Date(dateStr);
    const now = new Date();
    const diffMs = now.getTime() - d.getTime();
    const diffSec = Math.floor(diffMs / 1000);
    const diffMin = Math.floor(diffSec / 60);
    const diffHour = Math.floor(diffMin / 60);
    const diffDay = Math.floor(diffHour / 24);

    if (diffSec < 60) return "just now";
    if (diffMin < 60) return `${diffMin}m ago`;
    if (diffHour < 24) return `${diffHour}h ago`;
    if (diffDay < 7) return `${diffDay}d ago`;
    return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
  } catch {
    return dateStr;
  }
}

function formatLiveCountdown(endsAt: string | null | undefined, serverNow?: string): string {
  if (!endsAt) return "No end time";
  try {
    const endMs = new Date(endsAt).getTime();
    const nowMs = serverNow ? new Date(serverNow).getTime() : Date.now();
    const diffSec = Math.max(0, Math.floor((endMs - nowMs) / 1000));
    if (diffSec <= 0) return "Closing now";
    const h = Math.floor(diffSec / 3600);
    const m = Math.floor((diffSec % 3600) / 60);
    const s = diffSec % 60;
    if (h > 0) return `Closes in ${h}h ${m}m`;
    if (m > 0) return `Closes in ${m}m ${s}s`;
    return `Closes in ${s}s`;
  } catch {
    return "Active";
  }
}

function getPerformanceBadge(avg: number | null) {
  if (avg === null || avg === undefined) return { label: "N/A", style: "bg-muted text-muted-foreground border-border" };
  if (avg >= 80) return { label: "Excellent", style: "bg-emerald-50 text-emerald-700 border-emerald-200" };
  if (avg >= 65) return { label: "Good", style: "bg-blue-50 text-blue-700 border-blue-200" };
  if (avg >= 50) return { label: "Average", style: "bg-amber-50 text-amber-700 border-amber-200" };
  return { label: "Needs Improvement", style: "bg-rose-50 text-rose-700 border-rose-200" };
}

export function FacultyDashboard() {
  const navigate = useNavigate();
  const [data, setData] = useState<FacultyDashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [lastUpdated, setLastUpdated] = useState<Date>(new Date());
  const [error, setError] = useState("");
  const [selectedExamForDetails, setSelectedExamForDetails] = useState<FacultyOngoingExamItem | null>(null);

  const loadDashboard = async (silent = false) => {
    try {
      if (!silent) {
        if (!data) setLoading(true);
        setIsRefreshing(true);
      }
      setError("");
      const res = await facultyDashboardApi.getDashboard();
      setData(res.data);
      setLastUpdated(new Date());
    } catch (err) {
      if (!silent) {
        setError(err instanceof Error ? err.message : "Unable to load faculty dashboard.");
      }
    } finally {
      setLoading(false);
      setIsRefreshing(false);
    }
  };

  useEffect(() => {
    void loadDashboard();
    const interval = setInterval(() => {
      if (!document.hidden) {
        void loadDashboard(true);
      }
    }, 15000);
    return () => clearInterval(interval);
  }, []);

  const profile = data?.profile;
  const stats = data?.stats;
  const ongoingExams = data?.ongoing_exams || [];
  const upcomingExams = data?.upcoming_exams || [];
  const recentExams = data?.recent_exams || [];
  const examPerf = data?.exam_performance || [];
  const scoreDist = data?.score_distribution || [];
  const topPerformers = data?.top_performers || [];
  const lowScorers = data?.needs_attention?.low_scorers || [];
  const unattempted = data?.needs_attention?.unattempted_students || [];
  const hardest = data?.hardest_questions || [];
  const pendingActions = data?.pending_actions;

  const hasZeroExams = stats?.total_exams === 0;

  return (
    <DashboardLayout menuItems={menuItems} userRole="Faculty">
      <div className="space-y-6">
        {/* Loading Skeletons */}
        {loading && (
          <div className="space-y-6 animate-pulse">
            <div className="h-24 bg-muted/60 rounded-xl" />
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3.5">
              {[...Array(6)].map((_, i) => (
                <div key={i} className="h-24 bg-muted/60 rounded-xl" />
              ))}
            </div>
            <div className="grid lg:grid-cols-2 gap-6">
              <div className="h-64 bg-muted/60 rounded-xl" />
              <div className="h-64 bg-muted/60 rounded-xl" />
            </div>
          </div>
        )}

        {/* Error State */}
        {!loading && error && (
          <div className="bg-white rounded-xl p-8 border border-destructive/20 text-center shadow-xs space-y-3">
            <AlertCircle className="w-10 h-10 text-destructive mx-auto" />
            <h3 className="font-semibold text-foreground text-base">Failed to load dashboard</h3>
            <p className="text-xs sm:text-sm text-muted-foreground">{error}</p>
            <button
              onClick={() => void loadDashboard()}
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-primary text-white text-xs sm:text-sm font-medium hover:opacity-90 transition-opacity"
            >
              <RefreshCw className="w-4 h-4" />
              Retry
            </button>
          </div>
        )}

        {/* Main Content */}
        {!loading && !error && data && (
          <>
            {/* Header Greeting Banner */}
            <div className="bg-gradient-to-r from-primary/10 via-secondary/10 to-transparent border border-primary/20 rounded-2xl p-5 sm:p-6 flex flex-col md:flex-row md:items-center justify-between gap-4">
              <div className="space-y-1.5">
                <div className="flex items-center gap-2 flex-wrap">
                  <h1 className="text-2xl sm:text-3xl font-bold text-foreground">
                    Welcome back, {profile?.first_name ? `Prof. ${profile.first_name}` : profile?.name || "Professor"}!
                  </h1>
                  {profile?.department && (
                    <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-primary/15 text-primary border border-primary/25">
                      {profile.department}
                    </span>
                  )}
                  {profile?.designation && (
                    <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-muted text-muted-foreground border border-border">
                      {profile.designation}
                    </span>
                  )}
                </div>
                <div className="text-xs sm:text-sm text-muted-foreground flex items-center gap-2 flex-wrap">
                  {profile?.employee_id && <span>ID: {profile.employee_id}</span>}
                </div>
              </div>

              {/* Quick Actions */}
              <div className="flex items-center gap-2 shrink-0">
                <Link
                  to="/faculty/generate"
                  className="px-4 py-2 rounded-lg bg-gradient-to-r from-primary to-secondary text-white text-xs sm:text-sm font-medium shadow-sm hover:opacity-90 transition-all flex items-center gap-1.5"
                >
                  <PlusCircle className="w-4 h-4" />
                  Generate Exam Paper
                </Link>
                <Link
                  to="/faculty/history"
                  className="px-3.5 py-2 rounded-lg border border-border bg-white text-foreground text-xs sm:text-sm font-medium hover:bg-muted/50 transition-colors flex items-center gap-1.5 shadow-2xs"
                >
                  <History className="w-4 h-4 text-primary" />
                  Exam History
                </Link>
              </div>
            </div>

            {/* Pending Actions Notification (if any drafts or empty exams) */}
            {pendingActions && (pendingActions.draft_exams_count > 0 || pendingActions.empty_exams_count > 0) && (
              <div className="bg-amber-50/60 border border-amber-200/80 rounded-xl p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <div className="flex items-center gap-3">
                  <div className="w-9 h-9 rounded-lg bg-amber-100 text-amber-700 flex items-center justify-center shrink-0">
                    <AlertTriangle className="w-5 h-5" />
                  </div>
                  <div>
                    <h4 className="font-semibold text-xs sm:text-sm text-amber-900">
                      Pending Exam Actions Required
                    </h4>
                    <p className="text-xs text-amber-700">
                      You have <strong>{pendingActions.draft_exams_count} draft {pendingActions.draft_exams_count === 1 ? "exam" : "exams"}</strong> awaiting review & publication
                      {pendingActions.empty_exams_count > 0 ? ` and ${pendingActions.empty_exams_count} with no questions.` : "."}
                    </p>
                  </div>
                </div>
                <Link
                  to="/faculty/history"
                  className="px-3 py-1.5 rounded-lg bg-amber-600 text-white text-xs font-medium hover:bg-amber-700 transition-colors shrink-0 self-start sm:self-auto"
                >
                  Review Drafts
                </Link>
              </div>
            )}

            {/* Empty State when faculty has 0 exams */}
            {hasZeroExams ? (
              <div className="bg-white rounded-xl p-12 text-center border border-border shadow-xs space-y-4">
                <div className="w-16 h-16 rounded-full bg-primary/10 flex items-center justify-center mx-auto text-primary">
                  <FileText className="w-8 h-8" />
                </div>
                <h3 className="text-xl font-bold text-foreground">You haven't created any exams yet</h3>
                <p className="text-xs sm:text-sm text-muted-foreground max-w-md mx-auto">
                  Upload your syllabus or use our AI Paper Generator to create your first exam. Once students take your exam, real-time analytics, score distributions, and performance insights will appear here.
                </p>
                <Link
                  to="/faculty/generate"
                  className="inline-flex items-center gap-2 px-5 py-2.5 rounded-lg bg-gradient-to-r from-primary to-secondary text-white font-medium text-xs sm:text-sm shadow-sm hover:opacity-90 transition-all"
                >
                  <PlusCircle className="w-4 h-4" />
                  Create Your First Exam
                </Link>
              </div>
            ) : (
              <>
                {/* 6 Quick Stat Cards */}
                <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3.5">
                  <div className="bg-white rounded-xl p-4 shadow-2xs border border-border">
                    <div className="text-xs text-muted-foreground font-medium mb-1">Total Exams</div>
                    <div className="text-xl sm:text-2xl font-bold text-foreground">{stats?.total_exams}</div>
                    <div className="text-[11px] text-muted-foreground mt-1">
                      <span className="text-emerald-600 font-medium">{stats?.published_exams} published</span> · {stats?.draft_exams} drafts
                    </div>
                  </div>

                  <div className="bg-white rounded-xl p-4 shadow-2xs border border-border">
                    <div className="text-xs text-muted-foreground font-medium mb-1">Active / Ongoing</div>
                    <div className="text-xl sm:text-2xl font-bold text-emerald-600">{stats?.ongoing_exams}</div>
                    <div className="text-[11px] text-muted-foreground mt-1">Live for students</div>
                  </div>

                  <div className="bg-white rounded-xl p-4 shadow-2xs border border-border">
                    <div className="text-xs text-muted-foreground font-medium mb-1">Department Students</div>
                    <div className="text-xl sm:text-2xl font-bold text-foreground">{stats?.total_students}</div>
                    <div className="text-[11px] text-muted-foreground mt-1 flex items-center gap-1">
                      <Users className="w-3 h-3 text-primary" /> In {profile?.department}
                    </div>
                  </div>

                  <div className="bg-white rounded-xl p-4 shadow-2xs border border-border">
                    <div className="text-xs text-muted-foreground font-medium mb-1">Total Submissions</div>
                    <div className="text-xl sm:text-2xl font-bold text-foreground">{stats?.total_attempts}</div>
                    <div className="text-[11px] text-muted-foreground mt-1">Completed attempts</div>
                  </div>

                  <div className="bg-white rounded-xl p-4 shadow-2xs border border-border">
                    <div className="text-xs text-muted-foreground font-medium mb-1">Average Score</div>
                    <div className="text-xl sm:text-2xl font-bold text-primary">
                      {stats?.overall_average !== null && stats?.overall_average !== undefined ? `${stats.overall_average}%` : "N/A"}
                    </div>
                    <div className="mt-1">
                      {(() => {
                        const b = getPerformanceBadge(stats?.overall_average ?? null);
                        return (
                          <span className={`inline-flex items-center px-1.5 py-0.2 rounded-full text-[10px] font-semibold border ${b.style}`}>
                            {b.label}
                          </span>
                        );
                      })()}
                    </div>
                  </div>

                  <div className="bg-white rounded-xl p-4 shadow-2xs border border-border">
                    <div className="text-xs text-muted-foreground font-medium mb-1">Overall Pass Rate</div>
                    <div className="text-xl sm:text-2xl font-bold text-foreground">
                      {stats?.overall_pass_rate !== null && stats?.overall_pass_rate !== undefined ? `${stats.overall_pass_rate}%` : "N/A"}
                    </div>
                    <div className="text-[11px] text-muted-foreground mt-1">
                      {stats?.pass_count} passed · {stats?.fail_count} failed
                    </div>
                  </div>
                </div>

                {/* Ongoing Exams Highlight Section */}
                <div id="ongoing-live-exams" className="bg-card rounded-xl border border-border shadow-xs overflow-hidden min-w-0 max-w-full">
                  <div className="p-4 sm:p-5 border-b border-border bg-emerald-500/5 flex flex-wrap items-center justify-between gap-3">
                    <div className="flex items-center gap-2.5">
                      <span className="relative flex h-2.5 w-2.5">
                        <span className="animate-ping motion-reduce:hidden absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
                        <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-500" />
                      </span>
                      <h3 className="font-bold text-foreground text-sm sm:text-base">Ongoing Live Exams</h3>
                      <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-bold bg-emerald-100 text-emerald-800 border border-emerald-300">
                        {data?.total_live_count ?? ongoingExams.length} Live
                      </span>
                    </div>
                    <div className="flex items-center gap-3 text-xs text-muted-foreground">
                      <span className="hidden sm:inline" aria-live="polite">
                        Updated {formatRelativeTime(lastUpdated.toISOString())}
                      </span>
                      <button
                        onClick={() => void loadDashboard(false)}
                        className="p-1 rounded-md hover:bg-muted text-muted-foreground hover:text-foreground transition-colors"
                        title="Refresh live metrics"
                        aria-label="Refresh live metrics"
                      >
                        <RefreshCw className={`w-3.5 h-3.5 ${isRefreshing ? "animate-spin" : ""}`} />
                      </button>
                      <Link
                        to="/faculty/history?status=published"
                        className="text-primary hover:underline font-semibold flex items-center gap-1"
                      >
                        View all <ArrowRight className="w-3 h-3" />
                      </Link>
                    </div>
                  </div>

                  {ongoingExams.length === 0 ? (
                    <div className="p-8 text-center space-y-3">
                      <div className="w-12 h-12 rounded-full bg-emerald-50 text-emerald-600 flex items-center justify-center mx-auto">
                        <PlayCircle className="w-6 h-6" />
                      </div>
                      <div>
                        <h4 className="font-semibold text-foreground text-sm">No exams are live right now</h4>
                        <p className="text-xs text-muted-foreground max-w-md mx-auto mt-0.5">
                          Published exams with active testing windows will automatically appear here with real-time participation metrics.
                        </p>
                      </div>
                      <Link
                        to="/faculty/generate"
                        className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-primary text-white text-xs font-semibold hover:opacity-90 transition-all shadow-xs"
                      >
                        <PlusCircle className="w-3.5 h-3.5" />
                        Create exam
                      </Link>
                    </div>
                  ) : (
                    <div className="p-4 sm:p-5">
                      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                        {ongoingExams.slice(0, 3).map((exam) => {
                          const sec = exam.seconds_remaining;
                          const totalSec = exam.window_total_seconds || (exam.duration_minutes || 60) * 60;
                          const elapsedSec = sec !== null && sec !== undefined ? Math.max(0, totalSec - sec) : 0;
                          const progressPct = sec !== null && sec !== undefined
                            ? Math.min(100, Math.max(0, Math.round((elapsedSec / totalSec) * 100)))
                            : 0;
                          const isUrgent = sec !== null && sec !== undefined && sec < 600;
                          const isWarning = sec !== null && sec !== undefined && sec < 1800 && !isUrgent;
                          const countdownText = formatLiveCountdown(exam.ends_at, data?.server_now);

                          return (
                            <div
                              key={exam.id}
                              className="bg-card rounded-xl border border-border p-4 space-y-3.5 hover:shadow-md transition-all flex flex-col justify-between"
                            >
                              <div className="space-y-2.5">
                                <div className="flex items-start justify-between gap-2">
                                  <div className="min-w-0 flex-1">
                                    <h4 className="font-bold text-foreground text-sm truncate" title={exam.title}>
                                      {exam.title}
                                    </h4>
                                    <p className="text-xs text-muted-foreground truncate" title={exam.subject}>
                                      {exam.subject}
                                    </p>
                                  </div>
                                  <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-bold bg-emerald-100 text-emerald-800 border border-emerald-300 shrink-0">
                                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-600 animate-pulse motion-reduce:hidden" />
                                    Live
                                  </span>
                                </div>

                                {/* Countdown & Duration Bar */}
                                <div className="space-y-1">
                                  <div className="flex items-center justify-between text-xs">
                                    <span className="text-muted-foreground flex items-center gap-1 text-[11px]">
                                      <Clock className="w-3 h-3" />
                                      Time remaining:
                                    </span>
                                    <span
                                      className={`font-semibold text-xs ${
                                        !exam.ends_at
                                          ? "text-muted-foreground"
                                          : isUrgent
                                          ? "text-rose-600 animate-pulse font-bold"
                                          : isWarning
                                          ? "text-amber-600 font-bold"
                                          : "text-foreground"
                                      }`}
                                    >
                                      {countdownText}
                                    </span>
                                  </div>
                                  <div className="w-full h-1.5 bg-muted rounded-full overflow-hidden">
                                    <div
                                      className={`h-full rounded-full transition-all duration-500 ${
                                        !exam.ends_at
                                          ? "bg-muted-foreground/30"
                                          : isUrgent
                                          ? "bg-rose-500"
                                          : isWarning
                                          ? "bg-amber-500"
                                          : "bg-emerald-500"
                                      }`}
                                      style={{ width: `${exam.ends_at ? progressPct : 100}%` }}
                                    />
                                  </div>
                                </div>

                                {/* 4 Live Stats Tiles (Consistent single-line labels, aligned numbers) */}
                                <div className="grid grid-cols-4 gap-1.5 text-center bg-muted/40 p-2 rounded-lg border border-border/50">
                                  <div
                                    className="p-1 min-h-[52px] flex flex-col justify-between"
                                    title="Students currently taking this exam"
                                  >
                                    <p className="text-[10px] text-muted-foreground uppercase font-medium truncate">
                                      In progress
                                    </p>
                                    <p className="text-sm font-bold text-blue-600">
                                      {exam.in_progress_count ?? exam.in_progress ?? 0}
                                    </p>
                                  </div>
                                  <div
                                    className="p-1 min-h-[52px] flex flex-col justify-between"
                                    title="Students who submitted their exam"
                                  >
                                    <p className="text-[10px] text-muted-foreground uppercase font-medium truncate">
                                      Submitted
                                    </p>
                                    <p className="text-sm font-bold text-emerald-600">
                                      {exam.submitted_count ?? exam.submitted ?? 0}
                                    </p>
                                  </div>
                                  <div
                                    className="p-1 min-h-[52px] flex flex-col justify-between"
                                    title="Eligible students who have not started yet"
                                  >
                                    <p className="text-[10px] text-muted-foreground uppercase font-medium truncate">
                                      Not started
                                    </p>
                                    <p className="text-sm font-bold text-slate-600">
                                      {exam.not_started_count ?? exam.not_started ?? 0}
                                    </p>
                                  </div>
                                  <div
                                    className={`p-1 min-h-[52px] flex flex-col justify-between rounded transition-colors ${
                                      (exam.flagged_students || 0) > 0
                                        ? "bg-rose-50/80 cursor-pointer hover:bg-rose-100"
                                        : ""
                                    }`}
                                    title={`${exam.total_violations || 0} violation events logged by ${
                                      exam.flagged_students || 0
                                    } student(s)`}
                                    onClick={() => {
                                      if ((exam.flagged_students || 0) > 0) {
                                        navigate(`/faculty/exams/${exam.id}/monitor?filter=flagged`);
                                      }
                                    }}
                                  >
                                    <p className="text-[10px] text-muted-foreground uppercase font-medium truncate">
                                      Flagged
                                    </p>
                                    <p
                                      className={`text-sm font-bold ${
                                        (exam.flagged_students || 0) > 0 ? "text-rose-600" : "text-muted-foreground"
                                      }`}
                                    >
                                      {exam.flagged_students || 0}
                                    </p>
                                  </div>
                                </div>
                              </div>

                              {/* Card Actions (Distinct Monitor vs View) */}
                              <div className="flex items-center gap-2 pt-2 border-t border-border">
                                <Link
                                  to={`/faculty/exams/${exam.id}/monitor`}
                                  className="flex-1 py-1.5 px-3 rounded-lg bg-primary text-white text-xs font-semibold hover:opacity-90 transition-all text-center flex items-center justify-center gap-1.5 shadow-xs focus:outline-none focus:ring-2 focus:ring-primary/40"
                                  title="Open live monitoring dashboard for real-time student tracking"
                                  aria-label={`Monitor live exam ${exam.title}`}
                                >
                                  <Activity className="w-3.5 h-3.5" />
                                  Monitor
                                </Link>
                                <button
                                  type="button"
                                  onClick={() => setSelectedExamForDetails(exam)}
                                  className="py-1.5 px-3 rounded-lg border border-border bg-card text-foreground hover:bg-muted text-xs font-medium transition-colors text-center flex items-center justify-center gap-1.5 cursor-pointer focus:outline-none focus:ring-2 focus:ring-primary/40"
                                  title="View exam details and specifications"
                                  aria-label={`View specifications for ${exam.title}`}
                                >
                                  <Eye className="w-3.5 h-3.5 text-muted-foreground" />
                                  View
                                </button>
                              </div>
                            </div>
                          );
                        })}
                      </div>

                      {/* Footer: Showing 3 of N Live Exams indicator */}
                      {(data?.total_live_count ?? ongoingExams.length) > 3 && (
                        <div className="mt-4 pt-3 border-t border-border flex items-center justify-between text-xs text-muted-foreground">
                          <span>
                            Showing 3 of <strong>{data?.total_live_count ?? ongoingExams.length}</strong> live exams
                          </span>
                          <Link
                            to="/faculty/history?status=published"
                            className="font-semibold text-primary hover:underline flex items-center gap-1"
                          >
                            View all live exams ({data?.total_live_count ?? ongoingExams.length}) <ArrowRight className="w-3 h-3" />
                          </Link>
                        </div>
                      )}
                    </div>
                  )}
                </div>

                {/* Read-Only Exam Details Modal */}
                <ExamDetailsModal
                  exam={selectedExamForDetails}
                  isOpen={Boolean(selectedExamForDetails)}
                  onClose={() => setSelectedExamForDetails(null)}
                />

                {/* 2-Column Visualizations: Exam Performance & Score Distribution */}
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 min-w-0">
                  {/* Redesigned Exam Performance Overview */}
                  <ExamPerformanceOverviewChart
                    exams={examPerf}
                    summary={data?.exam_perf_summary}
                    generatedAt={data?.exam_perf_generated_at}
                    loading={loading}
                    error={error}
                    onRetry={() => void loadDashboard()}
                  />

                  {/* Score Distribution Chart */}
                  <div className="bg-card rounded-xl shadow-2xs border border-border p-5 sm:p-6 flex flex-col justify-between min-w-0">
                    <div className="flex items-center justify-between mb-4">
                      <div>
                        <h3 className="font-semibold text-foreground text-sm sm:text-base">Student Score Distribution</h3>
                        <p className="text-xs text-muted-foreground">Attempt distribution across performance brackets</p>
                      </div>
                      <span className="text-xs text-muted-foreground font-medium bg-muted px-2 py-0.5 rounded-full">
                        {stats?.total_attempts} total
                      </span>
                    </div>

                    {stats?.total_attempts === 0 ? (
                      <div className="h-56 flex items-center justify-center text-xs text-muted-foreground">
                        No student attempts evaluated yet.
                      </div>
                    ) : (
                      <div className="h-56 sm:h-64 w-full min-w-0">
                        <ResponsiveContainer width="100%" height="100%">
                          <BarChart data={scoreDist} margin={{ top: 5, right: 10, left: -20, bottom: 5 }}>
                            <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" opacity={0.6} />
                            <XAxis dataKey="range" stroke="#6B7280" fontSize={11} tickLine={false} />
                            <YAxis allowDecimals={false} stroke="#6B7280" fontSize={11} tickLine={false} />
                            <Tooltip
                              formatter={(val: any, _, item) => [`${val} submissions`, item.payload.label]}
                              contentStyle={{
                                backgroundColor: "var(--card)",
                                borderColor: "var(--border)",
                                borderRadius: "8px",
                                fontSize: "12px",
                                color: "var(--foreground)",
                              }}
                            />
                            <Bar dataKey="count" radius={[6, 6, 0, 0]}>
                              {scoreDist.map((_, index) => (
                                <Cell key={`cell-${index}`} fill={SCORE_COLORS[index % SCORE_COLORS.length]} />
                              ))}
                            </Bar>
                          </BarChart>
                        </ResponsiveContainer>
                      </div>
                    )}
                  </div>
                </div>

                {/* 2-Column Student Insights: Top Performers & Needs Attention */}
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                  {/* Top Performers */}
                  <div className="bg-white rounded-xl shadow-2xs border border-border overflow-hidden">
                    <div className="p-4 sm:p-5 border-b border-border flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <Award className="w-4 h-4 text-emerald-600" />
                        <h3 className="font-semibold text-foreground text-sm sm:text-base">Top Performing Students</h3>
                      </div>
                      <span className="text-xs text-muted-foreground font-medium">Top 5 by Average</span>
                    </div>
                    <div className="p-4 sm:p-5">
                      {topPerformers.length === 0 ? (
                        <p className="text-xs text-muted-foreground text-center py-6">
                          No student attempts recorded yet.
                        </p>
                      ) : (
                        <div className="divide-y divide-border space-y-2.5">
                          {topPerformers.map((s, idx) => (
                            <div key={s.student_id} className="pt-2.5 first:pt-0 flex items-center justify-between gap-3">
                              <div className="flex items-center gap-3">
                                <div className="w-8 h-8 rounded-full bg-emerald-100 text-emerald-800 font-bold text-xs flex items-center justify-center shrink-0">
                                  #{idx + 1}
                                </div>
                                <div>
                                  <h4 className="font-semibold text-xs sm:text-sm text-foreground">{s.name}</h4>
                                  <p className="text-[11px] text-muted-foreground">Roll: {s.roll_number} · {s.exams_taken} exams</p>
                                </div>
                              </div>
                              <div className="text-right">
                                <span className="font-bold text-emerald-600 text-sm">{s.average_score}%</span>
                                <div className="text-[10px] text-muted-foreground">Average</div>
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Needs Attention */}
                  <div className="bg-white rounded-xl shadow-2xs border border-border overflow-hidden">
                    <div className="p-4 sm:p-5 border-b border-border flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <AlertCircle className="w-4 h-4 text-amber-600" />
                        <h3 className="font-semibold text-foreground text-sm sm:text-base">Students Needing Attention</h3>
                      </div>
                      <span className="text-xs text-amber-700 font-medium bg-amber-50 px-2 py-0.5 rounded-full border border-amber-200">
                        {lowScorers.length + unattempted.length} Flagged
                      </span>
                    </div>
                    <div className="p-4 sm:p-5">
                      {lowScorers.length === 0 && unattempted.length === 0 ? (
                        <p className="text-xs text-emerald-700 font-medium text-center py-6">
                          All students are performing well above pass criteria!
                        </p>
                      ) : (
                        <div className="divide-y divide-border space-y-2.5">
                          {lowScorers.map((s) => (
                            <div key={`low-${s.student_id}`} className="pt-2.5 first:pt-0 flex items-center justify-between gap-3">
                              <div>
                                <h4 className="font-semibold text-xs sm:text-sm text-foreground">{s.name}</h4>
                                <p className="text-[11px] text-rose-600 font-medium">{s.issue}</p>
                              </div>
                              <span className="px-2 py-0.5 rounded-full text-[11px] font-semibold bg-rose-50 text-rose-700 border border-rose-200">
                                {s.average_score}%
                              </span>
                            </div>
                          ))}
                          {unattempted.map((s) => (
                            <div key={`unatt-${s.student_id}`} className="pt-2.5 first:pt-0 flex items-center justify-between gap-3">
                              <div>
                                <h4 className="font-semibold text-xs sm:text-sm text-foreground">{s.name}</h4>
                                <p className="text-[11px] text-amber-700 font-medium">{s.issue}</p>
                              </div>
                              <span className="px-2 py-0.5 rounded-full text-[11px] font-medium bg-amber-50 text-amber-700 border border-amber-200">
                                0 attempts
                              </span>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                </div>

                {/* Hardest Questions Widget */}
                {hardest.length > 0 && (
                  <div className="bg-white rounded-xl shadow-2xs border border-border overflow-hidden">
                    <div className="p-4 sm:p-5 border-b border-border flex items-center justify-between">
                      <div>
                        <h3 className="font-semibold text-foreground text-sm sm:text-base">Hardest Questions Analysis</h3>
                        <p className="text-xs text-muted-foreground">Questions most frequently answered incorrectly by students</p>
                      </div>
                      <span className="text-xs text-rose-600 bg-rose-50 border border-rose-200 px-2 py-0.5 rounded-full font-medium">
                        Top {hardest.length} Struggle Points
                      </span>
                    </div>
                    <div className="p-4 sm:p-5 divide-y divide-border">
                      {hardest.map((q, idx) => (
                        <div key={q.question_id} className="py-3.5 first:pt-0 last:pb-0 flex flex-col md:flex-row md:items-start justify-between gap-3">
                          <div className="space-y-1 flex-1">
                            <div className="flex items-center gap-2 flex-wrap">
                              <span className="font-bold text-xs text-primary">Q{idx + 1}.</span>
                              <span className="font-medium text-xs sm:text-sm text-foreground">{q.text}</span>
                            </div>
                            <div className="text-[11px] text-muted-foreground flex items-center gap-2 flex-wrap">
                              <span>Exam: <strong>{q.exam_title}</strong></span>
                              <span>•</span>
                              <span>Topic: {q.topic}</span>
                              <span>•</span>
                              <span className="capitalize font-medium">Difficulty: {q.difficulty}</span>
                            </div>
                          </div>
                          <div className="text-right shrink-0">
                            <span className="text-xs sm:text-sm font-bold text-rose-600">
                              {q.wrong_answers} of {q.total_answers} wrong
                            </span>
                            <div className="text-[10px] text-muted-foreground">{q.error_rate}% error rate</div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Recent Exams Section */}
                <div className="bg-card rounded-xl shadow-xs border border-border overflow-hidden min-w-0 max-w-full">
                  <div className="p-4 sm:p-5 border-b border-border flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <div className="flex items-center gap-2">
                        <h3 className="font-bold text-foreground text-sm sm:text-base">Recent Created Exams</h3>
                        <span className="text-xs text-muted-foreground bg-muted px-2 py-0.5 rounded-full font-medium">
                          {recentExams.length}
                        </span>
                      </div>
                      <p className="text-xs text-muted-foreground mt-0.5">Manage and track your published, draft, and shortfall exams</p>
                    </div>
                    <div className="flex items-center gap-2.5">
                      <Link
                        to="/faculty/generate"
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-primary text-white text-xs font-semibold hover:opacity-90 transition-all shadow-xs"
                      >
                        <PlusCircle className="w-3.5 h-3.5" />
                        Create new exam
                      </Link>
                      <Link
                        to="/faculty/history"
                        className="text-xs font-semibold text-primary hover:underline flex items-center gap-1"
                      >
                        View all <ArrowRight className="w-3 h-3" />
                      </Link>
                    </div>
                  </div>

                  {recentExams.length === 0 ? (
                    <div className="p-8 text-center space-y-3">
                      <FileText className="w-10 h-10 text-muted-foreground/50 mx-auto" />
                      <div>
                        <h4 className="font-semibold text-foreground text-sm">You haven't created any exams yet</h4>
                        <p className="text-xs text-muted-foreground max-w-md mx-auto mt-0.5">
                          Generate an AI-powered exam from your course syllabus or create questions manually.
                        </p>
                      </div>
                      <Link
                        to="/faculty/generate"
                        className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-primary text-white text-xs font-semibold hover:opacity-90 transition-all"
                      >
                        <PlusCircle className="w-4 h-4" />
                        Generate Paper
                      </Link>
                    </div>
                  ) : (
                    <>
                      {/* Desktop Table-like List (>= 768px) */}
                      <div className="hidden md:block overflow-x-auto w-full min-w-0">
                        <table className="w-full text-left border-collapse table-fixed">
                          <colgroup>
                            <col className="w-[32%]" />
                            <col className="w-[15%]" />
                            <col className="w-[18%]" />
                            <col className="w-[12%]" />
                            <col className="w-[10%]" />
                            <col className="w-[13%]" />
                          </colgroup>
                          <thead className="border-b border-border bg-muted/40 text-muted-foreground text-xs uppercase font-semibold">
                            <tr>
                              <th className="py-3 px-4">Exam & Subject</th>
                              <th className="py-3 px-4">Status</th>
                              <th className="py-3 px-4">Marks & Questions</th>
                              <th className="py-3 px-4">Created</th>
                              <th className="py-3 px-4">Submissions</th>
                              <th className="py-3 px-4 text-right">Actions</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-border text-sm">
                            {recentExams.map((exam) => {
                              const badge = getStatusBadgeStyle(exam.status);
                              return (
                                <tr key={exam.id} className="hover:bg-muted/20 transition-colors">
                                  <td className="py-3.5 px-4 overflow-hidden">
                                    <div className="min-w-0">
                                      <Link
                                        to={`/faculty/edit-paper/${exam.id}`}
                                        className="font-semibold text-foreground hover:text-primary transition-colors text-sm truncate block"
                                        title={exam.title}
                                      >
                                        {exam.title}
                                      </Link>
                                      <p className="text-xs text-muted-foreground truncate" title={exam.subject}>
                                        {exam.subject || "General Course"}
                                      </p>
                                    </div>
                                  </td>
                                  <td className="py-3.5 px-4 overflow-hidden">
                                    <div className="flex flex-col gap-1 items-start">
                                      <span
                                        className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold border capitalize truncate max-w-full ${badge.bg} ${badge.border}`}
                                      >
                                        {exam.status}
                                      </span>
                                      {exam.needs_attention && (
                                        <span className="inline-flex items-center gap-1 text-[10px] font-bold text-amber-700 bg-amber-100/70 border border-amber-200 px-1.5 py-0.2 rounded">
                                          <AlertTriangle className="w-2.5 h-2.5" />
                                          {exam.attention_reason}
                                        </span>
                                      )}
                                    </div>
                                  </td>
                                  <td className="py-3.5 px-4 text-xs">
                                    <div className="font-semibold text-foreground truncate">
                                      {exam.total_marks || 0}
                                      {exam.target_total_marks && exam.target_total_marks !== exam.total_marks
                                        ? ` / ${exam.target_total_marks}`
                                        : ""}{" "}
                                      pts
                                    </div>
                                    <div className="text-muted-foreground text-[11px] flex items-center gap-1 mt-0.5">
                                      <span>{exam.question_count || 0} questions</span>
                                      {exam.marks_shortfall !== undefined && exam.marks_shortfall > 0 && (
                                        <span className="text-amber-700 font-bold bg-amber-100 px-1 rounded text-[10px]">
                                          {exam.marks_shortfall} short
                                        </span>
                                      )}
                                    </div>
                                  </td>
                                  <td
                                    className="py-3.5 px-4 text-xs text-muted-foreground truncate"
                                    title={new Date(exam.created_at).toLocaleString()}
                                  >
                                    {formatRelativeTime(exam.created_at)}
                                  </td>
                                  <td className="py-3.5 px-4 text-xs">
                                    <span className="font-semibold text-foreground">{exam.attempts_count}</span>
                                    {exam.average_score !== null && (
                                      <span className="text-muted-foreground text-[11px] ml-1">({exam.average_score}% avg)</span>
                                    )}
                                  </td>
                                  <td className="py-3.5 px-4 text-right">
                                    <div className="inline-flex items-center gap-2 justify-end">
                                      <Link
                                        to={`/faculty/edit-paper/${exam.id}`}
                                        className="px-2.5 py-1 rounded-md border border-border bg-card text-foreground hover:bg-muted text-xs font-medium transition-colors"
                                      >
                                        {exam.status.toLowerCase() === "draft" ? "Edit" : "Review"}
                                      </Link>
                                      <Link
                                        to="/faculty/history"
                                        className="p-1.5 rounded-md hover:bg-muted text-muted-foreground hover:text-foreground transition-colors"
                                        title="Manage in History"
                                        aria-label="Manage in History"
                                      >
                                        <ArrowRight className="w-3.5 h-3.5" />
                                      </Link>
                                    </div>
                                  </td>
                                </tr>
                              );
                            })}
                          </tbody>
                        </table>
                      </div>

                      {/* Mobile Stacked Cards (< 768px, no horizontal scrollbar) */}
                      <div className="md:hidden divide-y divide-border">
                        {recentExams.map((exam) => {
                          const badge = getStatusBadgeStyle(exam.status);
                          return (
                            <div key={exam.id} className="p-4 space-y-2.5">
                              <div className="flex items-start justify-between gap-2">
                                <div className="min-w-0 flex-1">
                                  <Link
                                    to={`/faculty/edit-paper/${exam.id}`}
                                    className="font-semibold text-foreground text-sm truncate block"
                                  >
                                    {exam.title}
                                  </Link>
                                  <p className="text-xs text-muted-foreground truncate">{exam.subject}</p>
                                </div>
                                <span
                                  className={`inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold border capitalize shrink-0 ${badge.bg} ${badge.border}`}
                                >
                                  {exam.status}
                                </span>
                              </div>

                              {exam.needs_attention && (
                                <div className="inline-flex items-center gap-1.5 text-xs font-medium text-amber-800 bg-amber-50 border border-amber-200 px-2 py-0.5 rounded-md">
                                  <AlertTriangle className="w-3 h-3 text-amber-600" />
                                  Attention: {exam.attention_reason}
                                </div>
                              )}

                              <div className="grid grid-cols-2 gap-2 text-xs bg-muted/40 p-2.5 rounded-lg border border-border/50">
                                <div>
                                  <span className="text-muted-foreground">Marks: </span>
                                  <strong className="text-foreground">
                                    {exam.total_marks || 0}
                                    {exam.target_total_marks && exam.target_total_marks !== exam.total_marks
                                      ? `/${exam.target_total_marks}`
                                      : ""}{" "}
                                    pts
                                  </strong>
                                </div>
                                <div>
                                  <span className="text-muted-foreground">Questions: </span>
                                  <strong className="text-foreground">{exam.question_count || 0}</strong>
                                </div>
                                <div>
                                  <span className="text-muted-foreground">Submissions: </span>
                                  <strong className="text-foreground">{exam.attempts_count}</strong>
                                </div>
                                <div>
                                  <span className="text-muted-foreground">Created: </span>
                                  <strong className="text-foreground">{formatRelativeTime(exam.created_at)}</strong>
                                </div>
                              </div>

                              <div className="flex items-center justify-between pt-1">
                                <Link
                                  to={`/faculty/edit-paper/${exam.id}`}
                                  className="text-xs font-semibold text-primary hover:underline"
                                >
                                  {exam.status.toLowerCase() === "draft" ? "Edit Paper →" : "Review Paper →"}
                                </Link>
                                <Link
                                  to="/faculty/history"
                                  className="text-xs text-muted-foreground hover:text-foreground"
                                >
                                  Manage in History
                                </Link>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </>
                  )}
                </div>
              </>
            )}
          </>
        )}
      </div>
    </DashboardLayout>
  );
}

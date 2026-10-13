import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  Activity,
  AlertCircle,
  AlertTriangle,
  ArrowRight,
  Award,
  BarChart3,
  Building,
  Calendar,
  CheckCircle2,
  Clock,
  ExternalLink,
  FileText,
  Filter,
  GraduationCap,
  Info,
  Layers,
  PlayCircle,
  Plus,
  RefreshCw,
  Search,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  TrendingDown,
  TrendingUp,
  UserCheck,
  Users,
  X,
  XCircle,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { DashboardLayout } from "../components/DashboardLayout";
import {
  adminDashboardApi,
  type AdminDashboardData,
  type AdminDepartmentOverview,
  type AdminOngoingExam,
  type LiveRosterResponse,
  type LiveRosterStudent,
  type IneligibleAttempt,
} from "../../services/api";

const SCORE_DIST_COLORS = ["#EF4444", "#F59E0B", "#3B82F6", "#10B981"];

function formatTimeAgo(isoString: string): string {
  try {
    const diff = (Date.now() - new Date(isoString).getTime()) / 1000;
    if (diff < 60) return "Just now";
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
    if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
    if (diff < 604800) return `${Math.floor(diff / 86400)}d ago`;
    return new Date(isoString).toLocaleDateString("en-US", { month: "short", day: "numeric" });
  } catch {
    return isoString;
  }
}

function formatDateTime(isoString: string | null): string {
  if (!isoString) return "Flexible schedule";
  try {
    return new Date(isoString).toLocaleString("en-US", {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return isoString;
  }
}

function getPerformanceBadge(avg: number | null) {
  if (avg === null || avg === undefined) {
    return { label: "No Attempts", style: "bg-muted text-muted-foreground border-border" };
  }
  if (avg >= 80) return { label: "Excellent", style: "bg-emerald-50 text-emerald-700 border-emerald-200" };
  if (avg >= 60) return { label: "Good", style: "bg-blue-50 text-blue-700 border-blue-200" };
  if (avg >= 40) return { label: "Passing", style: "bg-amber-50 text-amber-700 border-amber-200" };
  return { label: "Needs Improvement", style: "bg-rose-50 text-rose-700 border-rose-200" };
}

export function AdminDashboard() {
  const navigate = useNavigate();
  const [data, setData] = useState<AdminDashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [selectedDept, setSelectedDept] = useState("all");
  const [selectedRange, setSelectedRange] = useState("all");
  const [atRiskTab, setAtRiskTab] = useState<"low_score" | "unattempted">("low_score");
  const [deptChartMetric, setDeptChartMetric] = useState<"students" | "exams" | "average">("students");

  const fetchDashboard = useCallback(
    async (isManualRefresh = false) => {
      try {
        if (isManualRefresh) setRefreshing(true);
        else setLoading(true);
        setError(null);

        const params: { department?: string; range?: string } = {};
        if (selectedDept && selectedDept !== "all") params.department = selectedDept;
        if (selectedRange && selectedRange !== "all") params.range = selectedRange;

        const res = await adminDashboardApi.getDashboard(params);
        setData(res.data);
      } catch (err: any) {
        console.error("Failed to load admin dashboard:", err);
        setError(err?.response?.data?.message || err?.message || "Unable to load admin dashboard data.");
      } finally {
        setLoading(false);
        setRefreshing(false);
      }
    },
    [selectedDept, selectedRange]
  );

  useEffect(() => {
    void fetchDashboard();
  }, [fetchDashboard]);

  // Auto-refresh every 20 seconds, pausing when document is hidden
  useEffect(() => {
    const interval = setInterval(() => {
      if (document.visibilityState === "visible") {
        void fetchDashboard(true);
      }
    }, 20000);
    return () => clearInterval(interval);
  }, [fetchDashboard]);

  // Real-time second countdown ticker for live ongoing exams
  const [countdownOffsets, setCountdownOffsets] = useState<Record<number, number>>({});

  useEffect(() => {
    const timer = setInterval(() => {
      setCountdownOffsets((prev) => {
        const next = { ...prev };
        (data?.ongoing_exams || []).forEach((exam) => {
          next[exam.id] = (next[exam.id] || 0) + 1;
        });
        return next;
      });
    }, 1000);
    return () => clearInterval(timer);
  }, [data?.ongoing_exams]);

  const formatLiveCountdown = (exam: AdminOngoingExam): string => {
    let remainingSec = exam.seconds_remaining;
    if (remainingSec === null || remainingSec === undefined) {
      if (exam.ends_at) {
        remainingSec = Math.max(0, Math.floor((new Date(exam.ends_at).getTime() - Date.now()) / 1000));
      } else {
        return `${exam.duration_minutes}m duration`;
      }
    }
    const offset = countdownOffsets[exam.id] || 0;
    const currentRem = Math.max(0, remainingSec - offset);
    if (currentRem <= 0) return "Ending now";
    const hrs = Math.floor(currentRem / 3600);
    const mins = Math.floor((currentRem % 3600) / 60);
    const secs = currentRem % 60;
    if (hrs > 0) return `${hrs}h ${mins}m ${secs < 10 ? "0" : ""}${secs}s`;
    return `${mins}m ${secs < 10 ? "0" : ""}${secs}s`;
  };

  // Live Roster Modal state
  const [selectedExamForRoster, setSelectedExamForRoster] = useState<AdminOngoingExam | null>(null);
  const [rosterData, setRosterData] = useState<LiveRosterResponse["data"] | null>(null);
  const [rosterLoading, setRosterLoading] = useState(false);
  const [rosterError, setRosterError] = useState<string | null>(null);
  const [rosterStatusFilter, setRosterStatusFilter] = useState<string>("all");
  const [rosterSearch, setRosterSearch] = useState<string>("");
  const [rosterPage, setRosterPage] = useState<number>(1);

  const loadLiveRoster = useCallback(
    async (examId: number, page = 1, status = "all", search = "") => {
      try {
        setRosterLoading(true);
        setRosterError(null);
        const params: { page: number; page_size: number; status?: string; search?: string } = {
          page,
          page_size: 10,
        };
        if (status !== "all" && status !== "ineligible") {
          params.status = status;
        }
        if (search.trim()) {
          params.search = search.trim();
        }
        const res = await adminDashboardApi.getLiveRoster(examId, params);
        setRosterData(res.data);
      } catch (err: any) {
        console.error("Failed to load live roster:", err);
        setRosterError(err?.response?.data?.error || err?.message || "Failed to load live roster");
      } finally {
        setRosterLoading(false);
      }
    },
    []
  );

  const openLiveRoster = (exam: AdminOngoingExam) => {
    setSelectedExamForRoster(exam);
    setRosterPage(1);
    setRosterStatusFilter("all");
    setRosterSearch("");
    void loadLiveRoster(exam.id, 1, "all", "");
  };

  const closeLiveRoster = () => {
    setSelectedExamForRoster(null);
    setRosterData(null);
    setRosterError(null);
  };

  const handleRosterPageChange = (newPage: number) => {
    if (!selectedExamForRoster) return;
    setRosterPage(newPage);
    void loadLiveRoster(selectedExamForRoster.id, newPage, rosterStatusFilter, rosterSearch);
  };

  const handleRosterFilterChange = (status: string) => {
    if (!selectedExamForRoster) return;
    setRosterStatusFilter(status);
    setRosterPage(1);
    void loadLiveRoster(selectedExamForRoster.id, 1, status, rosterSearch);
  };

  const handleRosterSearchChange = (val: string) => {
    setRosterSearch(val);
    if (!selectedExamForRoster) return;
    setRosterPage(1);
    void loadLiveRoster(selectedExamForRoster.id, 1, rosterStatusFilter, val);
  };

  const profile = data?.profile;
  const stats = data?.stats;
  const ongoingExams = data?.ongoing_exams || [];
  const upcomingExams = data?.upcoming_exams || [];
  const deptOverview = data?.department_overview || [];
  const topFaculty = data?.exams_per_faculty || [];
  const topStudents = data?.top_students || [];
  const lowScorers = data?.at_risk_students?.low_scorers || [];
  const unattemptedStudents = data?.at_risk_students?.unattempted_students || [];
  const activityTrend = data?.activity_trend || [];
  const scoreDist = data?.score_distribution || [];
  const recentActivity = data?.recent_activity || [];
  const pendingActions = data?.pending_actions;
  const departmentsList = data?.departments || [];

  const hasPendingItems =
    pendingActions &&
    (pendingActions.draft_exams_count > 0 ||
      pendingActions.empty_exams_count > 0 ||
      pendingActions.unassigned_students_count > 0);

  // Department chart formatting
  const deptChartData = deptOverview
    .filter((d) => d.students_count > 0 || d.exams_count > 0 || d.attempts_count > 0)
    .map((d) => ({
      name: d.department.length > 14 ? `${d.department.slice(0, 12)}...` : d.department,
      fullName: d.department,
      students: d.students_count,
      exams: d.exams_count,
      average: d.average_score ?? 0,
      attempts: d.attempts_count,
    }));

  return (
    <DashboardLayout userRole="Admin">
      <div className="space-y-6 pb-12">
        {/* Top Header & Context */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <h1 className="text-2xl sm:text-3xl font-bold text-foreground">
                Welcome back, {profile?.name || "Admin"}
              </h1>
              <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-primary/10 text-primary border border-primary/20">
                <ShieldAlert className="w-3.5 h-3.5" />
                Admin Console
              </span>
            </div>
            <div className="flex flex-wrap items-center gap-2 text-xs sm:text-sm text-muted-foreground">
              <span className="flex items-center gap-1.5 font-semibold text-foreground bg-muted/60 px-2 py-0.5 rounded-md border border-border">
                <Building className="w-3.5 h-3.5 text-primary" />
                {profile?.institution_name || "ExamAI Central"}
              </span>
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
                <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" />
                Tenant Isolated
              </span>
              {profile?.institution_code && (
                <>
                  <span>•</span>
                  <span className="font-mono bg-muted px-1.5 py-0.5 rounded text-xs">
                    Code: {profile.institution_code}
                  </span>
                </>
              )}
              <span>•</span>
              <span>Central institutional analytics and operations</span>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <button
              onClick={() => void fetchDashboard(true)}
              disabled={loading || refreshing}
              className="px-3.5 py-2 rounded-lg border border-border bg-card text-foreground hover:bg-muted text-xs font-medium flex items-center gap-1.5 transition-all shadow-sm disabled:opacity-60"
              title="Refresh dashboard metrics"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? "animate-spin text-primary" : ""}`} />
              <span>Refresh</span>
            </button>

            <Link
              to="/admin/exams"
              className="px-4 py-2 rounded-lg bg-gradient-to-r from-primary to-secondary text-white hover:opacity-90 shadow-sm font-medium text-xs sm:text-sm transition-all flex items-center gap-1.5"
            >
              <Plus className="w-4 h-4" />
              Manage Exams
            </Link>
          </div>
        </div>

        {/* Filter Controls Bar */}
        <div className="bg-card rounded-xl p-3 sm:p-4 border border-border shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-3">
            <div className="flex items-center gap-2 text-xs font-medium text-muted-foreground">
              <Filter className="w-3.5 h-3.5 text-primary" />
              <span>Filter Scope:</span>
            </div>

            {/* Department Select */}
            <select
              value={selectedDept}
              onChange={(e) => setSelectedDept(e.target.value)}
              className="text-xs bg-background border border-border rounded-lg px-3 py-1.5 font-medium text-foreground focus:outline-none focus:ring-2 focus:ring-primary/20 transition-all"
            >
              <option value="all">All Departments ({departmentsList.length})</option>
              {departmentsList.map((dept) => (
                <option key={dept} value={dept}>
                  {dept}
                </option>
              ))}
            </select>

            {/* Time Range Filter Pills */}
            <div className="inline-flex items-center rounded-lg bg-muted p-1 border border-border text-xs">
              {[
                { key: "all", label: "All Time" },
                { key: "semester", label: "Semester (120d)" },
                { key: "30d", label: "Last 30 Days" },
                { key: "7d", label: "Last 7 Days" },
              ].map((pill) => (
                <button
                  key={pill.key}
                  onClick={() => setSelectedRange(pill.key)}
                  className={`px-2.5 py-1 rounded-md text-xs font-medium transition-all ${
                    selectedRange === pill.key
                      ? "bg-card text-foreground shadow-xs font-semibold"
                      : "text-muted-foreground hover:text-foreground"
                  }`}
                >
                  {pill.label}
                </button>
              ))}
            </div>
          </div>

          {(selectedDept !== "all" || selectedRange !== "all") && (
            <button
              onClick={() => {
                setSelectedDept("all");
                setSelectedRange("all");
              }}
              className="text-xs text-primary hover:underline font-medium self-end md:self-auto"
            >
              Reset filters
            </button>
          )}
        </div>

        {/* Error State */}
        {error && (
          <div className="bg-rose-50 border border-rose-200 text-rose-800 rounded-xl p-4 flex items-start justify-between gap-3 shadow-xs">
            <div className="flex items-start gap-3">
              <AlertCircle className="w-5 h-5 text-rose-600 shrink-0 mt-0.5" />
              <div>
                <h4 className="font-semibold text-sm">Failed to sync dashboard metrics</h4>
                <p className="text-xs text-rose-700 mt-0.5">{error}</p>
              </div>
            </div>
            <button
              onClick={() => void fetchDashboard()}
              className="px-3 py-1.5 bg-rose-600 text-white text-xs font-medium rounded-lg hover:bg-rose-700 transition-colors"
            >
              Retry
            </button>
          </div>
        )}

        {/* Pending Actions / Attention Banner */}
        {hasPendingItems && (
          <div className="bg-amber-50/90 border border-amber-200/80 rounded-xl p-4 shadow-xs">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-lg bg-amber-500/20 text-amber-700 flex items-center justify-center shrink-0">
                  <AlertTriangle className="w-5 h-5" />
                </div>
                <div>
                  <h4 className="text-xs sm:text-sm font-semibold text-amber-900">
                    System Attention Required
                  </h4>
                  <div className="flex flex-wrap items-center gap-2 mt-1">
                    {pendingActions.draft_exams_count > 0 && (
                      <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-amber-100 text-amber-800">
                        {pendingActions.draft_exams_count} Draft Exams awaiting publishing
                      </span>
                    )}
                    {pendingActions.unassigned_students_count > 0 && (
                      <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-amber-100 text-amber-800">
                        {pendingActions.unassigned_students_count} Students with unassigned department
                      </span>
                    )}
                    {pendingActions.empty_exams_count > 0 && (
                      <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-amber-100 text-amber-800">
                        {pendingActions.empty_exams_count} Exams with 0 questions
                      </span>
                    )}
                  </div>
                </div>
              </div>

              <div className="flex items-center gap-2 self-end sm:self-auto">
                <Link
                  to="/admin/exams"
                  className="px-3 py-1.5 rounded-lg bg-white border border-amber-300 text-amber-900 hover:bg-amber-100 text-xs font-medium transition-colors"
                >
                  Review Exams
                </Link>
                <Link
                  to="/admin/students"
                  className="px-3 py-1.5 rounded-lg bg-white border border-amber-300 text-amber-900 hover:bg-amber-100 text-xs font-medium transition-colors"
                >
                  Review Students
                </Link>
              </div>
            </div>
          </div>
        )}

        {/* Loading Skeleton */}
        {loading && !data ? (
          <div className="space-y-6 animate-pulse">
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
              {[...Array(6)].map((_, i) => (
                <div key={i} className="h-28 bg-card border border-border rounded-xl" />
              ))}
            </div>
            <div className="h-44 bg-card border border-border rounded-xl" />
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <div className="h-80 bg-card border border-border rounded-xl" />
              <div className="h-80 bg-card border border-border rounded-xl" />
            </div>
          </div>
        ) : (
          <>
            {/* 6 Key Stat Cards */}
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4">
              {/* Card 1: Students */}
              <div className="bg-card rounded-xl p-4 shadow-sm border border-border hover:border-primary/30 transition-all flex flex-col justify-between">
                <div className="flex items-center justify-between mb-2">
                  <div className="w-9 h-9 rounded-lg bg-blue-50 text-blue-600 flex items-center justify-center">
                    <GraduationCap className="w-5 h-5" />
                  </div>
                  {stats && stats.new_students_this_week > 0 && (
                    <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded-full bg-blue-50 text-blue-700 border border-blue-200">
                      +{stats.new_students_this_week} this week
                    </span>
                  )}
                </div>
                <div>
                  <div className="text-2xl font-bold text-foreground tracking-tight">
                    {stats?.total_students ?? 0}
                  </div>
                  <div className="text-xs text-muted-foreground mt-0.5">Enrolled Students</div>
                </div>
              </div>

              {/* Card 2: Faculty */}
              <div className="bg-card rounded-xl p-4 shadow-sm border border-border hover:border-primary/30 transition-all flex flex-col justify-between">
                <div className="flex items-center justify-between mb-2">
                  <div className="w-9 h-9 rounded-lg bg-indigo-50 text-indigo-600 flex items-center justify-center">
                    <Users className="w-5 h-5" />
                  </div>
                  {stats && stats.new_faculty_this_week > 0 && (
                    <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded-full bg-indigo-50 text-indigo-700 border border-indigo-200">
                      +{stats.new_faculty_this_week} this week
                    </span>
                  )}
                </div>
                <div>
                  <div className="text-2xl font-bold text-foreground tracking-tight">
                    {stats?.total_faculty ?? 0}
                  </div>
                  <div className="text-xs text-muted-foreground mt-0.5">Faculty Members</div>
                </div>
              </div>

              {/* Card 3: Exams */}
              <div className="bg-card rounded-xl p-4 shadow-sm border border-border hover:border-primary/30 transition-all flex flex-col justify-between">
                <div className="flex items-center justify-between mb-2">
                  <div className="w-9 h-9 rounded-lg bg-purple-50 text-purple-600 flex items-center justify-center">
                    <FileText className="w-5 h-5" />
                  </div>
                  <span className="text-[10px] font-medium text-muted-foreground">
                    {stats?.published_exams ?? 0} active
                  </span>
                </div>
                <div>
                  <div className="text-2xl font-bold text-foreground tracking-tight">
                    {stats?.total_exams ?? 0}
                  </div>
                  <div className="text-xs text-muted-foreground mt-0.5">
                    Total Exams ({stats?.draft_exams ?? 0} drafts)
                  </div>
                </div>
              </div>

              {/* Card 4: Attempts */}
              <div className="bg-card rounded-xl p-4 shadow-sm border border-border hover:border-primary/30 transition-all flex flex-col justify-between">
                <div className="flex items-center justify-between mb-2">
                  <div className="w-9 h-9 rounded-lg bg-emerald-50 text-emerald-600 flex items-center justify-center">
                    <CheckCircle2 className="w-5 h-5" />
                  </div>
                  {stats && stats.new_attempts_this_week > 0 && (
                    <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200">
                      +{stats.new_attempts_this_week} this week
                    </span>
                  )}
                </div>
                <div>
                  <div className="text-2xl font-bold text-foreground tracking-tight">
                    {stats?.total_attempts ?? 0}
                  </div>
                  <div className="text-xs text-muted-foreground mt-0.5">Submissions Completed</div>
                </div>
              </div>

              {/* Card 5: Overall Average */}
              <div className="bg-card rounded-xl p-4 shadow-sm border border-border hover:border-primary/30 transition-all flex flex-col justify-between">
                <div className="flex items-center justify-between mb-2">
                  <div className="w-9 h-9 rounded-lg bg-amber-50 text-amber-600 flex items-center justify-center">
                    <Award className="w-5 h-5" />
                  </div>
                  {stats?.overall_average !== null && stats?.overall_average !== undefined && (
                    <span
                      className={`text-[10px] font-medium px-1.5 py-0.5 rounded-full border ${
                        getPerformanceBadge(stats.overall_average).style
                      }`}
                    >
                      {getPerformanceBadge(stats.overall_average).label}
                    </span>
                  )}
                </div>
                <div>
                  <div className="text-2xl font-bold text-foreground tracking-tight">
                    {stats?.overall_average !== null && stats?.overall_average !== undefined
                      ? `${stats.overall_average}%`
                      : "N/A"}
                  </div>
                  <div className="text-xs text-muted-foreground mt-0.5">Institutional Average</div>
                </div>
              </div>

              {/* Card 6: Pass Rate */}
              <div className="bg-card rounded-xl p-4 shadow-sm border border-border hover:border-primary/30 transition-all flex flex-col justify-between">
                <div className="flex items-center justify-between mb-2">
                  <div className="w-9 h-9 rounded-lg bg-teal-50 text-teal-600 flex items-center justify-center">
                    <TrendingUp className="w-5 h-5" />
                  </div>
                  <span className="text-[10px] font-medium text-muted-foreground">
                    Threshold ≥ 40%
                  </span>
                </div>
                <div>
                  <div className="text-2xl font-bold text-foreground tracking-tight">
                    {stats?.overall_pass_rate !== null && stats?.overall_pass_rate !== undefined
                      ? `${stats.overall_pass_rate}%`
                      : "N/A"}
                  </div>
                  <div className="text-xs text-muted-foreground mt-0.5">Overall Pass Rate</div>
                </div>
              </div>
            </div>

            {/* LIVE Ongoing Exams Spotlight */}
            <div className="bg-gradient-to-r from-emerald-500/10 via-teal-500/10 to-blue-500/10 border border-emerald-500/20 rounded-xl p-5 shadow-sm">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
                <div className="flex items-center gap-2.5">
                  <span className="relative flex h-3 w-3">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
                    <span className="relative inline-flex rounded-full h-3 w-3 bg-emerald-500" />
                  </span>
                  <div>
                    <div className="flex items-center gap-2">
                      <h3 className="font-bold text-sm sm:text-base text-foreground">
                        Active Live Examinations ({ongoingExams.length})
                      </h3>
                      <span className="inline-flex items-center gap-1 text-[11px] font-semibold px-2 py-0.5 rounded-full bg-emerald-100/80 text-emerald-800 border border-emerald-300/40">
                        <ShieldCheck className="w-3 h-3 text-emerald-600" />
                        {profile?.institution_name || "Institutional Roster"}
                      </span>
                    </div>
                    <p className="text-xs text-muted-foreground mt-0.5">
                      Real-time live monitoring strictly scoped to active students in your institution
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <Link
                    to="/admin/exams"
                    className="text-xs text-primary hover:underline font-semibold flex items-center gap-1"
                  >
                    View All in Exam Manager <ArrowRight className="w-3.5 h-3.5" />
                  </Link>
                </div>
              </div>

              {/* Institution Live Summary Counters */}
              {data?.live_summary && ongoingExams.length > 0 && (
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 mb-4 bg-card/60 backdrop-blur-xs p-3 rounded-lg border border-emerald-500/20">
                  <div className="text-center sm:text-left sm:pl-2">
                    <div className="text-[11px] text-muted-foreground font-medium">Eligible Students</div>
                    <div className="text-lg font-bold text-foreground">
                      {data.live_summary.total_eligible_unique}
                    </div>
                  </div>
                  <div className="text-center sm:text-left sm:pl-2 border-l border-border/60">
                    <div className="text-[11px] text-amber-700 dark:text-amber-400 font-medium">In-Progress Now</div>
                    <div className="text-lg font-bold text-amber-700 dark:text-amber-400">
                      {data.live_summary.total_in_progress}
                    </div>
                  </div>
                  <div className="text-center sm:text-left sm:pl-2 border-l border-border/60">
                    <div className="text-[11px] text-emerald-700 dark:text-emerald-400 font-medium">Submitted</div>
                    <div className="text-lg font-bold text-emerald-700 dark:text-emerald-400">
                      {data.live_summary.total_submitted}
                    </div>
                  </div>
                  <div className="text-center sm:text-left sm:pl-2 border-l border-border/60">
                    <div className="text-[11px] text-muted-foreground font-medium">Not Started</div>
                    <div className="text-lg font-bold text-muted-foreground">
                      {data.live_summary.total_not_started}
                    </div>
                  </div>
                </div>
              )}

              {ongoingExams.length === 0 ? (
                <div className="bg-card/70 border border-border/80 rounded-xl p-6 text-center">
                  <div className="w-10 h-10 rounded-full bg-muted flex items-center justify-center mx-auto mb-2 text-muted-foreground">
                    <Clock className="w-5 h-5" />
                  </div>
                  <h4 className="text-sm font-semibold text-foreground">No Live Examinations In Session</h4>
                  <p className="text-xs text-muted-foreground mt-1 max-w-md mx-auto">
                    There are no exams currently active in the schedule window for {profile?.institution_name || "your institution"}. Once an exam starts, real-time rosters and participation metrics will appear here automatically.
                  </p>
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {ongoingExams.map((exam) => {
                    const countdown = formatLiveCountdown(exam);
                    const participationPct = exam.participation_percent ?? 0;
                    return (
                      <div
                        key={exam.id}
                        className="bg-card rounded-xl p-4 border border-border shadow-xs hover:border-emerald-500/50 hover:shadow-md transition-all flex flex-col justify-between group"
                      >
                        <div>
                          <div className="flex items-center justify-between gap-2 mb-2">
                            <span className="text-[11px] font-semibold px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800 border border-emerald-200">
                              {exam.department}
                            </span>
                            <span className="text-xs font-mono font-medium text-emerald-700 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-950/40 px-2 py-0.5 rounded-full border border-emerald-200 dark:border-emerald-800/50 flex items-center gap-1">
                              <Clock className="w-3 h-3 animate-pulse" />
                              {countdown}
                            </span>
                          </div>
                          <h4 className="font-bold text-sm text-foreground line-clamp-1 group-hover:text-primary transition-colors">
                            {exam.title}
                          </h4>
                          <p className="text-xs text-muted-foreground mt-0.5">
                            By {exam.faculty_name} • {exam.total_marks} Marks
                          </p>

                          {/* 4 Invariant Breakdown Chips */}
                          <div className="grid grid-cols-2 gap-1.5 mt-3 pt-3 border-t border-border/80">
                            <div className="flex items-center justify-between px-2 py-1 rounded bg-blue-50/70 dark:bg-blue-950/30 border border-blue-200/50 text-[11px]">
                              <span className="text-blue-700 dark:text-blue-300 font-medium">Eligible</span>
                              <span className="font-bold text-blue-800 dark:text-blue-200">{exam.eligible_count}</span>
                            </div>
                            <div className="flex items-center justify-between px-2 py-1 rounded bg-amber-50/70 dark:bg-amber-950/30 border border-amber-200/50 text-[11px]">
                              <span className="text-amber-700 dark:text-amber-300 font-medium">In Progress</span>
                              <span className="font-bold text-amber-800 dark:text-amber-200">{exam.in_progress_count}</span>
                            </div>
                            <div className="flex items-center justify-between px-2 py-1 rounded bg-emerald-50/70 dark:bg-emerald-950/30 border border-emerald-200/50 text-[11px]">
                              <span className="text-emerald-700 dark:text-emerald-300 font-medium">Submitted</span>
                              <span className="font-bold text-emerald-800 dark:text-emerald-200">{exam.submitted_count}</span>
                            </div>
                            <div className="flex items-center justify-between px-2 py-1 rounded bg-muted/60 border border-border text-[11px]">
                              <span className="text-muted-foreground font-medium">Not Started</span>
                              <span className="font-bold text-foreground">{exam.not_started_count}</span>
                            </div>
                          </div>

                          {/* Ineligible attempts warning if present */}
                          {exam.ineligible_attempts > 0 && (
                            <div className="mt-2 flex items-center justify-between px-2 py-1 rounded bg-rose-50 dark:bg-rose-950/30 border border-rose-200 dark:border-rose-800 text-[11px] text-rose-700 dark:text-rose-300">
                              <span className="flex items-center gap-1 font-medium">
                                <AlertTriangle className="w-3 h-3 text-rose-500" />
                                Ineligible Attempts
                              </span>
                              <span className="font-bold">{exam.ineligible_attempts}</span>
                            </div>
                          )}
                        </div>

                        <div className="mt-4 pt-3 border-t border-border">
                          <div className="flex items-center justify-between text-xs mb-1.5">
                            <span className="text-muted-foreground font-medium">Participation Rate</span>
                            <span className="font-bold text-foreground">
                              {participationPct}% ({exam.submitted_count}/{exam.eligible_count})
                            </span>
                          </div>
                          <div className="w-full bg-muted rounded-full h-2 overflow-hidden mb-3">
                            <div
                              className="bg-emerald-500 h-2 rounded-full transition-all duration-500"
                              style={{ width: `${Math.max(4, Math.min(100, participationPct))}%` }}
                            />
                          </div>

                          <button
                            type="button"
                            onClick={() => openLiveRoster(exam)}
                            className="w-full py-1.5 px-3 rounded-lg bg-primary/10 hover:bg-primary/20 text-primary border border-primary/20 text-xs font-semibold flex items-center justify-center gap-1.5 transition-all shadow-2xs"
                          >
                            <Users className="w-3.5 h-3.5" />
                            View Live Student Roster
                          </button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>

            {/* Department Performance Overview */}
            <div className="bg-card rounded-xl p-5 border border-border shadow-sm">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-5">
                <div>
                  <h3 className="font-bold text-base text-foreground">Department Performance & Capacity</h3>
                  <p className="text-xs text-muted-foreground">
                    Comparative distribution across all 11 institution departments
                  </p>
                </div>

                <div className="inline-flex items-center rounded-lg bg-muted p-1 border border-border text-xs">
                  <button
                    onClick={() => setDeptChartMetric("students")}
                    className={`px-2.5 py-1 rounded-md text-xs font-medium transition-all ${
                      deptChartMetric === "students"
                        ? "bg-card text-foreground shadow-xs font-semibold"
                        : "text-muted-foreground hover:text-foreground"
                    }`}
                  >
                    Students
                  </button>
                  <button
                    onClick={() => setDeptChartMetric("exams")}
                    className={`px-2.5 py-1 rounded-md text-xs font-medium transition-all ${
                      deptChartMetric === "exams"
                        ? "bg-card text-foreground shadow-xs font-semibold"
                        : "text-muted-foreground hover:text-foreground"
                    }`}
                  >
                    Exams
                  </button>
                  <button
                    onClick={() => setDeptChartMetric("average")}
                    className={`px-2.5 py-1 rounded-md text-xs font-medium transition-all ${
                      deptChartMetric === "average"
                        ? "bg-card text-foreground shadow-xs font-semibold"
                        : "text-muted-foreground hover:text-foreground"
                    }`}
                  >
                    Avg Score %
                  </button>
                </div>
              </div>

              {/* Chart visualization */}
              <div className="w-full h-64 mb-6">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart
                    data={deptChartData.length > 0 ? deptChartData : [{ name: "No Active Depts", students: 0, exams: 0, average: 0 }]}
                    margin={{ top: 10, right: 10, left: -20, bottom: 25 }}
                  >
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" opacity={0.6} />
                    <XAxis
                      dataKey="name"
                      tick={{ fontSize: 11, fill: "var(--muted-foreground)" }}
                      interval={0}
                      angle={-20}
                      textAnchor="end"
                    />
                    <YAxis tick={{ fontSize: 11, fill: "var(--muted-foreground)" }} />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: "var(--card)",
                        borderColor: "var(--border)",
                        borderRadius: "8px",
                        fontSize: "12px",
                      }}
                      formatter={(value: any) => [
                        deptChartMetric === "average" ? `${value}%` : value,
                        deptChartMetric === "students"
                          ? "Students"
                          : deptChartMetric === "exams"
                          ? "Exams"
                          : "Average Score",
                      ]}
                    />
                    <Bar
                      dataKey={deptChartMetric}
                      fill={
                        deptChartMetric === "students"
                          ? "#3B82F6"
                          : deptChartMetric === "exams"
                          ? "#8B5CF6"
                          : "#10B981"
                      }
                      radius={[4, 4, 0, 0]}
                    />
                  </BarChart>
                </ResponsiveContainer>
              </div>

              {/* Compact Department Table */}
              <div className="overflow-x-auto rounded-lg border border-border">
                <table className="w-full text-left text-xs">
                  <thead className="bg-muted/60 text-muted-foreground border-b border-border font-semibold">
                    <tr>
                      <th className="py-2.5 px-4">Department</th>
                      <th className="py-2.5 px-3 text-center">Students</th>
                      <th className="py-2.5 px-3 text-center">Faculty</th>
                      <th className="py-2.5 px-3 text-center">Exams</th>
                      <th className="py-2.5 px-3 text-center">Attempts</th>
                      <th className="py-2.5 px-4 text-center">Avg Score</th>
                      <th className="py-2.5 px-4 text-center">Pass Rate</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {deptOverview.map((dept) => {
                      const perf = getPerformanceBadge(dept.average_score);
                      return (
                        <tr
                          key={dept.department}
                          className="hover:bg-muted/40 transition-colors"
                        >
                          <td className="py-2.5 px-4 font-medium text-foreground">
                            {dept.department}
                          </td>
                          <td className="py-2.5 px-3 text-center text-foreground font-semibold">
                            {dept.students_count}
                          </td>
                          <td className="py-2.5 px-3 text-center text-foreground">
                            {dept.faculty_count}
                          </td>
                          <td className="py-2.5 px-3 text-center text-foreground font-medium">
                            {dept.exams_count}
                          </td>
                          <td className="py-2.5 px-3 text-center text-foreground">
                            {dept.attempts_count}
                          </td>
                          <td className="py-2.5 px-4 text-center">
                            {dept.average_score !== null ? (
                              <span
                                className={`inline-block px-2 py-0.5 rounded text-[11px] font-semibold border ${perf.style}`}
                              >
                                {dept.average_score}%
                              </span>
                            ) : (
                              <span className="text-muted-foreground text-[11px]">-</span>
                            )}
                          </td>
                          <td className="py-2.5 px-4 text-center">
                            {dept.pass_rate !== null ? (
                              <span className="font-semibold text-foreground">
                                {dept.pass_rate}%
                              </span>
                            ) : (
                              <span className="text-muted-foreground text-[11px]">-</span>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Trends and Score Distribution (2-column grid) */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Activity Trend Chart */}
              <div className="bg-card rounded-xl p-5 border border-border shadow-sm flex flex-col justify-between">
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <h3 className="font-bold text-base text-foreground">Activity Trend</h3>
                    <span className="text-xs text-muted-foreground">Past 14 Days</span>
                  </div>
                  <p className="text-xs text-muted-foreground mb-4">
                    Daily breakdown of created exams and student exam submissions
                  </p>
                </div>

                <div className="w-full h-64">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={activityTrend} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                      <defs>
                        <linearGradient id="colorAttempts" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#10B981" stopOpacity={0.4} />
                          <stop offset="95%" stopColor="#10B981" stopOpacity={0} />
                        </linearGradient>
                        <linearGradient id="colorExams" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#3B82F6" stopOpacity={0.4} />
                          <stop offset="95%" stopColor="#3B82F6" stopOpacity={0} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" opacity={0.6} />
                      <XAxis dataKey="date" tick={{ fontSize: 11, fill: "var(--muted-foreground)" }} />
                      <YAxis tick={{ fontSize: 11, fill: "var(--muted-foreground)" }} allowDecimals={false} />
                      <Tooltip
                        contentStyle={{
                          backgroundColor: "var(--card)",
                          borderColor: "var(--border)",
                          borderRadius: "8px",
                          fontSize: "12px",
                        }}
                      />
                      <Legend wrapperStyle={{ fontSize: "12px", paddingTop: "8px" }} />
                      <Area
                        type="monotone"
                        dataKey="attempts"
                        name="Student Submissions"
                        stroke="#10B981"
                        strokeWidth={2}
                        fillOpacity={1}
                        fill="url(#colorAttempts)"
                      />
                      <Area
                        type="monotone"
                        dataKey="exams_created"
                        name="Exams Created"
                        stroke="#3B82F6"
                        strokeWidth={2}
                        fillOpacity={1}
                        fill="url(#colorExams)"
                      />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              </div>

              {/* Score Distribution Chart */}
              <div className="bg-card rounded-xl p-5 border border-border shadow-sm flex flex-col justify-between">
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <h3 className="font-bold text-base text-foreground">Score Distribution</h3>
                    <span className="text-xs text-muted-foreground font-medium">All Completed Attempts</span>
                  </div>
                  <p className="text-xs text-muted-foreground mb-4">
                    Student performance categorized across benchmark brackets
                  </p>
                </div>

                <div className="w-full h-64">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={scoreDist} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" opacity={0.6} />
                      <XAxis dataKey="range" tick={{ fontSize: 11, fill: "var(--muted-foreground)" }} />
                      <YAxis tick={{ fontSize: 11, fill: "var(--muted-foreground)" }} allowDecimals={false} />
                      <Tooltip
                        contentStyle={{
                          backgroundColor: "var(--card)",
                          borderColor: "var(--border)",
                          borderRadius: "8px",
                          fontSize: "12px",
                        }}
                        formatter={(val: any, _name: any, item: any) => [
                          `${val} students`,
                          item?.payload?.label || "Range",
                        ]}
                      />
                      <Bar dataKey="count" radius={[6, 6, 0, 0]}>
                        {scoreDist.map((_entry, index) => (
                          <Cell
                            key={`cell-${index}`}
                            fill={SCORE_DIST_COLORS[index % SCORE_DIST_COLORS.length]}
                          />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>

                <div className="grid grid-cols-4 gap-2 pt-3 border-t border-border mt-3 text-center">
                  {scoreDist.map((dist, idx) => (
                    <div key={dist.range} className="rounded-lg bg-muted/40 p-2">
                      <div className="text-[11px] text-muted-foreground truncate" title={dist.label}>
                        {dist.range}
                      </div>
                      <div className="text-sm font-bold text-foreground mt-0.5">{dist.count}</div>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Students Intelligence: Top Performers & At-Risk Students */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Top Students */}
              <div className="bg-card rounded-xl p-5 border border-border shadow-sm flex flex-col justify-between">
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <div className="flex items-center gap-2">
                      <Award className="w-5 h-5 text-amber-500" />
                      <h3 className="font-bold text-base text-foreground">Top Performing Students</h3>
                    </div>
                    <Link
                      to="/admin/students"
                      className="text-xs text-primary hover:underline font-semibold flex items-center gap-1"
                    >
                      View All <ArrowRight className="w-3.5 h-3.5" />
                    </Link>
                  </div>
                  <p className="text-xs text-muted-foreground mb-4">
                    Highest average score achieved across all attempted examinations
                  </p>
                </div>

                {topStudents.length === 0 ? (
                  <div className="py-12 text-center text-muted-foreground text-xs">
                    No student submissions evaluated yet.
                  </div>
                ) : (
                  <div className="space-y-3">
                    {topStudents.map((st, idx) => (
                      <div
                        key={st.student_id}
                        className="flex items-center justify-between p-3 rounded-xl bg-muted/40 border border-border/80 hover:bg-muted/70 transition-all"
                      >
                        <div className="flex items-center gap-3">
                          <span
                            className={`w-6 h-6 rounded-full flex items-center justify-center font-bold text-xs ${
                              idx === 0
                                ? "bg-amber-100 text-amber-800"
                                : idx === 1
                                ? "bg-slate-200 text-slate-800"
                                : idx === 2
                                ? "bg-orange-100 text-orange-800"
                                : "bg-muted text-muted-foreground"
                            }`}
                          >
                            {idx + 1}
                          </span>
                          <div>
                            <h4 className="font-semibold text-xs sm:text-sm text-foreground">
                              {st.name}
                            </h4>
                            <div className="text-[11px] text-muted-foreground flex items-center gap-1.5 mt-0.5">
                              <span>Roll: {st.roll_number}</span>
                              <span>•</span>
                              <span>{st.department}</span>
                            </div>
                          </div>
                        </div>

                        <div className="text-right">
                          <span className="text-sm font-bold text-emerald-600">
                            {st.average_score}%
                          </span>
                          <div className="text-[10px] text-muted-foreground">
                            {st.exams_taken} exam{st.exams_taken === 1 ? "" : "s"}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* At-Risk Students & Attention */}
              <div className="bg-card rounded-xl p-5 border border-border shadow-sm flex flex-col justify-between">
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <div className="flex items-center gap-2">
                      <ShieldAlert className="w-5 h-5 text-rose-500" />
                      <h3 className="font-bold text-base text-foreground">Students Requiring Attention</h3>
                    </div>
                    <Link
                      to="/admin/students"
                      className="text-xs text-primary hover:underline font-semibold flex items-center gap-1"
                    >
                      Manage Students <ArrowRight className="w-3.5 h-3.5" />
                    </Link>
                  </div>
                  <p className="text-xs text-muted-foreground mb-4">
                    Students scoring below 40% threshold or without exam attempts
                  </p>

                  {/* Tabs */}
                  <div className="flex items-center gap-2 mb-3">
                    <button
                      onClick={() => setAtRiskTab("low_score")}
                      className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                        atRiskTab === "low_score"
                          ? "bg-rose-100 text-rose-800 border border-rose-200"
                          : "bg-muted text-muted-foreground hover:text-foreground"
                      }`}
                    >
                      Low Scorers (&lt;40%) ({lowScorers.length})
                    </button>
                    <button
                      onClick={() => setAtRiskTab("unattempted")}
                      className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                        atRiskTab === "unattempted"
                          ? "bg-amber-100 text-amber-800 border border-amber-200"
                          : "bg-muted text-muted-foreground hover:text-foreground"
                      }`}
                    >
                      Zero Attempts ({unattemptedStudents.length})
                    </button>
                  </div>
                </div>

                {atRiskTab === "low_score" ? (
                  lowScorers.length === 0 ? (
                    <div className="py-10 text-center text-emerald-600 text-xs font-medium flex flex-col items-center gap-1">
                      <CheckCircle2 className="w-6 h-6 text-emerald-500" />
                      <span>Great news! No students currently below the 40% pass mark.</span>
                    </div>
                  ) : (
                    <div className="space-y-2.5">
                      {lowScorers.map((st) => (
                        <div
                          key={st.student_id}
                          className="flex items-center justify-between p-3 rounded-xl bg-rose-50/50 border border-rose-100 hover:bg-rose-50 transition-all"
                        >
                          <div>
                            <h4 className="font-semibold text-xs text-foreground">{st.name}</h4>
                            <div className="text-[11px] text-muted-foreground flex items-center gap-1.5 mt-0.5">
                              <span>Roll: {st.roll_number}</span>
                              <span>•</span>
                              <span>{st.department}</span>
                            </div>
                          </div>
                          <div className="text-right">
                            <span className="text-xs font-bold text-rose-600">
                              {st.average_score}% Avg
                            </span>
                            <div className="text-[10px] text-muted-foreground">
                              {st.exams_taken} attempt{st.exams_taken === 1 ? "" : "s"}
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  )
                ) : unattemptedStudents.length === 0 ? (
                  <div className="py-10 text-center text-emerald-600 text-xs font-medium flex flex-col items-center gap-1">
                    <CheckCircle2 className="w-6 h-6 text-emerald-500" />
                    <span>All active students have completed at least one examination.</span>
                  </div>
                ) : (
                  <div className="space-y-2.5">
                    {unattemptedStudents.map((st) => (
                      <div
                        key={st.student_id}
                        className="flex items-center justify-between p-3 rounded-xl bg-amber-50/50 border border-amber-100 hover:bg-amber-50 transition-all"
                      >
                        <div>
                          <h4 className="font-semibold text-xs text-foreground">{st.name}</h4>
                          <div className="text-[11px] text-muted-foreground flex items-center gap-1.5 mt-0.5">
                            <span>Roll: {st.roll_number}</span>
                            <span>•</span>
                            <span>{st.department}</span>
                          </div>
                        </div>
                        <span className="text-[11px] font-medium text-amber-700 bg-amber-100 px-2 py-0.5 rounded">
                          0 Exams Taken
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>

            {/* Faculty Contributors & Upcoming Exams (2 columns) */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Top Faculty */}
              <div className="bg-card rounded-xl p-5 border border-border shadow-sm flex flex-col justify-between">
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <div className="flex items-center gap-2">
                      <UserCheck className="w-5 h-5 text-indigo-500" />
                      <h3 className="font-bold text-base text-foreground">Faculty Exam Contributors</h3>
                    </div>
                    <Link
                      to="/admin/faculty"
                      className="text-xs text-primary hover:underline font-semibold flex items-center gap-1"
                    >
                      Manage Faculty <ArrowRight className="w-3.5 h-3.5" />
                    </Link>
                  </div>
                  <p className="text-xs text-muted-foreground mb-4">
                    Faculty members with published exams and student reach
                  </p>
                </div>

                {topFaculty.length === 0 ? (
                  <div className="py-10 text-center text-muted-foreground text-xs">
                    No faculty members found.
                  </div>
                ) : (
                  <div className="space-y-3">
                    {topFaculty.map((fac) => (
                      <div
                        key={fac.faculty_id}
                        className="flex items-center justify-between p-3 rounded-xl bg-muted/40 border border-border hover:bg-muted/70 transition-all"
                      >
                        <div>
                          <h4 className="font-semibold text-xs sm:text-sm text-foreground">
                            {fac.name}
                          </h4>
                          <div className="text-[11px] text-muted-foreground flex items-center gap-1.5 mt-0.5">
                            <span>{fac.department}</span>
                            <span>•</span>
                            <span>{fac.email}</span>
                          </div>
                        </div>
                        <div className="text-right">
                          <div className="text-xs font-bold text-foreground">
                            {fac.published_exams} published / {fac.total_exams} total
                          </div>
                          <div className="text-[10px] text-muted-foreground">
                            {fac.total_attempts} student submissions
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Upcoming Exams */}
              <div className="bg-card rounded-xl p-5 border border-border shadow-sm flex flex-col justify-between">
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <div className="flex items-center gap-2">
                      <Calendar className="w-5 h-5 text-blue-500" />
                      <h3 className="font-bold text-base text-foreground">Upcoming & Scheduled Exams</h3>
                    </div>
                    <Link
                      to="/admin/exams"
                      className="text-xs text-primary hover:underline font-semibold flex items-center gap-1"
                    >
                      All Exams <ArrowRight className="w-3.5 h-3.5" />
                    </Link>
                  </div>
                  <p className="text-xs text-muted-foreground mb-4">
                    Exams queued for administration
                  </p>
                </div>

                {upcomingExams.length === 0 ? (
                  <div className="py-10 text-center text-muted-foreground text-xs">
                    No upcoming exams scheduled.
                  </div>
                ) : (
                  <div className="space-y-3">
                    {upcomingExams.map((ex) => (
                      <div
                        key={ex.id}
                        className="flex items-center justify-between p-3 rounded-xl bg-muted/40 border border-border hover:bg-muted/70 transition-all"
                      >
                        <div>
                          <h4 className="font-semibold text-xs sm:text-sm text-foreground">
                            {ex.title}
                          </h4>
                          <div className="text-[11px] text-muted-foreground flex items-center gap-1.5 mt-0.5">
                            <span className="font-medium text-primary">{ex.department}</span>
                            <span>•</span>
                            <span>By {ex.faculty_name}</span>
                          </div>
                        </div>
                        <div className="text-right">
                          <div className="text-xs font-semibold text-foreground flex items-center gap-1">
                            <Clock className="w-3 h-3 text-muted-foreground" />
                            {formatDateTime(ex.starts_at)}
                          </div>
                          <div className="text-[10px] text-muted-foreground">
                            {ex.duration_minutes}m • {ex.total_marks} marks
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>

            {/* Real Recent Activity Feed */}
            <div className="bg-card rounded-xl p-5 border border-border shadow-sm">
              <div className="flex items-center justify-between mb-1">
                <div className="flex items-center gap-2">
                  <Activity className="w-5 h-5 text-primary" />
                  <h3 className="font-bold text-base text-foreground">Recent Institutional Activity</h3>
                </div>
                <span className="text-xs text-muted-foreground">Live Audit Trail</span>
              </div>
              <p className="text-xs text-muted-foreground mb-4">
                Real-time events recorded across users, examinations, and submissions
              </p>

              {recentActivity.length === 0 ? (
                <div className="py-8 text-center text-muted-foreground text-xs">
                  No activity recorded recently.
                </div>
              ) : (
                <div className="divide-y divide-border">
                  {recentActivity.map((act, i) => (
                    <div
                      key={i}
                      className="py-3 flex items-start justify-between gap-3 text-xs hover:bg-muted/30 px-2 rounded-lg transition-colors"
                    >
                      <div className="flex items-start gap-3">
                        <div
                          className={`w-7 h-7 rounded-full flex items-center justify-center shrink-0 mt-0.5 ${
                            act.type === "exam_submitted"
                              ? "bg-emerald-100 text-emerald-700"
                              : act.type === "exam_created"
                              ? "bg-purple-100 text-purple-700"
                              : act.type === "student_registered"
                              ? "bg-blue-100 text-blue-700"
                              : "bg-indigo-100 text-indigo-700"
                          }`}
                        >
                          {act.type === "exam_submitted" ? (
                            <CheckCircle2 className="w-3.5 h-3.5" />
                          ) : act.type === "exam_created" ? (
                            <FileText className="w-3.5 h-3.5" />
                          ) : act.type === "student_registered" ? (
                            <GraduationCap className="w-3.5 h-3.5" />
                          ) : (
                            <Users className="w-3.5 h-3.5" />
                          )}
                        </div>
                        <div>
                          <div className="font-medium text-foreground">{act.title}</div>
                          <div className="text-[11px] text-muted-foreground mt-0.5">
                            {act.department} • Initiated by {act.actor}
                          </div>
                        </div>
                      </div>
                      <div className="text-[11px] text-muted-foreground font-mono shrink-0">
                        {formatTimeAgo(act.timestamp)}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Quick Actions Shortcuts */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              <Link
                to="/admin/students"
                className="bg-card rounded-xl p-4 border border-border hover:border-primary/40 hover:shadow-sm transition-all group flex items-start gap-3"
              >
                <div className="w-10 h-10 rounded-lg bg-blue-50 text-blue-600 flex items-center justify-center shrink-0 group-hover:scale-105 transition-transform">
                  <GraduationCap className="w-5 h-5" />
                </div>
                <div>
                  <h4 className="font-semibold text-sm text-foreground group-hover:text-primary transition-colors flex items-center gap-1">
                    Manage Students <ArrowRight className="w-3.5 h-3.5 opacity-0 group-hover:opacity-100 transition-opacity" />
                  </h4>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    Enrolled records, performance histories, departments
                  </p>
                </div>
              </Link>

              <Link
                to="/admin/faculty"
                className="bg-card rounded-xl p-4 border border-border hover:border-primary/40 hover:shadow-sm transition-all group flex items-start gap-3"
              >
                <div className="w-10 h-10 rounded-lg bg-indigo-50 text-indigo-600 flex items-center justify-center shrink-0 group-hover:scale-105 transition-transform">
                  <Users className="w-5 h-5" />
                </div>
                <div>
                  <h4 className="font-semibold text-sm text-foreground group-hover:text-primary transition-colors flex items-center gap-1">
                    Manage Faculty <ArrowRight className="w-3.5 h-3.5 opacity-0 group-hover:opacity-100 transition-opacity" />
                  </h4>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    Faculty roster, credentials, assigned subjects
                  </p>
                </div>
              </Link>

              <Link
                to="/admin/exams"
                className="bg-card rounded-xl p-4 border border-border hover:border-primary/40 hover:shadow-sm transition-all group flex items-start gap-3"
              >
                <div className="w-10 h-10 rounded-lg bg-purple-50 text-purple-600 flex items-center justify-center shrink-0 group-hover:scale-105 transition-transform">
                  <FileText className="w-5 h-5" />
                </div>
                <div>
                  <h4 className="font-semibold text-sm text-foreground group-hover:text-primary transition-colors flex items-center gap-1">
                    Exam Repository <ArrowRight className="w-3.5 h-3.5 opacity-0 group-hover:opacity-100 transition-opacity" />
                  </h4>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    Exam status, schedule parameters, publishing
                  </p>
                </div>
              </Link>

              <Link
                to="/admin/questions"
                className="bg-card rounded-xl p-4 border border-border hover:border-primary/40 hover:shadow-sm transition-all group flex items-start gap-3"
              >
                <div className="w-10 h-10 rounded-lg bg-amber-50 text-amber-600 flex items-center justify-center shrink-0 group-hover:scale-105 transition-transform">
                  <Layers className="w-5 h-5" />
                </div>
                <div>
                  <h4 className="font-semibold text-sm text-foreground group-hover:text-primary transition-colors flex items-center gap-1">
                    Question Bank <ArrowRight className="w-3.5 h-3.5 opacity-0 group-hover:opacity-100 transition-opacity" />
                  </h4>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    Central institutional questions and syllabus bank
                  </p>
                </div>
              </Link>
            </div>
          </>
        )}

        {/* Live Roster Modal Dialog */}
        {selectedExamForRoster && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6 bg-background/80 backdrop-blur-xs animate-in fade-in duration-200">
            <div className="bg-card w-full max-w-4xl max-h-[90vh] rounded-2xl border border-border shadow-2xl flex flex-col overflow-hidden">
              {/* Modal Header */}
              <div className="p-5 border-b border-border flex items-start justify-between gap-4 bg-muted/30">
                <div>
                  <div className="flex flex-wrap items-center gap-2 mb-1">
                    <span className="text-[11px] font-semibold px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800 border border-emerald-200">
                      {selectedExamForRoster.department}
                    </span>
                    <span className="inline-flex items-center gap-1 text-[11px] font-semibold px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200">
                      <ShieldCheck className="w-3 h-3 text-emerald-600" />
                      {profile?.institution_name || "Institution Isolated"}
                    </span>
                    <span className="text-xs font-mono font-medium text-emerald-700 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-950/40 px-2 py-0.5 rounded-full border border-emerald-200 flex items-center gap-1">
                      <Clock className="w-3 h-3 animate-pulse" />
                      {formatLiveCountdown(selectedExamForRoster)}
                    </span>
                  </div>
                  <h3 className="text-lg font-bold text-foreground">
                    {selectedExamForRoster.title} — Live Student Roster
                  </h3>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    Faculty: {selectedExamForRoster.faculty_name} • Total Marks: {selectedExamForRoster.total_marks} • Real-time attendance & submission status
                  </p>
                </div>
                <button
                  type="button"
                  onClick={closeLiveRoster}
                  className="p-1.5 rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted transition-colors cursor-pointer"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              {/* Metrics Summary Strip */}
              <div className="p-4 bg-muted/20 border-b border-border grid grid-cols-2 sm:grid-cols-5 gap-2 text-center">
                <div className="bg-card p-2 rounded-lg border border-border/80">
                  <div className="text-[10px] text-blue-600 font-semibold uppercase">Eligible</div>
                  <div className="text-base font-bold text-foreground">
                    {rosterData?.metrics.eligible_count ?? selectedExamForRoster.eligible_count}
                  </div>
                </div>
                <div className="bg-card p-2 rounded-lg border border-border/80">
                  <div className="text-[10px] text-amber-600 font-semibold uppercase">In Progress</div>
                  <div className="text-base font-bold text-amber-600">
                    {rosterData?.metrics.in_progress_count ?? selectedExamForRoster.in_progress_count}
                  </div>
                </div>
                <div className="bg-card p-2 rounded-lg border border-border/80">
                  <div className="text-[10px] text-emerald-600 font-semibold uppercase">Submitted</div>
                  <div className="text-base font-bold text-emerald-600">
                    {rosterData?.metrics.submitted_count ?? selectedExamForRoster.submitted_count}
                  </div>
                </div>
                <div className="bg-card p-2 rounded-lg border border-border/80">
                  <div className="text-[10px] text-muted-foreground font-semibold uppercase">Not Started</div>
                  <div className="text-base font-bold text-muted-foreground">
                    {rosterData?.metrics.not_started_count ?? selectedExamForRoster.not_started_count}
                  </div>
                </div>
                <div className="bg-card p-2 rounded-lg border border-border/80 col-span-2 sm:col-span-1">
                  <div className="text-[10px] text-rose-600 font-semibold uppercase">Ineligible</div>
                  <div className="text-base font-bold text-rose-600">
                    {rosterData?.metrics.ineligible_attempts ?? selectedExamForRoster.ineligible_attempts}
                  </div>
                </div>
              </div>

              {/* Filters & Search Toolbar */}
              <div className="p-4 border-b border-border flex flex-col sm:flex-row items-center justify-between gap-3 bg-card">
                {/* Status Tabs */}
                <div className="flex flex-wrap items-center gap-1 w-full sm:w-auto">
                  {(["all", "not_started", "in_progress", "submitted"] as const).map((st) => (
                    <button
                      key={st}
                      type="button"
                      onClick={() => handleRosterFilterChange(st)}
                      className={`px-3 py-1 rounded-lg text-xs font-medium capitalize transition-all cursor-pointer ${
                        rosterStatusFilter === st
                          ? "bg-primary text-white font-semibold shadow-xs"
                          : "text-muted-foreground hover:bg-muted"
                      }`}
                    >
                      {st.replace("_", " ")}
                    </button>
                  ))}
                  {(rosterData?.ineligible_attempts?.length || 0) > 0 && (
                    <button
                      type="button"
                      onClick={() => handleRosterFilterChange("ineligible")}
                      className={`px-3 py-1 rounded-lg text-xs font-medium transition-all cursor-pointer ${
                        rosterStatusFilter === "ineligible"
                          ? "bg-rose-600 text-white font-semibold shadow-xs"
                          : "text-rose-600 hover:bg-rose-50"
                      }`}
                    >
                      Ineligible ({rosterData?.ineligible_attempts.length})
                    </button>
                  )}
                </div>

                {/* Search Input */}
                <div className="relative w-full sm:w-64">
                  <Search className="w-3.5 h-3.5 text-muted-foreground absolute left-3 top-1/2 -translate-y-1/2" />
                  <input
                    type="text"
                    placeholder="Search name, roll number..."
                    value={rosterSearch}
                    onChange={(e) => handleRosterSearchChange(e.target.value)}
                    className="w-full pl-8 pr-3 py-1.5 text-xs rounded-lg border border-border bg-muted/40 focus:bg-background focus:outline-hidden focus:ring-1 focus:ring-primary"
                  />
                  {rosterSearch && (
                    <button
                      type="button"
                      onClick={() => handleRosterSearchChange("")}
                      className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground cursor-pointer"
                    >
                      <X className="w-3 h-3" />
                    </button>
                  )}
                </div>
              </div>

              {/* Roster Table Content */}
              <div className="flex-1 overflow-y-auto p-4 min-h-[260px]">
                {rosterLoading ? (
                  <div className="flex flex-col items-center justify-center py-12 text-muted-foreground gap-2">
                    <RefreshCw className="w-6 h-6 animate-spin text-primary" />
                    <span className="text-xs">Loading live roster...</span>
                  </div>
                ) : rosterError ? (
                  <div className="p-4 rounded-xl bg-destructive/10 text-destructive text-xs border border-destructive/20 text-center">
                    {rosterError}
                  </div>
                ) : rosterStatusFilter === "ineligible" ? (
                  /* Ineligible Attempts Tab */
                  <div>
                    <div className="p-3 mb-3 rounded-lg bg-amber-50 dark:bg-amber-950/30 border border-amber-200 text-xs text-amber-800 dark:text-amber-200">
                      These attempts were submitted by students outside the eligible cohort (different institution or inactive account). They are isolated and excluded from institutional invariant metrics.
                    </div>
                    {(!rosterData?.ineligible_attempts || rosterData.ineligible_attempts.length === 0) ? (
                      <div className="text-center py-8 text-xs text-muted-foreground">
                        No ineligible attempts recorded.
                      </div>
                    ) : (
                      <div className="divide-y divide-border">
                        {rosterData.ineligible_attempts.map((att) => (
                          <div key={att.attempt_id} className="py-2.5 flex items-center justify-between text-xs">
                            <div>
                              <div className="font-semibold text-foreground">{att.student_name}</div>
                              <div className="text-[11px] text-muted-foreground">
                                Roll: {att.student_roll || "N/A"} • Reason: <span className="text-rose-600 font-medium">{att.reason}</span>
                              </div>
                            </div>
                            <div className="text-right">
                              <span className="px-2 py-0.5 rounded text-[10px] font-medium bg-rose-50 text-rose-700 border border-rose-200">
                                Status: {att.status}
                              </span>
                              {att.score !== null && (
                                <div className="text-[11px] font-bold mt-0.5">{att.score} pts</div>
                              )}
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                ) : (!rosterData?.roster || rosterData.roster.length === 0) ? (
                  <div className="text-center py-12 text-muted-foreground text-xs">
                    No students match the current criteria.
                  </div>
                ) : (
                  <table className="w-full text-xs text-left">
                    <thead>
                      <tr className="border-b border-border text-muted-foreground font-semibold">
                        <th className="pb-2">Student</th>
                        <th className="pb-2">Roll Number</th>
                        <th className="pb-2">Department</th>
                        <th className="pb-2">Live Status</th>
                        <th className="pb-2 text-right">Score</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border/60">
                      {rosterData.roster.map((s) => (
                        <tr key={s.student_id} className="hover:bg-muted/30 transition-colors">
                          <td className="py-2.5 font-medium text-foreground">
                            <div>{s.full_name}</div>
                            <div className="text-[10px] text-muted-foreground">{s.email}</div>
                          </td>
                          <td className="py-2.5 font-mono text-muted-foreground">{s.roll_number || "—"}</td>
                          <td className="py-2.5 text-muted-foreground">{s.department}</td>
                          <td className="py-2.5">
                            {s.status === "submitted" && (
                              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-100 text-emerald-800">
                                <CheckCircle2 className="w-3 h-3 text-emerald-600" />
                                Submitted
                              </span>
                            )}
                            {s.status === "in_progress" && (
                              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-amber-100 text-amber-800">
                                <span className="w-1.5 h-1.5 rounded-full bg-amber-500 animate-ping" />
                                In Progress
                              </span>
                            )}
                            {s.status === "not_started" && (
                              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-muted text-muted-foreground border border-border">
                                Not Started
                              </span>
                            )}
                          </td>
                          <td className="py-2.5 text-right font-medium">
                            {s.score !== null && s.score !== undefined ? `${s.score} pts` : "—"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>

              {/* Modal Footer & Pagination */}
              {rosterData && rosterStatusFilter !== "ineligible" && rosterData.pagination.total_pages > 1 && (
                <div className="p-3 border-t border-border flex items-center justify-between text-xs bg-muted/20">
                  <span className="text-muted-foreground">
                    Page {rosterData.pagination.page} of {rosterData.pagination.total_pages} ({rosterData.pagination.total_items} students)
                  </span>
                  <div className="flex items-center gap-1.5">
                    <button
                      type="button"
                      disabled={rosterData.pagination.page <= 1 || rosterLoading}
                      onClick={() => handleRosterPageChange(rosterData.pagination.page - 1)}
                      className="p-1 rounded-md border border-border bg-card hover:bg-muted disabled:opacity-40 transition-all cursor-pointer"
                    >
                      <ChevronLeft className="w-4 h-4" />
                    </button>
                    <button
                      type="button"
                      disabled={rosterData.pagination.page >= rosterData.pagination.total_pages || rosterLoading}
                      onClick={() => handleRosterPageChange(rosterData.pagination.page + 1)}
                      className="p-1 rounded-md border border-border bg-card hover:bg-muted disabled:opacity-40 transition-all cursor-pointer"
                    >
                      <ChevronRight className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}

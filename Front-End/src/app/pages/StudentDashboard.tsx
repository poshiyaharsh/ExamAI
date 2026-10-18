import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  AlertCircle,
  ArrowRight,
  Award,
  BookOpen,
  Calendar,
  CheckCircle,
  Clock,
  FileText,
  Hourglass,
  LayoutDashboard,
  PlayCircle,
  RefreshCw,
  Settings,
  TrendingDown,
  TrendingUp,
  XCircle,
} from "lucide-react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip as RechartsTooltip,
  XAxis,
  YAxis,
} from "recharts";
import { DashboardLayout } from "../components/DashboardLayout";
import { AttemptStatusBadge } from "../components/AttemptStatusBadge";
import {
  Tooltip as UITooltip,
  TooltipContent,
  TooltipProvider as UITooltipProvider,
  TooltipTrigger,
} from "../components/ui/tooltip";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "../components/ui/popover";
import {
  studentDashboardApi,
  type StudentDashboardData,
  type StudentDashboardRecentResult,
} from "../../services/api";

function formatShortDate(dateStr: string): string {
  try {
    const d = new Date(dateStr);
    return d.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
  } catch {
    return dateStr;
  }
}

function formatFullDateTime(dateStr: string): string {
  try {
    const d = new Date(dateStr);
    return d.toLocaleString("en-US", {
      day: "numeric",
      month: "short",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  } catch {
    return dateStr;
  }
}

function getOutcomeBarColor(item: StudentDashboardRecentResult): string {
  const code = (item.result_status?.status_code || (item.is_passed ? "pass" : "fail")).toLowerCase();
  switch (code) {
    case "pass":
      return "bg-emerald-500";
    case "fail":
      return "bg-rose-500";
    case "pending_grading":
      return "bg-amber-500";
    case "auto_submitted":
      return item.is_passed ? "bg-amber-500" : "bg-rose-500";
    default:
      return "bg-primary";
  }
}

const menuItems = [
  { icon: LayoutDashboard, label: "Dashboard", path: "/student" },
  { icon: FileText, label: "Exams", path: "/student/exams" },
  { icon: TrendingUp, label: "Performance", path: "/student/performance" },
  { icon: Settings, label: "Settings", path: "/student/settings" },
];

function getStatusBadge(status: string) {
  switch (status) {
    case "Excellent":
      return "bg-emerald-50 text-emerald-700 border-emerald-200";
    case "Good":
      return "bg-blue-50 text-blue-700 border-blue-200";
    case "Average":
      return "bg-amber-50 text-amber-700 border-amber-200";
    case "Needs Improvement":
      return "bg-rose-50 text-rose-700 border-rose-200";
    default:
      return "bg-muted text-muted-foreground border-border";
  }
}

function formatExamWindow(startsAt: string | null, endsAt: string | null, isOpen: boolean) {
  if (isOpen) {
    if (endsAt) {
      return `Open now · Closes ${new Date(endsAt).toLocaleDateString()} ${new Date(endsAt).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`;
    }
    return "Open now · Available anytime";
  }
  if (startsAt) {
    return `Opens ${new Date(startsAt).toLocaleDateString()} ${new Date(startsAt).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`;
  }
  return "Scheduled";
}

export function StudentDashboard() {
  const [data, setData] = useState<StudentDashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const loadDashboard = async () => {
    try {
      setLoading(true);
      setError("");
      const res = await studentDashboardApi.getDashboard();
      setData(res.data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load student dashboard.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadDashboard();
  }, []);

  const profile = data?.profile;
  const stats = data?.stats;
  const ongoingExams = data?.ongoing_exams || [];
  const upcomingExams = data?.upcoming_exams || [];
  const recentResults = data?.recent_results || [];
  const trend = data?.performance_trend || [];
  const strengths = data?.subject_strengths;

  return (
    <DashboardLayout menuItems={menuItems} userRole="Student">
      <div className="space-y-6">
        {/* Loading Skeleton */}
        {loading && (
          <div className="space-y-6 animate-pulse">
            <div className="h-20 bg-muted/60 rounded-xl" />
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
            {/* Personalized Greeting Header */}
            <div className="bg-gradient-to-r from-primary/10 via-secondary/10 to-transparent border border-primary/20 rounded-2xl p-5 sm:p-6 flex flex-col md:flex-row md:items-center justify-between gap-4">
              <div className="space-y-1">
                <div className="flex items-center gap-2 flex-wrap">
                  <h1 className="text-2xl sm:text-3xl font-bold text-foreground">
                    Welcome back, {profile?.first_name || profile?.name}!
                  </h1>
                  {profile?.department && (
                    <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-primary/15 text-primary border border-primary/25">
                      {profile.department}
                    </span>
                  )}
                </div>
                <p className="text-xs sm:text-sm text-muted-foreground">
                  {profile?.roll_number ? `Roll No: ${profile.roll_number}` : ""}
                  {profile?.year_semester ? ` · ${profile.year_semester}` : ""}
                </p>
              </div>

              {/* Quick Action Buttons */}
              <div className="flex items-center gap-2 shrink-0">
                <Link
                  to="/student/exams"
                  className="px-3.5 py-2 rounded-lg bg-gradient-to-r from-primary to-secondary text-white text-xs sm:text-sm font-medium shadow-sm hover:opacity-90 transition-all flex items-center gap-1.5"
                >
                  <FileText className="w-4 h-4" />
                  View All Exams
                </Link>
                <Link
                  to="/student/performance"
                  className="px-3.5 py-2 rounded-lg border border-border bg-white text-foreground text-xs sm:text-sm font-medium hover:bg-muted/50 transition-colors flex items-center gap-1.5 shadow-2xs"
                >
                  <TrendingUp className="w-4 h-4 text-primary" />
                  Analytics
                </Link>
              </div>
            </div>

            {/* Quick Stats Grid */}
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3.5">
              <div className="bg-white rounded-xl p-4 shadow-2xs border border-border">
                <div className="text-xs text-muted-foreground font-medium mb-1">Available Exams</div>
                <div className="text-xl sm:text-2xl font-bold text-foreground">{stats?.total_available}</div>
                <div className="text-[11px] text-muted-foreground mt-1">In your department</div>
              </div>

              <div className="bg-white rounded-xl p-4 shadow-2xs border border-border">
                <div className="text-xs text-muted-foreground font-medium mb-1">Attempted</div>
                <div className="text-xl sm:text-2xl font-bold text-emerald-600">{stats?.exams_attempted}</div>
                <div className="text-[11px] text-muted-foreground mt-1 flex items-center gap-1">
                  <CheckCircle className="w-3 h-3 text-emerald-600" /> Completed
                </div>
              </div>

              <div className="bg-white rounded-xl p-4 shadow-2xs border border-border">
                <div className="text-xs text-muted-foreground font-medium mb-1">Pending</div>
                <div className="text-xl sm:text-2xl font-bold text-amber-600">{stats?.exams_pending}</div>
                <div className="text-[11px] text-muted-foreground mt-1 flex items-center gap-1">
                  <Hourglass className="w-3 h-3 text-amber-600" /> Remaining
                </div>
              </div>

              <div className="bg-white rounded-xl p-4 shadow-2xs border border-border">
                <div className="text-xs text-muted-foreground font-medium mb-1">Average Score</div>
                <div className="text-xl sm:text-2xl font-bold text-primary">
                  {stats?.average_score !== null && stats?.average_score !== undefined ? `${stats.average_score}%` : "N/A"}
                </div>
                <div className="mt-1">
                  <span className={`inline-flex items-center px-1.5 py-0.2 rounded-full text-[10px] font-semibold border ${getStatusBadge(stats?.performance_status || "")}`}>
                    {stats?.performance_status || "N/A"}
                  </span>
                </div>
              </div>

              <div className="bg-white rounded-xl p-4 shadow-2xs border border-border">
                <div className="text-xs text-muted-foreground font-medium mb-1">Highest Score</div>
                <div className="text-xl sm:text-2xl font-bold text-foreground">
                  {stats?.highest_score !== null && stats?.highest_score !== undefined ? `${stats.highest_score}%` : "N/A"}
                </div>
                <div className="text-[11px] text-muted-foreground mt-1 flex items-center gap-1">
                  <Award className="w-3 h-3 text-primary" /> Best exam
                </div>
              </div>

              <div className="bg-white rounded-xl p-4 shadow-2xs border border-border">
                <div className="text-xs text-muted-foreground font-medium mb-1">Pass Rate</div>
                <div className="text-xl sm:text-2xl font-bold text-foreground">
                  {stats?.pass_rate !== null && stats?.pass_rate !== undefined ? `${stats.pass_rate}%` : "N/A"}
                </div>
                <div className="text-[11px] text-muted-foreground mt-1">
                  {stats?.pass_count} passed · {stats?.fail_count} failed
                </div>
              </div>
            </div>

            {/* Ongoing Exams Highlight (if any active exams ready to take) */}
            {ongoingExams.length > 0 && (
              <div className="bg-white rounded-xl border border-primary/30 shadow-xs overflow-hidden">
                <div className="p-4 sm:p-5 border-b border-border bg-primary/5 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse" />
                    <h3 className="font-bold text-foreground text-sm sm:text-base">Ongoing Exams — Open Now</h3>
                  </div>
                  <span className="text-xs font-semibold text-primary bg-primary/10 px-2 py-0.5 rounded-full">
                    {ongoingExams.length} Available
                  </span>
                </div>
                <div className="p-4 sm:p-5 divide-y divide-border/60">
                  {ongoingExams.map((exam) => (
                    <div key={exam.id} className="py-3 first:pt-0 last:pb-0 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                      <div className="space-y-1">
                        <div className="flex items-center gap-2 flex-wrap">
                          <h4 className="font-semibold text-foreground text-sm sm:text-base">{exam.title}</h4>
                          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-medium bg-muted text-foreground border border-border">
                            {exam.subject}
                          </span>
                        </div>
                        <div className="flex items-center gap-3 text-xs text-muted-foreground flex-wrap">
                          <span className="flex items-center gap-1"><Clock className="w-3.5 h-3.5" /> {exam.duration_minutes} min</span>
                          <span>•</span>
                          <span>{exam.total_marks} marks</span>
                          <span>•</span>
                          <span className="text-emerald-700 font-medium">{formatExamWindow(exam.starts_at, exam.ends_at, exam.is_open)}</span>
                        </div>
                      </div>
                      <Link to={`/student/exams/${exam.id}/take`}>
                        <button className="w-full sm:w-auto px-4 py-2 rounded-lg bg-gradient-to-r from-primary to-secondary text-white font-medium text-xs sm:text-sm hover:opacity-90 shadow-sm transition-all flex items-center justify-center gap-1.5 shrink-0">
                          <PlayCircle className="w-4 h-4" />
                          Start Exam
                        </button>
                      </Link>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* 2-Column Section: Upcoming Exams & Performance Trend */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Upcoming Exams Card */}
              <div className="bg-white rounded-xl shadow-2xs border border-border overflow-hidden flex flex-col">
                <div className="p-4 sm:p-5 border-b border-border flex items-center justify-between">
                  <div>
                    <h3 className="font-semibold text-foreground text-sm sm:text-base">Upcoming Exams</h3>
                    <p className="text-xs text-muted-foreground">Department exams on your schedule</p>
                  </div>
                  <Link to="/student/exams" className="text-xs font-medium text-primary hover:underline flex items-center gap-1">
                    All exams <ArrowRight className="w-3 h-3" />
                  </Link>
                </div>
                <div className="p-4 sm:p-5 flex-1 flex flex-col justify-center">
                  {upcomingExams.length === 0 ? (
                    <div className="text-center py-8">
                      <Calendar className="w-10 h-10 text-muted-foreground/40 mx-auto mb-2" />
                      <p className="text-xs sm:text-sm text-muted-foreground">
                        No upcoming exams scheduled for {profile?.department || "your department"}.
                      </p>
                    </div>
                  ) : (
                    <div className="divide-y divide-border space-y-3">
                      {upcomingExams.map((exam) => (
                        <div key={exam.id} className="pt-3 first:pt-0 flex items-center justify-between gap-3">
                          <div className="space-y-0.5">
                            <h4 className="font-semibold text-foreground text-xs sm:text-sm">{exam.title}</h4>
                            <p className="text-[11px] text-muted-foreground">
                              {exam.subject} · {exam.duration_minutes} min · {exam.total_marks} marks
                            </p>
                            <p className="text-[11px] text-primary font-medium">
                              {formatExamWindow(exam.starts_at, exam.ends_at, exam.is_open)}
                            </p>
                          </div>
                          {exam.is_open ? (
                            <Link to={`/student/exams/${exam.id}/take`}>
                              <button className="px-3 py-1.5 rounded-lg bg-primary text-white text-xs font-medium hover:opacity-90 shadow-2xs transition-all shrink-0">
                                Start
                              </button>
                            </Link>
                          ) : (
                            <span className="px-2.5 py-1 rounded-lg bg-muted text-muted-foreground text-xs font-medium border border-border shrink-0">
                              Upcoming
                            </span>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>

              {/* Performance Trend Mini-Chart */}
              <div className="bg-white rounded-xl shadow-2xs border border-border overflow-hidden flex flex-col">
                <div className="p-4 sm:p-5 border-b border-border flex items-center justify-between">
                  <div>
                    <h3 className="font-semibold text-foreground text-sm sm:text-base">Recent Score Progression</h3>
                    <p className="text-xs text-muted-foreground">Score percentage trend over completed attempts</p>
                  </div>
                  <Link to="/student/performance" className="text-xs font-medium text-primary hover:underline flex items-center gap-1">
                    Details <ArrowRight className="w-3 h-3" />
                  </Link>
                </div>
                <div className="p-4 sm:p-5 flex-1 flex flex-col justify-center">
                  {trend.length === 0 ? (
                    <div className="text-center py-8">
                      <TrendingUp className="w-10 h-10 text-muted-foreground/40 mx-auto mb-2" />
                      <p className="text-xs sm:text-sm text-muted-foreground">
                        You haven't taken any exams yet. Complete an exam to view your trend chart.
                      </p>
                    </div>
                  ) : (
                    <div className="h-52 w-full">
                      <ResponsiveContainer width="100%" height="100%">
                        <LineChart data={trend} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
                          <CartesianGrid strokeDasharray="3 3" stroke="#F3F4F6" />
                          <XAxis dataKey="date" stroke="#6B7280" fontSize={11} tickLine={false} />
                          <YAxis domain={[0, 100]} stroke="#6B7280" fontSize={11} tickLine={false} unit="%" />
                          <RechartsTooltip
                            formatter={(val: any) => [`${val}%`, "Percentage"]}
                            labelFormatter={(l) => `Date: ${l}`}
                            contentStyle={{ backgroundColor: "#FFFFFF", borderRadius: "8px", borderColor: "#E5E7EB", fontSize: "12px" }}
                          />
                          <Line
                            type="monotone"
                            dataKey="percentage"
                            stroke="#4F46E5"
                            strokeWidth={2.5}
                            dot={{ r: 4, fill: "#4F46E5", strokeWidth: 2, stroke: "#FFFFFF" }}
                          />
                        </LineChart>
                      </ResponsiveContainer>
                    </div>
                  )}
                </div>
              </div>
            </div>

            {/* Subject Strengths Callouts */}
            {(strengths?.strongest || strengths?.weakest) && (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {strengths.strongest && (
                  <div className="bg-emerald-50/50 border border-emerald-200/60 rounded-xl p-4 flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-lg bg-emerald-100 flex items-center justify-center text-emerald-700 shrink-0">
                        <TrendingUp className="w-5 h-5" />
                      </div>
                      <div>
                        <div className="text-xs text-emerald-800 font-semibold uppercase tracking-wider">Strongest Subject</div>
                        <h4 className="font-bold text-foreground text-sm sm:text-base">{strengths.strongest.subject}</h4>
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="text-xl font-bold text-emerald-700">{strengths.strongest.average_score}%</div>
                      <div className="text-[11px] text-muted-foreground">{strengths.strongest.count} exams</div>
                    </div>
                  </div>
                )}

                {strengths.weakest && (
                  <div className="bg-amber-50/50 border border-amber-200/60 rounded-xl p-4 flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-lg bg-amber-100 flex items-center justify-center text-amber-700 shrink-0">
                        <TrendingDown className="w-5 h-5" />
                      </div>
                      <div>
                        <div className="text-xs text-amber-800 font-semibold uppercase tracking-wider">Needs Focus</div>
                        <h4 className="font-bold text-foreground text-sm sm:text-base">{strengths.weakest.subject}</h4>
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="text-xl font-bold text-amber-700">{strengths.weakest.average_score}%</div>
                      <div className="text-[11px] text-muted-foreground">{strengths.weakest.count} exams</div>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Recent Results Table / Cards */}
            <div id="recent-exam-results" className="bg-white rounded-xl shadow-2xs border border-border overflow-hidden min-w-0 max-w-full">
              <div className="p-4 sm:p-5 border-b border-border flex items-center justify-between gap-3">
                <div>
                  <h3 className="font-semibold text-foreground text-sm sm:text-base">Recent Exam Results</h3>
                  <p className="text-xs text-muted-foreground">Your most recently completed examinations</p>
                </div>
                {recentResults.length > 0 && (
                  <Link to="/student/performance" className="text-xs font-semibold text-primary hover:underline flex items-center gap-1 shrink-0">
                    View all in Performance <ArrowRight className="w-3 h-3" />
                  </Link>
                )}
              </div>

              {recentResults.length === 0 ? (
                <div className="p-10 text-center space-y-2">
                  <FileText className="w-10 h-10 text-muted-foreground/40 mx-auto" />
                  <h4 className="text-sm font-semibold text-foreground">You haven't taken any exams yet</h4>
                  <p className="text-xs text-muted-foreground max-w-sm mx-auto">
                    Start an available exam above to see your scores and detailed performance analytics here.
                  </p>
                </div>
              ) : (
                <>
                  {/* Desktop Table (Fixed layout, nowrap values, rich status badges, zero horizontal scroll) */}
                  <div className="hidden sm:block overflow-x-hidden">
                    <table className="table-fixed w-full text-left text-xs sm:text-sm" role="table" aria-label="Recent Exam Results">
                      <thead className="sticky top-0 z-10 border-b border-border bg-muted/40 backdrop-blur-xs text-muted-foreground font-medium text-xs">
                        <tr>
                          <th scope="col" className="py-3 px-3 w-[29%] text-left font-semibold">Exam</th>
                          <th scope="col" className="py-3 px-2 w-[11%] text-right font-semibold">Marks</th>
                          <th scope="col" className="py-3 px-3 w-[14%] text-left font-semibold">Percentage</th>
                          <th scope="col" className="py-3 px-2 w-[11%] text-left font-semibold">Date</th>
                          <th scope="col" className="py-3 px-3 w-[21%] text-left font-semibold">Status</th>
                          <th scope="col" className="py-3 px-3 w-[14%] text-right font-semibold">Action</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-border">
                        {recentResults.slice(0, 5).map((item) => (
                          <tr key={item.attempt_id} className="hover:bg-muted/20 transition-colors h-14">
                            {/* Exam Cell */}
                            <td className="py-3 px-4 align-middle">
                              <div className="min-w-0 pr-2">
                                <UITooltipProvider delayDuration={200}>
                                  <UITooltip>
                                    <TooltipTrigger asChild>
                                      <span className="block font-semibold text-foreground truncate cursor-default text-xs sm:text-sm">
                                        {item.exam_title}
                                      </span>
                                    </TooltipTrigger>
                                    <TooltipContent side="top" className="max-w-sm">
                                      {item.exam_title}
                                    </TooltipContent>
                                  </UITooltip>
                                </UITooltipProvider>

                                <div className="flex items-center gap-1.5 mt-0.5 text-xs text-muted-foreground truncate">
                                  <span className="truncate font-medium text-muted-foreground/90">{item.subject}</span>
                                  {item.topics && item.topics.length > 0 && (
                                    <>
                                      <span className="text-muted-foreground/40 shrink-0">•</span>
                                      <div className="flex items-center gap-1 shrink-0">
                                        {item.topics.slice(0, 2).map((topic, idx) => (
                                          <span
                                            key={idx}
                                            className="px-1.5 py-0.2 bg-muted/60 text-muted-foreground text-[10px] rounded border border-border/50 truncate max-w-[85px]"
                                            title={topic}
                                          >
                                            {topic}
                                          </span>
                                        ))}
                                        {item.topics.length > 2 && (
                                          <Popover>
                                            <PopoverTrigger asChild>
                                              <button
                                                type="button"
                                                className="px-1 py-0.2 text-[10px] font-semibold text-primary hover:underline bg-primary/5 rounded border border-primary/20 cursor-pointer"
                                                title="View all topics"
                                                aria-label={`View ${item.topics.length - 2} more topics`}
                                              >
                                                +{item.topics.length - 2} more
                                              </button>
                                            </PopoverTrigger>
                                            <PopoverContent className="w-64 p-3 text-xs" align="start">
                                              <p className="font-semibold text-foreground mb-1.5 pb-1 border-b border-border">
                                                All Topics ({item.topics.length})
                                              </p>
                                              <div className="max-h-48 overflow-y-auto space-y-1 pr-1">
                                                {item.topics.map((t, i) => (
                                                  <div key={i} className="text-muted-foreground flex items-center gap-1.5 text-[11px]">
                                                    <span className="w-1 h-1 rounded-full bg-primary shrink-0" />
                                                    <span className="truncate">{t}</span>
                                                  </div>
                                                ))}
                                              </div>
                                            </PopoverContent>
                                          </Popover>
                                        )}
                                      </div>
                                    </>
                                  )}
                                </div>
                              </div>
                            </td>

                            {/* Marks Cell */}
                            <td className="py-3 px-2 text-right whitespace-nowrap align-middle">
                              <span className="font-mono tabular-nums text-xs sm:text-sm font-semibold text-foreground">
                                {item.marks_obtained !== null && item.marks_obtained !== undefined
                                  ? `${item.marks_obtained} / ${item.total_marks}`
                                  : `- / ${item.total_marks}`}
                              </span>
                            </td>

                            {/* Percentage Cell */}
                            <td className="py-3 px-3 align-middle">
                              <div className="flex flex-col pr-2">
                                <div className="flex items-center justify-between gap-1">
                                  <span className="font-bold text-xs sm:text-sm text-foreground tabular-nums">
                                    {item.percentage !== null && item.percentage !== undefined
                                      ? `${item.percentage}%`
                                      : "-"}
                                  </span>
                                  {item.result_status?.is_provisional && (
                                    <span className="text-[10px] text-amber-700 font-semibold bg-amber-50 border border-amber-200 px-1 py-0.2 rounded">
                                      Provisional
                                    </span>
                                  )}
                                </div>
                                <div className="w-full h-1.5 bg-muted rounded-full overflow-hidden mt-1">
                                  <div
                                    className={`h-full rounded-full transition-all duration-300 ${getOutcomeBarColor(item)}`}
                                    style={{ width: `${Math.min(100, Math.max(0, item.percentage || 0))}%` }}
                                  />
                                </div>
                              </div>
                            </td>

                            {/* Date Cell */}
                            <td className="py-3 px-2 whitespace-nowrap text-muted-foreground text-xs align-middle">
                              <UITooltipProvider delayDuration={200}>
                                <UITooltip>
                                  <TooltipTrigger asChild>
                                    <span className="cursor-default font-medium">{formatShortDate(item.date)}</span>
                                  </TooltipTrigger>
                                  <TooltipContent side="top" className="text-xs">
                                    {formatFullDateTime(item.date)}
                                  </TooltipContent>
                                </UITooltip>
                              </UITooltipProvider>
                            </td>

                            {/* Status Cell */}
                            <td className="py-3 px-3 whitespace-nowrap align-middle">
                              <AttemptStatusBadge
                                resultStatus={item.result_status}
                                status={item.status}
                                isPassed={item.is_passed}
                                size="sm"
                              />
                            </td>

                            {/* Action Cell */}
                            <td className="py-3 px-3 text-right whitespace-nowrap align-middle">
                              {item.result_status?.status_code === "not_attempted" ? (
                                <span className="text-xs text-muted-foreground/60 italic">No result</span>
                              ) : (
                                <Link
                                  to={`/student/results/${item.attempt_id}`}
                                  className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-semibold text-primary hover:bg-primary/10 border border-primary/20 transition-colors whitespace-nowrap focus:outline-none focus:ring-2 focus:ring-primary/40"
                                  aria-label={`View result for ${item.exam_title}`}
                                >
                                  View Result
                                </Link>
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>

                  {/* Mobile Stacked Cards (Below tablet breakpoint) */}
                  <div className="sm:hidden divide-y divide-border p-3.5 space-y-3.5">
                    {recentResults.slice(0, 5).map((item) => (
                      <div key={item.attempt_id} className="pt-3.5 first:pt-0 space-y-2.5">
                        <div className="flex items-start justify-between gap-2">
                          <div className="min-w-0 flex-1">
                            <h4 className="font-semibold text-foreground text-sm truncate" title={item.exam_title}>
                              {item.exam_title}
                            </h4>
                            <p className="text-xs text-muted-foreground truncate mt-0.5">
                              {item.subject}
                            </p>
                          </div>
                          <AttemptStatusBadge
                            resultStatus={item.result_status}
                            status={item.status}
                            isPassed={item.is_passed}
                            size="sm"
                          />
                        </div>

                        <div className="bg-muted/30 p-2.5 rounded-lg space-y-2 border border-border/50 text-xs">
                          <div className="flex items-center justify-between">
                            <span className="text-muted-foreground">Marks:</span>
                            <span className="font-mono font-semibold text-foreground">
                              {item.marks_obtained !== null && item.marks_obtained !== undefined
                                ? `${item.marks_obtained} / ${item.total_marks}`
                                : `- / ${item.total_marks}`}
                            </span>
                          </div>
                          <div className="space-y-1">
                            <div className="flex items-center justify-between">
                              <span className="text-muted-foreground">Score:</span>
                              <span className="font-bold text-foreground">
                                {item.percentage !== null && item.percentage !== undefined ? `${item.percentage}%` : "-"}
                              </span>
                            </div>
                            <div className="w-full h-1.5 bg-muted rounded-full overflow-hidden">
                              <div
                                className={`h-full rounded-full ${getOutcomeBarColor(item)}`}
                                style={{ width: `${Math.min(100, Math.max(0, item.percentage || 0))}%` }}
                              />
                            </div>
                          </div>
                          <div className="flex items-center justify-between text-muted-foreground text-[11px] pt-1 border-t border-border/40">
                            <span>Date: {formatShortDate(item.date)}</span>
                            <span>Duration: {item.time_taken}</span>
                          </div>
                        </div>

                        {item.result_status?.status_code === "not_attempted" ? (
                          <span className="block text-center text-xs text-muted-foreground/60 italic py-1.5">No result</span>
                        ) : (
                          <Link
                            to={`/student/results/${item.attempt_id}`}
                            className="w-full py-2 px-3 rounded-lg bg-primary/10 text-primary hover:bg-primary hover:text-white font-semibold text-xs transition-colors flex items-center justify-center gap-1.5 text-center focus:outline-none focus:ring-2 focus:ring-primary/40"
                          >
                            View Result
                          </Link>
                        )}
                      </div>
                    ))}
                  </div>
                </>
              )}
            </div>
          </>
        )}
      </div>
    </DashboardLayout>
  );
}

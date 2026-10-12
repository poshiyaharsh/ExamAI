import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  AlertCircle,
  AlertTriangle,
  ArrowRight,
  Award,
  BookOpen,
  Calendar,
  CheckCircle,
  Clock,
  FileText,
  History,
  Hourglass,
  LayoutDashboard,
  PlayCircle,
  PlusCircle,
  RefreshCw,
  Settings,
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
import {
  facultyDashboardApi,
  type FacultyDashboardData,
} from "../../services/api";

const menuItems = [
  { icon: LayoutDashboard, label: "Dashboard", path: "/faculty" },
  { icon: FileText, label: "Generate Paper", path: "/faculty/generate" },
  { icon: History, label: "Exam History", path: "/faculty/history" },
  { icon: Settings, label: "Settings", path: "/faculty/settings" },
];

const SCORE_COLORS = ["#EF4444", "#F59E0B", "#3B82F6", "#10B981"];

function getStatusBadge(status: string) {
  switch (status?.toLowerCase()) {
    case "published":
      return "bg-emerald-50 text-emerald-700 border-emerald-200";
    case "draft":
      return "bg-amber-50 text-amber-700 border-amber-200";
    case "generating":
      return "bg-blue-50 text-blue-700 border-blue-200";
    case "closed":
      return "bg-muted text-muted-foreground border-border";
    default:
      return "bg-muted text-foreground border-border";
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
  const [data, setData] = useState<FacultyDashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const loadDashboard = async () => {
    try {
      setLoading(true);
      setError("");
      const res = await facultyDashboardApi.getDashboard();
      setData(res.data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load faculty dashboard.");
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
                {ongoingExams.length > 0 && (
                  <div className="bg-white rounded-xl border border-primary/30 shadow-xs overflow-hidden">
                    <div className="p-4 sm:p-5 border-b border-border bg-primary/5 flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse" />
                        <h3 className="font-bold text-foreground text-sm sm:text-base">Ongoing Live Exams</h3>
                      </div>
                      <span className="text-xs font-semibold text-primary bg-primary/10 px-2 py-0.5 rounded-full">
                        {ongoingExams.length} Live
                      </span>
                    </div>
                    <div className="p-4 sm:p-5 divide-y divide-border/60">
                      {ongoingExams.map((exam) => {
                        const pct = exam.eligible_students > 0 ? Math.round((exam.submitted_count / exam.eligible_students) * 100) : 0;
                        return (
                          <div key={exam.id} className="py-3.5 first:pt-0 last:pb-0 flex flex-col md:flex-row md:items-center justify-between gap-4">
                            <div className="space-y-1 flex-1">
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
                                <span className="text-emerald-700 font-medium">
                                  {exam.ends_at ? `Closes ${new Date(exam.ends_at).toLocaleDateString()}` : "Open indefinitely"}
                                </span>
                              </div>
                            </div>

                            {/* Progress bar */}
                            <div className="w-full md:w-64 space-y-1">
                              <div className="flex items-center justify-between text-xs">
                                <span className="text-muted-foreground font-medium">Submissions:</span>
                                <span className="font-semibold text-foreground">
                                  {exam.submitted_count} / {exam.eligible_students} ({pct}%)
                                </span>
                              </div>
                              <div className="w-full h-2 bg-muted rounded-full overflow-hidden">
                                <div
                                  className="h-full bg-gradient-to-r from-primary to-secondary rounded-full transition-all duration-300"
                                  style={{ width: `${Math.min(100, pct)}%` }}
                                />
                              </div>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}

                {/* 2-Column Visualizations: Exam Performance & Score Distribution */}
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                  {/* Exam Performance Bar Chart */}
                  <div className="bg-white rounded-xl shadow-2xs border border-border p-5 sm:p-6 flex flex-col">
                    <div className="flex items-center justify-between mb-4">
                      <div>
                        <h3 className="font-semibold text-foreground text-sm sm:text-base">Exam Performance Overview</h3>
                        <p className="text-xs text-muted-foreground">Average score (%) across recent published exams</p>
                      </div>
                      <span className="text-xs text-primary font-medium bg-primary/10 px-2 py-0.5 rounded-full">
                        {examPerf.length} exams
                      </span>
                    </div>

                    {examPerf.length === 0 ? (
                      <div className="h-56 flex items-center justify-center text-xs text-muted-foreground">
                        No exam attempts recorded yet.
                      </div>
                    ) : (
                      <div className="h-56 sm:h-64 w-full">
                        <ResponsiveContainer width="100%" height="100%">
                          <BarChart data={examPerf} margin={{ top: 5, right: 10, left: -20, bottom: 5 }}>
                            <CartesianGrid strokeDasharray="3 3" stroke="#F3F4F6" />
                            <XAxis dataKey="exam_title" stroke="#6B7280" fontSize={11} tickLine={false} interval={0} />
                            <YAxis domain={[0, 100]} stroke="#6B7280" fontSize={11} tickLine={false} unit="%" />
                            <Tooltip
                              formatter={(val: any, _, item) => [
                                `${val}% (${item.payload.attempts_count} ${item.payload.attempts_count === 1 ? "attempt" : "attempts"})`,
                                "Average",
                              ]}
                              contentStyle={{ backgroundColor: "#FFFFFF", borderRadius: "8px", borderColor: "#E5E7EB", fontSize: "12px" }}
                            />
                            <Bar dataKey="average_score" fill="#4F46E5" radius={[6, 6, 0, 0]} />
                          </BarChart>
                        </ResponsiveContainer>
                      </div>
                    )}
                  </div>

                  {/* Score Distribution Chart */}
                  <div className="bg-white rounded-xl shadow-2xs border border-border p-5 sm:p-6 flex flex-col">
                    <div className="flex items-center justify-between mb-4">
                      <div>
                        <h3 className="font-semibold text-foreground text-sm sm:text-base">Student Score Distribution</h3>
                        <p className="text-xs text-muted-foreground">Attempt distribution across performance brackets</p>
                      </div>
                      <span className="text-xs text-muted-foreground font-medium">
                        {stats?.total_attempts} total
                      </span>
                    </div>

                    {stats?.total_attempts === 0 ? (
                      <div className="h-56 flex items-center justify-center text-xs text-muted-foreground">
                        No student attempts evaluated yet.
                      </div>
                    ) : (
                      <div className="h-56 sm:h-64 w-full">
                        <ResponsiveContainer width="100%" height="100%">
                          <BarChart data={scoreDist} margin={{ top: 5, right: 10, left: -20, bottom: 5 }}>
                            <CartesianGrid strokeDasharray="3 3" stroke="#F3F4F6" />
                            <XAxis dataKey="range" stroke="#6B7280" fontSize={11} tickLine={false} />
                            <YAxis allowDecimals={false} stroke="#6B7280" fontSize={11} tickLine={false} />
                            <Tooltip
                              formatter={(val: any, _, item) => [`${val} submissions`, item.payload.label]}
                              contentStyle={{ backgroundColor: "#FFFFFF", borderRadius: "8px", borderColor: "#E5E7EB", fontSize: "12px" }}
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

                {/* Recent Exams Table Section */}
                <div className="bg-white rounded-xl shadow-2xs border border-border overflow-hidden">
                  <div className="p-4 sm:p-5 border-b border-border flex items-center justify-between">
                    <div>
                      <h3 className="font-semibold text-foreground text-sm sm:text-base">Recent Created Exams</h3>
                      <p className="text-xs text-muted-foreground">Manage and track your published and draft exams</p>
                    </div>
                    <Link to="/faculty/history" className="text-xs font-medium text-primary hover:underline flex items-center gap-1">
                      View full history <ArrowRight className="w-3 h-3" />
                    </Link>
                  </div>

                  {recentExams.length === 0 ? (
                    <div className="p-8 text-center text-xs text-muted-foreground">
                      No exams created yet.
                    </div>
                  ) : (
                    <>
                      {/* Desktop Table View (>= 768px) */}
                      <div className="hidden md:block overflow-x-auto">
                        <table className="w-full text-left text-xs sm:text-sm">
                          <thead className="border-b border-border bg-muted/30 text-muted-foreground font-medium">
                            <tr>
                              <th className="py-3 px-4">Exam Title</th>
                              <th className="py-3 px-4">Subject</th>
                              <th className="py-3 px-4">Created Date</th>
                              <th className="py-3 px-4">Status</th>
                              <th className="py-3 px-4">Submissions</th>
                              <th className="py-3 px-4">Average Score</th>
                              <th className="py-3 px-4">Pass Rate</th>
                              <th className="py-3 px-4 text-right">Actions</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-border">
                            {recentExams.map((exam) => (
                              <tr key={exam.id} className="hover:bg-muted/20 transition-colors">
                                <td className="py-3.5 px-4 font-semibold text-foreground">{exam.title}</td>
                                <td className="py-3.5 px-4 text-muted-foreground">{exam.subject}</td>
                                <td className="py-3.5 px-4 text-muted-foreground whitespace-nowrap">
                                  {new Date(exam.created_at).toLocaleDateString()}
                                </td>
                                <td className="py-3.5 px-4">
                                  <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold border capitalize ${getStatusBadge(exam.status)}`}>
                                    {exam.status}
                                  </span>
                                </td>
                                <td className="py-3.5 px-4 font-medium text-foreground">{exam.attempts_count}</td>
                                <td className="py-3.5 px-4 font-semibold text-foreground">
                                  {exam.average_score !== null && exam.average_score !== undefined ? `${exam.average_score}%` : "N/A"}
                                </td>
                                <td className="py-3.5 px-4">
                                  {exam.pass_rate !== null && exam.pass_rate !== undefined ? `${exam.pass_rate}%` : "N/A"}
                                </td>
                                <td className="py-3.5 px-4 text-right">
                                  <Link
                                    to="/faculty/history"
                                    className="text-primary hover:underline font-medium text-xs"
                                  >
                                    View / Manage
                                  </Link>
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>

                      {/* Mobile Stacked Cards (< 768px, no horizontal scrollbar) */}
                      <div className="md:hidden divide-y divide-border p-3 space-y-3">
                        {recentExams.map((exam) => (
                          <div key={exam.id} className="pt-3 first:pt-0 space-y-2">
                            <div className="flex items-start justify-between gap-2">
                              <div>
                                <h4 className="font-semibold text-foreground text-sm">{exam.title}</h4>
                                <p className="text-xs text-muted-foreground">
                                  {exam.subject} · {new Date(exam.created_at).toLocaleDateString()}
                                </p>
                              </div>
                              <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold border capitalize shrink-0 ${getStatusBadge(exam.status)}`}>
                                {exam.status}
                              </span>
                            </div>
                            <div className="grid grid-cols-2 gap-2 text-xs text-muted-foreground bg-muted/40 p-2.5 rounded-lg">
                              <div>Submissions: <strong className="text-foreground">{exam.attempts_count}</strong></div>
                              <div>Average: <strong className="text-foreground">{exam.average_score !== null ? `${exam.average_score}%` : "N/A"}</strong></div>
                              <div>Pass Rate: <strong className="text-foreground">{exam.pass_rate !== null ? `${exam.pass_rate}%` : "N/A"}</strong></div>
                              <div>
                                <Link to="/faculty/history" className="text-primary font-semibold">
                                  Manage →
                                </Link>
                              </div>
                            </div>
                          </div>
                        ))}
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

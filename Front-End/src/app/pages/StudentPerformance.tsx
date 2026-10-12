import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  Award,
  BookOpen,
  Calendar,
  CheckCircle,
  Clock,
  Download,
  Eye,
  FileText,
  Filter,
  LayoutDashboard,
  RotateCcw,
  Search,
  Settings,
  TrendingDown,
  TrendingUp,
  X,
  XCircle,
} from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { DashboardLayout } from "../components/DashboardLayout";
import {
  studentExamApi,
  studentPerformanceApi,
  type StudentAttempt,
  type StudentPerformanceResultRow,
  type StudentPerformanceSummary,
  type StudentPerformanceTrendItem,
  type StudentSubjectItem,
} from "../../services/api";

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

export function StudentPerformance() {
  const [summary, setSummary] = useState<StudentPerformanceSummary | null>(null);
  const [trend, setTrend] = useState<StudentPerformanceTrendItem[]>([]);
  const [subjectsData, setSubjectsData] = useState<{
    subjects: StudentSubjectItem[];
    strongest_subject: string | null;
    weakest_subject: string | null;
  } | null>(null);

  const [results, setResults] = useState<StudentPerformanceResultRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [resultsLoading, setResultsLoading] = useState(false);
  const [error, setError] = useState("");

  // Filters & Pagination
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedSubject, setSelectedSubject] = useState("all");
  const [selectedStatus, setSelectedStatus] = useState<"all" | "pass" | "fail">("all");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [sortBy, setSortBy] = useState("-date");
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [totalCount, setTotalCount] = useState(0);

  // Attempt Detail Modal State
  const [selectedAttemptId, setSelectedAttemptId] = useState<number | null>(null);
  const [attemptDetails, setAttemptDetails] = useState<StudentAttempt | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState("");

  // Initial Load (Summary, Trend, Subjects)
  const loadAnalytics = async () => {
    try {
      setLoading(true);
      setError("");
      const [sumRes, trendRes, subRes] = await Promise.all([
        studentPerformanceApi.getSummary(),
        studentPerformanceApi.getTrend(),
        studentPerformanceApi.getSubjects(),
      ]);
      setSummary(sumRes.data);
      setTrend(trendRes.data);
      setSubjectsData(subRes.data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load performance analytics.");
    } finally {
      setLoading(false);
    }
  };

  // Load Results table
  const loadResults = async (pageNum = page) => {
    try {
      setResultsLoading(true);
      const res = await studentPerformanceApi.getResults({
        search: searchQuery || undefined,
        subject: selectedSubject !== "all" ? selectedSubject : undefined,
        status: selectedStatus !== "all" ? selectedStatus : undefined,
        start_date: startDate || undefined,
        end_date: endDate || undefined,
        sort: sortBy,
        page: pageNum,
        page_size: 10,
      });
      setResults(res.data);
      setPage(res.pagination.page);
      setTotalPages(res.pagination.total_pages || 1);
      setTotalCount(res.pagination.total_count);
    } catch (err) {
      console.error("Failed to load results table:", err);
    } finally {
      setResultsLoading(false);
    }
  };

  useEffect(() => {
    void loadAnalytics();
  }, []);

  useEffect(() => {
    void loadResults(page);
  }, [selectedSubject, selectedStatus, startDate, endDate, sortBy, page]);

  // Handle search submission or reset
  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(1);
    void loadResults(1);
  };

  const handleResetFilters = () => {
    setSearchQuery("");
    setSelectedSubject("all");
    setSelectedStatus("all");
    setStartDate("");
    setEndDate("");
    setSortBy("-date");
    setPage(1);
  };

  // Load Attempt Details for Modal
  const openAttemptModal = async (attemptId: number) => {
    setSelectedAttemptId(attemptId);
    setDetailLoading(true);
    setDetailError("");
    try {
      const data = await studentExamApi.getAttempt(attemptId);
      setAttemptDetails(data);
    } catch (err) {
      setDetailError("Unable to load attempt details.");
    } finally {
      setDetailLoading(false);
    }
  };

  const closeAttemptModal = () => {
    setSelectedAttemptId(null);
    setAttemptDetails(null);
  };

  // CSV Export
  const downloadReport = () => {
    if (results.length === 0) return;
    const headers = ["Exam Title", "Subject", "Department", "Faculty", "Date", "Marks Obtained", "Total Marks", "Percentage", "Status", "Time Taken"];
    const rows = results.map((r) => [
      `"${r.exam_title.replace(/"/g, '""')}"`,
      `"${r.subject.replace(/"/g, '""')}"`,
      `"${r.department || ""}"`,
      `"${r.faculty_name.replace(/"/g, '""')}"`,
      new Date(r.date).toLocaleDateString(),
      r.marks_obtained,
      r.total_marks,
      `${r.percentage}%`,
      r.is_passed ? "PASS" : "FAIL",
      `"${r.time_taken}"`,
    ]);

    const csvContent = "data:text/csv;charset=utf-8," + [headers.join(","), ...rows.map((e) => e.join(","))].join("\n");
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", `student_performance_report_${new Date().toISOString().slice(0, 10)}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const hasZeroAttempts = summary?.total_attempts === 0;

  return (
    <DashboardLayout menuItems={menuItems} userRole="Student">
      <div className="space-y-6">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="text-2xl sm:text-3xl font-bold text-foreground mb-1">Performance Analytics</h1>
            <p className="text-xs sm:text-sm text-muted-foreground">
              Track your academic progress, trends, and subject proficiencies
            </p>
          </div>
          {!hasZeroAttempts && results.length > 0 && (
            <button
              onClick={downloadReport}
              className="inline-flex items-center justify-center gap-2 px-4 py-2 rounded-lg border border-border bg-white text-foreground text-xs sm:text-sm font-medium hover:bg-muted/50 transition-colors shadow-xs"
            >
              <Download className="w-4 h-4 text-primary" />
              <span>Download Report (CSV)</span>
            </button>
          )}
        </div>

        {/* Global Loading / Error */}
        {loading ? (
          <div className="bg-white rounded-xl p-12 text-center text-sm text-muted-foreground border border-border">
            Loading performance data...
          </div>
        ) : error ? (
          <div className="bg-white rounded-xl p-8 text-center text-sm text-destructive border border-destructive/20">
            {error}
          </div>
        ) : hasZeroAttempts ? (
          /* Empty State for student with 0 attempts */
          <div className="bg-white rounded-xl p-12 text-center border border-border shadow-xs">
            <div className="w-16 h-16 rounded-full bg-primary/10 flex items-center justify-center mx-auto mb-4">
              <FileText className="w-8 h-8 text-primary" />
            </div>
            <h2 className="text-xl font-bold text-foreground mb-2">You haven't taken any exams yet</h2>
            <p className="text-xs sm:text-sm text-muted-foreground max-w-md mx-auto mb-6">
              Complete your department exams to see your average score, trends, strength analysis, and detailed question breakdowns here.
            </p>
            <Link
              to="/student/exams"
              className="inline-flex items-center gap-2 px-5 py-2.5 rounded-lg bg-gradient-to-r from-primary to-secondary text-white font-medium text-xs sm:text-sm shadow-sm hover:opacity-90 transition-all"
            >
              Browse Available Exams
            </Link>
          </div>
        ) : (
          <>
            {/* Summary Cards */}
            <div className="grid grid-cols-2 md:grid-cols-5 gap-3.5 sm:gap-5">
              <div className="bg-white rounded-xl p-4 sm:p-5 shadow-xs border border-border">
                <div className="text-xs text-muted-foreground font-medium mb-1">Exams Attempted</div>
                <div className="text-2xl sm:text-3xl font-bold text-foreground">{summary?.total_attempts}</div>
                <div className="text-xs text-muted-foreground mt-1 flex items-center gap-1">
                  <CheckCircle className="w-3.5 h-3.5 text-emerald-600" /> Completed
                </div>
              </div>

              <div className="bg-white rounded-xl p-4 sm:p-5 shadow-xs border border-border">
                <div className="text-xs text-muted-foreground font-medium mb-1">Overall Average</div>
                <div className="text-2xl sm:text-3xl font-bold text-primary">
                  {summary?.overall_average !== null && summary?.overall_average !== undefined ? `${summary.overall_average}%` : "N/A"}
                </div>
                <div className="mt-1.5">
                  <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold border ${getStatusBadge(summary?.performance_status || "")}`}>
                    {summary?.performance_status || "N/A"}
                  </span>
                </div>
              </div>

              <div className="bg-white rounded-xl p-4 sm:p-5 shadow-xs border border-border">
                <div className="text-xs text-muted-foreground font-medium mb-1">Highest Score</div>
                <div className="text-2xl sm:text-3xl font-bold text-emerald-600">
                  {summary?.highest_score !== null && summary?.highest_score !== undefined ? `${summary.highest_score}%` : "N/A"}
                </div>
                <div className="text-xs text-muted-foreground mt-1 flex items-center gap-1">
                  <TrendingUp className="w-3.5 h-3.5 text-emerald-600" /> Peak Result
                </div>
              </div>

              <div className="bg-white rounded-xl p-4 sm:p-5 shadow-xs border border-border">
                <div className="text-xs text-muted-foreground font-medium mb-1">Lowest Score</div>
                <div className="text-2xl sm:text-3xl font-bold text-amber-600">
                  {summary?.lowest_score !== null && summary?.lowest_score !== undefined ? `${summary.lowest_score}%` : "N/A"}
                </div>
                <div className="text-xs text-muted-foreground mt-1 flex items-center gap-1">
                  <TrendingDown className="w-3.5 h-3.5 text-amber-600" /> Baseline Result
                </div>
              </div>

              <div className="bg-white rounded-xl p-4 sm:p-5 shadow-xs border border-border col-span-2 md:col-span-1">
                <div className="text-xs text-muted-foreground font-medium mb-1">Pass Rate</div>
                <div className="text-2xl sm:text-3xl font-bold text-foreground">
                  {summary?.pass_rate !== null && summary?.pass_rate !== undefined ? `${summary.pass_rate}%` : "N/A"}
                </div>
                <div className="text-xs text-muted-foreground mt-1">
                  <span className="text-emerald-600 font-medium">{summary?.pass_count} passed</span> · <span className="text-rose-600 font-medium">{summary?.fail_count} failed</span>
                </div>
              </div>
            </div>

            {/* Department Rank Banner (if available) */}
            {summary?.department_rank && summary?.department_total_students && (
              <div className="bg-gradient-to-r from-primary/5 via-secondary/5 to-transparent border border-primary/20 rounded-xl p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center text-primary shrink-0">
                    <Award className="w-5 h-5" />
                  </div>
                  <div>
                    <h3 className="font-semibold text-sm sm:text-base text-foreground">
                      Department Standing: {summary.department}
                    </h3>
                    <p className="text-xs text-muted-foreground">
                      Ranked <strong>#{summary.department_rank}</strong> out of {summary.department_total_students} students
                      {summary.department_percentile !== null && summary.department_percentile !== undefined && ` (Top ${100 - summary.department_percentile}% percentile)`}
                    </p>
                  </div>
                </div>
                {summary.last_exam_date && (
                  <div className="text-xs text-muted-foreground flex items-center gap-1.5 self-start sm:self-auto">
                    <Calendar className="w-3.5 h-3.5" />
                    Last Exam: {new Date(summary.last_exam_date).toLocaleDateString()}
                  </div>
                )}
              </div>
            )}

            {/* Charts Section */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Line Chart: Trend over time */}
              <div className="bg-white rounded-xl p-5 sm:p-6 shadow-xs border border-border">
                <div className="flex items-center justify-between mb-4">
                  <div>
                    <h3 className="font-semibold text-foreground text-sm sm:text-base">Score Trend Over Time</h3>
                    <p className="text-xs text-muted-foreground">Percentage progression across exam attempts</p>
                  </div>
                  <span className="text-xs font-medium text-primary bg-primary/10 px-2.5 py-1 rounded-full">
                    {trend.length} {trend.length === 1 ? "attempt" : "attempts"}
                  </span>
                </div>

                {trend.length === 0 ? (
                  <div className="h-64 flex items-center justify-center text-xs text-muted-foreground">
                    No trend history recorded yet.
                  </div>
                ) : (
                  <div className="h-64 sm:h-72 w-full">
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart data={trend} margin={{ top: 10, right: 15, left: -15, bottom: 5 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#F3F4F6" />
                        <XAxis dataKey="date" stroke="#6B7280" fontSize={12} tickLine={false} />
                        <YAxis domain={[0, 100]} stroke="#6B7280" fontSize={12} tickLine={false} unit="%" />
                        <Tooltip
                          formatter={(value: any) => [`${value}%`, "Score"]}
                          labelFormatter={(label) => `Date: ${label}`}
                          contentStyle={{ backgroundColor: "#FFFFFF", borderRadius: "8px", borderColor: "#E5E7EB", fontSize: "12px" }}
                        />
                        <Line
                          type="monotone"
                          dataKey="percentage"
                          stroke="#4F46E5"
                          strokeWidth={2.5}
                          dot={{ r: 4, fill: "#4F46E5", strokeWidth: 2, stroke: "#FFFFFF" }}
                          activeDot={{ r: 6 }}
                        />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                )}
              </div>

              {/* Bar Chart: Subject / Topic Analysis */}
              <div className="bg-white rounded-xl p-5 sm:p-6 shadow-xs border border-border">
                <div className="flex items-center justify-between mb-4">
                  <div>
                    <h3 className="font-semibold text-foreground text-sm sm:text-base">Subject & Topic Breakdown</h3>
                    <p className="text-xs text-muted-foreground">Average performance across subjects</p>
                  </div>
                  <div className="flex items-center gap-2 text-xs">
                    <span className="flex items-center gap-1 font-medium text-emerald-700">
                      <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 inline-block" /> Strongest
                    </span>
                    <span className="flex items-center gap-1 font-medium text-amber-700">
                      <span className="w-2.5 h-2.5 rounded-full bg-amber-500 inline-block" /> Needs Focus
                    </span>
                  </div>
                </div>

                {!subjectsData || subjectsData.subjects.length === 0 ? (
                  <div className="h-64 flex items-center justify-center text-xs text-muted-foreground">
                    No subject breakdown available.
                  </div>
                ) : (
                  <div className="h-64 sm:h-72 w-full">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={subjectsData.subjects} margin={{ top: 10, right: 15, left: -15, bottom: 5 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#F3F4F6" />
                        <XAxis dataKey="subject" stroke="#6B7280" fontSize={11} tickLine={false} interval={0} />
                        <YAxis domain={[0, 100]} stroke="#6B7280" fontSize={12} tickLine={false} unit="%" />
                        <Tooltip
                          formatter={(value: any, _, item) => [
                            `${value}% (${item.payload.exam_count} ${item.payload.exam_count === 1 ? "exam" : "exams"})`,
                            "Average",
                          ]}
                          contentStyle={{ backgroundColor: "#FFFFFF", borderRadius: "8px", borderColor: "#E5E7EB", fontSize: "12px" }}
                        />
                        <Bar dataKey="average_score" radius={[6, 6, 0, 0]}>
                          {subjectsData.subjects.map((entry, index) => (
                            <Cell
                              key={`cell-${index}`}
                              fill={entry.is_strongest ? "#10B981" : entry.is_weakest ? "#F59E0B" : "#4F46E5"}
                            />
                          ))}
                        </Bar>
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                )}
              </div>
            </div>

            {/* Results Table Section */}
            <div className="bg-white rounded-xl shadow-xs border border-border overflow-hidden">
              <div className="p-5 border-b border-border">
                <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 mb-4">
                  <div>
                    <h3 className="font-semibold text-foreground text-base sm:text-lg">Exam Results History</h3>
                    <p className="text-xs text-muted-foreground">Detailed logs of all submitted exam attempts</p>
                  </div>
                  <div className="text-xs text-muted-foreground">
                    Showing {results.length} of {totalCount} attempts
                  </div>
                </div>

                {/* Filters toolbar */}
                <div className="flex flex-col lg:flex-row gap-3">
                  {/* Search */}
                  <form onSubmit={handleSearchSubmit} className="flex-1 relative">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                    <input
                      type="text"
                      placeholder="Search exam title or topic..."
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      className="w-full pl-9 pr-3 py-2 rounded-lg border border-border bg-input-background text-xs sm:text-sm focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-all"
                    />
                  </form>

                  <div className="flex flex-wrap items-center gap-2">
                    {/* Subject Filter */}
                    <select
                      value={selectedSubject}
                      onChange={(e) => {
                        setSelectedSubject(e.target.value);
                        setPage(1);
                      }}
                      className="px-3 py-2 rounded-lg border border-border bg-white text-foreground text-xs sm:text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                    >
                      <option value="all">All Subjects</option>
                      {subjectsData?.subjects.map((s) => (
                        <option key={s.subject} value={s.subject}>
                          {s.subject}
                        </option>
                      ))}
                    </select>

                    {/* Status Filter */}
                    <select
                      value={selectedStatus}
                      onChange={(e) => {
                        setSelectedStatus(e.target.value as "all" | "pass" | "fail");
                        setPage(1);
                      }}
                      className="px-3 py-2 rounded-lg border border-border bg-white text-foreground text-xs sm:text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                    >
                      <option value="all">All Status</option>
                      <option value="pass">Passed (≥40%)</option>
                      <option value="fail">Failed (&lt;40%)</option>
                    </select>

                    {/* Sort */}
                    <select
                      value={sortBy}
                      onChange={(e) => {
                        setSortBy(e.target.value);
                        setPage(1);
                      }}
                      className="px-3 py-2 rounded-lg border border-border bg-white text-foreground text-xs sm:text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                    >
                      <option value="-date">Date (Newest First)</option>
                      <option value="date">Date (Oldest First)</option>
                      <option value="-percentage">Score (Highest First)</option>
                      <option value="percentage">Score (Lowest First)</option>
                    </select>

                    {/* Reset Button */}
                    <button
                      type="button"
                      onClick={handleResetFilters}
                      title="Reset filters"
                      className="p-2 rounded-lg border border-border hover:bg-muted text-muted-foreground hover:text-foreground transition-colors"
                    >
                      <RotateCcw className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              </div>

              {/* Table / Mobile Cards */}
              {resultsLoading ? (
                <div className="p-12 text-center text-xs sm:text-sm text-muted-foreground">
                  Loading exam results...
                </div>
              ) : results.length === 0 ? (
                <div className="p-12 text-center">
                  <FileText className="w-10 h-10 text-muted-foreground/50 mx-auto mb-2" />
                  <p className="text-xs sm:text-sm text-muted-foreground">
                    No attempts match the selected filter criteria.
                  </p>
                </div>
              ) : (
                <>
                  {/* Desktop Table View (>= 768px) */}
                  <div className="hidden md:block overflow-x-auto">
                    <table className="w-full text-left text-xs sm:text-sm border-collapse">
                      <thead>
                        <tr className="border-b border-border bg-muted/30 text-muted-foreground font-medium">
                          <th className="py-3 px-4">Exam</th>
                          <th className="py-3 px-4">Subject</th>
                          <th className="py-3 px-4">Date</th>
                          <th className="py-3 px-4">Marks</th>
                          <th className="py-3 px-4">Percentage</th>
                          <th className="py-3 px-4">Time Taken</th>
                          <th className="py-3 px-4">Status</th>
                          <th className="py-3 px-4 text-right">Action</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-border">
                        {results.map((item) => (
                          <tr key={item.attempt_id} className="hover:bg-muted/30 transition-colors">
                            <td className="py-3.5 px-4 font-semibold text-foreground">
                              {item.exam_title}
                              <div className="text-xs text-muted-foreground font-normal">Faculty: {item.faculty_name}</div>
                            </td>
                            <td className="py-3.5 px-4 text-muted-foreground">
                              <span className="inline-block px-2 py-0.5 rounded-full text-xs font-medium bg-muted text-foreground border border-border">
                                {item.subject}
                              </span>
                            </td>
                            <td className="py-3.5 px-4 text-muted-foreground whitespace-nowrap">
                              {new Date(item.date).toLocaleDateString()}
                            </td>
                            <td className="py-3.5 px-4 font-medium text-foreground whitespace-nowrap">
                              {item.marks_obtained} / {item.total_marks}
                            </td>
                            <td className="py-3.5 px-4 font-bold text-foreground whitespace-nowrap">
                              {item.percentage}%
                            </td>
                            <td className="py-3.5 px-4 text-muted-foreground whitespace-nowrap">
                              {item.time_taken}
                            </td>
                            <td className="py-3.5 px-4 whitespace-nowrap">
                              {item.is_passed ? (
                                <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
                                  <CheckCircle className="w-3 h-3" /> PASS
                                </span>
                              ) : (
                                <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-rose-50 text-rose-700 border border-rose-200">
                                  <XCircle className="w-3 h-3" /> FAIL
                                </span>
                              )}
                            </td>
                            <td className="py-3.5 px-4 text-right whitespace-nowrap">
                              <button
                                onClick={() => openAttemptModal(item.attempt_id)}
                                className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg border border-border bg-white text-foreground hover:bg-muted font-medium text-xs shadow-2xs transition-colors"
                              >
                                <Eye className="w-3.5 h-3.5 text-primary" />
                                <span>View Details</span>
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>

                  {/* Mobile Stacked Cards (< 768px, no horizontal scroll) */}
                  <div className="md:hidden divide-y divide-border p-3 space-y-3">
                    {results.map((item) => (
                      <div key={item.attempt_id} className="pt-3 first:pt-0 space-y-2">
                        <div className="flex items-start justify-between gap-2">
                          <div>
                            <h4 className="font-semibold text-foreground text-sm">{item.exam_title}</h4>
                            <p className="text-xs text-muted-foreground">
                              {item.subject} · {new Date(item.date).toLocaleDateString()}
                            </p>
                          </div>
                          {item.is_passed ? (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200 shrink-0">
                              PASS
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold bg-rose-50 text-rose-700 border border-rose-200 shrink-0">
                              FAIL
                            </span>
                          )}
                        </div>
                        <div className="grid grid-cols-2 gap-2 text-xs text-muted-foreground bg-muted/40 p-2.5 rounded-lg">
                          <div>
                            Marks: <strong className="text-foreground">{item.marks_obtained} / {item.total_marks}</strong>
                          </div>
                          <div>
                            Percentage: <strong className="text-foreground">{item.percentage}%</strong>
                          </div>
                          <div>
                            Time: <span className="text-foreground">{item.time_taken}</span>
                          </div>
                          <div>
                            Faculty: <span className="text-foreground">{item.faculty_name}</span>
                          </div>
                        </div>
                        <button
                          onClick={() => openAttemptModal(item.attempt_id)}
                          className="w-full py-2 rounded-lg border border-border bg-white text-foreground font-medium text-xs hover:bg-muted/50 transition-colors flex items-center justify-center gap-1.5"
                        >
                          <Eye className="w-3.5 h-3.5 text-primary" />
                          View Detailed Breakdown
                        </button>
                      </div>
                    ))}
                  </div>

                  {/* Pagination Bar */}
                  {totalPages > 1 && (
                    <div className="p-4 border-t border-border flex items-center justify-between text-xs text-muted-foreground">
                      <div>
                        Page {page} of {totalPages}
                      </div>
                      <div className="flex items-center gap-2">
                        <button
                          disabled={page <= 1}
                          onClick={() => setPage((p) => Math.max(1, p - 1))}
                          className="px-3 py-1.5 rounded-lg border border-border bg-white text-foreground font-medium hover:bg-muted/50 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                        >
                          Previous
                        </button>
                        <button
                          disabled={page >= totalPages}
                          onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                          className="px-3 py-1.5 rounded-lg border border-border bg-white text-foreground font-medium hover:bg-muted/50 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                        >
                          Next
                        </button>
                      </div>
                    </div>
                  )}
                </>
              )}
            </div>
          </>
        )}

        {/* View Details Modal */}
        {selectedAttemptId !== null && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-xs animate-in fade-in duration-150">
            <div className="bg-white rounded-2xl border border-border shadow-xl max-w-3xl w-full max-h-[85vh] flex flex-col overflow-hidden">
              {/* Modal Header */}
              <div className="p-5 border-b border-border flex items-center justify-between">
                <div>
                  <h3 className="text-base sm:text-lg font-bold text-foreground">
                    {attemptDetails ? attemptDetails.exam_title : "Attempt Breakdown"}
                  </h3>
                  {attemptDetails && (
                    <p className="text-xs text-muted-foreground">
                      Final Score: <strong className="text-primary">{attemptDetails.total_score} / {attemptDetails.exam_total_marks} marks</strong>
                    </p>
                  )}
                </div>
                <button
                  onClick={closeAttemptModal}
                  className="p-1.5 rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              {/* Modal Body */}
              <div className="p-5 overflow-y-auto space-y-4 flex-1">
                {detailLoading ? (
                  <div className="py-12 text-center text-xs sm:text-sm text-muted-foreground">
                    Loading question breakdown...
                  </div>
                ) : detailError ? (
                  <div className="py-8 text-center text-xs sm:text-sm text-destructive font-medium">
                    {detailError}
                  </div>
                ) : attemptDetails ? (
                  <div className="space-y-4">
                    {attemptDetails.answers.map((ans, idx) => (
                      <div
                        key={ans.question || idx}
                        className="rounded-xl border border-border p-4 bg-muted/20 space-y-2 text-xs sm:text-sm"
                      >
                        <div className="flex items-start justify-between gap-3">
                          <h4 className="font-semibold text-foreground">
                            Question {idx + 1}
                          </h4>
                          {ans.is_correct === true ? (
                            <span className="inline-flex items-center gap-1 text-emerald-600 font-semibold text-xs">
                              <CheckCircle className="w-4 h-4 shrink-0" /> Correct
                            </span>
                          ) : ans.is_correct === false ? (
                            <span className="inline-flex items-center gap-1 text-rose-600 font-semibold text-xs">
                              <XCircle className="w-4 h-4 shrink-0" /> Incorrect
                            </span>
                          ) : (
                            <span className="text-amber-600 text-xs font-medium">
                              Pending Evaluation
                            </span>
                          )}
                        </div>

                        <p className="text-foreground">{ans.question_text}</p>

                        <div className="pt-2 border-t border-border/60 space-y-1.5">
                          <div>
                            <span className="text-muted-foreground font-medium">Your answer: </span>
                            <span className="font-medium text-foreground">{ans.answer_text || "No answer submitted"}</span>
                          </div>

                          {ans.correct_answer !== undefined && ans.correct_answer !== null && (
                            <div>
                              <span className="text-muted-foreground font-medium">Correct answer: </span>
                              <span className="text-emerald-700 font-medium">{String(ans.correct_answer)}</span>
                            </div>
                          )}

                          <div>
                            <span className="text-muted-foreground font-medium">Score awarded: </span>
                            <strong className="text-primary">{ans.score_awarded ?? 0} marks</strong>
                          </div>

                          {ans.ai_feedback && (
                            <div className="mt-2 rounded-lg bg-primary/5 border border-primary/10 p-2.5 text-xs text-muted-foreground">
                              <strong className="text-foreground">AI Feedback: </strong>
                              {ans.ai_feedback}
                            </div>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                ) : null}
              </div>

              {/* Modal Footer */}
              <div className="p-4 border-t border-border bg-muted/20 flex justify-end">
                <button
                  onClick={closeAttemptModal}
                  className="px-4 py-2 rounded-lg bg-white border border-border text-foreground font-medium text-xs sm:text-sm hover:bg-muted transition-colors"
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

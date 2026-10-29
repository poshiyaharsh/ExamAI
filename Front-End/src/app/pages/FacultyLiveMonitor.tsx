import React, { useEffect, useMemo, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import {
  Activity,
  AlertCircle,
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  Clock,
  ExternalLink,
  Eye,
  FileQuestion,
  Filter,
  History,
  LayoutDashboard,
  PlayCircle,
  RefreshCw,
  Search,
  ShieldAlert,
  Users,
  X,
} from "lucide-react";
import { DashboardLayout } from "../components/DashboardLayout";
import { AttemptStatusBadge } from "../components/AttemptStatusBadge";
import {
  facultyLiveMonitorApi,
  type FacultyLiveMonitorData,
  type LiveStudentRosterItem,
} from "../../services/api";

const menuItems = [
  { icon: LayoutDashboard, label: "Dashboard", path: "/faculty" },
  { icon: FileQuestion, label: "Generate Paper", path: "/faculty/generate" },
  { icon: History, label: "Exam History", path: "/faculty/history" },
];

function formatTimeLeft(seconds: number): string {
  if (seconds <= 0) return "0s";
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  if (h > 0) return `${h}h ${m}m`;
  if (m > 0) return `${m}m ${s}s`;
  return `${s}s`;
}

function formatRelativeTime(dateStr: string | null): string {
  if (!dateStr) return "-";
  try {
    const d = new Date(dateStr);
    const now = new Date();
    const diffSec = Math.floor((now.getTime() - d.getTime()) / 1000);
    if (diffSec < 10) return "just now";
    if (diffSec < 60) return `${diffSec}s ago`;
    const diffMin = Math.floor(diffSec / 60);
    if (diffMin < 60) return `${diffMin}m ago`;
    const diffHour = Math.floor(diffMin / 60);
    if (diffHour < 24) return `${diffHour}h ago`;
    return d.toLocaleDateString();
  } catch {
    return dateStr;
  }
}

export function FacultyLiveMonitor() {
  const { id } = useParams<{ id: string }>();
  const [searchParams, setSearchParams] = useSearchParams();
  const examId = Number(id);

  const [data, setData] = useState<FacultyLiveMonitorData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [lastUpdated, setLastUpdated] = useState<Date>(new Date());
  const [serverOffsetMs, setServerOffsetMs] = useState<number>(0);

  // Filters & Search
  const [searchQuery, setSearchQuery] = useState("");
  const initialFilter = searchParams.get("filter") || "all";
  const [statusFilter, setStatusFilter] = useState<string>(initialFilter);
  const [sortBy, setSortBy] = useState<"name" | "progress" | "violations" | "time">("name");

  // Selected student for violation timeline drawer
  const [selectedStudent, setSelectedStudent] = useState<LiveStudentRosterItem | null>(null);

  const fetchLiveMonitor = async (silent = false) => {
    if (!examId || isNaN(examId)) {
      setError("Invalid Exam ID provided.");
      setLoading(false);
      return;
    }

    try {
      if (!silent) {
        if (!data) setLoading(true);
        setIsRefreshing(true);
      }
      setError("");

      const clientFetchTime = Date.now();
      const res = await facultyLiveMonitorApi.getExamMonitor(examId);
      setData(res.data);
      setLastUpdated(new Date());

      // Compute server clock offset
      if (res.data?.exam?.server_now) {
        const serverTime = new Date(res.data.exam.server_now).getTime();
        setServerOffsetMs(serverTime - clientFetchTime);
      }
    } catch (err: any) {
      if (!silent) {
        const msg = err.response?.data?.detail || err.message || "Unable to fetch live monitoring data.";
        setError(msg);
      }
    } finally {
      setLoading(false);
      setIsRefreshing(false);
    }
  };

  useEffect(() => {
    void fetchLiveMonitor(false);
    const interval = setInterval(() => {
      if (!document.hidden) {
        void fetchLiveMonitor(true);
      }
    }, 15000);
    return () => clearInterval(interval);
  }, [examId]);

  // Update query params when filter changes
  const handleFilterChange = (filter: string) => {
    setStatusFilter(filter);
    if (filter === "all") {
      searchParams.delete("filter");
    } else {
      searchParams.set("filter", filter);
    }
    setSearchParams(searchParams);
  };

  const exam = data?.exam;
  const summary = data?.summary;
  const roster = data?.roster || [];

  // Filter and sort roster
  const filteredRoster = useMemo(() => {
    return roster
      .filter((student) => {
        // Text search
        if (searchQuery.trim()) {
          const q = searchQuery.toLowerCase();
          const matchName = student.name.toLowerCase().includes(q);
          const matchId = student.student_id.toLowerCase().includes(q);
          const matchEmail = student.email.toLowerCase().includes(q);
          if (!matchName && !matchId && !matchEmail) return false;
        }

        // Status tab filter
        if (statusFilter === "in_progress") return student.status === "in_progress";
        if (statusFilter === "submitted") return student.status === "submitted" || student.status === "auto_submitted";
        if (statusFilter === "not_started") return student.status === "not_started";
        if (statusFilter === "flagged") return student.violation_count > 0;
        return true;
      })
      .sort((a, b) => {
        if (sortBy === "violations") return b.violation_count - a.violation_count;
        if (sortBy === "progress") return b.questions_answered - a.questions_answered;
        if (sortBy === "time") return a.time_left_seconds - b.time_left_seconds;
        return a.name.localeCompare(b.name);
      });
  }, [roster, searchQuery, statusFilter, sortBy]);

  // Compute live window countdown
  const countdownText = useMemo(() => {
    if (!exam) return "-";
    if (!exam.ends_at) return "No closing deadline";

    const adjustedNow = Date.now() + serverOffsetMs;
    const endMs = new Date(exam.ends_at).getTime();
    const diffSec = Math.max(0, Math.floor((endMs - adjustedNow) / 1000));

    if (diffSec <= 0) return "Closed";
    const h = Math.floor(diffSec / 3600);
    const m = Math.floor((diffSec % 3600) / 60);
    if (h > 0) return `Closes in ${h}h ${m}m`;
    return `Closes in ${m}m ${diffSec % 60}s`;
  }, [exam, serverOffsetMs, lastUpdated]);

  const isUrgent = exam?.seconds_remaining !== null && exam?.seconds_remaining !== undefined && exam.seconds_remaining < 600;
  const isWarning = exam?.seconds_remaining !== null && exam?.seconds_remaining !== undefined && exam.seconds_remaining < 1800 && !isUrgent;

  return (
    <DashboardLayout menuItems={menuItems} userRole="Faculty">
      <div className="space-y-6">
        {/* Top Navigation & Live Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-2 border-b border-border">
          <div className="space-y-1">
            <Link
              to="/faculty"
              className="inline-flex items-center gap-1.5 text-xs font-semibold text-primary hover:underline mb-1"
            >
              <ArrowLeft className="w-3.5 h-3.5" /> Back to Dashboard
            </Link>
            <div className="flex items-center gap-2.5 flex-wrap">
              <h1 className="text-xl sm:text-2xl font-bold text-foreground">
                {exam?.title || "Live Exam Monitor"}
              </h1>
              {exam && (
                <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-bold bg-emerald-100 text-emerald-800 border border-emerald-300">
                  <span className="w-2 h-2 rounded-full bg-emerald-600 animate-pulse motion-reduce:hidden" />
                  Live Proctoring
                </span>
              )}
            </div>
            <p className="text-xs text-muted-foreground font-medium">
              Subject: <span className="text-foreground font-semibold">{exam?.subject}</span> · Department:{" "}
              <span className="text-foreground font-semibold">{exam?.department}</span>
            </p>
          </div>

          {/* Action / Refresh controls */}
          <div className="flex items-center gap-3 self-start sm:self-auto">
            <div className="text-right text-xs">
              <div
                className={`font-bold flex items-center gap-1 justify-end ${
                  isUrgent ? "text-rose-600 animate-pulse" : isWarning ? "text-amber-600" : "text-foreground"
                }`}
              >
                <Clock className="w-3.5 h-3.5" />
                {countdownText}
              </div>
              <div className="text-[11px] text-muted-foreground mt-0.5" aria-live="polite">
                Updated {formatRelativeTime(lastUpdated.toISOString())}
              </div>
            </div>
            <button
              onClick={() => void fetchLiveMonitor(false)}
              disabled={isRefreshing}
              className="p-2 rounded-lg bg-card border border-border text-foreground hover:bg-muted transition-colors disabled:opacity-50"
              title="Refresh live roster"
              aria-label="Refresh live roster"
            >
              <RefreshCw className={`w-4 h-4 ${isRefreshing ? "animate-spin" : ""}`} />
            </button>
          </div>
        </div>

        {/* Error State */}
        {error && (
          <div className="bg-destructive/10 border border-destructive/20 rounded-xl p-6 text-center space-y-3">
            <AlertCircle className="w-8 h-8 text-destructive mx-auto" />
            <h3 className="font-bold text-foreground text-sm sm:text-base">Unable to load Live Monitor</h3>
            <p className="text-xs text-muted-foreground max-w-md mx-auto">{error}</p>
            <button
              onClick={() => void fetchLiveMonitor(false)}
              className="px-4 py-2 bg-primary text-white text-xs font-semibold rounded-lg hover:opacity-90 transition-opacity"
            >
              Retry
            </button>
          </div>
        )}

        {/* Loading Skeletons */}
        {loading && !error && (
          <div className="space-y-6 animate-pulse">
            <div className="grid grid-cols-2 sm:grid-cols-5 gap-3.5">
              {[...Array(5)].map((_, i) => (
                <div key={i} className="h-24 bg-muted/60 rounded-xl" />
              ))}
            </div>
            <div className="h-96 bg-muted/60 rounded-xl" />
          </div>
        )}

        {!loading && !error && data && (
          <>
            {/* 5 Invariant KPI Summary Cards */}
            <div className="grid grid-cols-2 sm:grid-cols-5 gap-3.5">
              <div className="bg-card p-4 rounded-xl border border-border shadow-2xs">
                <p className="text-xs text-muted-foreground font-medium uppercase tracking-wider">Assigned Total</p>
                <p className="text-2xl font-bold text-foreground mt-1">{summary?.assigned_total || 0}</p>
                <p className="text-[11px] text-muted-foreground mt-0.5">Eligible students</p>
              </div>

              <div className="bg-card p-4 rounded-xl border border-border shadow-2xs">
                <p className="text-xs text-blue-600 font-semibold uppercase tracking-wider">In Progress</p>
                <p className="text-2xl font-bold text-blue-600 mt-1">{summary?.in_progress || 0}</p>
                <p className="text-[11px] text-muted-foreground mt-0.5">Taking exam now</p>
              </div>

              <div className="bg-card p-4 rounded-xl border border-border shadow-2xs">
                <p className="text-xs text-emerald-600 font-semibold uppercase tracking-wider">Submitted</p>
                <p className="text-2xl font-bold text-emerald-600 mt-1">{summary?.submitted || 0}</p>
                <p className="text-[11px] text-muted-foreground mt-0.5">{summary?.participation_percent || 0}% finished</p>
              </div>

              <div className="bg-card p-4 rounded-xl border border-border shadow-2xs">
                <p className="text-xs text-slate-600 font-semibold uppercase tracking-wider">Not Started</p>
                <p className="text-2xl font-bold text-slate-700 mt-1">{summary?.not_started || 0}</p>
                <p className="text-[11px] text-muted-foreground mt-0.5">Pending launch</p>
              </div>

              <div
                className={`p-4 rounded-xl border shadow-2xs transition-colors cursor-pointer ${
                  (summary?.flagged_students || 0) > 0
                    ? "bg-rose-50/60 border-rose-200 hover:bg-rose-100/60"
                    : "bg-card border-border"
                }`}
                onClick={() => handleFilterChange("flagged")}
                title="Click to filter flagged students"
              >
                <p className="text-xs text-rose-600 font-semibold uppercase tracking-wider flex items-center justify-between">
                  <span>Flagged</span>
                  <ShieldAlert className="w-3.5 h-3.5 text-rose-500" />
                </p>
                <p className="text-2xl font-bold text-rose-600 mt-1">{summary?.flagged_students || 0}</p>
                <p className="text-[11px] text-rose-700/80 mt-0.5 font-medium">
                  {summary?.total_violations || 0} violation events
                </p>
              </div>
            </div>

            {/* Filter, Search & Table Container */}
            <div className="bg-card rounded-xl border border-border shadow-xs overflow-hidden">
              {/* Controls bar */}
              <div className="p-4 border-b border-border flex flex-col md:flex-row md:items-center justify-between gap-3 bg-muted/10">
                {/* Search */}
                <div className="relative flex-1 max-w-sm">
                  <Search className="w-4 h-4 text-muted-foreground absolute left-3 top-1/2 -translate-y-1/2" />
                  <input
                    type="text"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    placeholder="Search by student name or roll number..."
                    className="w-full pl-9 pr-3 py-1.5 text-xs bg-card border border-border rounded-lg text-foreground focus:outline-none focus:ring-2 focus:ring-primary/30"
                  />
                  {searchQuery && (
                    <button
                      onClick={() => setSearchQuery("")}
                      className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                    >
                      <X className="w-3.5 h-3.5" />
                    </button>
                  )}
                </div>

                {/* Filter Pills */}
                <div className="flex items-center gap-1.5 flex-wrap">
                  {[
                    { key: "all", label: `All (${summary?.assigned_total || 0})` },
                    { key: "in_progress", label: `In Progress (${summary?.in_progress || 0})` },
                    { key: "submitted", label: `Submitted (${summary?.submitted || 0})` },
                    { key: "not_started", label: `Not Started (${summary?.not_started || 0})` },
                    { key: "flagged", label: `Flagged (${summary?.flagged_students || 0})` },
                  ].map((tab) => (
                    <button
                      key={tab.key}
                      onClick={() => handleFilterChange(tab.key)}
                      className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                        statusFilter === tab.key
                          ? "bg-primary text-white shadow-xs"
                          : "bg-muted/50 text-muted-foreground hover:text-foreground hover:bg-muted"
                      }`}
                    >
                      {tab.label}
                    </button>
                  ))}
                </div>
              </div>

              {/* Student Roster Table */}
              {filteredRoster.length === 0 ? (
                <div className="p-12 text-center space-y-2">
                  <Users className="w-10 h-10 text-muted-foreground/40 mx-auto" />
                  <h4 className="text-sm font-semibold text-foreground">No students matched your search</h4>
                  <p className="text-xs text-muted-foreground">Try clearing filters or search query.</p>
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs sm:text-sm">
                    <thead className="border-b border-border bg-muted/30 text-muted-foreground font-semibold text-xs">
                      <tr>
                        <th className="py-3 px-4">Student</th>
                        <th className="py-3 px-4">Status</th>
                        <th className="py-3 px-4">Questions Answered</th>
                        <th className="py-3 px-4">Time Left</th>
                        <th className="py-3 px-4">Violations</th>
                        <th className="py-3 px-4">Last Activity</th>
                        <th className="py-3 px-4 text-right">Actions</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border">
                      {filteredRoster.map((student) => (
                        <tr
                          key={student.student_user_id}
                          className="hover:bg-muted/20 transition-colors cursor-pointer"
                          onClick={() => setSelectedStudent(student)}
                        >
                          {/* Student Info */}
                          <td className="py-3.5 px-4">
                            <div>
                              <p className="font-semibold text-foreground text-xs sm:text-sm">{student.name}</p>
                              <p className="text-[11px] text-muted-foreground">
                                {student.student_id} · {student.email}
                              </p>
                            </div>
                          </td>

                          {/* Status */}
                          <td className="py-3.5 px-4 whitespace-nowrap">
                            <span
                              className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold border ${
                                student.status === "in_progress"
                                  ? "bg-blue-50 text-blue-700 border-blue-200"
                                  : student.status === "submitted"
                                  ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                                  : student.status === "auto_submitted"
                                  ? "bg-rose-50 text-rose-700 border-rose-200"
                                  : "bg-slate-100 text-slate-700 border-slate-200"
                              }`}
                            >
                              {student.status === "in_progress" && <PlayCircle className="w-3 h-3 text-blue-600" />}
                              {student.status === "submitted" && <CheckCircle2 className="w-3 h-3 text-emerald-600" />}
                              {student.status === "auto_submitted" && <AlertTriangle className="w-3 h-3 text-rose-600" />}
                              {student.status === "not_started" && <Clock className="w-3 h-3 text-slate-500" />}
                              <span className="capitalize">
                                {student.status === "auto_submitted" ? "Auto Submitted" : student.status.replace("_", " ")}
                              </span>
                            </span>
                          </td>

                          {/* Questions Answered */}
                          <td className="py-3.5 px-4">
                            <div className="w-36 space-y-1">
                              <div className="flex items-center justify-between text-xs">
                                <span className="font-semibold text-foreground">
                                  {student.questions_answered} / {student.total_questions}
                                </span>
                                <span className="text-[11px] text-muted-foreground">
                                  {student.progress_percent}%
                                </span>
                              </div>
                              <div className="w-full h-1.5 bg-muted rounded-full overflow-hidden">
                                <div
                                  className="h-full bg-primary rounded-full transition-all duration-300"
                                  style={{ width: `${student.progress_percent}%` }}
                                />
                              </div>
                            </div>
                          </td>

                          {/* Time Left */}
                          <td className="py-3.5 px-4 whitespace-nowrap font-mono text-xs">
                            {student.status === "in_progress" ? (
                              <span className="font-semibold text-foreground">
                                {formatTimeLeft(student.time_left_seconds)}
                              </span>
                            ) : student.status === "not_started" ? (
                              <span className="text-muted-foreground">{exam?.duration_minutes}m (Not started)</span>
                            ) : (
                              <span className="text-muted-foreground italic">Completed</span>
                            )}
                          </td>

                          {/* Violations */}
                          <td className="py-3.5 px-4 whitespace-nowrap">
                            {student.violation_count > 0 ? (
                              <button
                                onClick={(e) => {
                                  e.stopPropagation();
                                  setSelectedStudent(student);
                                }}
                                className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-bold bg-rose-100 text-rose-800 border border-rose-300 hover:bg-rose-200 transition-colors"
                              >
                                <AlertTriangle className="w-3 h-3" />
                                {student.violation_count} {student.violation_count === 1 ? "warning" : "warnings"}
                              </button>
                            ) : (
                              <span className="text-xs text-muted-foreground">0</span>
                            )}
                          </td>

                          {/* Last Activity */}
                          <td className="py-3.5 px-4 whitespace-nowrap text-xs text-muted-foreground">
                            {formatRelativeTime(student.last_activity)}
                          </td>

                          {/* Actions */}
                          <td className="py-3.5 px-4 text-right whitespace-nowrap">
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                setSelectedStudent(student);
                              }}
                              className="px-2.5 py-1 text-xs font-semibold rounded-md border border-border text-foreground hover:bg-muted transition-colors"
                            >
                              View Timeline
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </>
        )}

        {/* Slide-over Drawer for Student Violation Events Timeline */}
        {selectedStudent && (
          <div
            className="fixed inset-0 z-50 flex justify-end bg-black/40 backdrop-blur-2xs animate-in fade-in-0"
            role="dialog"
            aria-modal="true"
          >
            <div className="bg-card w-full max-w-md h-full shadow-2xl border-l border-border flex flex-col animate-in slide-in-from-right duration-300">
              {/* Drawer Header */}
              <div className="p-5 border-b border-border flex items-start justify-between gap-3 bg-muted/20">
                <div>
                  <h3 className="font-bold text-foreground text-base">{selectedStudent.name}</h3>
                  <p className="text-xs text-muted-foreground">
                    ID: {selectedStudent.student_id} · {selectedStudent.email}
                  </p>
                </div>
                <button
                  onClick={() => setSelectedStudent(null)}
                  className="p-1.5 rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
                  aria-label="Close timeline drawer"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              {/* Status summary */}
              <div className="p-4 border-b border-border bg-muted/10 grid grid-cols-2 gap-3 text-xs">
                <div className="bg-card p-2.5 rounded-lg border border-border/50">
                  <p className="text-[10px] text-muted-foreground uppercase font-medium">Exam Status</p>
                  <p className="font-bold text-foreground mt-0.5 capitalize">
                    {selectedStudent.status.replace("_", " ")}
                  </p>
                </div>
                <div className="bg-card p-2.5 rounded-lg border border-border/50">
                  <p className="text-[10px] text-muted-foreground uppercase font-medium">Violations Logged</p>
                  <p className={`font-bold mt-0.5 ${selectedStudent.violation_count > 0 ? "text-rose-600" : "text-foreground"}`}>
                    {selectedStudent.violation_count} of {exam?.max_warnings ?? 1} allowed
                  </p>
                </div>
              </div>

              {/* Chronological Timeline */}
              <div className="p-5 flex-1 overflow-y-auto space-y-4">
                <h4 className="font-bold text-foreground text-xs uppercase tracking-wider flex items-center gap-1.5">
                  <ShieldAlert className="w-3.5 h-3.5 text-primary" /> Proctoring Events Timeline
                </h4>

                {selectedStudent.violations_timeline.length === 0 ? (
                  <div className="p-8 text-center bg-muted/20 rounded-xl border border-border/40 space-y-2">
                    <CheckCircle2 className="w-8 h-8 text-emerald-600 mx-auto" />
                    <p className="font-semibold text-foreground text-xs sm:text-sm">No violations recorded</p>
                    <p className="text-xs text-muted-foreground">
                      Student has respected all fullscreen and tab constraints.
                    </p>
                  </div>
                ) : (
                  <div className="relative pl-6 space-y-4 before:absolute before:left-2.5 before:top-2 before:bottom-2 before:w-0.5 before:bg-border">
                    {selectedStudent.violations_timeline.map((event, idx) => (
                      <div key={event.id || idx} className="relative">
                        <span className="absolute -left-6 top-1 w-3 h-3 rounded-full bg-rose-500 ring-4 ring-card shrink-0" />
                        <div className="bg-muted/40 p-3 rounded-xl border border-border/60 space-y-1">
                          <div className="flex items-center justify-between text-xs">
                            <span className="font-bold text-rose-700">{event.event_label || event.event_type}</span>
                            <span className="text-[11px] text-muted-foreground font-mono">
                              {new Date(event.timestamp).toLocaleTimeString()}
                            </span>
                          </div>
                          <p className="text-[11px] text-muted-foreground">
                            Event #{selectedStudent.violations_timeline.length - idx} recorded during active attempt.
                          </p>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Drawer Footer */}
              <div className="p-4 border-t border-border bg-muted/20 text-right">
                <button
                  onClick={() => setSelectedStudent(null)}
                  className="px-4 py-2 rounded-lg bg-primary text-white text-xs font-semibold hover:opacity-90 transition-opacity"
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

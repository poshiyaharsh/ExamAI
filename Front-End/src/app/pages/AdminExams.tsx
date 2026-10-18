import { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { DashboardLayout } from "../components/DashboardLayout";
import {
  FileText,
  Search,
  Filter,
  Eye,
  Trash2,
  CheckCircle2,
  Clock,
  AlertCircle,
  X,
  ChevronLeft,
  ChevronRight,
  User,
  BookOpen,
  Award,
  HelpCircle,
  RefreshCw,
  Globe,
  Lock,
  Layers,
  Calendar,
} from "lucide-react";
import { toast } from "sonner";
import {
  adminExamsApi,
  type AdminExamDetail,
  type AdminExamItem,
  type AdminExamsQueryParams,
} from "../../services/api";

type StatusColorMap = {
  bg: string;
  text: string;
  border: string;
};

function getStatusBadgeStyle(status: string): StatusColorMap {
  switch (status.toLowerCase()) {
    case "live":
      return { bg: "bg-emerald-100 text-emerald-800", text: "text-emerald-800", border: "border-emerald-300" };
    case "published":
      return { bg: "bg-emerald-50 text-emerald-700", text: "text-emerald-700", border: "border-emerald-200" };
    case "draft":
      return { bg: "bg-amber-50 text-amber-700", text: "text-amber-700", border: "border-amber-200" };
    case "closed":
      return { bg: "bg-slate-100 text-slate-700", text: "text-slate-700", border: "border-slate-200" };
    case "generating":
      return { bg: "bg-blue-50 text-blue-700", text: "text-blue-700", border: "border-blue-200" };
    case "failed":
      return { bg: "bg-rose-50 text-rose-700", text: "text-rose-700", border: "border-rose-200" };
    default:
      return { bg: "bg-gray-100 text-gray-700", text: "text-gray-700", border: "border-gray-200" };
  }
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return "-";
  try {
    const d = new Date(dateStr);
    return d.toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return dateStr;
  }
}

export function AdminExams() {
  const [exams, setExams] = useState<AdminExamItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // Filters & Search
  const [searchTerm, setSearchTerm] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [searchParams, setSearchParams] = useSearchParams();
  const [facultyFilter, setFacultyFilter] = useState("all");
  const [departmentFilter, setDepartmentFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState(searchParams.get("status") || "all");
  const [subjectFilter, setSubjectFilter] = useState("all");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");

  useEffect(() => {
    const urlStatus = searchParams.get("status") || "all";
    if (urlStatus !== statusFilter) {
      setStatusFilter(urlStatus);
      setPage(1);
    }
  }, [searchParams]);

  const handleStatusChange = (newStatus: string) => {
    setStatusFilter(newStatus);
    setPage(1);
    const newParams = new URLSearchParams(searchParams);
    if (newStatus === "all") {
      newParams.delete("status");
    } else {
      newParams.set("status", newStatus);
    }
    setSearchParams(newParams);
  };

  // Pagination
  const [page, setPage] = useState(1);
  const [pageSize] = useState(10);
  const [totalPages, setTotalPages] = useState(1);
  const [totalCount, setTotalCount] = useState(0);

  // Stats & filter options
  const [stats, setStats] = useState({
    total_exams: 0,
    published_exams: 0,
    draft_exams: 0,
    created_this_week: 0,
  });

  const [filterOptions, setFilterOptions] = useState<{
    faculties: { id: number; name: string; email: string }[];
    departments: string[];
    subjects: string[];
    statuses: { value: string; label: string }[];
  }>({
    faculties: [],
    departments: [],
    subjects: [],
    statuses: [],
  });

  // View Detail Modal
  const [selectedExamId, setSelectedExamId] = useState<number | null>(null);
  const [detailExam, setDetailExam] = useState<AdminExamDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [isDetailOpen, setIsDetailOpen] = useState(false);

  // Status Action & Delete Modals
  const [actionExam, setActionExam] = useState<AdminExamItem | null>(null);
  const [actionType, setActionType] = useState<"publish" | "unpublish" | "delete" | null>(null);
  const [isActionSubmitting, setIsActionSubmitting] = useState(false);

  // Debounce search term
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(searchTerm);
      setPage(1);
    }, 350);
    return () => clearTimeout(timer);
  }, [searchTerm]);

  const fetchExams = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const params: AdminExamsQueryParams = {
        page,
        page_size: pageSize,
      };

      if (debouncedSearch.trim()) params.search = debouncedSearch.trim();
      if (facultyFilter !== "all") params.faculty = facultyFilter;
      if (departmentFilter !== "all") params.department = departmentFilter;
      if (statusFilter !== "all") params.status = statusFilter;
      if (subjectFilter !== "all") params.subject = subjectFilter;
      if (startDate) params.start_date = startDate;
      if (endDate) params.end_date = endDate;

      const response = await adminExamsApi.getExams(params);
      if (response.status === "success") {
        setExams(response.data);
        setTotalPages(response.pagination.total_pages);
        setTotalCount(response.pagination.total_count);
        setStats(response.stats);
        if (response.filter_options) {
          setFilterOptions(response.filter_options);
        }
      } else {
        setError("Failed to fetch exams.");
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Unable to load exams.";
      setError(msg);
      toast.error(msg);
    } finally {
      setLoading(false);
    }
  }, [page, pageSize, debouncedSearch, facultyFilter, departmentFilter, statusFilter, subjectFilter, startDate, endDate]);

  useEffect(() => {
    void fetchExams();
  }, [fetchExams]);

  const handleOpenDetail = async (examId: number) => {
    setSelectedExamId(examId);
    setIsDetailOpen(true);
    setDetailLoading(true);
    try {
      const response = await adminExamsApi.getExamDetail(examId);
      if (response.status === "success") {
        setDetailExam(response.data);
      } else {
        toast.error("Unable to load exam details.");
      }
    } catch {
      toast.error("Failed to fetch exam details.");
    } finally {
      setDetailLoading(false);
    }
  };

  const handleConfirmAction = async () => {
    if (!actionExam || !actionType) return;
    setIsActionSubmitting(true);
    try {
      if (actionType === "delete") {
        await adminExamsApi.deleteExam(actionExam.id);
        toast.success(`Exam "${actionExam.title}" deleted successfully.`);
        if (selectedExamId === actionExam.id) {
          setIsDetailOpen(false);
        }
      } else if (actionType === "publish") {
        await adminExamsApi.updateExamStatus(actionExam.id, "published");
        toast.success(`Exam "${actionExam.title}" is now published.`);
        if (selectedExamId === actionExam.id) {
          void handleOpenDetail(actionExam.id);
        }
      } else if (actionType === "unpublish") {
        await adminExamsApi.updateExamStatus(actionExam.id, "draft");
        toast.success(`Exam "${actionExam.title}" moved to draft.`);
        if (selectedExamId === actionExam.id) {
          void handleOpenDetail(actionExam.id);
        }
      }
      setActionExam(null);
      setActionType(null);
      void fetchExams();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Action failed. Please try again.";
      toast.error(msg);
    } finally {
      setIsActionSubmitting(false);
    }
  };

  const resetFilters = () => {
    setSearchTerm("");
    setDebouncedSearch("");
    setFacultyFilter("all");
    setDepartmentFilter("all");
    setStatusFilter("all");
    setSubjectFilter("all");
    setStartDate("");
    setEndDate("");
    setPage(1);
    const newParams = new URLSearchParams(searchParams);
    newParams.delete("status");
    setSearchParams(newParams);
  };

  const hasActiveFilters = useMemo(() => {
    return (
      debouncedSearch.trim() !== "" ||
      facultyFilter !== "all" ||
      departmentFilter !== "all" ||
      statusFilter !== "all" ||
      subjectFilter !== "all" ||
      startDate !== "" ||
      endDate !== ""
    );
  }, [debouncedSearch, facultyFilter, departmentFilter, statusFilter, subjectFilter, startDate, endDate]);

  return (
    <DashboardLayout userRole="Admin">
      <div className="space-y-6 min-w-0 max-w-full">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="text-2xl sm:text-3xl font-bold text-foreground mb-1">Faculty Exams</h1>
            <p className="text-xs sm:text-sm text-muted-foreground">
              Monitor, inspect, and manage all exams generated and authored by faculty members
            </p>
          </div>
          <button
            onClick={() => void fetchExams()}
            className="self-start sm:self-auto px-4 py-2 rounded-lg border border-border bg-card text-foreground hover:bg-muted/50 font-medium text-sm transition-all flex items-center gap-2"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
            Refresh
          </button>
        </div>

        {/* Stats Strip */}
        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="bg-card rounded-xl p-5 shadow-sm border border-border hover:shadow-md transition-all">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs sm:text-sm text-muted-foreground mb-1">Total Exams</p>
                <p className="text-2xl sm:text-3xl font-bold text-foreground">{stats.total_exams}</p>
              </div>
              <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center text-primary">
                <FileText className="w-5 h-5" />
              </div>
            </div>
          </div>

          <div className="bg-card rounded-xl p-5 shadow-sm border border-border hover:shadow-md transition-all">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs sm:text-sm text-muted-foreground mb-1">Published</p>
                <p className="text-2xl sm:text-3xl font-bold text-emerald-600">{stats.published_exams}</p>
              </div>
              <div className="w-10 h-10 rounded-lg bg-emerald-50 flex items-center justify-center text-emerald-600">
                <Globe className="w-5 h-5" />
              </div>
            </div>
          </div>

          <div className="bg-card rounded-xl p-5 shadow-sm border border-border hover:shadow-md transition-all">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs sm:text-sm text-muted-foreground mb-1">Drafts</p>
                <p className="text-2xl sm:text-3xl font-bold text-amber-600">{stats.draft_exams}</p>
              </div>
              <div className="w-10 h-10 rounded-lg bg-amber-50 flex items-center justify-center text-amber-600">
                <Clock className="w-5 h-5" />
              </div>
            </div>
          </div>

          <div className="bg-card rounded-xl p-5 shadow-sm border border-border hover:shadow-md transition-all">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs sm:text-sm text-muted-foreground mb-1">Created This Week</p>
                <p className="text-2xl sm:text-3xl font-bold text-indigo-600">{stats.created_this_week}</p>
              </div>
              <div className="w-10 h-10 rounded-lg bg-indigo-50 flex items-center justify-center text-indigo-600">
                <Calendar className="w-5 h-5" />
              </div>
            </div>
          </div>
        </div>

        {/* Filter & Search Bar */}
        <div className="bg-card rounded-xl p-4 sm:p-5 shadow-sm border border-border space-y-4">
          <div className="flex flex-col md:flex-row gap-3">
            {/* Search Input */}
            <div className="flex-1 relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
              <input
                type="text"
                placeholder="Search by title, topics, or faculty name/email..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full pl-9 pr-3.5 py-2 rounded-lg bg-input-background border border-border text-sm focus:outline-none focus:ring-2 focus:ring-primary transition-all text-foreground"
              />
            </div>

            {/* Quick Filter: Status */}
            <div className="w-full sm:w-48">
              <select
                value={statusFilter}
                onChange={(e) => handleStatusChange(e.target.value)}
                className="w-full px-3 py-2 rounded-lg bg-input-background border border-border text-sm focus:outline-none focus:ring-2 focus:ring-primary transition-all text-foreground"
              >
                <option value="all">All Statuses</option>
                <option value="live">Live / Active Now</option>
                <option value="published">Published</option>
                <option value="draft">Draft</option>
                <option value="closed">Closed / Completed</option>
                <option value="generating">Generating</option>
                <option value="failed">Failed</option>
              </select>
            </div>
          </div>

          {/* Secondary Filters Strip */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 pt-2 border-t border-border">
            {/* Faculty Filter */}
            <div>
              <label className="block text-xs font-medium text-muted-foreground mb-1">Filter by Faculty</label>
              <select
                value={facultyFilter}
                onChange={(e) => {
                  setFacultyFilter(e.target.value);
                  setPage(1);
                }}
                className="w-full px-3 py-1.5 rounded-lg bg-input-background border border-border text-xs focus:outline-none focus:ring-2 focus:ring-primary transition-all text-foreground"
              >
                <option value="all">All Faculty</option>
                {filterOptions.faculties.map((f) => (
                  <option key={f.id} value={f.id}>
                    {f.name} ({f.email})
                  </option>
                ))}
              </select>
            </div>

            {/* Department Filter */}
            <div>
              <label className="block text-xs font-medium text-muted-foreground mb-1">Filter by Department</label>
              <select
                value={departmentFilter}
                onChange={(e) => {
                  setDepartmentFilter(e.target.value);
                  setPage(1);
                }}
                className="w-full px-3 py-1.5 rounded-lg bg-input-background border border-border text-xs focus:outline-none focus:ring-2 focus:ring-primary transition-all text-foreground"
              >
                <option value="all">All Departments</option>
                {filterOptions.departments.map((dept) => (
                  <option key={dept} value={dept}>
                    {dept}
                  </option>
                ))}
              </select>
            </div>

            {/* Subject/Topic Filter */}
            <div>
              <label className="block text-xs font-medium text-muted-foreground mb-1">Filter by Subject / Topic</label>
              <select
                value={subjectFilter}
                onChange={(e) => {
                  setSubjectFilter(e.target.value);
                  setPage(1);
                }}
                className="w-full px-3 py-1.5 rounded-lg bg-input-background border border-border text-xs focus:outline-none focus:ring-2 focus:ring-primary transition-all text-foreground"
              >
                <option value="all">All Subjects / Topics</option>
                {filterOptions.subjects.map((sub) => (
                  <option key={sub} value={sub}>
                    {sub}
                  </option>
                ))}
              </select>
            </div>

            {/* Date Range / Reset */}
            <div className="flex items-end gap-2">
              <div className="flex-1">
                <label className="block text-xs font-medium text-muted-foreground mb-1">Created From</label>
                <input
                  type="date"
                  value={startDate}
                  onChange={(e) => {
                    setStartDate(e.target.value);
                    setPage(1);
                  }}
                  className="w-full px-2.5 py-1.5 rounded-lg bg-input-background border border-border text-xs focus:outline-none focus:ring-2 focus:ring-primary transition-all text-foreground"
                />
              </div>
              {hasActiveFilters && (
                <button
                  onClick={resetFilters}
                  className="px-3 py-1.5 rounded-lg border border-border bg-muted/30 hover:bg-muted text-xs font-medium text-muted-foreground transition-colors whitespace-nowrap"
                >
                  Reset
                </button>
              )}
            </div>
          </div>
        </div>

        {/* Exams Table Card */}
        <div className="bg-card rounded-xl shadow-sm border border-border overflow-hidden">
          {loading ? (
            <div className="p-12 text-center text-muted-foreground flex flex-col items-center justify-center gap-3">
              <RefreshCw className="w-8 h-8 animate-spin text-primary" />
              <p className="text-sm font-medium">Loading faculty exams...</p>
            </div>
          ) : error ? (
            <div className="p-12 text-center text-rose-600 flex flex-col items-center justify-center gap-3">
              <AlertCircle className="w-8 h-8" />
              <p className="text-sm font-medium">{error}</p>
              <button
                onClick={() => void fetchExams()}
                className="px-4 py-2 rounded-lg bg-primary text-white text-xs font-medium hover:opacity-90"
              >
                Retry
              </button>
            </div>
          ) : exams.length === 0 ? (
            <div className="text-center py-16 px-4">
              <FileText className="w-16 h-16 text-muted-foreground/40 mx-auto mb-4" />
              <h3 className="text-lg font-semibold text-foreground mb-1">No exams found</h3>
              <p className="text-sm text-muted-foreground max-w-md mx-auto mb-4">
                {hasActiveFilters
                  ? "No exams match your active search and filter criteria. Try adjusting or clearing your filters."
                  : "No faculty members have generated or created exams in your institution yet."}
              </p>
              {hasActiveFilters && (
                <button
                  onClick={resetFilters}
                  className="px-4 py-2 rounded-lg bg-primary text-white text-xs font-medium hover:opacity-90 transition-all"
                >
                  Clear All Filters
                </button>
              )}
            </div>
          ) : (
            <div className="w-full min-w-0 max-w-full">
              {/* Desktop Table (>= xl) with table-layout: fixed */}
              <div className="hidden xl:block w-full min-w-0">
                <table className="w-full text-left border-collapse table-fixed">
                  <thead className="bg-muted/50 border-b border-border text-xs uppercase font-semibold text-muted-foreground tracking-wider">
                    <tr>
                      <th className="px-4 py-3.5 truncate">Exam Title & Subject</th>
                      <th className="w-44 px-3 py-3.5 truncate">Faculty / Dept</th>
                      <th className="w-20 px-3 py-3.5 truncate">Duration</th>
                      <th className="w-28 px-3 py-3.5 truncate">Total Marks</th>
                      <th className="w-20 px-3 py-3.5 text-center truncate">Questions</th>
                      <th className="w-20 px-3 py-3.5 text-center truncate hidden 2xl:table-cell">Attempts</th>
                      <th className="w-28 px-3 py-3.5 truncate">Status</th>
                      <th className="w-28 px-3 py-3.5 truncate hidden 2xl:table-cell">Created On</th>
                      <th className="w-28 px-4 py-3.5 text-right truncate">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border text-sm">
                    {exams.map((exam) => {
                      const badge = getStatusBadgeStyle(exam.status);
                      return (
                        <tr key={exam.id} className="hover:bg-muted/30 transition-colors">
                          {/* Title & Subject */}
                          <td className="px-4 py-3.5 overflow-hidden">
                            <div className="min-w-0">
                              <button
                                onClick={() => void handleOpenDetail(exam.id)}
                                className="font-semibold text-foreground hover:text-primary transition-colors text-left truncate block text-sm w-full"
                                title={exam.title}
                              >
                                {exam.title}
                              </button>
                              <p className="text-xs text-muted-foreground font-medium mt-0.5 truncate" title={exam.subject || "General Course"}>
                                {exam.subject || "General Course"}
                              </p>
                              {Array.isArray(exam.topics) && exam.topics.length > 0 && (
                                <div className="flex flex-wrap items-center gap-1 mt-1.5 overflow-hidden">
                                  {exam.topics.slice(0, 2).map((t, tIdx) => (
                                    <span
                                      key={tIdx}
                                      className="inline-block px-1.5 py-0.5 rounded bg-muted/70 text-[10px] text-muted-foreground truncate max-w-[100px]"
                                      title={t}
                                    >
                                      {t}
                                    </span>
                                  ))}
                                  {exam.topics.length > 2 && (
                                    <button
                                      type="button"
                                      onClick={() => void handleOpenDetail(exam.id)}
                                      className="text-[10px] text-primary hover:underline font-semibold shrink-0"
                                    >
                                      +{exam.topics.length - 2} more
                                    </button>
                                  )}
                                </div>
                              )}
                            </div>
                          </td>

                          {/* Faculty & Dept */}
                          <td className="px-3 py-3.5 overflow-hidden">
                            <div className="flex items-center gap-2 min-w-0">
                              <div className="w-7 h-7 rounded-full bg-primary/10 text-primary flex items-center justify-center font-bold text-xs shrink-0">
                                {exam.faculty?.name?.charAt(0) || "F"}
                              </div>
                              <div className="min-w-0 flex-1">
                                <p className="font-medium text-foreground text-xs truncate" title={exam.faculty?.name || "Unknown Faculty"}>
                                  {exam.faculty?.name || "Unknown Faculty"}
                                </p>
                                <p className="text-xs text-muted-foreground truncate" title={exam.faculty?.department || exam.faculty?.email}>
                                  {exam.faculty?.department || exam.faculty?.email}
                                </p>
                              </div>
                            </div>
                          </td>

                          {/* Duration */}
                          <td className="px-3 py-3.5 text-xs text-foreground truncate">
                            {exam.duration_minutes} min
                          </td>

                          {/* Total Marks */}
                          <td className="px-3 py-3.5 text-xs text-foreground overflow-hidden">
                            <div className="truncate">
                              <span className="font-semibold">
                                {exam.total_marks}
                                {exam.target_total_marks && exam.target_total_marks !== exam.total_marks
                                  ? ` / ${exam.target_total_marks}`
                                  : ""} pts
                              </span>
                            </div>
                            {exam.marks_shortfall !== undefined && exam.marks_shortfall > 0 && (
                              <span className="inline-block px-1.5 py-0.5 rounded bg-amber-100 text-amber-800 text-[10px] font-bold border border-amber-200 mt-0.5 truncate max-w-full">
                                {exam.marks_shortfall} short
                              </span>
                            )}
                          </td>

                          {/* Questions count */}
                          <td className="px-3 py-3.5 text-xs text-center text-foreground font-medium">
                            <span className="inline-block px-2 py-0.5 rounded bg-muted/60 text-xs">
                              {exam.question_count}
                            </span>
                          </td>

                          {/* Attempts count (hidden below 2xl) */}
                          <td className="px-3 py-3.5 text-xs text-center text-foreground font-medium hidden 2xl:table-cell">
                            <span className="inline-block px-2 py-0.5 rounded bg-muted/60 text-xs">
                              {exam.attempts_count}
                            </span>
                          </td>

                          {/* Status */}
                          <td className="px-3 py-3.5 overflow-hidden">
                            <span
                              className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border capitalize truncate max-w-full ${badge.bg} ${badge.border}`}
                              title={exam.status}
                            >
                              {exam.status}
                            </span>
                          </td>

                          {/* Created On (hidden below 2xl) */}
                          <td className="px-3 py-3.5 text-xs text-muted-foreground truncate hidden 2xl:table-cell" title={formatDate(exam.created_at)}>
                            {formatDate(exam.created_at)}
                          </td>

                          {/* Actions */}
                          <td className="px-4 py-3.5 text-right">
                            <div className="inline-flex items-center gap-1 shrink-0">
                              <button
                                onClick={() => void handleOpenDetail(exam.id)}
                                className="p-1.5 rounded-md hover:bg-muted text-muted-foreground hover:text-foreground transition-colors"
                                title="View Details"
                                aria-label="View Details"
                              >
                                <Eye className="w-4 h-4" />
                              </button>

                              {exam.status.toLowerCase() === "draft" && (
                                <button
                                  onClick={() => {
                                    setActionExam(exam);
                                    setActionType("publish");
                                  }}
                                  className="p-1.5 rounded-md hover:bg-emerald-50 text-emerald-600 transition-colors"
                                  title="Publish Exam"
                                  aria-label="Publish Exam"
                                >
                                  <Globe className="w-4 h-4" />
                                </button>
                              )}

                              {exam.status.toLowerCase() === "published" && (
                                <button
                                  onClick={() => {
                                    setActionExam(exam);
                                    setActionType("unpublish");
                                  }}
                                  className="p-1.5 rounded-md hover:bg-amber-50 text-amber-600 transition-colors"
                                  title="Unpublish Exam"
                                  aria-label="Unpublish Exam"
                                >
                                  <Lock className="w-4 h-4" />
                                </button>
                              )}

                              <button
                                onClick={() => {
                                  setActionExam(exam);
                                  setActionType("delete");
                                }}
                                className="p-1.5 rounded-md hover:bg-rose-50 text-rose-600 transition-colors"
                                title="Delete Exam"
                                aria-label="Delete Exam"
                              >
                                <Trash2 className="w-4 h-4" />
                              </button>
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>

              {/* Tablet & Mobile Stacked Cards (< 1280px) with zero horizontal overflow */}
              <div className="xl:hidden divide-y divide-border">
                {exams.map((exam) => {
                  const badge = getStatusBadgeStyle(exam.status);
                  return (
                    <div key={exam.id} className="p-4 space-y-3">
                      {/* Title & Status */}
                      <div className="flex items-start justify-between gap-2">
                        <div className="min-w-0 flex-1">
                          <button
                            onClick={() => void handleOpenDetail(exam.id)}
                            className="font-semibold text-foreground hover:text-primary transition-colors text-left text-sm line-clamp-1"
                            title={exam.title}
                          >
                            {exam.title}
                          </button>
                          <p className="text-xs text-muted-foreground font-medium mt-0.5 truncate">
                            {exam.subject || "General Course"}
                          </p>
                        </div>
                        <span
                          className={`inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-medium border capitalize shrink-0 ${badge.bg} ${badge.border}`}
                        >
                          {exam.status}
                        </span>
                      </div>

                      {/* Faculty Info */}
                      <div className="flex items-center gap-2 text-xs text-muted-foreground">
                        <div className="w-6 h-6 rounded-full bg-primary/10 text-primary flex items-center justify-center font-bold text-[10px] shrink-0">
                          {exam.faculty?.name?.charAt(0) || "F"}
                        </div>
                        <span className="font-medium text-foreground truncate">{exam.faculty?.name || "Unknown Faculty"}</span>
                        <span>•</span>
                        <span className="truncate">{exam.faculty?.department || exam.faculty?.email}</span>
                      </div>

                      {/* Compact Topics */}
                      {Array.isArray(exam.topics) && exam.topics.length > 0 && (
                        <div className="flex flex-wrap items-center gap-1">
                          {exam.topics.slice(0, 2).map((t, tIdx) => (
                            <span
                              key={tIdx}
                              className="inline-block px-1.5 py-0.5 rounded bg-muted text-[10px] text-muted-foreground truncate max-w-[120px]"
                            >
                              {t}
                            </span>
                          ))}
                          {exam.topics.length > 2 && (
                            <button
                              type="button"
                              onClick={() => void handleOpenDetail(exam.id)}
                              className="text-[10px] text-primary font-semibold hover:underline"
                            >
                              +{exam.topics.length - 2} more
                            </button>
                          )}
                        </div>
                      )}

                      {/* 4-Stat Specs Grid */}
                      <div className="grid grid-cols-2 gap-2 text-xs bg-muted/40 p-2.5 rounded-lg border border-border/50">
                        <div>
                          <span className="text-muted-foreground">Duration: </span>
                          <strong className="text-foreground">{exam.duration_minutes}m</strong>
                        </div>
                        <div>
                          <span className="text-muted-foreground">Marks: </span>
                          <strong className="text-foreground">
                            {exam.total_marks}
                            {exam.target_total_marks && exam.target_total_marks !== exam.total_marks
                              ? `/${exam.target_total_marks}`
                              : ""}{" "}
                            pts
                          </strong>
                        </div>
                        <div>
                          <span className="text-muted-foreground">Questions: </span>
                          <strong className="text-foreground">{exam.question_count}</strong>
                        </div>
                        <div>
                          <span className="text-muted-foreground">Attempts: </span>
                          <strong className="text-foreground">{exam.attempts_count}</strong>
                        </div>
                      </div>

                      {/* Shortfall notice if applicable */}
                      {exam.marks_shortfall !== undefined && exam.marks_shortfall > 0 && (
                        <div className="px-2.5 py-1 rounded-md bg-amber-50 text-amber-800 text-xs font-medium border border-amber-200 flex items-center justify-between">
                          <span>Shortfall detected:</span>
                          <span className="font-bold">{exam.marks_shortfall} marks short</span>
                        </div>
                      )}

                      {/* Card Actions */}
                      <div className="flex items-center justify-between pt-1">
                        <span className="text-[11px] text-muted-foreground">{formatDate(exam.created_at)}</span>
                        <div className="flex items-center gap-1.5">
                          <button
                            onClick={() => void handleOpenDetail(exam.id)}
                            className="px-2.5 py-1 rounded-md border border-border bg-card text-foreground hover:bg-muted text-xs font-medium transition-colors flex items-center gap-1"
                            title="View Details"
                          >
                            <Eye className="w-3.5 h-3.5" />
                            Details
                          </button>
                          {exam.status.toLowerCase() === "draft" && (
                            <button
                              onClick={() => {
                                setActionExam(exam);
                                setActionType("publish");
                              }}
                              className="px-2.5 py-1 rounded-md bg-emerald-600 text-white hover:bg-emerald-700 text-xs font-medium transition-colors flex items-center gap-1"
                              title="Publish"
                            >
                              <Globe className="w-3.5 h-3.5" />
                              Publish
                            </button>
                          )}
                          <button
                            onClick={() => {
                              setActionExam(exam);
                              setActionType("delete");
                            }}
                            className="p-1 rounded-md hover:bg-rose-50 text-rose-600 transition-colors"
                            title="Delete"
                            aria-label="Delete"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Pagination Bar */}
          {!loading && !error && totalPages > 1 && (
            <div className="flex flex-col sm:flex-row items-center justify-between px-5 py-3.5 border-t border-border bg-muted/20 text-xs text-muted-foreground gap-3">
              <div>
                Showing page <span className="font-semibold text-foreground">{page}</span> of{" "}
                <span className="font-semibold text-foreground">{totalPages}</span> ({totalCount} total exams)
              </div>
              <div className="inline-flex items-center gap-1.5">
                <button
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page <= 1}
                  className="px-2.5 py-1.5 rounded-md border border-border bg-card hover:bg-muted text-foreground disabled:opacity-40 disabled:cursor-not-allowed transition-all flex items-center gap-1"
                >
                  <ChevronLeft className="w-3.5 h-3.5" />
                  Previous
                </button>
                <button
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  disabled={page >= totalPages}
                  className="px-2.5 py-1.5 rounded-md border border-border bg-card hover:bg-muted text-foreground disabled:opacity-40 disabled:cursor-not-allowed transition-all flex items-center gap-1"
                >
                  Next
                  <ChevronRight className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* VIEW EXAM DETAIL MODAL */}
      {isDetailOpen && (
        <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm flex items-center justify-center p-3 sm:p-5 overflow-y-auto">
          <div className="bg-card w-full max-w-4xl rounded-2xl shadow-xl border border-border overflow-hidden my-auto max-h-[90vh] flex flex-col">
            {/* Modal Header */}
            <div className="flex items-center justify-between p-5 border-b border-border bg-muted/20">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center text-primary font-bold">
                  <BookOpen className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="font-bold text-lg text-foreground">
                    {detailLoading ? "Loading Exam Details..." : detailExam?.title || "Exam Details"}
                  </h3>
                  <p className="text-xs text-muted-foreground">
                    {detailExam?.faculty?.name ? `Created by ${detailExam.faculty.name}` : "Faculty Assessment Paper"}
                  </p>
                </div>
              </div>
              <button
                onClick={() => setIsDetailOpen(false)}
                className="p-1.5 rounded-lg text-muted-foreground hover:bg-muted hover:text-foreground transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Modal Body */}
            <div className="p-5 overflow-y-auto flex-1 space-y-6">
              {detailLoading ? (
                <div className="py-16 text-center text-muted-foreground flex flex-col items-center justify-center gap-3">
                  <RefreshCw className="w-8 h-8 animate-spin text-primary" />
                  <p className="text-sm">Fetching questions and exam configuration...</p>
                </div>
              ) : !detailExam ? (
                <div className="py-12 text-center text-muted-foreground">
                  <AlertCircle className="w-10 h-10 mx-auto mb-2 text-rose-500" />
                  <p>Unable to load exam details.</p>
                </div>
              ) : (
                <>
                  {/* Exam Info Grid */}
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 bg-muted/30 p-4 rounded-xl border border-border text-xs">
                    <div>
                      <span className="text-muted-foreground block mb-0.5">Duration</span>
                      <span className="font-semibold text-foreground text-sm flex items-center gap-1">
                        <Clock className="w-3.5 h-3.5 text-muted-foreground" />
                        {detailExam.duration_minutes} minutes
                      </span>
                    </div>
                    <div>
                      <span className="text-muted-foreground block mb-0.5">Total Marks</span>
                      <span className="font-semibold text-foreground text-sm flex items-center gap-1">
                        <Award className="w-3.5 h-3.5 text-muted-foreground" />
                        {detailExam.total_marks}
                        {detailExam.target_total_marks && detailExam.target_total_marks !== detailExam.total_marks
                          ? ` / ${detailExam.target_total_marks}`
                          : ""} pts
                      </span>
                      {detailExam.marks_shortfall !== undefined && detailExam.marks_shortfall > 0 && (
                        <span className="text-[10px] text-amber-700 font-bold block mt-0.5">
                          {detailExam.marks_shortfall} marks shortfall
                        </span>
                      )}
                    </div>
                    <div>
                      <span className="text-muted-foreground block mb-0.5">Total Questions</span>
                      <span className="font-semibold text-foreground text-sm flex items-center gap-1">
                        <HelpCircle className="w-3.5 h-3.5 text-muted-foreground" />
                        {detailExam.question_count}
                      </span>
                    </div>
                    <div>
                      <span className="text-muted-foreground block mb-0.5">Student Attempts</span>
                      <span className="font-semibold text-foreground text-sm flex items-center gap-1">
                        <User className="w-3.5 h-3.5 text-muted-foreground" />
                        {detailExam.attempts_count}
                      </span>
                    </div>
                  </div>

                  {/* Faculty & Author Info Card */}
                  <div className="p-4 rounded-xl border border-border bg-card space-y-2">
                    <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                      Faculty Author Information
                    </h4>
                    <div className="flex flex-wrap items-center gap-4 text-xs text-foreground">
                      <div>
                        <span className="text-muted-foreground">Name: </span>
                        <span className="font-medium">{detailExam.faculty?.name || "N/A"}</span>
                      </div>
                      <div>
                        <span className="text-muted-foreground">Email: </span>
                        <span className="font-medium">{detailExam.faculty?.email || "N/A"}</span>
                      </div>
                      {detailExam.faculty?.department && (
                        <div>
                          <span className="text-muted-foreground">Department: </span>
                          <span className="font-medium">{detailExam.faculty.department}</span>
                        </div>
                      )}
                      {detailExam.faculty?.employee_id && (
                        <div>
                          <span className="text-muted-foreground">Employee ID: </span>
                          <span className="font-medium">{detailExam.faculty.employee_id}</span>
                        </div>
                      )}
                      <div>
                        <span className="text-muted-foreground">AI Model: </span>
                        <span className="font-medium">{detailExam.ai_model_used || "N/A"}</span>
                      </div>
                      <div>
                        <span className="text-muted-foreground">Status: </span>
                        <span
                          className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium border uppercase ${
                            getStatusBadgeStyle(detailExam.status).bg
                          }`}
                        >
                          {detailExam.status}
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Topics Tags */}
                  {Array.isArray(detailExam.topics) && detailExam.topics.length > 0 && (
                    <div>
                      <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-2">
                        Topics & Subject Coverage
                      </h4>
                      <div className="flex flex-wrap gap-1.5">
                        {detailExam.topics.map((t, idx) => (
                          <span
                            key={idx}
                            className="px-2.5 py-1 rounded-md bg-primary/10 text-primary text-xs font-medium"
                          >
                            {t}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Questions List */}
                  <div className="space-y-4">
                    <div className="flex items-center justify-between">
                      <h4 className="text-sm font-bold text-foreground flex items-center gap-2">
                        <Layers className="w-4 h-4 text-primary" />
                        Questions ({detailExam.questions?.length || 0})
                      </h4>
                      <span className="text-xs text-muted-foreground">
                        Total Marks: {detailExam.total_marks}
                      </span>
                    </div>

                    {!detailExam.questions || detailExam.questions.length === 0 ? (
                      <div className="p-8 text-center border border-dashed border-border rounded-xl text-muted-foreground text-xs">
                        No questions generated or added for this exam yet.
                      </div>
                    ) : (
                      <div className="space-y-4">
                        {detailExam.questions.map((q, idx) => (
                          <div
                            key={q.id || idx}
                            className="p-4 rounded-xl border border-border bg-card space-y-3 shadow-xs hover:border-primary/30 transition-all"
                          >
                            {/* Question Header */}
                            <div className="flex items-center justify-between flex-wrap gap-2">
                              <div className="flex items-center gap-2">
                                <span className="w-6 h-6 rounded-full bg-primary/10 text-primary font-bold text-xs flex items-center justify-center">
                                  {q.order || idx + 1}
                                </span>
                                <span className="px-2 py-0.5 rounded text-xs font-medium bg-muted text-muted-foreground uppercase">
                                  {q.question_type}
                                </span>
                                <span className="px-2 py-0.5 rounded text-xs font-medium bg-muted text-muted-foreground capitalize">
                                  {q.difficulty}
                                </span>
                              </div>
                              <span className="text-xs font-semibold text-primary px-2 py-0.5 rounded bg-primary/5">
                                {q.marks} {q.marks === 1 ? "Mark" : "Marks"}
                              </span>
                            </div>

                            {/* Question Prompt */}
                            <p className="text-sm font-medium text-foreground leading-relaxed whitespace-pre-wrap">
                              {q.text}
                            </p>

                            {/* Options if MCQ or True/False */}
                            {Array.isArray(q.options) && q.options.length > 0 && (
                              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 pt-1">
                                {q.options.map((opt, optIdx) => {
                                  const isCorrect =
                                    String(q.correct_answer).trim().toLowerCase() ===
                                    String(opt).trim().toLowerCase();
                                  return (
                                    <div
                                      key={optIdx}
                                      className={`p-2.5 rounded-lg border text-xs flex items-start gap-2 ${
                                        isCorrect
                                          ? "border-emerald-300 bg-emerald-50 text-emerald-900 font-medium"
                                          : "border-border bg-muted/20 text-foreground"
                                      }`}
                                    >
                                      <span className="font-bold text-muted-foreground uppercase">
                                        {String.fromCharCode(65 + optIdx)}.
                                      </span>
                                      <span className="flex-1">{opt}</span>
                                      {isCorrect && (
                                        <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0 ml-auto" />
                                      )}
                                    </div>
                                  );
                                })}
                              </div>
                            )}

                            {/* Correct Answer or Model Answer */}
                            <div className="pt-1 text-xs">
                              {q.correct_answer !== undefined &&
                                q.correct_answer !== null &&
                                !Array.isArray(q.options) && (
                                  <div className="p-2.5 rounded-lg bg-emerald-50 text-emerald-900 border border-emerald-200">
                                    <span className="font-semibold block text-emerald-700">Correct Answer:</span>
                                    <span>{String(q.correct_answer)}</span>
                                  </div>
                                )}

                              {q.model_answer && (
                                <div className="mt-2 p-2.5 rounded-lg bg-blue-50 text-blue-900 border border-blue-200">
                                  <span className="font-semibold block text-blue-700">Model / Reference Answer:</span>
                                  <span className="whitespace-pre-wrap">{q.model_answer}</span>
                                </div>
                              )}
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </>
              )}
            </div>

            {/* Modal Footer */}
            <div className="p-4 border-t border-border bg-muted/20 flex items-center justify-between">
              <div>
                {detailExam && (
                  <span className="text-xs text-muted-foreground">
                    Created on {formatDate(detailExam.created_at)}
                  </span>
                )}
              </div>
              <div className="flex items-center gap-2">
                {detailExam?.status.toLowerCase() === "draft" && (
                  <button
                    onClick={() => {
                      setActionExam(detailExam);
                      setActionType("publish");
                    }}
                    className="px-4 py-2 rounded-lg bg-emerald-600 text-white font-medium text-xs hover:bg-emerald-700 transition-all flex items-center gap-1.5"
                  >
                    <Globe className="w-3.5 h-3.5" />
                    Publish Exam
                  </button>
                )}
                {detailExam?.status.toLowerCase() === "published" && (
                  <button
                    onClick={() => {
                      setActionExam(detailExam);
                      setActionType("unpublish");
                    }}
                    className="px-4 py-2 rounded-lg bg-amber-600 text-white font-medium text-xs hover:bg-amber-700 transition-all flex items-center gap-1.5"
                  >
                    <Lock className="w-3.5 h-3.5" />
                    Unpublish Exam
                  </button>
                )}
                <button
                  onClick={() => setIsDetailOpen(false)}
                  className="px-4 py-2 rounded-lg border border-border bg-card hover:bg-muted text-foreground font-medium text-xs transition-all"
                >
                  Close
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* CONFIRMATION MODAL (Publish, Unpublish, Delete) */}
      {actionExam && actionType && (
        <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-card w-full max-w-md rounded-2xl shadow-xl border border-border p-6 space-y-4">
            <div className="flex items-center gap-3">
              <div
                className={`w-10 h-10 rounded-full flex items-center justify-center shrink-0 ${
                  actionType === "delete"
                    ? "bg-rose-100 text-rose-600"
                    : actionType === "publish"
                    ? "bg-emerald-100 text-emerald-600"
                    : "bg-amber-100 text-amber-600"
                }`}
              >
                {actionType === "delete" ? (
                  <Trash2 className="w-5 h-5" />
                ) : actionType === "publish" ? (
                  <Globe className="w-5 h-5" />
                ) : (
                  <Lock className="w-5 h-5" />
                )}
              </div>
              <div>
                <h3 className="font-bold text-base text-foreground capitalize">
                  {actionType === "delete"
                    ? "Delete Exam"
                    : actionType === "publish"
                    ? "Publish Exam"
                    : "Unpublish Exam"}
                </h3>
                <p className="text-xs text-muted-foreground mt-0.5">Please confirm this action</p>
              </div>
            </div>

            <p className="text-sm text-foreground leading-relaxed">
              {actionType === "delete" ? (
                <>
                  Are you sure you want to permanently delete the exam{" "}
                  <strong className="text-foreground">"{actionExam.title}"</strong> created by{" "}
                  <strong>{actionExam.faculty?.name}</strong>? This will remove all associated questions and student
                  attempts. This action cannot be undone.
                </>
              ) : actionType === "publish" ? (
                <>
                  Are you sure you want to publish{" "}
                  <strong className="text-foreground">"{actionExam.title}"</strong>? Once published, students will be
                  able to see and attempt this exam according to schedule.
                </>
              ) : (
                <>
                  Are you sure you want to unpublish{" "}
                  <strong className="text-foreground">"{actionExam.title}"</strong> and return it to draft status?
                  Students will no longer be able to start new attempts.
                </>
              )}
            </p>

            <div className="flex items-center justify-end gap-3 pt-3 border-t border-border">
              <button
                type="button"
                onClick={() => {
                  setActionExam(null);
                  setActionType(null);
                }}
                disabled={isActionSubmitting}
                className="px-4 py-2 rounded-lg border border-border text-foreground hover:bg-muted text-xs font-medium transition-all"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={() => void handleConfirmAction()}
                disabled={isActionSubmitting}
                className={`px-4 py-2 rounded-lg text-white text-xs font-medium transition-all flex items-center gap-2 ${
                  actionType === "delete"
                    ? "bg-rose-600 hover:bg-rose-700"
                    : actionType === "publish"
                    ? "bg-emerald-600 hover:bg-emerald-700"
                    : "bg-amber-600 hover:bg-amber-700"
                }`}
              >
                {isActionSubmitting && <RefreshCw className="w-3.5 h-3.5 animate-spin" />}
                {actionType === "delete" ? "Delete Exam" : actionType === "publish" ? "Publish" : "Unpublish"}
              </button>
            </div>
          </div>
        </div>
      )}
    </DashboardLayout>
  );
}

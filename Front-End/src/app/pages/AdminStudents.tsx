import axios from "axios";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { DashboardLayout } from "../components/DashboardLayout";
import {
  Search,
  Filter,
  Plus,
  Edit,
  Trash2,
  Eye,
  Mail,
  Award,
  Download,
  TrendingUp,
  BarChart3,
  CheckCircle2,
  XCircle,
  Clock,
  AlertCircle,
  RefreshCw,
  X,
  ChevronLeft,
  ChevronRight,
  User,
  Users,
  GraduationCap,
} from "lucide-react";
import { toast } from "sonner";
import { Combobox } from "../components/ui/combobox";
import {
  adminStudentsApi,
  departmentsApi,
  type DepartmentOption,
  type AdminStudentCreatePayload,
  type AdminStudentDetails,
  type AdminStudentRow,
  type AdminStudentResultsResponse,
} from "../../services/api";
import { authStorage } from "../../services/auth";

function extractApiErrorMessage(apiError: unknown): string | null {
  if (!apiError || typeof apiError !== "object") {
    return null;
  }
  const record = apiError as Record<string, unknown>;
  if (typeof record.detail === "string") {
    return record.detail;
  }
  if (typeof record.message === "string") {
    return record.message;
  }
  const firstFieldError = Object.values(record).find((value) => {
    if (typeof value === "string") {
      return true;
    }
    return Array.isArray(value) && typeof value[0] === "string";
  });
  if (typeof firstFieldError === "string") {
    return firstFieldError;
  }
  if (Array.isArray(firstFieldError) && typeof firstFieldError[0] === "string") {
    return firstFieldError[0];
  }
  return null;
}

function getPerformanceBadge(status?: string, average?: number | null) {
  if (average === null || average === undefined || status === "N/A") {
    return {
      label: "N/A",
      bg: "bg-slate-100 text-slate-700 border-slate-200",
      barColor: "bg-slate-300",
    };
  }
  if (average >= 80) {
    return {
      label: "Excellent",
      bg: "bg-emerald-50 text-emerald-700 border-emerald-200",
      barColor: "bg-emerald-500",
    };
  }
  if (average >= 65) {
    return {
      label: "Good",
      bg: "bg-blue-50 text-blue-700 border-blue-200",
      barColor: "bg-blue-500",
    };
  }
  if (average >= 50) {
    return {
      label: "Average",
      bg: "bg-amber-50 text-amber-700 border-amber-200",
      barColor: "bg-amber-500",
    };
  }
  return {
    label: "Needs Improvement",
    bg: "bg-rose-50 text-rose-700 border-rose-200",
    barColor: "bg-rose-500",
  };
}

export function AdminStudents() {
  const navigate = useNavigate();

  // Search & Filters
  const [searchTerm, setSearchTerm] = useState("");
  const [departmentFilter, setDepartmentFilter] = useState("all");
  const [scoreRangeFilter, setScoreRangeFilter] = useState("all");
  const [sortBy, setSortBy] = useState("default");

  // Pagination
  const [page, setPage] = useState(1);
  const [pageSize] = useState(10);
  const [totalPages, setTotalPages] = useState(1);
  const [totalCount, setTotalCount] = useState(0);

  // Data
  const [students, setStudents] = useState<AdminStudentRow[]>([]);
  const [departments, setDepartments] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // Stats from backend
  const [stats, setStats] = useState({
    total_students: 0,
    overall_average_score: null as number | null,
    top_performer: null as {
      id: number;
      name: string;
      email: string;
      roll_number: string;
      percentage: number;
    } | null,
    students_below_pass: 0,
  });

  // Profile View Modal
  const [isViewOpen, setIsViewOpen] = useState(false);
  const [viewLoading, setViewLoading] = useState(false);
  const [selectedStudent, setSelectedStudent] = useState<AdminStudentDetails | null>(null);
  const [viewError, setViewError] = useState("");

  // Results & Score Breakdown Modal
  const [isResultsOpen, setIsResultsOpen] = useState(false);
  const [resultsLoading, setResultsLoading] = useState(false);
  const [studentResults, setStudentResults] = useState<AdminStudentResultsResponse["data"] | null>(null);

  // Edit Modal
  const [editStudentDetails, setEditStudentDetails] = useState<AdminStudentDetails | null>(null);
  const [editDepartments, setEditDepartments] = useState<DepartmentOption[]>([]);
  const [isEditOpen, setIsEditOpen] = useState(false);
  const [editLoading, setEditLoading] = useState(false);
  const [savingEdit, setSavingEdit] = useState(false);
  const [editError, setEditError] = useState("");
  const [editSuccess, setEditSuccess] = useState("");
  const [editStudentId, setEditStudentId] = useState<number | null>(null);
  const [editForm, setEditForm] = useState({
    first_name: "",
    last_name: "",
    email: "",
    student_id: "",
    department_id: "",
  });

  // Delete
  const [deletingId, setDeletingId] = useState<number | null>(null);

  // Create Student Modal
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [creatingStudent, setCreatingStudent] = useState(false);
  const [createDepartmentsLoading, setCreateDepartmentsLoading] = useState(false);
  const [createDepartments, setCreateDepartments] = useState<DepartmentOption[]>([]);
  const [createError, setCreateError] = useState("");
  const [createSuccess, setCreateSuccess] = useState("");
  const [createForm, setCreateForm] = useState({
    first_name: "",
    last_name: "",
    email: "",
    department_id: "",
    password: "",
    confirm_password: "",
  });

  const handleUnauthorized = useCallback(() => {
    authStorage.clearSession();
    navigate("/login", { replace: true });
  }, [navigate]);

  const fetchStudents = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const params: {
        search?: string;
        department?: string;
        score_range?: string;
        sort?: string;
        page?: number;
        page_size?: number;
      } = {
        page,
        page_size: pageSize,
      };

      const trimmedSearch = searchTerm.trim();
      if (trimmedSearch) params.search = trimmedSearch;
      if (departmentFilter !== "all") params.department = departmentFilter;
      if (scoreRangeFilter !== "all") params.score_range = scoreRangeFilter;
      if (sortBy !== "default") params.sort = sortBy;

      const response = await adminStudentsApi.getStudents(params);
      setStudents(response.data);

      if (response.pagination) {
        setTotalPages(response.pagination.total_pages);
        setTotalCount(response.pagination.total_count);
      } else {
        setTotalPages(1);
        setTotalCount(response.data.length);
      }

      if (response.stats) {
        setStats(response.stats);
      }
      if (response.departments) {
        setDepartments(response.departments);
      }
    } catch (requestError) {
      if (axios.isAxiosError(requestError)) {
        if (requestError.response?.status === 401) {
          handleUnauthorized();
          return;
        }
        const extracted = extractApiErrorMessage(requestError.response?.data);
        setError(extracted ?? "Unable to fetch students. Please try again.");
      } else {
        setError("Unable to fetch students. Please try again.");
      }
    } finally {
      setLoading(false);
    }
  }, [departmentFilter, scoreRangeFilter, sortBy, page, pageSize, handleUnauthorized, searchTerm]);

  const fetchDepartments = useCallback(async () => {
    try {
      const response = await departmentsApi.getDepartments();
      const names = response.data
        .map((department) => department.department_name)
        .filter((departmentName) => Boolean(departmentName?.trim()));
      setDepartments(Array.from(new Set(names)).sort((a, b) => a.localeCompare(b)));
    } catch {
      setDepartments([]);
    }
  }, []);

  const fetchEditDepartments = useCallback(async () => {
    try {
      const response = await departmentsApi.getDepartments();
      const departmentsList = (response.data || [])
        .slice()
        .sort((left, right) => left.department_name.localeCompare(right.department_name));
      setEditDepartments(departmentsList);
    } catch {
      setEditDepartments([]);
    }
  }, []);

  useEffect(() => {
    void fetchDepartments();
  }, [fetchDepartments]);

  useEffect(() => {
    const debounceTimer = setTimeout(() => {
      void fetchStudents();
    }, 300);

    return () => {
      clearTimeout(debounceTimer);
    };
  }, [fetchStudents]);

  useEffect(() => {
    if (!isEditOpen) return;
    void fetchEditDepartments();
  }, [fetchEditDepartments, isEditOpen]);

  useEffect(() => {
    if (!isEditOpen || !editStudentDetails || editDepartments.length === 0) return;
    const currentDepartmentId = editDepartments.find(
      (department) => department.department_name === editStudentDetails.department
    )?.id;

    setEditForm((prev) => ({
      ...prev,
      department_id: currentDepartmentId ? String(currentDepartmentId) : "",
    }));
  }, [editDepartments, editStudentDetails, isEditOpen]);

  const handleViewStudent = async (studentId: number) => {
    setIsViewOpen(true);
    setViewLoading(true);
    setViewError("");
    setSelectedStudent(null);
    try {
      const response = await adminStudentsApi.getStudentById(studentId);
      setSelectedStudent(response.data);
    } catch (requestError) {
      if (axios.isAxiosError(requestError)) {
        if (requestError.response?.status === 401) {
          handleUnauthorized();
          return;
        }
        const extracted = extractApiErrorMessage(requestError.response?.data);
        setViewError(extracted ?? "Unable to fetch student details.");
      } else {
        setViewError("Unable to fetch student details.");
      }
    } finally {
      setViewLoading(false);
    }
  };

  const handleOpenResults = async (studentId: number) => {
    setIsResultsOpen(true);
    setResultsLoading(true);
    setStudentResults(null);
    try {
      const response = await adminStudentsApi.getStudentResults(studentId);
      if (response.status === "success") {
        setStudentResults(response.data);
      } else {
        toast.error("Unable to load student results.");
      }
    } catch {
      toast.error("Failed to fetch student results.");
    } finally {
      setResultsLoading(false);
    }
  };

  const handleEditStudent = async (studentId: number) => {
    setIsEditOpen(true);
    setEditLoading(true);
    setEditError("");
    setEditSuccess("");
    setEditStudentId(studentId);
    setEditStudentDetails(null);
    try {
      const response = await adminStudentsApi.getStudentById(studentId);
      setEditStudentDetails(response.data);
      setEditForm({
        first_name: response.data.first_name,
        last_name: response.data.last_name,
        email: response.data.email,
        student_id: response.data.roll_number,
        department_id: "",
      });
    } catch (requestError) {
      if (axios.isAxiosError(requestError)) {
        if (requestError.response?.status === 401) {
          handleUnauthorized();
          return;
        }
        const extracted = extractApiErrorMessage(requestError.response?.data);
        setEditError(extracted ?? "Unable to load student.");
      } else {
        setEditError("Unable to load student.");
      }
    } finally {
      setEditLoading(false);
    }
  };

  const handleSaveEdit = async () => {
    if (!editStudentId) return;
    setEditError("");
    setEditSuccess("");

    const departmentId = Number(editForm.department_id);
    if (!editForm.first_name || !editForm.last_name || !editForm.email) {
      setEditError("All fields are required.");
      return;
    }

    if (!Number.isFinite(departmentId) || departmentId <= 0) {
      setEditError("Please select a valid department.");
      return;
    }

    setSavingEdit(true);
    try {
      await adminStudentsApi.updateStudent(editStudentId, {
        first_name: editForm.first_name.trim(),
        last_name: editForm.last_name.trim(),
        email: editForm.email.trim(),
        student_id: editForm.student_id.trim(),
        department_id: departmentId,
      });

      setEditSuccess("Student Updated Successfully");
      await Promise.all([fetchStudents(), fetchDepartments()]);
      setTimeout(() => {
        setIsEditOpen(false);
      }, 700);
    } catch (requestError) {
      if (axios.isAxiosError(requestError)) {
        if (requestError.response?.status === 401) {
          handleUnauthorized();
          return;
        }
        const extracted = extractApiErrorMessage(requestError.response?.data);
        setEditError(extracted ?? "Unable to update student.");
      } else {
        setEditError("Unable to update student.");
      }
    } finally {
      setSavingEdit(false);
    }
  };

  const handleDeleteStudent = async (student: AdminStudentRow) => {
    const confirmed = window.confirm(`Are you sure you want to delete student "${student.full_name}"?`);
    if (!confirmed) return;

    setDeletingId(student.id);
    try {
      await adminStudentsApi.deleteStudent(student.id);
      await Promise.all([fetchStudents(), fetchDepartments()]);
      toast.success(`Student "${student.full_name}" deleted.`);
    } catch (requestError) {
      if (axios.isAxiosError(requestError)) {
        if (requestError.response?.status === 401) {
          handleUnauthorized();
          return;
        }
        const extracted = extractApiErrorMessage(requestError.response?.data);
        setError(extracted ?? "Unable to delete student.");
      } else {
        setError("Unable to delete student.");
      }
    } finally {
      setDeletingId(null);
    }
  };

  const resetCreateForm = () => {
    setCreateForm({
      first_name: "",
      last_name: "",
      email: "",
      department_id: "",
      password: "",
      confirm_password: "",
    });
    setCreateError("");
    setCreateSuccess("");
  };

  const fetchCreateDepartments = async () => {
    setCreateDepartmentsLoading(true);
    setCreateError("");
    try {
      const response = await departmentsApi.getDepartments();
      setCreateDepartments(response.data || []);
    } catch (requestError) {
      if (axios.isAxiosError(requestError)) {
        if (requestError.response?.status === 401) {
          handleUnauthorized();
          return;
        }
        const extracted = extractApiErrorMessage(requestError.response?.data);
        setCreateError(extracted ?? "Unable to fetch departments.");
      } else {
        setCreateError("Unable to fetch departments.");
      }
      setCreateDepartments([]);
    } finally {
      setCreateDepartmentsLoading(false);
    }
  };

  const handleCreateStudent = async () => {
    setCreateError("");
    setCreateSuccess("");

    const departmentId = Number(createForm.department_id);
    const payload: AdminStudentCreatePayload = {
      first_name: createForm.first_name.trim(),
      last_name: createForm.last_name.trim(),
      email: createForm.email.trim(),
      department_id: departmentId,
      password: createForm.password,
    };

    if (
      !payload.first_name ||
      !payload.last_name ||
      !payload.email ||
      !createForm.department_id ||
      !payload.password ||
      !createForm.confirm_password
    ) {
      setCreateError("All fields are required.");
      return;
    }

    if (!Number.isFinite(departmentId) || departmentId <= 0) {
      setCreateError("Please select a valid department.");
      return;
    }

    if (payload.password.length < 8) {
      setCreateError("Password must be at least 8 characters long.");
      return;
    }

    const hasLetter = /[A-Za-z]/.test(payload.password);
    const hasNumber = /\d/.test(payload.password);
    if (!hasLetter || !hasNumber) {
      setCreateError("Password must include at least one letter and one number.");
      return;
    }

    if (payload.password !== createForm.confirm_password) {
      setCreateError("Confirm Password must match Password.");
      return;
    }

    setCreatingStudent(true);
    try {
      await adminStudentsApi.createStudent(payload);
      setCreateSuccess("Student Created Successfully");
      await Promise.all([fetchStudents(), fetchDepartments()]);
      setTimeout(() => {
        setIsCreateOpen(false);
        resetCreateForm();
      }, 700);
    } catch (requestError) {
      if (axios.isAxiosError(requestError)) {
        if (requestError.response?.status === 401) {
          handleUnauthorized();
          return;
        }
        const extracted = extractApiErrorMessage(requestError.response?.data);
        setCreateError(extracted ?? "Unable to create student.");
      } else {
        setCreateError("Unable to create student.");
      }
    } finally {
      setCreatingStudent(false);
    }
  };

  // Export CSV Handler
  const handleExportCSV = () => {
    if (!students.length) {
      toast.error("No students to export.");
      return;
    }
    const headers = [
      "Roll Number",
      "Full Name",
      "Email",
      "Department",
      "Exams Attempted",
      "Average Score (%)",
      "Highest Score (%)",
      "Lowest Score (%)",
      "Performance Status",
      "Last Exam Date",
    ];

    const rows = students.map((s) => [
      `"${s.roll_number || ""}"`,
      `"${s.full_name || ""}"`,
      `"${s.email || ""}"`,
      `"${s.department || ""}"`,
      s.number_of_exams || 0,
      typeof s.average_score === "number" ? s.average_score : "N/A",
      typeof s.highest_score === "number" ? s.highest_score : "N/A",
      typeof s.lowest_score === "number" ? s.lowest_score : "N/A",
      `"${s.performance_status || "N/A"}"`,
      `"${s.last_exam_date || ""}"`,
    ]);

    const csvContent = "data:text/csv;charset=utf-8," + [headers.join(","), ...rows.map((r) => r.join(","))].join("\n");
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", `student_performance_report_${new Date().toISOString().split("T")[0]}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    toast.success("Student performance report exported to CSV.");
  };

  return (
    <DashboardLayout userRole="Admin">
      <div className="space-y-6">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="text-2xl sm:text-3xl font-bold text-foreground mb-1">Student Performance</h1>
            <p className="text-xs sm:text-sm text-muted-foreground">
              Monitor student enrollments, exam participation, and academic performance metrics
            </p>
          </div>
          <div className="flex items-center gap-2.5">
            <button
              onClick={handleExportCSV}
              className="px-3.5 py-2 rounded-lg border border-border bg-card hover:bg-muted/50 text-foreground font-medium text-sm transition-all flex items-center gap-2"
              title="Export filtered student report as CSV"
            >
              <Download className="w-4 h-4 text-muted-foreground" />
              Export CSV
            </button>
            <button
              className="px-4 py-2 rounded-lg bg-gradient-to-r from-primary to-secondary text-white hover:opacity-90 shadow-md font-medium text-sm transition-all flex items-center gap-2"
              onClick={() => {
                setIsCreateOpen(true);
                setCreateError("");
                setCreateSuccess("");
                void fetchCreateDepartments();
              }}
            >
              <Plus className="w-4 h-4" />
              Add Student
            </button>
          </div>
        </div>

        {/* Stats Strip */}
        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="bg-card rounded-xl p-5 shadow-sm border border-border hover:shadow-md transition-all">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs sm:text-sm text-muted-foreground mb-1">Total Students</p>
                <p className="text-2xl sm:text-3xl font-bold text-foreground">{stats.total_students}</p>
              </div>
              <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center text-primary">
                <Users className="w-5 h-5" />
              </div>
            </div>
          </div>

          <div className="bg-card rounded-xl p-5 shadow-sm border border-border hover:shadow-md transition-all">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs sm:text-sm text-muted-foreground mb-1">Overall Avg Score</p>
                <p className="text-2xl sm:text-3xl font-bold text-blue-600">
                  {typeof stats.overall_average_score === "number" ? `${stats.overall_average_score}%` : "N/A"}
                </p>
              </div>
              <div className="w-10 h-10 rounded-lg bg-blue-50 flex items-center justify-center text-blue-600">
                <TrendingUp className="w-5 h-5" />
              </div>
            </div>
          </div>

          <div className="bg-card rounded-xl p-5 shadow-sm border border-border hover:shadow-md transition-all">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs sm:text-sm text-muted-foreground mb-1">Top Performer</p>
                <p className="text-base sm:text-lg font-bold text-emerald-600 truncate max-w-[150px]">
                  {stats.top_performer ? `${stats.top_performer.name}` : "N/A"}
                </p>
                {stats.top_performer && (
                  <p className="text-xs font-semibold text-emerald-700">{stats.top_performer.percentage}% Avg</p>
                )}
              </div>
              <div className="w-10 h-10 rounded-lg bg-emerald-50 flex items-center justify-center text-emerald-600">
                <Award className="w-5 h-5" />
              </div>
            </div>
          </div>

          <div className="bg-card rounded-xl p-5 shadow-sm border border-border hover:shadow-md transition-all">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs sm:text-sm text-muted-foreground mb-1">Below Pass Mark (&lt;40%)</p>
                <p className="text-2xl sm:text-3xl font-bold text-rose-600">{stats.students_below_pass}</p>
              </div>
              <div className="w-10 h-10 rounded-lg bg-rose-50 flex items-center justify-center text-rose-600">
                <AlertCircle className="w-5 h-5" />
              </div>
            </div>
          </div>
        </div>

        {/* Search and Filters Card */}
        <div className="bg-card rounded-xl p-4 sm:p-5 shadow-sm border border-border space-y-3">
          <div className="flex flex-col sm:flex-row gap-3">
            <div className="flex-1 relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
              <input
                type="text"
                placeholder="Search by name, email, or roll number..."
                value={searchTerm}
                onChange={(e) => {
                  setSearchTerm(e.target.value);
                  setPage(1);
                }}
                className="w-full pl-9 pr-3.5 py-2 rounded-lg bg-input-background border border-border text-sm focus:outline-none focus:ring-2 focus:ring-primary transition-all text-foreground"
              />
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <Filter className="w-4 h-4 text-muted-foreground" />
              {/* Department Filter */}
              <select
                value={departmentFilter}
                onChange={(e) => {
                  setDepartmentFilter(e.target.value);
                  setPage(1);
                }}
                className="px-3 py-2 rounded-lg bg-input-background border border-border text-xs sm:text-sm focus:outline-none focus:ring-2 focus:ring-primary transition-all text-foreground"
              >
                <option value="all">All Departments</option>
                {departments.map((dept) => (
                  <option key={dept} value={dept}>
                    {dept}
                  </option>
                ))}
              </select>

              {/* Score Range Filter */}
              <select
                value={scoreRangeFilter}
                onChange={(e) => {
                  setScoreRangeFilter(e.target.value);
                  setPage(1);
                }}
                className="px-3 py-2 rounded-lg bg-input-background border border-border text-xs sm:text-sm focus:outline-none focus:ring-2 focus:ring-primary transition-all text-foreground"
              >
                <option value="all">All Score Ranges</option>
                <option value="excellent">Excellent (&ge;80%)</option>
                <option value="good">Good (65-79%)</option>
                <option value="average">Average (50-64%)</option>
                <option value="needs_improvement">Needs Improvement (&lt;50%)</option>
                <option value="no_exams">No Exams Taken</option>
              </select>

              {/* Sort By */}
              <select
                value={sortBy}
                onChange={(e) => {
                  setSortBy(e.target.value);
                  setPage(1);
                }}
                className="px-3 py-2 rounded-lg bg-input-background border border-border text-xs sm:text-sm focus:outline-none focus:ring-2 focus:ring-primary transition-all text-foreground"
              >
                <option value="default">Sort: Default</option>
                <option value="average_desc">Avg Score: High to Low</option>
                <option value="average_asc">Avg Score: Low to High</option>
                <option value="exams_desc">Most Exams Attempted</option>
                <option value="name_asc">Name: A to Z</option>
                <option value="name_desc">Name: Z to A</option>
                <option value="last_exam_desc">Latest Exam Attempted</option>
              </select>
            </div>
          </div>
          {error && <p className="text-xs sm:text-sm text-destructive">{error}</p>}
        </div>

        {/* Students Table */}
        <div className="bg-card rounded-xl shadow-sm border border-border overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead className="bg-muted/50 border-b border-border text-xs uppercase font-semibold text-muted-foreground tracking-wider">
                <tr>
                  <th className="px-5 py-3.5">Student</th>
                  <th className="px-5 py-3.5">Roll No</th>
                  <th className="px-5 py-3.5">Department</th>
                  <th className="px-5 py-3.5 text-center">Exams Attempted</th>
                  <th className="px-5 py-3.5">Avg Score (%)</th>
                  <th className="px-5 py-3.5 text-center">Highest / Lowest</th>
                  <th className="px-5 py-3.5">Performance Status</th>
                  <th className="px-5 py-3.5 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border text-sm">
                {loading ? (
                  <tr>
                    <td colSpan={8} className="px-6 py-12 text-center text-muted-foreground">
                      <div className="flex items-center justify-center gap-2">
                        <RefreshCw className="w-4 h-4 animate-spin text-primary" />
                        Loading student performance data...
                      </div>
                    </td>
                  </tr>
                ) : students.length === 0 ? (
                  <tr>
                    <td colSpan={8} className="px-6 py-12 text-center text-muted-foreground">
                      <GraduationCap className="w-12 h-12 mx-auto mb-2 text-muted-foreground/40" />
                      <p className="font-medium text-foreground">No Students Found</p>
                      <p className="text-xs text-muted-foreground mt-1">Try adjusting your search query or filters.</p>
                    </td>
                  </tr>
                ) : (
                  students.map((student) => {
                    const badge = getPerformanceBadge(student.performance_status, student.average_score);
                    return (
                      <tr key={student.id} className="hover:bg-muted/30 transition-colors">
                        {/* Student Name & Email */}
                        <td className="px-5 py-4">
                          <div className="flex items-center gap-2.5">
                            <div className="w-8 h-8 rounded-full bg-primary/10 text-primary flex items-center justify-center font-bold text-xs shrink-0">
                              {student.full_name?.charAt(0) || "S"}
                            </div>
                            <div>
                              <p className="font-medium text-foreground">{student.full_name}</p>
                              <p className="text-xs text-muted-foreground">{student.email}</p>
                            </div>
                          </div>
                        </td>

                        {/* Roll No */}
                        <td className="px-5 py-4 text-xs font-mono text-foreground whitespace-nowrap">
                          {student.roll_number || "-"}
                        </td>

                        {/* Department */}
                        <td className="px-5 py-4 text-xs text-foreground">
                          {student.department || "-"}
                        </td>

                        {/* Exams Attempted */}
                        <td className="px-5 py-4 text-xs text-center font-semibold text-foreground">
                          <span className="inline-block px-2.5 py-0.5 rounded bg-muted/60 text-xs">
                            {student.number_of_exams}
                          </span>
                        </td>

                        {/* Average Score */}
                        <td className="px-5 py-4 whitespace-nowrap">
                          {typeof student.average_score === "number" ? (
                            <div className="space-y-1 w-28">
                              <div className="flex justify-between items-center text-xs">
                                <span className="font-bold text-foreground">{student.average_score.toFixed(1)}%</span>
                              </div>
                              <div className="w-full bg-muted rounded-full h-1.5 overflow-hidden">
                                <div
                                  className={`h-1.5 rounded-full ${badge.barColor}`}
                                  style={{ width: `${Math.min(100, Math.max(0, student.average_score))}%` }}
                                />
                              </div>
                            </div>
                          ) : (
                            <span className="text-xs text-muted-foreground italic">N/A</span>
                          )}
                        </td>

                        {/* Highest / Lowest */}
                        <td className="px-5 py-4 text-xs text-center whitespace-nowrap">
                          {typeof student.highest_score === "number" ? (
                            <span className="text-foreground">
                              <span className="text-emerald-600 font-semibold">{student.highest_score}%</span>
                              <span className="text-muted-foreground mx-1">/</span>
                              <span className="text-rose-600 font-semibold">{student.lowest_score}%</span>
                            </span>
                          ) : (
                            <span className="text-muted-foreground">-</span>
                          )}
                        </td>

                        {/* Status Badge */}
                        <td className="px-5 py-4 whitespace-nowrap">
                          <span
                            className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border ${badge.bg}`}
                          >
                            {badge.label}
                          </span>
                        </td>

                        {/* Actions */}
                        <td className="px-5 py-4 text-right whitespace-nowrap">
                          <div className="inline-flex items-center gap-1.5">
                            {/* View Results Button */}
                            <button
                              className="p-1.5 rounded-md hover:bg-primary/10 text-primary transition-colors"
                              title="View Exam Results & Breakdown"
                              onClick={() => void handleOpenResults(student.id)}
                            >
                              <BarChart3 className="w-4 h-4" />
                            </button>

                            {/* View Profile */}
                            <button
                              className="p-1.5 rounded-md hover:bg-muted text-muted-foreground transition-colors"
                              title="View Student Profile"
                              onClick={() => void handleViewStudent(student.id)}
                            >
                              <Eye className="w-4 h-4" />
                            </button>

                            {/* Edit */}
                            <button
                              className="p-1.5 rounded-md hover:bg-muted text-muted-foreground transition-colors"
                              title="Edit Student"
                              onClick={() => void handleEditStudent(student.id)}
                            >
                              <Edit className="w-4 h-4" />
                            </button>

                            {/* Email */}
                            <a
                              className="p-1.5 rounded-md hover:bg-muted text-muted-foreground transition-colors"
                              title="Send Email"
                              href={`mailto:${student.email}`}
                            >
                              <Mail className="w-4 h-4" />
                            </a>

                            {/* Delete */}
                            <button
                              className="p-1.5 rounded-md hover:bg-rose-50 text-rose-600 transition-colors disabled:opacity-50"
                              title="Delete Student"
                              onClick={() => void handleDeleteStudent(student)}
                              disabled={deletingId === student.id}
                            >
                              <Trash2 className="w-4 h-4" />
                            </button>
                          </div>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          {!loading && totalPages > 1 && (
            <div className="flex flex-col sm:flex-row items-center justify-between px-5 py-3.5 border-t border-border bg-muted/20 text-xs text-muted-foreground gap-3">
              <div>
                Showing page <span className="font-semibold text-foreground">{page}</span> of{" "}
                <span className="font-semibold text-foreground">{totalPages}</span> ({totalCount} total students)
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

      {/* STUDENT RESULTS & EXAM BREAKDOWN MODAL */}
      {isResultsOpen && (
        <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm flex items-center justify-center p-3 sm:p-5 overflow-y-auto">
          <div className="bg-card w-full max-w-4xl rounded-2xl shadow-xl border border-border overflow-hidden my-auto max-h-[90vh] flex flex-col">
            {/* Header */}
            <div className="flex items-center justify-between p-5 border-b border-border bg-muted/20">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center text-primary font-bold">
                  <BarChart3 className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="font-bold text-lg text-foreground">
                    {studentResults?.student?.full_name || "Student Results"}
                  </h3>
                  <p className="text-xs text-muted-foreground">
                    Roll No: {studentResults?.student?.roll_number || "N/A"} · Department:{" "}
                    {studentResults?.student?.department || "General"}
                  </p>
                </div>
              </div>
              <button
                onClick={() => setIsResultsOpen(false)}
                className="p-1.5 rounded-lg text-muted-foreground hover:bg-muted hover:text-foreground transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Content */}
            <div className="p-5 overflow-y-auto flex-1 space-y-6">
              {resultsLoading ? (
                <div className="py-16 text-center text-muted-foreground flex flex-col items-center justify-center gap-3">
                  <RefreshCw className="w-8 h-8 animate-spin text-primary" />
                  <p className="text-sm">Fetching student exam history and score calculations...</p>
                </div>
              ) : !studentResults ? (
                <div className="py-12 text-center text-muted-foreground">
                  <AlertCircle className="w-10 h-10 mx-auto mb-2 text-rose-500" />
                  <p>Unable to load student results.</p>
                </div>
              ) : (
                <>
                  {/* Results Summary Strip */}
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 bg-muted/30 p-4 rounded-xl border border-border text-xs">
                    <div>
                      <span className="text-muted-foreground block mb-0.5">Exams Attempted</span>
                      <span className="font-bold text-foreground text-base">
                        {studentResults.summary.total_attempts}
                      </span>
                    </div>
                    <div>
                      <span className="text-muted-foreground block mb-0.5">Overall Average</span>
                      <span className="font-bold text-blue-600 text-base">
                        {typeof studentResults.summary.overall_average === "number"
                          ? `${studentResults.summary.overall_average}%`
                          : "N/A"}
                      </span>
                    </div>
                    <div>
                      <span className="text-muted-foreground block mb-0.5">Highest Score</span>
                      <span className="font-bold text-emerald-600 text-base">
                        {typeof studentResults.summary.highest_score === "number"
                          ? `${studentResults.summary.highest_score}%`
                          : "N/A"}
                      </span>
                    </div>
                    <div>
                      <span className="text-muted-foreground block mb-0.5">Lowest Score</span>
                      <span className="font-bold text-rose-600 text-base">
                        {typeof studentResults.summary.lowest_score === "number"
                          ? `${studentResults.summary.lowest_score}%`
                          : "N/A"}
                      </span>
                    </div>
                  </div>

                  {/* Chronological Score Trend Cards */}
                  {studentResults.trend && studentResults.trend.length > 0 && (
                    <div className="space-y-2">
                      <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                        Score Progression Over Time
                      </h4>
                      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-2 pt-1">
                        {studentResults.trend.map((t, idx) => (
                          <div
                            key={idx}
                            className="p-2.5 rounded-lg border border-border bg-card text-center space-y-1 hover:border-primary/40 transition-all"
                          >
                            <p className="text-[10px] text-muted-foreground truncate">{t.date}</p>
                            <p
                              className={`text-sm font-bold ${
                                t.percentage >= 65
                                  ? "text-emerald-600"
                                  : t.percentage >= 40
                                  ? "text-amber-600"
                                  : "text-rose-600"
                              }`}
                            >
                              {t.percentage}%
                            </p>
                            <p className="text-[10px] text-muted-foreground truncate" title={t.exam_title}>
                              {t.exam_title}
                            </p>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Per-Exam Breakdown Table */}
                  <div className="space-y-3">
                    <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                      Per-Exam Score Breakdown
                    </h4>

                    {studentResults.results.length === 0 ? (
                      <div className="p-8 text-center border border-dashed border-border rounded-xl text-muted-foreground text-xs">
                        This student has not attempted any exams yet.
                      </div>
                    ) : (
                      <div className="overflow-x-auto rounded-xl border border-border">
                        <table className="w-full text-left text-xs border-collapse">
                          <thead className="bg-muted/50 border-b border-border uppercase font-semibold text-muted-foreground">
                            <tr>
                              <th className="px-4 py-3">Exam Title & Subject</th>
                              <th className="px-4 py-3">Faculty</th>
                              <th className="px-4 py-3">Date</th>
                              <th className="px-4 py-3 text-center">Marks</th>
                              <th className="px-4 py-3 text-center">Score (%)</th>
                              <th className="px-4 py-3 text-center">Result</th>
                              <th className="px-4 py-3 text-center">Status</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-border">
                            {studentResults.results.map((res) => (
                              <tr key={res.attempt_id} className="hover:bg-muted/20">
                                <td className="px-4 py-3">
                                  <p className="font-semibold text-foreground">{res.exam_title}</p>
                                  <p className="text-[11px] text-muted-foreground">{res.subject}</p>
                                </td>
                                <td className="px-4 py-3 text-muted-foreground">{res.faculty_name}</td>
                                <td className="px-4 py-3 text-muted-foreground whitespace-nowrap">
                                  {res.date
                                    ? new Date(res.date).toLocaleDateString("en-US", {
                                        month: "short",
                                        day: "numeric",
                                        year: "numeric",
                                      })
                                    : "-"}
                                </td>
                                <td className="px-4 py-3 text-center font-semibold text-foreground whitespace-nowrap">
                                  {res.marks_obtained} / {res.total_marks}
                                </td>
                                <td className="px-4 py-3 text-center font-bold whitespace-nowrap">
                                  <span
                                    className={
                                      res.percentage >= 65
                                        ? "text-emerald-600"
                                        : res.percentage >= 40
                                        ? "text-amber-600"
                                        : "text-rose-600"
                                    }
                                  >
                                    {res.percentage}%
                                  </span>
                                </td>
                                <td className="px-4 py-3 text-center whitespace-nowrap">
                                  {res.is_passed ? (
                                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
                                      <CheckCircle2 className="w-3 h-3 text-emerald-600" /> Pass
                                    </span>
                                  ) : (
                                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-rose-50 text-rose-700 border border-rose-200">
                                      <XCircle className="w-3 h-3 text-rose-600" /> Fail
                                    </span>
                                  )}
                                </td>
                                <td className="px-4 py-3 text-center capitalize text-muted-foreground whitespace-nowrap">
                                  <span className="inline-block px-2 py-0.5 rounded bg-muted/60 text-[10px] font-medium">
                                    {res.status}
                                  </span>
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
            </div>

            {/* Footer */}
            <div className="p-4 border-t border-border bg-muted/20 flex justify-end">
              <button
                onClick={() => setIsResultsOpen(false)}
                className="px-4 py-2 rounded-lg border border-border bg-card hover:bg-muted text-foreground font-medium text-xs transition-all"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* STUDENT PROFILE VIEW MODAL */}
      {isViewOpen && (
        <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4">
          <div className="w-full max-w-2xl bg-card rounded-xl shadow-xl border border-border">
            <div className="flex items-center justify-between p-6 border-b border-border">
              <h3 className="text-xl font-semibold text-foreground">Student Details</h3>
              <button
                className="px-3 py-1.5 rounded border border-border hover:bg-muted text-foreground text-xs"
                onClick={() => setIsViewOpen(false)}
              >
                Close
              </button>
            </div>
            <div className="p-6">
              {viewLoading ? (
                <p className="text-center text-muted-foreground">Loading details...</p>
              ) : viewError ? (
                <p className="text-center text-destructive">{viewError}</p>
              ) : selectedStudent ? (
                <div className="space-y-4">
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <p className="text-xs text-muted-foreground">First Name</p>
                      <p className="font-medium text-foreground">{selectedStudent.first_name}</p>
                    </div>
                    <div>
                      <p className="text-xs text-muted-foreground">Last Name</p>
                      <p className="font-medium text-foreground">{selectedStudent.last_name}</p>
                    </div>
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground">Email</p>
                    <p className="font-medium text-foreground">{selectedStudent.email}</p>
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <p className="text-xs text-muted-foreground">Roll Number</p>
                      <p className="font-medium text-foreground">{selectedStudent.roll_number || "-"}</p>
                    </div>
                    <div>
                      <p className="text-xs text-muted-foreground">Department</p>
                      <p className="font-medium text-foreground">{selectedStudent.department || "-"}</p>
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <p className="text-xs text-muted-foreground">Number of Exams</p>
                      <p className="font-medium text-foreground">{selectedStudent.number_of_exams}</p>
                    </div>
                    <div>
                      <p className="text-xs text-muted-foreground">Average Score</p>
                      <p className="font-medium text-foreground">
                        {typeof selectedStudent.average_score === "number"
                          ? `${selectedStudent.average_score.toFixed(1)}%`
                          : "N/A"}
                      </p>
                    </div>
                  </div>
                </div>
              ) : null}
            </div>
          </div>
        </div>
      )}

      {/* EDIT STUDENT MODAL */}
      {isEditOpen && (
        <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4">
          <div className="w-full max-w-2xl bg-card rounded-xl shadow-xl border border-border">
            <div className="flex items-center justify-between p-6 border-b border-border">
              <h3 className="text-xl font-semibold text-foreground">Edit Student</h3>
              <button
                className="px-3 py-1.5 rounded border border-border hover:bg-muted text-foreground text-xs"
                onClick={() => setIsEditOpen(false)}
              >
                Close
              </button>
            </div>
            <div className="p-6">
              {editLoading ? (
                <p className="text-center text-muted-foreground">Loading student...</p>
              ) : (
                <div className="space-y-4">
                  {editError && <p className="text-sm text-destructive">{editError}</p>}
                  {editSuccess && <p className="text-sm text-green-600 font-semibold">{editSuccess}</p>}
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-xs font-medium text-muted-foreground mb-1">First Name</label>
                      <input
                        type="text"
                        className="w-full px-3 py-2 border border-border rounded-lg bg-input-background text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary"
                        value={editForm.first_name}
                        onChange={(e) => setEditForm((prev) => ({ ...prev, first_name: e.target.value }))}
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-muted-foreground mb-1">Last Name</label>
                      <input
                        type="text"
                        className="w-full px-3 py-2 border border-border rounded-lg bg-input-background text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary"
                        value={editForm.last_name}
                        onChange={(e) => setEditForm((prev) => ({ ...prev, last_name: e.target.value }))}
                      />
                    </div>
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-muted-foreground mb-1">Email</label>
                    <input
                      type="email"
                      className="w-full px-3 py-2 border border-border rounded-lg bg-input-background text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary"
                      value={editForm.email}
                      onChange={(e) => setEditForm((prev) => ({ ...prev, email: e.target.value }))}
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-muted-foreground mb-1">Roll Number</label>
                    <input
                      type="text"
                      className="w-full px-3 py-2 border border-border rounded-lg bg-input-background text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary"
                      value={editForm.student_id}
                      onChange={(e) => setEditForm((prev) => ({ ...prev, student_id: e.target.value }))}
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-muted-foreground mb-1">Department</label>
                    <Combobox
                      options={editDepartments.map((dept) => ({
                        value: String(dept.id),
                        label: dept.department_name,
                      }))}
                      value={editForm.department_id}
                      onValueChange={(val) => setEditForm((prev) => ({ ...prev, department_id: val }))}
                      placeholder="Select department..."
                    />
                  </div>
                  <div className="flex justify-end gap-3 pt-4 border-t border-border">
                    <button
                      className="px-4 py-2 rounded-lg border border-border hover:bg-muted text-foreground text-sm font-medium"
                      onClick={() => setIsEditOpen(false)}
                      disabled={savingEdit}
                    >
                      Cancel
                    </button>
                    <button
                      className="px-4 py-2 rounded-lg bg-primary text-white text-sm font-medium hover:opacity-90 disabled:opacity-60"
                      onClick={() => void handleSaveEdit()}
                      disabled={savingEdit}
                    >
                      {savingEdit ? "Saving..." : "Save Changes"}
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* CREATE STUDENT MODAL */}
      {isCreateOpen && (
        <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4">
          <div className="w-full max-w-2xl bg-card rounded-xl shadow-xl border border-border">
            <div className="flex items-center justify-between p-6 border-b border-border">
              <h3 className="text-xl font-semibold text-foreground">Add New Student</h3>
              <button
                className="px-3 py-1.5 rounded border border-border hover:bg-muted text-foreground text-xs"
                onClick={() => setIsCreateOpen(false)}
              >
                Close
              </button>
            </div>
            <div className="p-6">
              <div className="space-y-4">
                {createError && <p className="text-sm text-destructive">{createError}</p>}
                {createSuccess && <p className="text-sm text-green-600 font-semibold">{createSuccess}</p>}
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-medium text-muted-foreground mb-1">First Name</label>
                    <input
                      type="text"
                      className="w-full px-3 py-2 border border-border rounded-lg bg-input-background text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary"
                      value={createForm.first_name}
                      onChange={(e) => setCreateForm((prev) => ({ ...prev, first_name: e.target.value }))}
                      placeholder="Enter first name"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-muted-foreground mb-1">Last Name</label>
                    <input
                      type="text"
                      className="w-full px-3 py-2 border border-border rounded-lg bg-input-background text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary"
                      value={createForm.last_name}
                      onChange={(e) => setCreateForm((prev) => ({ ...prev, last_name: e.target.value }))}
                      placeholder="Enter last name"
                    />
                  </div>
                </div>
                <div>
                  <label className="block text-xs font-medium text-muted-foreground mb-1">Email</label>
                  <input
                    type="email"
                    className="w-full px-3 py-2 border border-border rounded-lg bg-input-background text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary"
                    value={createForm.email}
                    onChange={(e) => setCreateForm((prev) => ({ ...prev, email: e.target.value }))}
                    placeholder="Enter student email"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-muted-foreground mb-1">Department</label>
                  {createDepartmentsLoading ? (
                    <p className="text-xs text-muted-foreground">Loading departments...</p>
                  ) : (
                    <Combobox
                      options={createDepartments.map((dept) => ({
                        value: String(dept.id),
                        label: dept.department_name,
                      }))}
                      value={createForm.department_id}
                      onValueChange={(val) => setCreateForm((prev) => ({ ...prev, department_id: val }))}
                      placeholder="Select department..."
                    />
                  )}
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-medium text-muted-foreground mb-1">Password</label>
                    <input
                      type="password"
                      className="w-full px-3 py-2 border border-border rounded-lg bg-input-background text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary"
                      value={createForm.password}
                      onChange={(e) => setCreateForm((prev) => ({ ...prev, password: e.target.value }))}
                      placeholder="At least 8 chars"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-muted-foreground mb-1">Confirm Password</label>
                    <input
                      type="password"
                      className="w-full px-3 py-2 border border-border rounded-lg bg-input-background text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary"
                      value={createForm.confirm_password}
                      onChange={(e) => setCreateForm((prev) => ({ ...prev, confirm_password: e.target.value }))}
                      placeholder="Repeat password"
                    />
                  </div>
                </div>
                <div className="flex justify-end gap-3 pt-4 border-t border-border">
                  <button
                    className="px-4 py-2 rounded-lg border border-border hover:bg-muted text-foreground text-sm font-medium"
                    onClick={() => setIsCreateOpen(false)}
                    disabled={creatingStudent}
                  >
                    Cancel
                  </button>
                  <button
                    className="px-4 py-2 rounded-lg bg-primary text-white text-sm font-medium hover:opacity-90 disabled:opacity-60"
                    onClick={() => void handleCreateStudent()}
                    disabled={creatingStudent}
                  >
                    {creatingStudent ? "Creating..." : "Create Student"}
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </DashboardLayout>
  );
}

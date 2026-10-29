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
  MoreHorizontal,
  Building2,
  KeyRound,
  Copy,
  Check,
} from "lucide-react";
import { toast } from "sonner";
import { Combobox } from "../components/ui/combobox";
import {
  Sheet,
  SheetContent,
  SheetClose,
} from "../components/ui/sheet";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "../components/ui/tabs";
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
} from "../components/ui/dropdown-menu";
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
      tooltip: "No exam attempts",
      bg: "bg-slate-100 text-slate-700 border-slate-200",
      barColor: "bg-slate-300",
    };
  }
  if (average >= 80) {
    return {
      label: "Excellent",
      tooltip: "Excellent (≥80%)",
      bg: "bg-emerald-50 text-emerald-700 border-emerald-200",
      barColor: "bg-emerald-500",
    };
  }
  if (average >= 65) {
    return {
      label: "Good",
      tooltip: "Good (65-79%)",
      bg: "bg-blue-50 text-blue-700 border-blue-200",
      barColor: "bg-blue-500",
    };
  }
  if (average >= 50) {
    return {
      label: "Average",
      tooltip: "Average (50-64%)",
      bg: "bg-amber-50 text-amber-700 border-amber-200",
      barColor: "bg-amber-500",
    };
  }
  return {
    label: "Needs Work",
    tooltip: "Needs Improvement (<50%)",
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

  // Profile View Drawer
  const [isViewOpen, setIsViewOpen] = useState(false);
  const [viewLoading, setViewLoading] = useState(false);
  const [selectedStudent, setSelectedStudent] = useState<AdminStudentDetails | null>(null);
  const [viewError, setViewError] = useState("");
  const [drawerResults, setDrawerResults] = useState<any[] | null>(null);
  const [loadingDrawerResults, setLoadingDrawerResults] = useState(false);
  const [copiedField, setCopiedField] = useState<string | null>(null);

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

  const [changeDeptModal, setChangeDeptModal] = useState<{
    open: boolean;
    student: AdminStudentRow | null;
    department: string;
    reason: string;
    loading: boolean;
    error: string;
  }>({
    open: false,
    student: null,
    department: "",
    reason: "",
    loading: false,
    error: "",
  });

  const [resetPasswordModal, setResetPasswordModal] = useState<{
    open: boolean;
    student: AdminStudentRow | null;
    newPassword: string;
    reason: string;
    loading: boolean;
    error: string;
    temporaryPasswordResult: string | null;
    copied: boolean;
  }>({
    open: false,
    student: null,
    newPassword: "",
    reason: "",
    loading: false,
    error: "",
    temporaryPasswordResult: null,
    copied: false,
  });

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
      const studentRows = Array.isArray(response?.data)
        ? response.data
        : Array.isArray(response?.results)
        ? response.results
        : [];
      setStudents(studentRows);

      if (response.pagination) {
        setTotalPages(response.pagination.total_pages);
        setTotalCount(response.pagination.total_count);
      } else {
        setTotalPages(1);
        setTotalCount(studentRows.length);
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
    setDrawerResults(null);
    setLoadingDrawerResults(true);

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

    try {
      const resResults = await adminStudentsApi.getStudentResults(studentId);
      if (resResults.status === "success" && resResults.data?.attempts) {
        setDrawerResults(resResults.data.attempts);
      } else {
        setDrawerResults([]);
      }
    } catch {
      setDrawerResults([]);
    } finally {
      setLoadingDrawerResults(false);
    }
  };

  const handleCopyText = (text: string, fieldName: string) => {
    navigator.clipboard.writeText(text);
    setCopiedField(fieldName);
    toast.success(`Copied ${fieldName} to clipboard!`);
    setTimeout(() => setCopiedField(null), 2000);
  };

  const getStudentInitials = (name: string): string => {
    const parts = name.trim().split(/\s+/);
    if (parts.length >= 2) {
      return `${parts[0][0]}${parts[1][0]}`.toUpperCase();
    }
    return name.slice(0, 2).toUpperCase() || "ST";
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

  // Change Department Handlers
  const handleOpenChangeDept = (studentItem: AdminStudentRow) => {
    setChangeDeptModal({
      open: true,
      student: studentItem,
      department: studentItem.department || "",
      reason: "",
      loading: false,
      error: "",
    });
  };

  const handleSubmitChangeDept = async () => {
    if (!changeDeptModal.student) return;
    const targetUserId = changeDeptModal.student.user_id || changeDeptModal.student.id;
    if (!changeDeptModal.department.trim()) {
      setChangeDeptModal((prev) => ({ ...prev, error: "Please select a department." }));
      return;
    }
    if (!changeDeptModal.reason.trim()) {
      setChangeDeptModal((prev) => ({ ...prev, error: "A reason is required for administrative audit logs." }));
      return;
    }

    setChangeDeptModal((prev) => ({ ...prev, loading: true, error: "" }));
    try {
      await adminStudentsApi.changeDepartment(targetUserId, {
        department: changeDeptModal.department.trim(),
        reason: changeDeptModal.reason.trim(),
      });
      toast.success(`Department updated to ${changeDeptModal.department}.`);
      setChangeDeptModal((prev) => ({ ...prev, open: false, loading: false }));
      await fetchStudents();
    } catch (err: any) {
      const msg = err.response?.data?.message || err.response?.data?.detail || "Failed to change department.";
      setChangeDeptModal((prev) => ({ ...prev, error: msg, loading: false }));
    }
  };

  // Reset Password Handlers
  const handleOpenResetPassword = (studentItem: AdminStudentRow) => {
    setResetPasswordModal({
      open: true,
      student: studentItem,
      newPassword: "",
      reason: "",
      loading: false,
      error: "",
      temporaryPasswordResult: null,
      copied: false,
    });
  };

  const handleGeneratePassword = () => {
    const chars = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789!@#$%";
    let pwd = "";
    for (let i = 0; i < 12; i++) {
      pwd += chars.charAt(Math.floor(Math.random() * chars.length));
    }
    setResetPasswordModal((prev) => ({ ...prev, newPassword: pwd }));
  };

  const handleSubmitResetPassword = async () => {
    if (!resetPasswordModal.student) return;
    setResetPasswordModal((prev) => ({ ...prev, loading: true, error: "" }));
    try {
      const res = await adminStudentsApi.resetPassword(resetPasswordModal.student.id, {
        new_password: resetPasswordModal.newPassword.trim() || undefined,
        reason: resetPasswordModal.reason.trim() || undefined,
      });
      const generated = res.data?.new_password || resetPasswordModal.newPassword;
      setResetPasswordModal((prev) => ({
        ...prev,
        loading: false,
        temporaryPasswordResult: generated,
      }));
      toast.success("Password reset successfully.");
    } catch (err: any) {
      const msg = err.response?.data?.message || err.response?.data?.detail || "Failed to reset password.";
      setResetPasswordModal((prev) => ({ ...prev, error: msg, loading: false }));
    }
  };

  const handleCopyPassword = () => {
    if (resetPasswordModal.temporaryPasswordResult) {
      navigator.clipboard.writeText(resetPasswordModal.temporaryPasswordResult);
      setResetPasswordModal((prev) => ({ ...prev, copied: true }));
      toast.success("Password copied to clipboard.");
      setTimeout(() => {
        setResetPasswordModal((prev) => ({ ...prev, copied: false }));
      }, 2000);
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
      <div className="space-y-6 max-w-full min-w-0">
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

        {/* Students Table & Mobile Cards */}
        <div className="bg-card rounded-xl shadow-sm border border-border overflow-hidden w-full">
          {/* Desktop & Tablet Table (>= 768px) */}
          <div className="hidden md:block w-full">
            <table className="w-full text-left border-collapse table-fixed">
              <thead className="bg-muted/50 border-b border-border text-xs uppercase font-semibold text-muted-foreground tracking-wider">
                <tr>
                  <th className="px-3 py-3 w-[28%] xl:w-[24%]">Student</th>
                  <th className="px-3 py-3 w-[14%] xl:w-[11%]">Roll No</th>
                  <th className="px-3 py-3 hidden xl:table-cell xl:w-[12%]">Department</th>
                  <th className="px-3 py-3 text-center w-[10%] xl:w-[7%]">Exams</th>
                  <th className="px-3 py-3 w-[16%] xl:w-[13%]">Avg Score</th>
                  <th className="px-3 py-3 text-center hidden xl:table-cell xl:w-[9%]">High / Low</th>
                  <th className="px-3 py-3 w-[14%] xl:w-[10%]">Status</th>
                  <th className="px-3 py-3 text-right w-[18%] xl:w-[14%]">Actions</th>
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
                        <td className="px-3 py-3 min-w-0">
                          <div className="flex items-center gap-2.5 min-w-0">
                            <div className="w-8 h-8 rounded-full bg-primary/10 text-primary flex items-center justify-center font-bold text-xs shrink-0">
                              {student.full_name?.charAt(0) || "S"}
                            </div>
                            <div className="min-w-0 flex-1">
                              <p className="font-medium text-foreground text-xs sm:text-sm truncate" title={student.full_name}>
                                {student.full_name}
                              </p>
                              <p className="text-xs text-muted-foreground truncate" title={student.email}>
                                {student.email}
                              </p>
                            </div>
                          </div>
                        </td>

                        {/* Roll No */}
                        <td className="px-3 py-3 text-xs font-mono text-foreground truncate" title={student.roll_number || "-"}>
                          {student.roll_number || "-"}
                        </td>

                        {/* Department */}
                        <td className="px-3 py-3 text-xs text-foreground truncate hidden xl:table-cell" title={student.department || "-"}>
                          {student.department || "-"}
                        </td>

                        {/* Exams Attempted */}
                        <td className="px-3 py-3 text-xs text-center font-semibold text-foreground">
                          <span className="inline-block px-2 py-0.5 rounded bg-muted/60 text-xs font-semibold">
                            {student.number_of_exams}
                          </span>
                        </td>

                        {/* Average Score */}
                        <td className="px-3 py-3 min-w-0">
                          {typeof student.average_score === "number" ? (
                            <div className="space-y-1 max-w-[95px]">
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
                        <td className="px-3 py-3 text-xs text-center truncate hidden xl:table-cell">
                          {typeof student.highest_score === "number" ? (
                            <span className="text-foreground">
                              <span className="text-emerald-600 font-semibold">{student.highest_score}%</span>
                              <span className="text-muted-foreground mx-0.5">/</span>
                              <span className="text-rose-600 font-semibold">{student.lowest_score}%</span>
                            </span>
                          ) : (
                            <span className="text-muted-foreground">-</span>
                          )}
                        </td>

                        {/* Status Badge */}
                        <td className="px-3 py-3 min-w-0">
                          <span
                            className={`inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold border whitespace-nowrap ${badge.bg}`}
                            title={badge.tooltip || badge.label}
                          >
                            {badge.label}
                          </span>
                        </td>

                        {/* Actions Column (Clean hybrid pattern) */}
                        <td className="px-3 py-3 text-right whitespace-nowrap">
                          <div className="flex items-center justify-end gap-1.5 min-w-0">
                            {/* Primary View Details Button */}
                            <button
                              type="button"
                              className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border border-border bg-card hover:bg-muted text-xs font-semibold text-foreground shadow-2xs hover:shadow-xs transition-all shrink-0 cursor-pointer"
                              aria-label={`View ${student.full_name}`}
                              onClick={() => void handleViewStudent(student.id)}
                            >
                              <Eye className="w-3.5 h-3.5 text-muted-foreground" />
                              <span>View</span>
                            </button>

                            {/* Single More Actions Dropdown */}
                            <DropdownMenu>
                              <DropdownMenuTrigger asChild>
                                <button
                                  type="button"
                                  className="p-1.5 rounded-lg border border-transparent hover:border-border hover:bg-muted text-muted-foreground hover:text-foreground transition-all shrink-0 cursor-pointer"
                                  aria-label={`More actions for ${student.full_name}`}
                                >
                                  <MoreHorizontal className="w-4 h-4" />
                                </button>
                              </DropdownMenuTrigger>
                              <DropdownMenuContent align="end" className="w-52 z-50 p-1.5">
                                <DropdownMenuItem
                                  onClick={() => void handleOpenResults(student.id)}
                                  className="cursor-pointer text-xs"
                                >
                                  <BarChart3 className="w-3.5 h-3.5 mr-2 text-primary" />
                                  <span>Exam Results & Breakdown</span>
                                </DropdownMenuItem>
                                <DropdownMenuItem
                                  onClick={() => void handleEditStudent(student.id)}
                                  className="cursor-pointer text-xs"
                                >
                                  <Edit className="w-3.5 h-3.5 mr-2 text-muted-foreground" />
                                  <span>Edit Details</span>
                                </DropdownMenuItem>
                                <DropdownMenuItem
                                  onClick={() => {
                                    window.location.href = `mailto:${student.email}`;
                                  }}
                                  className="cursor-pointer text-xs"
                                >
                                  <Mail className="w-3.5 h-3.5 mr-2 text-muted-foreground" />
                                  <span>Email Student</span>
                                </DropdownMenuItem>
                                <DropdownMenuSeparator />
                                <DropdownMenuItem
                                  onClick={() => handleOpenChangeDept(student)}
                                  className="cursor-pointer text-xs"
                                >
                                  <Building2 className="w-3.5 h-3.5 mr-2 text-muted-foreground" />
                                  <span>Change Department</span>
                                </DropdownMenuItem>
                                <DropdownMenuItem
                                  onClick={() => handleOpenResetPassword(student)}
                                  className="cursor-pointer text-xs"
                                >
                                  <KeyRound className="w-3.5 h-3.5 mr-2 text-muted-foreground" />
                                  <span>Reset Password</span>
                                </DropdownMenuItem>
                                <DropdownMenuSeparator />
                                <DropdownMenuItem
                                  onClick={() => void handleDeleteStudent(student)}
                                  disabled={deletingId === student.id}
                                  className="cursor-pointer text-xs text-destructive focus:text-destructive focus:bg-destructive/10"
                                >
                                  <Trash2 className="w-3.5 h-3.5 mr-2" />
                                  <span>Delete Student</span>
                                </DropdownMenuItem>
                              </DropdownMenuContent>
                            </DropdownMenu>
                          </div>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>

          {/* Mobile Stacked Cards (< 768px) */}
          <div className="block md:hidden">
            {loading ? (
              <div className="p-8 text-center text-muted-foreground flex items-center justify-center gap-2">
                <RefreshCw className="w-4 h-4 animate-spin text-primary" />
                Loading students...
              </div>
            ) : students.length === 0 ? (
              <div className="p-8 text-center text-muted-foreground">
                <GraduationCap className="w-10 h-10 mx-auto mb-2 text-muted-foreground/40" />
                <p className="font-medium text-foreground">No Students Found</p>
                <p className="text-xs text-muted-foreground mt-1">Try adjusting search or filters.</p>
              </div>
            ) : (
              <div className="divide-y divide-border">
                {students.map((student) => {
                  const badge = getPerformanceBadge(student.performance_status, student.average_score);
                  return (
                    <div key={student.id} className="p-4 space-y-3">
                      <div className="flex items-start justify-between gap-3 min-w-0">
                        <div className="flex items-center gap-2.5 min-w-0 flex-1">
                          <div className="w-9 h-9 rounded-full bg-primary/10 text-primary flex items-center justify-center font-bold text-xs shrink-0">
                            {student.full_name?.charAt(0) || "S"}
                          </div>
                          <div className="min-w-0 flex-1">
                            <p className="font-semibold text-foreground text-sm truncate" title={student.full_name}>
                              {student.full_name}
                            </p>
                            <p className="text-xs text-muted-foreground truncate" title={student.email}>
                              {student.email}
                            </p>
                          </div>
                        </div>
                        <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border shrink-0 ${badge.bg}`}>
                          {badge.label}
                        </span>
                      </div>

                      <div className="grid grid-cols-2 gap-2 bg-muted/30 p-2.5 rounded-lg text-xs">
                        <div>
                          <span className="text-muted-foreground block text-[10px] uppercase font-semibold">Roll No</span>
                          <span className="font-mono text-foreground font-medium">{student.roll_number || "-"}</span>
                        </div>
                        <div>
                          <span className="text-muted-foreground block text-[10px] uppercase font-semibold">Department</span>
                          <span className="text-foreground truncate block font-medium" title={student.department || "-"}>
                            {student.department || "-"}
                          </span>
                        </div>
                        <div>
                          <span className="text-muted-foreground block text-[10px] uppercase font-semibold">Exams</span>
                          <span className="text-foreground font-medium">{student.number_of_exams} attempted</span>
                        </div>
                        <div>
                          <span className="text-muted-foreground block text-[10px] uppercase font-semibold">Avg Score</span>
                          <div className="flex items-center gap-1.5 mt-0.5">
                            <span className="font-bold text-foreground">
                              {typeof student.average_score === "number" ? `${student.average_score.toFixed(1)}%` : "N/A"}
                            </span>
                            {typeof student.average_score === "number" && (
                              <div className="w-12 bg-muted rounded-full h-1.5 overflow-hidden">
                                <div
                                  className={`h-1.5 rounded-full ${badge.barColor}`}
                                  style={{ width: `${Math.min(100, Math.max(0, student.average_score))}%` }}
                                />
                              </div>
                            )}
                          </div>
                        </div>
                      </div>

                      <div className="flex items-center justify-between gap-2 pt-2 border-t border-border/40">
                        <button
                          type="button"
                          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-border bg-card hover:bg-muted text-xs font-semibold text-foreground shadow-2xs cursor-pointer"
                          onClick={() => void handleViewStudent(student.id)}
                          aria-label={`View details for ${student.full_name}`}
                        >
                          <Eye className="w-3.5 h-3.5 text-muted-foreground" />
                          <span>View Profile</span>
                        </button>

                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <button
                              type="button"
                              className="p-1.5 rounded-lg border border-border bg-card hover:bg-muted text-muted-foreground text-xs flex items-center gap-1 cursor-pointer"
                              aria-label={`More actions for ${student.full_name}`}
                            >
                              <MoreHorizontal className="w-4 h-4" />
                              <span className="text-xs">Actions</span>
                            </button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end" className="w-52 z-50 p-1.5">
                            <DropdownMenuItem
                              onClick={() => void handleOpenResults(student.id)}
                              className="cursor-pointer text-xs"
                            >
                              <BarChart3 className="w-3.5 h-3.5 mr-2 text-primary" />
                              <span>Exam Results</span>
                            </DropdownMenuItem>
                            <DropdownMenuItem
                              onClick={() => void handleEditStudent(student.id)}
                              className="cursor-pointer text-xs"
                            >
                              <Edit className="w-3.5 h-3.5 mr-2 text-muted-foreground" />
                              <span>Edit Details</span>
                            </DropdownMenuItem>
                            <DropdownMenuItem
                              onClick={() => {
                                window.location.href = `mailto:${student.email}`;
                              }}
                              className="cursor-pointer text-xs"
                            >
                              <Mail className="w-3.5 h-3.5 mr-2 text-muted-foreground" />
                              <span>Email Student</span>
                            </DropdownMenuItem>
                            <DropdownMenuSeparator />
                            <DropdownMenuItem
                              onClick={() => handleOpenChangeDept(student)}
                              className="cursor-pointer text-xs"
                            >
                              <Building2 className="w-3.5 h-3.5 mr-2 text-muted-foreground" />
                              <span>Change Department</span>
                            </DropdownMenuItem>
                            <DropdownMenuItem
                              onClick={() => handleOpenResetPassword(student)}
                              className="cursor-pointer text-xs"
                            >
                              <KeyRound className="w-3.5 h-3.5 mr-2 text-muted-foreground" />
                              <span>Reset Password</span>
                            </DropdownMenuItem>
                            <DropdownMenuSeparator />
                            <DropdownMenuItem
                              onClick={() => void handleDeleteStudent(student)}
                              disabled={deletingId === student.id}
                              className="cursor-pointer text-xs text-destructive focus:text-destructive focus:bg-destructive/10"
                            >
                              <Trash2 className="w-3.5 h-3.5 mr-2" />
                              <span>Delete Student</span>
                            </DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
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

      {/* ================= STUDENT DETAILS DRAWER ================= */}
      <Sheet open={isViewOpen} onOpenChange={setIsViewOpen}>
        <SheetContent
          side="right"
          className="w-full sm:max-w-lg md:max-w-xl lg:max-w-2xl p-0 flex flex-col h-full bg-card border-l border-border shadow-2xl overflow-hidden focus:outline-none"
        >
          {viewLoading ? (
            <div className="flex-1 flex flex-col items-center justify-center p-8 text-center text-muted-foreground">
              <RefreshCw className="w-8 h-8 animate-spin text-primary mb-3" />
              <p className="text-sm font-medium">Loading student profile & performance record...</p>
            </div>
          ) : viewError ? (
            <div className="flex-1 flex flex-col items-center justify-center p-8 text-center">
              <AlertCircle className="w-10 h-10 text-destructive mb-3" />
              <h4 className="text-base font-bold text-foreground mb-1">Failed to Load Profile</h4>
              <p className="text-xs text-muted-foreground max-w-sm mb-4">{viewError}</p>
              <button
                type="button"
                onClick={() => setIsViewOpen(false)}
                className="px-4 py-2 text-xs font-semibold rounded-lg border border-border hover:bg-muted"
              >
                Close Drawer
              </button>
            </div>
          ) : selectedStudent ? (
            <div className="flex flex-col h-full overflow-hidden">
              {/* Sticky Drawer Header */}
              <div className="p-5 sm:p-6 bg-gradient-to-br from-primary/10 via-background to-secondary/10 border-b border-border shrink-0">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex items-start gap-4 min-w-0">
                    <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-primary to-secondary text-white font-extrabold text-xl flex items-center justify-center shadow-md shrink-0">
                      {getStudentInitials(selectedStudent.full_name)}
                    </div>
                    <div className="min-w-0 space-y-1">
                      <div className="flex items-center gap-2 flex-wrap">
                        <h3 className="text-lg sm:text-xl font-bold text-foreground truncate">
                          {selectedStudent.full_name}
                        </h3>
                        <span className="px-2 py-0.5 rounded-full text-[11px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">
                          Student
                        </span>
                      </div>
                      <div className="flex items-center gap-2 flex-wrap text-xs text-muted-foreground">
                        <span className="font-mono bg-muted/60 px-2 py-0.5 rounded text-[11px] font-semibold text-foreground">
                          {selectedStudent.roll_number || "No Roll Number"}
                        </span>
                        <span>•</span>
                        <span className="font-medium text-foreground">{selectedStudent.department || "Unassigned"}</span>
                        {selectedStudent.year && (
                          <>
                            <span>•</span>
                            <span>Class of {selectedStudent.year}</span>
                          </>
                        )}
                      </div>
                    </div>
                  </div>
                  <SheetClose className="p-1.5 rounded-lg border border-border bg-background hover:bg-muted text-muted-foreground hover:text-foreground transition-colors shrink-0">
                    <X className="w-4 h-4" />
                    <span className="sr-only">Close</span>
                  </SheetClose>
                </div>
              </div>

              {/* Drawer Content with Tabs */}
              <div className="flex-1 overflow-y-auto p-5 sm:p-6 space-y-6 overflow-x-hidden">
                <Tabs defaultValue="overview" className="w-full space-y-5">
                  <TabsList className="grid grid-cols-2 w-full bg-muted/60 p-1 rounded-xl">
                    <TabsTrigger value="overview" className="text-xs font-bold py-2 rounded-lg data-[state=active]:bg-background data-[state=active]:text-foreground data-[state=active]:shadow-xs">
                      Overview & Performance
                    </TabsTrigger>
                    <TabsTrigger value="history" className="text-xs font-bold py-2 rounded-lg data-[state=active]:bg-background data-[state=active]:text-foreground data-[state=active]:shadow-xs">
                      Exam Attempts ({drawerResults ? drawerResults.length : selectedStudent.number_of_exams})
                    </TabsTrigger>
                  </TabsList>

                  {/* TAB 1: OVERVIEW & PERFORMANCE */}
                  <TabsContent value="overview" className="space-y-6 focus:outline-none">
                    {/* 4-Grid Key Performance Stat Cards */}
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                      <div className="bg-card rounded-xl p-3.5 border border-border shadow-xs">
                        <div className="text-[11px] font-medium text-muted-foreground flex items-center gap-1 mb-1">
                          <Award className="w-3.5 h-3.5 text-primary" />
                          Exams Taken
                        </div>
                        <div className="text-xl sm:text-2xl font-bold text-foreground">
                          {selectedStudent.number_of_exams}
                        </div>
                      </div>

                      <div className="bg-card rounded-xl p-3.5 border border-border shadow-xs">
                        <div className="text-[11px] font-medium text-muted-foreground flex items-center gap-1 mb-1">
                          <TrendingUp className="w-3.5 h-3.5 text-emerald-600" />
                          Avg Score
                        </div>
                        <div className="text-xl sm:text-2xl font-bold text-emerald-600">
                          {typeof selectedStudent.average_score === "number"
                            ? `${selectedStudent.average_score.toFixed(1)}%`
                            : "N/A"}
                        </div>
                      </div>

                      <div className="bg-card rounded-xl p-3.5 border border-border shadow-xs">
                        <div className="text-[11px] font-medium text-muted-foreground flex items-center gap-1 mb-1">
                          <CheckCircle2 className="w-3.5 h-3.5 text-blue-600" />
                          Highest
                        </div>
                        <div className="text-xl sm:text-2xl font-bold text-blue-600">
                          {typeof selectedStudent.highest_score === "number"
                            ? `${selectedStudent.highest_score.toFixed(1)}%`
                            : typeof selectedStudent.average_score === "number"
                            ? `${selectedStudent.average_score.toFixed(1)}%`
                            : "N/A"}
                        </div>
                      </div>

                      <div className="bg-card rounded-xl p-3.5 border border-border shadow-xs">
                        <div className="text-[11px] font-medium text-muted-foreground flex items-center gap-1 mb-1">
                          <BarChart3 className="w-3.5 h-3.5 text-amber-600" />
                          Performance
                        </div>
                        <div className="text-xs sm:text-sm font-bold text-foreground mt-1">
                          <span
                            className={`px-2 py-0.5 rounded text-[11px] font-bold ${
                              selectedStudent.performance_status === "Excellent"
                                ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                                : selectedStudent.performance_status === "Good"
                                ? "bg-blue-50 text-blue-700 border border-blue-200"
                                : selectedStudent.performance_status === "Needs Improvement"
                                ? "bg-amber-50 text-amber-700 border border-amber-200"
                                : "bg-muted text-muted-foreground border border-border"
                            }`}
                          >
                            {selectedStudent.performance_status ||
                              (typeof selectedStudent.average_score === "number"
                                ? selectedStudent.average_score >= 80
                                  ? "Excellent"
                                  : selectedStudent.average_score >= 60
                                  ? "Good"
                                  : "Average"
                                : "No Activity")}
                          </span>
                        </div>
                      </div>
                    </div>

                    {/* Academic Profile Details Card */}
                    <div className="bg-card rounded-2xl border border-border p-4 sm:p-5 shadow-xs space-y-3.5">
                      <h4 className="text-xs font-bold uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
                        <User className="w-3.5 h-3.5" />
                        Academic & Contact Details
                      </h4>

                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
                        <div className="p-3 bg-muted/30 rounded-xl border border-border/60">
                          <span className="text-muted-foreground block text-[11px] mb-0.5">Email Address</span>
                          <div className="flex items-center justify-between gap-2">
                            <span className="font-semibold text-foreground truncate">{selectedStudent.email}</span>
                            <button
                              type="button"
                              onClick={() => handleCopyText(selectedStudent.email, "email")}
                              className="text-muted-foreground hover:text-foreground p-1 rounded"
                              title="Copy email"
                            >
                              {copiedField === "email" ? (
                                <Check className="w-3.5 h-3.5 text-emerald-600" />
                              ) : (
                                <Copy className="w-3.5 h-3.5" />
                              )}
                            </button>
                          </div>
                        </div>

                        <div className="p-3 bg-muted/30 rounded-xl border border-border/60">
                          <span className="text-muted-foreground block text-[11px] mb-0.5">Student / Roll ID</span>
                          <div className="flex items-center justify-between gap-2">
                            <span className="font-mono font-bold text-foreground">
                              {selectedStudent.roll_number || "N/A"}
                            </span>
                            {selectedStudent.roll_number && (
                              <button
                                type="button"
                                onClick={() => handleCopyText(selectedStudent.roll_number, "student ID")}
                                className="text-muted-foreground hover:text-foreground p-1 rounded"
                                title="Copy Roll ID"
                              >
                                {copiedField === "student ID" ? (
                                  <Check className="w-3.5 h-3.5 text-emerald-600" />
                                ) : (
                                  <Copy className="w-3.5 h-3.5" />
                                )}
                              </button>
                            )}
                          </div>
                        </div>

                        <div className="p-3 bg-muted/30 rounded-xl border border-border/60">
                          <span className="text-muted-foreground block text-[11px] mb-0.5">Assigned Department</span>
                          <span className="font-semibold text-foreground block">
                            {selectedStudent.department || "Unassigned"}
                          </span>
                        </div>

                        <div className="p-3 bg-muted/30 rounded-xl border border-border/60">
                          <span className="text-muted-foreground block text-[11px] mb-0.5">Institution Code</span>
                          <span className="font-semibold text-foreground block">
                            {selectedStudent.institution?.institution_code || "Default Institute"}
                          </span>
                        </div>
                      </div>

                      {selectedStudent.last_exam_date && (
                        <div className="text-[11px] text-muted-foreground flex items-center gap-1.5 pt-1">
                          <Clock className="w-3 h-3" />
                          Last Exam Activity:{" "}
                          <span className="font-medium text-foreground">
                            {new Date(selectedStudent.last_exam_date).toLocaleString("en-US", {
                              month: "short",
                              day: "numeric",
                              year: "numeric",
                              hour: "2-digit",
                              minute: "2-digit",
                            })}
                          </span>
                        </div>
                      )}
                    </div>

                    {/* Quick Admin Actions */}
                    <div className="space-y-2.5">
                      <h4 className="text-xs font-bold uppercase tracking-wider text-muted-foreground">
                        Administrative Quick Actions
                      </h4>
                      <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5">
                        <button
                          type="button"
                          onClick={() => {
                            setIsViewOpen(false);
                            handleOpenChangeDept({
                              id: selectedStudent.id,
                              user_id: selectedStudent.user_id || selectedStudent.id,
                              full_name: selectedStudent.full_name,
                              email: selectedStudent.email,
                              department: selectedStudent.department,
                              roll_number: selectedStudent.roll_number,
                              year: selectedStudent.year,
                              number_of_exams: selectedStudent.number_of_exams,
                              average_score: selectedStudent.average_score,
                              status: "Active",
                            } as AdminStudentRow);
                          }}
                          className="px-3.5 py-2.5 rounded-xl border border-border bg-card hover:bg-muted text-xs font-semibold text-foreground flex items-center justify-center gap-2 transition-colors shadow-2xs"
                        >
                          <Building2 className="w-3.5 h-3.5 text-primary" />
                          Transfer Dept
                        </button>

                        <button
                          type="button"
                          onClick={() => {
                            setIsViewOpen(false);
                            handleOpenResetPassword({
                              id: selectedStudent.id,
                              user_id: selectedStudent.user_id || selectedStudent.id,
                              full_name: selectedStudent.full_name,
                              email: selectedStudent.email,
                              department: selectedStudent.department,
                              roll_number: selectedStudent.roll_number,
                              year: selectedStudent.year,
                              number_of_exams: selectedStudent.number_of_exams,
                              average_score: selectedStudent.average_score,
                              status: "Active",
                            } as AdminStudentRow);
                          }}
                          className="px-3.5 py-2.5 rounded-xl border border-border bg-card hover:bg-muted text-xs font-semibold text-foreground flex items-center justify-center gap-2 transition-colors shadow-2xs"
                        >
                          <KeyRound className="w-3.5 h-3.5 text-amber-600" />
                          Reset Password
                        </button>

                        <button
                          type="button"
                          onClick={() => {
                            setIsViewOpen(false);
                            handleEditStudent(selectedStudent.id);
                          }}
                          className="px-3.5 py-2.5 rounded-xl border border-border bg-card hover:bg-muted text-xs font-semibold text-foreground flex items-center justify-center gap-2 transition-colors shadow-2xs"
                        >
                          <Edit className="w-3.5 h-3.5 text-slate-600" />
                          Edit Profile
                        </button>
                      </div>
                    </div>
                  </TabsContent>

                  {/* TAB 2: EXAM HISTORY & RESULTS */}
                  <TabsContent value="history" className="space-y-4 focus:outline-none">
                    {loadingDrawerResults ? (
                      <div className="p-8 text-center text-muted-foreground">
                        <RefreshCw className="w-6 h-6 animate-spin mx-auto mb-2 text-primary" />
                        <p className="text-xs">Fetching student exam attempts...</p>
                      </div>
                    ) : !drawerResults || drawerResults.length === 0 ? (
                      <div className="p-10 text-center bg-muted/20 border border-border rounded-2xl">
                        <GraduationCap className="w-10 h-10 mx-auto mb-2 text-muted-foreground/40" />
                        <p className="font-semibold text-foreground text-sm">No Exam Attempts Recorded</p>
                        <p className="text-xs text-muted-foreground max-w-xs mx-auto mt-1">
                          This student has not submitted any exam attempts in your institution yet.
                        </p>
                      </div>
                    ) : (
                      <div className="space-y-2.5">
                        {drawerResults.map((att: any, idx: number) => {
                          const pct =
                            typeof att.percentage === "number"
                              ? att.percentage
                              : typeof att.score === "number" && att.total_marks
                              ? (att.score / att.total_marks) * 100
                              : null;
                          return (
                            <div
                              key={att.id || idx}
                              className="p-3.5 rounded-xl border border-border bg-card hover:bg-muted/30 transition-all flex items-center justify-between gap-3 text-xs"
                            >
                              <div className="space-y-1 min-w-0 flex-1">
                                <h5 className="font-bold text-foreground truncate">
                                  {att.exam_title || att.exam?.title || "Exam"}
                                </h5>
                                <div className="flex items-center gap-2 text-[11px] text-muted-foreground">
                                  <span>
                                    {att.submitted_at || att.started_at
                                      ? new Date(att.submitted_at || att.started_at).toLocaleDateString("en-US", {
                                          month: "short",
                                          day: "numeric",
                                          year: "numeric",
                                        })
                                      : "Date N/A"}
                                  </span>
                                  {att.subject && (
                                    <>
                                      <span>•</span>
                                      <span className="truncate">{att.subject}</span>
                                    </>
                                  )}
                                </div>
                              </div>
                              <div className="text-right shrink-0 space-y-1">
                                <div className="font-bold text-foreground">
                                  {typeof att.score === "number" ? att.score : typeof att.total_score === "number" ? att.total_score : "-"} / {att.total_marks || att.exam?.total_marks || "-"}
                                </div>
                                {pct !== null && (
                                  <span
                                    className={`inline-block px-2 py-0.5 rounded text-[10px] font-extrabold ${
                                      pct >= 70
                                        ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                                        : pct >= 40
                                        ? "bg-amber-50 text-amber-700 border border-amber-200"
                                        : "bg-rose-50 text-rose-700 border border-rose-200"
                                    }`}
                                  >
                                    {pct.toFixed(1)}%
                                  </span>
                                )}
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </TabsContent>
                </Tabs>
              </div>

              {/* Drawer Footer */}
              <div className="p-4 bg-muted/20 border-t border-border flex items-center justify-between shrink-0">
                <button
                  type="button"
                  onClick={() => handleOpenResults(selectedStudent.id)}
                  className="text-xs font-semibold text-primary hover:text-primary/80 flex items-center gap-1.5"
                >
                  <BarChart3 className="w-3.5 h-3.5" />
                  View Detailed Score Breakdown
                </button>
                <SheetClose className="px-4 py-2 rounded-lg border border-border bg-background hover:bg-muted text-xs font-semibold text-foreground transition-colors">
                  Close
                </SheetClose>
              </div>
            </div>
          ) : null}
        </SheetContent>
      </Sheet>

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

      {/* Change Department Modal */}
      {changeDeptModal.open && changeDeptModal.student && (
        <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4">
          <div className="w-full max-w-lg bg-white rounded-2xl shadow-2xl border border-border overflow-hidden">
            <div className="flex items-center justify-between p-5 border-b border-border bg-muted/20">
              <div className="flex items-center gap-2.5">
                <div className="p-2 rounded-xl bg-primary/10 text-primary">
                  <Building2 className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-base font-bold text-foreground">Change Department</h3>
                  <p className="text-xs text-muted-foreground">Admin scope reassignment with audit log</p>
                </div>
              </div>
              <button
                className="p-1.5 rounded-lg border border-border hover:bg-muted text-muted-foreground text-xs cursor-pointer"
                onClick={() => setChangeDeptModal((prev) => ({ ...prev, open: false }))}
              >
                Close
              </button>
            </div>

            <div className="p-5 space-y-4">
              <div className="rounded-xl bg-muted/30 p-3 border border-border/60 text-xs space-y-1">
                <p className="text-muted-foreground">
                  Student: <strong className="text-foreground">{changeDeptModal.student.full_name}</strong>
                </p>
                <p className="text-muted-foreground">
                  Email: <span className="font-mono text-foreground">{changeDeptModal.student.email}</span>
                </p>
                <p className="text-muted-foreground">
                  Current Department: <span className="font-semibold text-primary">{changeDeptModal.student.department || "Unassigned"}</span>
                </p>
              </div>

              <div>
                <label className="block text-xs font-semibold text-foreground mb-1.5">New Department *</label>
                <Combobox
                  value={changeDeptModal.department}
                  onValueChange={(val) => setChangeDeptModal((prev) => ({ ...prev, department: val }))}
                  placeholder="Select new department"
                  searchPlaceholder="Filter departments..."
                  emptyText="No departments found"
                  options={departments.map((dept) => ({
                    value: dept,
                    label: dept,
                  }))}
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-foreground mb-1.5">Reason for Department Transfer *</label>
                <textarea
                  rows={3}
                  value={changeDeptModal.reason}
                  onChange={(e) => setChangeDeptModal((prev) => ({ ...prev, reason: e.target.value }))}
                  placeholder="Provide justification for administrative audit trail..."
                  className="w-full px-3 py-2 text-xs rounded-xl border border-border focus:outline-none focus:ring-2 focus:ring-primary/20"
                />
                <p className="text-[11px] text-muted-foreground mt-1">This reason is permanently logged in the department transfer audit records.</p>
              </div>

              {changeDeptModal.error && (
                <p className="text-xs text-destructive font-medium">{changeDeptModal.error}</p>
              )}

              <div className="flex items-center justify-end gap-2 pt-2 border-t border-border">
                <button
                  type="button"
                  onClick={() => setChangeDeptModal((prev) => ({ ...prev, open: false }))}
                  className="px-4 py-2 rounded-xl border border-border text-xs font-semibold hover:bg-muted cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  disabled={changeDeptModal.loading}
                  onClick={handleSubmitChangeDept}
                  className="px-4 py-2 rounded-xl bg-primary text-primary-foreground text-xs font-bold hover:bg-primary/90 disabled:opacity-60 cursor-pointer"
                >
                  {changeDeptModal.loading ? "Transferring..." : "Confirm Transfer"}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Reset Password Modal */}
      {resetPasswordModal.open && resetPasswordModal.student && (
        <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4">
          <div className="w-full max-w-lg bg-white rounded-2xl shadow-2xl border border-border overflow-hidden">
            <div className="flex items-center justify-between p-5 border-b border-border bg-muted/20">
              <div className="flex items-center gap-2.5">
                <div className="p-2 rounded-xl bg-primary/10 text-primary">
                  <KeyRound className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-base font-bold text-foreground">Reset Password</h3>
                  <p className="text-xs text-muted-foreground">Admin credential update with audit log</p>
                </div>
              </div>
              <button
                className="p-1.5 rounded-lg border border-border hover:bg-muted text-muted-foreground text-xs cursor-pointer"
                onClick={() => setResetPasswordModal((prev) => ({ ...prev, open: false }))}
              >
                Close
              </button>
            </div>

            <div className="p-5 space-y-4">
              <div className="rounded-xl bg-muted/30 p-3 border border-border/60 text-xs space-y-1">
                <p className="text-muted-foreground">
                  Target: <strong className="text-foreground">{resetPasswordModal.student.full_name}</strong>
                </p>
                <p className="text-muted-foreground">
                  Email: <span className="font-mono text-foreground">{resetPasswordModal.student.email}</span>
                </p>
              </div>

              {!resetPasswordModal.temporaryPasswordResult ? (
                <>
                  <div>
                    <div className="flex items-center justify-between mb-1.5">
                      <label className="text-xs font-semibold text-foreground">New Password (Optional)</label>
                      <button
                        type="button"
                        onClick={handleGeneratePassword}
                        className="text-[11px] font-semibold text-primary hover:underline cursor-pointer"
                      >
                        Generate Random
                      </button>
                    </div>
                    <input
                      type="text"
                      value={resetPasswordModal.newPassword}
                      onChange={(e) => setResetPasswordModal((prev) => ({ ...prev, newPassword: e.target.value }))}
                      placeholder="Leave blank to auto-generate a secure password"
                      className="w-full px-3 py-2 text-xs font-mono rounded-xl border border-border focus:outline-none focus:ring-2 focus:ring-primary/20"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-foreground mb-1.5">Reason for Password Reset</label>
                    <input
                      type="text"
                      value={resetPasswordModal.reason}
                      onChange={(e) => setResetPasswordModal((prev) => ({ ...prev, reason: e.target.value }))}
                      placeholder="e.g. Student requested password assistance"
                      className="w-full px-3 py-2 text-xs rounded-xl border border-border focus:outline-none focus:ring-2 focus:ring-primary/20"
                    />
                  </div>

                  {resetPasswordModal.error && (
                    <p className="text-xs text-destructive font-medium">{resetPasswordModal.error}</p>
                  )}

                  <div className="flex items-center justify-end gap-2 pt-2 border-t border-border">
                    <button
                      type="button"
                      onClick={() => setResetPasswordModal((prev) => ({ ...prev, open: false }))}
                      className="px-4 py-2 rounded-xl border border-border text-xs font-semibold hover:bg-muted cursor-pointer"
                    >
                      Cancel
                    </button>
                    <button
                      type="button"
                      disabled={resetPasswordModal.loading}
                      onClick={handleSubmitResetPassword}
                      className="px-4 py-2 rounded-xl bg-primary text-primary-foreground text-xs font-bold hover:bg-primary/90 disabled:opacity-60 cursor-pointer"
                    >
                      {resetPasswordModal.loading ? "Resetting..." : "Reset Password"}
                    </button>
                  </div>
                </>
              ) : (
                <div className="space-y-4 py-2">
                  <div className="rounded-xl bg-emerald-50 border border-emerald-200 p-4 space-y-2">
                    <p className="text-xs font-bold text-emerald-900">
                      Password Reset Successfully!
                    </p>
                    <p className="text-xs text-emerald-800">
                      Please copy this temporary password and securely convey it to the student.
                    </p>
                    <div className="flex items-center gap-2 mt-2">
                      <code className="flex-1 bg-white px-3 py-2 rounded-lg border border-emerald-300 font-mono text-sm text-foreground font-bold select-all">
                        {resetPasswordModal.temporaryPasswordResult}
                      </code>
                      <button
                        type="button"
                        onClick={handleCopyPassword}
                        className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg bg-emerald-600 text-white text-xs font-bold hover:bg-emerald-700 transition-all shadow-xs cursor-pointer"
                      >
                        {resetPasswordModal.copied ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
                        {resetPasswordModal.copied ? "Copied!" : "Copy"}
                      </button>
                    </div>
                  </div>

                  <div className="flex justify-end pt-2 border-t border-border">
                    <button
                      type="button"
                      onClick={() => setResetPasswordModal((prev) => ({ ...prev, open: false }))}
                      className="px-5 py-2 rounded-xl bg-foreground text-background text-xs font-bold hover:opacity-90 cursor-pointer"
                    >
                      Done
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </DashboardLayout>
  );
}

import axios from "axios";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { DashboardLayout } from "../components/DashboardLayout";
import {
  Search,
  Filter,
  Eye,
  Edit,
  Mail,
  Trash2,
  ShieldCheck,
  Plus,
  ChevronLeft,
  ChevronRight,
  MoreHorizontal,
  Building2,
  KeyRound,
  UserCheck,
  UserX,
  Copy,
  Check,
  User,
  BookOpen,
  FileText,
  Database,
  Award,
  Clock,
  AlertCircle,
  RefreshCw,
  X,
} from "lucide-react";
import { toast } from "sonner";
import { Combobox } from "../components/ui/combobox";
import {
  Tooltip,
  TooltipTrigger,
  TooltipContent,
} from "../components/ui/tooltip";
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
  adminInstitutionApi,
  adminFacultyApi,
  departmentsApi,
  institutionsApi,
  type AdminFacultyCreatePayload,
  type AdminFacultyRow,
  type AdminFacultyUpdatePayload,
  type DepartmentOption,
  type InstitutionOption,
} from "../../services/api";
import { authStorage } from "../../services/auth";

type FacultyStatusFilter = "all" | "active" | "inactive";

type FacultyStats = {
  total_faculty: number;
  active_faculty: number;
  inactive_faculty: number;
  total_departments: number;
};

const ALLOWED_PAGE_SIZES = [10, 25, 50, 100];

function extractApiErrorMessage(apiError: unknown): string | null {
  if (!apiError || typeof apiError !== "object") return null;
  const record = apiError as Record<string, unknown>;
  if (typeof record.detail === "string") return record.detail;
  if (typeof record.message === "string") return record.message;
  const firstFieldError = Object.values(record).find((value) => {
    if (typeof value === "string") return true;
    return Array.isArray(value) && typeof value[0] === "string";
  });
  if (typeof firstFieldError === "string") return firstFieldError;
  if (Array.isArray(firstFieldError) && typeof firstFieldError[0] === "string") return firstFieldError[0];
  return null;
}

function getFacultyDisplayStatus(faculty: AdminFacultyRow) {
  if (typeof faculty.is_active === "boolean") {
    return faculty.is_active ? "Active" : "Inactive";
  }
  return faculty.status || "Inactive";
}

function isFacultyActive(faculty: AdminFacultyRow) {
  return getFacultyDisplayStatus(faculty).toLowerCase() === "active";
}

function buildNextFacultyEmployeeId(rows: AdminFacultyRow[]) {
  const year = new Date().getFullYear();
  const prefix = `FAC-${year}-`;

  const safeRows = Array.isArray(rows) ? rows : [];
  const nextSequence = safeRows
    .map((facultyItem) => facultyItem?.employee_id?.trim() ?? "")
    .filter((employeeId) => employeeId.startsWith(prefix))
    .map((employeeId) => Number(employeeId.split("-").at(-1)))
    .filter((sequence) => Number.isFinite(sequence) && sequence > 0)
    .reduce((highest, sequence) => Math.max(highest, sequence), 0) + 1;

  return `${prefix}${String(nextSequence).padStart(3, "0")}`;
}

function getPageNumbers(currentPage: number, total: number): (number | string)[] {
  if (total <= 7) {
    return Array.from({ length: total }, (_, i) => i + 1);
  }
  if (currentPage <= 4) {
    return [1, 2, 3, 4, 5, "...", total];
  }
  if (currentPage >= total - 3) {
    return [1, "...", total - 4, total - 3, total - 2, total - 1, total];
  }
  return [1, "...", currentPage - 1, currentPage, currentPage + 1, "...", total];
}

export function AdminFaculty() {
  const [searchParams, setSearchParams] = useSearchParams();

  // Search & Filters initialized from URL query params
  const [searchInput, setSearchInput] = useState(() => searchParams.get("search") || "");
  const [searchTerm, setSearchTerm] = useState(() => searchParams.get("search") || "");
  const [departmentFilter, setDepartmentFilter] = useState(() => searchParams.get("department") || "all");
  const [statusFilter, setStatusFilter] = useState<FacultyStatusFilter>(() => {
    const s = searchParams.get("status");
    return s === "active" || s === "inactive" ? s : "all";
  });

  // Rows per page (URL -> localStorage -> default 10)
  const getInitialPageSize = (): number => {
    try {
      const stored = localStorage.getItem("admin_faculty_page_size");
      if (stored && ALLOWED_PAGE_SIZES.includes(Number(stored))) {
        return Number(stored);
      }
    } catch {}
    const param = searchParams.get("page_size");
    if (param && ALLOWED_PAGE_SIZES.includes(Number(param))) {
      return Number(param);
    }
    return 10;
  };

  const [pageSize, setPageSize] = useState<number>(getInitialPageSize);
  const [page, setPage] = useState<number>(() => {
    const p = parseInt(searchParams.get("page") || "1", 10);
    return isNaN(p) || p < 1 ? 1 : p;
  });

  const [faculty, setFaculty] = useState<AdminFacultyRow[]>([]);
  const [departments, setDepartments] = useState<string[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [totalPages, setTotalPages] = useState(1);
  const [stats, setStats] = useState<FacultyStats>({
    total_faculty: 0,
    active_faculty: 0,
    inactive_faculty: 0,
    total_departments: 0,
  });

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [selectedFaculty, setSelectedFaculty] = useState<AdminFacultyRow | null>(null);
  const [viewLoading, setViewLoading] = useState(false);
  const [isViewOpen, setIsViewOpen] = useState(false);
  const [copiedFacultyField, setCopiedFacultyField] = useState<string | null>(null);

  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [creatingFaculty, setCreatingFaculty] = useState(false);
  const [createError, setCreateError] = useState("");
  const [createSuccess, setCreateSuccess] = useState("");
  const [createDepartments, setCreateDepartments] = useState<DepartmentOption[]>([]);
  const [createDepartmentsLoading, setCreateDepartmentsLoading] = useState(false);
  const [createForm, setCreateForm] = useState({
    first_name: "",
    last_name: "",
    email: "",
    employee_id: "",
    department_id: "",
    designation: "",
    is_active: "active",
    password: "",
  });

  const [isEditOpen, setIsEditOpen] = useState(false);
  const [editLoading, setEditLoading] = useState(false);
  const [savingEdit, setSavingEdit] = useState(false);
  const [editError, setEditError] = useState("");
  const [editSuccess, setEditSuccess] = useState("");
  const [editFacultyId, setEditFacultyId] = useState<number | null>(null);
  const [editForm, setEditForm] = useState({
    first_name: "",
    last_name: "",
    email: "",
    employee_id: "",
    department: "",
    designation: "",
    is_active: true,
    institutionName: "",
  });

  const [deletingId, setDeletingId] = useState<number | null>(null);

  const [changeDeptModal, setChangeDeptModal] = useState<{
    open: boolean;
    faculty: AdminFacultyRow | null;
    department: string;
    reason: string;
    loading: boolean;
    error: string;
  }>({
    open: false,
    faculty: null,
    department: "",
    reason: "",
    loading: false,
    error: "",
  });

  const [resetPasswordModal, setResetPasswordModal] = useState<{
    open: boolean;
    faculty: AdminFacultyRow | null;
    newPassword: string;
    reason: string;
    loading: boolean;
    error: string;
    temporaryPasswordResult: string | null;
    copied: boolean;
  }>({
    open: false,
    faculty: null,
    newPassword: "",
    reason: "",
    loading: false,
    error: "",
    temporaryPasswordResult: null,
    copied: false,
  });

  const requestIdRef = useRef(0);

  const handleUnauthorized = useCallback(() => {
    authStorage.clearSession();
    window.location.href = "/login";
  }, []);

  // Debounce search input (~300ms)
  useEffect(() => {
    const timer = setTimeout(() => {
      setSearchTerm(searchInput.trim());
      setPage(1);
    }, 300);
    return () => clearTimeout(timer);
  }, [searchInput]);

  // Synchronize state with URL search params
  useEffect(() => {
    const params: Record<string, string> = {};
    if (page > 1) params.page = String(page);
    if (pageSize !== 10) params.page_size = String(pageSize);
    if (searchTerm) params.search = searchTerm;
    if (departmentFilter !== "all") params.department = departmentFilter;
    if (statusFilter !== "all") params.status = statusFilter;
    setSearchParams(params, { replace: true });
  }, [page, pageSize, searchTerm, departmentFilter, statusFilter, setSearchParams]);

  // Fetch paginated faculty from backend
  const fetchFaculty = useCallback(async (targetPage = page, targetPageSize = pageSize) => {
    const reqId = ++requestIdRef.current;
    setLoading(true);
    setError("");

    try {
      const params: {
        search?: string;
        department?: string;
        status?: string;
        page?: number;
        page_size?: number;
      } = {
        page: targetPage,
        page_size: targetPageSize,
      };

      if (searchTerm) params.search = searchTerm;
      if (departmentFilter !== "all") params.department = departmentFilter;
      if (statusFilter !== "all") params.status = statusFilter;

      const response = await adminFacultyApi.getFaculty(params);
      if (reqId !== requestIdRef.current) return;

      const rows = Array.isArray(response?.data)
        ? response.data
        : Array.isArray(response?.results)
        ? response.results
        : [];
      setFaculty(rows);

      const pData = response.pagination;
      const count = pData?.total_count ?? response.count ?? response.total_faculty ?? rows.length;
      const calculatedPages = pData?.total_pages ?? Math.max(1, Math.ceil(count / targetPageSize));

      setTotalCount(count);
      setTotalPages(calculatedPages);

      // Clamp if requested page exceeded available pages
      if (targetPage > calculatedPages && calculatedPages > 0) {
        setPage(calculatedPages);
      }

      // Populate department filter options if empty
      if (departments.length === 0) {
        try {
          const deptRes = await departmentsApi.getDepartments();
          const rawDepts = Array.isArray(deptRes?.data) ? deptRes.data : Array.isArray(deptRes) ? deptRes : [];
          const deptNames = rawDepts.map((d: any) => d.department_name).filter(Boolean);
          if (deptNames.length > 0) {
            setDepartments(deptNames);
          } else {
            const rowDepts = Array.from(
              new Set(rows.map((f) => f.department?.trim()).filter((d): d is string => Boolean(d)))
            ).sort((a, b) => a.localeCompare(b));
            setDepartments(rowDepts);
          }
        } catch {
          const rowDepts = Array.from(
            new Set(rows.map((f) => f.department?.trim()).filter((d): d is string => Boolean(d)))
          ).sort((a, b) => a.localeCompare(b));
          setDepartments(rowDepts);
        }
      }

      const statistics = response.statistics;
      const totalFaculty = typeof statistics?.total_faculty === "number"
        ? statistics.total_faculty
        : response.total_faculty ?? count;
      const activeCount = typeof statistics?.active_faculty === "number"
        ? statistics.active_faculty
        : typeof response.active_faculty === "number"
          ? response.active_faculty
          : rows.filter(isFacultyActive).length;
      const inactiveCount = typeof statistics?.inactive_faculty === "number"
        ? statistics.inactive_faculty
        : typeof response.inactive_faculty === "number"
          ? response.inactive_faculty
          : Math.max(totalFaculty - activeCount, 0);

      setStats({
        total_faculty: totalFaculty,
        active_faculty: activeCount,
        inactive_faculty: inactiveCount,
        total_departments: statistics?.total_departments ?? response.total_departments ?? departments.length,
      });
    } catch (requestError) {
      if (reqId !== requestIdRef.current) return;
      if (axios.isAxiosError(requestError)) {
        if (requestError.response?.status === 401) {
          handleUnauthorized();
          return;
        }
        const extracted = extractApiErrorMessage(requestError.response?.data);
        setError(extracted ?? "Unable to fetch faculty. Please try again.");
      } else {
        setError("Unable to fetch faculty. Please try again.");
      }
    } finally {
      if (reqId === requestIdRef.current) {
        setLoading(false);
      }
    }
  }, [departmentFilter, departments.length, handleUnauthorized, page, pageSize, searchTerm, statusFilter]);

  useEffect(() => {
    void fetchFaculty(page, pageSize);
  }, [fetchFaculty, page, pageSize]);

  const handlePageSizeChange = (newSize: number) => {
    if (!ALLOWED_PAGE_SIZES.includes(newSize)) return;
    setPageSize(newSize);
    setPage(1);
    try {
      localStorage.setItem("admin_faculty_page_size", String(newSize));
    } catch {}
  };

  const fetchCreateDefaults = useCallback(async () => {
    setCreateDepartmentsLoading(true);
    setCreateError("");
    try {
      const [departmentsResponse, facultyResponse] = await Promise.all([
        departmentsApi.getDepartments(),
        adminFacultyApi.getFaculty({ page: 1, page_size: 100 }),
      ]);

      setCreateDepartments(departmentsResponse.data || []);
      setCreateForm((prev) => ({
        ...prev,
        employee_id: buildNextFacultyEmployeeId(facultyResponse.data || []),
      }));
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
      setCreateForm((prev) => ({
        ...prev,
        employee_id: buildNextFacultyEmployeeId(faculty),
      }));
    } finally {
      setCreateDepartmentsLoading(false);
    }
  }, [faculty, handleUnauthorized]);

  const resetCreateForm = useCallback(() => {
    setCreateForm({
      first_name: "",
      last_name: "",
      email: "",
      employee_id: "",
      department_id: "",
      designation: "",
      is_active: "active",
      password: "",
    });
    setCreateError("");
    setCreateSuccess("");
  }, []);

  const openCreateFacultyModal = () => {
    setIsCreateOpen(true);
    setCreateError("");
    setCreateSuccess("");
    resetCreateForm();
    void fetchCreateDefaults();
  };

  const handleCreateFaculty = async () => {
    const payload: AdminFacultyCreatePayload = {
      first_name: createForm.first_name.trim(),
      last_name: createForm.last_name.trim(),
      email: createForm.email.trim(),
      employee_id: createForm.employee_id.trim(),
      department_id: Number(createForm.department_id),
      designation: createForm.designation.trim(),
      is_active: createForm.is_active === "active",
      password: createForm.password,
    };

    if (!payload.first_name || !payload.last_name || !payload.email || !payload.password) {
      setCreateError("First name, last name, email, and password are required.");
      return;
    }

    if (!payload.department_id || Number.isNaN(payload.department_id)) {
      setCreateError("Please select a department.");
      return;
    }

    setCreatingFaculty(true);
    setCreateError("");
    setCreateSuccess("");

    try {
      await adminFacultyApi.createFaculty(payload);
      setCreateSuccess("Faculty created successfully.");
      await fetchFaculty(page, pageSize);
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
        setCreateError(extracted ?? "Unable to create faculty.");
      } else {
        setCreateError("Unable to create faculty.");
      }
    } finally {
      setCreatingFaculty(false);
    }
  };

  const handleViewFaculty = async (facultyId: number) => {
    setViewLoading(true);
    setSelectedFaculty(null);
    setIsViewOpen(true);
    try {
      const response = await adminFacultyApi.getFacultyById(facultyId);
      setSelectedFaculty(response.data || null);
    } catch (requestError) {
      if (axios.isAxiosError(requestError)) {
        if (requestError.response?.status === 401) {
          handleUnauthorized();
          return;
        }
        const extracted = extractApiErrorMessage(requestError.response?.data);
        setError(extracted ?? "Unable to fetch faculty details.");
      } else {
        setError("Unable to fetch faculty details.");
      }
    } finally {
      setViewLoading(false);
    }
  };

  const handleCopyFacultyText = (text: string, fieldName: string) => {
    navigator.clipboard.writeText(text);
    setCopiedFacultyField(fieldName);
    toast.success(`Copied ${fieldName} to clipboard!`);
    setTimeout(() => setCopiedFacultyField(null), 2000);
  };

  const getFacultyInitials = (name: string): string => {
    const parts = name.trim().split(/\s+/);
    if (parts.length >= 2) {
      return `${parts[0][0]}${parts[1][0]}`.toUpperCase();
    }
    return name.slice(0, 2).toUpperCase() || "FA";
  };

  const handleEditFaculty = async (facultyId: number) => {
    setEditLoading(true);
    setEditError("");
    setEditSuccess("");
    setEditFacultyId(facultyId);
    setIsEditOpen(true);

    try {
      const response = await adminFacultyApi.getFacultyById(facultyId);
      const data = response.data;
      if (data) {
        setEditForm({
          first_name: data.first_name || data.full_name?.split(" ")[0] || "",
          last_name: data.last_name || data.full_name?.split(" ").slice(1).join(" ") || "",
          email: data.email || "",
          employee_id: data.employee_id || "",
          department: data.department || "",
          designation: data.designation || "",
          is_active: typeof data.is_active === "boolean" ? data.is_active : isFacultyActive(data),
          institutionName: data.institution?.institution_name || "",
        });
      }
    } catch (requestError) {
      if (axios.isAxiosError(requestError)) {
        if (requestError.response?.status === 401) {
          handleUnauthorized();
          return;
        }
        const extracted = extractApiErrorMessage(requestError.response?.data);
        setEditError(extracted ?? "Unable to load faculty details for editing.");
      } else {
        setEditError("Unable to load faculty details for editing.");
      }
    } finally {
      setEditLoading(false);
    }
  };

  const handleSaveEdit = async () => {
    if (!editFacultyId) return;

    const payload: AdminFacultyUpdatePayload = {
      first_name: editForm.first_name.trim(),
      last_name: editForm.last_name.trim(),
      email: editForm.email.trim(),
      employee_id: editForm.employee_id.trim(),
      department: editForm.department.trim(),
      designation: editForm.designation.trim(),
      is_active: editForm.is_active,
    };

    if (!payload.first_name || !payload.last_name || !payload.email) {
      setEditError("First name, last name, and email are required.");
      return;
    }

    setSavingEdit(true);
    try {
      const response = await adminFacultyApi.updateFaculty(editFacultyId, payload);
      setEditSuccess("Faculty updated successfully.");
      await fetchFaculty(page, pageSize);
      setSelectedFaculty(response.data || null);
      setTimeout(() => {
        setIsEditOpen(false);
      }, 600);
    } catch (requestError) {
      if (axios.isAxiosError(requestError)) {
        if (requestError.response?.status === 401) {
          handleUnauthorized();
          return;
        }
        const extracted = extractApiErrorMessage(requestError.response?.data);
        setEditError(extracted ?? "Unable to update faculty.");
      } else {
        setEditError("Unable to update faculty.");
      }
    } finally {
      setSavingEdit(false);
    }
  };

  const handleSendEmail = (facultyItem: AdminFacultyRow) => {
    window.location.href = `mailto:${facultyItem.email}`;
  };

  const handleDeleteFaculty = async (facultyItem: AdminFacultyRow) => {
    const shouldDelete = window.confirm(`Delete ${facultyItem.full_name}? This action cannot be undone.`);
    if (!shouldDelete) return;

    setDeletingId(facultyItem.id);
    setError("");
    try {
      await adminFacultyApi.deleteFaculty(facultyItem.id);

      // If we deleted the only item on the current page, step back to previous page
      const nextPage = faculty.length === 1 && page > 1 ? page - 1 : page;
      setPage(nextPage);
      await fetchFaculty(nextPage, pageSize);

      if (selectedFaculty?.id === facultyItem.id) {
        setSelectedFaculty(null);
        setIsViewOpen(false);
      }
      toast.success("Faculty member deleted.");
    } catch (requestError) {
      if (axios.isAxiosError(requestError)) {
        if (requestError.response?.status === 401) {
          handleUnauthorized();
          return;
        }
        const extracted = extractApiErrorMessage(requestError.response?.data);
        setError(extracted ?? "Unable to delete faculty.");
      } else {
        setError("Unable to delete faculty.");
      }
    } finally {
      setDeletingId(null);
    }
  };

  // Toggle Active Status
  const handleToggleStatus = async (facultyItem: AdminFacultyRow) => {
    const isCurrentlyActive = (facultyItem.status?.toLowerCase() === "active") || (facultyItem.is_active !== false);
    const actionLabel = isCurrentlyActive ? "deactivate" : "activate";
    if (!window.confirm(`Are you sure you want to ${actionLabel} ${facultyItem.full_name}?`)) {
      return;
    }

    try {
      await adminFacultyApi.updateFaculty(facultyItem.id, {
        is_active: !isCurrentlyActive,
      });
      toast.success(`${facultyItem.full_name} has been ${isCurrentlyActive ? "deactivated" : "activated"}.`);
      await fetchFaculty(page, pageSize);
    } catch (err) {
      toast.error(extractApiErrorMessage(err) || `Failed to ${actionLabel} faculty.`);
    }
  };

  // Change Department Handlers
  const handleOpenChangeDept = (facultyItem: AdminFacultyRow) => {
    setChangeDeptModal({
      open: true,
      faculty: facultyItem,
      department: facultyItem.department || "",
      reason: "",
      loading: false,
      error: "",
    });
  };

  const handleSubmitChangeDept = async () => {
    if (!changeDeptModal.faculty) return;
    const targetUserId = changeDeptModal.faculty.user_id || changeDeptModal.faculty.id;
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
      await adminFacultyApi.changeDepartment(targetUserId, {
        department: changeDeptModal.department.trim(),
        reason: changeDeptModal.reason.trim(),
      });
      toast.success(`Department updated to ${changeDeptModal.department}.`);
      setChangeDeptModal((prev) => ({ ...prev, open: false, loading: false }));
      await fetchFaculty(page, pageSize);
    } catch (err: any) {
      const msg = err.response?.data?.message || err.response?.data?.detail || "Failed to change department.";
      setChangeDeptModal((prev) => ({ ...prev, error: msg, loading: false }));
    }
  };

  // Reset Password Handlers
  const handleOpenResetPassword = (facultyItem: AdminFacultyRow) => {
    setResetPasswordModal({
      open: true,
      faculty: facultyItem,
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
    if (!resetPasswordModal.faculty) return;
    setResetPasswordModal((prev) => ({ ...prev, loading: true, error: "" }));
    try {
      const res = await adminFacultyApi.resetPassword(resetPasswordModal.faculty.id, {
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

  // Pagination calculation
  const startRow = totalCount === 0 ? 0 : (page - 1) * pageSize + 1;
  const endRow = Math.min(page * pageSize, totalCount);
  const pageNumbers = useMemo(() => getPageNumbers(page, totalPages), [page, totalPages]);

  return (
    <DashboardLayout userRole="Admin">
      <div className="space-y-6 min-w-0 max-w-full">
        {/* Header Title & Add Button */}
        <div className="flex items-center justify-between gap-3 min-w-0 max-w-full">
          <div className="min-w-0 flex-1">
            <h1 className="text-2xl sm:text-3xl font-bold text-foreground mb-1 truncate">
              Faculty Management
            </h1>
            <p className="text-xs sm:text-sm text-muted-foreground truncate">
              Manage all faculty members and credentials
            </p>
          </div>
          <button
            className="shrink-0 px-4 sm:px-5 py-2.5 rounded-lg bg-gradient-to-r from-primary to-secondary text-white hover:opacity-90 shadow-md font-medium text-xs sm:text-sm transition-all flex items-center gap-2"
            onClick={openCreateFacultyModal}
          >
            <Plus className="w-4 h-4" />
            <span className="hidden sm:inline">Add Faculty</span>
            <span className="sm:hidden">Add</span>
          </button>
        </div>

        {/* Stats Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 min-w-0 max-w-full">
          <div className="bg-white rounded-xl p-5 shadow-xs border border-border hover:shadow-md hover:border-primary/20 transition-all min-w-0">
            <p className="text-xs sm:text-sm text-muted-foreground mb-1">Total Faculty</p>
            <p className="text-2xl sm:text-3xl font-bold text-foreground">{stats.total_faculty}</p>
          </div>
          <div className="bg-white rounded-xl p-5 shadow-xs border border-border hover:shadow-md hover:border-emerald-200 transition-all min-w-0">
            <p className="text-xs sm:text-sm text-muted-foreground mb-1">Active Faculty</p>
            <p className="text-2xl sm:text-3xl font-bold text-emerald-600">{stats.active_faculty}</p>
          </div>
          <div className="bg-white rounded-xl p-5 shadow-xs border border-border hover:shadow-md hover:border-blue-200 transition-all min-w-0">
            <p className="text-xs sm:text-sm text-muted-foreground mb-1">Total Departments</p>
            <p className="text-2xl sm:text-3xl font-bold text-blue-600">{stats.total_departments}</p>
          </div>
          <div className="bg-white rounded-xl p-5 shadow-xs border border-border hover:shadow-md hover:border-gray-300 transition-all min-w-0">
            <p className="text-xs sm:text-sm text-muted-foreground mb-1">Inactive Faculty</p>
            <p className="text-2xl sm:text-3xl font-bold text-gray-600">{stats.inactive_faculty}</p>
          </div>
        </div>

        {/* Search & Filters */}
        <div className="bg-white rounded-xl p-4 sm:p-5 shadow-xs border border-border min-w-0 max-w-full">
          <div className="flex flex-col xl:flex-row gap-3 min-w-0 max-w-full">
            <div className="flex-1 relative min-w-0">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
              <input
                type="text"
                placeholder="Search by name, email, or employee ID..."
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
                className="w-full pl-9 pr-3.5 py-2 rounded-lg bg-input-background border border-border text-sm focus:outline-none focus:ring-2 focus:ring-primary transition-all min-w-0"
              />
            </div>
            <div className="flex flex-col sm:flex-row gap-2.5 min-w-0 max-w-full">
              <div className="flex items-center gap-2 min-w-0 max-w-full flex-1 sm:flex-initial">
                <Filter className="w-4 h-4 text-muted-foreground shrink-0" />
                <select
                  value={departmentFilter}
                  onChange={(e) => {
                    setDepartmentFilter(e.target.value);
                    setPage(1);
                  }}
                  className="w-full sm:w-auto max-w-full truncate px-3 py-2 rounded-lg bg-input-background border border-border text-sm focus:outline-none focus:ring-2 focus:ring-primary transition-all"
                >
                  <option value="all">All Departments</option>
                  {departments.map((department) => (
                    <option key={department} value={department}>
                      {department}
                    </option>
                  ))}
                </select>
              </div>
              <div className="flex items-center gap-2 min-w-0 max-w-full flex-1 sm:flex-initial">
                <ShieldCheck className="w-4 h-4 text-muted-foreground shrink-0" />
                <select
                  value={statusFilter}
                  onChange={(e) => {
                    setStatusFilter(e.target.value as FacultyStatusFilter);
                    setPage(1);
                  }}
                  className="w-full sm:w-auto max-w-full truncate px-3 py-2 rounded-lg bg-input-background border border-border text-sm focus:outline-none focus:ring-2 focus:ring-primary transition-all"
                >
                  <option value="all">All Statuses</option>
                  <option value="active">Active</option>
                  <option value="inactive">Inactive</option>
                </select>
              </div>
            </div>
          </div>
          {error && <p className="mt-3 text-sm text-destructive">{error}</p>}
        </div>

        {/* Table & Cards Container */}
        <div className="bg-white rounded-xl shadow-xs border border-border overflow-hidden min-w-0 max-w-full">
          {/* Desktop Table View (>= 768px) with table-fixed & pure percentage columns */}
          <div className="hidden md:block w-full min-w-0 max-w-full">
            <table className="w-full table-fixed divide-y divide-border">
              <colgroup className="hidden xl:table-column-group">
                <col className="w-[26%]" />
                <col className="w-[12%]" />
                <col className="w-[22%]" />
                <col className="w-[16%]" />
                <col className="w-[10%]" />
                <col className="w-[14%]" />
              </colgroup>
              <thead className="bg-muted/50">
                <tr>
                  <th className="w-[36%] lg:w-[28%] xl:w-[26%] text-left px-4 py-3 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                    Faculty Member
                  </th>
                  <th className="hidden xl:table-cell xl:w-[12%] text-left px-3 py-3 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                    Employee ID
                  </th>
                  <th className="w-[34%] lg:w-[28%] xl:w-[22%] text-left px-3 py-3 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                    Department
                  </th>
                  <th className="hidden lg:table-cell lg:w-[18%] xl:w-[16%] text-left px-3 py-3 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                    Designation
                  </th>
                  <th className="w-[14%] lg:w-[12%] xl:w-[10%] text-left px-3 py-3 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                    Status
                  </th>
                  <th className="w-[16%] lg:w-[14%] xl:w-[14%] text-right px-3 py-3 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border bg-white">
                {loading ? (
                  <tr>
                    <td colSpan={6} className="px-6 py-12 text-center text-muted-foreground text-sm">
                      <div className="inline-flex items-center gap-2">
                        <div className="w-4 h-4 border-2 border-indigo-200 border-t-indigo-600 rounded-full animate-spin" />
                        <span>Loading faculty...</span>
                      </div>
                    </td>
                  </tr>
                ) : faculty.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="px-6 py-12 text-center text-muted-foreground text-sm">
                      <p className="font-medium text-foreground mb-1">No faculty members found</p>
                      <p className="text-xs text-muted-foreground">Try clearing your search or filter criteria.</p>
                    </td>
                  </tr>
                ) : (
                  faculty.map((facultyItem) => {
                    const status = getFacultyDisplayStatus(facultyItem);
                    const isActive = status.toLowerCase() === "active";

                    return (
                      <tr key={facultyItem.id} className="hover:bg-muted/30 transition-colors">
                        {/* Faculty Name & Email (with responsive fallback for hidden fields) */}
                        <td className="px-4 py-3 min-w-0">
                          <div className="min-w-0 max-w-full">
                            <Tooltip>
                              <TooltipTrigger asChild>
                                <span className="font-semibold text-foreground text-sm truncate cursor-default block">
                                  {facultyItem.full_name}
                                </span>
                              </TooltipTrigger>
                              <TooltipContent side="top" align="start">
                                {facultyItem.full_name}
                              </TooltipContent>
                            </Tooltip>

                            <Tooltip>
                              <TooltipTrigger asChild>
                                <span className="text-xs text-muted-foreground truncate cursor-default block">
                                  {facultyItem.email}
                                </span>
                              </TooltipTrigger>
                              <TooltipContent side="bottom" align="start">
                                {facultyItem.email}
                              </TooltipContent>
                            </Tooltip>

                            {/* Responsive fallback when Employee ID is hidden (< xl) */}
                            <div className="xl:hidden mt-0.5 text-[11px] font-mono text-muted-foreground truncate">
                              ID: {facultyItem.employee_id || "-"}
                            </div>

                            {/* Responsive fallback when Designation is hidden (< lg) */}
                            <div className="lg:hidden text-[11px] text-muted-foreground truncate">
                              {facultyItem.designation || "-"}
                            </div>
                          </div>
                        </td>

                        {/* Employee ID (Hidden on < xl) */}
                        <td
                          className="hidden xl:table-cell px-3 py-3 text-xs text-foreground font-mono truncate"
                          title={facultyItem.employee_id || "-"}
                        >
                          {facultyItem.employee_id || "-"}
                        </td>

                        {/* Department (wraps up to 2 lines with Tooltip) */}
                        <td className="px-3 py-3 min-w-0">
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <div className="text-xs text-foreground line-clamp-2 cursor-default break-words">
                                {facultyItem.department || "-"}
                              </div>
                            </TooltipTrigger>
                            <TooltipContent side="top" align="start">
                              {facultyItem.department || "-"}
                            </TooltipContent>
                          </Tooltip>
                        </td>

                        {/* Designation (Hidden on < lg, wraps up to 2 lines with Tooltip) */}
                        <td className="hidden lg:table-cell px-3 py-3 min-w-0">
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <div className="text-xs text-muted-foreground line-clamp-2 cursor-default break-words">
                                {facultyItem.designation || "-"}
                              </div>
                            </TooltipTrigger>
                            <TooltipContent side="top" align="start">
                              {facultyItem.designation || "-"}
                            </TooltipContent>
                          </Tooltip>
                        </td>

                        {/* Status Badge */}
                        <td className="px-3 py-3 min-w-0">
                          <span
                            className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${
                              isActive
                                ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                                : "bg-gray-100 text-gray-700 border border-gray-200"
                            }`}
                          >
                            {status}
                          </span>
                        </td>

                        {/* Actions Column (Clean hybrid pattern fitting inside bounding box) */}
                        <td className="px-3 py-3 text-right whitespace-nowrap">
                          <div className="flex items-center justify-end gap-1.5 min-w-0">
                            {/* Primary View Details Button */}
                            <button
                              type="button"
                              className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border border-border bg-card hover:bg-muted text-xs font-semibold text-foreground shadow-2xs hover:shadow-xs transition-all shrink-0 cursor-pointer"
                              aria-label={`View ${facultyItem.full_name}`}
                              onClick={() => void handleViewFaculty(facultyItem.id)}
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
                                  aria-label={`More actions for ${facultyItem.full_name}`}
                                >
                                  <MoreHorizontal className="w-4 h-4" />
                                </button>
                              </DropdownMenuTrigger>
                              <DropdownMenuContent align="end" className="w-52 z-50 p-1.5">
                                <DropdownMenuItem
                                  onClick={() => void handleEditFaculty(facultyItem.id)}
                                  className="cursor-pointer text-xs"
                                >
                                  <Edit className="w-3.5 h-3.5 mr-2 text-muted-foreground" />
                                  <span>Edit Details</span>
                                </DropdownMenuItem>
                                <DropdownMenuItem
                                  onClick={() => handleSendEmail(facultyItem)}
                                  className="cursor-pointer text-xs"
                                >
                                  <Mail className="w-3.5 h-3.5 mr-2 text-muted-foreground" />
                                  <span>Email Faculty</span>
                                </DropdownMenuItem>
                                <DropdownMenuSeparator />
                                <DropdownMenuItem
                                  onClick={() => handleOpenChangeDept(facultyItem)}
                                  className="cursor-pointer text-xs"
                                >
                                  <Building2 className="w-3.5 h-3.5 mr-2 text-muted-foreground" />
                                  <span>Change Department</span>
                                </DropdownMenuItem>
                                <DropdownMenuItem
                                  onClick={() => handleOpenResetPassword(facultyItem)}
                                  className="cursor-pointer text-xs"
                                >
                                  <KeyRound className="w-3.5 h-3.5 mr-2 text-muted-foreground" />
                                  <span>Reset Password</span>
                                </DropdownMenuItem>
                                <DropdownMenuSeparator />
                                <DropdownMenuItem
                                  onClick={() => void handleToggleStatus(facultyItem)}
                                  className="cursor-pointer text-xs text-amber-600 focus:text-amber-600 focus:bg-amber-50"
                                >
                                  {isActive ? (
                                    <UserX className="w-3.5 h-3.5 mr-2" />
                                  ) : (
                                    <UserCheck className="w-3.5 h-3.5 mr-2" />
                                  )}
                                  <span>{isActive ? "Deactivate Account" : "Activate Account"}</span>
                                </DropdownMenuItem>
                                <DropdownMenuItem
                                  onClick={() => void handleDeleteFaculty(facultyItem)}
                                  disabled={deletingId === facultyItem.id}
                                  className="cursor-pointer text-xs text-destructive focus:text-destructive focus:bg-destructive/10"
                                >
                                  <Trash2 className="w-3.5 h-3.5 mr-2" />
                                  <span>Delete Faculty</span>
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

          {/* Mobile Stacked Cards View (< 768px) with Zero Horizontal Overflow */}
          <div className="block md:hidden divide-y divide-border min-w-0 max-w-full">
            {loading ? (
              <div className="p-8 text-center text-muted-foreground text-sm">
                <div className="inline-flex items-center gap-2">
                  <div className="w-4 h-4 border-2 border-indigo-200 border-t-indigo-600 rounded-full animate-spin" />
                  <span>Loading faculty...</span>
                </div>
              </div>
            ) : faculty.length === 0 ? (
              <div className="p-8 text-center text-muted-foreground text-sm">
                <p className="font-medium text-foreground mb-1">No faculty members found</p>
                <p className="text-xs text-muted-foreground">Try clearing your search or filter criteria.</p>
              </div>
            ) : (
              faculty.map((facultyItem) => {
                const status = getFacultyDisplayStatus(facultyItem);
                const isActive = status.toLowerCase() === "active";

                return (
                  <div key={facultyItem.id} className="p-4 space-y-3 min-w-0 max-w-full">
                    <div className="flex items-start justify-between gap-2 min-w-0">
                      <div className="min-w-0 flex-1">
                        <p
                          className="font-semibold text-sm text-foreground truncate"
                          title={facultyItem.full_name}
                        >
                          {facultyItem.full_name}
                        </p>
                        <a
                          href={`mailto:${facultyItem.email}`}
                          className="text-xs text-primary truncate block hover:underline"
                          title={facultyItem.email}
                        >
                          {facultyItem.email}
                        </a>
                      </div>
                      <span
                        className={`inline-flex shrink-0 items-center px-2 py-0.5 rounded-full text-xs font-medium ${
                          isActive
                            ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                            : "bg-gray-100 text-gray-700 border border-gray-200"
                        }`}
                      >
                        {status}
                      </span>
                    </div>

                    <div className="grid grid-cols-2 gap-2 text-xs bg-muted/30 p-2.5 rounded-lg border border-border/60 min-w-0">
                      <div className="min-w-0">
                        <span className="text-muted-foreground block text-[10px] uppercase font-medium">
                          Employee ID
                        </span>
                        <span className="font-mono text-foreground truncate block">
                          {facultyItem.employee_id || "-"}
                        </span>
                      </div>
                      <div className="min-w-0">
                        <span className="text-muted-foreground block text-[10px] uppercase font-medium">
                          Department
                        </span>
                        <span className="text-foreground truncate block" title={facultyItem.department || "-"}>
                          {facultyItem.department || "-"}
                        </span>
                      </div>
                      {facultyItem.designation && (
                        <div className="col-span-2 min-w-0">
                          <span className="text-muted-foreground block text-[10px] uppercase font-medium">
                            Designation
                          </span>
                          <span className="text-muted-foreground truncate block">
                            {facultyItem.designation}
                          </span>
                        </div>
                      )}
                    </div>

                    <div className="flex items-center justify-between gap-2 pt-2 border-t border-border/40">
                      <button
                        type="button"
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-border bg-card hover:bg-muted text-xs font-semibold text-foreground shadow-2xs cursor-pointer"
                        onClick={() => void handleViewFaculty(facultyItem.id)}
                        aria-label={`View details for ${facultyItem.full_name}`}
                      >
                        <Eye className="w-3.5 h-3.5 text-muted-foreground" />
                        <span>View Details</span>
                      </button>

                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <button
                            type="button"
                            className="p-1.5 rounded-lg border border-border bg-card hover:bg-muted text-muted-foreground text-xs flex items-center gap-1 cursor-pointer"
                            aria-label={`More actions for ${facultyItem.full_name}`}
                          >
                            <MoreHorizontal className="w-4 h-4" />
                            <span className="text-xs">Actions</span>
                          </button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end" className="w-52 z-50 p-1.5">
                          <DropdownMenuItem
                            onClick={() => void handleEditFaculty(facultyItem.id)}
                            className="cursor-pointer text-xs"
                          >
                            <Edit className="w-3.5 h-3.5 mr-2 text-muted-foreground" />
                            <span>Edit Details</span>
                          </DropdownMenuItem>
                          <DropdownMenuItem
                            onClick={() => handleSendEmail(facultyItem)}
                            className="cursor-pointer text-xs"
                          >
                            <Mail className="w-3.5 h-3.5 mr-2 text-muted-foreground" />
                            <span>Email Faculty</span>
                          </DropdownMenuItem>
                          <DropdownMenuSeparator />
                          <DropdownMenuItem
                            onClick={() => handleOpenChangeDept(facultyItem)}
                            className="cursor-pointer text-xs"
                          >
                            <Building2 className="w-3.5 h-3.5 mr-2 text-muted-foreground" />
                            <span>Change Department</span>
                          </DropdownMenuItem>
                          <DropdownMenuItem
                            onClick={() => handleOpenResetPassword(facultyItem)}
                            className="cursor-pointer text-xs"
                          >
                            <KeyRound className="w-3.5 h-3.5 mr-2 text-muted-foreground" />
                            <span>Reset Password</span>
                          </DropdownMenuItem>
                          <DropdownMenuSeparator />
                          <DropdownMenuItem
                            onClick={() => void handleToggleStatus(facultyItem)}
                            className="cursor-pointer text-xs text-amber-600 focus:text-amber-600 focus:bg-amber-50"
                          >
                            {isActive ? (
                              <UserX className="w-3.5 h-3.5 mr-2" />
                            ) : (
                              <UserCheck className="w-3.5 h-3.5 mr-2" />
                            )}
                            <span>{isActive ? "Deactivate Account" : "Activate Account"}</span>
                          </DropdownMenuItem>
                          <DropdownMenuItem
                            onClick={() => void handleDeleteFaculty(facultyItem)}
                            disabled={deletingId === facultyItem.id}
                            className="cursor-pointer text-xs text-destructive focus:text-destructive focus:bg-destructive/10"
                          >
                            <Trash2 className="w-3.5 h-3.5 mr-2" />
                            <span>Delete Faculty</span>
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </div>
                  </div>
                );
              })
            )}
          </div>

          {/* Accessible Server-Side Pagination Footer */}
          {!loading && totalCount > 0 && (
            <nav
              aria-label="Pagination"
              className="flex flex-col sm:flex-row items-center justify-between px-4 sm:px-5 py-3.5 border-t border-border bg-muted/20 text-xs text-muted-foreground gap-3 min-w-0 max-w-full"
            >
              <div className="flex items-center gap-3 min-w-0" aria-live="polite">
                <span className="truncate">
                  Showing <span className="font-semibold text-foreground">{startRow}</span> to{" "}
                  <span className="font-semibold text-foreground">{endRow}</span> of{" "}
                  <span className="font-semibold text-foreground">{totalCount}</span> faculty
                </span>

                <div className="flex items-center gap-1.5 shrink-0">
                  <label htmlFor="rows-per-page" className="sr-only sm:not-sr-only text-xs text-muted-foreground">
                    Rows:
                  </label>
                  <select
                    id="rows-per-page"
                    aria-label="Rows per page"
                    value={pageSize}
                    onChange={(e) => handlePageSizeChange(Number(e.target.value))}
                    className="px-2 py-1 rounded border border-border bg-card text-foreground font-medium text-xs focus:outline-none focus:ring-2 focus:ring-primary cursor-pointer"
                  >
                    <option value={10}>10</option>
                    <option value={25}>25</option>
                    <option value={50}>50</option>
                    <option value={100}>100</option>
                  </select>
                </div>
              </div>

              <div className="inline-flex items-center gap-1">
                <button
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page <= 1}
                  aria-label="Go to previous page"
                  className="px-2.5 py-1.5 rounded-md border border-border bg-card hover:bg-muted text-foreground disabled:opacity-40 disabled:cursor-not-allowed transition-all flex items-center gap-1 focus:outline-none focus:ring-2 focus:ring-primary"
                >
                  <ChevronLeft className="w-3.5 h-3.5" />
                  <span className="hidden sm:inline">Previous</span>
                </button>

                {/* Numbered buttons with ellipsis for larger screens */}
                <div className="hidden sm:flex items-center gap-1">
                  {pageNumbers.map((pNum, idx) => {
                    if (pNum === "...") {
                      return (
                        <span key={`ellipsis-${idx}`} className="px-2 py-1 text-muted-foreground">
                          ...
                        </span>
                      );
                    }
                    const isCurrent = pNum === page;
                    return (
                      <button
                        key={`page-${pNum}`}
                        onClick={() => setPage(Number(pNum))}
                        aria-current={isCurrent ? "page" : undefined}
                        aria-label={`Page ${pNum}`}
                        className={`min-w-[32px] h-8 px-2 py-1 rounded-md text-xs font-medium transition-all focus:outline-none focus:ring-2 focus:ring-primary ${
                          isCurrent
                            ? "bg-primary text-white shadow-xs font-semibold"
                            : "border border-border bg-card hover:bg-muted text-foreground"
                        }`}
                      >
                        {pNum}
                      </button>
                    );
                  })}
                </div>

                {/* Mobile compact indicator */}
                <span className="sm:hidden px-2 text-xs font-medium text-foreground">
                  Page {page} of {totalPages}
                </span>

                <button
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  disabled={page >= totalPages}
                  aria-label="Go to next page"
                  className="px-2.5 py-1.5 rounded-md border border-border bg-card hover:bg-muted text-foreground disabled:opacity-40 disabled:cursor-not-allowed transition-all flex items-center gap-1 focus:outline-none focus:ring-2 focus:ring-primary"
                >
                  <span className="hidden sm:inline">Next</span>
                  <ChevronRight className="w-3.5 h-3.5" />
                </button>
              </div>
            </nav>
          )}
        </div>

        {/* ================= FACULTY DETAILS DRAWER ================= */}
        <Sheet open={isViewOpen} onOpenChange={setIsViewOpen}>
          <SheetContent
            side="right"
            className="w-full sm:max-w-lg md:max-w-xl lg:max-w-2xl p-0 flex flex-col h-full bg-card border-l border-border shadow-2xl overflow-hidden focus:outline-none"
          >
            {viewLoading ? (
              <div className="flex-1 flex flex-col items-center justify-center p-8 text-center text-muted-foreground">
                <RefreshCw className="w-8 h-8 animate-spin text-primary mb-3" />
                <p className="text-sm font-medium">Loading faculty profile & teaching summary...</p>
              </div>
            ) : selectedFaculty ? (
              <div className="flex flex-col h-full overflow-hidden">
                {/* Sticky Drawer Header */}
                <div className="p-5 sm:p-6 bg-gradient-to-br from-indigo-500/10 via-background to-primary/10 border-b border-border shrink-0">
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex items-start gap-4 min-w-0">
                      <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-indigo-600 to-primary text-white font-extrabold text-xl flex items-center justify-center shadow-md shrink-0">
                        {getFacultyInitials(selectedFaculty.full_name)}
                      </div>
                      <div className="min-w-0 space-y-1">
                        <div className="flex items-center gap-2 flex-wrap">
                          <h3 className="text-lg sm:text-xl font-bold text-foreground truncate">
                            {selectedFaculty.full_name}
                          </h3>
                          <span
                            className={`px-2 py-0.5 rounded-full text-[11px] font-bold ${
                              selectedFaculty.is_active !== false
                                ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                                : "bg-rose-50 text-rose-700 border border-rose-200"
                            }`}
                          >
                            {getFacultyDisplayStatus(selectedFaculty)}
                          </span>
                        </div>
                        <div className="flex items-center gap-2 flex-wrap text-xs text-muted-foreground">
                          <span className="font-mono bg-muted/60 px-2 py-0.5 rounded text-[11px] font-semibold text-foreground">
                            {selectedFaculty.employee_id || "No Employee ID"}
                          </span>
                          <span>•</span>
                          <span className="font-medium text-foreground">{selectedFaculty.department || "Unassigned"}</span>
                          {selectedFaculty.designation && (
                            <>
                              <span>•</span>
                              <span className="font-medium">{selectedFaculty.designation}</span>
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

                {/* Drawer Body with Tabs */}
                <div className="flex-1 overflow-y-auto p-5 sm:p-6 space-y-6 overflow-x-hidden">
                  <Tabs defaultValue="overview" className="w-full space-y-5">
                    <TabsList className="grid grid-cols-2 w-full bg-muted/60 p-1 rounded-xl">
                      <TabsTrigger value="overview" className="text-xs font-bold py-2 rounded-lg data-[state=active]:bg-background data-[state=active]:text-foreground data-[state=active]:shadow-xs">
                        Profile & Summary
                      </TabsTrigger>
                      <TabsTrigger value="exams" className="text-xs font-bold py-2 rounded-lg data-[state=active]:bg-background data-[state=active]:text-foreground data-[state=active]:shadow-xs">
                        Created Exams ({selectedFaculty.recent_exams ? selectedFaculty.recent_exams.length : selectedFaculty.exams_count || 0})
                      </TabsTrigger>
                    </TabsList>

                    {/* TAB 1: PROFILE & SUMMARY */}
                    <TabsContent value="overview" className="space-y-6 focus:outline-none">
                      {/* 3-Grid Key Activity Stat Cards */}
                      <div className="grid grid-cols-3 gap-3">
                        <div className="bg-card rounded-xl p-3.5 border border-border shadow-xs text-center sm:text-left">
                          <div className="text-[11px] font-medium text-muted-foreground flex items-center justify-center sm:justify-start gap-1 mb-1">
                            <BookOpen className="w-3.5 h-3.5 text-primary" />
                            Exams Created
                          </div>
                          <div className="text-xl sm:text-2xl font-bold text-foreground">
                            {selectedFaculty.exams_count ?? 0}
                          </div>
                        </div>

                        <div className="bg-card rounded-xl p-3.5 border border-border shadow-xs text-center sm:text-left">
                          <div className="text-[11px] font-medium text-muted-foreground flex items-center justify-center sm:justify-start gap-1 mb-1">
                            <Award className="w-3.5 h-3.5 text-emerald-600" />
                            Active Exams
                          </div>
                          <div className="text-xl sm:text-2xl font-bold text-emerald-600">
                            {selectedFaculty.active_exams_count ?? 0}
                          </div>
                        </div>

                        <div className="bg-card rounded-xl p-3.5 border border-border shadow-xs text-center sm:text-left">
                          <div className="text-[11px] font-medium text-muted-foreground flex items-center justify-center sm:justify-start gap-1 mb-1">
                            <Database className="w-3.5 h-3.5 text-indigo-600" />
                            Bank Items
                          </div>
                          <div className="text-xl sm:text-2xl font-bold text-indigo-600">
                            {selectedFaculty.questions_count ?? 0}
                          </div>
                        </div>
                      </div>

                      {/* Faculty Details Card */}
                      <div className="bg-card rounded-2xl border border-border p-4 sm:p-5 shadow-xs space-y-3.5">
                        <h4 className="text-xs font-bold uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
                          <User className="w-3.5 h-3.5" />
                          Faculty Details & Contact
                        </h4>

                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
                          <div className="p-3 bg-muted/30 rounded-xl border border-border/60">
                            <span className="text-muted-foreground block text-[11px] mb-0.5">Email Address</span>
                            <div className="flex items-center justify-between gap-2">
                              <span className="font-semibold text-foreground truncate">{selectedFaculty.email}</span>
                              <button
                                type="button"
                                onClick={() => handleCopyFacultyText(selectedFaculty.email, "email")}
                                className="text-muted-foreground hover:text-foreground p-1 rounded"
                                title="Copy email"
                              >
                                {copiedFacultyField === "email" ? (
                                  <Check className="w-3.5 h-3.5 text-emerald-600" />
                                ) : (
                                  <Copy className="w-3.5 h-3.5" />
                                )}
                              </button>
                            </div>
                          </div>

                          <div className="p-3 bg-muted/30 rounded-xl border border-border/60">
                            <span className="text-muted-foreground block text-[11px] mb-0.5">Employee ID</span>
                            <div className="flex items-center justify-between gap-2">
                              <span className="font-mono font-bold text-foreground">
                                {selectedFaculty.employee_id || "N/A"}
                              </span>
                              {selectedFaculty.employee_id && (
                                <button
                                  type="button"
                                  onClick={() => handleCopyFacultyText(selectedFaculty.employee_id!, "Employee ID")}
                                  className="text-muted-foreground hover:text-foreground p-1 rounded"
                                  title="Copy Employee ID"
                                >
                                  {copiedFacultyField === "Employee ID" ? (
                                    <Check className="w-3.5 h-3.5 text-emerald-600" />
                                  ) : (
                                    <Copy className="w-3.5 h-3.5" />
                                  )}
                                </button>
                              )}
                            </div>
                          </div>

                          <div className="p-3 bg-muted/30 rounded-xl border border-border/60">
                            <span className="text-muted-foreground block text-[11px] mb-0.5">Department</span>
                            <span className="font-semibold text-foreground block">
                              {selectedFaculty.department || "Unassigned"}
                            </span>
                          </div>

                          <div className="p-3 bg-muted/30 rounded-xl border border-border/60">
                            <span className="text-muted-foreground block text-[11px] mb-0.5">Designation</span>
                            <span className="font-semibold text-foreground block">
                              {selectedFaculty.designation || "Faculty Member"}
                            </span>
                          </div>

                          <div className="p-3 bg-muted/30 rounded-xl border border-border/60 sm:col-span-2">
                            <span className="text-muted-foreground block text-[11px] mb-0.5">Institution</span>
                            <span className="font-semibold text-foreground block">
                              {selectedFaculty.institution?.institution_name || "Apex University"} (
                              {selectedFaculty.institution?.institution_code || "APEX"})
                            </span>
                          </div>
                        </div>
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
                              handleOpenChangeDept(selectedFaculty);
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
                              handleOpenResetPassword(selectedFaculty);
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
                              handleEditFaculty(selectedFaculty.id);
                            }}
                            className="px-3.5 py-2.5 rounded-xl border border-border bg-card hover:bg-muted text-xs font-semibold text-foreground flex items-center justify-center gap-2 transition-colors shadow-2xs"
                          >
                            <Edit className="w-3.5 h-3.5 text-slate-600" />
                            Edit Faculty
                          </button>
                        </div>
                      </div>
                    </TabsContent>

                    {/* TAB 2: CREATED EXAMS & PAPERS */}
                    <TabsContent value="exams" className="space-y-4 focus:outline-none">
                      {!selectedFaculty.recent_exams || selectedFaculty.recent_exams.length === 0 ? (
                        <div className="p-10 text-center bg-muted/20 border border-border rounded-2xl">
                          <BookOpen className="w-10 h-10 mx-auto mb-2 text-muted-foreground/40" />
                          <p className="font-semibold text-foreground text-sm">No Exams Created Yet</p>
                          <p className="text-xs text-muted-foreground max-w-xs mx-auto mt-1">
                            This faculty member has not generated or published any exams in this institution.
                          </p>
                        </div>
                      ) : (
                        <div className="space-y-2.5">
                          {selectedFaculty.recent_exams.map((ex: any) => (
                            <div
                              key={ex.id}
                              className="p-3.5 rounded-xl border border-border bg-card hover:bg-muted/30 transition-all flex items-center justify-between gap-3 text-xs"
                            >
                              <div className="space-y-1 min-w-0 flex-1">
                                <h5 className="font-bold text-foreground truncate">{ex.title}</h5>
                                <div className="flex items-center gap-2 text-[11px] text-muted-foreground">
                                  {ex.subject && <span>{ex.subject}</span>}
                                  {ex.duration_minutes && (
                                    <>
                                      <span>•</span>
                                      <span>{ex.duration_minutes} mins</span>
                                    </>
                                  )}
                                  {ex.created_at && (
                                    <>
                                      <span>•</span>
                                      <span>{new Date(ex.created_at).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })}</span>
                                    </>
                                  )}
                                </div>
                              </div>
                              <div className="text-right shrink-0 space-y-1">
                                <div className="font-bold text-foreground">{ex.total_marks || 0} Marks</div>
                                <span
                                  className={`inline-block px-2 py-0.5 rounded text-[10px] font-extrabold uppercase ${
                                    ex.status === "published"
                                      ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                                      : ex.status === "draft"
                                      ? "bg-amber-50 text-amber-700 border border-amber-200"
                                      : "bg-slate-100 text-slate-600 border border-slate-200"
                                  }`}
                                >
                                  {ex.status}
                                </span>
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </TabsContent>
                  </Tabs>
                </div>

                {/* Drawer Footer */}
                <div className="p-4 bg-muted/20 border-t border-border flex items-center justify-end shrink-0">
                  <SheetClose className="px-4 py-2 rounded-lg border border-border bg-background hover:bg-muted text-xs font-semibold text-foreground transition-colors">
                    Close
                  </SheetClose>
                </div>
              </div>
            ) : null}
          </SheetContent>
        </Sheet>

        {/* Edit Faculty Modal */}
        {isEditOpen && (
          <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4">
            <div className="w-full max-w-2xl bg-white rounded-xl shadow-xl border border-border">
              <div className="flex items-center justify-between p-6 border-b border-border">
                <h3 className="text-xl font-semibold">Edit Faculty</h3>
                <button
                  className="px-3 py-1.5 rounded border border-border hover:bg-muted"
                  onClick={() => setIsEditOpen(false)}
                >
                  Close
                </button>
              </div>
              <div className="p-6 space-y-4">
                {editLoading ? (
                  <p className="text-muted-foreground">Loading edit form...</p>
                ) : (
                  <>
                    <div className="grid sm:grid-cols-2 gap-4">
                      <div>
                        <label className="block text-sm text-muted-foreground mb-2">First Name</label>
                        <input
                          type="text"
                          value={editForm.first_name}
                          onChange={(e) => setEditForm((prev) => ({ ...prev, first_name: e.target.value }))}
                          className="w-full px-4 py-2.5 rounded-lg border border-border focus:outline-none focus:ring-2 focus:ring-primary/20 transition-all"
                        />
                      </div>
                      <div>
                        <label className="block text-sm text-muted-foreground mb-2">Last Name</label>
                        <input
                          type="text"
                          value={editForm.last_name}
                          onChange={(e) => setEditForm((prev) => ({ ...prev, last_name: e.target.value }))}
                          className="w-full px-4 py-2.5 rounded-lg border border-border focus:outline-none focus:ring-2 focus:ring-primary/20 transition-all"
                        />
                      </div>
                    </div>

                    <div className="grid sm:grid-cols-2 gap-4">
                      <div>
                        <label className="block text-sm text-muted-foreground mb-2">Email</label>
                        <input
                          type="email"
                          value={editForm.email}
                          onChange={(e) => setEditForm((prev) => ({ ...prev, email: e.target.value }))}
                          className="w-full px-4 py-2.5 rounded-lg border border-border focus:outline-none focus:ring-2 focus:ring-primary/20 transition-all"
                        />
                      </div>
                      <div>
                        <label className="block text-sm text-muted-foreground mb-2">Employee ID</label>
                        <input
                          type="text"
                          value={editForm.employee_id}
                          readOnly
                          className="w-full px-4 py-2.5 rounded-lg border border-border bg-muted text-muted-foreground cursor-not-allowed focus:outline-none"
                        />
                      </div>
                    </div>

                    <div className="grid sm:grid-cols-2 gap-4">
                      <div>
                        <label className="block text-sm text-muted-foreground mb-2">Department</label>
                        <input
                          type="text"
                          value={editForm.department}
                          onChange={(e) => setEditForm((prev) => ({ ...prev, department: e.target.value }))}
                          className="w-full px-4 py-2.5 rounded-lg border border-border focus:outline-none focus:ring-2 focus:ring-primary/20 transition-all"
                        />
                      </div>
                      <div>
                        <label className="block text-sm text-muted-foreground mb-2">Designation</label>
                        <input
                          type="text"
                          value={editForm.designation}
                          onChange={(e) => setEditForm((prev) => ({ ...prev, designation: e.target.value }))}
                          className="w-full px-4 py-2.5 rounded-lg border border-border focus:outline-none focus:ring-2 focus:ring-primary/20 transition-all"
                        />
                      </div>
                    </div>

                    <div className="grid sm:grid-cols-2 gap-4">
                      <div>
                        <label className="block text-sm text-muted-foreground mb-2">Status</label>
                        <select
                          value={editForm.is_active ? "active" : "inactive"}
                          onChange={(e) => setEditForm((prev) => ({ ...prev, is_active: e.target.value === "active" }))}
                          className="w-full px-4 py-2.5 rounded-lg border border-border focus:outline-none focus:ring-2 focus:ring-primary/20 transition-all"
                        >
                          <option value="active">Active</option>
                          <option value="inactive">Inactive</option>
                        </select>
                      </div>
                      <div>
                        <label className="block text-sm text-muted-foreground mb-2">Institution</label>
                        <input
                          type="text"
                          readOnly
                          disabled
                          value={editForm.institutionName}
                          className="w-full px-4 py-2.5 rounded-lg border border-border bg-muted text-muted-foreground cursor-not-allowed"
                        />
                      </div>
                    </div>

                    {editError && <p className="text-sm text-destructive">{editError}</p>}
                    {editSuccess && <p className="text-sm text-green-600">{editSuccess}</p>}

                    <div className="pt-2">
                      <button
                        onClick={() => void handleSaveEdit()}
                        disabled={savingEdit}
                        className="px-6 py-2.5 rounded-lg bg-gradient-to-r from-primary to-secondary text-white font-semibold hover:shadow-lg transition-all disabled:opacity-60 disabled:cursor-not-allowed"
                      >
                        {savingEdit ? "Saving..." : "Save Changes"}
                      </button>
                    </div>
                  </>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Add Faculty Modal */}
        {isCreateOpen && (
          <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4">
            <div className="w-full max-w-2xl bg-white rounded-xl shadow-xl border border-border">
              <div className="flex items-center justify-between p-6 border-b border-border">
                <h3 className="text-xl font-semibold">Add Faculty</h3>
                <button
                  className="px-3 py-1.5 rounded border border-border hover:bg-muted"
                  onClick={() => {
                    setIsCreateOpen(false);
                    resetCreateForm();
                  }}
                >
                  Close
                </button>
              </div>
              <div className="p-6 space-y-4">
                <div className="grid sm:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm text-muted-foreground mb-2">First Name</label>
                    <input
                      type="text"
                      value={createForm.first_name}
                      onChange={(e) => setCreateForm((prev) => ({ ...prev, first_name: e.target.value }))}
                      disabled={creatingFaculty}
                      className="w-full px-4 py-2.5 rounded-lg border border-border focus:outline-none focus:ring-2 focus:ring-primary/20 transition-all"
                    />
                  </div>
                  <div>
                    <label className="block text-sm text-muted-foreground mb-2">Last Name</label>
                    <input
                      type="text"
                      value={createForm.last_name}
                      onChange={(e) => setCreateForm((prev) => ({ ...prev, last_name: e.target.value }))}
                      disabled={creatingFaculty}
                      className="w-full px-4 py-2.5 rounded-lg border border-border focus:outline-none focus:ring-2 focus:ring-primary/20 transition-all"
                    />
                  </div>
                </div>

                <div className="grid sm:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm text-muted-foreground mb-2">Email</label>
                    <input
                      type="email"
                      value={createForm.email}
                      onChange={(e) => setCreateForm((prev) => ({ ...prev, email: e.target.value }))}
                      disabled={creatingFaculty}
                      className="w-full px-4 py-2.5 rounded-lg border border-border focus:outline-none focus:ring-2 focus:ring-primary/20 transition-all"
                    />
                  </div>
                  <div>
                    <label className="block text-sm text-muted-foreground mb-2">Employee ID (Auto-generated)</label>
                    <input
                      type="text"
                      value={createForm.employee_id}
                      readOnly
                      disabled={creatingFaculty}
                      className="w-full px-4 py-2.5 rounded-lg border border-border bg-muted text-muted-foreground cursor-not-allowed focus:outline-none"
                    />
                  </div>
                </div>

                <div className="grid sm:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm text-muted-foreground mb-2">Department</label>
                    <Combobox
                      value={createForm.department_id}
                      onValueChange={(value) => setCreateForm((prev) => ({ ...prev, department_id: value }))}
                      disabled={creatingFaculty || createDepartmentsLoading || createDepartments.length === 0}
                      placeholder={createDepartmentsLoading ? "Loading departments..." : "Select Department"}
                      searchPlaceholder="Type to filter departments..."
                      emptyText={createDepartmentsLoading ? "Loading departments..." : "No departments available"}
                      options={createDepartments.map((department) => ({
                        value: String(department.id),
                        label: department.department_name,
                      }))}
                    />
                  </div>
                  <div>
                    <label className="block text-sm text-muted-foreground mb-2">Designation</label>
                    <input
                      type="text"
                      value={createForm.designation}
                      onChange={(e) => setCreateForm((prev) => ({ ...prev, designation: e.target.value }))}
                      disabled={creatingFaculty}
                      className="w-full px-4 py-2.5 rounded-lg border border-border focus:outline-none focus:ring-2 focus:ring-primary/20 transition-all"
                    />
                  </div>
                </div>

                <div className="grid sm:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm text-muted-foreground mb-2">Status</label>
                    <select
                      value={createForm.is_active}
                      onChange={(e) => setCreateForm((prev) => ({ ...prev, is_active: e.target.value }))}
                      disabled={creatingFaculty}
                      className="w-full px-4 py-2.5 rounded-lg border border-border focus:outline-none focus:ring-2 focus:ring-primary/20 transition-all"
                    >
                      <option value="active">Active</option>
                      <option value="inactive">Inactive</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm text-muted-foreground mb-2">Password</label>
                    <input
                      type="password"
                      value={createForm.password}
                      onChange={(e) => setCreateForm((prev) => ({ ...prev, password: e.target.value }))}
                      disabled={creatingFaculty}
                      className="w-full px-4 py-2.5 rounded-lg border border-border focus:outline-none focus:ring-2 focus:ring-primary/20 transition-all"
                    />
                  </div>
                </div>

                {createError && <p className="text-sm text-destructive">{createError}</p>}
                {createSuccess && <p className="text-sm text-green-600">{createSuccess}</p>}

                <div className="pt-2">
                  <button
                    onClick={() => void handleCreateFaculty()}
                    disabled={creatingFaculty}
                    className="px-6 py-2.5 rounded-lg bg-gradient-to-r from-primary to-secondary text-white font-semibold hover:shadow-lg transition-all disabled:opacity-60 disabled:cursor-not-allowed"
                  >
                    {creatingFaculty ? "Creating..." : "Create Faculty"}
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Change Department Modal */}
        {changeDeptModal.open && changeDeptModal.faculty && (
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
                    Faculty: <strong className="text-foreground">{changeDeptModal.faculty.full_name}</strong>
                  </p>
                  <p className="text-muted-foreground">
                    Email: <span className="font-mono text-foreground">{changeDeptModal.faculty.email}</span>
                  </p>
                  <p className="text-muted-foreground">
                    Current Department: <span className="font-semibold text-primary">{changeDeptModal.faculty.department || "Unassigned"}</span>
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
        {resetPasswordModal.open && resetPasswordModal.faculty && (
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
                    Target: <strong className="text-foreground">{resetPasswordModal.faculty.full_name}</strong>
                  </p>
                  <p className="text-muted-foreground">
                    Email: <span className="font-mono text-foreground">{resetPasswordModal.faculty.email}</span>
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
                        placeholder="e.g. Faculty requested password assistance"
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
                        Please copy this temporary password and securely convey it to the faculty member.
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
      </div>
    </DashboardLayout>
  );
}

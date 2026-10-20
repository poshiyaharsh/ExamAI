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
} from "lucide-react";
import { toast } from "sonner";
import { Combobox } from "../components/ui/combobox";
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

  const nextSequence = rows
    .map((facultyItem) => facultyItem.employee_id?.trim() ?? "")
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

      const rows = response.data || response.results || [];
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
          const deptNames = (deptRes.data || []).map((d) => d.department_name).filter(Boolean);
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
          {/* Desktop Table View (>= 768px) with table-fixed & colgroup */}
          <div className="hidden md:block overflow-x-auto min-w-0 max-w-full">
            <table className="w-full table-fixed divide-y divide-border">
              <colgroup>
                <col className="w-[30%]" />
                <col className="w-[16%]" />
                <col className="w-[24%]" />
                <col className="w-[18%]" />
                <col className="w-[12%]" />
                <col className="w-[110px]" />
              </colgroup>
              <thead className="bg-muted/50">
                <tr>
                  <th className="text-left px-5 py-3 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                    Faculty Member
                  </th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                    Employee ID
                  </th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                    Department
                  </th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                    Designation
                  </th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                    Status
                  </th>
                  <th className="text-right px-5 py-3 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
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
                        <td className="px-5 py-3.5 min-w-0">
                          <div className="min-w-0 max-w-full">
                            <p
                              className="font-semibold text-foreground text-sm truncate"
                              title={facultyItem.full_name}
                            >
                              {facultyItem.full_name}
                            </p>
                            <p
                              className="text-xs text-muted-foreground truncate"
                              title={facultyItem.email}
                            >
                              {facultyItem.email}
                            </p>
                          </div>
                        </td>
                        <td
                          className="px-4 py-3.5 text-xs text-foreground font-mono truncate"
                          title={facultyItem.employee_id || "-"}
                        >
                          {facultyItem.employee_id || "-"}
                        </td>
                        <td
                          className="px-4 py-3.5 text-xs text-foreground truncate"
                          title={facultyItem.department || "-"}
                        >
                          {facultyItem.department || "-"}
                        </td>
                        <td
                          className="px-4 py-3.5 text-xs text-muted-foreground truncate"
                          title={facultyItem.designation || "-"}
                        >
                          {facultyItem.designation || "-"}
                        </td>
                        <td className="px-4 py-3.5">
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
                        <td className="px-5 py-3.5 text-right whitespace-nowrap">
                          <div className="inline-flex items-center justify-end gap-1">
                            <button
                              className="p-1.5 rounded hover:bg-muted transition-colors"
                              title="View Details"
                              aria-label={`View ${facultyItem.full_name}`}
                              onClick={() => void handleViewFaculty(facultyItem.id)}
                            >
                              <Eye className="w-4 h-4 text-muted-foreground hover:text-foreground" />
                            </button>
                            <button
                              className="p-1.5 rounded hover:bg-muted transition-colors"
                              title="Edit Faculty"
                              aria-label={`Edit ${facultyItem.full_name}`}
                              onClick={() => void handleEditFaculty(facultyItem.id)}
                            >
                              <Edit className="w-4 h-4 text-muted-foreground hover:text-primary" />
                            </button>
                            <a
                              className="p-1.5 rounded hover:bg-muted transition-colors"
                              title="Send Email"
                              aria-label={`Email ${facultyItem.full_name}`}
                              href={`mailto:${facultyItem.email}`}
                              onClick={(event) => {
                                event.preventDefault();
                                handleSendEmail(facultyItem);
                              }}
                            >
                              <Mail className="w-4 h-4 text-muted-foreground hover:text-blue-600" />
                            </a>
                            <button
                              className="p-1.5 rounded hover:bg-red-50 transition-colors disabled:opacity-60"
                              title="Delete Faculty"
                              aria-label={`Delete ${facultyItem.full_name}`}
                              disabled={deletingId === facultyItem.id}
                              onClick={() => void handleDeleteFaculty(facultyItem)}
                            >
                              <Trash2 className="w-4 h-4 text-muted-foreground hover:text-red-600" />
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

                    <div className="flex items-center justify-end gap-2 pt-1 border-t border-border/40">
                      <button
                        className="p-1.5 rounded-lg border border-border bg-card hover:bg-muted text-muted-foreground hover:text-foreground text-xs flex items-center gap-1"
                        onClick={() => void handleViewFaculty(facultyItem.id)}
                        aria-label={`View ${facultyItem.full_name}`}
                      >
                        <Eye className="w-3.5 h-3.5" /> Details
                      </button>
                      <button
                        className="p-1.5 rounded-lg border border-border bg-card hover:bg-muted text-muted-foreground hover:text-primary text-xs flex items-center gap-1"
                        onClick={() => void handleEditFaculty(facultyItem.id)}
                        aria-label={`Edit ${facultyItem.full_name}`}
                      >
                        <Edit className="w-3.5 h-3.5" /> Edit
                      </button>
                      <button
                        className="p-1.5 rounded-lg border border-red-200 bg-red-50 hover:bg-red-100 text-red-600 text-xs flex items-center gap-1"
                        onClick={() => void handleDeleteFaculty(facultyItem)}
                        aria-label={`Delete ${facultyItem.full_name}`}
                      >
                        <Trash2 className="w-3.5 h-3.5" /> Delete
                      </button>
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

        {/* View Details Modal */}
        {isViewOpen && (
          <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4">
            <div className="w-full max-w-2xl bg-white rounded-xl shadow-xl border border-border">
              <div className="flex items-center justify-between p-6 border-b border-border">
                <h3 className="text-xl font-semibold">Faculty Details</h3>
                <button
                  className="px-3 py-1.5 rounded border border-border hover:bg-muted"
                  onClick={() => setIsViewOpen(false)}
                >
                  Close
                </button>
              </div>
              <div className="p-6">
                {viewLoading ? (
                  <p className="text-muted-foreground">Loading faculty details...</p>
                ) : selectedFaculty ? (
                  <div className="grid sm:grid-cols-2 gap-4 text-sm">
                    <div>
                      <p className="text-muted-foreground">Full Name</p>
                      <p className="font-medium text-foreground">{selectedFaculty.full_name}</p>
                    </div>
                    <div>
                      <p className="text-muted-foreground">Email</p>
                      <p className="font-medium text-foreground">{selectedFaculty.email}</p>
                    </div>
                    <div>
                      <p className="text-muted-foreground">Employee ID</p>
                      <p className="font-medium text-foreground">{selectedFaculty.employee_id || "-"}</p>
                    </div>
                    <div>
                      <p className="text-muted-foreground">Department</p>
                      <p className="font-medium text-foreground">{selectedFaculty.department || "-"}</p>
                    </div>
                    <div>
                      <p className="text-muted-foreground">Designation</p>
                      <p className="font-medium text-foreground">{selectedFaculty.designation || "-"}</p>
                    </div>
                    <div>
                      <p className="text-muted-foreground">Status</p>
                      <p className="font-medium text-foreground">{getFacultyDisplayStatus(selectedFaculty)}</p>
                    </div>
                    <div className="sm:col-span-2">
                      <p className="text-muted-foreground">Institution</p>
                      <p className="font-medium text-foreground">
                        {selectedFaculty.institution?.institution_name || "-"}
                      </p>
                    </div>
                  </div>
                ) : null}
              </div>
            </div>
          </div>
        )}

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
      </div>
    </DashboardLayout>
  );
}

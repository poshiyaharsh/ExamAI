import axios from "axios";
import { useCallback, useEffect, useMemo, useState } from "react";
import { DashboardLayout } from "../components/DashboardLayout";
import { Search, Filter, Eye, Edit, Mail, Trash2, ShieldCheck } from "lucide-react";
import {
  adminFacultyApi,
  type AdminFacultyRow,
  type AdminFacultyUpdatePayload,
} from "../../services/api";
import { authStorage } from "../../services/auth";

type FacultyStatusFilter = "all" | "active" | "inactive";

type FacultyStats = {
  total_faculty: number;
  active_faculty: number;
  inactive_faculty: number;
  total_departments: number;
};

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

export function AdminFaculty() {
  const [searchTerm, setSearchTerm] = useState("");
  const [departmentFilter, setDepartmentFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState<FacultyStatusFilter>("all");
  const [faculty, setFaculty] = useState<AdminFacultyRow[]>([]);
  const [departments, setDepartments] = useState<string[]>([]);
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
  });

  const [deletingId, setDeletingId] = useState<number | null>(null);

  const handleUnauthorized = useCallback(() => {
    authStorage.clearSession();
    window.location.href = "/login";
  }, []);

  const fetchFaculty = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const params: { search?: string; department?: string; status?: string } = {};
      const trimmedSearch = searchTerm.trim();
      if (trimmedSearch) params.search = trimmedSearch;
      if (departmentFilter !== "all") params.department = departmentFilter;
      if (statusFilter !== "all") params.status = statusFilter;

      const response = await adminFacultyApi.getFaculty(params);
      console.debug("Admin faculty API response", response);
      const rows = response.data || [];
      setFaculty(rows);

      const uniqueDepartments = Array.from(
        new Set(
          rows
            .map((facultyItem) => facultyItem.department?.trim())
            .filter((departmentName): departmentName is string => Boolean(departmentName))
        )
      ).sort((a, b) => a.localeCompare(b));
      setDepartments(uniqueDepartments);

      const statistics = response.statistics;
      const totalFaculty = typeof statistics?.total_faculty === "number"
        ? statistics.total_faculty
        : response.total_faculty ?? rows.length;
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
        total_departments: statistics?.total_departments ?? response.total_departments ?? uniqueDepartments.length,
      });
    } catch (requestError) {
      console.error("Admin faculty API error", requestError);
      if (axios.isAxiosError(requestError)) {
        console.error("Admin faculty API error response", requestError.response?.data);
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
      setLoading(false);
    }
  }, [departmentFilter, handleUnauthorized, searchTerm, statusFilter]);

  useEffect(() => {
    const timer = setTimeout(() => void fetchFaculty(), 300);
    return () => clearTimeout(timer);
  }, [fetchFaculty]);

  const inactiveFaculty = useMemo(() => stats.inactive_faculty, [stats.inactive_faculty]);

  const handleViewFaculty = async (facultyId: number) => {
    setIsViewOpen(true);
    setViewLoading(true);
    setSelectedFaculty(null);
    try {
      const response = await adminFacultyApi.getFacultyById(facultyId);
      console.debug("Admin faculty detail API response", response);
      setSelectedFaculty(response.data || null);
    } catch (requestError) {
      if (axios.isAxiosError(requestError) && requestError.response?.status === 401) {
        handleUnauthorized();
      }
    } finally {
      setViewLoading(false);
    }
  };

  const handleEditFaculty = async (facultyId: number) => {
    setIsEditOpen(true);
    setEditLoading(true);
    setEditError("");
    setEditSuccess("");
    setEditFacultyId(facultyId);
    try {
      const response = await adminFacultyApi.getFacultyById(facultyId);
      const details = response.data;
      setEditForm({
        first_name: details.first_name || "",
        last_name: details.last_name || "",
        email: details.email || "",
        employee_id: details.employee_id || "",
        department: details.department || "",
        designation: details.designation || "",
        is_active: typeof details.is_active === "boolean" ? details.is_active : getFacultyDisplayStatus(details).toLowerCase() === "active",
      });
    } catch (requestError) {
      if (axios.isAxiosError(requestError) && requestError.response?.status === 401) {
        handleUnauthorized();
        return;
      }
      setEditError("Unable to fetch faculty details for editing.");
    } finally {
      setEditLoading(false);
    }
  };

  const handleSaveEdit = async () => {
    setEditError("");
    setEditSuccess("");

    if (!editFacultyId) {
      setEditError("Faculty id is missing.");
      return;
    }

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
      console.debug("Admin faculty update API response", response);
      setEditSuccess("Faculty updated successfully.");
      await fetchFaculty();
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
    if (!shouldDelete) {
      return;
    }

    setDeletingId(facultyItem.id);
    setError("");
    try {
      await adminFacultyApi.deleteFaculty(facultyItem.id);
      await fetchFaculty();
      if (selectedFaculty?.id === facultyItem.id) {
        setSelectedFaculty(null);
        setIsViewOpen(false);
      }
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

  return (
    <DashboardLayout userRole="Admin">
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-foreground mb-2">Faculty Management</h1>
            <p className="text-muted-foreground">Manage all faculty members</p>
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="bg-white rounded-xl p-6 shadow-sm border border-border">
            <p className="text-sm text-muted-foreground mb-1">Total Faculty</p>
            <p className="text-3xl font-bold text-foreground">{stats.total_faculty}</p>
          </div>
          <div className="bg-white rounded-xl p-6 shadow-sm border border-border">
            <p className="text-sm text-muted-foreground mb-1">Active Faculty</p>
            <p className="text-3xl font-bold text-green-600">{stats.active_faculty}</p>
          </div>
          <div className="bg-white rounded-xl p-6 shadow-sm border border-border">
            <p className="text-sm text-muted-foreground mb-1">Total Departments</p>
            <p className="text-3xl font-bold text-foreground">{stats.total_departments}</p>
          </div>
          <div className="bg-white rounded-xl p-6 shadow-sm border border-border">
            <p className="text-sm text-muted-foreground mb-1">Inactive Faculty</p>
            <p className="text-3xl font-bold text-foreground">{inactiveFaculty}</p>
          </div>
        </div>

        <div className="bg-white rounded-xl p-6 shadow-sm border border-border">
          <div className="flex flex-col xl:flex-row gap-4">
            <div className="flex-1 relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
              <input
                type="text"
                placeholder="Search by name, email, or employee ID..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full pl-10 pr-4 py-2.5 rounded-lg border border-border focus:outline-none focus:ring-2 focus:ring-primary/20 transition-all"
              />
            </div>
            <div className="flex flex-col sm:flex-row gap-3">
              <div className="flex items-center gap-2">
                <Filter className="w-5 h-5 text-muted-foreground" />
                <select
                  value={departmentFilter}
                  onChange={(e) => setDepartmentFilter(e.target.value)}
                  className="px-4 py-2.5 rounded-lg border border-border focus:outline-none focus:ring-2 focus:ring-primary/20 transition-all"
                >
                  <option value="all">All Departments</option>
                  {departments.map((department) => (
                    <option key={department} value={department}>{department}</option>
                  ))}
                </select>
              </div>
              <div className="flex items-center gap-2">
                <ShieldCheck className="w-5 h-5 text-muted-foreground" />
                <select
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value as FacultyStatusFilter)}
                  className="px-4 py-2.5 rounded-lg border border-border focus:outline-none focus:ring-2 focus:ring-primary/20 transition-all"
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

        <div className="bg-white rounded-xl shadow-sm border border-border overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-muted/50">
                <tr>
                  <th className="text-left px-6 py-3 text-sm font-medium text-muted-foreground">Faculty Name</th>
                  <th className="text-left px-6 py-3 text-sm font-medium text-muted-foreground">Employee ID</th>
                  <th className="text-left px-6 py-3 text-sm font-medium text-muted-foreground">Department</th>
                  <th className="text-left px-6 py-3 text-sm font-medium text-muted-foreground">Designation</th>
                  <th className="text-left px-6 py-3 text-sm font-medium text-muted-foreground">Email</th>
                  <th className="text-left px-6 py-3 text-sm font-medium text-muted-foreground">Status</th>
                  <th className="text-left px-6 py-3 text-sm font-medium text-muted-foreground">Actions</th>
                </tr>
              </thead>
              <tbody>
                {loading ? (
                  <tr>
                    <td colSpan={7} className="px-6 py-12 text-center text-muted-foreground">Loading faculty...</td>
                  </tr>
                ) : faculty.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="px-6 py-12 text-center text-muted-foreground">No faculty found</td>
                  </tr>
                ) : (
                  faculty.map((facultyItem) => {
                    const status = getFacultyDisplayStatus(facultyItem);
                    const isActive = status.toLowerCase() === "active";

                    return (
                      <tr key={facultyItem.id} className="border-t border-border hover:bg-muted/30 transition-colors">
                        <td className="px-6 py-4">
                          <div>
                            <p className="font-medium text-foreground">{facultyItem.full_name}</p>
                            <p className="text-sm text-muted-foreground">{facultyItem.email}</p>
                          </div>
                        </td>
                        <td className="px-6 py-4 text-sm">{facultyItem.employee_id || "-"}</td>
                        <td className="px-6 py-4 text-sm">{facultyItem.department || "-"}</td>
                        <td className="px-6 py-4 text-sm">{facultyItem.designation || "-"}</td>
                        <td className="px-6 py-4 text-sm">{facultyItem.email}</td>
                        <td className="px-6 py-4">
                          <span
                            className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium ${
                              isActive ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-700"
                            }`}
                          >
                            {status}
                          </span>
                        </td>
                        <td className="px-6 py-4">
                          <div className="flex items-center gap-2">
                            <button
                              className="p-1.5 rounded hover:bg-muted transition-colors"
                              title="View Details"
                              onClick={() => void handleViewFaculty(facultyItem.id)}
                            >
                              <Eye className="w-4 h-4 text-muted-foreground" />
                            </button>
                            <button
                              className="p-1.5 rounded hover:bg-muted transition-colors"
                              title="Edit Faculty"
                              onClick={() => void handleEditFaculty(facultyItem.id)}
                            >
                              <Edit className="w-4 h-4 text-muted-foreground" />
                            </button>
                            <a
                              className="p-1.5 rounded hover:bg-muted transition-colors"
                              title="Send Email"
                              href={`mailto:${facultyItem.email}`}
                              onClick={(event) => {
                                event.preventDefault();
                                handleSendEmail(facultyItem);
                              }}
                            >
                              <Mail className="w-4 h-4 text-muted-foreground" />
                            </a>
                            <button
                              className="p-1.5 rounded hover:bg-red-50 transition-colors disabled:opacity-60"
                              title="Delete Faculty"
                              disabled={deletingId === facultyItem.id}
                              onClick={() => void handleDeleteFaculty(facultyItem)}
                            >
                              <Trash2 className="w-4 h-4 text-red-600" />
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
        </div>

        {isViewOpen && (
          <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4">
            <div className="w-full max-w-2xl bg-white rounded-xl shadow-xl border border-border">
              <div className="flex items-center justify-between p-6 border-b border-border">
                <h3 className="text-xl font-semibold">Faculty Details</h3>
                <button className="px-3 py-1.5 rounded border border-border hover:bg-muted" onClick={() => setIsViewOpen(false)}>
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
                      <p className="font-medium text-foreground">{selectedFaculty.institution?.institution_name || "-"}</p>
                    </div>
                  </div>
                ) : null}
              </div>
            </div>
          </div>
        )}

        {isEditOpen && (
          <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4">
            <div className="w-full max-w-2xl bg-white rounded-xl shadow-xl border border-border">
              <div className="flex items-center justify-between p-6 border-b border-border">
                <h3 className="text-xl font-semibold">Edit Faculty</h3>
                <button className="px-3 py-1.5 rounded border border-border hover:bg-muted" onClick={() => setIsEditOpen(false)}>
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
                          onChange={(e) => setEditForm((prev) => ({ ...prev, employee_id: e.target.value }))}
                          className="w-full px-4 py-2.5 rounded-lg border border-border focus:outline-none focus:ring-2 focus:ring-primary/20 transition-all"
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
                          disabled
                          value={selectedFaculty?.institution?.institution_name || ""}
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
      </div>
    </DashboardLayout>
  );
}
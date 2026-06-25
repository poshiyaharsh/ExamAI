import axios from "axios";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router";
import { DashboardLayout } from "../components/DashboardLayout";
import { Search, Filter, Plus, Edit, Trash2, Eye, Mail } from "lucide-react";
import {
  adminStudentsApi,
  departmentsApi,
  type DepartmentOption,
  type AdminStudentCreatePayload,
  type AdminStudentDetails,
  type AdminStudentRow,
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

export function AdminStudents() {
  const navigate = useNavigate();
  const [searchTerm, setSearchTerm] = useState("");
  const [departmentFilter, setDepartmentFilter] = useState("all");
  const [students, setStudents] = useState<AdminStudentRow[]>([]);
  const [departments, setDepartments] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [isViewOpen, setIsViewOpen] = useState(false);
  const [viewLoading, setViewLoading] = useState(false);
  const [selectedStudent, setSelectedStudent] = useState<AdminStudentDetails | null>(null);
  const [viewError, setViewError] = useState("");

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
    department: "",
  });
  const [deletingId, setDeletingId] = useState<number | null>(null);

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
      const params: { search?: string; department?: string } = {};
      const trimmedSearch = searchTerm.trim();
      if (trimmedSearch) {
        params.search = trimmedSearch;
      }
      if (departmentFilter !== "all") {
        params.department = departmentFilter;
      }

      const response = await adminStudentsApi.getStudents(params);
      setStudents(response.data);
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
  }, [departmentFilter, handleUnauthorized, searchTerm]);

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

  const getScoreColor = (score: number) => {
    if (score >= 90) return "text-green-600";
    if (score >= 75) return "text-blue-600";
    if (score >= 60) return "text-yellow-600";
    return "text-red-600";
  };

  const averagePerformance = useMemo(() => {
    const scores = students
      .map((student) => student.average_score)
      .filter((score): score is number => typeof score === "number");

    if (!scores.length) {
      return "0.0";
    }

    const average = scores.reduce((acc, score) => acc + score, 0) / scores.length;
    return average.toFixed(1);
  }, [students]);

  const totalExams = useMemo(
    () => students.reduce((acc, student) => acc + student.number_of_exams, 0),
    [students]
  );

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

  const handleEditStudent = async (studentId: number) => {
    setIsEditOpen(true);
    setEditLoading(true);
    setEditError("");
    setEditSuccess("");
    setEditStudentId(studentId);
    try {
      const response = await adminStudentsApi.getStudentById(studentId);
      const details = response.data;
      setEditForm({
        first_name: details.first_name || "",
        last_name: details.last_name || "",
        email: details.email || "",
        student_id: details.roll_number || "",
        department: details.department || "",
      });
    } catch (requestError) {
      if (axios.isAxiosError(requestError)) {
        if (requestError.response?.status === 401) {
          handleUnauthorized();
          return;
        }
        const extracted = extractApiErrorMessage(requestError.response?.data);
        setEditError(extracted ?? "Unable to fetch student details for editing.");
      } else {
        setEditError("Unable to fetch student details for editing.");
      }
    } finally {
      setEditLoading(false);
    }
  };

  const handleSaveEdit = async () => {
    setEditError("");
    setEditSuccess("");

    if (!editStudentId) {
      setEditError("Student id is missing.");
      return;
    }

    const payload = {
      first_name: editForm.first_name.trim(),
      last_name: editForm.last_name.trim(),
      email: editForm.email.trim(),
    };

    if (!payload.first_name || !payload.last_name || !payload.email) {
      setEditError("All fields are required.");
      return;
    }

    setSavingEdit(true);
    try {
      await adminStudentsApi.updateStudent(editStudentId, payload);
      setEditSuccess("Student updated successfully.");
      await Promise.all([fetchStudents(), fetchDepartments()]);
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
    const shouldDelete = window.confirm(`Delete ${student.full_name}? This action cannot be undone.`);
    if (!shouldDelete) {
      return;
    }

    setDeletingId(student.id);
    setError("");
    try {
      await adminStudentsApi.deleteStudent(student.id);
      await Promise.all([fetchStudents(), fetchDepartments()]);
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

    if (!payload.first_name || !payload.last_name || !payload.email || !createForm.department_id || !payload.password || !createForm.confirm_password) {
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

  return (
    <DashboardLayout userRole="Admin">
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-foreground mb-2">Student Management</h1>
            <p className="text-muted-foreground">Manage all enrolled students</p>
          </div>
          <button
            className="px-6 py-3 rounded-lg bg-gradient-to-r from-primary to-secondary text-white hover:opacity-90 transition-opacity flex items-center gap-2"
            onClick={() => {
              setIsCreateOpen(true);
              setCreateError("");
              setCreateSuccess("");
              void fetchCreateDepartments();
            }}
          >
            <Plus className="w-5 h-5" />
            Add Student
          </button>
        </div>

        {/* Stats */}
        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="bg-white rounded-xl p-6 shadow-sm border border-border">
            <p className="text-sm text-muted-foreground mb-1">Total Students</p>
            <p className="text-3xl font-bold text-foreground">{students.length}</p>
          </div>
          <div className="bg-white rounded-xl p-6 shadow-sm border border-border">
            <p className="text-sm text-muted-foreground mb-1">Active Students</p>
            <p className="text-3xl font-bold text-green-600">{students.length}</p>
          </div>
          <div className="bg-white rounded-xl p-6 shadow-sm border border-border">
            <p className="text-sm text-muted-foreground mb-1">Avg Performance</p>
            <p className="text-3xl font-bold text-foreground">{averagePerformance}%</p>
          </div>
          <div className="bg-white rounded-xl p-6 shadow-sm border border-border">
            <p className="text-sm text-muted-foreground mb-1">Total Exams</p>
            <p className="text-3xl font-bold text-foreground">{totalExams}</p>
          </div>
        </div>

        {/* Search and Filters */}
        <div className="bg-white rounded-xl p-6 shadow-sm border border-border">
          <div className="flex flex-col sm:flex-row gap-4">
            <div className="flex-1 relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
              <input
                type="text"
                placeholder="Search by name, email, or roll number..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full pl-10 pr-4 py-2.5 rounded-lg border border-border focus:outline-none focus:ring-2 focus:ring-primary/20 transition-all"
              />
            </div>
            <div className="flex items-center gap-2">
              <Filter className="w-5 h-5 text-muted-foreground" />
              <select
                value={departmentFilter}
                onChange={(e) => setDepartmentFilter(e.target.value)}
                className="px-4 py-2.5 rounded-lg border border-border focus:outline-none focus:ring-2 focus:ring-primary/20 transition-all"
              >
                <option value="all">All Departments</option>
                {departments.map((dept) => (
                  <option key={dept} value={dept}>{dept}</option>
                ))}
              </select>
            </div>
          </div>
          {error && <p className="mt-3 text-sm text-destructive">{error}</p>}
        </div>

        {/* Students Table */}
        <div className="bg-white rounded-xl shadow-sm border border-border overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-muted/50">
                <tr>
                  <th className="text-left px-6 py-3 text-sm font-medium text-muted-foreground">Student</th>
                  <th className="text-left px-6 py-3 text-sm font-medium text-muted-foreground">Roll No</th>
                  <th className="text-left px-6 py-3 text-sm font-medium text-muted-foreground">Department</th>
                  <th className="text-left px-6 py-3 text-sm font-medium text-muted-foreground">Year</th>
                  <th className="text-left px-6 py-3 text-sm font-medium text-muted-foreground">Exams</th>
                  <th className="text-left px-6 py-3 text-sm font-medium text-muted-foreground">Avg Score</th>
                  <th className="text-left px-6 py-3 text-sm font-medium text-muted-foreground">Actions</th>
                </tr>
              </thead>
              <tbody>
                {loading ? (
                  <tr>
                    <td colSpan={7} className="px-6 py-12 text-center text-muted-foreground">
                      Loading students...
                    </td>
                  </tr>
                ) : (
                  students.map((student) => (
                    <tr key={student.id} className="border-t border-border hover:bg-muted/30 transition-colors">
                      <td className="px-6 py-4">
                        <div>
                          <p className="font-medium text-foreground">{student.full_name}</p>
                          <p className="text-sm text-muted-foreground">{student.email}</p>
                        </div>
                      </td>
                      <td className="px-6 py-4 text-sm">{student.roll_number || "-"}</td>
                      <td className="px-6 py-4 text-sm">{student.department || "-"}</td>
                      <td className="px-6 py-4 text-sm">{student.year || "-"}</td>
                      <td className="px-6 py-4 text-sm">{student.number_of_exams}</td>
                      <td className="px-6 py-4">
                        {typeof student.average_score === "number" ? (
                          <span className={`font-semibold ${getScoreColor(student.average_score)}`}>
                            {student.average_score.toFixed(1)}%
                          </span>
                        ) : (
                          <span className="text-muted-foreground">-</span>
                        )}
                      </td>
                      <td className="px-6 py-4">
                        <div className="flex items-center gap-2">
                          <button
                            className="p-1.5 rounded hover:bg-muted transition-colors"
                            title="View Profile"
                            onClick={() => void handleViewStudent(student.id)}
                          >
                            <Eye className="w-4 h-4 text-muted-foreground" />
                          </button>
                          <button
                            className="p-1.5 rounded hover:bg-muted transition-colors"
                            title="Edit"
                            onClick={() => void handleEditStudent(student.id)}
                          >
                            <Edit className="w-4 h-4 text-muted-foreground" />
                          </button>
                          <a
                            className="p-1.5 rounded hover:bg-muted transition-colors"
                            title="Email"
                            href={`mailto:${student.email}`}
                          >
                            <Mail className="w-4 h-4 text-muted-foreground" />
                          </a>
                          <button
                            className="p-1.5 rounded hover:bg-red-50 transition-colors disabled:opacity-60"
                            title="Delete"
                            onClick={() => void handleDeleteStudent(student)}
                            disabled={deletingId === student.id}
                          >
                            <Trash2 className="w-4 h-4 text-red-600" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>

        {!loading && students.length === 0 && (
          <div className="text-center py-12">
            <Users className="w-16 h-16 text-muted-foreground mx-auto mb-4" />
            <p className="text-lg font-medium text-foreground mb-2">No Students Found</p>
            <p className="text-muted-foreground">Try adjusting your search or filters</p>
          </div>
        )}

        {isViewOpen && (
          <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4">
            <div className="w-full max-w-2xl bg-white rounded-xl shadow-xl border border-border">
              <div className="flex items-center justify-between p-6 border-b border-border">
                <h3 className="text-xl font-semibold">Student Details</h3>
                <button
                  className="px-3 py-1.5 rounded border border-border hover:bg-muted"
                  onClick={() => setIsViewOpen(false)}
                >
                  Close
                </button>
              </div>
              <div className="p-6">
                {viewLoading ? (
                  <p className="text-muted-foreground">Loading student details...</p>
                ) : viewError ? (
                  <p className="text-destructive text-sm">{viewError}</p>
                ) : selectedStudent ? (
                  <div className="grid sm:grid-cols-2 gap-4 text-sm">
                    <div>
                      <p className="text-muted-foreground">Full Name</p>
                      <p className="font-medium text-foreground">{selectedStudent.full_name}</p>
                    </div>
                    <div>
                      <p className="text-muted-foreground">Email</p>
                      <p className="font-medium text-foreground">{selectedStudent.email}</p>
                    </div>
                    <div>
                      <p className="text-muted-foreground">Roll Number / Student ID</p>
                      <p className="font-medium text-foreground">{selectedStudent.roll_number || "-"}</p>
                    </div>
                    <div>
                      <p className="text-muted-foreground">Department</p>
                      <p className="font-medium text-foreground">{selectedStudent.department || "-"}</p>
                    </div>
                    <div>
                      <p className="text-muted-foreground">Year</p>
                      <p className="font-medium text-foreground">{selectedStudent.year || "-"}</p>
                    </div>
                    <div>
                      <p className="text-muted-foreground">Number of Exams</p>
                      <p className="font-medium text-foreground">{selectedStudent.number_of_exams}</p>
                    </div>
                    <div>
                      <p className="text-muted-foreground">Average Score</p>
                      <p className="font-medium text-foreground">
                        {typeof selectedStudent.average_score === "number"
                          ? `${selectedStudent.average_score.toFixed(1)}%`
                          : "-"}
                      </p>
                    </div>
                    <div>
                      <p className="text-muted-foreground">Institution</p>
                      <p className="font-medium text-foreground">
                        {selectedStudent.institution?.institution_name || "-"}
                      </p>
                    </div>
                  </div>
                ) : null}
              </div>
            </div>
          </div>
        )}

        {isCreateOpen && (
          <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4">
            <div className="w-full max-w-2xl bg-white rounded-xl shadow-xl border border-border">
              <div className="flex items-center justify-between p-6 border-b border-border">
                <h3 className="text-xl font-semibold">Add Student</h3>
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
                      disabled={creatingStudent}
                      className="w-full px-4 py-2.5 rounded-lg border border-border focus:outline-none focus:ring-2 focus:ring-primary/20 transition-all"
                    />
                  </div>
                  <div>
                    <label className="block text-sm text-muted-foreground mb-2">Last Name</label>
                    <input
                      type="text"
                      value={createForm.last_name}
                      onChange={(e) => setCreateForm((prev) => ({ ...prev, last_name: e.target.value }))}
                      disabled={creatingStudent}
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
                      disabled={creatingStudent}
                      className="w-full px-4 py-2.5 rounded-lg border border-border focus:outline-none focus:ring-2 focus:ring-primary/20 transition-all"
                    />
                  </div>
                  <div>
                    <label className="block text-sm text-muted-foreground mb-2">Department</label>
                    <select
                      value={createForm.department_id}
                      onChange={(e) => setCreateForm((prev) => ({ ...prev, department_id: e.target.value }))}
                      disabled={creatingStudent || createDepartmentsLoading || createDepartments.length === 0}
                      className="w-full px-4 py-2.5 rounded-lg border border-border focus:outline-none focus:ring-2 focus:ring-primary/20 transition-all"
                    >
                      {createDepartmentsLoading ? (
                        <option value="">Loading departments...</option>
                      ) : createDepartments.length === 0 ? (
                        <option value="">No departments available</option>
                      ) : (
                        <option value="">Select Department</option>
                      )}
                      {createDepartments.map((department) => (
                        <option key={department.id} value={department.id}>
                          {department.department_name}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>

                <div className="grid sm:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm text-muted-foreground mb-2">Password</label>
                    <input
                      type="password"
                      value={createForm.password}
                      onChange={(e) => setCreateForm((prev) => ({ ...prev, password: e.target.value }))}
                      disabled={creatingStudent}
                      className="w-full px-4 py-2.5 rounded-lg border border-border focus:outline-none focus:ring-2 focus:ring-primary/20 transition-all"
                    />
                  </div>
                  <div>
                    <label className="block text-sm text-muted-foreground mb-2">Confirm Password</label>
                    <input
                      type="password"
                      value={createForm.confirm_password}
                      onChange={(e) => setCreateForm((prev) => ({ ...prev, confirm_password: e.target.value }))}
                      disabled={creatingStudent}
                      className="w-full px-4 py-2.5 rounded-lg border border-border focus:outline-none focus:ring-2 focus:ring-primary/20 transition-all"
                    />
                  </div>
                </div>

                {createError && <p className="text-sm text-destructive">{createError}</p>}
                {createSuccess && <p className="text-sm text-green-600">{createSuccess}</p>}

                <div className="pt-2">
                  <button
                    onClick={() => void handleCreateStudent()}
                    disabled={creatingStudent}
                    className="px-6 py-2.5 rounded-lg bg-gradient-to-r from-primary to-secondary text-white font-semibold hover:shadow-lg transition-all disabled:opacity-60 disabled:cursor-not-allowed"
                  >
                    {creatingStudent ? "Creating..." : "Create Student"}
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        {isEditOpen && (
          <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4">
            <div className="w-full max-w-2xl bg-white rounded-xl shadow-xl border border-border">
              <div className="flex items-center justify-between p-6 border-b border-border">
                <h3 className="text-xl font-semibold">Edit Student</h3>
                <button
                  className="px-3 py-1.5 rounded border border-border hover:bg-muted"
                  onClick={() => {
                    setIsEditOpen(false);
                    setEditError("");
                    setEditSuccess("");
                  }}
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
                        <label className="block text-sm text-muted-foreground mb-2">Roll Number / Student ID</label>
                        <input
                          type="text"
                          value={editForm.student_id}
                          disabled
                          className="w-full px-4 py-2.5 rounded-lg border border-border bg-muted text-muted-foreground cursor-not-allowed"
                        />
                      </div>
                    </div>

                    <div>
                      <label className="block text-sm text-muted-foreground mb-2">Department</label>
                      <input
                        type="text"
                        value={editForm.department}
                        disabled
                        className="w-full px-4 py-2.5 rounded-lg border border-border bg-muted text-muted-foreground cursor-not-allowed"
                      />
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

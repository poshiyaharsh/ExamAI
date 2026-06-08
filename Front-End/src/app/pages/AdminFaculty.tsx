import axios from "axios";
import { useCallback, useEffect, useMemo, useState } from "react";
import { DashboardLayout } from "../components/DashboardLayout";
import { LayoutDashboard, FileText, Users, Database, Settings, Search, Filter, Eye } from "lucide-react";
import { adminFacultyApi } from "../../services/api";
import { authStorage } from "../../services/auth";

const menuItems = [
  { icon: LayoutDashboard, label: "Dashboard", path: "/admin" },
  { icon: FileText, label: "Exams", path: "/admin/exams" },
  { icon: Users, label: "Faculty", path: "/admin/faculty" },
  { icon: Database, label: "Question Bank", path: "/admin/question-bank" },
  { icon: Settings, label: "Settings", path: "/admin/settings" },
];

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

export function AdminFaculty() {
  const [searchTerm, setSearchTerm] = useState("");
  const [departmentFilter, setDepartmentFilter] = useState("all");
  const [faculty, setFaculty] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [selected, setSelected] = useState<any | null>(null);
  const [viewLoading, setViewLoading] = useState(false);

  const handleUnauthorized = useCallback((navigateFn?: () => void) => {
    authStorage.clearSession();
    if (navigateFn) navigateFn();
  }, []);

  const fetchFaculty = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const params: { search?: string; department?: string } = {};
      if (searchTerm.trim()) params.search = searchTerm.trim();
      if (departmentFilter !== "all") params.department = departmentFilter;
      const response = await adminFacultyApi.getFaculty(params);
      setFaculty(response.data || []);
    } catch (err) {
      if (axios.isAxiosError(err)) {
        if (err.response?.status === 401) {
          handleUnauthorized();
          return;
        }
        const extracted = extractApiErrorMessage(err.response?.data);
        setError(extracted ?? "Unable to fetch faculty.");
      } else {
        setError("Unable to fetch faculty.");
      }
    } finally {
      setLoading(false);
    }
  }, [departmentFilter, handleUnauthorized, searchTerm]);

  useEffect(() => {
    const timer = setTimeout(() => void fetchFaculty(), 300);
    return () => clearTimeout(timer);
  }, [fetchFaculty]);

  const totalFaculty = useMemo(() => faculty.length, [faculty]);

  const handleView = async (id: number) => {
    setViewLoading(true);
    setSelected(null);
    try {
      const resp = await adminFacultyApi.getFacultyById(id);
      setSelected(resp.data || null);
    } catch (err) {
      // ignore for now
    } finally {
      setViewLoading(false);
    }
  };

  return (
    <DashboardLayout menuItems={menuItems} userRole="Admin">
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-foreground mb-2">Faculty Management</h1>
            <p className="text-muted-foreground">View and manage faculty members</p>
          </div>
        </div>

        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="bg-white rounded-xl p-6 shadow-sm border border-border">
            <p className="text-sm text-muted-foreground mb-1">Total Faculty</p>
            <p className="text-3xl font-bold text-foreground">{totalFaculty}</p>
          </div>
        </div>

        <div className="bg-white rounded-xl p-6 shadow-sm border border-border">
          <div className="flex flex-col sm:flex-row gap-4">
            <div className="flex-1 relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
              <input
                type="text"
                placeholder="Search by name or email..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full pl-10 pr-4 py-2.5 rounded-lg border border-border focus:outline-none focus:ring-2 focus:ring-primary/20 transition-all"
              />
            </div>
            <div className="flex items-center gap-2">
              <Filter className="w-5 h-5 text-muted-foreground" />
              <select value={departmentFilter} onChange={(e) => setDepartmentFilter(e.target.value)} className="px-4 py-2.5 rounded-lg border border-border">
                <option value="all">All Departments</option>
              </select>
            </div>
          </div>
          {error && <p className="mt-3 text-sm text-destructive">{error}</p>}
        </div>

        <div className="bg-white rounded-xl shadow-sm border border-border overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-muted/50">
                <tr>
                  <th className="text-left px-6 py-3 text-sm font-medium text-muted-foreground">Faculty</th>
                  <th className="text-left px-6 py-3 text-sm font-medium text-muted-foreground">Employee ID</th>
                  <th className="text-left px-6 py-3 text-sm font-medium text-muted-foreground">Department</th>
                  <th className="text-left px-6 py-3 text-sm font-medium text-muted-foreground">Email</th>
                  <th className="text-left px-6 py-3 text-sm font-medium text-muted-foreground">Actions</th>
                </tr>
              </thead>
              <tbody>
                {loading ? (
                  <tr>
                    <td colSpan={5} className="px-6 py-12 text-center text-muted-foreground">Loading faculty...</td>
                  </tr>
                ) : (
                  faculty.map((f) => (
                    <tr key={f.id} className="border-t border-border hover:bg-muted/30 transition-colors">
                      <td className="px-6 py-4">
                        <div>
                          <p className="font-medium text-foreground">{f.full_name}</p>
                          <p className="text-sm text-muted-foreground">{f.email}</p>
                        </div>
                      </td>
                      <td className="px-6 py-4 text-sm">{f.employee_id || '-'}</td>
                      <td className="px-6 py-4 text-sm">{f.department || '-'}</td>
                      <td className="px-6 py-4 text-sm">{f.email}</td>
                      <td className="px-6 py-4">
                        <div className="flex items-center gap-2">
                          <button className="p-1.5 rounded hover:bg-muted transition-colors" title="View Profile" onClick={() => void handleView(f.id)}>
                            <Eye className="w-4 h-4 text-muted-foreground" />
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

        {selected && (
          <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4">
            <div className="w-full max-w-2xl bg-white rounded-xl shadow-xl border border-border">
              <div className="flex items-center justify-between p-6 border-b border-border">
                <h3 className="text-xl font-semibold">Faculty Details</h3>
                <button className="px-3 py-1.5 rounded border border-border hover:bg-muted" onClick={() => setSelected(null)}>Close</button>
              </div>
              <div className="p-6">
                {viewLoading ? (
                  <p className="text-muted-foreground">Loading...</p>
                ) : (
                  <div className="grid sm:grid-cols-2 gap-4 text-sm">
                    <div>
                      <p className="text-muted-foreground">Full Name</p>
                      <p className="font-medium text-foreground">{selected.full_name}</p>
                    </div>
                    <div>
                      <p className="text-muted-foreground">Email</p>
                      <p className="font-medium text-foreground">{selected.email}</p>
                    </div>
                    <div>
                      <p className="text-muted-foreground">Employee ID</p>
                      <p className="font-medium text-foreground">{selected.employee_id || '-'}</p>
                    </div>
                    <div>
                      <p className="text-muted-foreground">Department</p>
                      <p className="font-medium text-foreground">{selected.department || '-'}</p>
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

import { useState } from "react";
import { DashboardLayout } from "../components/DashboardLayout";
import { LayoutDashboard, FileText, Users, Database, Settings, Search, Filter, Plus, Edit, Trash2, Eye, Mail } from "lucide-react";

const menuItems = [
  { icon: LayoutDashboard, label: "Dashboard", path: "/admin" },
  { icon: FileText, label: "Exams", path: "/admin/exams" },
  { icon: Users, label: "Students", path: "/admin/students" },
  { icon: Database, label: "Question Bank", path: "/question-bank" },
  { icon: Settings, label: "Settings", path: "/admin/settings" }
];

const studentsData = [
  {
    id: "STU-001",
    name: "Alice Johnson",
    email: "alice.j@university.edu",
    rollNo: "2024-CS-001",
    department: "Computer Science",
    year: "3rd Year",
    examsTaken: 12,
    avgScore: 88.5,
    status: "Active"
  },
  {
    id: "STU-002",
    name: "Bob Smith",
    email: "bob.s@university.edu",
    rollNo: "2024-CS-002",
    department: "Computer Science",
    year: "3rd Year",
    examsTaken: 11,
    avgScore: 76.2,
    status: "Active"
  },
  {
    id: "STU-003",
    name: "Carol Davis",
    email: "carol.d@university.edu",
    rollNo: "2024-MATH-015",
    department: "Mathematics",
    year: "2nd Year",
    examsTaken: 10,
    avgScore: 92.3,
    status: "Active"
  },
  {
    id: "STU-004",
    name: "David Lee",
    email: "david.l@university.edu",
    rollNo: "2024-PHY-008",
    department: "Physics",
    year: "4th Year",
    examsTaken: 15,
    avgScore: 81.7,
    status: "Active"
  },
  {
    id: "STU-005",
    name: "Emma Wilson",
    email: "emma.w@university.edu",
    rollNo: "2024-CS-045",
    department: "Computer Science",
    year: "1st Year",
    examsTaken: 6,
    avgScore: 85.9,
    status: "Active"
  }
];

export function AdminStudents() {
  const [searchTerm, setSearchTerm] = useState("");
  const [departmentFilter, setDepartmentFilter] = useState("all");

  const filteredStudents = studentsData.filter(student => {
    const matchesSearch = student.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
                          student.email.toLowerCase().includes(searchTerm.toLowerCase()) ||
                          student.rollNo.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesDepartment = departmentFilter === "all" || student.department === departmentFilter;
    return matchesSearch && matchesDepartment;
  });

  const departments = Array.from(new Set(studentsData.map(s => s.department)));

  const getScoreColor = (score: number) => {
    if (score >= 90) return "text-green-600";
    if (score >= 75) return "text-blue-600";
    if (score >= 60) return "text-yellow-600";
    return "text-red-600";
  };

  return (
    <DashboardLayout menuItems={menuItems} userRole="Admin">
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-foreground mb-2">Student Management</h1>
            <p className="text-muted-foreground">Manage all enrolled students</p>
          </div>
          <button className="px-6 py-3 rounded-lg bg-gradient-to-r from-primary to-secondary text-white hover:opacity-90 transition-opacity flex items-center gap-2">
            <Plus className="w-5 h-5" />
            Add Student
          </button>
        </div>

        {/* Stats */}
        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="bg-white rounded-xl p-6 shadow-sm border border-border">
            <p className="text-sm text-muted-foreground mb-1">Total Students</p>
            <p className="text-3xl font-bold text-foreground">{studentsData.length}</p>
          </div>
          <div className="bg-white rounded-xl p-6 shadow-sm border border-border">
            <p className="text-sm text-muted-foreground mb-1">Active Students</p>
            <p className="text-3xl font-bold text-green-600">
              {studentsData.filter(s => s.status === "Active").length}
            </p>
          </div>
          <div className="bg-white rounded-xl p-6 shadow-sm border border-border">
            <p className="text-sm text-muted-foreground mb-1">Avg Performance</p>
            <p className="text-3xl font-bold text-foreground">
              {(studentsData.reduce((acc, s) => acc + s.avgScore, 0) / studentsData.length).toFixed(1)}%
            </p>
          </div>
          <div className="bg-white rounded-xl p-6 shadow-sm border border-border">
            <p className="text-sm text-muted-foreground mb-1">Total Exams</p>
            <p className="text-3xl font-bold text-foreground">
              {studentsData.reduce((acc, s) => acc + s.examsTaken, 0)}
            </p>
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
                {filteredStudents.map((student) => (
                  <tr key={student.id} className="border-t border-border hover:bg-muted/30 transition-colors">
                    <td className="px-6 py-4">
                      <div>
                        <p className="font-medium text-foreground">{student.name}</p>
                        <p className="text-sm text-muted-foreground">{student.email}</p>
                      </div>
                    </td>
                    <td className="px-6 py-4 text-sm">{student.rollNo}</td>
                    <td className="px-6 py-4 text-sm">{student.department}</td>
                    <td className="px-6 py-4 text-sm">{student.year}</td>
                    <td className="px-6 py-4 text-sm">{student.examsTaken}</td>
                    <td className="px-6 py-4">
                      <span className={`font-semibold ${getScoreColor(student.avgScore)}`}>
                        {student.avgScore}%
                      </span>
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-2">
                        <button className="p-1.5 rounded hover:bg-muted transition-colors" title="View Profile">
                          <Eye className="w-4 h-4 text-muted-foreground" />
                        </button>
                        <button className="p-1.5 rounded hover:bg-muted transition-colors" title="Edit">
                          <Edit className="w-4 h-4 text-muted-foreground" />
                        </button>
                        <button className="p-1.5 rounded hover:bg-muted transition-colors" title="Email">
                          <Mail className="w-4 h-4 text-muted-foreground" />
                        </button>
                        <button className="p-1.5 rounded hover:bg-red-50 transition-colors" title="Delete">
                          <Trash2 className="w-4 h-4 text-red-600" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {filteredStudents.length === 0 && (
          <div className="text-center py-12">
            <Users className="w-16 h-16 text-muted-foreground mx-auto mb-4" />
            <p className="text-lg font-medium text-foreground mb-2">No students found</p>
            <p className="text-muted-foreground">Try adjusting your search or filters</p>
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}

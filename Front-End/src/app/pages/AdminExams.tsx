import { useState } from "react";
import { DashboardLayout } from "../components/DashboardLayout";
import { FileText, Search, Filter, Plus, Edit, Trash2, Eye } from "lucide-react";

const examsData = [
  {
    id: "exam-001",
    title: "Midterm - Computer Science",
    course: "CS101",
    date: "2026-03-15",
    duration: 120,
    totalMarks: 100,
    students: 156,
    status: "Scheduled",
    faculty: "Dr. Sarah Johnson"
  },
  {
    id: "exam-002",
    title: "Final - Mathematics",
    course: "MATH201",
    date: "2026-03-10",
    duration: 180,
    totalMarks: 150,
    students: 142,
    status: "Active",
    faculty: "Dr. Michael Chen"
  },
  {
    id: "exam-003",
    title: "Quiz - Physics",
    course: "PHY101",
    date: "2026-03-08",
    duration: 60,
    totalMarks: 50,
    students: 98,
    status: "Completed",
    faculty: "Dr. Emily Wilson"
  },
  {
    id: "exam-004",
    title: "Midterm - Chemistry",
    course: "CHEM101",
    date: "2026-03-05",
    duration: 90,
    totalMarks: 75,
    students: 134,
    status: "Completed",
    faculty: "Dr. Robert Davis"
  },
  {
    id: "exam-005",
    title: "Final - Data Structures",
    course: "CS201",
    date: "2026-03-20",
    duration: 150,
    totalMarks: 120,
    students: 89,
    status: "Scheduled",
    faculty: "Dr. Sarah Johnson"
  }
];

export function AdminExams() {
  const [searchTerm, setSearchTerm] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");

  const filteredExams = examsData.filter(exam => {
    const matchesSearch = exam.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
                          exam.course.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesStatus = statusFilter === "all" || exam.status.toLowerCase() === statusFilter;
    return matchesSearch && matchesStatus;
  });

  const getStatusColor = (status: string) => {
    switch (status.toLowerCase()) {
      case "scheduled": return "bg-blue-100 text-blue-700";
      case "active": return "bg-green-100 text-green-700";
      case "completed": return "bg-gray-100 text-gray-700";
      default: return "bg-gray-100 text-gray-700";
    }
  };

  return (
    <DashboardLayout userRole="Admin">
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-foreground mb-2">Exam Management</h1>
            <p className="text-muted-foreground">Create and manage all institution exams</p>
          </div>
          <button className="px-6 py-3 rounded-lg bg-gradient-to-r from-primary to-secondary text-white hover:opacity-90 transition-opacity flex items-center gap-2">
            <Plus className="w-5 h-5" />
            Create Exam
          </button>
        </div>

        {/* Stats */}
        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="bg-white rounded-xl p-6 shadow-sm border border-border">
            <p className="text-sm text-muted-foreground mb-1">Total Exams</p>
            <p className="text-3xl font-bold text-foreground">{examsData.length}</p>
          </div>
          <div className="bg-white rounded-xl p-6 shadow-sm border border-border">
            <p className="text-sm text-muted-foreground mb-1">Scheduled</p>
            <p className="text-3xl font-bold text-blue-600">
              {examsData.filter(e => e.status === "Scheduled").length}
            </p>
          </div>
          <div className="bg-white rounded-xl p-6 shadow-sm border border-border">
            <p className="text-sm text-muted-foreground mb-1">Active</p>
            <p className="text-3xl font-bold text-green-600">
              {examsData.filter(e => e.status === "Active").length}
            </p>
          </div>
          <div className="bg-white rounded-xl p-6 shadow-sm border border-border">
            <p className="text-sm text-muted-foreground mb-1">Completed</p>
            <p className="text-3xl font-bold text-gray-600">
              {examsData.filter(e => e.status === "Completed").length}
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
                placeholder="Search exams or courses..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full pl-10 pr-4 py-2.5 rounded-lg border border-border focus:outline-none focus:ring-2 focus:ring-primary/20 transition-all"
              />
            </div>
            <div className="flex items-center gap-2">
              <Filter className="w-5 h-5 text-muted-foreground" />
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="px-4 py-2.5 rounded-lg border border-border focus:outline-none focus:ring-2 focus:ring-primary/20 transition-all"
              >
                <option value="all">All Status</option>
                <option value="scheduled">Scheduled</option>
                <option value="active">Active</option>
                <option value="completed">Completed</option>
              </select>
            </div>
          </div>
        </div>

        {/* Exams Table */}
        <div className="bg-white rounded-xl shadow-sm border border-border overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-muted/50">
                <tr>
                  <th className="text-left px-6 py-3 text-sm font-medium text-muted-foreground">Exam Title</th>
                  <th className="text-left px-6 py-3 text-sm font-medium text-muted-foreground">Course</th>
                  <th className="text-left px-6 py-3 text-sm font-medium text-muted-foreground">Date</th>
                  <th className="text-left px-6 py-3 text-sm font-medium text-muted-foreground">Duration</th>
                  <th className="text-left px-6 py-3 text-sm font-medium text-muted-foreground">Students</th>
                  <th className="text-left px-6 py-3 text-sm font-medium text-muted-foreground">Status</th>
                  <th className="text-left px-6 py-3 text-sm font-medium text-muted-foreground">Actions</th>
                </tr>
              </thead>
              <tbody>
                {filteredExams.map((exam) => (
                  <tr key={exam.id} className="border-t border-border hover:bg-muted/30 transition-colors">
                    <td className="px-6 py-4">
                      <div>
                        <p className="font-medium text-foreground">{exam.title}</p>
                        <p className="text-sm text-muted-foreground">{exam.faculty}</p>
                      </div>
                    </td>
                    <td className="px-6 py-4 text-sm">{exam.course}</td>
                    <td className="px-6 py-4 text-sm">{exam.date}</td>
                    <td className="px-6 py-4 text-sm">{exam.duration} min</td>
                    <td className="px-6 py-4 text-sm">{exam.students}</td>
                    <td className="px-6 py-4">
                      <span className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium ${getStatusColor(exam.status)}`}>
                        {exam.status}
                      </span>
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-2">
                        <button className="p-1.5 rounded hover:bg-muted transition-colors" title="View">
                          <Eye className="w-4 h-4 text-muted-foreground" />
                        </button>
                        <button className="p-1.5 rounded hover:bg-muted transition-colors" title="Edit">
                          <Edit className="w-4 h-4 text-muted-foreground" />
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

        {filteredExams.length === 0 && (
          <div className="text-center py-12">
            <FileText className="w-16 h-16 text-muted-foreground mx-auto mb-4" />
            <p className="text-lg font-medium text-foreground mb-2">No exams found</p>
            <p className="text-muted-foreground">Try adjusting your search or filters</p>
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}

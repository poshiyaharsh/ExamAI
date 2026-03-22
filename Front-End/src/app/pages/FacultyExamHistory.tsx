import { useState } from "react";
import { DashboardLayout } from "../components/DashboardLayout";
import { LayoutDashboard, FileText, History, Settings, Search, Download, Eye, Trash2, Filter } from "lucide-react";

const menuItems = [
  { icon: LayoutDashboard, label: "Dashboard", path: "/faculty" },
  { icon: FileText, label: "Generate Paper", path: "/faculty/generate" },
  { icon: History, label: "Exam History", path: "/faculty/history" },
  { icon: Settings, label: "Settings", path: "/faculty/settings" }
];

const examHistory = [
  { 
    id: 1,
    title: "Data Structures Midterm", 
    date: "2026-02-28", 
    questions: 25, 
    difficulty: "Medium",
    totalMarks: 100,
    duration: 90,
    students: 45,
    avgScore: 72
  },
  { 
    id: 2,
    title: "Algorithms Final", 
    date: "2026-02-15", 
    questions: 30, 
    difficulty: "Hard",
    totalMarks: 150,
    duration: 120,
    students: 42,
    avgScore: 65
  },
  { 
    id: 3,
    title: "Database Quiz", 
    date: "2026-02-10", 
    questions: 15, 
    difficulty: "Easy",
    totalMarks: 50,
    duration: 45,
    students: 48,
    avgScore: 85
  },
  { 
    id: 4,
    title: "Networks Test", 
    date: "2026-01-25", 
    questions: 20, 
    difficulty: "Medium",
    totalMarks: 75,
    duration: 60,
    students: 44,
    avgScore: 68
  },
  { 
    id: 5,
    title: "Operating Systems Quiz", 
    date: "2026-01-15", 
    questions: 18, 
    difficulty: "Medium",
    totalMarks: 60,
    duration: 50,
    students: 46,
    avgScore: 71
  }
];

export function FacultyExamHistory() {
  const [searchTerm, setSearchTerm] = useState("");
  const [filterDifficulty, setFilterDifficulty] = useState("all");

  const filteredExams = examHistory.filter(exam => {
    const matchesSearch = exam.title.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesDifficulty = filterDifficulty === "all" || exam.difficulty.toLowerCase() === filterDifficulty;
    return matchesSearch && matchesDifficulty;
  });

  const getDifficultyColor = (difficulty: string) => {
    switch (difficulty.toLowerCase()) {
      case "easy": return "bg-green-100 text-green-700";
      case "medium": return "bg-yellow-100 text-yellow-700";
      case "hard": return "bg-red-100 text-red-700";
      default: return "bg-gray-100 text-gray-700";
    }
  };

  return (
    <DashboardLayout menuItems={menuItems} userRole="Faculty">
      <div className="space-y-6">
        {/* Header */}
        <div>
          <h1 className="text-3xl font-bold text-foreground mb-2">Exam History</h1>
          <p className="text-muted-foreground">View and manage all your created exams</p>
        </div>

        {/* Stats */}
        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="bg-white rounded-xl p-6 shadow-sm border border-border">
            <p className="text-sm text-muted-foreground mb-1">Total Exams</p>
            <p className="text-3xl font-bold text-foreground">{examHistory.length}</p>
          </div>
          <div className="bg-white rounded-xl p-6 shadow-sm border border-border">
            <p className="text-sm text-muted-foreground mb-1">Total Questions</p>
            <p className="text-3xl font-bold text-foreground">
              {examHistory.reduce((acc, exam) => acc + exam.questions, 0)}
            </p>
          </div>
          <div className="bg-white rounded-xl p-6 shadow-sm border border-border">
            <p className="text-sm text-muted-foreground mb-1">Total Students</p>
            <p className="text-3xl font-bold text-foreground">
              {examHistory.reduce((acc, exam) => acc + exam.students, 0)}
            </p>
          </div>
          <div className="bg-white rounded-xl p-6 shadow-sm border border-border">
            <p className="text-sm text-muted-foreground mb-1">Avg Score</p>
            <p className="text-3xl font-bold text-foreground">
              {Math.round(examHistory.reduce((acc, exam) => acc + exam.avgScore, 0) / examHistory.length)}%
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
                placeholder="Search exams..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full pl-10 pr-4 py-2.5 rounded-lg border border-border focus:outline-none focus:ring-2 focus:ring-primary/20 transition-all"
              />
            </div>
            <div className="flex items-center gap-2">
              <Filter className="w-5 h-5 text-muted-foreground" />
              <select
                value={filterDifficulty}
                onChange={(e) => setFilterDifficulty(e.target.value)}
                className="px-4 py-2.5 rounded-lg border border-border focus:outline-none focus:ring-2 focus:ring-primary/20 transition-all"
              >
                <option value="all">All Difficulties</option>
                <option value="easy">Easy</option>
                <option value="medium">Medium</option>
                <option value="hard">Hard</option>
              </select>
            </div>
          </div>
        </div>

        {/* Exam List */}
        <div className="space-y-4">
          {filteredExams.map((exam) => (
            <div key={exam.id} className="bg-white rounded-xl p-6 shadow-sm border border-border hover:shadow-md transition-shadow">
              <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
                <div className="flex-1">
                  <div className="flex items-center gap-3 mb-2">
                    <h3 className="font-semibold text-lg">{exam.title}</h3>
                    <span className={`px-2.5 py-0.5 rounded-full text-xs font-medium ${getDifficultyColor(exam.difficulty)}`}>
                      {exam.difficulty}
                    </span>
                  </div>
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-sm text-muted-foreground">
                    <div>
                      <span className="block font-medium text-foreground">{exam.questions}</span>
                      <span>Questions</span>
                    </div>
                    <div>
                      <span className="block font-medium text-foreground">{exam.totalMarks}</span>
                      <span>Marks</span>
                    </div>
                    <div>
                      <span className="block font-medium text-foreground">{exam.duration} min</span>
                      <span>Duration</span>
                    </div>
                    <div>
                      <span className="block font-medium text-foreground">{exam.students}</span>
                      <span>Students</span>
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <button className="px-4 py-2 rounded-lg border border-border hover:bg-muted transition-colors flex items-center gap-2">
                    <Eye className="w-4 h-4" />
                    View
                  </button>
                  <button className="px-4 py-2 rounded-lg border border-border hover:bg-muted transition-colors flex items-center gap-2">
                    <Download className="w-4 h-4" />
                    Export
                  </button>
                  <button className="p-2 rounded-lg text-red-600 hover:bg-red-50 transition-colors">
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
              <div className="mt-4 pt-4 border-t border-border flex items-center justify-between text-sm">
                <span className="text-muted-foreground">Created: {exam.date}</span>
                <span className="text-muted-foreground">Average Score: <span className="font-medium text-foreground">{exam.avgScore}%</span></span>
              </div>
            </div>
          ))}
        </div>

        {filteredExams.length === 0 && (
          <div className="text-center py-12">
            <History className="w-16 h-16 text-muted-foreground mx-auto mb-4" />
            <p className="text-lg font-medium text-foreground mb-2">No exams found</p>
            <p className="text-muted-foreground">Try adjusting your search or filters</p>
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}

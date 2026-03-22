import { useState } from "react";
import { Link } from "react-router";
import { DashboardLayout } from "../components/DashboardLayout";
import { LayoutDashboard, FileText, TrendingUp, Settings, Clock, Calendar, CheckCircle, XCircle, Search, Filter } from "lucide-react";

const menuItems = [
  { icon: LayoutDashboard, label: "Dashboard", path: "/student" },
  { icon: FileText, label: "Exams", path: "/student/exams" },
  { icon: TrendingUp, label: "Performance", path: "/student/performance" },
  { icon: Settings, label: "Settings", path: "/student/settings" }
];

const availableExams = [
  { 
    id: 1, 
    title: "Data Structures Midterm", 
    subject: "Computer Science", 
    duration: "90 min", 
    date: "2026-03-05", 
    time: "10:00 AM",
    totalQuestions: 50,
    totalMarks: 100,
    status: "Available" 
  },
  { 
    id: 2, 
    title: "Calculus Quiz", 
    subject: "Mathematics", 
    duration: "45 min", 
    date: "2026-03-06", 
    time: "2:00 PM",
    totalQuestions: 30,
    totalMarks: 50,
    status: "Available" 
  },
  { 
    id: 3, 
    title: "Quantum Mechanics Test", 
    subject: "Physics", 
    duration: "60 min", 
    date: "2026-03-07", 
    time: "11:00 AM",
    totalQuestions: 40,
    totalMarks: 75,
    status: "Available" 
  }
];

const upcomingExams = [
  { 
    id: 4,
    title: "Physics Final", 
    subject: "Physics", 
    date: "2026-03-10", 
    time: "10:00 AM",
    duration: "120 min",
    totalQuestions: 80,
    totalMarks: 150,
    status: "Scheduled" 
  },
  { 
    id: 5,
    title: "Chemistry Lab Test", 
    subject: "Chemistry", 
    date: "2026-03-12", 
    time: "2:00 PM",
    duration: "60 min",
    totalQuestions: 50,
    totalMarks: 100,
    status: "Scheduled" 
  },
  { 
    id: 6,
    title: "English Literature", 
    subject: "English", 
    date: "2026-03-15", 
    time: "11:00 AM",
    duration: "90 min",
    totalQuestions: 40,
    totalMarks: 80,
    status: "Scheduled" 
  }
];

const completedExams = [
  { 
    id: 101,
    title: "Algorithms Midterm", 
    subject: "Computer Science",
    completedDate: "2026-02-20",
    score: 85,
    maxScore: 100,
    grade: "A",
    status: "Completed" 
  },
  { 
    id: 102,
    title: "Database Systems", 
    subject: "Computer Science",
    completedDate: "2026-02-15",
    score: 78,
    maxScore: 100,
    grade: "B+",
    status: "Completed" 
  },
  { 
    id: 103,
    title: "Operating Systems", 
    subject: "Computer Science",
    completedDate: "2026-02-10",
    score: 92,
    maxScore: 100,
    grade: "A+",
    status: "Completed" 
  },
  { 
    id: 104,
    title: "Linear Algebra Quiz", 
    subject: "Mathematics",
    completedDate: "2026-02-05",
    score: 88,
    maxScore: 100,
    grade: "A",
    status: "Completed" 
  }
];

export function StudentExams() {
  const [activeTab, setActiveTab] = useState<"available" | "upcoming" | "completed">("available");
  const [searchQuery, setSearchQuery] = useState("");

  return (
    <DashboardLayout menuItems={menuItems} userRole="Student">
      <div className="space-y-6">
        {/* Header */}
        <div>
          <h1 className="text-3xl font-bold text-foreground mb-2">My Exams</h1>
          <p className="text-muted-foreground">View and manage all your exams</p>
        </div>

        {/* Search and Filter */}
        <div className="flex flex-col sm:flex-row gap-4">
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
            <input
              type="text"
              placeholder="Search exams..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-10 pr-4 py-2 rounded-lg border border-border bg-input-background focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </div>
          <button className="flex items-center gap-2 px-4 py-2 rounded-lg border border-border bg-white hover:bg-muted/30 transition-colors">
            <Filter className="w-5 h-5" />
            <span>Filter</span>
          </button>
        </div>

        {/* Tabs */}
        <div className="bg-white rounded-xl shadow-sm border border-border">
          <div className="border-b border-border">
            <div className="flex">
              <button
                onClick={() => setActiveTab("available")}
                className={`flex-1 px-6 py-4 font-medium transition-colors ${
                  activeTab === "available"
                    ? "text-primary border-b-2 border-primary"
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                Available ({availableExams.length})
              </button>
              <button
                onClick={() => setActiveTab("upcoming")}
                className={`flex-1 px-6 py-4 font-medium transition-colors ${
                  activeTab === "upcoming"
                    ? "text-primary border-b-2 border-primary"
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                Upcoming ({upcomingExams.length})
              </button>
              <button
                onClick={() => setActiveTab("completed")}
                className={`flex-1 px-6 py-4 font-medium transition-colors ${
                  activeTab === "completed"
                    ? "text-primary border-b-2 border-primary"
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                Completed ({completedExams.length})
              </button>
            </div>
          </div>

          <div className="p-6">
            {/* Available Exams */}
            {activeTab === "available" && (
              <div className="space-y-4">
                {availableExams.length === 0 ? (
                  <div className="text-center py-12">
                    <FileText className="w-16 h-16 text-muted-foreground mx-auto mb-4" />
                    <p className="text-muted-foreground">No available exams at the moment</p>
                  </div>
                ) : (
                  availableExams.map((exam) => (
                    <div key={exam.id} className="p-6 rounded-lg border border-border hover:border-primary transition-colors">
                      <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
                        <div className="flex-1">
                          <div className="flex items-start gap-3 mb-3">
                            <div className="w-12 h-12 rounded-lg bg-gradient-to-br from-primary to-secondary flex items-center justify-center flex-shrink-0">
                              <FileText className="w-6 h-6 text-white" />
                            </div>
                            <div>
                              <h4 className="font-semibold text-lg text-foreground mb-1">{exam.title}</h4>
                              <p className="text-sm text-muted-foreground">{exam.subject}</p>
                            </div>
                          </div>
                          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 ml-15">
                            <div className="flex items-center gap-2 text-sm text-muted-foreground">
                              <Calendar className="w-4 h-4" />
                              <span>{exam.date}</span>
                            </div>
                            <div className="flex items-center gap-2 text-sm text-muted-foreground">
                              <Clock className="w-4 h-4" />
                              <span>{exam.time}</span>
                            </div>
                            <div className="text-sm text-muted-foreground">
                              Duration: {exam.duration}
                            </div>
                            <div className="text-sm text-muted-foreground">
                              {exam.totalQuestions} Questions
                            </div>
                          </div>
                        </div>
                        <div className="flex flex-col sm:flex-row gap-3">
                          <Link to={`/exam/${exam.id}`}>
                            <button className="w-full sm:w-auto px-6 py-2 rounded-lg bg-gradient-to-r from-primary to-secondary text-white hover:opacity-90 transition-opacity">
                              Start Exam
                            </button>
                          </Link>
                        </div>
                      </div>
                    </div>
                  ))
                )}
              </div>
            )}

            {/* Upcoming Exams */}
            {activeTab === "upcoming" && (
              <div className="space-y-4">
                {upcomingExams.length === 0 ? (
                  <div className="text-center py-12">
                    <Calendar className="w-16 h-16 text-muted-foreground mx-auto mb-4" />
                    <p className="text-muted-foreground">No upcoming exams scheduled</p>
                  </div>
                ) : (
                  upcomingExams.map((exam) => (
                    <div key={exam.id} className="p-6 rounded-lg border border-border">
                      <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
                        <div className="flex-1">
                          <div className="flex items-start gap-3 mb-3">
                            <div className="w-12 h-12 rounded-lg bg-gradient-to-br from-secondary to-primary flex items-center justify-center flex-shrink-0">
                              <Calendar className="w-6 h-6 text-white" />
                            </div>
                            <div>
                              <h4 className="font-semibold text-lg text-foreground mb-1">{exam.title}</h4>
                              <p className="text-sm text-muted-foreground">{exam.subject}</p>
                            </div>
                          </div>
                          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 ml-15">
                            <div className="flex items-center gap-2 text-sm text-muted-foreground">
                              <Calendar className="w-4 h-4" />
                              <span>{exam.date}</span>
                            </div>
                            <div className="flex items-center gap-2 text-sm text-muted-foreground">
                              <Clock className="w-4 h-4" />
                              <span>{exam.time}</span>
                            </div>
                            <div className="text-sm text-muted-foreground">
                              Duration: {exam.duration}
                            </div>
                            <div className="text-sm text-muted-foreground">
                              {exam.totalQuestions} Questions
                            </div>
                          </div>
                        </div>
                        <div className="flex items-center">
                          <span className="inline-flex items-center px-3 py-1 rounded-full text-sm bg-blue-100 text-blue-700">
                            Scheduled
                          </span>
                        </div>
                      </div>
                    </div>
                  ))
                )}
              </div>
            )}

            {/* Completed Exams */}
            {activeTab === "completed" && (
              <div className="space-y-4">
                {completedExams.length === 0 ? (
                  <div className="text-center py-12">
                    <CheckCircle className="w-16 h-16 text-muted-foreground mx-auto mb-4" />
                    <p className="text-muted-foreground">No completed exams yet</p>
                  </div>
                ) : (
                  completedExams.map((exam) => (
                    <div key={exam.id} className="p-6 rounded-lg border border-border">
                      <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
                        <div className="flex-1">
                          <div className="flex items-start gap-3 mb-3">
                            <div className="w-12 h-12 rounded-lg bg-gradient-to-br from-green-500 to-green-600 flex items-center justify-center flex-shrink-0">
                              <CheckCircle className="w-6 h-6 text-white" />
                            </div>
                            <div>
                              <h4 className="font-semibold text-lg text-foreground mb-1">{exam.title}</h4>
                              <p className="text-sm text-muted-foreground">{exam.subject}</p>
                            </div>
                          </div>
                          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 ml-15">
                            <div className="text-sm text-muted-foreground">
                              Completed: {exam.completedDate}
                            </div>
                            <div className="text-sm font-medium text-foreground">
                              Score: {exam.score}/{exam.maxScore}
                            </div>
                            <div>
                              <span className="inline-flex items-center px-2 py-1 rounded-full text-sm bg-green-100 text-green-700">
                                Grade: {exam.grade}
                              </span>
                            </div>
                          </div>
                        </div>
                        <div className="flex flex-col sm:flex-row gap-3">
                          <Link to={`/result/${exam.id}`}>
                            <button className="w-full sm:w-auto px-6 py-2 rounded-lg border border-border bg-white hover:bg-muted/30 transition-colors">
                              View Result
                            </button>
                          </Link>
                        </div>
                      </div>
                    </div>
                  ))
                )}
              </div>
            )}
          </div>
        </div>

        {/* Quick Stats */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="bg-white rounded-xl p-6 shadow-sm border border-border">
            <div className="flex items-center gap-3 mb-2">
              <div className="w-10 h-10 rounded-lg bg-blue-100 flex items-center justify-center">
                <FileText className="w-5 h-5 text-blue-600" />
              </div>
              <div className="text-sm text-muted-foreground">Total Exams</div>
            </div>
            <div className="text-2xl font-bold text-foreground">
              {availableExams.length + upcomingExams.length + completedExams.length}
            </div>
          </div>

          <div className="bg-white rounded-xl p-6 shadow-sm border border-border">
            <div className="flex items-center gap-3 mb-2">
              <div className="w-10 h-10 rounded-lg bg-green-100 flex items-center justify-center">
                <CheckCircle className="w-5 h-5 text-green-600" />
              </div>
              <div className="text-sm text-muted-foreground">Completion Rate</div>
            </div>
            <div className="text-2xl font-bold text-foreground">
              {Math.round((completedExams.length / (availableExams.length + upcomingExams.length + completedExams.length)) * 100)}%
            </div>
          </div>

          <div className="bg-white rounded-xl p-6 shadow-sm border border-border">
            <div className="flex items-center gap-3 mb-2">
              <div className="w-10 h-10 rounded-lg bg-purple-100 flex items-center justify-center">
                <TrendingUp className="w-5 h-5 text-purple-600" />
              </div>
              <div className="text-sm text-muted-foreground">Average Score</div>
            </div>
            <div className="text-2xl font-bold text-foreground">
              {Math.round(completedExams.reduce((acc, exam) => acc + (exam.score / exam.maxScore) * 100, 0) / completedExams.length)}%
            </div>
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
}

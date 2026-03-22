import { Link } from "react-router";
import { DashboardLayout } from "../components/DashboardLayout";
import { LayoutDashboard, FileText, Clock, TrendingUp, Settings } from "lucide-react";
import { PieChart, Pie, Cell, ResponsiveContainer, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip } from "recharts";

const menuItems = [
  { icon: LayoutDashboard, label: "Dashboard", path: "/student" },
  { icon: FileText, label: "Exams", path: "/student/exams" },
  { icon: TrendingUp, label: "Performance", path: "/student/performance" },
  { icon: Settings, label: "Settings", path: "/student/settings" }
];

const availableExams = [
  { id: 1, title: "Data Structures Midterm", subject: "Computer Science", duration: "90 min", date: "2026-03-05", status: "Available" },
  { id: 2, title: "Calculus Quiz", subject: "Mathematics", duration: "45 min", date: "2026-03-06", status: "Available" }
];

const upcomingExams = [
  { title: "Physics Final", subject: "Physics", date: "2026-03-10", time: "10:00 AM" },
  { title: "Chemistry Lab Test", subject: "Chemistry", date: "2026-03-12", time: "2:00 PM" },
  { title: "English Literature", subject: "English", date: "2026-03-15", time: "11:00 AM" }
];

const previousResults = [
  { exam: "Algorithms Midterm", score: 85, maxScore: 100, date: "2026-02-20", grade: "A" },
  { exam: "Database Systems", score: 78, maxScore: 100, date: "2026-02-15", grade: "B+" },
  { exam: "Operating Systems", score: 92, maxScore: 100, date: "2026-02-10", grade: "A+" },
  { exam: "Computer Networks", score: 88, maxScore: 100, date: "2026-02-05", grade: "A" }
];

const performanceData = [
  { month: "Jan", score: 75 },
  { month: "Feb", score: 80 },
  { month: "Mar", score: 85 }
];

const subjectPerformance = [
  { id: "cs", subject: "Computer Science", value: 85 },
  { id: "math", subject: "Mathematics", value: 78 },
  { id: "physics", subject: "Physics", value: 82 },
  { id: "chem", subject: "Chemistry", value: 88 }
];

const COLORS = ["#4F46E5", "#6366F1", "#8B5CF6", "#A78BFA"];

export function StudentDashboard() {
  return (
    <DashboardLayout menuItems={menuItems} userRole="Student">
      <div className="space-y-6">
        {/* Header */}
        <div>
          <h1 className="text-3xl font-bold text-foreground mb-2">Student Dashboard</h1>
          <p className="text-muted-foreground">Welcome back! Here's your exam overview</p>
        </div>

        {/* Quick Stats */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
          <div className="bg-white rounded-xl p-6 shadow-sm border border-border">
            <div className="flex items-center justify-between mb-4">
              <div className="w-12 h-12 rounded-lg bg-gradient-to-br from-primary to-secondary flex items-center justify-center">
                <FileText className="w-6 h-6 text-white" />
              </div>
            </div>
            <div className="text-3xl font-bold text-foreground mb-1">2</div>
            <div className="text-sm text-muted-foreground">Available Exams</div>
          </div>

          <div className="bg-white rounded-xl p-6 shadow-sm border border-border">
            <div className="flex items-center justify-between mb-4">
              <div className="w-12 h-12 rounded-lg bg-gradient-to-br from-secondary to-primary flex items-center justify-center">
                <Clock className="w-6 h-6 text-white" />
              </div>
            </div>
            <div className="text-3xl font-bold text-foreground mb-1">3</div>
            <div className="text-sm text-muted-foreground">Upcoming Exams</div>
          </div>

          <div className="bg-white rounded-xl p-6 shadow-sm border border-border">
            <div className="flex items-center justify-between mb-4">
              <div className="w-12 h-12 rounded-lg bg-gradient-to-br from-primary to-secondary flex items-center justify-center">
                <TrendingUp className="w-6 h-6 text-white" />
              </div>
            </div>
            <div className="text-3xl font-bold text-foreground mb-1">85.8%</div>
            <div className="text-sm text-muted-foreground">Average Score</div>
          </div>

          <div className="bg-white rounded-xl p-6 shadow-sm border border-border">
            <div className="flex items-center justify-between mb-4">
              <div className="w-12 h-12 rounded-lg bg-gradient-to-br from-secondary to-primary flex items-center justify-center">
                <FileText className="w-6 h-6 text-white" />
              </div>
            </div>
            <div className="text-3xl font-bold text-foreground mb-1">12</div>
            <div className="text-sm text-muted-foreground">Completed Exams</div>
          </div>
        </div>

        {/* Available Exams */}
        <div className="bg-white rounded-xl shadow-sm border border-border">
          <div className="p-6 border-b border-border">
            <h3 className="font-semibold">Available Exams</h3>
          </div>
          <div className="p-6 space-y-4">
            {availableExams.map((exam) => (
              <div key={exam.id} className="flex items-center justify-between p-4 rounded-lg border border-border hover:border-primary transition-colors">
                <div>
                  <h4 className="font-semibold text-foreground mb-1">{exam.title}</h4>
                  <div className="flex gap-4 text-sm text-muted-foreground">
                    <span>{exam.subject}</span>
                    <span>•</span>
                    <span>{exam.duration}</span>
                    <span>•</span>
                    <span>{exam.date}</span>
                  </div>
                </div>
                <Link to={`/exam/${exam.id}`}>
                  <button className="px-6 py-2 rounded-lg bg-gradient-to-r from-primary to-secondary text-white hover:opacity-90 transition-opacity">
                    Start Exam
                  </button>
                </Link>
              </div>
            ))}
          </div>
        </div>

        {/* Upcoming Exams */}
        <div className="bg-white rounded-xl shadow-sm border border-border">
          <div className="p-6 border-b border-border">
            <h3 className="font-semibold">Upcoming Exams</h3>
          </div>
          <div className="divide-y divide-border">
            {upcomingExams.map((exam, index) => (
              <div key={index} className="p-6 hover:bg-muted/30 transition-colors">
                <div className="flex items-center justify-between">
                  <div>
                    <h4 className="font-semibold text-foreground mb-1">{exam.title}</h4>
                    <p className="text-sm text-muted-foreground">{exam.subject}</p>
                  </div>
                  <div className="text-right">
                    <p className="text-sm text-foreground">{exam.date}</p>
                    <p className="text-sm text-muted-foreground">{exam.time}</p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Performance Overview */}
        <div className="grid lg:grid-cols-2 gap-6">
          <div className="bg-white rounded-xl p-6 shadow-sm border border-border">
            <h3 className="font-semibold mb-6">Performance Trend</h3>
            <ResponsiveContainer width="100%" height={250}>
              <LineChart data={performanceData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
                <XAxis dataKey="month" stroke="#6B7280" />
                <YAxis stroke="#6B7280" />
                <Tooltip />
                <Line type="monotone" dataKey="score" stroke="#4F46E5" strokeWidth={2} />
              </LineChart>
            </ResponsiveContainer>
          </div>

          <div className="bg-white rounded-xl p-6 shadow-sm border border-border">
            <h3 className="font-semibold mb-6">Subject Performance</h3>
            <div className="flex items-center justify-center">
              <ResponsiveContainer width="100%" height={250}>
                <PieChart>
                  <Pie
                    data={subjectPerformance}
                    cx="50%"
                    cy="50%"
                    labelLine={false}
                    label={(entry) => `${entry.subject.split(" ")[0]}`}
                    outerRadius={80}
                    fill="#8884d8"
                    dataKey="value"
                  >
                    {subjectPerformance.map((entry) => (
                      <Cell key={`cell-${entry.id}`} fill={COLORS[subjectPerformance.indexOf(entry) % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>

        {/* Previous Results */}
        <div className="bg-white rounded-xl shadow-sm border border-border">
          <div className="p-6 border-b border-border">
            <h3 className="font-semibold">Previous Results</h3>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-muted/50">
                <tr>
                  <th className="text-left px-6 py-3 text-sm text-muted-foreground">Exam</th>
                  <th className="text-left px-6 py-3 text-sm text-muted-foreground">Score</th>
                  <th className="text-left px-6 py-3 text-sm text-muted-foreground">Date</th>
                  <th className="text-left px-6 py-3 text-sm text-muted-foreground">Grade</th>
                  <th className="text-left px-6 py-3 text-sm text-muted-foreground">Actions</th>
                </tr>
              </thead>
              <tbody>
                {previousResults.map((result, index) => (
                  <tr key={index} className="border-t border-border hover:bg-muted/30 transition-colors">
                    <td className="px-6 py-4">{result.exam}</td>
                    <td className="px-6 py-4">{result.score}/{result.maxScore}</td>
                    <td className="px-6 py-4">{result.date}</td>
                    <td className="px-6 py-4">
                      <span className="inline-flex items-center px-2 py-1 rounded-full text-xs bg-green-100 text-green-700">
                        {result.grade}
                      </span>
                    </td>
                    <td className="px-6 py-4">
                      <Link to={`/result/${index + 1}`}>
                        <button className="text-primary hover:text-secondary text-sm">View Details</button>
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
}

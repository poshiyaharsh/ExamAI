import { DashboardLayout } from "../components/DashboardLayout";
import { FileText, Users, Database, Plus } from "lucide-react";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, AreaChart, Area } from "recharts";

const performanceData = [
  { month: "Jan", score: 75 },
  { month: "Feb", score: 78 },
  { month: "Mar", score: 82 },
  { month: "Apr", score: 85 },
  { month: "May", score: 88 },
  { month: "Jun", score: 90 }
];

const recentExams = [
  { id: "exam-001", title: "Midterm - Computer Science", date: "2026-03-01", students: 156, status: "Completed" },
  { id: "exam-002", title: "Final - Mathematics", date: "2026-03-02", students: 142, status: "Active" },
  { id: "exam-003", title: "Quiz - Physics", date: "2026-03-03", students: 98, status: "Scheduled" },
  { id: "exam-004", title: "Midterm - Chemistry", date: "2026-02-28", students: 134, status: "Completed" }
];

export function AdminDashboard() {
  return (
    <DashboardLayout userRole="Admin">
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-foreground mb-2">Admin Dashboard</h1>
            <p className="text-muted-foreground">Overview of your institution's exam performance</p>
          </div>
          <button className="px-6 py-3 rounded-lg bg-gradient-to-r from-primary to-secondary text-white hover:opacity-90 transition-opacity flex items-center gap-2">
            <Plus className="w-5 h-5" />
            Create Exam
          </button>
        </div>

        {/* Stats Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          <div className="bg-white rounded-xl p-6 shadow-sm border border-border">
            <div className="flex items-center justify-between mb-4">
              <div className="w-12 h-12 rounded-lg bg-gradient-to-br from-primary to-secondary flex items-center justify-center">
                <FileText className="w-6 h-6 text-white" />
              </div>
              <span className="text-xs px-2 py-1 rounded-full bg-green-100 text-green-700">
                +12%
              </span>
            </div>
            <div className="text-3xl font-bold text-foreground mb-1">247</div>
            <div className="text-sm text-muted-foreground">Total Exams</div>
          </div>

          <div className="bg-white rounded-xl p-6 shadow-sm border border-border">
            <div className="flex items-center justify-between mb-4">
              <div className="w-12 h-12 rounded-lg bg-gradient-to-br from-secondary to-primary flex items-center justify-center">
                <Users className="w-6 h-6 text-white" />
              </div>
              <span className="text-xs px-2 py-1 rounded-full bg-green-100 text-green-700">
                +8%
              </span>
            </div>
            <div className="text-3xl font-bold text-foreground mb-1">3,456</div>
            <div className="text-sm text-muted-foreground">Total Students</div>
          </div>

          <div className="bg-white rounded-xl p-6 shadow-sm border border-border">
            <div className="flex items-center justify-between mb-4">
              <div className="w-12 h-12 rounded-lg bg-gradient-to-br from-primary to-secondary flex items-center justify-center">
                <BarChart className="w-6 h-6 text-white" />
              </div>
              <span className="text-xs px-2 py-1 rounded-full bg-green-100 text-green-700">
                +5%
              </span>
            </div>
            <div className="text-3xl font-bold text-foreground mb-1">85.4%</div>
            <div className="text-sm text-muted-foreground">Avg Performance</div>
          </div>

          <div className="bg-white rounded-xl p-6 shadow-sm border border-border">
            <div className="flex items-center justify-between mb-4">
              <div className="w-12 h-12 rounded-lg bg-gradient-to-br from-secondary to-primary flex items-center justify-center">
                <Database className="w-6 h-6 text-white" />
              </div>
              <span className="text-xs px-2 py-1 rounded-full bg-accent text-accent-foreground">
                Updated
              </span>
            </div>
            <div className="text-3xl font-bold text-foreground mb-1">12,847</div>
            <div className="text-sm text-muted-foreground">Question Bank</div>
          </div>
        </div>

        {/* Performance Graph */}
        <div className="bg-white rounded-xl p-6 shadow-sm border border-border">
          <div className="mb-6">
            <h3 className="font-semibold text-foreground mb-1">Performance Overview</h3>
            <p className="text-sm text-muted-foreground">Average student performance over time</p>
          </div>
          <ResponsiveContainer width="100%" height={350}>
            <AreaChart data={performanceData}>
              <defs>
                <linearGradient id="colorScore" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#4F46E5" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#4F46E5" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
              <XAxis dataKey="month" stroke="#6B7280" />
              <YAxis stroke="#6B7280" />
              <Tooltip />
              <Area
                type="monotone"
                dataKey="score"
                stroke="#4F46E5"
                strokeWidth={2}
                fillOpacity={1}
                fill="url(#colorScore)"
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        {/* Recent Exams */}
        <div className="bg-white rounded-xl shadow-sm border border-border">
          <div className="p-6 border-b border-border">
            <h3 className="font-semibold">Recent Exams</h3>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-muted/50">
                <tr>
                  <th className="text-left px-6 py-3 text-sm text-muted-foreground">Exam Title</th>
                  <th className="text-left px-6 py-3 text-sm text-muted-foreground">Date</th>
                  <th className="text-left px-6 py-3 text-sm text-muted-foreground">Students</th>
                  <th className="text-left px-6 py-3 text-sm text-muted-foreground">Status</th>
                  <th className="text-left px-6 py-3 text-sm text-muted-foreground">Actions</th>
                </tr>
              </thead>
              <tbody>
                {recentExams.map((exam) => (
                  <tr key={exam.id} className="border-t border-border hover:bg-muted/30 transition-colors">
                    <td className="px-6 py-4">{exam.title}</td>
                    <td className="px-6 py-4">{exam.date}</td>
                    <td className="px-6 py-4">{exam.students}</td>
                    <td className="px-6 py-4">
                      <span
                        className={`inline-flex items-center px-2 py-1 rounded-full text-xs ${
                          exam.status === "Completed"
                            ? "bg-green-100 text-green-700"
                            : exam.status === "Active"
                            ? "bg-blue-100 text-blue-700"
                            : "bg-gray-100 text-gray-700"
                        }`}
                      >
                        {exam.status}
                      </span>
                    </td>
                    <td className="px-6 py-4">
                      <button className="text-primary hover:text-secondary text-sm">View Details</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Quick Actions */}
        <div className="grid md:grid-cols-3 gap-6">
          <div className="bg-white rounded-xl p-6 shadow-sm border border-border hover:shadow-md transition-shadow cursor-pointer">
            <div className="w-12 h-12 rounded-lg bg-accent flex items-center justify-center mb-4">
              <Plus className="w-6 h-6 text-accent-foreground" />
            </div>
            <h4 className="font-semibold mb-2">Create New Exam</h4>
            <p className="text-sm text-muted-foreground">Set up a new examination for your students</p>
          </div>

          <div className="bg-white rounded-xl p-6 shadow-sm border border-border hover:shadow-md transition-shadow cursor-pointer">
            <div className="w-12 h-12 rounded-lg bg-accent flex items-center justify-center mb-4">
              <Database className="w-6 h-6 text-accent-foreground" />
            </div>
            <h4 className="font-semibold mb-2">Manage Questions</h4>
            <p className="text-sm text-muted-foreground">Add or edit questions in the question bank</p>
          </div>

          <div className="bg-white rounded-xl p-6 shadow-sm border border-border hover:shadow-md transition-shadow cursor-pointer">
            <div className="w-12 h-12 rounded-lg bg-accent flex items-center justify-center mb-4">
              <Users className="w-6 h-6 text-accent-foreground" />
            </div>
            <h4 className="font-semibold mb-2">View Reports</h4>
            <p className="text-sm text-muted-foreground">Access detailed student performance reports</p>
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
}

import { DashboardLayout } from "../components/DashboardLayout";
import { LayoutDashboard, FileText, TrendingUp, Settings } from "lucide-react";
import { PieChart, Pie, Cell, ResponsiveContainer, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, BarChart, Bar } from "recharts";

const menuItems = [
  { icon: LayoutDashboard, label: "Dashboard", path: "/student" },
  { icon: FileText, label: "Exams", path: "/student/exams" },
  { icon: TrendingUp, label: "Performance", path: "/student/performance" },
  { icon: Settings, label: "Settings", path: "/student/settings" }
];

const performanceData = [
  { month: "Sep", score: 68 },
  { month: "Oct", score: 72 },
  { month: "Nov", score: 75 },
  { month: "Dec", score: 78 },
  { month: "Jan", score: 80 },
  { month: "Feb", score: 85 },
  { month: "Mar", score: 88 }
];

const subjectPerformance = [
  { subject: "Computer Science", score: 85, maxScore: 100 },
  { subject: "Mathematics", score: 78, maxScore: 100 },
  { subject: "Physics", score: 82, maxScore: 100 },
  { subject: "Chemistry", score: 88, maxScore: 100 },
  { subject: "English", score: 90, maxScore: 100 }
];

const topicAnalysis = [
  { topic: "Data Structures", strength: 92, attempts: 15 },
  { topic: "Algorithms", strength: 85, attempts: 12 },
  { topic: "Calculus", strength: 78, attempts: 10 },
  { topic: "Quantum Physics", strength: 70, attempts: 8 },
  { topic: "Organic Chemistry", strength: 88, attempts: 14 }
];

const COLORS = ["#4F46E5", "#6366F1", "#8B5CF6", "#A78BFA", "#C4B5FD"];

export function StudentPerformance() {
  return (
    <DashboardLayout menuItems={menuItems} userRole="Student">
      <div className="space-y-6">
        {/* Header */}
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold text-foreground mb-1">Performance Analytics</h1>
          <p className="text-xs sm:text-sm text-muted-foreground">Track your academic progress and insights</p>
        </div>

        {/* Overall Stats */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 sm:gap-6">
          <div className="bg-white rounded-xl p-5 shadow-sm border border-border hover:shadow-md transition-all">
            <div className="text-xs sm:text-sm text-muted-foreground font-medium mb-1">Overall Average</div>
            <div className="text-2xl sm:text-3xl font-bold text-foreground">84.6%</div>
            <div className="text-xs text-emerald-600 font-medium mt-1">↑ 5.2% from last month</div>
          </div>

          <div className="bg-white rounded-xl p-5 shadow-sm border border-border hover:shadow-md transition-all">
            <div className="text-xs sm:text-sm text-muted-foreground font-medium mb-1">Total Exams</div>
            <div className="text-2xl sm:text-3xl font-bold text-foreground">28</div>
            <div className="text-xs text-muted-foreground mt-1">Completed</div>
          </div>

          <div className="bg-white rounded-xl p-5 shadow-sm border border-border hover:shadow-md transition-all">
            <div className="text-xs sm:text-sm text-muted-foreground font-medium mb-1">Best Score</div>
            <div className="text-2xl sm:text-3xl font-bold text-primary">95%</div>
            <div className="text-xs text-muted-foreground mt-1">English Literature</div>
          </div>

          <div className="bg-white rounded-xl p-5 shadow-sm border border-border hover:shadow-md transition-all">
            <div className="text-xs sm:text-sm text-muted-foreground font-medium mb-1">Improvement</div>
            <div className="text-2xl sm:text-3xl font-bold text-emerald-600">+20%</div>
            <div className="text-xs text-emerald-600 font-medium mt-1">Since semester start</div>
          </div>
        </div>

        {/* Performance Trend */}
        <div className="bg-white rounded-xl p-5 sm:p-6 shadow-sm border border-border">
          <h3 className="font-semibold text-foreground mb-5">Performance Trend (Last 7 Months)</h3>
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={performanceData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
              <XAxis dataKey="month" stroke="#6B7280" />
              <YAxis stroke="#6B7280" />
              <Tooltip />
              <Line type="monotone" dataKey="score" stroke="#4F46E5" strokeWidth={3} />
            </LineChart>
          </ResponsiveContainer>
        </div>

        {/* Subject-wise Performance */}
        <div className="bg-white rounded-xl p-5 sm:p-6 shadow-sm border border-border">
          <h3 className="font-semibold text-foreground mb-5">Subject-wise Performance</h3>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={subjectPerformance}>
              <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
              <XAxis dataKey="subject" stroke="#6B7280" />
              <YAxis stroke="#6B7280" />
              <Tooltip />
              <Bar dataKey="score" fill="#4F46E5" radius={[8, 8, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Topic Analysis */}
        <div className="bg-white rounded-xl shadow-sm border border-border overflow-hidden">
          <div className="p-5 sm:p-6 border-b border-border">
            <h3 className="font-semibold text-foreground">Topic-wise Strength Analysis</h3>
          </div>
          <div className="p-5 sm:p-6 space-y-4">
            {topicAnalysis.map((topic, index) => (
              <div key={index} className="space-y-1.5">
                <div className="flex items-center justify-between text-xs sm:text-sm">
                  <span className="font-medium text-foreground">{topic.topic}</span>
                  <span className="text-muted-foreground">{topic.attempts} attempts</span>
                </div>
                <div className="relative w-full h-2.5 bg-muted rounded-full overflow-hidden">
                  <div
                    className="absolute left-0 top-0 h-full bg-gradient-to-r from-primary to-secondary rounded-full"
                    style={{ width: `${topic.strength}%` }}
                  />
                </div>
                <div className="text-right text-xs font-semibold text-primary">{topic.strength}%</div>
              </div>
            ))}
          </div>
        </div>

        {/* Strengths & Weaknesses */}
        <div className="grid lg:grid-cols-2 gap-6">
          <div className="bg-white rounded-xl p-5 sm:p-6 shadow-sm border border-border">
            <h3 className="font-semibold text-emerald-700 mb-4 flex items-center gap-2">💪 Strengths</h3>
            <div className="space-y-3">
              <div className="p-3.5 bg-emerald-50/60 border border-emerald-200/60 rounded-xl">
                <div className="text-sm font-medium text-foreground">Quick Problem Solving</div>
                <div className="text-xs text-muted-foreground mt-0.5">Consistently fast in MCQ sections</div>
              </div>
              <div className="p-3.5 bg-emerald-50/60 border border-emerald-200/60 rounded-xl">
                <div className="text-sm font-medium text-foreground">Strong Conceptual Understanding</div>
                <div className="text-xs text-muted-foreground mt-0.5">High scores in theory-based questions</div>
              </div>
              <div className="p-3.5 bg-emerald-50/60 border border-emerald-200/60 rounded-xl">
                <div className="text-sm font-medium text-foreground">Consistent Performance</div>
                <div className="text-xs text-muted-foreground mt-0.5">Steady improvement over time</div>
              </div>
            </div>
          </div>

          <div className="bg-white rounded-xl p-5 sm:p-6 shadow-sm border border-border">
            <h3 className="font-semibold text-amber-700 mb-4 flex items-center gap-2">📈 Areas for Improvement</h3>
            <div className="space-y-3">
              <div className="p-3.5 bg-amber-50/60 border border-amber-200/60 rounded-xl">
                <div className="text-sm font-medium text-foreground">Complex Problem Analysis</div>
                <div className="text-xs text-muted-foreground mt-0.5">Spend more time on multi-step problems</div>
              </div>
              <div className="p-3.5 bg-amber-50/60 border border-amber-200/60 rounded-xl">
                <div className="text-sm font-medium text-foreground">Time Management</div>
                <div className="text-xs text-muted-foreground mt-0.5">Practice timed mock tests</div>
              </div>
              <div className="p-3.5 bg-amber-50/60 border border-amber-200/60 rounded-xl">
                <div className="text-sm font-medium text-foreground">Numerical Accuracy</div>
                <div className="text-xs text-muted-foreground mt-0.5">Review calculation methods</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
}

import { useState } from "react";
import { DashboardLayout } from "../components/DashboardLayout";
import { LayoutDashboard, FileText, Database, History, Settings, Plus, Search, Upload, X } from "lucide-react";
import { useAuth } from "../context/useAuth";

const facultyMenu = [
  { icon: LayoutDashboard, label: "Dashboard", path: "/faculty" },
  { icon: FileText, label: "Generate Paper", path: "/faculty/generate" },
  { icon: Database, label: "Question Bank", path: "/question-bank" },
  { icon: History, label: "Exam History", path: "/faculty/history" },
  { icon: Settings, label: "Settings", path: "/faculty/settings" },
];

const adminMenu = [
  { icon: LayoutDashboard, label: "Dashboard", path: "/admin" },
  { icon: FileText, label: "Exams", path: "/admin/exams" },
  { icon: Database, label: "Question Bank", path: "/admin/question-bank" },
  { icon: History, label: "Students", path: "/admin/students" },
  { icon: Settings, label: "Settings", path: "/admin/settings" },
];

const bloomLevels = ["Remember", "Understand", "Apply", "Analyze", "Evaluate", "Create"];
const difficultyLevels = ["Easy", "Medium", "Hard"];

const sampleQuestions = [
  {
    id: 1,
    question: "What is the time complexity of QuickSort in the average case?",
    difficulty: "Medium",
    bloom: "Understand",
    subject: "Data Structures",
    type: "MCQ"
  },
  {
    id: 2,
    question: "Explain the concept of polymorphism in object-oriented programming.",
    difficulty: "Hard",
    bloom: "Analyze",
    subject: "OOP",
    type: "Subjective"
  },
  {
    id: 3,
    question: "Which data structure uses LIFO principle?",
    difficulty: "Easy",
    bloom: "Remember",
    subject: "Data Structures",
    type: "MCQ"
  },
  {
    id: 4,
    question: "Implement a binary search algorithm in pseudocode.",
    difficulty: "Hard",
    bloom: "Create",
    subject: "Algorithms",
    type: "Subjective"
  }
];

export function QuestionBank() {
  const [showAddModal, setShowAddModal] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [filterDifficulty, setFilterDifficulty] = useState("all");
  const [filterBloom, setFilterBloom] = useState("all");
  const { session } = useAuth();
  const role = session?.role ?? "faculty";
  const menuItems = role === "admin" ? adminMenu : facultyMenu;
  const userRole = role === "admin" ? "Admin" : "Faculty";

  return (
    <DashboardLayout menuItems={menuItems} userRole={userRole}>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl sm:text-3xl font-bold text-foreground mb-1">Question Bank Management</h1>
            <p className="text-xs sm:text-sm text-muted-foreground">Organize and manage your question repository</p>
          </div>
          <div className="flex flex-wrap items-center gap-2.5">
            <button className="px-4 py-2 rounded-lg border border-border text-foreground hover:bg-muted/50 text-xs sm:text-sm font-medium transition-colors flex items-center gap-2">
              <Upload className="w-4 h-4" />
              Bulk Upload CSV
            </button>
            <button
              onClick={() => setShowAddModal(true)}
              className="px-4 py-2 rounded-lg bg-gradient-to-r from-primary to-secondary text-white text-xs sm:text-sm font-medium hover:opacity-90 shadow-md transition-all flex items-center gap-2"
            >
              <Plus className="w-4 h-4" />
              Add Question
            </button>
          </div>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 sm:gap-6">
          <div className="bg-white rounded-xl p-5 shadow-sm border border-border hover:shadow-md transition-all">
            <div className="text-2xl sm:text-3xl font-bold text-foreground mb-1">1,247</div>
            <div className="text-xs sm:text-sm text-muted-foreground font-medium">Total Questions</div>
          </div>
          <div className="bg-white rounded-xl p-5 shadow-sm border border-border hover:shadow-md transition-all">
            <div className="text-2xl sm:text-3xl font-bold text-emerald-600 mb-1">342</div>
            <div className="text-xs sm:text-sm text-muted-foreground font-medium">Easy</div>
          </div>
          <div className="bg-white rounded-xl p-5 shadow-sm border border-border hover:shadow-md transition-all">
            <div className="text-2xl sm:text-3xl font-bold text-amber-600 mb-1">589</div>
            <div className="text-xs sm:text-sm text-muted-foreground font-medium">Medium</div>
          </div>
          <div className="bg-white rounded-xl p-5 shadow-sm border border-border hover:shadow-md transition-all">
            <div className="text-2xl sm:text-3xl font-bold text-rose-600 mb-1">316</div>
            <div className="text-xs sm:text-sm text-muted-foreground font-medium">Hard</div>
          </div>
        </div>

        {/* Search & Filter Bar */}
        <div className="bg-white rounded-xl p-4 sm:p-5 shadow-sm border border-border">
          <div className="grid sm:grid-cols-2 md:grid-cols-4 gap-3">
            <div className="sm:col-span-2">
              <div className="relative">
                <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                <input
                  type="text"
                  placeholder="Search questions..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full pl-10 pr-3.5 py-2 rounded-lg bg-input-background border border-border text-sm focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-all"
                />
              </div>
            </div>
            <div>
              <select
                value={filterDifficulty}
                onChange={(e) => setFilterDifficulty(e.target.value)}
                className="w-full px-3.5 py-2 rounded-lg bg-input-background border border-border text-sm focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-all"
              >
                <option value="all">All Difficulties</option>
                {difficultyLevels.map((level) => (
                  <option key={level} value={level}>{level}</option>
                ))}
              </select>
            </div>
            <div>
              <select
                value={filterBloom}
                onChange={(e) => setFilterBloom(e.target.value)}
                className="w-full px-3.5 py-2 rounded-lg bg-input-background border border-border text-sm focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-all"
              >
                <option value="all">All Bloom Levels</option>
                {bloomLevels.map((level) => (
                  <option key={level} value={level}>{level}</option>
                ))}
              </select>
            </div>
          </div>
        </div>

        {/* Questions List */}
        <div className="bg-white rounded-xl shadow-sm border border-border overflow-hidden">
          <div className="p-5 sm:p-6 border-b border-border">
            <h3 className="font-semibold text-foreground">Questions</h3>
          </div>
          <div className="divide-y divide-border">
            {sampleQuestions.map((question) => (
              <div key={question.id} className="p-5 sm:p-6 hover:bg-muted/30 transition-colors">
                <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
                  <div className="flex-1">
                    <p className="text-foreground text-sm font-medium mb-3">{question.question}</p>
                    <div className="flex flex-wrap gap-2">
                      <span className="px-2.5 py-0.5 rounded-full text-xs font-medium bg-muted text-muted-foreground border border-border/60">
                        {question.subject}
                      </span>
                      <span className="px-2.5 py-0.5 rounded-full text-xs font-medium bg-muted text-muted-foreground border border-border/60">
                        {question.type}
                      </span>
                      <span
                        className={`px-2.5 py-0.5 rounded-full text-xs font-medium border ${
                          question.difficulty === "Easy"
                            ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                            : question.difficulty === "Medium"
                            ? "bg-amber-50 text-amber-700 border-amber-200"
                            : "bg-rose-50 text-rose-700 border-rose-200"
                        }`}
                      >
                        {question.difficulty}
                      </span>
                      <span className="px-2.5 py-0.5 rounded-full text-xs font-medium bg-purple-50 text-purple-700 border border-purple-200">
                        {question.bloom}
                      </span>
                    </div>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <button className="px-3 py-1.5 text-xs sm:text-sm font-semibold text-primary hover:text-secondary transition-colors">
                      Edit
                    </button>
                    <button className="px-3 py-1.5 text-xs sm:text-sm font-semibold text-rose-600 hover:text-rose-700 transition-colors">
                      Delete
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Add Question Modal */}
        {showAddModal && (
          <div className="fixed inset-0 bg-black/50 backdrop-blur-xs flex items-center justify-center z-50 p-4">
            <div className="bg-white rounded-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto border border-border shadow-2xl">
              <div className="sticky top-0 bg-white border-b border-border p-5 flex items-center justify-between z-10">
                <h3 className="font-semibold text-base sm:text-lg text-foreground">Add New Question</h3>
                <button
                  onClick={() => setShowAddModal(false)}
                  className="p-1.5 hover:bg-muted rounded-lg text-muted-foreground hover:text-foreground transition-colors"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>
              <div className="p-5 sm:p-6 space-y-4">
                <div>
                  <label className="block text-xs font-medium text-foreground mb-1.5">Question Text</label>
                  <textarea
                    rows={4}
                    placeholder="Enter your question here..."
                    className="w-full px-3.5 py-2 rounded-lg bg-input-background border border-border text-sm focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-all"
                  />
                </div>
                <div className="grid md:grid-cols-2 gap-3.5">
                  <div>
                    <label className="block text-xs font-medium text-foreground mb-1.5">Difficulty Level</label>
                    <select className="w-full px-3.5 py-2 rounded-lg bg-input-background border border-border text-sm focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-all">
                      {difficultyLevels.map((level) => (
                        <option key={level} value={level}>{level}</option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-foreground mb-1.5">Bloom's Taxonomy</label>
                    <select className="w-full px-3.5 py-2 rounded-lg bg-input-background border border-border text-sm focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-all">
                      {bloomLevels.map((level) => (
                        <option key={level} value={level}>{level}</option>
                      ))}
                    </select>
                  </div>
                </div>
                <div className="grid md:grid-cols-2 gap-3.5">
                  <div>
                    <label className="block text-xs font-medium text-foreground mb-1.5">Subject</label>
                    <input
                      type="text"
                      placeholder="e.g., Data Structures"
                      className="w-full px-3.5 py-2 rounded-lg bg-input-background border border-border text-sm focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-all"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-foreground mb-1.5">Question Type</label>
                    <select className="w-full px-3.5 py-2 rounded-lg bg-input-background border border-border text-sm focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-all">
                      <option>MCQ</option>
                      <option>Subjective</option>
                      <option>True/False</option>
                    </select>
                  </div>
                </div>
                <div>
                  <label className="block text-xs font-medium text-foreground mb-1.5">Marks</label>
                  <input
                    type="number"
                    placeholder="5"
                    className="w-full px-3.5 py-2 rounded-lg bg-input-background border border-border text-sm focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-all"
                  />
                </div>
                <div className="flex gap-3 pt-3">
                  <button
                    onClick={() => setShowAddModal(false)}
                    className="flex-1 px-4 py-2.5 rounded-lg border border-border text-foreground font-medium text-sm hover:bg-muted/50 transition-colors"
                  >
                    Cancel
                  </button>
                  <button className="flex-1 px-4 py-2.5 rounded-lg bg-gradient-to-r from-primary to-secondary text-white font-medium text-sm hover:opacity-90 shadow-md transition-all">
                    Add Question
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}

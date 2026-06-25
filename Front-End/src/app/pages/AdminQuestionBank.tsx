import { useState } from "react";
import { DashboardLayout } from "../components/DashboardLayout";
import { Plus, Search, Upload, X } from "lucide-react";

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

export function AdminQuestionBank() {
  const [showAddModal, setShowAddModal] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [filterDifficulty, setFilterDifficulty] = useState("all");
  const [filterBloom, setFilterBloom] = useState("all");

  return (
    <DashboardLayout userRole="Admin">
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-foreground mb-2">Question Bank Management</h1>
            <p className="text-muted-foreground">Manage the institution question repository</p>
          </div>
          <div className="flex gap-3">
            <button className="px-6 py-3 rounded-lg border border-border text-foreground hover:bg-accent transition-colors flex items-center gap-2">
              <Upload className="w-5 h-5" />
              Bulk Upload CSV
            </button>
            <button
              onClick={() => setShowAddModal(true)}
              className="px-6 py-3 rounded-lg bg-gradient-to-r from-primary to-secondary text-white hover:opacity-90 transition-opacity flex items-center gap-2"
            >
              <Plus className="w-5 h-5" />
              Add Question
            </button>
          </div>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
          <div className="bg-white rounded-xl p-6 shadow-sm border border-border">
            <div className="text-3xl font-bold text-foreground mb-1">1,247</div>
            <div className="text-sm text-muted-foreground">Total Questions</div>
          </div>
          <div className="bg-white rounded-xl p-6 shadow-sm border border-border">
            <div className="text-3xl font-bold text-foreground mb-1">342</div>
            <div className="text-sm text-muted-foreground">Easy</div>
          </div>
          <div className="bg-white rounded-xl p-6 shadow-sm border border-border">
            <div className="text-3xl font-bold text-foreground mb-1">589</div>
            <div className="text-sm text-muted-foreground">Medium</div>
          </div>
          <div className="bg-white rounded-xl p-6 shadow-sm border border-border">
            <div className="text-3xl font-bold text-foreground mb-1">316</div>
            <div className="text-sm text-muted-foreground">Hard</div>
          </div>
        </div>

        {/* Search & Filter Bar */}
        <div className="bg-white rounded-xl p-6 shadow-sm border border-border">
          <div className="grid md:grid-cols-4 gap-4">
            <div className="md:col-span-2">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
                <input
                  type="text"
                  placeholder="Search questions..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full pl-10 pr-4 py-2 rounded-lg bg-input-background border border-border focus:outline-none focus:ring-2 focus:ring-primary"
                />
              </div>
            </div>
            <div>
              <select
                value={filterDifficulty}
                onChange={(e) => setFilterDifficulty(e.target.value)}
                className="w-full px-4 py-2 rounded-lg bg-input-background border border-border focus:outline-none focus:ring-2 focus:ring-primary"
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
                className="w-full px-4 py-2 rounded-lg bg-input-background border border-border focus:outline-none focus:ring-2 focus:ring-primary"
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
        <div className="bg-white rounded-xl shadow-sm border border-border">
          <div className="p-6 border-b border-border">
            <h3 className="font-semibold">Questions</h3>
          </div>
          <div className="divide-y divide-border">
            {sampleQuestions.map((question) => (
              <div key={question.id} className="p-6 hover:bg-muted/30 transition-colors">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1">
                    <p className="text-foreground mb-3">{question.question}</p>
                    <div className="flex flex-wrap gap-2">
                      <span className="px-2 py-1 rounded-full text-xs bg-accent text-accent-foreground">
                        {question.subject}
                      </span>
                      <span className="px-2 py-1 rounded-full text-xs bg-accent text-accent-foreground">
                        {question.type}
                      </span>
                      <span
                        className={`px-2 py-1 rounded-full text-xs ${
                          question.difficulty === "Easy"
                            ? "bg-green-100 text-green-700"
                            : question.difficulty === "Medium"
                            ? "bg-yellow-100 text-yellow-700"
                            : "bg-red-100 text-red-700"
                        }`}
                      >
                        {question.difficulty}
                      </span>
                      <span className="px-2 py-1 rounded-full text-xs bg-purple-100 text-purple-700">
                        {question.bloom}
                      </span>
                    </div>
                  </div>
                  <div className="flex gap-2">
                    <button className="px-3 py-1 text-sm text-primary hover:text-secondary transition-colors">
                      Edit
                    </button>
                    <button className="px-3 py-1 text-sm text-destructive hover:opacity-70 transition-opacity">
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
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-6">
            <div className="bg-white rounded-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto">
              <div className="sticky top-0 bg-white border-b border-border p-6 flex items-center justify-between">
                <h3 className="font-semibold text-lg">Add New Question</h3>
                <button
                  onClick={() => setShowAddModal(false)}
                  className="p-2 hover:bg-accent rounded-lg transition-colors"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>
              <div className="p-6 space-y-6">
                <div>
                  <label className="block text-sm mb-2">Question Text</label>
                  <textarea
                    rows={4}
                    placeholder="Enter your question here..."
                    className="w-full px-4 py-3 rounded-lg bg-input-background border border-border focus:outline-none focus:ring-2 focus:ring-primary"
                  />
                </div>
                <div className="grid md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm mb-2">Difficulty Level</label>
                    <select className="w-full px-4 py-2 rounded-lg bg-input-background border border-border focus:outline-none focus:ring-2 focus:ring-primary">
                      {difficultyLevels.map((level) => (
                        <option key={level} value={level}>{level}</option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm mb-2">Bloom's Taxonomy</label>
                    <select className="w-full px-4 py-2 rounded-lg bg-input-background border border-border focus:outline-none focus:ring-2 focus:ring-primary">
                      {bloomLevels.map((level) => (
                        <option key={level} value={level}>{level}</option>
                      ))}
                    </select>
                  </div>
                </div>
                <div className="grid md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm mb-2">Subject</label>
                    <input
                      type="text"
                      placeholder="e.g., Data Structures"
                      className="w-full px-4 py-2 rounded-lg bg-input-background border border-border focus:outline-none focus:ring-2 focus:ring-primary"
                    />
                  </div>
                  <div>
                    <label className="block text-sm mb-2">Question Type</label>
                    <select className="w-full px-4 py-2 rounded-lg bg-input-background border border-border focus:outline-none focus:ring-2 focus:ring-primary">
                      <option>MCQ</option>
                      <option>Subjective</option>
                      <option>True/False</option>
                    </select>
                  </div>
                </div>
                <div>
                  <label className="block text-sm mb-2">Marks</label>
                  <input
                    type="number"
                    placeholder="5"
                    className="w-full px-4 py-2 rounded-lg bg-input-background border border-border focus:outline-none focus:ring-2 focus:ring-primary"
                  />
                </div>
                <div className="flex gap-3 pt-4">
                  <button
                    onClick={() => setShowAddModal(false)}
                    className="flex-1 px-6 py-3 rounded-lg border border-border text-foreground hover:bg-accent transition-colors"
                  >
                    Cancel
                  </button>
                  <button className="flex-1 px-6 py-3 rounded-lg bg-gradient-to-r from-primary to-secondary text-white hover:opacity-90 transition-opacity">
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

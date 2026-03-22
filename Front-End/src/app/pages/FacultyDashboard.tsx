import { useState } from "react";
import { DashboardLayout } from "../components/DashboardLayout";
import { LayoutDashboard, Upload, FileText, History, Settings } from "lucide-react";

const menuItems = [
  { icon: LayoutDashboard, label: "Dashboard", path: "/faculty" },
  { icon: FileText, label: "Generate Paper", path: "/faculty/generate" },
  { icon: History, label: "Exam History", path: "/faculty/history" },
  { icon: Settings, label: "Settings", path: "/faculty/settings" }
];

const examHistory = [
  { title: "Data Structures Midterm", date: "2026-02-28", questions: 25, difficulty: "Medium" },
  { title: "Algorithms Final", date: "2026-02-15", questions: 30, difficulty: "Hard" },
  { title: "Database Quiz", date: "2026-02-10", questions: 15, difficulty: "Easy" },
  { title: "Networks Test", date: "2026-01-25", questions: 20, difficulty: "Medium" }
];

export function FacultyDashboard() {
  const [difficultyMix, setDifficultyMix] = useState({ easy: 30, medium: 50, hard: 20 });

  return (
    <DashboardLayout menuItems={menuItems} userRole="Faculty">
      <div className="space-y-6">
        {/* Header */}
        <div>
          <h1 className="text-3xl font-bold text-foreground mb-2">Faculty Dashboard</h1>
          <p className="text-muted-foreground">Generate and manage exam papers with AI assistance</p>
        </div>

        {/* Main Actions */}
        <div className="grid lg:grid-cols-2 gap-6">
          {/* Upload Syllabus */}
          <div className="bg-white rounded-xl p-6 shadow-sm border border-border">
            <div className="flex items-center gap-3 mb-6">
              <div className="w-12 h-12 rounded-lg bg-gradient-to-br from-primary to-secondary flex items-center justify-center">
                <Upload className="w-6 h-6 text-white" />
              </div>
              <div>
                <h3 className="font-semibold">Upload Syllabus</h3>
                <p className="text-sm text-muted-foreground">Upload course syllabus for AI analysis</p>
              </div>
            </div>
            <div className="border-2 border-dashed border-border rounded-lg p-8 text-center hover:border-primary transition-colors cursor-pointer">
              <Upload className="w-12 h-12 text-muted-foreground mx-auto mb-3" />
              <p className="text-sm text-muted-foreground mb-2">Click to upload or drag and drop</p>
              <p className="text-xs text-muted-foreground">PDF, DOC, DOCX (Max 10MB)</p>
            </div>
            <div className="mt-4 space-y-2">
              <div className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground">Computer Science Syllabus.pdf</span>
                <span className="text-green-600">✓ Uploaded</span>
              </div>
              <div className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground">Data Structures Topics.docx</span>
                <span className="text-green-600">✓ Uploaded</span>
              </div>
            </div>
          </div>

          {/* Generate Paper Form */}
          <div className="bg-white rounded-xl p-6 shadow-sm border border-border">
            <div className="flex items-center gap-3 mb-6">
              <div className="w-12 h-12 rounded-lg bg-gradient-to-br from-primary to-secondary flex items-center justify-center">
                <FileText className="w-6 h-6 text-white" />
              </div>
              <div>
                <h3 className="font-semibold">Generate Exam Paper</h3>
                <p className="text-sm text-muted-foreground">AI-powered paper generation</p>
              </div>
            </div>
            <div className="space-y-4">
              <div>
                <label className="block text-sm mb-2">Exam Title</label>
                <input
                  type="text"
                  placeholder="e.g., Midterm Examination"
                  className="w-full px-4 py-2 rounded-lg bg-input-background border border-border focus:outline-none focus:ring-2 focus:ring-primary"
                />
              </div>
              <div>
                <label className="block text-sm mb-2">Number of Questions</label>
                <input
                  type="number"
                  placeholder="25"
                  className="w-full px-4 py-2 rounded-lg bg-input-background border border-border focus:outline-none focus:ring-2 focus:ring-primary"
                />
              </div>
              <div>
                <label className="block text-sm mb-2">Exam Duration (minutes)</label>
                <input
                  type="number"
                  placeholder="60"
                  className="w-full px-4 py-2 rounded-lg bg-input-background border border-border focus:outline-none focus:ring-2 focus:ring-primary"
                />
              </div>
              <div>
                <label className="block text-sm mb-2">Question Type</label>
                <select className="w-full px-4 py-2 rounded-lg bg-input-background border border-border focus:outline-none focus:ring-2 focus:ring-primary">
                  <option>Multiple Choice</option>
                  <option>Subjective</option>
                  <option>Mixed</option>
                </select>
              </div>
            </div>
          </div>
        </div>

        {/* Difficulty Slider */}
        <div className="bg-white rounded-xl p-6 shadow-sm border border-border">
          <h3 className="font-semibold mb-6">Difficulty Distribution</h3>
          <div className="space-y-6">
            <div>
              <div className="flex justify-between mb-2">
                <label className="text-sm">Easy</label>
                <span className="text-sm font-semibold text-primary">{difficultyMix.easy}%</span>
              </div>
              <input
                type="range"
                min="0"
                max="100"
                value={difficultyMix.easy}
                onChange={(e) => setDifficultyMix({ ...difficultyMix, easy: parseInt(e.target.value) })}
                className="w-full h-2 bg-accent rounded-lg appearance-none cursor-pointer accent-primary"
              />
            </div>
            <div>
              <div className="flex justify-between mb-2">
                <label className="text-sm">Medium</label>
                <span className="text-sm font-semibold text-primary">{difficultyMix.medium}%</span>
              </div>
              <input
                type="range"
                min="0"
                max="100"
                value={difficultyMix.medium}
                onChange={(e) => setDifficultyMix({ ...difficultyMix, medium: parseInt(e.target.value) })}
                className="w-full h-2 bg-accent rounded-lg appearance-none cursor-pointer accent-primary"
              />
            </div>
            <div>
              <div className="flex justify-between mb-2">
                <label className="text-sm">Hard</label>
                <span className="text-sm font-semibold text-primary">{difficultyMix.hard}%</span>
              </div>
              <input
                type="range"
                min="0"
                max="100"
                value={difficultyMix.hard}
                onChange={(e) => setDifficultyMix({ ...difficultyMix, hard: parseInt(e.target.value) })}
                className="w-full h-2 bg-accent rounded-lg appearance-none cursor-pointer accent-primary"
              />
            </div>
          </div>
          <div className="mt-6 flex gap-4">
            <button className="flex-1 px-6 py-3 rounded-lg bg-gradient-to-r from-primary to-secondary text-white hover:opacity-90 transition-opacity">
              Generate Paper
            </button>
            <button className="px-6 py-3 rounded-lg border border-border text-foreground hover:bg-accent transition-colors">
              Preview
            </button>
          </div>
        </div>

        {/* Preview Generated Paper */}
        <div className="bg-white rounded-xl p-6 shadow-sm border border-border">
          <h3 className="font-semibold mb-4">Preview Generated Paper</h3>
          <div className="bg-muted/30 rounded-lg p-6 space-y-4">
            <div className="border-b border-border pb-4">
              <h4 className="font-semibold mb-2">Data Structures Midterm Examination</h4>
              <div className="flex gap-6 text-sm text-muted-foreground">
                <span>Total Questions: 25</span>
                <span>Duration: 60 minutes</span>
                <span>Total Marks: 100</span>
              </div>
            </div>
            <div className="space-y-3">
              <div className="bg-white rounded-lg p-4">
                <div className="flex items-start gap-3">
                  <span className="font-semibold">Q1.</span>
                  <div className="flex-1">
                    <p className="mb-3">What is the time complexity of binary search in a sorted array?</p>
                    <div className="space-y-2 text-sm">
                      <div className="flex items-center gap-2">
                        <div className="w-4 h-4 rounded border border-border"></div>
                        <span>O(n)</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <div className="w-4 h-4 rounded border border-border"></div>
                        <span>O(log n)</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <div className="w-4 h-4 rounded border border-border"></div>
                        <span>O(n²)</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <div className="w-4 h-4 rounded border border-border"></div>
                        <span>O(1)</span>
                      </div>
                    </div>
                    <div className="mt-2 text-xs text-muted-foreground">
                      <span className="bg-green-100 text-green-700 px-2 py-1 rounded">Easy</span>
                      <span className="ml-2">Marks: 2</span>
                    </div>
                  </div>
                </div>
              </div>
              <div className="text-center text-sm text-muted-foreground py-4">
                ... 24 more questions ...
              </div>
            </div>
          </div>
        </div>

        {/* Exam History */}
        <div className="bg-white rounded-xl shadow-sm border border-border">
          <div className="p-6 border-b border-border">
            <h3 className="font-semibold">Exam History</h3>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-muted/50">
                <tr>
                  <th className="text-left px-6 py-3 text-sm text-muted-foreground">Exam Title</th>
                  <th className="text-left px-6 py-3 text-sm text-muted-foreground">Date</th>
                  <th className="text-left px-6 py-3 text-sm text-muted-foreground">Questions</th>
                  <th className="text-left px-6 py-3 text-sm text-muted-foreground">Difficulty</th>
                  <th className="text-left px-6 py-3 text-sm text-muted-foreground">Actions</th>
                </tr>
              </thead>
              <tbody>
                {examHistory.map((exam, index) => (
                  <tr key={index} className="border-t border-border hover:bg-muted/30 transition-colors">
                    <td className="px-6 py-4">{exam.title}</td>
                    <td className="px-6 py-4">{exam.date}</td>
                    <td className="px-6 py-4">{exam.questions}</td>
                    <td className="px-6 py-4">
                      <span
                        className={`inline-flex items-center px-2 py-1 rounded-full text-xs ${
                          exam.difficulty === "Easy"
                            ? "bg-green-100 text-green-700"
                            : exam.difficulty === "Medium"
                            ? "bg-yellow-100 text-yellow-700"
                            : "bg-red-100 text-red-700"
                        }`}
                      >
                        {exam.difficulty}
                      </span>
                    </td>
                    <td className="px-6 py-4">
                      <button className="text-primary hover:text-secondary text-sm">View/Edit</button>
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

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
          <h1 className="text-2xl sm:text-3xl font-bold text-foreground mb-1">Faculty Dashboard</h1>
          <p className="text-xs sm:text-sm text-muted-foreground">Generate and manage exam papers with AI assistance</p>
        </div>

        {/* Main Actions */}
        <div className="grid lg:grid-cols-2 gap-6">
          {/* Upload Syllabus */}
          <div className="bg-white rounded-xl p-5 sm:p-6 shadow-sm border border-border hover:shadow-md transition-all">
            <div className="flex items-center gap-3 mb-5">
              <div className="w-11 h-11 rounded-lg bg-gradient-to-br from-primary to-secondary flex items-center justify-center shadow-sm">
                <Upload className="w-5 h-5 text-white" />
              </div>
              <div>
                <h3 className="font-semibold text-foreground">Upload Syllabus</h3>
                <p className="text-xs sm:text-sm text-muted-foreground">Upload course syllabus for AI analysis</p>
              </div>
            </div>
            <div className="border-2 border-dashed border-border rounded-xl p-6 sm:p-8 text-center hover:border-primary/60 hover:bg-primary/5 transition-all cursor-pointer">
              <Upload className="w-10 h-10 text-muted-foreground/60 mx-auto mb-2" />
              <p className="text-sm font-medium text-foreground mb-1">Click to upload or drag and drop</p>
              <p className="text-xs text-muted-foreground">PDF, DOC, DOCX (Max 10MB)</p>
            </div>
            <div className="mt-4 space-y-2">
              <div className="flex items-center justify-between text-xs sm:text-sm p-2 rounded-lg bg-muted/40">
                <span className="text-foreground font-medium truncate">Computer Science Syllabus.pdf</span>
                <span className="text-emerald-600 font-medium shrink-0 ml-2">✓ Uploaded</span>
              </div>
              <div className="flex items-center justify-between text-xs sm:text-sm p-2 rounded-lg bg-muted/40">
                <span className="text-foreground font-medium truncate">Data Structures Topics.docx</span>
                <span className="text-emerald-600 font-medium shrink-0 ml-2">✓ Uploaded</span>
              </div>
            </div>
          </div>

          {/* Generate Paper Form */}
          <div className="bg-white rounded-xl p-5 sm:p-6 shadow-sm border border-border hover:shadow-md transition-all">
            <div className="flex items-center gap-3 mb-5">
              <div className="w-11 h-11 rounded-lg bg-gradient-to-br from-primary to-secondary flex items-center justify-center shadow-sm">
                <FileText className="w-5 h-5 text-white" />
              </div>
              <div>
                <h3 className="font-semibold text-foreground">Generate Exam Paper</h3>
                <p className="text-xs sm:text-sm text-muted-foreground">AI-powered paper generation</p>
              </div>
            </div>
            <div className="space-y-3.5">
              <div>
                <label className="block text-xs font-medium text-foreground mb-1.5">Exam Title</label>
                <input
                  type="text"
                  placeholder="e.g., Midterm Examination"
                  className="w-full px-3.5 py-2 rounded-lg bg-input-background border border-border text-sm focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-all"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-foreground mb-1.5">Number of Questions</label>
                <input
                  type="number"
                  placeholder="25"
                  className="w-full px-3.5 py-2 rounded-lg bg-input-background border border-border text-sm focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-all"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-foreground mb-1.5">Exam Duration (minutes)</label>
                <input
                  type="number"
                  placeholder="60"
                  className="w-full px-3.5 py-2 rounded-lg bg-input-background border border-border text-sm focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-all"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-foreground mb-1.5">Question Type</label>
                <select className="w-full px-3.5 py-2 rounded-lg bg-input-background border border-border text-sm focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-all">
                  <option>Multiple Choice</option>
                  <option>Subjective</option>
                  <option>Mixed</option>
                </select>
              </div>
            </div>
          </div>
        </div>

        {/* Difficulty Slider */}
        <div className="bg-white rounded-xl p-5 sm:p-6 shadow-sm border border-border">
          <h3 className="font-semibold text-foreground mb-5">Difficulty Distribution</h3>
          <div className="space-y-5">
            <div>
              <div className="flex justify-between mb-1.5">
                <label className="text-xs font-medium text-foreground">Easy</label>
                <span className="text-xs font-bold text-primary">{difficultyMix.easy}%</span>
              </div>
              <input
                type="range"
                min="0"
                max="100"
                value={difficultyMix.easy}
                onChange={(e) => setDifficultyMix({ ...difficultyMix, easy: parseInt(e.target.value) })}
                className="w-full h-2 bg-muted rounded-lg appearance-none cursor-pointer accent-primary"
              />
            </div>
            <div>
              <div className="flex justify-between mb-1.5">
                <label className="text-xs font-medium text-foreground">Medium</label>
                <span className="text-xs font-bold text-primary">{difficultyMix.medium}%</span>
              </div>
              <input
                type="range"
                min="0"
                max="100"
                value={difficultyMix.medium}
                onChange={(e) => setDifficultyMix({ ...difficultyMix, medium: parseInt(e.target.value) })}
                className="w-full h-2 bg-muted rounded-lg appearance-none cursor-pointer accent-primary"
              />
            </div>
            <div>
              <div className="flex justify-between mb-1.5">
                <label className="text-xs font-medium text-foreground">Hard</label>
                <span className="text-xs font-bold text-primary">{difficultyMix.hard}%</span>
              </div>
              <input
                type="range"
                min="0"
                max="100"
                value={difficultyMix.hard}
                onChange={(e) => setDifficultyMix({ ...difficultyMix, hard: parseInt(e.target.value) })}
                className="w-full h-2 bg-muted rounded-lg appearance-none cursor-pointer accent-primary"
              />
            </div>
          </div>
          <div className="mt-6 flex flex-wrap gap-3">
            <button className="flex-1 min-w-[160px] px-5 py-2.5 rounded-lg bg-gradient-to-r from-primary to-secondary text-white font-medium text-sm hover:opacity-90 shadow-md transition-all">
              Generate Paper
            </button>
            <button className="px-5 py-2.5 rounded-lg border border-border text-foreground font-medium text-sm hover:bg-muted/50 transition-all">
              Preview
            </button>
          </div>
        </div>

        {/* Preview Generated Paper */}
        <div className="bg-white rounded-xl p-5 sm:p-6 shadow-sm border border-border">
          <h3 className="font-semibold text-foreground mb-4">Preview Generated Paper</h3>
          <div className="bg-muted/30 rounded-xl p-5 sm:p-6 space-y-4 border border-border/50">
            <div className="border-b border-border pb-4">
              <h4 className="font-semibold text-foreground mb-2">Data Structures Midterm Examination</h4>
              <div className="flex flex-wrap gap-4 sm:gap-6 text-xs sm:text-sm text-muted-foreground">
                <span>Total Questions: <strong className="text-foreground">25</strong></span>
                <span>Duration: <strong className="text-foreground">60 minutes</strong></span>
                <span>Total Marks: <strong className="text-foreground">100</strong></span>
              </div>
            </div>
            <div className="space-y-3">
              <div className="bg-white rounded-xl p-4 sm:p-5 border border-border shadow-xs">
                <div className="flex items-start gap-3">
                  <span className="font-semibold text-primary text-sm">Q1.</span>
                  <div className="flex-1">
                    <p className="mb-3 text-sm font-medium text-foreground">What is the time complexity of binary search in a sorted array?</p>
                    <div className="space-y-2 text-sm">
                      <div className="flex items-center gap-2.5 text-foreground text-xs sm:text-sm">
                        <div className="w-4 h-4 rounded border border-border bg-input-background"></div>
                        <span>O(n)</span>
                      </div>
                      <div className="flex items-center gap-2.5 text-foreground text-xs sm:text-sm">
                        <div className="w-4 h-4 rounded border border-border bg-input-background"></div>
                        <span>O(log n)</span>
                      </div>
                      <div className="flex items-center gap-2.5 text-foreground text-xs sm:text-sm">
                        <div className="w-4 h-4 rounded border border-border bg-input-background"></div>
                        <span>O(n²)</span>
                      </div>
                      <div className="flex items-center gap-2.5 text-foreground text-xs sm:text-sm">
                        <div className="w-4 h-4 rounded border border-border bg-input-background"></div>
                        <span>O(1)</span>
                      </div>
                    </div>
                    <div className="mt-3 flex items-center gap-2 text-xs text-muted-foreground">
                      <span className="bg-emerald-50 text-emerald-700 border border-emerald-200 px-2.5 py-0.5 rounded-full font-medium">Easy</span>
                      <span>Marks: 2</span>
                    </div>
                  </div>
                </div>
              </div>
              <div className="text-center text-xs text-muted-foreground py-3">
                ... 24 more questions ...
              </div>
            </div>
          </div>
        </div>

        {/* Exam History */}
        <div className="bg-white rounded-xl shadow-sm border border-border overflow-hidden">
          <div className="p-5 sm:p-6 border-b border-border">
            <h3 className="font-semibold text-foreground">Exam History</h3>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-muted/40">
                <tr>
                  <th className="text-left px-5 sm:px-6 py-3.5 text-xs font-semibold text-muted-foreground uppercase tracking-wider">Exam Title</th>
                  <th className="text-left px-5 sm:px-6 py-3.5 text-xs font-semibold text-muted-foreground uppercase tracking-wider">Date</th>
                  <th className="text-left px-5 sm:px-6 py-3.5 text-xs font-semibold text-muted-foreground uppercase tracking-wider">Questions</th>
                  <th className="text-left px-5 sm:px-6 py-3.5 text-xs font-semibold text-muted-foreground uppercase tracking-wider">Difficulty</th>
                  <th className="text-left px-5 sm:px-6 py-3.5 text-xs font-semibold text-muted-foreground uppercase tracking-wider">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {examHistory.map((exam, index) => (
                  <tr key={index} className="hover:bg-muted/30 transition-colors">
                    <td className="px-5 sm:px-6 py-4 text-sm font-medium text-foreground">{exam.title}</td>
                    <td className="px-5 sm:px-6 py-4 text-sm text-muted-foreground">{exam.date}</td>
                    <td className="px-5 sm:px-6 py-4 text-sm text-foreground">{exam.questions}</td>
                    <td className="px-5 sm:px-6 py-4">
                      <span
                        className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium ${
                          exam.difficulty === "Easy"
                            ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                            : exam.difficulty === "Medium"
                            ? "bg-amber-50 text-amber-700 border border-amber-200"
                            : "bg-rose-50 text-rose-700 border border-rose-200"
                        }`}
                      >
                        {exam.difficulty}
                      </span>
                    </td>
                    <td className="px-5 sm:px-6 py-4">
                      <button className="text-primary hover:text-secondary text-sm font-semibold transition-colors">View/Edit</button>
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

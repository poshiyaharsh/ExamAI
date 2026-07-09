import axios from "axios";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { DashboardLayout } from "../components/DashboardLayout";
import { LayoutDashboard, FileText, History, Settings, Search, Download, Eye, Trash2, Filter, Copy } from "lucide-react";
import { toast } from "sonner";
import { facultyPaperApi, type GeneratedPaper, type PaperHistoryRow } from "../../services/api";

const menuItems = [
  { icon: LayoutDashboard, label: "Dashboard", path: "/faculty" },
  { icon: FileText, label: "Generate Paper", path: "/faculty/generate" },
  { icon: History, label: "Exam History", path: "/faculty/history" },
  { icon: Settings, label: "Settings", path: "/faculty/settings" }
];

const draftKey = "faculty-paper-duplicate-draft";

function extractApiErrorMessage(error: unknown, fallback: string) {
  if (!axios.isAxiosError(error)) return fallback;
  const data = error.response?.data;
  if (data && typeof data === "object" && "message" in data && typeof data.message === "string") {
    return data.message;
  }
  return fallback;
}

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

export function FacultyExamHistory() {
  const navigate = useNavigate();
  const [searchTerm, setSearchTerm] = useState("");
  const [filterDifficulty, setFilterDifficulty] = useState("all");
  const [examHistory, setExamHistory] = useState<PaperHistoryRow[]>([]);
  const [selectedPaper, setSelectedPaper] = useState<GeneratedPaper | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [deletingId, setDeletingId] = useState<number | null>(null);

  const fetchHistory = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const response = await facultyPaperApi.getHistory();
      setExamHistory(response.data || []);
    } catch (requestError) {
      const message = extractApiErrorMessage(requestError, "Unable to fetch paper history.");
      setError(message);
      toast.error(message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void fetchHistory();
  }, [fetchHistory]);

  const filteredExams = useMemo(() => examHistory.filter(exam => {
    const matchesSearch = exam.title.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesDifficulty = filterDifficulty === "all" || exam.difficulty.toLowerCase() === filterDifficulty;
    return matchesSearch && matchesDifficulty;
  }), [examHistory, filterDifficulty, searchTerm]);

  const getDifficultyColor = (difficulty: string) => {
    switch (difficulty.toLowerCase()) {
      case "easy": return "bg-green-100 text-green-700";
      case "medium": return "bg-yellow-100 text-yellow-700";
      case "hard": return "bg-red-100 text-red-700";
      default: return "bg-gray-100 text-gray-700";
    }
  };

  const handleView = async (paperId: number) => {
    try {
      const response = await facultyPaperApi.getPaper(paperId);
      setSelectedPaper(response.data);
    } catch (requestError) {
      toast.error(extractApiErrorMessage(requestError, "Unable to fetch paper."));
    }
  };

  const handleExport = async (paperId: number, title: string, format: "pdf" | "docx") => {
    try {
      const blob = await facultyPaperApi.exportPaper(paperId, format);
      downloadBlob(blob, `${title}.${format}`);
    } catch (requestError) {
      toast.error(extractApiErrorMessage(requestError, `Unable to download ${format.toUpperCase()}.`));
    }
  };

  const handleDuplicate = async (paperId: number) => {
    try {
      const response = await facultyPaperApi.getPaper(paperId);
      localStorage.setItem(draftKey, JSON.stringify(response.data));
      navigate("/faculty/generate");
    } catch (requestError) {
      toast.error(extractApiErrorMessage(requestError, "Unable to duplicate paper."));
    }
  };

  const handleDelete = async (paperId: number) => {
    const shouldDelete = window.confirm("Delete this paper? This action cannot be undone.");
    if (!shouldDelete) return;
    setDeletingId(paperId);
    try {
      await facultyPaperApi.deletePaper(paperId);
      setExamHistory((current) => current.filter((paper) => paper.id !== paperId));
      if (selectedPaper?.id === paperId) setSelectedPaper(null);
      toast.success("Paper deleted successfully.");
    } catch (requestError) {
      toast.error(extractApiErrorMessage(requestError, "Unable to delete paper."));
    } finally {
      setDeletingId(null);
    }
  };

  const totalQuestions = examHistory.reduce((acc, exam) => acc + exam.questions, 0);

  return (
    <DashboardLayout menuItems={menuItems} userRole="Faculty">
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-bold text-foreground mb-2">Exam History</h1>
          <p className="text-muted-foreground">View and manage all your created exams</p>
        </div>

        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="bg-white rounded-xl p-6 shadow-sm border border-border">
            <p className="text-sm text-muted-foreground mb-1">Total Exams</p>
            <p className="text-3xl font-bold text-foreground">{examHistory.length}</p>
          </div>
          <div className="bg-white rounded-xl p-6 shadow-sm border border-border">
            <p className="text-sm text-muted-foreground mb-1">Total Questions</p>
            <p className="text-3xl font-bold text-foreground">{totalQuestions}</p>
          </div>
          <div className="bg-white rounded-xl p-6 shadow-sm border border-border">
            <p className="text-sm text-muted-foreground mb-1">Total Marks</p>
            <p className="text-3xl font-bold text-foreground">
              {examHistory.reduce((acc, exam) => acc + exam.total_marks, 0)}
            </p>
          </div>
          <div className="bg-white rounded-xl p-6 shadow-sm border border-border">
            <p className="text-sm text-muted-foreground mb-1">Avg Questions</p>
            <p className="text-3xl font-bold text-foreground">
              {examHistory.length ? Math.round(totalQuestions / examHistory.length) : 0}
            </p>
          </div>
        </div>

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
          {error && <p className="mt-3 text-sm text-destructive">{error}</p>}
        </div>

        {selectedPaper && (
          <div className="bg-white rounded-xl p-6 shadow-sm border border-border">
            <div className="flex items-center justify-between gap-4 mb-4">
              <h3 className="font-semibold">Preview</h3>
              <button className="px-3 py-1.5 rounded-lg border border-border hover:bg-muted transition-colors text-sm" onClick={() => setSelectedPaper(null)}>
                Close
              </button>
            </div>
            <div className="space-y-4 text-sm">
              <div className="text-center border-b border-border pb-4">
                <p className="font-semibold text-lg">{selectedPaper.institution.institution_name}</p>
                <p className="font-semibold">{selectedPaper.title}</p>
                <p className="text-muted-foreground">Duration: {selectedPaper.duration} minutes | Total Marks: {selectedPaper.total_marks}</p>
              </div>
              <div>
                <p className="font-medium">Instructions</p>
                <p className="text-muted-foreground">Answer all questions. Marks are shown beside each question.</p>
              </div>
              {["MCQ", "Subjective", "True/False", "Fill in the Blanks"].map((type, sectionIndex) => {
                const questions = selectedPaper.questions.filter((question) => question.type === type);
                if (!questions.length) return null;
                return (
                  <div key={type}>
                    <p className="font-semibold mb-2">Section {String.fromCharCode(65 + sectionIndex)}</p>
                    <div className="space-y-3">
                      {questions.map((question) => (
                        <div key={question.question_number}>
                          <p>{question.question_number}. {question.question} <span className="text-muted-foreground">[{question.marks} marks]</span></p>
                          {question.options.length > 0 && (
                            <ul className="mt-1 ml-5 list-disc text-muted-foreground">
                              {question.options.map((option) => <li key={option}>{option}</li>)}
                            </ul>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        <div className="space-y-4">
          {loading ? (
            <div className="bg-white rounded-xl p-6 shadow-sm border border-border text-muted-foreground">Loading exams...</div>
          ) : filteredExams.map((exam) => (
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
                      <span className="block font-medium text-foreground">{exam.total_marks}</span>
                      <span>Marks</span>
                    </div>
                    <div>
                      <span className="block font-medium text-foreground">{exam.duration} min</span>
                      <span>Duration</span>
                    </div>
                    <div>
                      <span className="block font-medium text-foreground">{exam.model}</span>
                      <span>AI Model</span>
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <button onClick={() => void handleView(exam.id)} className="px-4 py-2 rounded-lg border border-border hover:bg-muted transition-colors flex items-center gap-2">
                    <Eye className="w-4 h-4" />
                    View
                  </button>
                  <button onClick={() => void handleExport(exam.id, exam.title, "pdf")} className="px-4 py-2 rounded-lg border border-border hover:bg-muted transition-colors flex items-center gap-2">
                    <Download className="w-4 h-4" />
                    PDF
                  </button>
                  <button onClick={() => void handleExport(exam.id, exam.title, "docx")} className="px-4 py-2 rounded-lg border border-border hover:bg-muted transition-colors flex items-center gap-2">
                    <Download className="w-4 h-4" />
                    DOCX
                  </button>
                  <button onClick={() => void handleDuplicate(exam.id)} className="p-2 rounded-lg hover:bg-muted transition-colors" title="Duplicate">
                    <Copy className="w-4 h-4" />
                  </button>
                  <button
                    disabled={deletingId === exam.id}
                    onClick={() => void handleDelete(exam.id)}
                    className="p-2 rounded-lg text-red-600 hover:bg-red-50 transition-colors disabled:opacity-60"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
              <div className="mt-4 pt-4 border-t border-border flex items-center justify-between text-sm">
                <span className="text-muted-foreground">Created: {new Date(exam.created_at).toLocaleDateString()}</span>
                <span className="text-muted-foreground">Model: <span className="font-medium text-foreground">{exam.model}</span></span>
              </div>
            </div>
          ))}
        </div>

        {!loading && filteredExams.length === 0 && (
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

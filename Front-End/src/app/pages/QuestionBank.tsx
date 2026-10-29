import { useEffect, useState, useCallback } from "react";
import { DashboardLayout } from "../components/DashboardLayout";
import {
  LayoutDashboard,
  FileText,
  Database,
  History,
  Settings,
  Plus,
  Search,
  Upload,
  X,
  Download,
  CheckCircle2,
  AlertCircle,
  Loader2,
  Share2,
  Lock,
  Filter,
  FileSpreadsheet,
  FileCode,
  File,
  Check,
  ChevronLeft,
  ChevronRight,
  RefreshCw,
} from "lucide-react";
import { useAuth } from "../context/useAuth";
import { toast } from "sonner";
import {
  facultyQuestionBankApi,
  type FacultyQuestionBankItem,
  type QuestionBankUploadResponse,
} from "../../services/api";

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

const difficultyLevels = ["Easy", "Medium", "Hard"];
const questionTypeOptions = [
  { value: "all", label: "All Types" },
  { value: "mcq", label: "Multiple Choice (MCQ)" },
  { value: "true_false", label: "True / False" },
  { value: "fill_blank", label: "Fill in the Blank" },
  { value: "short_answer", label: "Short Answer" },
  { value: "long_answer", label: "Long Answer" },
];

function extractApiErrorMessage(err: any, fallback: string): string {
  if (err?.response?.data?.detail) return err.response.data.detail;
  if (err?.response?.data?.message) return err.response.data.message;
  return fallback;
}

export function QuestionBank() {
  const { session } = useAuth();
  const role = session?.role ?? "faculty";
  const menuItems = role === "admin" ? adminMenu : facultyMenu;
  const userRole = role === "admin" ? "Admin" : "Faculty";

  // Question list state
  const [questions, setQuestions] = useState<FacultyQuestionBankItem[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [totalCount, setTotalCount] = useState<number>(0);
  const [currentPage, setCurrentPage] = useState<number>(1);
  const [totalPages, setTotalPages] = useState<number>(1);

  // Filters
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [filterDifficulty, setFilterDifficulty] = useState<string>("all");
  const [filterType, setFilterType] = useState<string>("all");
  const [filterScope, setFilterScope] = useState<"all" | "mine" | "shared">("all");

  // Upload modal state
  const [showUploadModal, setShowUploadModal] = useState<boolean>(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isDryRunning, setIsDryRunning] = useState<boolean>(false);
  const [dryRunResult, setDryRunResult] = useState<QuestionBankUploadResponse | null>(null);
  const [isImporting, setIsImporting] = useState<boolean>(false);
  const [importValidOnly, setImportValidOnly] = useState<boolean>(true);
  const [isSharedUpload, setIsSharedUpload] = useState<boolean>(true);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [isDownloadingTemplate, setIsDownloadingTemplate] = useState<string | null>(null);

  // Fetch Questions from API
  const fetchQuestions = useCallback(async (page: number = 1) => {
    setIsLoading(true);
    try {
      const params: Record<string, any> = {
        page,
        limit: 20,
      };
      if (searchQuery.trim()) params.q = searchQuery.trim();
      if (filterDifficulty !== "all") params.difficulty = filterDifficulty.toLowerCase();
      if (filterType !== "all") params.type = filterType;
      if (filterScope === "mine") params.only_mine = "true";
      if (filterScope === "shared") params.only_shared = "true";

      const res = await facultyQuestionBankApi.getQuestions(params);
      setQuestions(res.questions || []);
      setTotalCount(res.total_count || 0);
      setCurrentPage(res.page || 1);
      setTotalPages(res.total_pages || 1);
    } catch (err: any) {
      toast.error(extractApiErrorMessage(err, "Failed to load question bank items."));
    } finally {
      setIsLoading(false);
    }
  }, [searchQuery, filterDifficulty, filterType, filterScope]);

  useEffect(() => {
    fetchQuestions(1);
  }, [fetchQuestions]);

  // Handle Download Sample Templates
  const handleDownloadTemplate = async (format: "csv" | "xlsx" | "docx" | "json") => {
    setIsDownloadingTemplate(format);
    try {
      const blob = await facultyQuestionBankApi.downloadTemplate(format);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `question_bank_template.${format}`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
      toast.success(`Downloaded ${format.toUpperCase()} sample template.`);
    } catch (err: any) {
      toast.error(extractApiErrorMessage(err, `Failed to download ${format.toUpperCase()} template.`));
    } finally {
      setIsDownloadingTemplate(null);
    }
  };

  // Handle File Selection and Automatic Dry-Run Preview
  const handleFileChange = async (file: File) => {
    setSelectedFile(file);
    setIsDryRunning(true);
    setDryRunResult(null);
    setUploadError(null);

    const formData = new FormData();
    formData.append("file", file);
    formData.append("dry_run", "true");
    formData.append("is_shared", String(isSharedUpload));

    try {
      const result = await facultyQuestionBankApi.uploadFile(formData);
      setDryRunResult(result);
      if (result.invalid_count > 0) {
        setImportValidOnly(true);
      }
    } catch (err: any) {
      setUploadError(extractApiErrorMessage(err, "Failed to parse upload file. Please verify format and file structure."));
    } finally {
      setIsDryRunning(false);
    }
  };

  // Commit Real Import
  const handleConfirmImport = async () => {
    if (!selectedFile) return;
    setIsImporting(true);
    setUploadError(null);

    const formData = new FormData();
    formData.append("file", selectedFile);
    formData.append("dry_run", "false");
    formData.append("import_valid_rows_only", String(importValidOnly));
    formData.append("is_shared", String(isSharedUpload));

    try {
      const result = await facultyQuestionBankApi.uploadFile(formData);
      toast.success(result.detail || `Successfully imported ${result.imported_count} question(s)!`);
      setShowUploadModal(false);
      setSelectedFile(null);
      setDryRunResult(null);
      fetchQuestions(1);
    } catch (err: any) {
      setUploadError(extractApiErrorMessage(err, "Failed to import questions. Please review errors."));
    } finally {
      setIsImporting(false);
    }
  };

  // Statistics summaries
  const easyCount = questions.filter((q) => q.difficulty?.toLowerCase() === "easy").length;
  const mediumCount = questions.filter((q) => q.difficulty?.toLowerCase() === "medium").length;
  const hardCount = questions.filter((q) => q.difficulty?.toLowerCase() === "hard").length;

  return (
    <DashboardLayout menuItems={menuItems} userRole={userRole}>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl sm:text-3xl font-bold text-foreground mb-1">Question Bank Management</h1>
            <p className="text-xs sm:text-sm text-muted-foreground">
              Upload custom question bank files (.csv, .xlsx, .docx, .json) and build offline papers without AI.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2.5">
            <button
              onClick={() => {
                setSelectedFile(null);
                setDryRunResult(null);
                setUploadError(null);
                setShowUploadModal(true);
              }}
              className="px-4 py-2 rounded-lg bg-gradient-to-r from-primary to-secondary text-white text-xs sm:text-sm font-medium hover:opacity-90 shadow-md transition-all flex items-center gap-2"
            >
              <Upload className="w-4 h-4" />
              Upload Question Bank
            </button>
            <button
              onClick={() => fetchQuestions(currentPage)}
              disabled={isLoading}
              className="px-3 py-2 rounded-lg border border-border text-foreground hover:bg-muted/50 text-xs sm:text-sm font-medium transition-colors flex items-center gap-1.5"
              title="Refresh Question List"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? "animate-spin" : ""}`} />
              Refresh
            </button>
          </div>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 sm:gap-6">
          <div className="bg-white rounded-xl p-5 shadow-sm border border-border hover:shadow-md transition-all">
            <div className="text-2xl sm:text-3xl font-bold text-foreground mb-1">{totalCount}</div>
            <div className="text-xs sm:text-sm text-muted-foreground font-medium">Total Questions in Bank</div>
          </div>
          <div className="bg-white rounded-xl p-5 shadow-sm border border-border hover:shadow-md transition-all">
            <div className="text-2xl sm:text-3xl font-bold text-emerald-600 mb-1">{easyCount}</div>
            <div className="text-xs sm:text-sm text-muted-foreground font-medium">Easy (on this page)</div>
          </div>
          <div className="bg-white rounded-xl p-5 shadow-sm border border-border hover:shadow-md transition-all">
            <div className="text-2xl sm:text-3xl font-bold text-amber-600 mb-1">{mediumCount}</div>
            <div className="text-xs sm:text-sm text-muted-foreground font-medium">Medium (on this page)</div>
          </div>
          <div className="bg-white rounded-xl p-5 shadow-sm border border-border hover:shadow-md transition-all">
            <div className="text-2xl sm:text-3xl font-bold text-rose-600 mb-1">{hardCount}</div>
            <div className="text-xs sm:text-sm text-muted-foreground font-medium">Hard (on this page)</div>
          </div>
        </div>

        {/* Search & Filter Bar */}
        <div className="bg-white rounded-xl p-4 sm:p-5 shadow-sm border border-border space-y-3">
          <div className="grid sm:grid-cols-2 md:grid-cols-4 gap-3">
            <div className="sm:col-span-2">
              <div className="relative">
                <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                <input
                  type="text"
                  placeholder="Search questions by text or topic..."
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
                  <option key={level} value={level}>
                    {level}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <select
                value={filterType}
                onChange={(e) => setFilterType(e.target.value)}
                className="w-full px-3.5 py-2 rounded-lg bg-input-background border border-border text-sm focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-all"
              >
                {questionTypeOptions.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="flex flex-wrap items-center justify-between gap-2 pt-2 border-t border-border/50 text-xs text-muted-foreground">
            <div className="flex items-center gap-2">
              <span className="font-medium">Filter by Scope:</span>
              <button
                type="button"
                onClick={() => setFilterScope("all")}
                className={`px-2.5 py-1 rounded-md text-xs font-medium transition-colors ${
                  filterScope === "all" ? "bg-primary text-white" : "bg-muted text-muted-foreground hover:bg-muted/80"
                }`}
              >
                All Visible
              </button>
              <button
                type="button"
                onClick={() => setFilterScope("mine")}
                className={`px-2.5 py-1 rounded-md text-xs font-medium transition-colors ${
                  filterScope === "mine" ? "bg-primary text-white" : "bg-muted text-muted-foreground hover:bg-muted/80"
                }`}
              >
                My Questions
              </button>
              <button
                type="button"
                onClick={() => setFilterScope("shared")}
                className={`px-2.5 py-1 rounded-md text-xs font-medium transition-colors ${
                  filterScope === "shared" ? "bg-primary text-white" : "bg-muted text-muted-foreground hover:bg-muted/80"
                }`}
              >
                Shared with Department
              </button>
            </div>
            <span>Showing {questions.length} of {totalCount} questions</span>
          </div>
        </div>

        {/* Questions List */}
        <div className="bg-white rounded-xl shadow-sm border border-border overflow-hidden">
          <div className="p-4 sm:p-5 border-b border-border flex items-center justify-between">
            <h3 className="font-semibold text-foreground text-sm sm:text-base">Question Repository</h3>
            {totalPages > 1 && (
              <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                <span>
                  Page {currentPage} of {totalPages}
                </span>
                <button
                  type="button"
                  onClick={() => fetchQuestions(currentPage - 1)}
                  disabled={currentPage <= 1 || isLoading}
                  className="p-1 rounded hover:bg-muted disabled:opacity-40"
                >
                  <ChevronLeft className="w-4 h-4" />
                </button>
                <button
                  type="button"
                  onClick={() => fetchQuestions(currentPage + 1)}
                  disabled={currentPage >= totalPages || isLoading}
                  className="p-1 rounded hover:bg-muted disabled:opacity-40"
                >
                  <ChevronRight className="w-4 h-4" />
                </button>
              </div>
            )}
          </div>

          {isLoading ? (
            <div className="p-12 text-center text-muted-foreground">
              <Loader2 className="w-8 h-8 animate-spin mx-auto mb-2 text-primary" />
              <p className="text-sm">Loading question bank items...</p>
            </div>
          ) : questions.length === 0 ? (
            <div className="p-12 text-center text-muted-foreground">
              <Database className="w-10 h-10 mx-auto mb-3 text-muted-foreground/40" />
              <p className="font-semibold text-foreground text-sm sm:text-base mb-1">No questions found</p>
              <p className="text-xs sm:text-sm text-muted-foreground max-w-md mx-auto mb-4">
                {searchQuery || filterDifficulty !== "all" || filterType !== "all"
                  ? "No questions match your current search or filters. Try adjusting your search criteria."
                  : "Your question bank is empty. Upload your own question file (.csv, .xlsx, .docx, .json) to get started."}
              </p>
              <button
                onClick={() => {
                  setSelectedFile(null);
                  setDryRunResult(null);
                  setUploadError(null);
                  setShowUploadModal(true);
                }}
                className="px-4 py-2 rounded-lg bg-primary text-white text-xs sm:text-sm font-medium hover:opacity-90 inline-flex items-center gap-2"
              >
                <Upload className="w-4 h-4" />
                Upload Your Question File
              </button>
            </div>
          ) : (
            <div className="divide-y divide-border">
              {questions.map((q) => (
                <div key={q.id} className="p-4 sm:p-5 hover:bg-muted/30 transition-colors">
                  <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3">
                    <div className="flex-1 space-y-2">
                      <p className="text-foreground text-sm font-medium whitespace-pre-wrap">{q.question_text}</p>

                      {/* Options preview for MCQ */}
                      {q.options && q.options.length > 0 && (
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-1.5 pt-1">
                          {q.options.map((opt: any, optIdx: number) => {
                            const optText = typeof opt === "string" ? opt : opt?.text || opt?.label || "";
                            const isCorrect =
                              typeof opt === "object" && opt?.is_correct !== undefined
                                ? opt.is_correct
                                : String.fromCharCode(65 + optIdx) === q.correct_answer;
                            return (
                              <div
                                key={optIdx}
                                className={`text-xs px-2.5 py-1 rounded-md border flex items-center justify-between ${
                                  isCorrect
                                    ? "bg-emerald-50 text-emerald-800 border-emerald-200 font-semibold"
                                    : "bg-muted/40 text-muted-foreground border-border/60"
                                }`}
                              >
                                <span>
                                  <span className="font-bold mr-1.5">{String.fromCharCode(65 + optIdx)}.</span>
                                  {optText}
                                </span>
                                {isCorrect && <Check className="w-3.5 h-3.5 text-emerald-600 shrink-0" />}
                              </div>
                            );
                          })}
                        </div>
                      )}

                      {/* Correct answer / model answer for non-MCQs */}
                      {(!q.options || q.options.length === 0) && (q.correct_answer || q.model_answer) && (
                        <div className="bg-slate-50 border border-slate-200 rounded-lg p-2.5 text-xs text-slate-700">
                          <span className="font-semibold text-slate-900 mr-1.5">Model Answer:</span>
                          {q.correct_answer || q.model_answer}
                        </div>
                      )}

                      {/* Badges */}
                      <div className="flex flex-wrap items-center gap-2 pt-1">
                        <span className="px-2 py-0.5 rounded-md text-[11px] font-bold bg-indigo-50 text-indigo-700 border border-indigo-200">
                          {q.marks} {q.marks === 1 ? "Mark" : "Marks"}
                        </span>
                        <span className="px-2 py-0.5 rounded-md text-[11px] font-semibold bg-muted text-muted-foreground border border-border/60">
                          {q.question_type?.toUpperCase().replace("_", " ")}
                        </span>
                        <span
                          className={`px-2 py-0.5 rounded-md text-[11px] font-semibold border ${
                            q.difficulty?.toLowerCase() === "easy"
                              ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                              : q.difficulty?.toLowerCase() === "medium"
                              ? "bg-amber-50 text-amber-700 border-amber-200"
                              : "bg-rose-50 text-rose-700 border-rose-200"
                          }`}
                        >
                          {q.difficulty?.toUpperCase()}
                        </span>
                        {q.subject_name && (
                          <span className="px-2 py-0.5 rounded-md text-[11px] font-medium bg-muted text-muted-foreground border border-border/60">
                            {q.subject_name}
                          </span>
                        )}
                        {q.topic && (
                          <span className="px-2 py-0.5 rounded-md text-[11px] font-medium bg-muted text-muted-foreground border border-border/60">
                            {q.topic}
                          </span>
                        )}
                        {q.is_shared ? (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px] font-semibold bg-blue-50 text-blue-700 border border-blue-200">
                            <Share2 className="w-3 h-3" />
                            Dept Shared
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px] font-semibold bg-slate-100 text-slate-600 border border-slate-300">
                            <Lock className="w-3 h-3" />
                            Private
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Pagination bar at bottom */}
          {totalPages > 1 && (
            <div className="p-4 border-t border-border flex items-center justify-between text-xs text-muted-foreground">
              <span>
                Showing page {currentPage} of {totalPages} ({totalCount} total)
              </span>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => fetchQuestions(currentPage - 1)}
                  disabled={currentPage <= 1 || isLoading}
                  className="px-3 py-1.5 rounded-md border border-border hover:bg-muted font-medium disabled:opacity-40"
                >
                  Previous
                </button>
                <button
                  type="button"
                  onClick={() => fetchQuestions(currentPage + 1)}
                  disabled={currentPage >= totalPages || isLoading}
                  className="px-3 py-1.5 rounded-md border border-border hover:bg-muted font-medium disabled:opacity-40"
                >
                  Next
                </button>
              </div>
            </div>
          )}
        </div>

        {/* ================= UPLOAD MODAL ================= */}
        {showUploadModal && (
          <div className="fixed inset-0 bg-black/50 backdrop-blur-xs flex items-center justify-center z-50 p-4">
            <div className="bg-white rounded-2xl w-full max-w-3xl max-h-[92vh] overflow-y-auto border border-border shadow-2xl flex flex-col">
              <div className="sticky top-0 bg-white border-b border-border p-5 flex items-center justify-between z-10">
                <div className="flex items-center gap-2.5">
                  <div className="w-8 h-8 rounded-lg bg-primary/10 text-primary flex items-center justify-center">
                    <Upload className="w-4 h-4" />
                  </div>
                  <div>
                    <h3 className="font-semibold text-base sm:text-lg text-foreground">Upload Question Bank File</h3>
                    <p className="text-xs text-muted-foreground">
                      Supported formats: CSV, Excel (.xlsx), Word (.docx), JSON (max 10MB, up to 500 rows)
                    </p>
                  </div>
                </div>
                <button
                  onClick={() => setShowUploadModal(false)}
                  className="p-1.5 hover:bg-muted rounded-lg text-muted-foreground hover:text-foreground transition-colors"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              <div className="p-5 sm:p-6 space-y-5 flex-1">
                {/* Download sample templates bar */}
                <div className="p-3.5 bg-slate-50 border border-slate-200 rounded-xl">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                    <div>
                      <span className="text-xs font-bold text-slate-800 block">Download Sample Templates:</span>
                      <span className="text-[11px] text-slate-500">
                        Use our standard templates with sample MCQ, True/False, Fill blank, and Subjective rows.
                      </span>
                    </div>
                    <div className="flex flex-wrap gap-1.5">
                      {(["csv", "xlsx", "docx", "json"] as const).map((fmt) => (
                        <button
                          key={fmt}
                          type="button"
                          onClick={() => handleDownloadTemplate(fmt)}
                          disabled={isDownloadingTemplate === fmt}
                          className="px-2.5 py-1 text-xs font-semibold rounded-md border border-slate-300 bg-white hover:bg-slate-100 text-slate-700 flex items-center gap-1.5 transition-colors shadow-2xs disabled:opacity-50"
                        >
                          {isDownloadingTemplate === fmt ? (
                            <Loader2 className="w-3 h-3 animate-spin" />
                          ) : (
                            <Download className="w-3 h-3" />
                          )}
                          {fmt.toUpperCase()}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>

                {/* File Dropzone */}
                <div>
                  <label className="block text-xs font-bold text-foreground mb-1.5">
                    Select Question Bank Document
                  </label>
                  <label className="border-2 border-dashed border-border rounded-xl p-6 flex flex-col items-center justify-center cursor-pointer hover:bg-muted/30 transition-colors">
                    <input
                      type="file"
                      accept=".csv, .xlsx, .docx, .json, application/vnd.openxmlformats-officedocument.spreadsheetml.sheet, application/vnd.openxmlformats-officedocument.wordprocessingml.document, application/json, text/csv"
                      onChange={(e) => {
                        if (e.target.files && e.target.files[0]) {
                          handleFileChange(e.target.files[0]);
                        }
                      }}
                      className="hidden"
                    />
                    <Upload className="w-8 h-8 text-muted-foreground/60 mb-2" />
                    <span className="text-sm font-semibold text-foreground">
                      {selectedFile ? selectedFile.name : "Click or drag file here to analyze"}
                    </span>
                    <span className="text-xs text-muted-foreground mt-0.5">
                      {selectedFile
                        ? `${(selectedFile.size / 1024).toFixed(1)} KB - click to choose a different file`
                        : "CSV, XLSX, DOCX, or JSON (max 10MB)"}
                    </span>
                  </label>
                </div>

                {/* Privacy checkbox */}
                <div className="flex items-center gap-2.5 p-3 rounded-lg border border-border bg-muted/20">
                  <input
                    type="checkbox"
                    id="is_shared_upload"
                    checked={isSharedUpload}
                    onChange={(e) => setIsSharedUpload(e.target.checked)}
                    className="w-4 h-4 rounded text-primary focus:ring-primary border-border"
                  />
                  <label htmlFor="is_shared_upload" className="text-xs font-medium text-foreground cursor-pointer">
                    Share these questions with other faculty in your department (uncheck to keep private to you only)
                  </label>
                </div>

                {/* Upload Error Banner */}
                {uploadError && (
                  <div className="p-3.5 rounded-xl border border-rose-200 bg-rose-50 text-rose-800 text-xs flex items-start gap-2.5">
                    <AlertCircle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
                    <div>
                      <span className="font-bold block">File Analysis Error</span>
                      <span>{uploadError}</span>
                    </div>
                  </div>
                )}

                {/* Dry Run Analyzing Loader */}
                {isDryRunning && (
                  <div className="p-8 text-center bg-slate-50 border border-slate-200 rounded-xl text-slate-600">
                    <Loader2 className="w-6 h-6 animate-spin mx-auto mb-2 text-primary" />
                    <p className="text-xs font-semibold">Validating rows, formulas, and schema security...</p>
                  </div>
                )}

                {/* Dry Run Preview Table */}
                {dryRunResult && (
                  <div className="space-y-3">
                    <div className="flex flex-wrap items-center justify-between gap-2 p-3 bg-muted/30 border border-border rounded-xl">
                      <div className="flex items-center gap-3">
                        <span className="text-xs font-bold text-foreground">
                          Detected Format: <span className="uppercase text-primary">{dryRunResult.format}</span>
                        </span>
                        <span className="px-2 py-0.5 rounded-md text-xs font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">
                          {dryRunResult.valid_count} Valid Rows
                        </span>
                        {dryRunResult.invalid_count > 0 && (
                          <span className="px-2 py-0.5 rounded-md text-xs font-bold bg-rose-50 text-rose-700 border border-rose-200">
                            {dryRunResult.invalid_count} Invalid Rows
                          </span>
                        )}
                      </div>
                      <span className="text-xs text-muted-foreground font-medium">
                        Total {dryRunResult.total_rows} rows analyzed
                      </span>
                    </div>

                    {/* Invalid Rows Notice & Toggle */}
                    {dryRunResult.invalid_count > 0 && (
                      <div className="p-3.5 rounded-xl border border-amber-200 bg-amber-50 text-amber-800 text-xs space-y-2">
                        <div className="flex items-center gap-2">
                          <AlertCircle className="w-4 h-4 text-amber-600 shrink-0" />
                          <span className="font-bold">
                            {dryRunResult.invalid_count} row(s) contain validation errors.
                          </span>
                        </div>
                        <div className="flex items-center gap-2 pt-1">
                          <input
                            type="checkbox"
                            id="import_valid_toggle"
                            checked={importValidOnly}
                            onChange={(e) => setImportValidOnly(e.target.checked)}
                            className="w-4 h-4 rounded text-amber-600 focus:ring-amber-500 border-amber-300"
                          />
                          <label htmlFor="import_valid_toggle" className="font-semibold text-amber-900 cursor-pointer">
                            Import valid rows only (skip the {dryRunResult.invalid_count} invalid row(s))
                          </label>
                        </div>
                      </div>
                    )}

                    {/* Preview Table */}
                    <div className="border border-border rounded-xl overflow-hidden">
                      <div className="bg-muted/40 px-3 py-2 border-b border-border text-xs font-bold text-muted-foreground">
                        Preview of Questions to Import (First {dryRunResult.preview_rows.length} rows)
                      </div>
                      <div className="max-h-56 overflow-y-auto divide-y divide-border">
                        {dryRunResult.preview_rows.map((row: any, rIdx: number) => (
                          <div key={rIdx} className="p-2.5 text-xs flex items-start justify-between gap-3">
                            <div className="flex-1">
                              <span className="font-bold text-muted-foreground mr-1.5">Row {row.row_number || rIdx + 1}:</span>
                              <span className="font-medium text-foreground">{row.question_text || row.text}</span>
                              <div className="flex items-center gap-2 mt-1 text-[11px] text-muted-foreground">
                                <span className="uppercase font-semibold">{row.question_type || "mcq"}</span>
                                <span>•</span>
                                <span>{row.marks || 1} Marks</span>
                                {row.topic && (
                                  <>
                                    <span>•</span>
                                    <span>{row.topic}</span>
                                  </>
                                )}
                              </div>
                            </div>
                            <div className="shrink-0">
                              {row.is_valid ? (
                                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">
                                  <Check className="w-3 h-3" /> Valid
                                </span>
                              ) : (
                                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-bold bg-rose-50 text-rose-700 border border-rose-200">
                                  <AlertCircle className="w-3 h-3" /> Error: {row.error || "Malformed row"}
                                </span>
                              )}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                )}
              </div>

              {/* Modal footer */}
              <div className="p-4 bg-muted/20 border-t border-border flex items-center justify-end gap-3">
                <button
                  type="button"
                  onClick={() => setShowUploadModal(false)}
                  className="px-4 py-2 rounded-lg border border-border text-foreground font-medium text-xs hover:bg-muted/50 transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={handleConfirmImport}
                  disabled={
                    !selectedFile ||
                    isDryRunning ||
                    isImporting ||
                    !dryRunResult ||
                    dryRunResult.valid_count === 0 ||
                    (dryRunResult.invalid_count > 0 && !importValidOnly)
                  }
                  className="px-4 py-2 rounded-lg bg-gradient-to-r from-primary to-secondary text-white font-medium text-xs hover:opacity-90 shadow-md transition-all flex items-center gap-2 disabled:opacity-50"
                >
                  {isImporting ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" />
                      Importing Questions...
                    </>
                  ) : (
                    <>
                      <CheckCircle2 className="w-4 h-4" />
                      Confirm Import ({dryRunResult?.valid_count || 0} Questions)
                    </>
                  )}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}

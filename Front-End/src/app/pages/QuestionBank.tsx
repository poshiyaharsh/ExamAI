import { useEffect, useState, useCallback, useMemo } from "react";
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
  AlertTriangle,
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
  Sparkles,
  Trash2,
  Edit3,
  SlidersHorizontal,
  ArrowRight,
  ArrowLeft,
  Layers,
} from "lucide-react";
import { useAuth } from "../context/useAuth";
import { toast } from "sonner";
import {
  facultyQuestionBankApi,
  type FacultyQuestionBankItem,
  type QuestionBankUploadResponse,
  type SmartImportRow,
  type SmartImportDetectedColumn,
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

const targetFieldOptions = [
  { value: "question_text", label: "Question Stem / Text" },
  { value: "option_a", label: "Option A" },
  { value: "option_b", label: "Option B" },
  { value: "option_c", label: "Option C" },
  { value: "option_d", label: "Option D" },
  { value: "option_e", label: "Option E" },
  { value: "options", label: "Combined Options (A|B|C|D)" },
  { value: "correct_answer", label: "Correct Answer" },
  { value: "marks", label: "Marks / Points" },
  { value: "question_type", label: "Question Type" },
  { value: "difficulty", label: "Difficulty" },
  { value: "topic", label: "Topic" },
  { value: "subject", label: "Subject" },
  { value: "explanation", label: "Explanation" },
  { value: "ignore", label: "-- Ignore this column --" },
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

  // ================= SMART IMPORT MODAL STATE =================
  const [showUploadModal, setShowUploadModal] = useState<boolean>(false);
  const [importStep, setImportStep] = useState<"upload" | "mapping" | "preview">("upload");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState<boolean>(false);
  const [isImporting, setIsImporting] = useState<boolean>(false);
  const [isAiAssisting, setIsAiAssisting] = useState<boolean>(false);
  const [isExporting, setIsExporting] = useState<boolean>(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [isDownloadingTemplate, setIsDownloadingTemplate] = useState<string | null>(null);

  // Analysis result & rows
  const [analysisResult, setAnalysisResult] = useState<QuestionBankUploadResponse | null>(null);
  const [parsedRows, setParsedRows] = useState<SmartImportRow[]>([]);
  const [detectedColumns, setDetectedColumns] = useState<SmartImportDetectedColumn[]>([]);
  const [columnMappings, setColumnMappings] = useState<Record<string, string>>({});
  const [selectedSheet, setSelectedSheet] = useState<string>("");

  // Global default overrides
  const [defaultMarks, setDefaultMarks] = useState<number>(1);
  const [defaultDifficulty, setDefaultDifficulty] = useState<string>("medium");
  const [defaultType, setDefaultType] = useState<string>("auto");
  const [isSharedUpload, setIsSharedUpload] = useState<boolean>(true);

  // Preview filtering & search
  const [previewTab, setPreviewTab] = useState<"all" | "ready" | "needs_review" | "invalid">("all");
  const [previewSearch, setPreviewSearch] = useState<string>("");

  // Inline row edit state
  const [editingRowIndex, setEditingRowIndex] = useState<number | null>(null);
  const [editDraft, setEditDraft] = useState<SmartImportRow | null>(null);

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

  // Reset modal state
  const handleOpenUploadModal = () => {
    setSelectedFile(null);
    setAnalysisResult(null);
    setParsedRows([]);
    setDetectedColumns([]);
    setColumnMappings({});
    setSelectedSheet("");
    setImportStep("upload");
    setUploadError(null);
    setPreviewTab("all");
    setPreviewSearch("");
    setEditingRowIndex(null);
    setEditDraft(null);
    setShowUploadModal(true);
  };

  // File Analysis via Smart Import
  const runAnalysis = async (fileToAnalyze: File, customMap?: Record<string, string>, sheetToUse?: string) => {
    setIsAnalyzing(true);
    setUploadError(null);

    const formData = new FormData();
    formData.append("file", fileToAnalyze);
    formData.append("mode", "analyze");
    formData.append("smart_import", "true");
    formData.append("default_marks", String(defaultMarks));
    formData.append("default_difficulty", defaultDifficulty);
    if (defaultType !== "auto") {
      formData.append("default_type", defaultType);
    }
    if (customMap && Object.keys(customMap).length > 0) {
      formData.append("custom_mapping", JSON.stringify(customMap));
    }
    const effSheet = sheetToUse || selectedSheet;
    if (effSheet) {
      formData.append("sheet_name", effSheet);
    }

    try {
      const result = await facultyQuestionBankApi.analyzeFile(formData);
      setAnalysisResult(result);
      const rows = result.all_rows && result.all_rows.length > 0 ? result.all_rows : result.preview_rows || [];
      setParsedRows(rows);

      if (result.sheet_names && result.sheet_names.length > 0 && !selectedSheet) {
        setSelectedSheet(result.selected_sheet || result.sheet_names[0]);
      }

      if (result.columns && result.columns.length > 0) {
        setDetectedColumns(result.columns);
        const mapObj: Record<string, string> = {};
        result.columns.forEach((col) => {
          mapObj[`col_${col.index}`] = col.proposed_target || "ignore";
        });
        setColumnMappings(mapObj);
      }

      // If spreadsheet with custom columns, open mapping screen; otherwise jump to preview
      const ext = fileToAnalyze.name.split(".").pop()?.toLowerCase();
      if ((ext === "csv" || ext === "xlsx") && result.columns && result.columns.length > 0 && !customMap) {
        setImportStep("mapping");
      } else {
        setImportStep("preview");
      }
    } catch (err: any) {
      setUploadError(extractApiErrorMessage(err, "Failed to analyze question bank file. Please verify file integrity."));
    } finally {
      setIsAnalyzing(false);
    }
  };

  const handleFileChange = (file: File) => {
    setSelectedFile(file);
    runAnalysis(file);
  };

  // Switch sheet for multi-tab Excel
  const handleSheetChange = (newSheet: string) => {
    setSelectedSheet(newSheet);
    if (selectedFile) {
      runAnalysis(selectedFile, columnMappings, newSheet);
    }
  };

  // Re-run analysis with adjusted column mappings
  const handleApplyMappings = () => {
    if (selectedFile) {
      runAnalysis(selectedFile, columnMappings, selectedSheet);
    }
  };

  // Inline option toggle: user clicks an option in the preview to designate it as the verified answer
  const handleSelectOptionAnswer = (rowIdx: number, optText: string, optOrder: number) => {
    setParsedRows((prevRows) => {
      const updated = [...prevRows];
      const target = { ...updated[rowIdx] };
      const rowData = { ...target.data };

      const letter = String.fromCharCode(64 + optOrder);
      rowData.correct_answer = letter;

      if (Array.isArray(rowData.options)) {
        rowData.options = rowData.options.map((opt: any, oIdx: number) => {
          const isThis = oIdx + 1 === optOrder;
          if (typeof opt === "object") {
            return { ...opt, is_correct: isThis };
          }
          return { text: String(opt), is_correct: isThis, order: oIdx + 1 };
        });
      }

      // Clear review notes concerning missing answer
      const filteredNotes = (target.review_notes || []).filter(
        (n) => !n.toLowerCase().includes("answer") && !n.toLowerCase().includes("option")
      );

      target.review_notes = filteredNotes;
      target.warnings = filteredNotes;
      target.data = rowData;
      target.status = target.errors.length > 0 ? "invalid" : filteredNotes.length > 0 ? "needs_review" : "ready";
      target.is_ready = target.status === "ready";
      target.needs_review = target.status === "needs_review";

      updated[rowIdx] = target;
      return updated;
    });
  };

  // Quick edit modal openers
  const handleStartEditRow = (rowIdx: number) => {
    setEditingRowIndex(rowIdx);
    setEditDraft(JSON.parse(JSON.stringify(parsedRows[rowIdx])));
  };

  const handleSaveRowEdit = () => {
    if (editingRowIndex === null || !editDraft) return;
    setParsedRows((prevRows) => {
      const updated = [...prevRows];
      const row = { ...editDraft };
      // re-check validity
      const stem = row.data.question_text?.trim();
      const errs: string[] = [];
      if (!stem || stem.length < 5) errs.push("Question stem is required (minimum 5 chars).");
      if (row.data.question_type === "mcq" && (!row.data.options || row.data.options.length < 2)) {
        errs.push("MCQ requires at least 2 distinct options.");
      }
      row.errors = errs;
      row.status = errs.length > 0 ? "invalid" : (row.review_notes?.length || 0) > 0 ? "needs_review" : "ready";
      row.is_ready = row.status === "ready";
      row.needs_review = row.status === "needs_review";
      row.is_valid = errs.length === 0;

      updated[editingRowIndex] = row;
      return updated;
    });
    setEditingRowIndex(null);
    setEditDraft(null);
    toast.success("Question row updated.");
  };

  // Delete a single row from the preview table
  const handleDeleteRow = (rowIdx: number) => {
    setParsedRows((prev) => prev.filter((_, idx) => idx !== rowIdx));
    toast.info("Row removed from import queue.");
  };

  // Bulk action: remove all invalid rows
  const handleRemoveAllInvalid = () => {
    const validOnes = parsedRows.filter((r) => r.status !== "invalid");
    const removedCount = parsedRows.length - validOnes.length;
    setParsedRows(validOnes);
    toast.success(`Removed ${removedCount} invalid row(s).`);
  };

  // Bulk action: mark all Needs Review as Ready
  const handleMarkAllReviewedAsReady = () => {
    setParsedRows((prev) =>
      prev.map((r) => {
        if (r.status === "needs_review") {
          return {
            ...r,
            status: "ready",
            is_ready: true,
            needs_review: false,
            warnings: [],
            review_notes: [],
          };
        }
        return r;
      })
    );
    toast.success("Marked all reviewed rows as ready.");
  };

  // AI Assist on unclear items
  const handleRunAiAssist = async () => {
    const unclearRows = parsedRows.filter((r) => r.status === "needs_review");
    if (unclearRows.length === 0) {
      toast.info("No rows currently require AI assistance.");
      return;
    }
    setIsAiAssisting(true);
    try {
      const itemsPayload = unclearRows.map((r) => ({
        question_text: r.data.question_text,
        options: r.data.options,
        correct_answer: r.data.correct_answer,
      }));
      const res = await facultyQuestionBankApi.aiAssist({ items: itemsPayload });
      toast.success(`AI Assist parsed ${res.extracted_count} question structure(s).`);
    } catch (err: any) {
      toast.error(extractApiErrorMessage(err, "AI Assist unavailable or could not process items."));
    } finally {
      setIsAiAssisting(false);
    }
  };

  // Export diagnostic report CSV
  const handleExportErrorReport = async () => {
    setIsExporting(true);
    try {
      const skippedRows = parsedRows.filter((r) => r.status !== "ready");
      const rowsToReport = skippedRows.length > 0 ? skippedRows : parsedRows;
      const blob = await facultyQuestionBankApi.exportReport(rowsToReport);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `question_bank_import_report.csv`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
      toast.success("Downloaded import diagnostic CSV report.");
    } catch (err: any) {
      toast.error(extractApiErrorMessage(err, "Failed to export diagnostic report."));
    } finally {
      setIsExporting(false);
    }
  };

  // Export Cleaned Template XLSX
  const handleExportCleanedXlsx = async () => {
    setIsExporting(true);
    try {
      const blob = await facultyQuestionBankApi.exportCleaned(parsedRows);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `cleaned_question_bank.xlsx`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
      toast.success("Exported cleaned question bank as standard XLSX.");
    } catch (err: any) {
      toast.error(extractApiErrorMessage(err, "Failed to export cleaned template."));
    } finally {
      setIsExporting(false);
    }
  };

  // Commit Questions to Database
  const handleCommitQuestions = async (mode: "ready_only" | "ready_and_reviewed") => {
    if (parsedRows.length === 0) return;
    setIsImporting(true);
    setUploadError(null);

    const targetRows = parsedRows.filter((r) => {
      if (mode === "ready_only") return r.status === "ready";
      return r.status === "ready" || r.status === "needs_review";
    });

    if (targetRows.length === 0) {
      toast.error("No eligible questions selected for import.");
      setIsImporting(false);
      return;
    }

    try {
      const result = await facultyQuestionBankApi.commitCuratedQuestions({
        questions: targetRows.map((r) => r.data),
        is_shared: isSharedUpload,
        filename: selectedFile?.name || "smart_import.csv",
        format: analysisResult?.format || "smart",
      });

      toast.success(result.detail || `Successfully imported ${result.imported_count} questions into your question bank!`);
      setShowUploadModal(false);
      fetchQuestions(1);
    } catch (err: any) {
      setUploadError(extractApiErrorMessage(err, "Failed to save questions to database. Please review errors."));
    } finally {
      setIsImporting(false);
    }
  };

  // Filtered rows for the preview table
  const filteredPreviewRows = useMemo(() => {
    return parsedRows.filter((r) => {
      if (previewTab === "ready" && r.status !== "ready") return false;
      if (previewTab === "needs_review" && r.status !== "needs_review") return false;
      if (previewTab === "invalid" && r.status !== "invalid") return false;

      if (previewSearch.trim()) {
        const query = previewSearch.toLowerCase();
        const textMatch = r.data.question_text?.toLowerCase().includes(query);
        const topicMatch = r.data.topic?.toLowerCase().includes(query);
        return textMatch || topicMatch;
      }
      return true;
    });
  }, [parsedRows, previewTab, previewSearch]);

  const readyRowsCount = parsedRows.filter((r) => r.status === "ready").length;
  const reviewRowsCount = parsedRows.filter((r) => r.status === "needs_review").length;
  const invalidRowsCount = parsedRows.filter((r) => r.status === "invalid").length;

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
              Smart Import accepts almost any file format (.csv, .xlsx, .docx, .pdf, .txt, .json) without needing strict templates.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2.5">
            <button
              onClick={handleOpenUploadModal}
              className="px-4 py-2 rounded-lg bg-gradient-to-r from-primary to-secondary text-white text-xs sm:text-sm font-medium hover:opacity-90 shadow-md transition-all flex items-center gap-2 cursor-pointer"
            >
              <Upload className="w-4 h-4" />
              Smart Import Questions
            </button>
            <button
              onClick={() => fetchQuestions(currentPage)}
              disabled={isLoading}
              className="px-3 py-2 rounded-lg border border-border text-foreground hover:bg-muted/50 text-xs sm:text-sm font-medium transition-colors flex items-center gap-1.5 cursor-pointer"
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
                  : "Your question bank is empty. Upload your own question file (.csv, .xlsx, .docx, .pdf, .txt, .json) to get started."}
              </p>
              <button
                onClick={handleOpenUploadModal}
                className="px-4 py-2 rounded-lg bg-primary text-white text-xs sm:text-sm font-medium hover:opacity-90 inline-flex items-center gap-2 cursor-pointer"
              >
                <Upload className="w-4 h-4" />
                Smart Import Your Questions
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
                                : String.fromCharCode(65 + optIdx) === q.correct_answer || optText === q.correct_answer;
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
                              : q.difficulty?.toLowerCase() === "hard"
                              ? "bg-rose-50 text-rose-700 border-rose-200"
                              : "bg-amber-50 text-amber-700 border-amber-200"
                          }`}
                        >
                          {q.difficulty ? q.difficulty.charAt(0).toUpperCase() + q.difficulty.slice(1) : "Medium"}
                        </span>
                        {q.topic && (
                          <span className="px-2 py-0.5 rounded-md text-[11px] bg-slate-100 text-slate-700">
                            {q.topic}
                          </span>
                        )}
                        {q.is_shared ? (
                          <span className="inline-flex items-center gap-1 text-[11px] text-muted-foreground">
                            <Share2 className="w-3 h-3 text-indigo-500" /> Shared
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 text-[11px] text-muted-foreground">
                            <Lock className="w-3 h-3 text-slate-400" /> Private
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* ================= SMART IMPORT MODAL ================= */}
        {showUploadModal && (
          <div className="fixed inset-0 bg-black/50 backdrop-blur-xs flex items-center justify-center z-50 p-2 sm:p-4">
            <div className="bg-white rounded-2xl w-full max-w-4xl max-h-[94vh] overflow-hidden border border-border shadow-2xl flex flex-col">
              {/* Modal Header & Stepper */}
              <div className="bg-white border-b border-border p-4 sm:p-5 flex flex-col gap-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2.5">
                    <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-primary/10 to-secondary/10 text-primary flex items-center justify-center shadow-xs">
                      <Sparkles className="w-4 h-4" />
                    </div>
                    <div>
                      <h3 className="font-semibold text-base sm:text-lg text-foreground">
                        Smart Question Bank Importer
                      </h3>
                      <p className="text-xs text-muted-foreground">
                        No template needed. Accepts DOCX, PDF, CSV, Excel, TXT, and JSON files.
                      </p>
                    </div>
                  </div>
                  <button
                    onClick={() => setShowUploadModal(false)}
                    className="p-1.5 hover:bg-muted rounded-lg text-muted-foreground hover:text-foreground transition-colors cursor-pointer"
                    aria-label="Close"
                  >
                    <X className="w-5 h-5" />
                  </button>
                </div>

                {/* Steps Pill Indicator */}
                <div className="flex items-center gap-2 text-xs font-semibold pt-1">
                  <div
                    className={`flex items-center gap-1.5 px-3 py-1 rounded-full border transition-all ${
                      importStep === "upload"
                        ? "bg-primary text-white border-primary shadow-xs"
                        : "bg-muted/40 text-muted-foreground border-border"
                    }`}
                  >
                    <span className="w-4 h-4 rounded-full bg-white/20 flex items-center justify-center text-[10px]">1</span>
                    Upload & Sniff
                  </div>
                  <span className="text-muted-foreground">→</span>
                  <div
                    className={`flex items-center gap-1.5 px-3 py-1 rounded-full border transition-all ${
                      importStep === "mapping"
                        ? "bg-primary text-white border-primary shadow-xs"
                        : "bg-muted/40 text-muted-foreground border-border"
                    }`}
                  >
                    <span className="w-4 h-4 rounded-full bg-white/20 flex items-center justify-center text-[10px]">2</span>
                    Column Mapping
                  </div>
                  <span className="text-muted-foreground">→</span>
                  <div
                    className={`flex items-center gap-1.5 px-3 py-1 rounded-full border transition-all ${
                      importStep === "preview"
                        ? "bg-primary text-white border-primary shadow-xs"
                        : "bg-muted/40 text-muted-foreground border-border"
                    }`}
                  >
                    <span className="w-4 h-4 rounded-full bg-white/20 flex items-center justify-center text-[10px]">3</span>
                    Preview & Curation ({parsedRows.length})
                  </div>
                </div>
              </div>

              {/* Modal Body */}
              <div className="p-4 sm:p-6 overflow-y-auto flex-1 space-y-4">
                {/* Upload Error Banner */}
                {uploadError && (
                  <div className="p-3.5 rounded-xl border border-rose-200 bg-rose-50 text-rose-800 text-xs flex items-start gap-2.5">
                    <AlertCircle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
                    <div>
                      <span className="font-bold block">Import Diagnostics</span>
                      <span>{uploadError}</span>
                    </div>
                  </div>
                )}

                {/* ================= STEP 1: UPLOAD ================= */}
                {importStep === "upload" && (
                  <div className="space-y-4">
                    {/* Sample Templates Bar */}
                    <div className="p-3.5 bg-slate-50 border border-slate-200 rounded-xl">
                      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                        <div>
                          <span className="text-xs font-bold text-slate-800 block">Optional Standard Templates:</span>
                          <span className="text-[11px] text-slate-500">
                            You do not need to use these, but standard templates are available if preferred.
                          </span>
                        </div>
                        <div className="flex flex-wrap gap-1.5">
                          {(["csv", "xlsx", "docx", "json"] as const).map((fmt) => (
                            <button
                              key={fmt}
                              type="button"
                              onClick={() => handleDownloadTemplate(fmt)}
                              disabled={isDownloadingTemplate === fmt}
                              className="px-2.5 py-1 text-xs font-semibold rounded-md border border-slate-300 bg-white hover:bg-slate-100 text-slate-700 flex items-center gap-1.5 transition-colors shadow-2xs disabled:opacity-50 cursor-pointer"
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
                        Select Any Question Bank File
                      </label>
                      <label className="border-2 border-dashed border-border rounded-xl p-8 flex flex-col items-center justify-center cursor-pointer hover:bg-muted/30 transition-colors">
                        <input
                          type="file"
                          accept=".csv, .xlsx, .docx, .pdf, .txt, .json, text/plain, application/pdf, application/vnd.openxmlformats-officedocument.spreadsheetml.sheet, application/vnd.openxmlformats-officedocument.wordprocessingml.document, text/csv, application/json"
                          onChange={(e) => {
                            if (e.target.files && e.target.files[0]) {
                              handleFileChange(e.target.files[0]);
                            }
                          }}
                          className="hidden"
                        />
                        <Upload className="w-10 h-10 text-primary/60 mb-2" />
                        <span className="text-sm font-semibold text-foreground">
                          {selectedFile ? selectedFile.name : "Click or drag your question document here"}
                        </span>
                        <span className="text-xs text-muted-foreground mt-1">
                          {selectedFile
                            ? `${(selectedFile.size / 1024).toFixed(1)} KB - click to choose a different file`
                            : "Supports DOCX, PDF, CSV, XLSX, TXT, JSON (max 10MB)"}
                        </span>
                      </label>
                    </div>

                    {/* Default values configuration */}
                    <div className="p-4 rounded-xl border border-border bg-slate-50/70 space-y-3">
                      <div className="flex items-center gap-2">
                        <SlidersHorizontal className="w-4 h-4 text-slate-600" />
                        <span className="text-xs font-bold text-slate-800">
                          Fallback Defaults (Applied if missing in file):
                        </span>
                      </div>
                      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                        <div>
                          <label className="block text-[11px] font-semibold text-slate-600 mb-1">
                            Default Marks
                          </label>
                          <input
                            type="number"
                            min="0.5"
                            step="0.5"
                            value={defaultMarks}
                            onChange={(e) => setDefaultMarks(parseFloat(e.target.value) || 1)}
                            className="w-full px-2.5 py-1.5 text-xs rounded-lg border border-border bg-white"
                          />
                        </div>
                        <div>
                          <label className="block text-[11px] font-semibold text-slate-600 mb-1">
                            Default Difficulty
                          </label>
                          <select
                            value={defaultDifficulty}
                            onChange={(e) => setDefaultDifficulty(e.target.value)}
                            className="w-full px-2.5 py-1.5 text-xs rounded-lg border border-border bg-white"
                          >
                            <option value="easy">Easy</option>
                            <option value="medium">Medium</option>
                            <option value="hard">Hard</option>
                          </select>
                        </div>
                        <div>
                          <label className="block text-[11px] font-semibold text-slate-600 mb-1">
                            Question Type
                          </label>
                          <select
                            value={defaultType}
                            onChange={(e) => setDefaultType(e.target.value)}
                            className="w-full px-2.5 py-1.5 text-xs rounded-lg border border-border bg-white"
                          >
                            <option value="auto">Auto-Detect from Text</option>
                            <option value="mcq">Multiple Choice (MCQ)</option>
                            <option value="true_false">True / False</option>
                            <option value="short_answer">Short Answer</option>
                            <option value="long_answer">Long Answer</option>
                          </select>
                        </div>
                      </div>
                    </div>

                    {/* Privacy toggle */}
                    <div className="flex items-center gap-2.5 p-3 rounded-lg border border-border bg-muted/20">
                      <input
                        type="checkbox"
                        id="is_shared_upload_modal"
                        checked={isSharedUpload}
                        onChange={(e) => setIsSharedUpload(e.target.checked)}
                        className="w-4 h-4 rounded text-primary focus:ring-primary border-border"
                      />
                      <label htmlFor="is_shared_upload_modal" className="text-xs font-medium text-foreground cursor-pointer">
                        Share imported questions with other faculty in your department
                      </label>
                    </div>

                    {isAnalyzing && (
                      <div className="p-8 text-center bg-slate-50 border border-slate-200 rounded-xl text-slate-600">
                        <Loader2 className="w-7 h-7 animate-spin mx-auto mb-2 text-primary" />
                        <p className="text-xs font-semibold">
                          Analyzing document structure, detecting options, answers, and formulas...
                        </p>
                      </div>
                    )}
                  </div>
                )}

                {/* ================= STEP 2: COLUMN MAPPING ================= */}
                {importStep === "mapping" && (
                  <div className="space-y-4">
                    <div className="flex items-center justify-between p-3 bg-indigo-50 border border-indigo-200 rounded-xl text-indigo-900 text-xs">
                      <div>
                        <span className="font-bold block">Review Column Matching</span>
                        <span>We detected the following spreadsheet columns. Adjust any mapping if necessary.</span>
                      </div>
                      {analysisResult?.sheet_names && analysisResult.sheet_names.length > 1 && (
                        <div className="flex items-center gap-2">
                          <span className="font-semibold text-xs">Sheet:</span>
                          <select
                            value={selectedSheet}
                            onChange={(e) => handleSheetChange(e.target.value)}
                            className="text-xs px-2 py-1 rounded bg-white border border-indigo-300"
                          >
                            {analysisResult.sheet_names.map((s) => (
                              <option key={s} value={s}>
                                {s}
                              </option>
                            ))}
                          </select>
                        </div>
                      )}
                    </div>

                    <div className="border border-border rounded-xl overflow-hidden">
                      <table className="w-full text-left text-xs">
                        <thead className="bg-muted/50 border-b border-border font-semibold text-muted-foreground">
                          <tr>
                            <th className="p-2.5">Original Column Header</th>
                            <th className="p-2.5">Sample Values</th>
                            <th className="p-2.5">Mapped Field</th>
                            <th className="p-2.5">Match Confidence</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-border">
                          {detectedColumns.map((col) => {
                            const curKey = `col_${col.index}`;
                            const curTarget = columnMappings[curKey] || col.proposed_target || "ignore";
                            return (
                              <tr key={col.index} className="hover:bg-muted/20">
                                <td className="p-2.5 font-bold text-foreground">
                                  {col.original_header || `Column ${col.index + 1}`}
                                </td>
                                <td className="p-2.5 text-muted-foreground max-w-xs truncate">
                                  {col.sample_values?.slice(0, 2).join(", ") || "(empty)"}
                                </td>
                                <td className="p-2.5">
                                  <select
                                    value={curTarget}
                                    onChange={(e) => {
                                      const newVal = e.target.value;
                                      setColumnMappings((prev) => ({ ...prev, [curKey]: newVal }));
                                    }}
                                    className="px-2.5 py-1 text-xs rounded-lg border border-border bg-white"
                                  >
                                    {targetFieldOptions.map((opt) => (
                                      <option key={opt.value} value={opt.value}>
                                        {opt.label}
                                      </option>
                                    ))}
                                  </select>
                                </td>
                                <td className="p-2.5">
                                  <span
                                    className={`px-2 py-0.5 rounded text-[11px] font-bold ${
                                      col.confidence >= 0.8
                                        ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                                        : "bg-amber-50 text-amber-700 border border-amber-200"
                                    }`}
                                  >
                                    {Math.round((col.confidence || 0.7) * 100)}% Match
                                  </span>
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>

                    <div className="flex items-center justify-between pt-2">
                      <button
                        type="button"
                        onClick={() => setImportStep("upload")}
                        className="px-3.5 py-2 rounded-lg border border-border text-xs font-semibold text-foreground hover:bg-muted/50 cursor-pointer flex items-center gap-1.5"
                      >
                        <ArrowLeft className="w-3.5 h-3.5" /> Back to Upload
                      </button>
                      <button
                        type="button"
                        onClick={handleApplyMappings}
                        className="px-4 py-2 rounded-lg bg-primary text-white text-xs font-semibold hover:opacity-90 cursor-pointer flex items-center gap-1.5 shadow-xs"
                      >
                        Preview Mapped Questions <ArrowRight className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>
                )}

                {/* ================= STEP 3: INTERACTIVE PREVIEW & CURATION ================= */}
                {importStep === "preview" && (
                  <div className="space-y-4">
                    {/* Summary Metrics Bar */}
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
                      <div className="p-3 rounded-xl bg-slate-50 border border-slate-200">
                        <div className="text-xl font-bold text-slate-900">{parsedRows.length}</div>
                        <div className="text-[11px] font-semibold text-slate-500">Total Questions</div>
                      </div>
                      <div className="p-3 rounded-xl bg-emerald-50 border border-emerald-200">
                        <div className="text-xl font-bold text-emerald-700">{readyRowsCount}</div>
                        <div className="text-[11px] font-semibold text-emerald-600">Ready to Import</div>
                      </div>
                      <div className="p-3 rounded-xl bg-amber-50 border border-amber-200">
                        <div className="text-xl font-bold text-amber-700">{reviewRowsCount}</div>
                        <div className="text-[11px] font-semibold text-amber-600">Needs Review</div>
                      </div>
                      <div className="p-3 rounded-xl bg-rose-50 border border-rose-200">
                        <div className="text-xl font-bold text-rose-700">{invalidRowsCount}</div>
                        <div className="text-[11px] font-semibold text-rose-600">Invalid Rows</div>
                      </div>
                    </div>

                    {/* Toolbar & Filter Tabs */}
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2.5 pt-1">
                      <div className="flex items-center gap-1 text-xs font-semibold">
                        <button
                          type="button"
                          onClick={() => setPreviewTab("all")}
                          className={`px-3 py-1.5 rounded-lg border transition-all cursor-pointer ${
                            previewTab === "all"
                              ? "bg-slate-900 text-white border-slate-900"
                              : "bg-white text-slate-700 border-border hover:bg-slate-50"
                          }`}
                        >
                          All ({parsedRows.length})
                        </button>
                        <button
                          type="button"
                          onClick={() => setPreviewTab("ready")}
                          className={`px-3 py-1.5 rounded-lg border transition-all cursor-pointer ${
                            previewTab === "ready"
                              ? "bg-emerald-600 text-white border-emerald-600"
                              : "bg-white text-emerald-700 border-border hover:bg-emerald-50/50"
                          }`}
                        >
                          Ready ({readyRowsCount})
                        </button>
                        <button
                          type="button"
                          onClick={() => setPreviewTab("needs_review")}
                          className={`px-3 py-1.5 rounded-lg border transition-all cursor-pointer ${
                            previewTab === "needs_review"
                              ? "bg-amber-600 text-white border-amber-600"
                              : "bg-white text-amber-700 border-border hover:bg-amber-50/50"
                          }`}
                        >
                          Needs Review ({reviewRowsCount})
                        </button>
                        <button
                          type="button"
                          onClick={() => setPreviewTab("invalid")}
                          className={`px-3 py-1.5 rounded-lg border transition-all cursor-pointer ${
                            previewTab === "invalid"
                              ? "bg-rose-600 text-white border-rose-600"
                              : "bg-white text-rose-700 border-border hover:bg-rose-50/50"
                          }`}
                        >
                          Invalid ({invalidRowsCount})
                        </button>
                      </div>

                      <div className="flex items-center gap-2">
                        {reviewRowsCount > 0 && (
                          <button
                            type="button"
                            onClick={handleRunAiAssist}
                            disabled={isAiAssisting}
                            className="px-2.5 py-1.5 rounded-lg border border-purple-200 bg-purple-50 text-purple-700 text-xs font-semibold hover:bg-purple-100 transition-colors flex items-center gap-1 cursor-pointer disabled:opacity-50"
                            title="Use Local Ollama to clarify stems"
                          >
                            {isAiAssisting ? (
                              <Loader2 className="w-3.5 h-3.5 animate-spin" />
                            ) : (
                              <Sparkles className="w-3.5 h-3.5 text-purple-600" />
                            )}
                            AI Assist
                          </button>
                        )}
                        {invalidRowsCount > 0 && (
                          <button
                            type="button"
                            onClick={handleRemoveAllInvalid}
                            className="px-2.5 py-1.5 rounded-lg border border-rose-200 bg-rose-50 text-rose-700 text-xs font-semibold hover:bg-rose-100 transition-colors flex items-center gap-1 cursor-pointer"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                            Remove Invalid
                          </button>
                        )}
                        {reviewRowsCount > 0 && (
                          <button
                            type="button"
                            onClick={handleMarkAllReviewedAsReady}
                            className="px-2.5 py-1.5 rounded-lg border border-emerald-200 bg-emerald-50 text-emerald-700 text-xs font-semibold hover:bg-emerald-100 transition-colors flex items-center gap-1 cursor-pointer"
                          >
                            <Check className="w-3.5 h-3.5" />
                            Mark All Ready
                          </button>
                        )}
                      </div>
                    </div>

                    {/* Search inside preview */}
                    <div className="relative">
                      <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted-foreground" />
                      <input
                        type="text"
                        placeholder="Search questions in this import batch..."
                        value={previewSearch}
                        onChange={(e) => setPreviewSearch(e.target.value)}
                        className="w-full pl-9 pr-3 py-1.5 text-xs rounded-lg border border-border bg-slate-50 focus:bg-white focus:outline-none focus:ring-1 focus:ring-primary"
                      />
                    </div>

                    {/* Questions Preview List */}
                    <div className="space-y-2.5 max-h-[46vh] overflow-y-auto pr-1">
                      {filteredPreviewRows.length === 0 ? (
                        <div className="p-8 text-center text-xs text-muted-foreground border border-dashed border-border rounded-xl">
                          No questions match the current filter or search query.
                        </div>
                      ) : (
                        filteredPreviewRows.map((row, idx) => {
                          const realIdx = parsedRows.indexOf(row);
                          const isMcq = row.data.question_type === "mcq";
                          const opts = Array.isArray(row.data.options) ? row.data.options : [];

                          return (
                            <div
                              key={realIdx}
                              className={`p-3.5 rounded-xl border transition-all ${
                                row.status === "ready"
                                  ? "bg-white border-border/80 hover:border-emerald-300"
                                  : row.status === "needs_review"
                                  ? "bg-amber-50/40 border-amber-200 hover:border-amber-300"
                                  : "bg-rose-50/40 border-rose-200 hover:border-rose-300"
                              }`}
                            >
                              <div className="flex items-start justify-between gap-3">
                                <div className="flex-1 space-y-1.5">
                                  <div className="flex items-center gap-2">
                                    <span className="font-bold text-xs text-slate-800">
                                      #{row.row_number || realIdx + 1}
                                    </span>
                                    {row.status === "ready" ? (
                                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">
                                        <Check className="w-3 h-3" /> Ready
                                      </span>
                                    ) : row.status === "needs_review" ? (
                                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold bg-amber-50 text-amber-800 border border-amber-200">
                                        <AlertTriangle className="w-3 h-3 text-amber-600" /> Needs Review
                                      </span>
                                    ) : (
                                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold bg-rose-50 text-rose-700 border border-rose-200">
                                        <AlertCircle className="w-3 h-3" /> Invalid
                                      </span>
                                    )}
                                    <span className="px-1.5 py-0.5 rounded text-[10px] uppercase font-bold bg-slate-100 text-slate-700">
                                      {row.data.question_type || "MCQ"}
                                    </span>
                                    <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-indigo-50 text-indigo-700">
                                      {row.data.marks} {row.data.marks === 1 ? "Mark" : "Marks"}
                                    </span>
                                  </div>

                                  <p className="text-xs font-medium text-foreground whitespace-pre-wrap">
                                    {row.data.question_text}
                                  </p>

                                  {/* Review Notes or Errors */}
                                  {row.errors && row.errors.length > 0 && (
                                    <div className="text-[11px] text-rose-600 font-medium">
                                      Errors: {row.errors.join("; ")}
                                    </div>
                                  )}
                                  {row.warnings && row.warnings.length > 0 && (
                                    <div className="text-[11px] text-amber-700 font-medium">
                                      Note: {row.warnings.join("; ")}
                                    </div>
                                  )}

                                  {/* MCQ Options with One-Click Answer Toggle */}
                                  {isMcq && opts.length > 0 && (
                                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-1.5 pt-1">
                                      {opts.map((opt: any, oIdx: number) => {
                                        const optText = typeof opt === "string" ? opt : opt?.text || "";
                                        const letter = String.fromCharCode(65 + oIdx);
                                        const isSelected =
                                          (row.data.correct_answer && row.data.correct_answer.toUpperCase() === letter) ||
                                          (row.data.correct_answer && row.data.correct_answer === optText) ||
                                          (typeof opt === "object" && opt.is_correct);

                                        return (
                                          <button
                                            key={oIdx}
                                            type="button"
                                            onClick={() => handleSelectOptionAnswer(realIdx, optText, oIdx + 1)}
                                            className={`p-1.5 rounded-lg border text-left text-xs flex items-center justify-between transition-colors cursor-pointer ${
                                              isSelected
                                                ? "bg-emerald-50 text-emerald-900 border-emerald-300 font-semibold"
                                                : "bg-slate-50 text-slate-700 border-border/70 hover:bg-slate-100"
                                            }`}
                                          >
                                            <span className="truncate pr-2">
                                              <span className="font-bold mr-1">{letter}.</span> {optText}
                                            </span>
                                            {isSelected && (
                                              <span className="shrink-0 flex items-center gap-1 text-[10px] text-emerald-700 font-bold">
                                                <Check className="w-3 h-3" /> Correct
                                              </span>
                                            )}
                                          </button>
                                        );
                                      })}
                                    </div>
                                  )}

                                  {/* Non-MCQ Answer Preview */}
                                  {!isMcq && (row.data.correct_answer || row.data.model_answer) && (
                                    <div className="text-xs text-slate-600 bg-slate-50 p-2 rounded-lg border border-slate-200">
                                      <span className="font-bold text-slate-800">Answer:</span>{" "}
                                      {row.data.correct_answer || row.data.model_answer}
                                    </div>
                                  )}
                                </div>

                                {/* Row Actions */}
                                <div className="flex items-center gap-1 shrink-0 pt-0.5">
                                  <button
                                    type="button"
                                    onClick={() => handleStartEditRow(realIdx)}
                                    className="p-1.5 rounded hover:bg-slate-100 text-slate-600 hover:text-slate-900 transition-colors cursor-pointer"
                                    title="Edit Question Stem & Options"
                                  >
                                    <Edit3 className="w-3.5 h-3.5" />
                                  </button>
                                  <button
                                    type="button"
                                    onClick={() => handleDeleteRow(realIdx)}
                                    className="p-1.5 rounded hover:bg-rose-50 text-slate-400 hover:text-rose-600 transition-colors cursor-pointer"
                                    title="Delete from batch"
                                  >
                                    <Trash2 className="w-3.5 h-3.5" />
                                  </button>
                                </div>
                              </div>
                            </div>
                          );
                        })
                      )}
                    </div>

                    {/* Step 3 Action Footer */}
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pt-3 border-t border-border">
                      <div className="flex items-center gap-2">
                        <button
                          type="button"
                          onClick={handleExportErrorReport}
                          disabled={isExporting}
                          className="px-3 py-1.5 text-xs font-semibold rounded-lg border border-border bg-white hover:bg-slate-50 text-slate-700 flex items-center gap-1.5 transition-colors cursor-pointer"
                          title="Download CSV report of skipped/needs_review questions"
                        >
                          <Download className="w-3.5 h-3.5" />
                          Diagnostic CSV
                        </button>
                        <button
                          type="button"
                          onClick={handleExportCleanedXlsx}
                          disabled={isExporting}
                          className="px-3 py-1.5 text-xs font-semibold rounded-lg border border-border bg-white hover:bg-slate-50 text-slate-700 flex items-center gap-1.5 transition-colors cursor-pointer"
                          title="Export normalized question bank as standard XLSX"
                        >
                          <FileSpreadsheet className="w-3.5 h-3.5 text-emerald-600" />
                          Export Cleaned XLSX
                        </button>
                      </div>

                      <div className="flex items-center gap-2">
                        <button
                          type="button"
                          onClick={() => setImportStep("upload")}
                          className="px-3.5 py-1.5 text-xs font-semibold rounded-lg border border-border text-foreground hover:bg-slate-100 cursor-pointer"
                        >
                          Re-upload File
                        </button>
                        {reviewRowsCount > 0 && (
                          <button
                            type="button"
                            onClick={() => handleCommitQuestions("ready_and_reviewed")}
                            disabled={isImporting || readyRowsCount + reviewRowsCount === 0}
                            className="px-3.5 py-1.5 text-xs font-semibold rounded-lg border border-amber-300 bg-amber-50 text-amber-900 hover:bg-amber-100 cursor-pointer disabled:opacity-50"
                          >
                            Import Ready + Reviewed ({readyRowsCount + reviewRowsCount})
                          </button>
                        )}
                        <button
                          type="button"
                          onClick={() => handleCommitQuestions("ready_only")}
                          disabled={isImporting || readyRowsCount === 0}
                          className="px-4 py-1.5 text-xs font-bold rounded-lg bg-gradient-to-r from-primary to-secondary text-white hover:opacity-90 shadow-md cursor-pointer disabled:opacity-50 flex items-center gap-1.5"
                        >
                          {isImporting ? (
                            <>
                              <Loader2 className="w-3.5 h-3.5 animate-spin" /> Importing...
                            </>
                          ) : (
                            <>
                              <CheckCircle2 className="w-3.5 h-3.5" /> Import {readyRowsCount} Ready Questions
                            </>
                          )}
                        </button>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* ================= EDIT ROW MODAL ================= */}
        {editingRowIndex !== null && editDraft && (
          <div className="fixed inset-0 bg-black/50 backdrop-blur-2xs flex items-center justify-center z-60 p-4">
            <div className="bg-white rounded-2xl w-full max-w-xl max-h-[90vh] overflow-hidden border border-border shadow-2xl flex flex-col">
              <div className="p-4 border-b border-border flex items-center justify-between bg-slate-50">
                <span className="font-bold text-sm text-slate-800">
                  Edit Question #{editingRowIndex + 1}
                </span>
                <button
                  type="button"
                  onClick={() => {
                    setEditingRowIndex(null);
                    setEditDraft(null);
                  }}
                  className="p-1 rounded text-slate-400 hover:text-slate-700 cursor-pointer"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>

              <div className="p-4 overflow-y-auto space-y-3 text-xs flex-1">
                <div>
                  <label className="block font-semibold text-slate-700 mb-1">Question Stem</label>
                  <textarea
                    rows={3}
                    value={editDraft.data.question_text}
                    onChange={(e) =>
                      setEditDraft((prev: any) => ({
                        ...prev,
                        data: { ...prev.data, question_text: e.target.value },
                      }))
                    }
                    className="w-full p-2 rounded-lg border border-border bg-white text-xs font-medium"
                  />
                </div>

                <div className="grid grid-cols-3 gap-2">
                  <div>
                    <label className="block font-semibold text-slate-700 mb-1">Type</label>
                    <select
                      value={editDraft.data.question_type}
                      onChange={(e) =>
                        setEditDraft((prev: any) => ({
                          ...prev,
                          data: { ...prev.data, question_type: e.target.value },
                        }))
                      }
                      className="w-full p-1.5 rounded-lg border border-border bg-white text-xs"
                    >
                      <option value="mcq">MCQ</option>
                      <option value="true_false">True / False</option>
                      <option value="short_answer">Short Answer</option>
                      <option value="long_answer">Long Answer</option>
                      <option value="fill_blank">Fill in Blank</option>
                    </select>
                  </div>
                  <div>
                    <label className="block font-semibold text-slate-700 mb-1">Marks</label>
                    <input
                      type="number"
                      step="0.5"
                      min="0.5"
                      value={editDraft.data.marks}
                      onChange={(e) =>
                        setEditDraft((prev: any) => ({
                          ...prev,
                          data: { ...prev.data, marks: parseFloat(e.target.value) || 1 },
                        }))
                      }
                      className="w-full p-1.5 rounded-lg border border-border bg-white text-xs"
                    />
                  </div>
                  <div>
                    <label className="block font-semibold text-slate-700 mb-1">Difficulty</label>
                    <select
                      value={editDraft.data.difficulty}
                      onChange={(e) =>
                        setEditDraft((prev: any) => ({
                          ...prev,
                          data: { ...prev.data, difficulty: e.target.value },
                        }))
                      }
                      className="w-full p-1.5 rounded-lg border border-border bg-white text-xs"
                    >
                      <option value="easy">Easy</option>
                      <option value="medium">Medium</option>
                      <option value="hard">Hard</option>
                    </select>
                  </div>
                </div>

                {/* MCQ Options Edit */}
                {editDraft.data.question_type === "mcq" && (
                  <div className="space-y-2 pt-1">
                    <label className="block font-semibold text-slate-700">Options & Correct Answer</label>
                    {(Array.isArray(editDraft.data.options) ? editDraft.data.options : []).map(
                      (opt: any, oIdx: number) => {
                        const optText = typeof opt === "string" ? opt : opt?.text || "";
                        const letter = String.fromCharCode(65 + oIdx);
                        const isCorrect =
                          editDraft.data.correct_answer === letter ||
                          editDraft.data.correct_answer === optText ||
                          (typeof opt === "object" && opt.is_correct);

                        return (
                          <div key={oIdx} className="flex items-center gap-2">
                            <input
                              type="radio"
                              name="edit_correct_answer"
                              checked={isCorrect}
                              onChange={() => {
                                setEditDraft((prev: any) => ({
                                  ...prev,
                                  data: {
                                    ...prev.data,
                                    correct_answer: letter,
                                    options: (prev.data.options || []).map((o: any, idx: number) => ({
                                      ...(typeof o === "object" ? o : { text: o }),
                                      is_correct: idx === oIdx,
                                      order: idx + 1,
                                    })),
                                  },
                                }));
                              }}
                              className="w-3.5 h-3.5 text-primary"
                            />
                            <span className="font-bold text-slate-600 w-4">{letter}.</span>
                            <input
                              type="text"
                              value={optText}
                              onChange={(e) => {
                                const newText = e.target.value;
                                setEditDraft((prev: any) => {
                                  const newOpts = [...(prev.data.options || [])];
                                  newOpts[oIdx] =
                                    typeof newOpts[oIdx] === "object"
                                      ? { ...newOpts[oIdx], text: newText }
                                      : newText;
                                  return {
                                    ...prev,
                                    data: { ...prev.data, options: newOpts },
                                  };
                                });
                              }}
                              className="flex-1 p-1.5 rounded-md border border-border bg-white text-xs"
                            />
                          </div>
                        );
                      }
                    )}
                  </div>
                )}

                {/* Non-MCQ Correct Answer */}
                {editDraft.data.question_type !== "mcq" && (
                  <div>
                    <label className="block font-semibold text-slate-700 mb-1">
                      Correct Answer / Model Answer
                    </label>
                    <input
                      type="text"
                      value={editDraft.data.correct_answer || editDraft.data.model_answer || ""}
                      onChange={(e) =>
                        setEditDraft((prev: any) => ({
                          ...prev,
                          data: {
                            ...prev.data,
                            correct_answer: e.target.value,
                            model_answer: e.target.value,
                          },
                        }))
                      }
                      className="w-full p-2 rounded-lg border border-border bg-white text-xs"
                    />
                  </div>
                )}

                <div>
                  <label className="block font-semibold text-slate-700 mb-1">Explanation (Optional)</label>
                  <input
                    type="text"
                    value={editDraft.data.explanation || ""}
                    onChange={(e) =>
                      setEditDraft((prev: any) => ({
                        ...prev,
                        data: { ...prev.data, explanation: e.target.value },
                      }))
                    }
                    className="w-full p-2 rounded-lg border border-border bg-white text-xs"
                  />
                </div>
              </div>

              <div className="p-3 border-t border-border flex items-center justify-end gap-2 bg-slate-50">
                <button
                  type="button"
                  onClick={() => {
                    setEditingRowIndex(null);
                    setEditDraft(null);
                  }}
                  className="px-3 py-1.5 rounded-lg border border-border text-xs font-semibold text-slate-600 hover:bg-slate-200 cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={handleSaveRowEdit}
                  className="px-4 py-1.5 rounded-lg bg-primary text-white text-xs font-semibold hover:opacity-90 shadow-xs cursor-pointer"
                >
                  Save Changes
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}

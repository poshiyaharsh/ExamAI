import React, { useState, useEffect, useCallback, useMemo } from "react";
import { DashboardLayout } from "../components/DashboardLayout";
import {
  Plus,
  Search,
  Upload,
  Download,
  Trash2,
  Edit2,
  Copy,
  Eye,
  CheckCircle,
  AlertTriangle,
  X,
  FileSpreadsheet,
  Filter,
  RefreshCw,
  ChevronLeft,
  ChevronRight,
  BookOpen,
  Layers,
  HelpCircle,
  Archive,
  Check,
  FileText,
} from "lucide-react";
import {
  questionBankApi,
  BankQuestion,
  BankQuestionDetail,
  BankSubject,
  BankTopic,
  QuestionBankStats,
  QuestionImportReportRow,
  QuestionImportResponse,
} from "../../services/api";

const QUESTION_TYPES = [
  { value: "MCQ_SINGLE", label: "MCQ (Single Choice)" },
  { value: "MCQ_MULTIPLE", label: "MCQ (Multiple Choice)" },
  { value: "TRUE_FALSE", label: "True / False" },
  { value: "SHORT_ANSWER", label: "Short Answer" },
  { value: "LONG_ANSWER", label: "Long Answer" },
];

const DIFFICULTIES = ["EASY", "MEDIUM", "HARD"];
const STATUSES = ["ACTIVE", "DRAFT", "ARCHIVED"];

export function AdminQuestionBank() {
  // Stats
  const [stats, setStats] = useState<QuestionBankStats | null>(null);
  const [statsLoading, setStatsLoading] = useState(false);

  // Questions List & Pagination
  const [questions, setQuestions] = useState<BankQuestion[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [totalCount, setTotalCount] = useState(0);
  const [totalPages, setTotalPages] = useState(1);
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);

  // Filters & Search
  const [searchQuery, setSearchQuery] = useState("");
  const [filterSubject, setFilterSubject] = useState("");
  const [filterTopic, setFilterTopic] = useState("");
  const [filterDifficulty, setFilterDifficulty] = useState("all");
  const [filterType, setFilterType] = useState("all");
  const [filterStatus, setFilterStatus] = useState("all");
  const [filterUsed, setFilterUsed] = useState("all");
  const [sortBy, setSortBy] = useState("newest");

  // Reference Data
  const [subjects, setSubjects] = useState<BankSubject[]>([]);
  const [topics, setTopics] = useState<BankTopic[]>([]);

  // Selection
  const [selectedIds, setSelectedIds] = useState<number[]>([]);

  // Modals
  const [showAddModal, setShowAddModal] = useState(false);
  const [editingQuestionId, setEditingQuestionId] = useState<number | null>(null);
  const [showDetailModal, setShowDetailModal] = useState(false);
  const [detailQuestion, setDetailQuestion] = useState<BankQuestionDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [showImportModal, setShowImportModal] = useState(false);
  const [showSubjectsModal, setShowSubjectsModal] = useState(false);

  // Question Form State
  const [formData, setFormData] = useState<{
    text: string;
    department: string;
    subject: number | "";
    topic: number | "";
    topic_name: string;
    question_type: string;
    difficulty: string;
    marks: number;
    negative_marks: number;
    explanation: string;
    model_answer: string;
    status: string;
    tags: string;
    options: Array<{ text: string; is_correct: boolean; order: number }>;
  }>({
    text: "",
    department: "Computer Science",
    subject: "",
    topic: "",
    topic_name: "",
    question_type: "MCQ_SINGLE",
    difficulty: "MEDIUM",
    marks: 1.0,
    negative_marks: 0.0,
    explanation: "",
    model_answer: "",
    status: "ACTIVE",
    tags: "",
    options: [
      { text: "", is_correct: true, order: 1 },
      { text: "", is_correct: false, order: 2 },
      { text: "", is_correct: false, order: 3 },
      { text: "", is_correct: false, order: 4 },
    ],
  });

  const [formErrors, setFormErrors] = useState<Record<string, string>>({});
  const [formSubmitting, setFormSubmitting] = useState(false);
  const [formWarnings, setFormWarnings] = useState<string[]>([]);

  // Import State
  const [importFile, setImportFile] = useState<File | null>(null);
  const [importDryRunLoading, setImportDryRunLoading] = useState(false);
  const [importCommitLoading, setImportCommitLoading] = useState(false);
  const [importReport, setImportReport] = useState<QuestionImportResponse | null>(null);
  const [importMode, setImportMode] = useState<"all_or_nothing" | "valid_only">("all_or_nothing");

  // Feedback notifications
  const [toastMessage, setToastMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

  const showToast = useCallback((text: string, type: "success" | "error" = "success") => {
    setToastMessage({ type, text });
    setTimeout(() => setToastMessage(null), 4000);
  }, []);

  // Fetch Reference Data
  const loadReferenceData = useCallback(async () => {
    try {
      const [subs, tops] = await Promise.all([
        questionBankApi.getSubjects(),
        questionBankApi.getTopics(),
      ]);
      setSubjects(subs);
      setTopics(tops);
      if (subs.length > 0 && formData.subject === "") {
        setFormData((prev) => ({ ...prev, subject: subs[0].id }));
      }
    } catch (err: any) {
      console.error("Failed to load subjects/topics:", err);
    }
  }, [formData.subject]);

  // Fetch Stats
  const loadStats = useCallback(async () => {
    setStatsLoading(true);
    try {
      const data = await questionBankApi.getStats();
      setStats(data);
    } catch (err: any) {
      console.error("Failed to load question stats:", err);
    } finally {
      setStatsLoading(false);
    }
  }, []);

  // Fetch Questions
  const loadQuestions = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params: Record<string, any> = {
        page: currentPage,
        page_size: pageSize,
        ordering: sortBy,
      };
      if (searchQuery.trim()) params.search = searchQuery.trim();
      if (filterSubject) params.subject = filterSubject;
      if (filterTopic) params.topic = filterTopic;
      if (filterDifficulty !== "all") params.difficulty = filterDifficulty;
      if (filterType !== "all") params.type = filterType;
      if (filterStatus !== "all") params.status = filterStatus;
      if (filterUsed !== "all") params.used = filterUsed === "used";

      const data = await questionBankApi.getQuestions(params);
      setQuestions(data.results);
      setTotalCount(data.count);
      setTotalPages(data.total_pages || 1);
    } catch (err: any) {
      const msg = err.response?.data?.detail || "Failed to load questions. Please check your network.";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, [currentPage, pageSize, sortBy, searchQuery, filterSubject, filterTopic, filterDifficulty, filterType, filterStatus, filterUsed]);

  useEffect(() => {
    loadReferenceData();
    loadStats();
  }, [loadReferenceData, loadStats]);

  useEffect(() => {
    loadQuestions();
  }, [loadQuestions]);

  // Filtered topics for form
  const availableFormTopics = useMemo(() => {
    if (!formData.subject) return topics;
    return topics.filter((t) => t.subject === Number(formData.subject));
  }, [topics, formData.subject]);

  // Filtered topics for list filter
  const availableFilterTopics = useMemo(() => {
    if (!filterSubject) return topics;
    return topics.filter((t) => t.subject === Number(filterSubject));
  }, [topics, filterSubject]);

  // Open Add Modal
  const handleOpenAddModal = () => {
    setEditingQuestionId(null);
    setFormErrors({});
    setFormWarnings([]);
    setFormData({
      text: "",
      department: "Computer Science",
      subject: subjects.length > 0 ? subjects[0].id : "",
      topic: "",
      topic_name: "",
      question_type: "MCQ_SINGLE",
      difficulty: "MEDIUM",
      marks: 1.0,
      negative_marks: 0.0,
      explanation: "",
      model_answer: "",
      status: "ACTIVE",
      tags: "",
      options: [
        { text: "", is_correct: true, order: 1 },
        { text: "", is_correct: false, order: 2 },
        { text: "", is_correct: false, order: 3 },
        { text: "", is_correct: false, order: 4 },
      ],
    });
    setShowAddModal(true);
  };

  // Open Edit Modal
  const handleOpenEditModal = async (q: BankQuestion) => {
    setEditingQuestionId(q.id);
    setFormErrors({});
    setFormWarnings([]);
    try {
      const detail = await questionBankApi.getQuestion(q.id);
      setFormData({
        text: detail.text,
        department: detail.department || "Computer Science",
        subject: detail.subject,
        topic: detail.topic || "",
        topic_name: detail.topic_name || "",
        question_type: detail.question_type,
        difficulty: detail.difficulty,
        marks: Number(detail.marks) || 1.0,
        negative_marks: Number(detail.negative_marks) || 0.0,
        explanation: detail.explanation || "",
        model_answer: detail.model_answer || "",
        status: detail.status,
        tags: (detail.tags || []).join(", "),
        options: (detail.options && detail.options.length > 0)
          ? detail.options.map((o, idx) => ({ text: o.text, is_correct: o.is_correct, order: o.order || idx + 1 }))
          : [
              { text: "", is_correct: true, order: 1 },
              { text: "", is_correct: false, order: 2 },
            ],
      });
      setShowAddModal(true);
    } catch (err: any) {
      showToast("Failed to load question details for editing", "error");
    }
  };

  // Save Question Form
  const handleSaveQuestion = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormErrors({});
    setFormWarnings([]);

    // Client-side quick check
    const errors: Record<string, string> = {};
    if (!formData.text.trim()) errors.text = "Question text is required.";
    else if (formData.text.trim().length < 10) errors.text = "Question text must be at least 10 characters.";

    if (!formData.subject) errors.subject = "Subject is required.";
    if (formData.marks <= 0) errors.marks = "Marks must be greater than 0.";
    if (formData.negative_marks < 0) errors.negative_marks = "Negative marks cannot be negative.";
    if (formData.negative_marks > formData.marks) errors.negative_marks = "Negative marks cannot exceed positive marks.";

    if (formData.question_type.startsWith("MCQ") || formData.question_type === "TRUE_FALSE") {
      const correctCount = formData.options.filter((o) => o.is_correct).length;
      if (formData.question_type === "MCQ_SINGLE" && correctCount !== 1) {
        errors.options = "Single choice MCQ must have exactly 1 correct option.";
      } else if (formData.question_type === "MCQ_MULTIPLE" && (correctCount < 1 || correctCount === formData.options.length)) {
        errors.options = "Multiple choice MCQ must have at least 1 correct option, but not all.";
      } else if (formData.question_type === "TRUE_FALSE" && correctCount !== 1) {
        errors.options = "True/False must have exactly 1 correct option.";
      }
    } else if (formData.question_type.includes("ANSWER")) {
      if (!formData.model_answer.trim()) errors.model_answer = "Model answer is required for subjective questions.";
    }

    if (Object.keys(errors).length > 0) {
      setFormErrors(errors);
      return;
    }

    setFormSubmitting(true);
    try {
      const payload: any = {
        text: formData.text.trim(),
        department: formData.department,
        subject: Number(formData.subject),
        topic: formData.topic ? Number(formData.topic) : null,
        topic_name: formData.topic_name,
        question_type: formData.question_type,
        difficulty: formData.difficulty,
        marks: formData.marks,
        negative_marks: formData.negative_marks,
        explanation: formData.explanation.trim(),
        model_answer: formData.model_answer.trim(),
        status: formData.status,
        tags: formData.tags.split(",").map((t) => t.trim()).filter(Boolean),
        options: (formData.question_type.startsWith("MCQ") || formData.question_type === "TRUE_FALSE")
          ? formData.options.map((o, idx) => ({ text: o.text.trim(), is_correct: o.is_correct, order: idx + 1 }))
          : [],
      };

      if (editingQuestionId) {
        const res = await questionBankApi.updateQuestion(editingQuestionId, payload);
        showToast("Question updated successfully!");
        if (res.warnings && res.warnings.length > 0) {
          setFormWarnings(res.warnings);
        }
      } else {
        const res = await questionBankApi.createQuestion(payload);
        showToast("Question created successfully!");
        if (res.warnings && res.warnings.length > 0) {
          setFormWarnings(res.warnings);
        }
      }

      setShowAddModal(false);
      loadQuestions();
      loadStats();
    } catch (err: any) {
      const respData = err.response?.data;
      if (respData) {
        const backendErrors: Record<string, string> = {};
        for (const [key, val] of Object.entries(respData)) {
          backendErrors[key] = Array.isArray(val) ? val.join(" ") : String(val);
        }
        setFormErrors(backendErrors);
      } else {
        showToast("An unexpected error occurred while saving.", "error");
      }
    } finally {
      setFormSubmitting(false);
    }
  };

  // View Details Modal
  const handleViewDetail = async (id: number) => {
    setDetailLoading(true);
    setShowDetailModal(true);
    try {
      const data = await questionBankApi.getQuestion(id);
      setDetailQuestion(data);
    } catch (err: any) {
      showToast("Failed to load question details", "error");
      setShowDetailModal(false);
    } finally {
      setDetailLoading(false);
    }
  };

  // Duplicate Question
  const handleDuplicate = async (id: number) => {
    try {
      await questionBankApi.duplicateQuestion(id);
      showToast("Question duplicated as Draft!");
      loadQuestions();
      loadStats();
    } catch (err: any) {
      showToast(err.response?.data?.detail || "Failed to duplicate question", "error");
    }
  };

  // Delete Question
  const handleDelete = async (id: number) => {
    if (!window.confirm("Are you sure you want to delete this question? It will be soft-deleted.")) return;
    try {
      await questionBankApi.deleteQuestion(id);
      showToast("Question deleted successfully!");
      loadQuestions();
      loadStats();
    } catch (err: any) {
      showToast(err.response?.data?.detail || "Failed to delete question", "error");
    }
  };

  // Bulk Actions
  const handleBulkAction = async (action: string, targetValue?: string) => {
    if (selectedIds.length === 0) return;
    if (action === "delete" && !window.confirm(`Are you sure you want to delete ${selectedIds.length} question(s)?`)) return;

    try {
      const res = await questionBankApi.bulkAction(action, selectedIds, targetValue);
      showToast(res.message);
      setSelectedIds([]);
      loadQuestions();
      loadStats();
    } catch (err: any) {
      showToast(err.response?.data?.detail || "Bulk action failed", "error");
    }
  };

  // Export Download
  const handleExport = async (format: "csv" | "xlsx") => {
    try {
      const blob = await questionBankApi.downloadExport(format, {
        subject: filterSubject,
        topic: filterTopic,
        difficulty: filterDifficulty !== "all" ? filterDifficulty : undefined,
        type: filterType !== "all" ? filterType : undefined,
        status: filterStatus !== "all" ? filterStatus : undefined,
        search: searchQuery || undefined,
      });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `question_bank_export.${format}`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
      showToast(`Exported ${format.toUpperCase()} successfully!`);
    } catch (err: any) {
      showToast("Failed to export questions", "error");
    }
  };

  // Download Template
  const handleDownloadTemplate = async (format: "csv" | "xlsx") => {
    try {
      const blob = await questionBankApi.downloadTemplate(format);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `question_import_template.${format}`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (err: any) {
      showToast("Failed to download template", "error");
    }
  };

  // Dry-run Import
  const handleDryRunImport = async () => {
    if (!importFile) return;
    setImportDryRunLoading(true);
    setImportReport(null);
    try {
      const res = await questionBankApi.bulkImport(importFile, true, importMode);
      setImportReport(res);
      showToast(`Validation check complete: ${res.valid_count} valid, ${res.failed_count} errors.`);
    } catch (err: any) {
      const msg = err.response?.data?.file || err.response?.data?.detail || "Validation failed";
      showToast(msg, "error");
    } finally {
      setImportDryRunLoading(false);
    }
  };

  // Commit Import
  const handleCommitImport = async () => {
    if (!importFile) return;
    setImportCommitLoading(true);
    try {
      const res = await questionBankApi.bulkImport(importFile, false, importMode);
      showToast(`Imported ${res.imported_count ?? 0} questions successfully!`);
      setShowImportModal(false);
      setImportFile(null);
      setImportReport(null);
      loadQuestions();
      loadStats();
    } catch (err: any) {
      const msg = err.response?.data?.detail || err.response?.data?.file || "Import failed";
      showToast(msg, "error");
    } finally {
      setImportCommitLoading(false);
    }
  };

  // Select All Checkbox
  const allSelected = questions.length > 0 && selectedIds.length === questions.length;
  const toggleSelectAll = () => {
    if (allSelected) setSelectedIds([]);
    else setSelectedIds(questions.map((q) => q.id));
  };

  const toggleSelectId = (id: number) => {
    setSelectedIds((prev) => (prev.includes(id) ? prev.filter((i) => i !== id) : [...prev, id]));
  };

  return (
    <DashboardLayout userRole="Admin">
      <div className="space-y-6">
        {/* Toast Notification */}
        {toastMessage && (
          <div
            className={`fixed top-5 right-5 z-50 px-4 py-3 rounded-xl shadow-lg border flex items-center gap-3 transition-all ${
              toastMessage.type === "success"
                ? "bg-emerald-50 border-emerald-300 text-emerald-800"
                : "bg-rose-50 border-rose-300 text-rose-800"
            }`}
          >
            {toastMessage.type === "success" ? (
              <CheckCircle className="w-5 h-5 text-emerald-600" />
            ) : (
              <AlertTriangle className="w-5 h-5 text-rose-600" />
            )}
            <span className="text-sm font-medium">{toastMessage.text}</span>
            <button onClick={() => setToastMessage(null)} className="ml-2 text-muted-foreground hover:opacity-75">
              <X className="w-4 h-4" />
            </button>
          </div>
        )}

        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="text-2xl sm:text-3xl font-bold text-foreground tracking-tight">Question Bank</h1>
            <p className="text-sm text-muted-foreground mt-1">
              Centralized, multi-tenant repository of validated questions for examinations
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2.5">
            <button
              onClick={() => setShowSubjectsModal(true)}
              className="px-3.5 py-2 rounded-lg border border-border bg-white text-foreground hover:bg-muted text-sm font-medium transition-colors flex items-center gap-2 shadow-sm"
            >
              <BookOpen className="w-4 h-4 text-primary" />
              Subjects & Topics
            </button>
            <div className="relative group">
              <button
                onClick={() => handleExport("csv")}
                className="px-3.5 py-2 rounded-lg border border-border bg-white text-foreground hover:bg-muted text-sm font-medium transition-colors flex items-center gap-2 shadow-sm"
              >
                <Download className="w-4 h-4 text-emerald-600" />
                Export CSV
              </button>
            </div>
            <button
              onClick={() => setShowImportModal(true)}
              className="px-3.5 py-2 rounded-lg border border-border bg-white text-foreground hover:bg-muted text-sm font-medium transition-colors flex items-center gap-2 shadow-sm"
            >
              <Upload className="w-4 h-4 text-sky-600" />
              Bulk Import
            </button>
            <button
              onClick={handleOpenAddModal}
              className="px-4 py-2 rounded-lg bg-gradient-to-r from-primary to-secondary text-white hover:opacity-95 shadow-md font-medium text-sm transition-all flex items-center gap-2"
            >
              <Plus className="w-4 h-4" />
              Add Question
            </button>
          </div>
        </div>

        {/* Stats Header */}
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3.5">
          <div className="bg-white rounded-xl p-4 shadow-sm border border-border">
            <div className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Total Questions</div>
            <div className="text-2xl font-bold text-foreground mt-1">{stats?.total_questions ?? "—"}</div>
            <div className="text-xs text-muted-foreground mt-0.5">{stats?.unused_count ?? 0} unused in exams</div>
          </div>
          <div className="bg-white rounded-xl p-4 shadow-sm border border-border">
            <div className="text-xs font-medium text-emerald-700 uppercase tracking-wider">Easy</div>
            <div className="text-2xl font-bold text-emerald-600 mt-1">{stats?.by_difficulty?.Easy ?? 0}</div>
            <div className="text-xs text-muted-foreground mt-0.5">Foundational questions</div>
          </div>
          <div className="bg-white rounded-xl p-4 shadow-sm border border-border">
            <div className="text-xs font-medium text-amber-700 uppercase tracking-wider">Medium</div>
            <div className="text-2xl font-bold text-amber-600 mt-1">{stats?.by_difficulty?.Medium ?? 0}</div>
            <div className="text-xs text-muted-foreground mt-0.5">Core difficulty</div>
          </div>
          <div className="bg-white rounded-xl p-4 shadow-sm border border-border">
            <div className="text-xs font-medium text-rose-700 uppercase tracking-wider">Hard</div>
            <div className="text-2xl font-bold text-rose-600 mt-1">{stats?.by_difficulty?.Hard ?? 0}</div>
            <div className="text-xs text-muted-foreground mt-0.5">Advanced difficulty</div>
          </div>
          <div className="bg-white rounded-xl p-4 shadow-sm border border-border col-span-2 md:col-span-1">
            <div className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Status</div>
            <div className="flex items-center gap-2 mt-1">
              <span className="px-2 py-0.5 rounded text-xs font-semibold bg-emerald-100 text-emerald-800">
                {stats?.by_status?.Active ?? 0} Active
              </span>
              <span className="px-2 py-0.5 rounded text-xs font-semibold bg-slate-100 text-slate-700">
                {stats?.by_status?.Draft ?? 0} Draft
              </span>
            </div>
            <div className="text-xs text-muted-foreground mt-1">{stats?.by_status?.Archived ?? 0} archived</div>
          </div>
        </div>

        {/* Search & Filters */}
        <div className="bg-white rounded-xl p-4 shadow-sm border border-border space-y-3">
          <div className="flex flex-col md:flex-row gap-3">
            <div className="flex-1 relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
              <input
                type="text"
                placeholder="Search questions by text, tag, or topic..."
                value={searchQuery}
                onChange={(e) => {
                  setSearchQuery(e.target.value);
                  setCurrentPage(1);
                }}
                className="w-full pl-9 pr-4 py-2 rounded-lg bg-input-background border border-border text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
              />
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-4 md:grid-cols-5 gap-2">
              <select
                value={filterSubject}
                onChange={(e) => {
                  setFilterSubject(e.target.value);
                  setFilterTopic("");
                  setCurrentPage(1);
                }}
                className="px-3 py-2 rounded-lg bg-input-background border border-border text-xs sm:text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
              >
                <option value="">All Subjects</option>
                {subjects.map((sub) => (
                  <option key={sub.id} value={sub.id}>
                    {sub.name} ({sub.question_count})
                  </option>
                ))}
              </select>

              <select
                value={filterTopic}
                onChange={(e) => {
                  setFilterTopic(e.target.value);
                  setCurrentPage(1);
                }}
                className="px-3 py-2 rounded-lg bg-input-background border border-border text-xs sm:text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
              >
                <option value="">All Topics</option>
                {availableFilterTopics.map((top) => (
                  <option key={top.id} value={top.id}>
                    {top.name}
                  </option>
                ))}
              </select>

              <select
                value={filterDifficulty}
                onChange={(e) => {
                  setFilterDifficulty(e.target.value);
                  setCurrentPage(1);
                }}
                className="px-3 py-2 rounded-lg bg-input-background border border-border text-xs sm:text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
              >
                <option value="all">All Difficulties</option>
                {DIFFICULTIES.map((d) => (
                  <option key={d} value={d}>
                    {d}
                  </option>
                ))}
              </select>

              <select
                value={filterType}
                onChange={(e) => {
                  setFilterType(e.target.value);
                  setCurrentPage(1);
                }}
                className="px-3 py-2 rounded-lg bg-input-background border border-border text-xs sm:text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
              >
                <option value="all">All Question Types</option>
                {QUESTION_TYPES.map((t) => (
                  <option key={t.value} value={t.value}>
                    {t.label}
                  </option>
                ))}
              </select>

              <select
                value={sortBy}
                onChange={(e) => {
                  setSortBy(e.target.value);
                  setCurrentPage(1);
                }}
                className="px-3 py-2 rounded-lg bg-input-background border border-border text-xs sm:text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 col-span-2 sm:col-span-1"
              >
                <option value="newest">Newest First</option>
                <option value="oldest">Oldest First</option>
                <option value="most_used">Most Used</option>
                <option value="marks_high">Highest Marks</option>
                <option value="marks_low">Lowest Marks</option>
              </select>
            </div>
          </div>
        </div>

        {/* Bulk Action Toolbar */}
        {selectedIds.length > 0 && (
          <div className="bg-primary/5 border border-primary/20 rounded-xl p-3 flex flex-wrap items-center justify-between gap-3 animate-fade-in">
            <div className="flex items-center gap-2 text-sm font-medium text-foreground">
              <span className="w-5 h-5 rounded-full bg-primary text-white text-xs flex items-center justify-center font-bold">
                {selectedIds.length}
              </span>
              <span>questions selected</span>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <button
                onClick={() => handleBulkAction("activate")}
                className="px-3 py-1.5 rounded-lg bg-white border border-border text-emerald-700 hover:bg-emerald-50 text-xs font-semibold flex items-center gap-1.5 shadow-sm"
              >
                <Check className="w-3.5 h-3.5" />
                Activate
              </button>
              <button
                onClick={() => handleBulkAction("archive")}
                className="px-3 py-1.5 rounded-lg bg-white border border-border text-amber-700 hover:bg-amber-50 text-xs font-semibold flex items-center gap-1.5 shadow-sm"
              >
                <Archive className="w-3.5 h-3.5" />
                Archive
              </button>
              <button
                onClick={() => handleBulkAction("delete")}
                className="px-3 py-1.5 rounded-lg bg-white border border-rose-200 text-rose-700 hover:bg-rose-50 text-xs font-semibold flex items-center gap-1.5 shadow-sm"
              >
                <Trash2 className="w-3.5 h-3.5" />
                Delete Selected
              </button>
              <button
                onClick={() => setSelectedIds([])}
                className="px-3 py-1.5 rounded-lg border border-border text-muted-foreground hover:bg-muted text-xs font-medium"
              >
                Clear Selection
              </button>
            </div>
          </div>
        )}

        {/* Questions Table */}
        <div className="bg-white rounded-xl shadow-sm border border-border overflow-hidden">
          {loading ? (
            <div className="p-12 text-center space-y-3">
              <RefreshCw className="w-8 h-8 text-primary animate-spin mx-auto" />
              <p className="text-sm text-muted-foreground">Loading questions from institution repository...</p>
            </div>
          ) : error ? (
            <div className="p-12 text-center space-y-3">
              <AlertTriangle className="w-8 h-8 text-rose-500 mx-auto" />
              <p className="text-sm text-foreground font-medium">{error}</p>
              <button
                onClick={loadQuestions}
                className="px-4 py-2 rounded-lg bg-primary text-white text-sm font-medium hover:opacity-90 inline-flex items-center gap-2"
              >
                <RefreshCw className="w-4 h-4" />
                Retry
              </button>
            </div>
          ) : questions.length === 0 ? (
            <div className="p-16 text-center space-y-3">
              <HelpCircle className="w-12 h-12 text-muted-foreground/40 mx-auto" />
              <h3 className="text-lg font-semibold text-foreground">No questions found</h3>
              <p className="text-sm text-muted-foreground max-w-md mx-auto">
                No questions match your current filters. Try resetting search, or create new questions using the Add Question button.
              </p>
              <button
                onClick={handleOpenAddModal}
                className="mt-2 px-4 py-2 rounded-lg bg-primary text-white text-sm font-medium hover:opacity-90 inline-flex items-center gap-2 shadow-sm"
              >
                <Plus className="w-4 h-4" />
                Add Question
              </button>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="bg-muted/40 border-b border-border text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                    <th className="py-3 px-4 w-10">
                      <input
                        type="checkbox"
                        checked={allSelected}
                        onChange={toggleSelectAll}
                        className="rounded border-border text-primary focus:ring-primary w-4 h-4 cursor-pointer"
                      />
                    </th>
                    <th className="py-3 px-4 min-w-[280px]">Question</th>
                    <th className="py-3 px-3">Subject / Topic</th>
                    <th className="py-3 px-3">Type</th>
                    <th className="py-3 px-3">Difficulty</th>
                    <th className="py-3 px-3">Marks</th>
                    <th className="py-3 px-3">Status</th>
                    <th className="py-3 px-3 text-center">Usage</th>
                    <th className="py-3 px-4 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border text-sm">
                  {questions.map((q) => (
                    <tr key={q.id} className="hover:bg-muted/20 transition-colors group">
                      <td className="py-3.5 px-4 align-top">
                        <input
                          type="checkbox"
                          checked={selectedIds.includes(q.id)}
                          onChange={() => toggleSelectId(q.id)}
                          className="rounded border-border text-primary focus:ring-primary w-4 h-4 cursor-pointer mt-1"
                        />
                      </td>
                      <td className="py-3.5 px-4 align-top">
                        <div className="font-medium text-foreground line-clamp-2 group-hover:line-clamp-none transition-all">
                          {q.text}
                        </div>
                        {q.tags && q.tags.length > 0 && (
                          <div className="flex flex-wrap gap-1 mt-1.5">
                            {q.tags.slice(0, 3).map((tag, idx) => (
                              <span key={idx} className="px-1.5 py-0.5 rounded text-[10px] bg-slate-100 text-slate-600">
                                #{tag}
                              </span>
                            ))}
                            {q.tags.length > 3 && (
                              <span className="text-[10px] text-muted-foreground">+{q.tags.length - 3}</span>
                            )}
                          </div>
                        )}
                      </td>
                      <td className="py-3.5 px-3 align-top whitespace-nowrap">
                        <div className="font-medium text-xs text-foreground">{q.subject_name || "—"}</div>
                        <div className="text-[11px] text-muted-foreground mt-0.5">{q.topic_name || "General"}</div>
                      </td>
                      <td className="py-3.5 px-3 align-top whitespace-nowrap">
                        <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-blue-50 text-blue-700 border border-blue-200/60">
                          {q.question_type.replace("_", " ")}
                        </span>
                      </td>
                      <td className="py-3.5 px-3 align-top whitespace-nowrap">
                        <span
                          className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                            q.difficulty.toUpperCase() === "EASY"
                              ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                              : q.difficulty.toUpperCase() === "MEDIUM"
                              ? "bg-amber-50 text-amber-700 border border-amber-200"
                              : "bg-rose-50 text-rose-700 border border-rose-200"
                          }`}
                        >
                          {q.difficulty.toUpperCase()}
                        </span>
                      </td>
                      <td className="py-3.5 px-3 align-top whitespace-nowrap text-xs font-medium">
                        {q.marks} pts
                        {Number(q.negative_marks) > 0 && (
                          <span className="text-rose-600 text-[11px] block">(-{q.negative_marks})</span>
                        )}
                      </td>
                      <td className="py-3.5 px-3 align-top whitespace-nowrap">
                        <span
                          className={`px-2 py-0.5 rounded text-xs font-medium ${
                            q.status === "ACTIVE"
                              ? "bg-emerald-100 text-emerald-800"
                              : q.status === "DRAFT"
                              ? "bg-slate-100 text-slate-700"
                              : "bg-amber-100 text-amber-800"
                          }`}
                        >
                          {q.status}
                        </span>
                      </td>
                      <td className="py-3.5 px-3 align-top whitespace-nowrap text-center">
                        <span className="px-2 py-0.5 rounded-full text-xs font-semibold bg-muted text-muted-foreground">
                          {q.times_used}x
                        </span>
                      </td>
                      <td className="py-3.5 px-4 align-top text-right whitespace-nowrap">
                        <div className="flex items-center justify-end gap-1.5">
                          <button
                            onClick={() => handleViewDetail(q.id)}
                            title="View Details"
                            className="p-1.5 hover:bg-muted rounded-md text-muted-foreground hover:text-foreground transition-colors"
                          >
                            <Eye className="w-4 h-4" />
                          </button>
                          <button
                            onClick={() => handleOpenEditModal(q)}
                            title="Edit Question"
                            className="p-1.5 hover:bg-primary/10 rounded-md text-muted-foreground hover:text-primary transition-colors"
                          >
                            <Edit2 className="w-4 h-4" />
                          </button>
                          <button
                            onClick={() => handleDuplicate(q.id)}
                            title="Duplicate as Draft"
                            className="p-1.5 hover:bg-muted rounded-md text-muted-foreground hover:text-foreground transition-colors"
                          >
                            <Copy className="w-4 h-4" />
                          </button>
                          <button
                            onClick={() => handleDelete(q.id)}
                            title="Delete"
                            className="p-1.5 hover:bg-rose-50 rounded-md text-muted-foreground hover:text-rose-600 transition-colors"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Pagination Controls */}
          {!loading && questions.length > 0 && (
            <div className="p-4 border-t border-border flex flex-col sm:flex-row items-center justify-between gap-3 text-xs text-muted-foreground bg-muted/10">
              <div className="flex items-center gap-3">
                <span>
                  Showing {(currentPage - 1) * pageSize + 1} to{" "}
                  {Math.min(currentPage * pageSize, totalCount)} of {totalCount} questions
                </span>
                <select
                  value={pageSize}
                  onChange={(e) => {
                    setPageSize(Number(e.target.value));
                    setCurrentPage(1);
                  }}
                  className="px-2 py-1 rounded border border-border bg-white text-foreground focus:outline-none"
                >
                  <option value={10}>10 / page</option>
                  <option value={20}>20 / page</option>
                  <option value={50}>50 / page</option>
                </select>
              </div>
              <div className="flex items-center gap-1.5">
                <button
                  disabled={currentPage <= 1}
                  onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                  className="p-1.5 rounded border border-border bg-white disabled:opacity-40 disabled:cursor-not-allowed hover:bg-muted transition-colors"
                >
                  <ChevronLeft className="w-4 h-4" />
                </button>
                <span className="px-2 font-medium text-foreground">
                  Page {currentPage} of {totalPages}
                </span>
                <button
                  disabled={currentPage >= totalPages}
                  onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                  className="p-1.5 rounded border border-border bg-white disabled:opacity-40 disabled:cursor-not-allowed hover:bg-muted transition-colors"
                >
                  <ChevronRight className="w-4 h-4" />
                </button>
              </div>
            </div>
          )}
        </div>

        {/* ==================== ADD / EDIT QUESTION MODAL ==================== */}
        {showAddModal && (
          <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4 animate-fade-in backdrop-blur-sm">
            <div className="bg-white rounded-2xl w-full max-w-3xl max-h-[92vh] overflow-hidden flex flex-col shadow-2xl border border-border">
              {/* Modal Header */}
              <div className="p-5 border-b border-border flex items-center justify-between bg-muted/20">
                <div>
                  <h3 className="font-bold text-lg text-foreground">
                    {editingQuestionId ? `Edit Question #${editingQuestionId}` : "Create New Question"}
                  </h3>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    Enforces institution isolation and strict schema validation
                  </p>
                </div>
                <button
                  onClick={() => setShowAddModal(false)}
                  className="p-1.5 hover:bg-muted rounded-lg transition-colors text-muted-foreground"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              {/* Modal Body */}
              <form onSubmit={handleSaveQuestion} className="overflow-y-auto p-6 space-y-5 flex-1">
                {formWarnings.length > 0 && (
                  <div className="p-3.5 rounded-xl bg-amber-50 border border-amber-200 text-amber-800 text-xs space-y-1">
                    <div className="font-semibold flex items-center gap-1.5">
                      <AlertTriangle className="w-4 h-4 text-amber-600" />
                      Notice & Near Duplicate Warnings:
                    </div>
                    {formWarnings.map((w, idx) => (
                      <div key={idx}>• {w}</div>
                    ))}
                  </div>
                )}

                {/* Question Text */}
                <div>
                  <div className="flex justify-between items-center mb-1.5">
                    <label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                      Question Text *
                    </label>
                    <span className="text-[11px] text-muted-foreground">
                      {formData.text.length} / 5000 chars (min 10)
                    </span>
                  </div>
                  <textarea
                    rows={3}
                    placeholder="Enter the complete question text..."
                    value={formData.text}
                    onChange={(e) => setFormData({ ...formData, text: e.target.value })}
                    className={`w-full px-3.5 py-2.5 rounded-lg bg-input-background border text-sm focus:outline-none focus:ring-2 ${
                      formErrors.text ? "border-rose-400 focus:ring-rose-200" : "border-border focus:ring-primary/20"
                    }`}
                  />
                  {formErrors.text && <p className="text-xs text-rose-600 mt-1 font-medium">{formErrors.text}</p>}
                </div>

                {/* Subject, Topic, Department */}
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3.5">
                  <div>
                    <label className="block text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-1.5">
                      Subject *
                    </label>
                    <select
                      value={formData.subject}
                      onChange={(e) => setFormData({ ...formData, subject: Number(e.target.value), topic: "" })}
                      className="w-full px-3 py-2 rounded-lg bg-input-background border border-border text-sm focus:outline-none focus:ring-2 focus:ring-primary/20"
                    >
                      <option value="">Select Subject</option>
                      {subjects.map((s) => (
                        <option key={s.id} value={s.id}>
                          {s.name}
                        </option>
                      ))}
                    </select>
                    {formErrors.subject && (
                      <p className="text-xs text-rose-600 mt-1 font-medium">{formErrors.subject}</p>
                    )}
                  </div>

                  <div>
                    <label className="block text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-1.5">
                      Topic (Optional)
                    </label>
                    <select
                      value={formData.topic}
                      onChange={(e) => setFormData({ ...formData, topic: e.target.value ? Number(e.target.value) : "" })}
                      className="w-full px-3 py-2 rounded-lg bg-input-background border border-border text-sm focus:outline-none focus:ring-2 focus:ring-primary/20"
                    >
                      <option value="">General / None</option>
                      {availableFormTopics.map((t) => (
                        <option key={t.id} value={t.id}>
                          {t.name}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div>
                    <label className="block text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-1.5">
                      Department
                    </label>
                    <input
                      type="text"
                      value={formData.department}
                      onChange={(e) => setFormData({ ...formData, department: e.target.value })}
                      className="w-full px-3 py-2 rounded-lg bg-input-background border border-border text-sm focus:outline-none focus:ring-2 focus:ring-primary/20"
                    />
                  </div>
                </div>

                {/* Question Type, Difficulty, Marks */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3.5">
                  <div>
                    <label className="block text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-1.5">
                      Question Type *
                    </label>
                    <select
                      value={formData.question_type}
                      onChange={(e) => setFormData({ ...formData, question_type: e.target.value })}
                      className="w-full px-3 py-2 rounded-lg bg-input-background border border-border text-sm focus:outline-none focus:ring-2 focus:ring-primary/20"
                    >
                      {QUESTION_TYPES.map((t) => (
                        <option key={t.value} value={t.value}>
                          {t.label}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div>
                    <label className="block text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-1.5">
                      Difficulty *
                    </label>
                    <select
                      value={formData.difficulty}
                      onChange={(e) => setFormData({ ...formData, difficulty: e.target.value })}
                      className="w-full px-3 py-2 rounded-lg bg-input-background border border-border text-sm focus:outline-none focus:ring-2 focus:ring-primary/20"
                    >
                      {DIFFICULTIES.map((d) => (
                        <option key={d} value={d}>
                          {d}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div>
                    <label className="block text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-1.5">
                      Marks *
                    </label>
                    <input
                      type="number"
                      step="0.5"
                      min="0.5"
                      value={formData.marks}
                      onChange={(e) => setFormData({ ...formData, marks: parseFloat(e.target.value) || 1.0 })}
                      className="w-full px-3 py-2 rounded-lg bg-input-background border border-border text-sm focus:outline-none focus:ring-2 focus:ring-primary/20"
                    />
                    {formErrors.marks && <p className="text-xs text-rose-600 mt-1 font-medium">{formErrors.marks}</p>}
                  </div>

                  <div>
                    <label className="block text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-1.5">
                      Negative Marks
                    </label>
                    <input
                      type="number"
                      step="0.25"
                      min="0"
                      value={formData.negative_marks}
                      onChange={(e) => setFormData({ ...formData, negative_marks: parseFloat(e.target.value) || 0.0 })}
                      className="w-full px-3 py-2 rounded-lg bg-input-background border border-border text-sm focus:outline-none focus:ring-2 focus:ring-primary/20"
                    />
                    {formErrors.negative_marks && (
                      <p className="text-xs text-rose-600 mt-1 font-medium">{formErrors.negative_marks}</p>
                    )}
                  </div>
                </div>

                {/* Dynamic Options Editor for MCQ / True False */}
                {(formData.question_type.startsWith("MCQ") || formData.question_type === "TRUE_FALSE") && (
                  <div className="border border-border rounded-xl p-4 bg-muted/10 space-y-3">
                    <div className="flex items-center justify-between">
                      <div className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                        Options & Answer Key ({formData.options.length} options)
                      </div>
                      {formData.question_type !== "TRUE_FALSE" && formData.options.length < 6 && (
                        <button
                          type="button"
                          onClick={() =>
                            setFormData({
                              ...formData,
                              options: [
                                ...formData.options,
                                { text: "", is_correct: false, order: formData.options.length + 1 },
                              ],
                            })
                          }
                          className="text-xs text-primary font-semibold hover:underline flex items-center gap-1"
                        >
                          <Plus className="w-3.5 h-3.5" /> Add Option
                        </button>
                      )}
                    </div>

                    {formErrors.options && (
                      <p className="text-xs text-rose-600 font-medium">{formErrors.options}</p>
                    )}

                    <div className="space-y-2">
                      {formData.options.map((opt, idx) => (
                        <div key={idx} className="flex items-center gap-2.5">
                          {/* Radio/Checkbox for Correct */}
                          <label
                            className="cursor-pointer flex items-center gap-1 text-xs font-medium"
                            title="Mark as correct answer"
                          >
                            <input
                              type={formData.question_type === "MCQ_MULTIPLE" ? "checkbox" : "radio"}
                              name="is_correct_option"
                              checked={opt.is_correct}
                              onChange={(e) => {
                                const newOpts = [...formData.options];
                                if (formData.question_type === "MCQ_MULTIPLE") {
                                  newOpts[idx].is_correct = e.target.checked;
                                } else {
                                  newOpts.forEach((o, i) => (o.is_correct = i === idx));
                                }
                                setFormData({ ...formData, options: newOpts });
                              }}
                              className="rounded text-primary focus:ring-primary w-4 h-4 cursor-pointer"
                            />
                            <span className={opt.is_correct ? "text-emerald-700 font-bold" : "text-muted-foreground"}>
                              {String.fromCharCode(65 + idx)}
                            </span>
                          </label>

                          <input
                            type="text"
                            placeholder={`Option ${String.fromCharCode(65 + idx)} text...`}
                            value={opt.text}
                            onChange={(e) => {
                              const newOpts = [...formData.options];
                              newOpts[idx].text = e.target.value;
                              setFormData({ ...formData, options: newOpts });
                            }}
                            className={`flex-1 px-3 py-1.5 rounded-lg bg-white border text-sm focus:outline-none focus:ring-2 ${
                              opt.is_correct ? "border-emerald-300 bg-emerald-50/20" : "border-border"
                            }`}
                          />

                          {formData.question_type !== "TRUE_FALSE" && formData.options.length > 2 && (
                            <button
                              type="button"
                              onClick={() => {
                                const newOpts = formData.options.filter((_, i) => i !== idx);
                                setFormData({ ...formData, options: newOpts });
                              }}
                              className="p-1.5 hover:bg-rose-50 text-muted-foreground hover:text-rose-600 rounded"
                            >
                              <X className="w-4 h-4" />
                            </button>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Model Answer (for Subjective) */}
                {formData.question_type.includes("ANSWER") && (
                  <div>
                    <label className="block text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-1.5">
                      Model Answer / Key Points *
                    </label>
                    <textarea
                      rows={3}
                      placeholder="Provide the model answer or key evaluation points..."
                      value={formData.model_answer}
                      onChange={(e) => setFormData({ ...formData, model_answer: e.target.value })}
                      className="w-full px-3.5 py-2 rounded-lg bg-input-background border border-border text-sm focus:outline-none focus:ring-2 focus:ring-primary/20"
                    />
                    {formErrors.model_answer && (
                      <p className="text-xs text-rose-600 mt-1 font-medium">{formErrors.model_answer}</p>
                    )}
                  </div>
                )}

                {/* Explanation */}
                <div>
                  <label className="block text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-1.5">
                    Explanation / Rationale (Optional)
                  </label>
                  <textarea
                    rows={2}
                    placeholder="Provide an explanation for the solution (shown to students only after results are published)..."
                    value={formData.explanation}
                    onChange={(e) => setFormData({ ...formData, explanation: e.target.value })}
                    className="w-full px-3.5 py-2 rounded-lg bg-input-background border border-border text-sm focus:outline-none focus:ring-2 focus:ring-primary/20"
                  />
                </div>

                {/* Tags & Status */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
                  <div>
                    <label className="block text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-1.5">
                      Tags (Comma separated)
                    </label>
                    <input
                      type="text"
                      placeholder="e.g. recursion, arrays, midterm"
                      value={formData.tags}
                      onChange={(e) => setFormData({ ...formData, tags: e.target.value })}
                      className="w-full px-3 py-2 rounded-lg bg-input-background border border-border text-sm focus:outline-none focus:ring-2 focus:ring-primary/20"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-1.5">
                      Status
                    </label>
                    <select
                      value={formData.status}
                      onChange={(e) => setFormData({ ...formData, status: e.target.value })}
                      className="w-full px-3 py-2 rounded-lg bg-input-background border border-border text-sm focus:outline-none focus:ring-2 focus:ring-primary/20"
                    >
                      {STATUSES.map((s) => (
                        <option key={s} value={s}>
                          {s}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>

                {/* Footer Buttons */}
                <div className="pt-4 border-t border-border flex items-center justify-end gap-2.5">
                  <button
                    type="button"
                    onClick={() => setShowAddModal(false)}
                    className="px-4 py-2 rounded-lg border border-border text-foreground hover:bg-muted text-sm font-medium transition-colors"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={formSubmitting}
                    className="px-5 py-2 rounded-lg bg-primary text-white text-sm font-semibold hover:opacity-90 disabled:opacity-50 flex items-center gap-2 shadow-sm"
                  >
                    {formSubmitting && <RefreshCw className="w-4 h-4 animate-spin" />}
                    {editingQuestionId ? "Save Changes" : "Create Question"}
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* ==================== VIEW DETAILS MODAL ==================== */}
        {showDetailModal && (
          <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4 animate-fade-in backdrop-blur-sm">
            <div className="bg-white rounded-2xl w-full max-w-2xl max-h-[90vh] overflow-hidden flex flex-col shadow-2xl border border-border">
              <div className="p-5 border-b border-border flex items-center justify-between bg-muted/20">
                <div className="flex items-center gap-2.5">
                  <span className="font-bold text-lg text-foreground">
                    Question #{detailQuestion?.id}
                  </span>
                  <span
                    className={`px-2 py-0.5 rounded text-xs font-medium ${
                      detailQuestion?.status === "ACTIVE"
                        ? "bg-emerald-100 text-emerald-800"
                        : "bg-slate-100 text-slate-700"
                    }`}
                  >
                    {detailQuestion?.status}
                  </span>
                  <span className="text-xs text-muted-foreground font-mono">
                    v{detailQuestion?.version}
                  </span>
                </div>
                <button
                  onClick={() => setShowDetailModal(false)}
                  className="p-1.5 hover:bg-muted rounded-lg text-muted-foreground"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              <div className="p-6 overflow-y-auto space-y-4 flex-1 text-sm">
                {detailLoading ? (
                  <div className="py-12 text-center">
                    <RefreshCw className="w-6 h-6 animate-spin mx-auto text-primary" />
                  </div>
                ) : detailQuestion ? (
                  <>
                    <div>
                      <div className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-1">
                        Question Text
                      </div>
                      <div className="p-3 bg-muted/20 rounded-lg text-foreground font-medium whitespace-pre-wrap">
                        {detailQuestion.text}
                      </div>
                    </div>

                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 text-xs">
                      <div className="p-2.5 bg-muted/10 rounded-lg border border-border">
                        <span className="text-muted-foreground block">Subject</span>
                        <span className="font-semibold text-foreground">{detailQuestion.subject_name || "—"}</span>
                      </div>
                      <div className="p-2.5 bg-muted/10 rounded-lg border border-border">
                        <span className="text-muted-foreground block">Type</span>
                        <span className="font-semibold text-foreground">{detailQuestion.question_type}</span>
                      </div>
                      <div className="p-2.5 bg-muted/10 rounded-lg border border-border">
                        <span className="text-muted-foreground block">Difficulty</span>
                        <span className="font-semibold text-foreground">{detailQuestion.difficulty}</span>
                      </div>
                      <div className="p-2.5 bg-muted/10 rounded-lg border border-border">
                        <span className="text-muted-foreground block">Marks</span>
                        <span className="font-semibold text-foreground">
                          {detailQuestion.marks} pts {Number(detailQuestion.negative_marks) > 0 ? `(-${detailQuestion.negative_marks})` : ""}
                        </span>
                      </div>
                    </div>

                    {/* Options list */}
                    {detailQuestion.options && detailQuestion.options.length > 0 && (
                      <div>
                        <div className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-1.5">
                          Options & Answers
                        </div>
                        <div className="space-y-1.5">
                          {detailQuestion.options.map((opt, idx) => (
                            <div
                              key={idx}
                              className={`p-2.5 rounded-lg border text-xs flex items-center justify-between ${
                                opt.is_correct
                                  ? "bg-emerald-50/60 border-emerald-300 text-emerald-900 font-medium"
                                  : "bg-white border-border text-foreground"
                              }`}
                            >
                              <span>
                                <strong className="mr-2">{String.fromCharCode(65 + idx)}.</strong>
                                {opt.text}
                              </span>
                              {opt.is_correct && (
                                <span className="px-2 py-0.5 rounded bg-emerald-600 text-white font-bold text-[10px]">
                                  CORRECT
                                </span>
                              )}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Model Answer */}
                    {detailQuestion.model_answer && (
                      <div>
                        <div className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-1">
                          Model Answer
                        </div>
                        <div className="p-3 bg-muted/20 rounded-lg text-foreground text-xs whitespace-pre-wrap">
                          {detailQuestion.model_answer}
                        </div>
                      </div>
                    )}

                    {/* Explanation */}
                    {detailQuestion.explanation && (
                      <div>
                        <div className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-1">
                          Explanation
                        </div>
                        <div className="p-3 bg-muted/20 rounded-lg text-foreground text-xs whitespace-pre-wrap">
                          {detailQuestion.explanation}
                        </div>
                      </div>
                    )}

                    {/* Usage Info */}
                    <div className="p-3 rounded-lg bg-blue-50/60 border border-blue-200 text-xs text-blue-900">
                      <div className="font-semibold">Usage Summary:</div>
                      <div>Times used in exams: <strong>{detailQuestion.times_used}x</strong></div>
                      {detailQuestion.usage_info?.is_locked && (
                        <div className="text-amber-700 mt-1 font-medium">
                          ⚠️ {detailQuestion.usage_info.reason}
                        </div>
                      )}
                    </div>
                  </>
                ) : null}
              </div>
            </div>
          </div>
        )}

        {/* ==================== BULK IMPORT MODAL ==================== */}
        {showImportModal && (
          <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4 animate-fade-in backdrop-blur-sm">
            <div className="bg-white rounded-2xl w-full max-w-2xl max-h-[92vh] overflow-hidden flex flex-col shadow-2xl border border-border">
              <div className="p-5 border-b border-border flex items-center justify-between bg-muted/20">
                <div>
                  <h3 className="font-bold text-lg text-foreground">Bulk Import Questions</h3>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    Safe two-phase import with automatic validation, deduplication, and formula protection
                  </p>
                </div>
                <button
                  onClick={() => setShowImportModal(false)}
                  className="p-1.5 hover:bg-muted rounded-lg text-muted-foreground"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              <div className="p-6 overflow-y-auto space-y-5 flex-1">
                {/* Template download link */}
                <div className="flex items-center justify-between p-3.5 bg-muted/20 rounded-xl border border-border">
                  <div className="flex items-center gap-3">
                    <FileSpreadsheet className="w-5 h-5 text-emerald-600" />
                    <div>
                      <div className="text-xs font-semibold text-foreground">Need the import template?</div>
                      <div className="text-[11px] text-muted-foreground">Download standard formatted template with example rows</div>
                    </div>
                  </div>
                  <div className="flex gap-2">
                    <button
                      onClick={() => handleDownloadTemplate("csv")}
                      className="px-2.5 py-1 text-xs border border-border bg-white rounded-lg hover:bg-muted font-medium"
                    >
                      CSV
                    </button>
                    <button
                      onClick={() => handleDownloadTemplate("xlsx")}
                      className="px-2.5 py-1 text-xs border border-border bg-white rounded-lg hover:bg-muted font-medium"
                    >
                      XLSX
                    </button>
                  </div>
                </div>

                {/* File picker */}
                <div>
                  <label className="block text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-2">
                    Select File (.CSV or .XLSX)
                  </label>
                  <input
                    type="file"
                    accept=".csv, .xlsx"
                    onChange={(e) => {
                      if (e.target.files && e.target.files[0]) {
                        setImportFile(e.target.files[0]);
                        setImportReport(null);
                      }
                    }}
                    className="block w-full text-xs text-muted-foreground file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-primary file:text-white hover:file:opacity-90 cursor-pointer"
                  />
                </div>

                {/* Dry Run Report */}
                {importReport && (
                  <div className="space-y-3">
                    <div className="flex items-center justify-between text-xs font-semibold">
                      <span>Validation Report:</span>
                      <div className="flex gap-2">
                        <span className="text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
                          {importReport.valid_count} Valid
                        </span>
                        <span className="text-rose-700 bg-rose-50 px-2 py-0.5 rounded border border-rose-200">
                          {importReport.failed_count} Invalid
                        </span>
                      </div>
                    </div>

                    <div className="max-h-56 overflow-y-auto border border-border rounded-xl divide-y divide-border text-xs">
                      {importReport.row_results.map((r) => (
                        <div
                          key={r.row_number}
                          className={`p-2.5 ${r.is_valid ? "bg-emerald-50/20" : "bg-rose-50/30"}`}
                        >
                          <div className="flex items-center justify-between">
                            <span className="font-semibold">Row #{r.row_number}: {r.question_text || "—"}</span>
                            <span
                              className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                                r.is_valid ? "bg-emerald-100 text-emerald-800" : "bg-rose-100 text-rose-800"
                              }`}
                            >
                              {r.is_valid ? "VALID" : "ERROR"}
                            </span>
                          </div>
                          {r.errors && r.errors.length > 0 && (
                            <div className="text-rose-700 mt-1 font-medium space-y-0.5">
                              {r.errors.map((err, i) => (
                                <div key={i}>• {err}</div>
                              ))}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Actions */}
                <div className="flex items-center justify-between pt-4 border-t border-border">
                  <button
                    onClick={() => setShowImportModal(false)}
                    className="px-4 py-2 rounded-lg border border-border text-foreground hover:bg-muted text-sm font-medium"
                  >
                    Close
                  </button>
                  <div className="flex gap-2">
                    <button
                      onClick={handleDryRunImport}
                      disabled={!importFile || importDryRunLoading}
                      className="px-4 py-2 rounded-lg border border-border bg-white text-foreground hover:bg-muted text-sm font-medium disabled:opacity-50 flex items-center gap-2"
                    >
                      {importDryRunLoading && <RefreshCw className="w-3.5 h-3.5 animate-spin" />}
                      Test Dry Run
                    </button>
                    <button
                      onClick={handleCommitImport}
                      disabled={!importFile || importCommitLoading || (importReport !== null && importReport.valid_count === 0)}
                      className="px-4 py-2 rounded-lg bg-primary text-white text-sm font-semibold hover:opacity-90 disabled:opacity-50 flex items-center gap-2 shadow-sm"
                    >
                      {importCommitLoading && <RefreshCw className="w-3.5 h-3.5 animate-spin" />}
                      Confirm & Import
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ==================== SUBJECTS & TOPICS MODAL ==================== */}
        {showSubjectsModal && (
          <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4 animate-fade-in backdrop-blur-sm">
            <div className="bg-white rounded-2xl w-full max-w-2xl max-h-[90vh] overflow-hidden flex flex-col shadow-2xl border border-border">
              <div className="p-5 border-b border-border flex items-center justify-between bg-muted/20">
                <div>
                  <h3 className="font-bold text-lg text-foreground">Subjects & Topics Management</h3>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    Structure the curriculum for this institution
                  </p>
                </div>
                <button
                  onClick={() => setShowSubjectsModal(false)}
                  className="p-1.5 hover:bg-muted rounded-lg text-muted-foreground"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              <div className="p-6 overflow-y-auto space-y-4 flex-1">
                <div className="space-y-3">
                  <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                    Active Subjects ({subjects.length})
                  </h4>
                  <div className="divide-y divide-border border border-border rounded-xl">
                    {subjects.map((sub) => (
                      <div key={sub.id} className="p-3 flex items-center justify-between text-sm">
                        <div>
                          <div className="font-semibold text-foreground">{sub.name}</div>
                          <div className="text-xs text-muted-foreground">
                            {sub.department} • {sub.question_count} questions
                          </div>
                        </div>
                        <button
                          onClick={async () => {
                            if (!window.confirm(`Delete subject "${sub.name}"?`)) return;
                            try {
                              await questionBankApi.deleteSubject(sub.id);
                              showToast("Subject deleted!");
                              loadReferenceData();
                            } catch (err: any) {
                              showToast(err.response?.data?.detail || "Cannot delete subject", "error");
                            }
                          }}
                          className="p-1 text-muted-foreground hover:text-rose-600 rounded"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}

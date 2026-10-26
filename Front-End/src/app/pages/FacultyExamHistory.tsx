import { useEffect, useMemo, useState } from "react";
import {
  AlertCircle,
  AlertTriangle,
  ArrowLeft,
  ArrowRight,
  Bot,
  Calendar,
  Check,
  CheckCircle,
  ChevronDown,
  ChevronUp,
  Clock,
  Copy,
  Cpu,
  Edit3,
  Eye,
  FileText,
  Filter,
  History,
  LayoutDashboard,
  Loader2,
  Plus,
  RefreshCw,
  RotateCcw,
  Search,
  Settings,
  ShieldCheck,
  Sparkles,
  Trash2,
  X,
  XCircle,
} from "lucide-react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { DashboardLayout } from "../components/DashboardLayout";
import { GenerationProgressModal } from "../components/GenerationProgressModal";
import {
  facultyExamApi,
  generationApi,
  type FacultyExam,
  type PaperGenerationJob,
} from "../../services/api";

const menuItems = [
  { icon: LayoutDashboard, label: "Dashboard", path: "/faculty" },
  { icon: FileText, label: "Generate Paper", path: "/faculty/generate" },
  { icon: History, label: "Exam History", path: "/faculty/history" },
  { icon: Settings, label: "Settings", path: "/faculty/settings" },
];

export function FacultyExamHistory() {
  const navigate = useNavigate();
  const [exams, setExams] = useState<FacultyExam[]>([]);
  const [recentJobs, setRecentJobs] = useState<PaperGenerationJob[]>([]);
  const [loading, setLoading] = useState(true);

  // Search & Filters
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<"all" | "generating" | "draft" | "published" | "closed" | "failed">("all");
  const [sortBy, setSortBy] = useState<"newest" | "title" | "marks">("newest");

  // Viewed papers for "New" badge tracking
  const [viewedPaperIds, setViewedPaperIds] = useState<number[]>(() => {
    try {
      const stored = localStorage.getItem("examai_viewed_papers");
      return stored ? JSON.parse(stored) : [];
    } catch {
      return [];
    }
  });

  // Active generation modal
  const [progressJobId, setProgressJobId] = useState<number | null>(null);
  const [showProgressModal, setShowProgressModal] = useState(false);

  // Delete Confirmation Modal
  const [examToDelete, setExamToDelete] = useState<FacultyExam | null>(null);
  const [deleting, setDeleting] = useState(false);

  // Action states
  const [duplicatingId, setDuplicatingId] = useState<number | null>(null);
  const [publishingId, setPublishingId] = useState<number | null>(null);

  // Attempts Modal State
  const [selectedExam, setSelectedExam] = useState<FacultyExam | null>(null);
  const [attempts, setAttempts] = useState<any[]>([]);
  const [loadingAttempts, setLoadingAttempts] = useState(false);

  // Attempt Detail State
  const [selectedAttemptId, setSelectedAttemptId] = useState<number | null>(null);
  const [attemptDetail, setAttemptDetail] = useState<any | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [reevaluatingAttempt, setReevaluatingAttempt] = useState(false);
  const [reevaluatingAnswerId, setReevaluatingAnswerId] = useState<number | null>(null);
  const [suggestingAnswerId, setSuggestingAnswerId] = useState<number | null>(null);
  const [finalizingAttempt, setFinalizingAttempt] = useState(false);

  // Evaluation Override & Review State
  const [editingQuestionId, setEditingQuestionId] = useState<number | null>(null);
  const [overrideMarks, setOverrideMarks] = useState<string>("");
  const [overrideCorrectness, setOverrideCorrectness] = useState<"correct" | "partial" | "wrong">("correct");
  const [overrideComment, setOverrideComment] = useState<string>("");
  const [overrideReason, setOverrideReason] = useState<string>("");
  const [savingOverride, setSavingOverride] = useState(false);
  const [resettingQuestionId, setResettingQuestionId] = useState<number | null>(null);
  const [approvingAsIs, setApprovingAsIs] = useState(false);
  const [reopeningReview, setReopeningReview] = useState(false);
  const [showFinalizeModal, setShowFinalizeModal] = useState(false);
  const [expandedAuditQuestionId, setExpandedAuditQuestionId] = useState<number | null>(null);

  const loadData = async () => {
    try {
      const [examRes, jobRes] = await Promise.all([
        facultyExamApi.getExams(),
        generationApi.getRecentJobs().catch(() => ({ results: [], count: 0 })),
      ]);
      const loadedExams = Array.isArray(examRes) ? examRes : examRes.results ?? [];
      setExams(loadedExams);
      setRecentJobs(jobRes.results || []);
    } catch {
      toast.error("Unable to load exams.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadData();
  }, []);

  const markPaperAsViewed = (id: number) => {
    if (!viewedPaperIds.includes(id)) {
      const next = [...viewedPaperIds, id];
      setViewedPaperIds(next);
      try {
        localStorage.setItem("examai_viewed_papers", JSON.stringify(next));
      } catch {
        // Ignore
      }
    }
  };

  const handleOpenEdit = (examId: number) => {
    markPaperAsViewed(examId);
    navigate(`/faculty/exams/${examId}/edit`);
  };

  const publish = async (exam: FacultyExam) => {
    // Check review requirement
    if (!exam.is_reviewed) {
      toast.error("Review Required: Please open and review this draft paper before publishing it to students.", {
        action: {
          label: "Review Now",
          onClick: () => handleOpenEdit(exam.id),
        },
      });
      return;
    }

    // Check if schedule is missing
    if (!exam.starts_at || !exam.ends_at) {
      toast.error("Schedule Required: Exam start time and deadline must be set before publishing.", {
        action: {
          label: "Set Schedule",
          onClick: () => handleOpenEdit(exam.id),
        },
      });
      return;
    }

    setPublishingId(exam.id);
    try {
      const published = await facultyExamApi.publishExam(exam.id);
      setExams((current) => current.map((e) => (e.id === exam.id ? published : e)));
      toast.success("Exam published successfully! Students in your department can now access it.");
    } catch (err: any) {
      const data = err?.response?.data;
      const detailMsg =
        data?.detail ||
        (Array.isArray(data?.errors) ? data.errors.map((e: any) => e.message).join(". ") : null) ||
        "Publishing failed. Check question marks and review status.";
      toast.error(detailMsg, {
        ...(data?.code === "SCHEDULE_REQUIRED"
          ? {
              action: {
                label: "Set Schedule",
                onClick: () => handleOpenEdit(exam.id),
              },
            }
          : {}),
      });
    } finally {
      setPublishingId(null);
    }
  };

  const handleDuplicate = async (exam: FacultyExam) => {
    setDuplicatingId(exam.id);
    try {
      const res = await facultyExamApi.duplicateExam(exam);
      toast.success(`Duplicated "${exam.title}"!`);
      if (res.job_id) {
        setProgressJobId(res.job_id);
        setShowProgressModal(true);
      }
      await loadData();
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || "Failed to duplicate exam.");
    } finally {
      setDuplicatingId(null);
    }
  };

  const confirmDeleteExam = async () => {
    if (!examToDelete) return;
    setDeleting(true);
    try {
      await facultyExamApi.deleteExam(examToDelete.id);
      toast.success("Exam deleted successfully.");
      setExams((prev) => prev.filter((e) => e.id !== examToDelete.id));
      setExamToDelete(null);
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || "Failed to delete exam.");
    } finally {
      setDeleting(false);
    }
  };

  // Student attempts review handlers
  const handleOpenAttempts = async (exam: FacultyExam) => {
    setSelectedExam(exam);
    setSelectedAttemptId(null);
    setAttemptDetail(null);
    setLoadingAttempts(true);
    try {
      const res = await facultyExamApi.getExamAttempts(exam.id);
      setAttempts(res.attempts || []);
    } catch {
      toast.error("Failed to load student attempts.");
    } finally {
      setLoadingAttempts(false);
    }
  };

  const handleOpenAttemptDetail = async (attemptId: number) => {
    setSelectedAttemptId(attemptId);
    setLoadingDetail(true);
    try {
      const detail = await facultyExamApi.getAttemptDetail(attemptId);
      setAttemptDetail(detail);
    } catch {
      toast.error("Failed to load attempt details.");
    } finally {
      setLoadingDetail(false);
    }
  };

  const handleReevaluateAttempt = async (attemptId: number) => {
    setReevaluatingAttempt(true);
    try {
      await facultyExamApi.reevaluateAttempt(attemptId, true);
      toast.success("Attempt evaluation refreshed!");
      await handleOpenAttemptDetail(attemptId);
      if (selectedExam) {
        const res = await facultyExamApi.getExamAttempts(selectedExam.id);
        setAttempts(res.attempts || []);
      }
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || "Re-evaluation failed.");
    } finally {
      setReevaluatingAttempt(false);
    }
  };

  const handleReevaluateAnswer = async (answerId: number) => {
    setReevaluatingAnswerId(answerId);
    try {
      await facultyExamApi.reevaluateAnswer(answerId, true);
      toast.success("Answer re-evaluated!");
      if (selectedAttemptId) {
        await handleOpenAttemptDetail(selectedAttemptId);
      }
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || "Answer re-evaluation failed.");
    } finally {
      setReevaluatingAnswerId(null);
    }
  };

  const startOverride = (ans: any) => {
    setEditingQuestionId(ans.question_id);
    const currMarks = ans.effective_marks ?? (ans.score_awarded ?? 0);
    setOverrideMarks(String(currMarks));
    const corr = ans.effective_is_correct || (ans.is_correct ? "correct" : currMarks > 0 ? "partial" : "wrong");
    setOverrideCorrectness(corr === "partial" ? "partial" : corr === "wrong" ? "wrong" : "correct");
    setOverrideComment(ans.final_comment || ans.teacher_feedback || "");
    setOverrideReason("");
  };

  const handleSaveOverride = async (ans: any) => {
    if (!selectedAttemptId || !attemptDetail) return;
    const num = parseFloat(overrideMarks);
    if (isNaN(num)) {
      toast.error("Please enter a valid numeric score.");
      return;
    }
    const maxMarks = Number(ans.marks || 1);
    if (num < 0 || num > maxMarks) {
      toast.error(`Score must be between 0 and ${maxMarks} marks.`);
      return;
    }

    const autoMarks = ans.auto_marks !== null && ans.auto_marks !== undefined ? Number(ans.auto_marks) : (ans.score_awarded ?? 0);
    const autoCorr = ans.auto_is_correct || (ans.is_correct ? "correct" : "wrong");
    const isDeviating = num !== autoMarks || overrideCorrectness !== autoCorr;
    if (isDeviating && !overrideReason.trim()) {
      toast.error("Reason is required when changing marks away from auto evaluation.");
      return;
    }

    setSavingOverride(true);
    try {
      await facultyExamApi.overrideQuestionGrade(selectedAttemptId, ans.question_id, {
        final_marks: num,
        final_is_correct: overrideCorrectness,
        final_comment: overrideComment.trim(),
        reason: overrideReason.trim(),
        version: attemptDetail.version,
      });
      toast.success("Question grade overridden successfully!");
      setEditingQuestionId(null);
      await handleOpenAttemptDetail(selectedAttemptId);
      if (selectedExam) {
        const attemptsRes = await facultyExamApi.getExamAttempts(selectedExam.id);
        setAttempts(attemptsRes.attempts || []);
      }
    } catch (err: any) {
      if (err?.response?.status === 409) {
        toast.error("Conflict: Attempt was updated by another session. Refreshed with latest data.");
        await handleOpenAttemptDetail(selectedAttemptId);
      } else {
        toast.error(err?.response?.data?.detail || "Failed to save question override.");
      }
    } finally {
      setSavingOverride(false);
    }
  };

  const handleResetOverride = async (questionId: number) => {
    if (!selectedAttemptId || !attemptDetail) return;
    setResettingQuestionId(questionId);
    try {
      await facultyExamApi.resetQuestionGrade(selectedAttemptId, questionId, {
        version: attemptDetail.version,
      });
      toast.success("Question reset to automatic evaluation!");
      setEditingQuestionId(null);
      await handleOpenAttemptDetail(selectedAttemptId);
      if (selectedExam) {
        const attemptsRes = await facultyExamApi.getExamAttempts(selectedExam.id);
        setAttempts(attemptsRes.attempts || []);
      }
    } catch (err: any) {
      if (err?.response?.status === 409) {
        toast.error("Conflict: Attempt was updated by another session. Refreshed with latest data.");
        await handleOpenAttemptDetail(selectedAttemptId);
      } else {
        toast.error(err?.response?.data?.detail || "Failed to reset question override.");
      }
    } finally {
      setResettingQuestionId(null);
    }
  };

  const handleApproveAsIs = async (attemptId: number) => {
    if (!attemptDetail) return;
    setApprovingAsIs(true);
    try {
      await facultyExamApi.approveAsIsAttempt(attemptId, attemptDetail.version);
      toast.success("Attempt approved as-is and grading finalized!");
      await handleOpenAttemptDetail(attemptId);
      if (selectedExam) {
        const attemptsRes = await facultyExamApi.getExamAttempts(selectedExam.id);
        setAttempts(attemptsRes.attempts || []);
      }
    } catch (err: any) {
      if (err?.response?.status === 409) {
        toast.error("Conflict: Attempt was updated by another session. Refreshed with latest data.");
        await handleOpenAttemptDetail(attemptId);
      } else {
        toast.error(err?.response?.data?.detail || "Failed to approve attempt.");
      }
    } finally {
      setApprovingAsIs(false);
    }
  };

  const handleFinalizeAttemptGrading = async (attemptId: number) => {
    if (!attemptDetail) return;
    setFinalizingAttempt(true);
    try {
      await facultyExamApi.finalizeAttemptGrading(attemptId, attemptDetail.version);
      toast.success("Attempt review finalized! Student notified.");
      setShowFinalizeModal(false);
      await handleOpenAttemptDetail(attemptId);
      if (selectedExam) {
        const attemptsRes = await facultyExamApi.getExamAttempts(selectedExam.id);
        setAttempts(attemptsRes.attempts || []);
      }
    } catch (err: any) {
      if (err?.response?.status === 409) {
        toast.error("Conflict: Attempt was updated by another session. Refreshed with latest data.");
        await handleOpenAttemptDetail(attemptId);
      } else {
        toast.error(err?.response?.data?.detail || "Failed to finalize review.");
      }
    } finally {
      setFinalizingAttempt(false);
    }
  };

  const handleReopenReview = async (attemptId: number) => {
    if (!attemptDetail) return;
    setReopeningReview(true);
    try {
      await facultyExamApi.reopenAttemptReview(attemptId, attemptDetail.version);
      toast.success("Review reopened for editing.");
      await handleOpenAttemptDetail(attemptId);
      if (selectedExam) {
        const attemptsRes = await facultyExamApi.getExamAttempts(selectedExam.id);
        setAttempts(attemptsRes.attempts || []);
      }
    } catch (err: any) {
      if (err?.response?.status === 409) {
        toast.error("Conflict: Attempt was updated by another session. Refreshed with latest data.");
        await handleOpenAttemptDetail(attemptId);
      } else {
        toast.error(err?.response?.data?.detail || "Failed to reopen review.");
      }
    } finally {
      setReopeningReview(false);
    }
  };

  const handleSuggestGrade = async (answerId: number) => {
    setSuggestingAnswerId(answerId);
    try {
      const res = await facultyExamApi.suggestGrade(answerId);
      if ((res as any)?.suggestion_status === "failed") {
        toast.error((res as any)?.detail || "AI suggestion unavailable. Please grade manually.");
      } else {
        toast.success("AI suggestion generated!");
      }
      if (selectedAttemptId) {
        await handleOpenAttemptDetail(selectedAttemptId);
      }
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || "AI suggestion unavailable. Please grade manually.");
    } finally {
      setSuggestingAnswerId(null);
    }
  };

  // Filtered & Sorted Exams
  const filteredExams = useMemo(() => {
    let result = [...exams];

    // Status filter
    if (statusFilter !== "all") {
      result = result.filter((e) => {
        if (statusFilter === "generating") return e.status === "generating";
        if (statusFilter === "draft") return e.status === "draft";
        if (statusFilter === "published") return e.status === "published";
        if (statusFilter === "closed") return e.status === "closed";
        if (statusFilter === "failed") return e.status === "failed";
        return true;
      });
    }

    // Search query
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      result = result.filter(
        (e) =>
          e.title.toLowerCase().includes(q) ||
          e.department?.toLowerCase().includes(q) ||
          e.topics?.some((t) => t.toLowerCase().includes(q))
      );
    }

    // Sort
    result.sort((a, b) => {
      if (sortBy === "title") return a.title.localeCompare(b.title);
      if (sortBy === "marks") return (b.total_marks || 0) - (a.total_marks || 0);
      // newest
      return new Date(b.created_at || 0).getTime() - new Date(a.created_at || 0).getTime();
    });

    return result;
  }, [exams, statusFilter, searchQuery, sortBy]);

  // Check if an exam is newly generated (< 24 hours old and not in viewed list)
  const isNewPaper = (exam: FacultyExam) => {
    if (viewedPaperIds.includes(exam.id)) return false;
    const createdTime = new Date(exam.created_at).getTime();
    const now = Date.now();
    return now - createdTime < 24 * 60 * 60 * 1000;
  };

  return (
    <DashboardLayout menuItems={menuItems} userRole="Faculty">
      <div className="space-y-6">
        {/* Top Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="text-2xl sm:text-3xl font-bold text-foreground mb-1">My Papers & Exams</h1>
            <p className="text-xs sm:text-sm text-muted-foreground">
              Manage draft papers, review AI synthesized questions, and publish exams to students.
            </p>
          </div>
          <button
            type="button"
            onClick={() => navigate("/faculty/generate")}
            className="inline-flex items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-blue-600 to-indigo-600 px-5 py-2.5 text-sm font-bold text-white shadow-md hover:opacity-95 transition-all self-start sm:self-auto"
          >
            <Plus className="h-4 w-4" /> Generate New Paper
          </button>
        </div>

        {/* Filter & Search Bar */}
        <div className="rounded-2xl border border-border bg-white p-4 shadow-xs space-y-3">
          <div className="flex flex-col md:flex-row items-stretch md:items-center justify-between gap-3">
            {/* Search Input */}
            <div className="relative flex-1">
              <Search className="absolute left-3.5 top-2.5 h-4 w-4 text-muted-foreground" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search by paper title, department, or topic..."
                className="w-full rounded-xl border border-border bg-muted/20 pl-10 pr-4 py-2 text-sm focus:outline-hidden focus:ring-2 focus:ring-primary/20 focus:border-primary transition-all"
              />
            </div>

            {/* Sort Dropdown */}
            <div className="flex items-center gap-2 shrink-0">
              <span className="text-xs text-muted-foreground font-medium">Sort by:</span>
              <select
                value={sortBy}
                onChange={(e: any) => setSortBy(e.target.value)}
                className="rounded-xl border border-border bg-muted/20 px-3 py-2 text-xs font-semibold text-foreground focus:outline-hidden"
              >
                <option value="newest">Newest First</option>
                <option value="title">Title (A-Z)</option>
                <option value="marks">Total Marks</option>
              </select>
            </div>
          </div>

          {/* Status Filter Tabs */}
          <div className="flex items-center gap-1.5 overflow-x-auto pt-1 border-t border-border/60">
            {[
              { id: "all", label: "All Papers" },
              { id: "generating", label: "Generating" },
              { id: "draft", label: "Drafts (Needs Review)" },
              { id: "published", label: "Published" },
              { id: "closed", label: "Closed" },
              { id: "failed", label: "Failed" },
            ].map((tab) => (
              <button
                key={tab.id}
                type="button"
                onClick={() => setStatusFilter(tab.id as any)}
                className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all shrink-0 ${
                  statusFilter === tab.id
                    ? "bg-primary text-white shadow-xs"
                    : "text-muted-foreground hover:text-foreground hover:bg-muted/50"
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>
        </div>

        {/* Papers List */}
        {loading ? (
          <div className="space-y-3">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-32 rounded-2xl border border-border bg-white animate-pulse p-6" />
            ))}
          </div>
        ) : filteredExams.length === 0 ? (
          <div className="rounded-2xl border-2 border-dashed border-border bg-white p-12 text-center shadow-xs">
            <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-primary/10 text-primary mb-4">
              <FileText className="h-7 w-7" />
            </div>
            <h3 className="text-base font-bold text-foreground">No papers found</h3>
            <p className="mt-1 text-xs text-muted-foreground max-w-sm mx-auto">
              {searchQuery || statusFilter !== "all"
                ? "No exams match your current filters. Try resetting the search or filter tabs."
                : "No papers generated yet. Create your first balanced exam paper using AI from your syllabus."}
            </p>
            <div className="mt-6 flex justify-center gap-3">
              {searchQuery || statusFilter !== "all" ? (
                <button
                  type="button"
                  onClick={() => {
                    setSearchQuery("");
                    setStatusFilter("all");
                  }}
                  className="rounded-xl border border-border bg-white px-4 py-2 text-xs font-semibold text-foreground hover:bg-muted/50"
                >
                  Reset Filters
                </button>
              ) : (
                <button
                  type="button"
                  onClick={() => navigate("/faculty/generate")}
                  className="inline-flex items-center gap-2 rounded-xl bg-primary px-5 py-2.5 text-xs font-bold text-white shadow-sm hover:opacity-95"
                >
                  <Plus className="h-4 w-4" /> Generate Your First Paper
                </button>
              )}
            </div>
          </div>
        ) : (
          <div className="space-y-3.5">
            {filteredExams.map((exam) => {
              const isGen = exam.status === "generating";
              const isDraft = exam.status === "draft";
              const isReviewRequired = isDraft && !exam.is_reviewed;
              const isPub = exam.status === "published";
              const isFail = exam.status === "failed";
              const isNew = isNewPaper(exam);

              return (
                <div
                  key={exam.id}
                  className={`rounded-2xl border transition-all p-5 sm:p-6 shadow-xs hover:shadow-md ${
                    isReviewRequired
                      ? "border-amber-200 bg-amber-50/20"
                      : isGen
                      ? "border-blue-200 bg-blue-50/20"
                      : "border-border bg-white"
                  }`}
                >
                  <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
                    {/* Left: Info */}
                    <div className="space-y-2 min-w-0 flex-1">
                      <div className="flex items-center gap-2 flex-wrap">
                        <h2 className="text-base sm:text-lg font-bold text-foreground truncate">{exam.title}</h2>

                        {/* "New" Badge */}
                        {isNew && (
                          <span className="inline-flex items-center gap-1 rounded-full bg-gradient-to-r from-blue-600 to-indigo-600 px-2 py-0.5 text-[10px] font-extrabold text-white shadow-xs">
                            <Sparkles className="h-2.5 w-2.5" /> NEW
                          </span>
                        )}

                        {/* Status Badge */}
                        {isGen ? (
                          <button
                            type="button"
                            onClick={() => {
                              const job = recentJobs.find((j) => j.exam_id === exam.id);
                              if (job) {
                                setProgressJobId(job.id);
                                setShowProgressModal(true);
                              }
                            }}
                            className="inline-flex items-center gap-1.5 rounded-full bg-blue-50 px-2.5 py-0.5 text-xs font-bold text-blue-700 border border-blue-200 hover:bg-blue-100 transition-colors animate-pulse"
                            title="Click to view live generation progress"
                          >
                            <Loader2 className="h-3.5 w-3.5 animate-spin" /> Generating...
                          </button>
                        ) : isReviewRequired ? (
                          <span className="inline-flex items-center gap-1 rounded-full bg-amber-100 text-amber-900 border border-amber-300 px-2.5 py-0.5 text-xs font-bold">
                            <AlertTriangle className="h-3.5 w-3.5 text-amber-600" /> Generated · Review Required
                          </span>
                        ) : isDraft ? (
                          <span className="inline-flex items-center gap-1 rounded-full bg-sky-50 text-sky-700 border border-sky-200 px-2.5 py-0.5 text-xs font-semibold">
                            <CheckCircle className="h-3.5 w-3.5 text-sky-600" /> Draft · Reviewed
                          </span>
                        ) : isPub ? (
                          <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200 px-2.5 py-0.5 text-xs font-bold">
                            <Check className="h-3.5 w-3.5" /> Published
                          </span>
                        ) : isFail ? (
                          <span className="inline-flex items-center gap-1 rounded-full bg-rose-50 text-rose-700 border border-rose-200 px-2.5 py-0.5 text-xs font-semibold">
                            <XCircle className="h-3.5 w-3.5" /> Generation Failed
                          </span>
                        ) : (
                          <span className="rounded-full bg-muted text-muted-foreground border border-border px-2.5 py-0.5 text-xs font-medium">
                            {exam.status}
                          </span>
                        )}

                        {/* Schedule Missing Badge */}
                        {isDraft && (!exam.starts_at || !exam.ends_at) && (
                          <span className="inline-flex items-center gap-1 rounded-full bg-amber-50 text-amber-700 border border-amber-200 px-2 py-0.5 text-[11px] font-medium">
                            <Calendar className="h-3 w-3 text-amber-600" /> Schedule Missing
                          </span>
                        )}
                      </div>

                      {/* Meta Tags */}
                      <div className="flex flex-wrap items-center gap-y-1 gap-x-4 text-xs text-muted-foreground">
                        {exam.department && (
                          <span className="font-semibold text-slate-700">{exam.department}</span>
                        )}
                        <span>{exam.question_count ?? exam.questions?.length ?? 0} Questions</span>
                        <span>{exam.total_marks} Total Marks</span>
                        <span>{exam.duration_minutes} Mins</span>
                        {exam.ai_model_used && (
                          <span className="font-mono text-[11px] bg-slate-100 px-2 py-0.5 rounded-md text-slate-600">
                            Model: {exam.ai_model_used}
                          </span>
                        )}
                        <span className="flex items-center gap-1 text-slate-400">
                          <Calendar className="h-3 w-3" />
                          {exam.created_at ? new Date(exam.created_at).toLocaleDateString() : ""}
                        </span>
                      </div>

                      {/* Error details if failed */}
                      {isFail && exam.error_message && (
                        <p className="text-xs text-rose-600 font-medium">{exam.error_message}</p>
                      )}
                    </div>

                    {/* Right: Actions */}
                    <div className="flex flex-wrap items-center gap-2 shrink-0">
                      {isGen ? (
                        <button
                          type="button"
                          onClick={() => {
                            const job = recentJobs.find((j) => j.exam_id === exam.id);
                            if (job) {
                              setProgressJobId(job.id);
                              setShowProgressModal(true);
                            } else {
                              toast.info("Checking generation status...");
                              loadData();
                            }
                          }}
                          className="inline-flex items-center gap-1.5 rounded-xl bg-blue-600 px-4 py-2 text-xs font-bold text-white shadow-sm hover:bg-blue-700"
                        >
                          <Loader2 className="h-3.5 w-3.5 animate-spin" /> View Progress
                        </button>
                      ) : isFail ? (
                        <button
                          type="button"
                          onClick={() => navigate("/faculty/generate")}
                          className="inline-flex items-center gap-1.5 rounded-xl bg-blue-600 px-4 py-2 text-xs font-bold text-white shadow-sm hover:bg-blue-700"
                        >
                          <RefreshCw className="h-3.5 w-3.5" /> Retry
                        </button>
                      ) : (
                        <>
                          <button
                            type="button"
                            onClick={() => handleOpenEdit(exam.id)}
                            className="inline-flex items-center gap-1.5 rounded-xl border border-border bg-white px-3.5 py-2 text-xs font-semibold text-foreground hover:bg-muted/50 transition-colors shadow-2xs"
                          >
                            <Edit3 className="h-3.5 w-3.5" /> Review / Edit
                          </button>

                          {!isPub && (
                            <button
                              type="button"
                              disabled={publishingId === exam.id}
                              onClick={() => void publish(exam)}
                              className={`inline-flex items-center gap-1.5 rounded-xl px-4 py-2 text-xs font-bold transition-all ${
                                isReviewRequired
                                  ? "bg-amber-500 hover:bg-amber-600 text-white shadow-sm"
                                  : "bg-gradient-to-r from-emerald-600 to-teal-600 hover:opacity-95 text-white shadow-sm"
                              }`}
                              title={isReviewRequired ? "Review required before publishing" : "Publish exam to students"}
                            >
                              {publishingId === exam.id ? (
                                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                              ) : (
                                <Check className="h-3.5 w-3.5" />
                              )}
                              Publish
                            </button>
                          )}

                          <button
                            type="button"
                            disabled={duplicatingId === exam.id}
                            onClick={() => void handleDuplicate(exam)}
                            className="inline-flex items-center gap-1 rounded-xl border border-border bg-white px-2.5 py-2 text-xs font-medium text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors"
                            title="Duplicate as new draft"
                          >
                            <Copy className="h-3.5 w-3.5" />
                          </button>

                          <button
                            type="button"
                            onClick={() => setExamToDelete(exam)}
                            className="inline-flex items-center gap-1 rounded-xl border border-border bg-white px-2.5 py-2 text-xs font-medium text-rose-600 hover:bg-rose-50 hover:border-rose-200 transition-colors"
                            title="Delete exam"
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </button>

                          <button
                            type="button"
                            onClick={() => void handleOpenAttempts(exam)}
                            className="inline-flex items-center gap-1.5 rounded-xl border border-border bg-white px-3 py-2 text-xs font-medium text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors"
                          >
                            <Eye className="h-3.5 w-3.5" /> Attempts ({exam.attempts_count ?? 0})
                          </button>
                        </>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {/* Delete Confirmation Modal */}
        {examToDelete && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4 animate-in fade-in duration-150">
            <div className="bg-white rounded-2xl border border-border shadow-2xl w-full max-w-md p-6 space-y-4 animate-in zoom-in-95 duration-150">
              <div className="flex items-center gap-3">
                <div className="p-2.5 rounded-xl bg-rose-50 text-rose-600 shrink-0">
                  <Trash2 className="h-5 w-5" />
                </div>
                <div>
                  <h3 className="font-bold text-foreground text-base">Delete Exam</h3>
                  <p className="text-xs text-muted-foreground">Are you sure you want to permanently delete this exam?</p>
                </div>
              </div>

              <div className="p-3 rounded-xl bg-muted/40 text-xs space-y-1">
                <p className="font-semibold text-foreground truncate">{examToDelete.title}</p>
                <p className="text-muted-foreground">{examToDelete.total_marks} Marks · {examToDelete.department}</p>
              </div>

              <div className="flex justify-end gap-2.5 pt-2">
                <button
                  type="button"
                  disabled={deleting}
                  onClick={() => setExamToDelete(null)}
                  className="rounded-xl border border-border px-4 py-2 text-xs font-semibold text-foreground hover:bg-muted/50"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  disabled={deleting}
                  onClick={confirmDeleteExam}
                  className="inline-flex items-center gap-1.5 rounded-xl bg-rose-600 px-4 py-2 text-xs font-bold text-white shadow-sm hover:bg-rose-700 disabled:opacity-50"
                >
                  {deleting ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Trash2 className="h-3.5 w-3.5" />}
                  Delete
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Real-time Generation Progress Modal */}
        <GenerationProgressModal
          jobId={progressJobId}
          isOpen={showProgressModal}
          onClose={() => {
            setShowProgressModal(false);
            void loadData();
          }}
          onSuccess={() => {
            void loadData();
          }}
        />

        {/* Student Attempts Review Modal */}
        {selectedExam && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4 overflow-y-auto">
            <div className="bg-white rounded-2xl border border-border shadow-2xl w-full max-w-4xl max-h-[90vh] flex flex-col overflow-hidden animate-in fade-in zoom-in-95 duration-200">
              {/* Header */}
              <div className="px-6 py-4 border-b border-border flex items-center justify-between bg-muted/20">
                <div className="flex items-center gap-3">
                  {selectedAttemptId && (
                    <button
                      type="button"
                      onClick={() => setSelectedAttemptId(null)}
                      className="rounded-lg p-1.5 text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
                      title="Back to attempts list"
                    >
                      <ArrowLeft className="h-5 w-5" />
                    </button>
                  )}
                  <div>
                    <h3 className="font-semibold text-lg text-foreground">
                      {selectedAttemptId ? `Review Attempt #${selectedAttemptId}` : `Student Attempts: ${selectedExam.title}`}
                    </h3>
                    <p className="text-xs text-muted-foreground">
                      {selectedAttemptId ? "Detailed answer breakdown and evaluation review." : "Review student submissions and grades."}
                    </p>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => setSelectedExam(null)}
                  className="rounded-lg p-2 text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
                >
                  <X className="h-5 w-5" />
                </button>
              </div>

              {/* Content */}
              <div className="p-6 overflow-y-auto flex-1">
                {!selectedAttemptId ? (
                  loadingAttempts ? (
                    <div className="py-12 flex flex-col items-center justify-center gap-3 text-muted-foreground">
                      <Loader2 className="h-6 w-6 animate-spin text-primary" />
                      <p className="text-sm">Loading attempts...</p>
                    </div>
                  ) : attempts.length === 0 ? (
                    <div className="py-12 text-center text-sm text-muted-foreground">
                      No students have submitted attempts for this exam yet.
                    </div>
                  ) : (
                    <div className="space-y-3">
                      {attempts.map((att: any) => (
                        <div key={att.id} className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 p-4 rounded-xl border border-border bg-white hover:bg-muted/30 transition-colors shadow-xs">
                          <div>
                            <div className="font-semibold text-sm text-foreground">
                              {att.student_name || `Student #${att.student_id}`}
                              <span className="text-xs text-muted-foreground font-normal ml-2">({att.student_email})</span>
                            </div>
                            <div className="text-xs text-muted-foreground mt-0.5 flex items-center gap-3">
                              <span>Submitted: {new Date(att.submitted_at || att.created_at).toLocaleString()}</span>
                              <span className="uppercase text-[10px] font-bold px-2 py-0.5 rounded-full bg-muted border border-border">
                                {att.status}
                              </span>
                            </div>
                          </div>
                          <div className="flex items-center gap-3 shrink-0">
                            <span className="text-sm font-semibold text-primary">
                              {att.total_score} / {selectedExam.total_marks}
                            </span>
                            <button
                              type="button"
                              onClick={() => void handleOpenAttemptDetail(att.id)}
                              className="inline-flex items-center gap-1.5 rounded-lg bg-primary/10 text-primary hover:bg-primary/20 px-3 py-1.5 text-xs font-medium transition-colors"
                            >
                              Review Answers <Eye className="h-3.5 w-3.5" />
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  )
                ) : (
                  loadingDetail ? (
                    <div className="py-12 flex flex-col items-center justify-center gap-3 text-muted-foreground">
                      <Loader2 className="h-6 w-6 animate-spin text-primary" />
                      <p className="text-sm">Loading attempt questions...</p>
                    </div>
                  ) : !attemptDetail ? (
                    <div className="py-12 text-center text-sm text-rose-600">Failed to load attempt details.</div>
                  ) : (
                    <div className="space-y-4">
                      {/* Sticky Review Header */}
                      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 p-4 rounded-xl bg-slate-50 border border-slate-200 shadow-2xs">
                        <div className="space-y-1">
                          <div className="flex flex-wrap items-center gap-2">
                            <span className="text-sm font-bold text-foreground">
                              {attemptDetail.student_name}
                            </span>
                            <span className="text-xs text-muted-foreground">
                              ({attemptDetail.student_email || "No email"})
                            </span>
                            <span className={`px-2.5 py-0.5 rounded-full text-xs font-bold uppercase tracking-wider border ${
                              attemptDetail.review_status === "finalized"
                                ? "bg-emerald-50 text-emerald-700 border-emerald-300"
                                : attemptDetail.review_status === "in_review"
                                ? "bg-indigo-50 text-indigo-700 border-indigo-300"
                                : "bg-amber-50 text-amber-700 border-amber-300"
                            }`}>
                              {attemptDetail.review_status === "finalized"
                                ? "Finalized"
                                : attemptDetail.review_status === "in_review"
                                ? "In Review"
                                : "Provisional (Auto-Evaluated)"}
                            </span>
                          </div>
                          <div className="flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
                            <span>Auto Total: <strong className="text-foreground">{attemptDetail.auto_total ?? 0}</strong></span>
                            <span>·</span>
                            <span>Live Score: <strong className="text-primary font-bold text-sm">{attemptDetail.final_total ?? attemptDetail.total_score}</strong> / {attemptDetail.exam_total_marks} marks</span>
                            <span>·</span>
                            <span>{Math.round(((attemptDetail.final_total ?? attemptDetail.total_score) / (attemptDetail.exam_total_marks || 1)) * 100)}%</span>
                            {attemptDetail.finalized_at && (
                              <>
                                <span>·</span>
                                <span className="text-emerald-700">Reviewed {attemptDetail.reviewed_by ? `by ${attemptDetail.reviewed_by}` : ""} on {new Date(attemptDetail.finalized_at).toLocaleDateString()}</span>
                              </>
                            )}
                          </div>
                        </div>

                        {/* Action Buttons */}
                        <div className="flex flex-wrap items-center gap-2">
                          {attemptDetail.review_status !== "finalized" ? (
                            <>
                              <button
                                type="button"
                                disabled={approvingAsIs || finalizingAttempt}
                                onClick={() => void handleApproveAsIs(attemptDetail.attempt_id)}
                                className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 bg-white hover:bg-slate-100 text-slate-700 px-3 py-2 text-xs font-semibold shadow-2xs transition-colors disabled:opacity-50"
                                title="Approve automatic marks as is without overrides"
                              >
                                {approvingAsIs ? (
                                  <Loader2 className="h-4 w-4 animate-spin" />
                                ) : (
                                  <ShieldCheck className="h-4 w-4 text-emerald-600" />
                                )}
                                Approve As Is
                              </button>
                              <button
                                type="button"
                                disabled={finalizingAttempt || approvingAsIs}
                                onClick={() => setShowFinalizeModal(true)}
                                className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white px-3.5 py-2 text-xs font-bold shadow-sm transition-colors disabled:opacity-50"
                                title="Confirm review and notify student"
                              >
                                <CheckCircle className="h-4 w-4" /> Finalize Review
                              </button>
                            </>
                          ) : (
                            <button
                              type="button"
                              disabled={reopeningReview}
                              onClick={() => void handleReopenReview(attemptDetail.attempt_id)}
                              className="inline-flex items-center gap-1.5 rounded-lg border border-amber-300 bg-amber-50 hover:bg-amber-100 text-amber-800 px-3 py-2 text-xs font-semibold shadow-2xs transition-colors disabled:opacity-50"
                              title="Reopen review to make further corrections"
                            >
                              {reopeningReview ? (
                                <Loader2 className="h-4 w-4 animate-spin" />
                              ) : (
                                <RotateCcw className="h-4 w-4" />
                              )}
                              Reopen Review
                            </button>
                          )}
                        </div>
                      </div>

                      {/* Finalize Confirmation Modal */}
                      {showFinalizeModal && (
                        <div className="fixed inset-0 z-60 bg-black/50 flex items-center justify-center p-4">
                          <div className="bg-white rounded-2xl max-w-md w-full p-6 space-y-4 shadow-xl border border-border">
                            <div className="flex items-center gap-3">
                              <div className="h-10 w-10 rounded-full bg-emerald-100 flex items-center justify-center text-emerald-700 shrink-0">
                                <CheckCircle className="h-6 w-6" />
                              </div>
                              <div>
                                <h3 className="font-bold text-base text-foreground">Finalize Evaluation Review</h3>
                                <p className="text-xs text-muted-foreground mt-0.5">Publish final marks and notify student</p>
                              </div>
                            </div>
                            <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200 text-xs space-y-2">
                              <div className="flex justify-between">
                                <span className="text-muted-foreground">Student:</span>
                                <strong className="text-foreground">{attemptDetail.student_name}</strong>
                              </div>
                              <div className="flex justify-between">
                                <span className="text-muted-foreground">Auto Total:</span>
                                <span>{attemptDetail.auto_total ?? 0} marks</span>
                              </div>
                              <div className="flex justify-between">
                                <span className="text-muted-foreground">Final Total:</span>
                                <strong className="text-emerald-700 font-bold">{attemptDetail.final_total ?? attemptDetail.total_score} / {attemptDetail.exam_total_marks} marks</strong>
                              </div>
                              <div className="flex justify-between">
                                <span className="text-muted-foreground">Overridden Questions:</span>
                                <span className="font-semibold text-purple-700">
                                  {attemptDetail.answers?.filter((a: any) => a.overridden)?.length ?? 0} of {attemptDetail.answers?.length ?? 0}
                                </span>
                              </div>
                            </div>
                            <p className="text-xs text-muted-foreground leading-relaxed">
                              This replaces the provisional result with final marks. The student will be notified and can view the updated marks and comments for any overridden questions.
                            </p>
                            <div className="flex items-center justify-end gap-2 pt-2">
                              <button
                                type="button"
                                onClick={() => setShowFinalizeModal(false)}
                                className="px-3.5 py-2 rounded-lg border border-border text-xs font-medium text-foreground hover:bg-muted transition-colors"
                              >
                                Cancel
                              </button>
                              <button
                                type="button"
                                disabled={finalizingAttempt}
                                onClick={() => void handleFinalizeAttemptGrading(attemptDetail.attempt_id)}
                                className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-emerald-600 text-white text-xs font-bold hover:bg-emerald-700 transition-colors disabled:opacity-50"
                              >
                                {finalizingAttempt ? <Loader2 className="h-4 w-4 animate-spin" /> : <Check className="h-4 w-4" />}
                                Confirm & Finalize
                              </button>
                            </div>
                          </div>
                        </div>
                      )}

                      {/* Question Cards */}
                      <div className="space-y-4">
                        {attemptDetail.answers?.map((ans: any, idx: number) => {
                          const qType = String(ans.question_type || "").toLowerCase().trim();
                          const isFillBlank = qType === "fill_blank" || qType === "fillblank";
                          const isSubjective = ["subjective", "short_answer", "long_answer"].includes(qType);
                          const isMCQ = ["mcq", "true_false", "truefalse"].includes(qType);
                          const isOverridden = Boolean(ans.overridden);
                          const isEditing = editingQuestionId === ans.question_id;
                          const effectiveMarks = ans.effective_marks ?? (ans.score_awarded ?? 0);
                          const effectiveCorr = ans.effective_is_correct || (ans.is_correct ? "correct" : effectiveMarks > 0 ? "partial" : "wrong");

                          return (
                            <div
                              key={ans.id}
                              className={`rounded-xl border p-4 shadow-2xs space-y-3 transition-colors ${
                                isOverridden
                                  ? "border-purple-300 bg-purple-50/20"
                                  : "border-border bg-white"
                              }`}
                            >
                              {/* Question Header */}
                              <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-2">
                                <div className="space-y-1">
                                  <div className="flex flex-wrap items-center gap-2">
                                    <span className="text-xs font-bold uppercase text-muted-foreground tracking-wider">
                                      Q{idx + 1} · {ans.question_type} ({ans.marks} Marks)
                                    </span>
                                    {/* Auto Pill */}
                                    <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold border ${
                                      ans.auto_is_correct === "correct"
                                        ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                                        : ans.auto_is_correct === "partial"
                                        ? "bg-amber-50 text-amber-700 border-amber-200"
                                        : "bg-rose-50 text-rose-700 border-rose-200"
                                    }`}>
                                      Auto: {ans.auto_is_correct || (ans.is_correct ? "correct" : "wrong")} ({ans.auto_marks ?? 0}m)
                                    </span>
                                    {/* Overridden Pill */}
                                    {isOverridden && (
                                      <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-purple-100 text-purple-800 border border-purple-300">
                                        Overridden: {ans.final_is_correct} ({ans.final_marks}m)
                                      </span>
                                    )}
                                  </div>
                                  <p className="text-sm font-semibold text-foreground mt-1">{ans.question_text}</p>
                                </div>
                                <div className="flex items-center gap-2 shrink-0">
                                  <div className="text-right">
                                    <span className="text-[10px] uppercase font-bold text-muted-foreground block">Effective</span>
                                    <strong className="text-base font-bold text-primary">
                                      {effectiveMarks} / {ans.marks}
                                    </strong>
                                  </div>
                                  {effectiveCorr === "correct" ? (
                                    <CheckCircle className="h-5 w-5 text-emerald-600 shrink-0" />
                                  ) : effectiveCorr === "partial" ? (
                                    <AlertCircle className="h-5 w-5 text-amber-600 shrink-0" />
                                  ) : (
                                    <XCircle className="h-5 w-5 text-rose-600 shrink-0" />
                                  )}
                                </div>
                              </div>

                              {/* MCQ Options Display */}
                              {isMCQ && ans.options && ans.options.length > 0 && (
                                <div className="space-y-1.5 pt-2 border-t border-border">
                                  <span className="text-xs font-semibold text-muted-foreground">Options:</span>
                                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs">
                                    {ans.options.map((opt: string, optIdx: number) => {
                                      const letter = String.fromCharCode(65 + optIdx);
                                      const isSubmitted = String(ans.student_answer || "").trim().toLowerCase() === opt.toLowerCase() ||
                                                          String(ans.student_answer || "").trim().toUpperCase() === letter;
                                      const isCorrectOpt = String(ans.correct_answer || "").trim().toLowerCase() === opt.toLowerCase() ||
                                                           String(ans.correct_answer || "").trim().toUpperCase() === letter;

                                      return (
                                        <div
                                          key={optIdx}
                                          className={`p-2.5 rounded-lg border flex items-center justify-between gap-2 ${
                                            isCorrectOpt
                                              ? "border-emerald-300 bg-emerald-50/70 text-emerald-950 font-medium"
                                              : isSubmitted
                                              ? "border-rose-300 bg-rose-50/50 text-rose-950"
                                              : "border-border bg-slate-50/50 text-foreground"
                                          }`}
                                        >
                                          <div className="flex items-center gap-2">
                                            <span className="font-bold text-[11px] text-muted-foreground">{letter}.</span>
                                            <span>{opt}</span>
                                          </div>
                                          <div className="flex items-center gap-1 shrink-0">
                                            {isCorrectOpt && (
                                              <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-emerald-200/80 text-emerald-800">
                                                Key
                                              </span>
                                            )}
                                            {isSubmitted && (
                                              <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-blue-100 text-blue-800">
                                                Student
                                              </span>
                                            )}
                                          </div>
                                        </div>
                                      );
                                    })}
                                  </div>
                                </div>
                              )}

                              {/* Fill in the Blank details */}
                              {isFillBlank && (
                                <div className="space-y-2 pt-2 border-t border-border">
                                  {ans.blank_answers && ans.blank_answers.length > 0 && (
                                    <div className="rounded-lg bg-purple-50/60 border border-purple-200 p-3 text-xs text-purple-950">
                                      <span className="font-bold block mb-1 text-purple-900">Student Blanks:</span>
                                      <div className="flex flex-wrap gap-2">
                                        {ans.blank_answers.map((b: string, bIdx: number) => (
                                          <span key={bIdx} className="px-2.5 py-1 rounded-md bg-white border border-purple-300 font-mono text-xs">
                                            Blank #{bIdx + 1}: <strong className="text-purple-800">{b || "(empty)"}</strong>
                                          </span>
                                        ))}
                                      </div>
                                    </div>
                                  )}
                                  {ans.accepted_answers && (
                                    <div className="text-xs text-muted-foreground bg-muted/20 p-2.5 rounded-lg border border-border/60">
                                      <strong className="text-foreground">Accepted Key:</strong>{" "}
                                      <span className="font-mono">
                                        {typeof ans.accepted_answers === "object"
                                          ? JSON.stringify(ans.accepted_answers)
                                          : String(ans.accepted_answers)}
                                      </span>
                                    </div>
                                  )}
                                </div>
                              )}

                              {/* Subjective Model Answer & Rubric */}
                              {isSubjective && (
                                <div className="space-y-2 pt-2 border-t border-border text-xs">
                                  {ans.model_answer && (
                                    <div className="rounded-lg bg-slate-50 border border-slate-200 p-2.5 text-slate-700">
                                      <strong className="text-slate-900 block mb-0.5">Model Answer / Key Points:</strong>
                                      <p className="whitespace-pre-wrap">{ans.model_answer}</p>
                                    </div>
                                  )}
                                  {ans.rubric && (
                                    <div className="rounded-lg bg-slate-50/60 border border-slate-200/60 p-2 text-slate-600">
                                      <strong className="text-slate-800">Grading Rubric:</strong>{" "}
                                      {typeof ans.rubric === "string" ? ans.rubric : JSON.stringify(ans.rubric)}
                                    </div>
                                  )}
                                </div>
                              )}

                              {/* Student Submitted Answer */}
                              <div className="rounded-lg bg-muted/30 p-3 text-xs sm:text-sm">
                                <span className="font-medium text-muted-foreground block mb-1">Student Answer:</span>
                                <p className="text-foreground whitespace-pre-wrap">{ans.student_answer || "(No answer was submitted)"}</p>
                              </div>

                              {/* Auto Evaluation Feedback */}
                              <div className="rounded-lg bg-slate-50 border border-slate-200 p-2.5 text-xs flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                                <div>
                                  <span className="font-semibold text-slate-700">
                                    Automatic Evaluation ({ans.auto_source === "rules" ? "Deterministic Rules" : "AI"}):
                                  </span>
                                  <p className="text-muted-foreground mt-0.5">{ans.auto_feedback || ans.ai_feedback || "None"}</p>
                                </div>
                                <span className="text-[11px] text-muted-foreground whitespace-nowrap">
                                  Awarded: <strong className="text-foreground">{ans.auto_marks ?? 0}m</strong>
                                </span>
                              </div>

                              {/* Faculty Override Card (if overridden) */}
                              {isOverridden && (
                                <div className="rounded-lg bg-purple-50/70 border border-purple-200 p-3 text-xs text-purple-950 space-y-2">
                                  <div className="flex flex-wrap items-center justify-between gap-2">
                                    <div className="font-bold flex items-center gap-1.5 text-purple-900">
                                      <Edit3 className="h-3.5 w-3.5 text-purple-700" />
                                      Faculty Override Applied: {ans.final_marks} / {ans.marks} Marks ({ans.final_is_correct})
                                    </div>
                                    <button
                                      type="button"
                                      disabled={resettingQuestionId === ans.question_id}
                                      onClick={() => void handleResetOverride(ans.question_id)}
                                      className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md bg-white border border-purple-300 text-purple-800 hover:bg-purple-100 font-semibold text-[11px] shadow-2xs transition-colors disabled:opacity-50"
                                      title="Revert override back to automatic evaluation"
                                    >
                                      {resettingQuestionId === ans.question_id ? (
                                        <Loader2 className="h-3 w-3 animate-spin" />
                                      ) : (
                                        <RotateCcw className="h-3 w-3" />
                                      )}
                                      Reset to Auto
                                    </button>
                                  </div>
                                  {ans.final_comment && (
                                    <p className="text-purple-900">
                                      <strong className="text-purple-950">Faculty Comment:</strong> {ans.final_comment}
                                    </p>
                                  )}
                                  <div className="text-[11px] text-purple-700">
                                    Updated {ans.overridden_by ? `by ${ans.overridden_by}` : ""} {ans.overridden_at ? `on ${new Date(ans.overridden_at).toLocaleString()}` : ""}
                                  </div>
                                </div>
                              )}

                              {/* Action Buttons Row */}
                              <div className="flex flex-wrap items-center justify-between gap-2 pt-2 border-t border-border">
                                <div className="flex items-center gap-2">
                                  <button
                                    type="button"
                                    onClick={() => isEditing ? setEditingQuestionId(null) : startOverride(ans)}
                                    className="inline-flex items-center gap-1.5 rounded-lg border border-border px-3 py-1.5 text-xs font-semibold text-foreground hover:bg-muted/60 transition-colors"
                                  >
                                    <Edit3 className="h-3.5 w-3.5 text-primary" />
                                    {isOverridden ? "Edit Override" : "Override Evaluation"}
                                  </button>
                                  {isSubjective && (
                                    <button
                                      type="button"
                                      disabled={suggestingAnswerId === ans.id}
                                      onClick={() => void handleSuggestGrade(ans.id)}
                                      className="inline-flex items-center gap-1 rounded-lg border border-indigo-200 bg-indigo-50 text-indigo-700 hover:bg-indigo-100 px-2.5 py-1.5 text-xs font-semibold transition-colors disabled:opacity-50"
                                    >
                                      {suggestingAnswerId === ans.id ? (
                                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                                      ) : (
                                        <Sparkles className="h-3.5 w-3.5 text-indigo-600" />
                                      )}
                                      AI Suggest
                                    </button>
                                  )}
                                </div>

                                {ans.audit_history && ans.audit_history.length > 0 && (
                                  <button
                                    type="button"
                                    onClick={() => setExpandedAuditQuestionId(expandedAuditQuestionId === ans.question_id ? null : ans.question_id)}
                                    className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground font-medium transition-colors"
                                  >
                                    <History className="h-3.5 w-3.5" />
                                    Change Log ({ans.audit_history.length})
                                    {expandedAuditQuestionId === ans.question_id ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
                                  </button>
                                )}
                              </div>

                              {/* Override Editing Form */}
                              {isEditing && (
                                <div className="mt-3 p-4 rounded-xl border border-primary/30 bg-primary/5 space-y-3">
                                  <div className="flex items-center justify-between">
                                    <span className="text-xs font-bold text-primary uppercase tracking-wider">
                                      Faculty Evaluation Override
                                    </span>
                                    <button
                                      type="button"
                                      onClick={() => setEditingQuestionId(null)}
                                      className="text-xs text-muted-foreground hover:text-foreground"
                                    >
                                      Cancel
                                    </button>
                                  </div>

                                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                                    {/* Correctness Segmented Control */}
                                    <div className="space-y-1">
                                      <label className="text-xs font-semibold text-foreground">Marking Decision</label>
                                      <div className="grid grid-cols-3 gap-1 rounded-lg bg-white p-1 border border-border">
                                        <button
                                          type="button"
                                          onClick={() => setOverrideCorrectness("correct")}
                                          className={`py-1 text-xs font-bold rounded-md transition-all ${
                                            overrideCorrectness === "correct"
                                              ? "bg-emerald-600 text-white shadow-xs"
                                              : "text-muted-foreground hover:text-foreground"
                                          }`}
                                        >
                                          Right
                                        </button>
                                        <button
                                          type="button"
                                          onClick={() => setOverrideCorrectness("partial")}
                                          className={`py-1 text-xs font-bold rounded-md transition-all ${
                                            overrideCorrectness === "partial"
                                              ? "bg-amber-500 text-white shadow-xs"
                                              : "text-muted-foreground hover:text-foreground"
                                          }`}
                                        >
                                          Partial
                                        </button>
                                        <button
                                          type="button"
                                          onClick={() => setOverrideCorrectness("wrong")}
                                          className={`py-1 text-xs font-bold rounded-md transition-all ${
                                            overrideCorrectness === "wrong"
                                              ? "bg-rose-600 text-white shadow-xs"
                                              : "text-muted-foreground hover:text-foreground"
                                          }`}
                                        >
                                          Wrong
                                        </button>
                                      </div>
                                    </div>

                                    {/* Marks Input */}
                                    <div className="space-y-1">
                                      <label className="text-xs font-semibold text-foreground">
                                        Marks Awarded (Max: {ans.marks})
                                      </label>
                                      <input
                                        type="number"
                                        value={overrideMarks}
                                        onChange={(e) => setOverrideMarks(e.target.value)}
                                        min={0}
                                        max={ans.marks}
                                        step={0.5}
                                        className="w-full rounded-lg border border-border bg-white px-3 py-1.5 text-xs text-foreground focus:outline-hidden focus:ring-2 focus:ring-primary/20"
                                        placeholder={`0 - ${ans.marks}`}
                                      />
                                    </div>
                                  </div>

                                  {/* Comment for Student */}
                                  <div className="space-y-1">
                                    <label className="text-xs font-semibold text-foreground">
                                      Faculty Comment (Visible to student once finalized)
                                    </label>
                                    <input
                                      type="text"
                                      value={overrideComment}
                                      onChange={(e) => setOverrideComment(e.target.value)}
                                      className="w-full rounded-lg border border-border bg-white px-3 py-1.5 text-xs text-foreground focus:outline-hidden focus:ring-2 focus:ring-primary/20"
                                      placeholder="Explain evaluation or acceptable alternative..."
                                    />
                                  </div>

                                  {/* Audit Log Reason */}
                                  <div className="space-y-1">
                                    <label className="text-xs font-semibold text-foreground">
                                      Reason for Override <span className="text-rose-500 font-bold">*</span> (Audit Log)
                                    </label>
                                    <input
                                      type="text"
                                      value={overrideReason}
                                      onChange={(e) => setOverrideReason(e.target.value)}
                                      className="w-full rounded-lg border border-border bg-white px-3 py-1.5 text-xs text-foreground focus:outline-hidden focus:ring-2 focus:ring-primary/20"
                                      placeholder="Required when deviating from auto evaluation..."
                                    />
                                  </div>

                                  <div className="flex items-center justify-end gap-2 pt-1">
                                    <button
                                      type="button"
                                      onClick={() => setEditingQuestionId(null)}
                                      className="px-3 py-1.5 rounded-lg border border-border text-xs text-foreground hover:bg-muted"
                                    >
                                      Cancel
                                    </button>
                                    <button
                                      type="button"
                                      disabled={savingOverride}
                                      onClick={() => void handleSaveOverride(ans)}
                                      className="inline-flex items-center gap-1.5 px-4 py-1.5 rounded-lg bg-primary text-white text-xs font-bold hover:opacity-90 disabled:opacity-50 shadow-xs"
                                    >
                                      {savingOverride ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Check className="h-3.5 w-3.5" />}
                                      Save Override
                                    </button>
                                  </div>
                                </div>
                              )}

                              {/* Audit Log Drawer */}
                              {expandedAuditQuestionId === ans.question_id && ans.audit_history && ans.audit_history.length > 0 && (
                                <div className="mt-2 p-3 rounded-lg bg-slate-50 border border-slate-200 space-y-2 text-xs">
                                  <span className="font-bold text-slate-800 block">Change History</span>
                                  <div className="space-y-1.5">
                                    {ans.audit_history.map((log: any) => (
                                      <div key={log.id} className="p-2 rounded bg-white border border-slate-200 text-xs text-slate-700 space-y-0.5">
                                        <div className="flex items-center justify-between text-[11px] text-muted-foreground">
                                          <span><strong>{log.changed_by}</strong> on {new Date(log.created_at).toLocaleString()}</span>
                                          <span className="font-mono">{log.old_marks}m ({log.old_correctness}) → {log.new_marks}m ({log.new_correctness})</span>
                                        </div>
                                        <div className="text-slate-900">
                                          <strong>Reason:</strong> {log.reason}
                                        </div>
                                      </div>
                                    ))}
                                  </div>
                                </div>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  )
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}

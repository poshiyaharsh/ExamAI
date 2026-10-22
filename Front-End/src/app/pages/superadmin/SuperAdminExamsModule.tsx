import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import {
  Search,
  Filter,
  X,
  RotateCcw,
  Download,
  Calendar,
  Clock,
  Building2,
  Users,
  GraduationCap,
  Sparkles,
  AlertTriangle,
  CheckCircle2,
  FileSpreadsheet,
  FileText,
  SlidersHorizontal,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  RefreshCw,
  ShieldAlert,
  ArrowUpDown,
  BookOpen,
} from 'lucide-react';

interface SuperAdminExamsModuleProps {
  saFetch: (endpoint: string, options?: RequestInit) => Promise<Response>;
  onTriggerReauth: (callback: () => void) => void;
}

interface FilterMetadata {
  institutions: Array<{ id: number; institution_name: string; institution_code: string }>;
  departments: string[];
  faculty: Array<{ id: number; name: string; email: string; department: string }>;
  ai_models: string[];
  status_counts: Record<string, number>;
  allowed_statuses: string[];
  allowed_phases: string[];
  allowed_question_types: string[];
}

interface ExamItem {
  id: number;
  title: string;
  subject: string;
  department: string;
  institution: { id: number | null; name: string; code: string };
  faculty: { id: number | null; username: string; full_name: string; email: string };
  status: string;
  schedule_phase: string;
  duration_minutes: number;
  total_marks: number;
  target_total_marks: number | null;
  marks_shortfall: number;
  starts_at: string | null;
  ends_at: string | null;
  closing_soon: boolean;
  is_immutable: boolean;
  ai_model_used: string;
  attempts_count: number;
  pending_grading_count: number;
  flagged_students_count: number;
  questions_count: number;
  created_at: string;
}

export function SuperAdminExamsModule({ saFetch, onTriggerReauth }: SuperAdminExamsModuleProps) {
  // Query & Filter State
  const [search, setSearch] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [institutionId, setInstitutionId] = useState<string>('all');
  const [department, setDepartment] = useState<string>('all');
  const [facultyId, setFacultyId] = useState<string>('all');
  const [selectedStatuses, setSelectedStatuses] = useState<string[]>([]);
  const [selectedPhase, setSelectedPhase] = useState<string>('all');
  const [closingSoon, setClosingSoon] = useState(false);
  const [missingSchedule, setMissingSchedule] = useState(false);
  const [hasShortfall, setHasShortfall] = useState<string>('all');
  const [selectedQTypes, setSelectedQTypes] = useState<string[]>([]);
  const [hasAttempts, setHasAttempts] = useState<string>('all');
  const [hasPendingGrading, setHasPendingGrading] = useState(false);
  const [hasFlaggedStudents, setHasFlaggedStudents] = useState(false);
  const [aiModel, setAiModel] = useState<string>('all');
  const [sortBy, setSortBy] = useState<string>('created');

  // Advanced Drawer state
  const [filtersOpen, setFiltersOpen] = useState(false);

  // Pagination State
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [totalCount, setTotalCount] = useState(0);
  const [totalPages, setTotalPages] = useState(1);

  // Data & Loading
  const [exams, setExams] = useState<ExamItem[]>([]);
  const [metadata, setMetadata] = useState<FilterMetadata | null>(null);
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState(false);

  // Abort controller reference for cancelling outdated queries
  const abortControllerRef = useRef<AbortController | null>(null);

  // Debounce search by 300ms
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(search);
      setPage(1);
    }, 300);
    return () => clearTimeout(timer);
  }, [search]);

  // Load Filter Metadata on Mount and when institution changes
  useEffect(() => {
    const fetchMetadata = async () => {
      try {
        const query = institutionId && institutionId !== 'all' ? `?institution_id=${institutionId}` : '';
        const res = await saFetch(`exams/metadata/${query}`);
        if (res.ok) {
          const body = await res.json();
          setMetadata(body.metadata);
        }
      } catch (err) {
        console.error('Failed to load filter metadata', err);
      }
    };
    fetchMetadata();
  }, [institutionId, saFetch]);

  // Fetch Exams with all active filters
  const fetchExams = useCallback(async () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    const controller = new AbortController();
    abortControllerRef.current = controller;

    setLoading(true);
    try {
      const params = new URLSearchParams();
      params.set('page', String(page));
      params.set('page_size', String(pageSize));
      params.set('sort_by', sortBy);

      if (debouncedSearch.trim()) params.set('search', debouncedSearch.trim());
      if (institutionId !== 'all') params.set('institution_id', institutionId);
      if (department !== 'all') params.set('department', department);
      if (facultyId !== 'all') params.set('faculty_id', facultyId);
      if (selectedStatuses.length > 0) params.set('status', selectedStatuses.join(','));
      if (selectedPhase !== 'all') params.set('phase', selectedPhase);
      if (closingSoon) params.set('closing_soon', 'true');
      if (missingSchedule) params.set('missing_schedule', 'true');
      if (hasShortfall !== 'all') params.set('has_shortfall', hasShortfall === 'yes' ? 'true' : 'false');
      if (selectedQTypes.length > 0) params.set('question_types', selectedQTypes.join(','));
      if (hasAttempts !== 'all') params.set('has_attempts', hasAttempts === 'yes' ? 'true' : 'false');
      if (hasPendingGrading) params.set('has_pending_grading', 'true');
      if (hasFlaggedStudents) params.set('has_flagged_students', 'true');
      if (aiModel !== 'all') params.set('ai_model', aiModel);

      // Sync filter state to browser URL without reload
      const searchString = params.toString();
      const currentUrl = new URL(window.location.href);
      currentUrl.search = searchString;
      window.history.replaceState({}, '', currentUrl.toString());

      const res = await saFetch(`exams/?${searchString}`, { signal: controller.signal });
      if (res.ok) {
        const body = await res.json();
        setExams(body.data || []);
        setTotalCount(body.pagination?.total_count || 0);
        setTotalPages(body.pagination?.total_pages || 1);
      }
    } catch (err: any) {
      if (err.name !== 'AbortError') {
        console.error('Failed to fetch filtered exams', err);
      }
    } finally {
      setLoading(false);
    }
  }, [
    page,
    pageSize,
    sortBy,
    debouncedSearch,
    institutionId,
    department,
    facultyId,
    selectedStatuses,
    selectedPhase,
    closingSoon,
    missingSchedule,
    hasShortfall,
    selectedQTypes,
    hasAttempts,
    hasPendingGrading,
    hasFlaggedStudents,
    aiModel,
    saFetch,
  ]);

  useEffect(() => {
    fetchExams();
  }, [fetchExams]);

  // Clear all filters
  const handleClearAll = () => {
    setSearch('');
    setDebouncedSearch('');
    setInstitutionId('all');
    setDepartment('all');
    setFacultyId('all');
    setSelectedStatuses([]);
    setSelectedPhase('all');
    setClosingSoon(false);
    setMissingSchedule(false);
    setHasShortfall('all');
    setSelectedQTypes([]);
    setHasAttempts('all');
    setHasPendingGrading(false);
    setHasFlaggedStudents(false);
    setAiModel('all');
    setSortBy('created');
    setPage(1);
  };

  // Status toggle
  const toggleStatus = (st: string) => {
    setSelectedStatuses((prev) =>
      prev.includes(st) ? prev.filter((x) => x !== st) : [...prev, st]
    );
    setPage(1);
  };

  // Question Type toggle
  const toggleQType = (qt: string) => {
    setSelectedQTypes((prev) =>
      prev.includes(qt) ? prev.filter((x) => x !== qt) : [...prev, qt]
    );
    setPage(1);
  };

  // Export Trigger
  const handleExport = async (format: 'csv' | 'xlsx') => {
    setExporting(true);
    try {
      const params = new URLSearchParams();
      params.set('format', format);
      if (debouncedSearch.trim()) params.set('search', debouncedSearch.trim());
      if (institutionId !== 'all') params.set('institution_id', institutionId);
      if (department !== 'all') params.set('department', department);
      if (facultyId !== 'all') params.set('faculty_id', facultyId);
      if (selectedStatuses.length > 0) params.set('status', selectedStatuses.join(','));
      if (selectedPhase !== 'all') params.set('phase', selectedPhase);
      if (closingSoon) params.set('closing_soon', 'true');
      if (missingSchedule) params.set('missing_schedule', 'true');
      if (hasShortfall !== 'all') params.set('has_shortfall', hasShortfall === 'yes' ? 'true' : 'false');
      if (selectedQTypes.length > 0) params.set('question_types', selectedQTypes.join(','));
      if (hasAttempts !== 'all') params.set('has_attempts', hasAttempts === 'yes' ? 'true' : 'false');
      if (hasPendingGrading) params.set('has_pending_grading', 'true');
      if (hasFlaggedStudents) params.set('has_flagged_students', 'true');
      if (aiModel !== 'all') params.set('ai_model', aiModel);

      const res = await saFetch(`exams/export/?${params.toString()}`);
      if (res.ok) {
        const blob = await res.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `global_exams_${Date.now()}.${format}`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
      } else {
        alert('Export failed.');
      }
    } catch (err: any) {
      alert(err?.message || 'Export error.');
    } finally {
      setExporting(false);
    }
  };

  // Force close action
  const handleForceClose = (exam: ExamItem) => {
    const reason = window.prompt(`Enter mandatory justification reason to force-close exam "${exam.title}":`);
    if (!reason || !reason.trim()) return;

    onTriggerReauth(async () => {
      try {
        const res = await saFetch(`exams/${exam.id}/force-close/`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ reason: reason.trim() }),
        });
        if (res.ok) {
          fetchExams();
        } else {
          const body = await res.json();
          alert(body?.message || 'Failed to force close exam.');
        }
      } catch (err: any) {
        alert(err?.message || 'Error occurred.');
      }
    });
  };

  // Active filter count calculation
  const activeFilterCount = useMemo(() => {
    let count = 0;
    if (debouncedSearch.trim()) count++;
    if (institutionId !== 'all') count++;
    if (department !== 'all') count++;
    if (facultyId !== 'all') count++;
    if (selectedStatuses.length > 0) count += selectedStatuses.length;
    if (selectedPhase !== 'all') count++;
    if (closingSoon) count++;
    if (missingSchedule) count++;
    if (hasShortfall !== 'all') count++;
    if (selectedQTypes.length > 0) count += selectedQTypes.length;
    if (hasAttempts !== 'all') count++;
    if (hasPendingGrading) count++;
    if (hasFlaggedStudents) count++;
    if (aiModel !== 'all') count++;
    return count;
  }, [
    debouncedSearch,
    institutionId,
    department,
    facultyId,
    selectedStatuses,
    selectedPhase,
    closingSoon,
    missingSchedule,
    hasShortfall,
    selectedQTypes,
    hasAttempts,
    hasPendingGrading,
    hasFlaggedStudents,
    aiModel,
  ]);

  const startIndex = totalCount === 0 ? 0 : (page - 1) * pageSize + 1;
  const endIndex = Math.min(page * pageSize, totalCount);

  return (
    <div className="space-y-5 min-w-0 max-w-full">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800 pb-5">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl sm:text-2xl font-bold text-white tracking-tight">Global Exams Manager</h1>
            <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
              Cross-Tenant
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Server-side filtered examination blueprints, live test windows, and supervision controls.
          </p>
        </div>

        {/* Actions Toolbar */}
        <div className="flex items-center gap-2 self-start sm:self-auto">
          <button
            type="button"
            onClick={() => handleExport('csv')}
            disabled={exporting || totalCount === 0}
            className="px-3 py-1.5 rounded-xl bg-slate-900 hover:bg-slate-800 text-slate-300 hover:text-white border border-slate-800 text-xs font-semibold transition-all flex items-center gap-1.5 cursor-pointer disabled:opacity-50"
          >
            <Download className="w-3.5 h-3.5" />
            <span>CSV</span>
          </button>
          <button
            type="button"
            onClick={() => handleExport('xlsx')}
            disabled={exporting || totalCount === 0}
            className="px-3 py-1.5 rounded-xl bg-slate-900 hover:bg-slate-800 text-slate-300 hover:text-white border border-slate-800 text-xs font-semibold transition-all flex items-center gap-1.5 cursor-pointer disabled:opacity-50"
          >
            <FileSpreadsheet className="w-3.5 h-3.5" />
            <span>Excel</span>
          </button>
          <button
            type="button"
            onClick={fetchExams}
            disabled={loading}
            className="p-2 rounded-xl bg-slate-900 hover:bg-slate-800 text-slate-300 hover:text-white border border-slate-800 transition-all cursor-pointer disabled:opacity-50"
            title="Refresh List"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin text-emerald-400' : ''}`} />
          </button>
        </div>
      </div>

      {/* Main Filter & Search Bar */}
      <div className="bg-slate-900/70 border border-slate-800 rounded-2xl p-4 space-y-3">
        <div className="flex flex-col md:flex-row items-center gap-3">
          {/* Debounced Search Input */}
          <div className="relative flex-1 w-full">
            <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
            <input
              type="text"
              placeholder="Search exam title, subject, department, faculty, or ID..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full pl-9 pr-8 py-2 bg-slate-950 border border-slate-800 rounded-xl text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-emerald-500/40"
            />
            {search && (
              <button
                type="button"
                onClick={() => setSearch('')}
                className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-500 hover:text-white"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            )}
          </div>

          {/* Quick Filters */}
          <div className="flex items-center gap-2 w-full md:w-auto">
            {/* Institution Selector */}
            <select
              value={institutionId}
              onChange={(e) => {
                setInstitutionId(e.target.value);
                setDepartment('all');
                setFacultyId('all');
                setPage(1);
              }}
              className="px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-xs text-slate-300 focus:outline-none focus:border-emerald-500 w-full md:w-44"
            >
              <option value="all">All Institutions</option>
              {metadata?.institutions.map((inst) => (
                <option key={inst.id} value={inst.id}>
                  {inst.institution_name}
                </option>
              ))}
            </select>

            {/* Schedule Phase */}
            <select
              value={selectedPhase}
              onChange={(e) => {
                setSelectedPhase(e.target.value);
                setPage(1);
              }}
              className="px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-xs text-slate-300 focus:outline-none focus:border-emerald-500"
            >
              <option value="all">All Phases</option>
              <option value="upcoming">Upcoming</option>
              <option value="live">Live Now</option>
              <option value="ended">Ended</option>
            </select>

            {/* Sort Dropdown */}
            <select
              value={sortBy}
              onChange={(e) => {
                setSortBy(e.target.value);
                setPage(1);
              }}
              className="px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-xs text-slate-300 focus:outline-none focus:border-emerald-500"
            >
              <option value="created">Newest Created</option>
              <option value="created_asc">Oldest Created</option>
              <option value="title">Title (A-Z)</option>
              <option value="start">Start Time</option>
              <option value="end">End Time</option>
              <option value="marks">Highest Marks</option>
              <option value="shortfall">Largest Shortfall</option>
              <option value="attempts">Most Attempts</option>
            </select>

            {/* Toggle Advanced Filters Button */}
            <button
              type="button"
              onClick={() => setFiltersOpen(!filtersOpen)}
              className={`px-3 py-2 rounded-xl border text-xs font-semibold transition-all flex items-center gap-1.5 cursor-pointer shrink-0 ${
                filtersOpen || activeFilterCount > 0
                  ? 'bg-emerald-500/10 border-emerald-500/40 text-emerald-300'
                  : 'bg-slate-950 border-slate-800 text-slate-300 hover:text-white'
              }`}
            >
              <SlidersHorizontal className="w-3.5 h-3.5" />
              <span>Filters</span>
              {activeFilterCount > 0 && (
                <span className="ml-0.5 px-1.5 py-0.2 rounded-full bg-emerald-500 text-slate-950 font-bold text-[10px]">
                  {activeFilterCount}
                </span>
              )}
            </button>
          </div>
        </div>

        {/* Collapsible Advanced Filters Panel */}
        {filtersOpen && (
          <div className="pt-4 border-t border-slate-800/80 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 animate-in fade-in duration-200">
            {/* 1. Department & Faculty Dependent Selectors */}
            <div className="space-y-2">
              <label className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block">
                Department
              </label>
              <select
                value={department}
                onChange={(e) => {
                  setDepartment(e.target.value);
                  setPage(1);
                }}
                className="w-full px-3 py-1.5 bg-slate-950 border border-slate-800 rounded-xl text-xs text-slate-300 focus:outline-none focus:border-emerald-500"
              >
                <option value="all">All Departments</option>
                {metadata?.departments.map((dept) => (
                  <option key={dept} value={dept}>
                    {dept}
                  </option>
                ))}
              </select>

              <label className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block pt-1">
                Faculty Author
              </label>
              <select
                value={facultyId}
                onChange={(e) => {
                  setFacultyId(e.target.value);
                  setPage(1);
                }}
                className="w-full px-3 py-1.5 bg-slate-950 border border-slate-800 rounded-xl text-xs text-slate-300 focus:outline-none focus:border-emerald-500"
              >
                <option value="all">All Faculty Members</option>
                {metadata?.faculty.map((f) => (
                  <option key={f.id} value={f.id}>
                    {f.name} ({f.email})
                  </option>
                ))}
              </select>
            </div>

            {/* 2. Multi-Select Statuses */}
            <div className="space-y-1.5">
              <label className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block">
                Exam Status
              </label>
              <div className="space-y-1 max-h-32 overflow-y-auto pr-1">
                {(metadata?.allowed_statuses || ['generating', 'draft', 'published', 'closed', 'failed']).map((st) => {
                  const checked = selectedStatuses.includes(st);
                  const count = metadata?.status_counts?.[st] ?? 0;
                  return (
                    <label key={st} className="flex items-center justify-between text-xs text-slate-300 cursor-pointer select-none py-0.5">
                      <div className="flex items-center gap-2">
                        <input
                          type="checkbox"
                          checked={checked}
                          onChange={() => toggleStatus(st)}
                          className="rounded border-slate-700 bg-slate-950 text-emerald-500 focus:ring-0"
                        />
                        <span className="capitalize">{st}</span>
                      </div>
                      <span className="text-[10px] font-mono text-slate-500">({count})</span>
                    </label>
                  );
                })}
              </div>
            </div>

            {/* 3. Question Types & AI Model */}
            <div className="space-y-2">
              <label className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block">
                Question Types Present
              </label>
              <div className="grid grid-cols-2 gap-1 text-[11px] text-slate-300">
                {[
                  { id: 'mcq', label: 'MCQ' },
                  { id: 'true_false', label: 'True/False' },
                  { id: 'fill_blanks', label: 'Fill Blanks' },
                  { id: 'short', label: 'Short' },
                  { id: 'long', label: 'Long' },
                ].map((q) => (
                  <label key={q.id} className="flex items-center gap-1.5 cursor-pointer select-none">
                    <input
                      type="checkbox"
                      checked={selectedQTypes.includes(q.id)}
                      onChange={() => toggleQType(q.id)}
                      className="rounded border-slate-700 bg-slate-950 text-emerald-500 focus:ring-0"
                    />
                    <span>{q.label}</span>
                  </label>
                ))}
              </div>

              <label className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block pt-1">
                AI Model Used
              </label>
              <select
                value={aiModel}
                onChange={(e) => {
                  setAiModel(e.target.value);
                  setPage(1);
                }}
                className="w-full px-3 py-1.5 bg-slate-950 border border-slate-800 rounded-xl text-xs text-slate-300 focus:outline-none focus:border-emerald-500"
              >
                <option value="all">All Models</option>
                {metadata?.ai_models.map((m) => (
                  <option key={m} value={m}>
                    {m}
                  </option>
                ))}
              </select>
            </div>

            {/* 4. Schedule & Attempts Toggles */}
            <div className="space-y-2 text-xs text-slate-300">
              <label className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block">
                Supervision Criteria
              </label>

              <label className="flex items-center gap-2 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={closingSoon}
                  onChange={(e) => {
                    setClosingSoon(e.target.checked);
                    setPage(1);
                  }}
                  className="rounded border-slate-700 bg-slate-950 text-amber-500 focus:ring-0"
                />
                <span className="text-amber-300">Closing in Next 24 Hours</span>
              </label>

              <label className="flex items-center gap-2 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={missingSchedule}
                  onChange={(e) => {
                    setMissingSchedule(e.target.checked);
                    setPage(1);
                  }}
                  className="rounded border-slate-700 bg-slate-950 text-emerald-500 focus:ring-0"
                />
                <span>Missing Schedule (Drafts)</span>
              </label>

              <label className="flex items-center gap-2 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={hasPendingGrading}
                  onChange={(e) => {
                    setHasPendingGrading(e.target.checked);
                    setPage(1);
                  }}
                  className="rounded border-slate-700 bg-slate-950 text-sky-500 focus:ring-0"
                />
                <span>Pending Grading Attempts</span>
              </label>

              <label className="flex items-center gap-2 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={hasFlaggedStudents}
                  onChange={(e) => {
                    setHasFlaggedStudents(e.target.checked);
                    setPage(1);
                  }}
                  className="rounded border-slate-700 bg-slate-950 text-rose-500 focus:ring-0"
                />
                <span className="text-rose-300">Proctoring Flags Detected</span>
              </label>
            </div>
          </div>
        )}

        {/* Filter Chips & Count Banner */}
        <div className="flex flex-wrap items-center justify-between gap-2 pt-2 border-t border-slate-800/60 text-xs">
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="text-slate-400 font-medium">
              Showing <strong className="text-white">{startIndex}</strong> to{' '}
              <strong className="text-white">{endIndex}</strong> of{' '}
              <strong className="text-white">{totalCount}</strong> exams
            </span>

            {/* Active Chips */}
            {debouncedSearch && (
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-slate-800 text-slate-300 text-[11px]">
                Search: "{debouncedSearch}"
                <button type="button" onClick={() => setSearch('')} className="hover:text-white">
                  <X className="w-3 h-3" />
                </button>
              </span>
            )}

            {institutionId !== 'all' && (
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-slate-800 text-slate-300 text-[11px]">
                Inst: {metadata?.institutions.find((i) => String(i.id) === institutionId)?.institution_name || institutionId}
                <button type="button" onClick={() => setInstitutionId('all')} className="hover:text-white">
                  <X className="w-3 h-3" />
                </button>
              </span>
            )}

            {department !== 'all' && (
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-slate-800 text-slate-300 text-[11px]">
                Dept: {department}
                <button type="button" onClick={() => setDepartment('all')} className="hover:text-white">
                  <X className="w-3 h-3" />
                </button>
              </span>
            )}

            {selectedStatuses.map((st) => (
              <span key={st} className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-300 border border-emerald-500/30 text-[11px]">
                Status: {st}
                <button type="button" onClick={() => toggleStatus(st)} className="hover:text-white">
                  <X className="w-3 h-3" />
                </button>
              </span>
            ))}

            {selectedPhase !== 'all' && (
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-sky-500/10 text-sky-300 border border-sky-500/30 text-[11px]">
                Phase: {selectedPhase}
                <button type="button" onClick={() => setSelectedPhase('all')} className="hover:text-white">
                  <X className="w-3 h-3" />
                </button>
              </span>
            )}

            {closingSoon && (
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-300 border border-amber-500/30 text-[11px]">
                Closing &lt; 24h
                <button type="button" onClick={() => setClosingSoon(false)} className="hover:text-white">
                  <X className="w-3 h-3" />
                </button>
              </span>
            )}
          </div>

          {activeFilterCount > 0 && (
            <button
              type="button"
              onClick={handleClearAll}
              className="text-xs text-rose-400 hover:text-rose-300 flex items-center gap-1 font-semibold cursor-pointer"
            >
              <RotateCcw className="w-3 h-3" />
              <span>Clear all</span>
            </button>
          )}
        </div>
      </div>

      {/* Exams Table (Fixed Layout, Zero Horizontal Overflow) */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden shadow-xl">
        <div className="hidden md:block w-full overflow-hidden">
          <table className="w-full table-fixed text-left text-xs divide-y divide-slate-800">
            <thead className="bg-slate-950/80 text-slate-400 uppercase text-[10px] tracking-wider">
              <tr>
                <th className="py-3 px-4 w-[28%]">Exam / Subject</th>
                <th className="py-3 px-3 w-[20%]">Institution &amp; Dept</th>
                <th className="py-3 px-3 w-[16%]">Faculty &amp; Model</th>
                <th className="py-3 px-3 w-[14%]">Schedule &amp; Phase</th>
                <th className="py-3 px-3 w-[12%] text-center">Marks / Attempts</th>
                <th className="py-3 px-3 w-[10%] text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/50 bg-slate-900/30">
              {loading ? (
                <tr>
                  <td colSpan={6} className="py-12 text-center text-slate-400 text-xs">
                    <RefreshCw className="w-5 h-5 mx-auto animate-spin text-emerald-400 mb-2" />
                    <span>Loading examinations...</span>
                  </td>
                </tr>
              ) : exams.length === 0 ? (
                <tr>
                  <td colSpan={6} className="py-12 text-center text-slate-400 text-xs space-y-2">
                    <FileText className="w-6 h-6 mx-auto text-slate-600 mb-1" />
                    <p className="font-semibold text-slate-300">No examinations match the selected criteria.</p>
                    <p className="text-[11px] text-slate-500">Try loosening your search query or reset filter chips.</p>
                    <button
                      type="button"
                      onClick={handleClearAll}
                      className="px-3 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs mt-2"
                    >
                      Reset All Filters
                    </button>
                  </td>
                </tr>
              ) : (
                exams.map((exam) => (
                  <tr key={exam.id} className="hover:bg-slate-800/40 transition-colors">
                    {/* 1. Exam Title / Subject */}
                    <td className="py-3 px-4 truncate">
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-white text-xs truncate" title={exam.title}>
                          {exam.title}
                        </span>
                        {exam.closing_soon && (
                          <span className="px-1.5 py-0.5 rounded text-[9px] font-bold bg-amber-500/20 text-amber-300 border border-amber-500/30 uppercase shrink-0">
                            Closing
                          </span>
                        )}
                      </div>
                      <div className="flex items-center gap-1.5 text-[11px] text-slate-400 mt-0.5 truncate">
                        <span className="text-slate-300 font-medium">{exam.subject}</span>
                        <span>&bull;</span>
                        <span className="font-mono text-slate-500">ID #{exam.id}</span>
                      </div>
                    </td>

                    {/* 2. Institution & Department */}
                    <td className="py-3 px-3 truncate">
                      <div className="font-medium text-slate-200 truncate" title={exam.institution.name}>
                        {exam.institution.name}
                      </div>
                      <div className="text-[11px] text-slate-400 truncate mt-0.5">
                        {exam.department}
                      </div>
                    </td>

                    {/* 3. Faculty & AI Model */}
                    <td className="py-3 px-3 truncate">
                      <div className="font-medium text-slate-200 truncate" title={exam.faculty.full_name}>
                        {exam.faculty.full_name}
                      </div>
                      <div className="text-[11px] font-mono text-emerald-400/90 truncate mt-0.5">
                        {exam.ai_model_used}
                      </div>
                    </td>

                    {/* 4. Schedule & Phase */}
                    <td className="py-3 px-3 truncate">
                      <div className="flex items-center gap-1.5">
                        <span
                          className={`inline-flex items-center px-2 py-0.5 rounded-full text-[9px] font-bold uppercase tracking-wider ${
                            exam.schedule_phase === 'live'
                              ? 'bg-emerald-500/20 text-emerald-300 animate-pulse'
                              : exam.schedule_phase === 'upcoming'
                              ? 'bg-sky-500/20 text-sky-300'
                              : 'bg-slate-800 text-slate-400'
                          }`}
                        >
                          {exam.schedule_phase}
                        </span>
                        <span className="text-[10px] text-slate-400 font-mono">
                          {exam.duration_minutes}m
                        </span>
                      </div>
                      <div className="text-[10px] text-slate-400 mt-1 truncate">
                        {exam.starts_at ? new Date(exam.starts_at).toLocaleDateString() : 'No schedule'}
                      </div>
                    </td>

                    {/* 5. Marks & Attempts */}
                    <td className="py-3 px-3 text-center truncate">
                      <div className="font-mono text-xs font-bold text-white">
                        {exam.total_marks} / {exam.target_total_marks ?? '-'}
                      </div>
                      <div className="flex items-center justify-center gap-1.5 text-[10px] text-slate-400 mt-0.5">
                        <span>{exam.attempts_count} attempts</span>
                        {exam.flagged_students_count > 0 && (
                          <span className="text-rose-400 font-bold">({exam.flagged_students_count} flagged)</span>
                        )}
                      </div>
                    </td>

                    {/* 6. Actions */}
                    <td className="py-3 px-3 text-right">
                      {exam.status === 'published' ? (
                        <button
                          type="button"
                          onClick={() => handleForceClose(exam)}
                          className="px-2.5 py-1 rounded-lg bg-rose-500/10 hover:bg-rose-500/20 text-rose-300 border border-rose-500/30 text-xs font-semibold cursor-pointer transition-all"
                        >
                          Force Close
                        </button>
                      ) : (
                        <span className="text-[10px] font-mono text-slate-500 uppercase">
                          {exam.status}
                        </span>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Mobile View: Stacked Cards */}
        <div className="md:hidden p-3 space-y-3">
          {loading ? (
            <div className="p-8 text-center text-slate-400 text-xs">
              <RefreshCw className="w-5 h-5 mx-auto animate-spin text-emerald-400 mb-2" />
              <span>Loading examinations...</span>
            </div>
          ) : exams.length === 0 ? (
            <div className="p-6 text-center text-slate-400 text-xs">
              No matching examinations found.
            </div>
          ) : (
            exams.map((exam) => (
              <div key={exam.id} className="p-3.5 rounded-xl bg-slate-950 border border-slate-800 space-y-2 text-xs">
                <div className="flex justify-between items-start gap-2">
                  <div>
                    <h3 className="font-bold text-white text-xs">{exam.title}</h3>
                    <p className="text-[11px] text-slate-400">{exam.subject} &bull; {exam.department}</p>
                  </div>
                  <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase bg-slate-800 text-slate-300 shrink-0">
                    {exam.schedule_phase}
                  </span>
                </div>

                <div className="flex justify-between items-center text-[11px] text-slate-400 pt-1 border-t border-slate-800/60">
                  <span>{exam.institution.name}</span>
                  <span className="font-mono text-white font-semibold">{exam.total_marks} marks</span>
                </div>

                <div className="flex justify-between items-center text-[11px] text-slate-400">
                  <span>Author: {exam.faculty.full_name}</span>
                  <span>{exam.attempts_count} attempts</span>
                </div>

                {exam.status === 'published' && (
                  <button
                    type="button"
                    onClick={() => handleForceClose(exam)}
                    className="w-full mt-2 py-1.5 rounded-lg bg-rose-500/20 text-rose-300 text-xs font-semibold cursor-pointer"
                  >
                    Emergency Force-Close
                  </button>
                )}
              </div>
            ))
          )}
        </div>

        {/* Pagination Bar */}
        <div className="p-4 border-t border-slate-800/80 flex flex-col sm:flex-row items-center justify-between gap-3 text-xs text-slate-400 bg-slate-950/60">
          <div className="flex items-center gap-2">
            <span>Rows per page:</span>
            <select
              value={pageSize}
              onChange={(e) => {
                setPageSize(Number(e.target.value));
                setPage(1);
              }}
              className="px-2 py-1 bg-slate-900 border border-slate-800 rounded-lg text-slate-200"
            >
              <option value="10">10</option>
              <option value="25">25</option>
              <option value="50">50</option>
              <option value="100">100</option>
            </select>
          </div>

          <div className="flex items-center gap-3">
            <span>
              Page <strong className="text-white">{page}</strong> of <strong className="text-white">{totalPages}</strong>
            </span>
            <div className="flex items-center gap-1.5">
              <button
                type="button"
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page <= 1}
                className="p-1.5 rounded-lg bg-slate-900 border border-slate-800 text-slate-300 hover:text-white disabled:opacity-40 cursor-pointer"
              >
                <ChevronLeft className="w-4 h-4" />
              </button>
              <button
                type="button"
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page >= totalPages}
                className="p-1.5 rounded-lg bg-slate-900 border border-slate-800 text-slate-300 hover:text-white disabled:opacity-40 cursor-pointer"
              >
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

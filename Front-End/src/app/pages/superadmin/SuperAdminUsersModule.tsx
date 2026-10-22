import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  Users,
  GraduationCap,
  BookOpen,
  Building2,
  Search,
  Filter,
  Plus,
  RefreshCw,
  MoreVertical,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  KeyRound,
  LogOut,
  Eye,
  Edit2,
  Trash2,
  ChevronRight,
  ChevronLeft,
  X,
  Calendar,
  Clock,
  ArrowRightLeft,
  Copy,
  Check,
  CheckSquare,
  Square,
  ShieldAlert,
  ShieldCheck,
  ChevronDown,
  ExternalLink,
  Award,
} from 'lucide-react';

interface SuperAdminUsersModuleProps {
  saFetch: (endpoint: string, options?: RequestInit) => Promise<Response>;
  onTriggerReauth: (callback?: () => void) => void;
}

type UserRoleTab = 'student' | 'faculty' | 'admin';

export function SuperAdminUsersModule({ saFetch, onTriggerReauth }: SuperAdminUsersModuleProps) {
  // Current active sub-tab
  const [activeRole, setActiveRole] = useState<UserRoleTab>('student');

  // Query and Filter state
  const [search, setSearch] = useState('');
  const [instId, setInstId] = useState('');
  const [department, setDepartment] = useState('all');
  const [statusFilter, setStatusFilter] = useState('all');
  const [batchYear, setBatchYear] = useState('');
  const [examActivity, setExamActivity] = useState('all');
  const [flaggedViolations, setFlaggedViolations] = useState('all');
  const [designation, setDesignation] = useState('all');
  const [hasPublishedExams, setHasPublishedExams] = useState('all');
  const [hasLiveExams, setHasLiveExams] = useState('all');
  const [neverLoggedIn, setNeverLoggedIn] = useState(false);
  const [sortBy, setSortBy] = useState('joined');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');
  const [showAdvancedFilters, setShowAdvancedFilters] = useState(false);

  // Pagination state
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [totalPages, setTotalPages] = useState(1);
  const [totalCount, setTotalCount] = useState(0);
  const [tabCounts, setTabCounts] = useState<{ students: number; faculty: number; admins: number; total: number }>({
    students: 0,
    faculty: 0,
    admins: 0,
    total: 0,
  });

  // Data state
  const [users, setUsers] = useState<any[]>([]);
  const [institutes, setInstitutes] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  // Bulk selection state
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [selectAllAcrossPages, setSelectAllAcrossPages] = useState(false);

  // Modals & Drawer state
  const [drawerUserId, setDrawerUserId] = useState<number | null>(null);
  const [createUserOpen, setCreateUserOpen] = useState(false);
  const [editProfileUser, setEditProfileUser] = useState<any | null>(null);
  const [transferUser, setTransferUser] = useState<any | null>(null);
  const [toggleActiveUser, setToggleActiveUser] = useState<any | null>(null);
  const [resetPwdResult, setResetPwdResult] = useState<{ user: any; tempPass: string } | null>(null);
  const [bulkActionModal, setBulkActionModal] = useState<{ action: string; title: string } | null>(null);

  // Dropdown portal / menu tracking
  const [activeActionMenuId, setActiveActionMenuId] = useState<number | null>(null);

  // Fetch institutions list for filters
  useEffect(() => {
    saFetch('institutes/').then(async (res) => {
      if (res.ok) {
        const body = await res.json();
        setInstitutes(body.data || []);
      }
    }).catch(() => {});
  }, [saFetch]);

  // Main fetch users call
  const fetchUsers = useCallback(async () => {
    try {
      setLoading(true);
      const params = new URLSearchParams({
        role: activeRole,
        page: String(page),
        page_size: String(pageSize),
        sort_by: sortBy,
        sort_order: sortOrder,
      });

      if (search.trim()) params.set('search', search.trim());
      if (instId) params.set('institution_id', instId);
      if (department && department !== 'all') params.set('department', department);
      if (statusFilter !== 'all') params.set('status', statusFilter);
      if (neverLoggedIn) params.set('never_logged_in', 'true');

      if (activeRole === 'student') {
        if (batchYear.trim()) params.set('batch_year', batchYear.trim());
        if (examActivity !== 'all') params.set('exam_activity', examActivity);
        if (flaggedViolations !== 'all') params.set('flagged_violations', flaggedViolations);
      } else if (activeRole === 'faculty') {
        if (designation !== 'all') params.set('designation', designation);
        if (hasPublishedExams !== 'all') params.set('has_published_exams', hasPublishedExams);
        if (hasLiveExams !== 'all') params.set('has_live_exams', hasLiveExams);
      }

      const res = await saFetch(`users/?${params.toString()}`);
      if (res.ok) {
        const body = await res.json();
        setUsers(body.data || []);
        if (body.counts) {
          setTabCounts(body.counts);
        }
        if (body.pagination) {
          setTotalPages(body.pagination.total_pages || 1);
          setTotalCount(body.pagination.total_count || 0);
        }
      }
    } catch (err) {
      console.error('Error fetching users:', err);
    } finally {
      setLoading(false);
    }
  }, [
    activeRole,
    page,
    pageSize,
    search,
    instId,
    department,
    statusFilter,
    batchYear,
    examActivity,
    flaggedViolations,
    designation,
    hasPublishedExams,
    hasLiveExams,
    neverLoggedIn,
    sortBy,
    sortOrder,
    saFetch,
  ]);

  useEffect(() => {
    fetchUsers();
    setSelectedIds([]);
    setSelectAllAcrossPages(false);
  }, [fetchUsers]);

  // Clear all filters
  const handleClearFilters = () => {
    setSearch('');
    setInstId('');
    setDepartment('all');
    setStatusFilter('all');
    setBatchYear('');
    setExamActivity('all');
    setFlaggedViolations('all');
    setDesignation('all');
    setHasPublishedExams('all');
    setHasLiveExams('all');
    setNeverLoggedIn(false);
    setSortBy('joined');
    setSortOrder('desc');
    setPage(1);
  };

  // Active filter chips calculation
  const activeChips = useMemo(() => {
    const chips: { label: string; onRemove: () => void }[] = [];
    if (search.trim()) chips.push({ label: `Search: "${search}"`, onRemove: () => setSearch('') });
    if (instId) {
      const inst = institutes.find((i) => String(i.id) === String(instId));
      chips.push({ label: `Inst: ${inst?.name || instId}`, onRemove: () => setInstId('') });
    }
    if (department && department !== 'all') {
      chips.push({ label: `Dept: ${department}`, onRemove: () => setDepartment('all') });
    }
    if (statusFilter !== 'all') {
      chips.push({ label: `Status: ${statusFilter}`, onRemove: () => setStatusFilter('all') });
    }
    if (neverLoggedIn) {
      chips.push({ label: 'Never Logged In', onRemove: () => setNeverLoggedIn(false) });
    }
    if (activeRole === 'student') {
      if (batchYear.trim()) chips.push({ label: `Batch: ${batchYear}`, onRemove: () => setBatchYear('') });
      if (examActivity !== 'all') chips.push({ label: `Activity: ${examActivity}`, onRemove: () => setExamActivity('all') });
      if (flaggedViolations !== 'all') chips.push({ label: flaggedViolations === 'true' ? 'Violations Flagged' : 'No Violations', onRemove: () => setFlaggedViolations('all') });
    } else if (activeRole === 'faculty') {
      if (designation !== 'all') chips.push({ label: `Desig: ${designation}`, onRemove: () => setDesignation('all') });
      if (hasPublishedExams !== 'all') chips.push({ label: 'Has Published Exams', onRemove: () => setHasPublishedExams('all') });
      if (hasLiveExams !== 'all') chips.push({ label: 'Has Live Exams', onRemove: () => setHasLiveExams('all') });
    }
    return chips;
  }, [search, instId, institutes, department, statusFilter, neverLoggedIn, activeRole, batchYear, examActivity, flaggedViolations, designation, hasPublishedExams, hasLiveExams]);

  // Row selection handlers
  const handleToggleRow = (id: number) => {
    setSelectedIds((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));
  };

  const handleSelectAllOnPage = () => {
    const pageIds = users.map((u) => u.id);
    const allChecked = pageIds.every((id) => selectedIds.includes(id));
    if (allChecked) {
      setSelectedIds((prev) => prev.filter((id) => !pageIds.includes(id)));
      setSelectAllAcrossPages(false);
    } else {
      setSelectedIds((prev) => Array.from(new Set([...prev, ...pageIds])));
    }
  };

  const allPageRowsSelected = users.length > 0 && users.every((u) => selectedIds.includes(u.id));

  // Single User Actions
  const handleResetPassword = (user: any) => {
    onTriggerReauth(async () => {
      try {
        const res = await saFetch(`users/${user.id}/reset-password/`, {
          method: 'POST',
          body: JSON.stringify({ reason: 'Super Admin Administrative Reset' }),
        });
        const data = await res.json();
        if (res.ok) {
          setResetPwdResult({ user, tempPass: data.temporary_password });
        }
      } catch (err) {
        console.error(err);
      }
    });
  };

  const handleRevokeSessions = (user: any) => {
    if (!window.confirm(`Revoke all active sessions and tokens for "${user.full_name}"?`)) return;
    onTriggerReauth(async () => {
      try {
        const res = await saFetch(`users/${user.id}/revoke-sessions/`, { method: 'POST' });
        if (res.ok) {
          alert(`Sessions for ${user.username} revoked successfully.`);
          fetchUsers();
        }
      } catch (err) {
        console.error(err);
      }
    });
  };

  return (
    <div className="space-y-6 min-w-0 max-w-full font-sans">
      {/* Header with Title and Create Button */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800 pb-5">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl sm:text-2xl font-bold text-white tracking-tight">User Management</h1>
            <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
              {tabCounts.total} Total
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Role-separated directory of Students, Faculty, and Institute Administrators
          </p>
        </div>
        <div className="flex items-center gap-2.5">
          <button
            type="button"
            onClick={fetchUsers}
            className="p-2.5 rounded-xl bg-slate-900 hover:bg-slate-800 border border-slate-800 text-slate-300 hover:text-white cursor-pointer transition-colors"
            title="Refresh Directory"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin text-emerald-400' : ''}`} />
          </button>
          <button
            type="button"
            onClick={() => setCreateUserOpen(true)}
            className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold shadow-lg shadow-emerald-950/40 cursor-pointer transition-all"
          >
            <Plus className="w-4 h-4" />
            <span>Create User</span>
          </button>
        </div>
      </div>

      {/* Role Tabs Bar */}
      <div className="flex items-center gap-2 p-1.5 bg-slate-900 border border-slate-800 rounded-2xl w-fit">
        <RoleTabButton
          active={activeRole === 'student'}
          onClick={() => {
            setActiveRole('student');
            setPage(1);
          }}
          icon={<GraduationCap className="w-4 h-4" />}
          label="Students"
          count={tabCounts.students}
        />
        <RoleTabButton
          active={activeRole === 'faculty'}
          onClick={() => {
            setActiveRole('faculty');
            setPage(1);
          }}
          icon={<BookOpen className="w-4 h-4" />}
          label="Faculty"
          count={tabCounts.faculty}
        />
        <RoleTabButton
          active={activeRole === 'admin'}
          onClick={() => {
            setActiveRole('admin');
            setPage(1);
          }}
          icon={<Building2 className="w-4 h-4" />}
          label="Institute Admins"
          count={tabCounts.admins}
        />
      </div>

      {/* Filters Card */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-4 space-y-3 shadow-xs">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          {/* Keyword Search */}
          <div className="relative">
            <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
            <input
              type="text"
              placeholder={`Search ${activeRole}s by name, email, ID...`}
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setPage(1);
              }}
              className="w-full pl-9 pr-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-emerald-500/40"
            />
          </div>

          {/* Institution Selector */}
          <select
            value={instId}
            onChange={(e) => {
              setInstId(e.target.value);
              setPage(1);
            }}
            className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-xs text-slate-300 focus:outline-none focus:ring-2 focus:ring-emerald-500/40 cursor-pointer"
          >
            <option value="">All Institutions</option>
            {institutes.map((inst) => (
              <option key={inst.id} value={inst.id}>
                {inst.name} ({inst.code})
              </option>
            ))}
          </select>

          {/* Status Selector */}
          <select
            value={statusFilter}
            onChange={(e) => {
              setStatusFilter(e.target.value);
              setPage(1);
            }}
            className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-xs text-slate-300 focus:outline-none focus:ring-2 focus:ring-emerald-500/40 cursor-pointer"
          >
            <option value="all">Status: All</option>
            <option value="active">Active Only</option>
            <option value="inactive">Inactive Only</option>
          </select>

          {/* More Filters Toggle */}
          <button
            type="button"
            onClick={() => setShowAdvancedFilters(!showAdvancedFilters)}
            className={`flex items-center justify-between px-3.5 py-2 rounded-xl border text-xs font-semibold cursor-pointer transition-colors ${
              showAdvancedFilters || activeChips.length > 3
                ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400'
                : 'bg-slate-950 border-slate-800 text-slate-300 hover:text-white'
            }`}
          >
            <span className="flex items-center gap-1.5">
              <Filter className="w-3.5 h-3.5" />
              <span>More Filters</span>
            </span>
            <ChevronDown className={`w-3.5 h-3.5 transition-transform ${showAdvancedFilters ? 'rotate-180' : ''}`} />
          </button>
        </div>

        {/* Collapsible Advanced Filters */}
        {showAdvancedFilters && (
          <div className="pt-3 border-t border-slate-800/80 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 text-xs">
            {activeRole === 'student' && (
              <>
                <div>
                  <label className="block text-[11px] text-slate-400 mb-1">Batch / Year</label>
                  <input
                    type="text"
                    placeholder="e.g. 2026"
                    value={batchYear}
                    onChange={(e) => {
                      setBatchYear(e.target.value);
                      setPage(1);
                    }}
                    className="w-full px-3 py-1.5 bg-slate-950 border border-slate-800 rounded-xl text-xs text-white"
                  />
                </div>
                <div>
                  <label className="block text-[11px] text-slate-400 mb-1">Exam Participation</label>
                  <select
                    value={examActivity}
                    onChange={(e) => {
                      setExamActivity(e.target.value);
                      setPage(1);
                    }}
                    className="w-full px-3 py-1.5 bg-slate-950 border border-slate-800 rounded-xl text-xs text-slate-300"
                  >
                    <option value="all">All</option>
                    <option value="attempted">Attempted Exams</option>
                    <option value="never_attempted">Never Attempted</option>
                  </select>
                </div>
                <div>
                  <label className="block text-[11px] text-slate-400 mb-1">Proctoring Violations</label>
                  <select
                    value={flaggedViolations}
                    onChange={(e) => {
                      setFlaggedViolations(e.target.value);
                      setPage(1);
                    }}
                    className="w-full px-3 py-1.5 bg-slate-950 border border-slate-800 rounded-xl text-xs text-slate-300"
                  >
                    <option value="all">All</option>
                    <option value="true">Violations Flagged</option>
                    <option value="false">Clean (0 Violations)</option>
                  </select>
                </div>
              </>
            )}

            {activeRole === 'faculty' && (
              <>
                <div>
                  <label className="block text-[11px] text-slate-400 mb-1">Designation</label>
                  <input
                    type="text"
                    placeholder="e.g. Professor"
                    value={designation === 'all' ? '' : designation}
                    onChange={(e) => {
                      setDesignation(e.target.value || 'all');
                      setPage(1);
                    }}
                    className="w-full px-3 py-1.5 bg-slate-950 border border-slate-800 rounded-xl text-xs text-white"
                  />
                </div>
                <div>
                  <label className="block text-[11px] text-slate-400 mb-1">Published Exams</label>
                  <select
                    value={hasPublishedExams}
                    onChange={(e) => {
                      setHasPublishedExams(e.target.value);
                      setPage(1);
                    }}
                    className="w-full px-3 py-1.5 bg-slate-950 border border-slate-800 rounded-xl text-xs text-slate-300"
                  >
                    <option value="all">All</option>
                    <option value="true">Has Published</option>
                    <option value="false">None Published</option>
                  </select>
                </div>
                <div>
                  <label className="block text-[11px] text-slate-400 mb-1">Live Exams Now</label>
                  <select
                    value={hasLiveExams}
                    onChange={(e) => {
                      setHasLiveExams(e.target.value);
                      setPage(1);
                    }}
                    className="w-full px-3 py-1.5 bg-slate-950 border border-slate-800 rounded-xl text-xs text-slate-300"
                  >
                    <option value="all">All</option>
                    <option value="true">Currently Live</option>
                    <option value="false">No Live Exams</option>
                  </select>
                </div>
              </>
            )}

            {/* Sorting controls */}
            <div>
              <label className="block text-[11px] text-slate-400 mb-1">Sort Field</label>
              <select
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value)}
                className="w-full px-3 py-1.5 bg-slate-950 border border-slate-800 rounded-xl text-xs text-slate-300"
              >
                <option value="joined">Date Joined</option>
                <option value="name">Full Name</option>
                <option value="last_login">Last Login</option>
                <option value="identifier">ID Code</option>
              </select>
            </div>
            <div>
              <label className="block text-[11px] text-slate-400 mb-1">Sort Direction</label>
              <select
                value={sortOrder}
                onChange={(e) => setSortOrder(e.target.value as 'asc' | 'desc')}
                className="w-full px-3 py-1.5 bg-slate-950 border border-slate-800 rounded-xl text-xs text-slate-300"
              >
                <option value="desc">Descending (Newest / Z-A)</option>
                <option value="asc">Ascending (Oldest / A-Z)</option>
              </select>
            </div>
          </div>
        )}

        {/* Removable Filter Chips Bar */}
        {activeChips.length > 0 && (
          <div className="flex flex-wrap items-center gap-2 pt-2 border-t border-slate-800/60">
            <span className="text-[11px] font-semibold text-slate-400">Active Filters:</span>
            {activeChips.map((chip, idx) => (
              <span
                key={idx}
                className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-slate-800 text-[11px] text-slate-200 border border-slate-700 font-medium"
              >
                <span>{chip.label}</span>
                <button
                  type="button"
                  onClick={chip.onRemove}
                  className="text-slate-400 hover:text-white cursor-pointer"
                >
                  <X className="w-3 h-3" />
                </button>
              </span>
            ))}
            <button
              type="button"
              onClick={handleClearFilters}
              className="text-[11px] text-rose-400 hover:text-rose-300 font-semibold cursor-pointer underline ml-1"
            >
              Clear filters
            </button>
          </div>
        )}
      </div>

      {/* Floating / Sticky Bulk Action Bar */}
      {selectedIds.length > 0 && (
        <div className="p-3 bg-emerald-950/70 border border-emerald-500/40 rounded-2xl flex flex-wrap items-center justify-between gap-3 shadow-lg">
          <div className="flex items-center gap-2 text-xs">
            <span className="px-2 py-0.5 rounded-full bg-emerald-500 text-slate-950 font-bold text-[11px]">
              {selectAllAcrossPages ? totalCount : selectedIds.length}
            </span>
            <span className="font-semibold text-emerald-200">
              {selectAllAcrossPages ? `All ${totalCount} users selected` : `${selectedIds.length} user(s) selected`}
            </span>
            {!selectAllAcrossPages && selectedIds.length === users.length && totalCount > users.length && (
              <button
                type="button"
                onClick={() => setSelectAllAcrossPages(true)}
                className="text-emerald-400 hover:text-emerald-300 underline font-semibold ml-2 cursor-pointer"
              >
                Select all {totalCount} across all pages
              </button>
            )}
          </div>
          <div className="flex items-center gap-2 text-xs">
            <button
              type="button"
              onClick={() => setBulkActionModal({ action: 'activate', title: 'Bulk Activate Users' })}
              className="px-3 py-1.5 rounded-xl bg-slate-900 hover:bg-slate-800 text-emerald-400 border border-emerald-500/30 font-semibold cursor-pointer"
            >
              Activate
            </button>
            <button
              type="button"
              onClick={() => setBulkActionModal({ action: 'deactivate', title: 'Bulk Deactivate Users' })}
              className="px-3 py-1.5 rounded-xl bg-slate-900 hover:bg-slate-800 text-rose-400 border border-rose-500/30 font-semibold cursor-pointer"
            >
              Deactivate
            </button>
            <button
              type="button"
              onClick={() => setBulkActionModal({ action: 'move_department', title: 'Bulk Move Department' })}
              className="px-3 py-1.5 rounded-xl bg-slate-900 hover:bg-slate-800 text-sky-400 border border-sky-500/30 font-semibold cursor-pointer"
            >
              Move Dept
            </button>
            <button
              type="button"
              onClick={() => {
                setSelectedIds([]);
                setSelectAllAcrossPages(false);
              }}
              className="px-2.5 py-1.5 rounded-xl text-slate-400 hover:text-slate-200 text-xs cursor-pointer"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Users Table (Desktop) & Cards (Mobile) */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden shadow-xs">
        {loading ? (
          <div className="flex flex-col items-center justify-center p-16 text-slate-400 space-y-3">
            <RefreshCw className="w-6 h-6 animate-spin text-emerald-400" />
            <p className="text-xs font-mono">Loading {activeRole} directory...</p>
          </div>
        ) : users.length === 0 ? (
          <div className="flex flex-col items-center justify-center p-16 text-slate-400 space-y-2 text-center">
            <Users className="w-10 h-10 text-slate-600 mb-1" />
            <p className="text-sm font-semibold text-slate-300">No {activeRole} records found</p>
            <p className="text-xs text-slate-500 max-w-sm">
              Try adjusting your search criteria, clearing filters, or create a new user account.
            </p>
          </div>
        ) : (
          <>
            {/* Desktop Fixed Table */}
            <div className="hidden md:block overflow-hidden">
              <table className="w-full text-left text-xs text-slate-300 table-fixed">
                <thead className="bg-slate-950/80 text-slate-400 uppercase tracking-wider text-[11px] border-b border-slate-800">
                  <tr>
                    <th className="w-[4%] py-3.5 px-3 text-center">
                      <button
                        type="button"
                        onClick={handleSelectAllOnPage}
                        className="text-slate-400 hover:text-emerald-400 cursor-pointer"
                      >
                        {allPageRowsSelected ? (
                          <CheckSquare className="w-4 h-4 text-emerald-400" />
                        ) : (
                          <Square className="w-4 h-4" />
                        )}
                      </button>
                    </th>
                    <th className="w-[24%] py-3.5 px-3">Name & Email</th>
                    <th className="w-[14%] py-3.5 px-3">Identifier</th>
                    <th className="w-[18%] py-3.5 px-3">Institution</th>
                    <th className="w-[14%] py-3.5 px-3">
                      {activeRole === 'student' ? 'Dept / Batch' : activeRole === 'faculty' ? 'Dept / Desig' : 'Scope'}
                    </th>
                    <th className="w-[10%] py-3.5 px-3">Status</th>
                    <th className="w-[16%] py-3.5 px-3 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60">
                  {users.map((u) => {
                    const isSelected = selectedIds.includes(u.id);
                    return (
                      <tr
                        key={u.id}
                        className={`transition-colors ${
                          isSelected ? 'bg-emerald-500/5' : 'hover:bg-slate-800/40'
                        }`}
                      >
                        <td className="py-3.5 px-3 text-center">
                          <button
                            type="button"
                            onClick={() => handleToggleRow(u.id)}
                            className="cursor-pointer"
                          >
                            {isSelected ? (
                              <CheckSquare className="w-4 h-4 text-emerald-400" />
                            ) : (
                              <Square className="w-4 h-4 text-slate-500" />
                            )}
                          </button>
                        </td>

                        {/* Name & Email (Truncated with tooltip) */}
                        <td className="py-3.5 px-3 truncate" title={`${u.full_name} (${u.email})`}>
                          <p className="font-bold text-white text-xs truncate">{u.full_name}</p>
                          <p className="text-[11px] font-mono text-slate-400 truncate">{u.email}</p>
                        </td>

                        {/* Identifier Code */}
                        <td className="py-3.5 px-3 truncate">
                          <span className="font-mono text-[11px] px-2 py-0.5 rounded-md bg-slate-950 border border-slate-800 text-slate-300">
                            {u.identifier || 'N/A'}
                          </span>
                        </td>

                        {/* Institution */}
                        <td className="py-3.5 px-3 truncate" title={u.institution?.name || 'Unassigned'}>
                          <p className="truncate text-slate-200">{u.institution?.name || 'Unassigned'}</p>
                          <p className="text-[10px] font-mono text-slate-500">{u.institution?.code || ''}</p>
                        </td>

                        {/* Role Specific Meta */}
                        <td className="py-3.5 px-3 truncate">
                          <p className="truncate text-slate-300 font-medium">{u.department || 'General'}</p>
                          <p className="text-[10px] text-slate-500 truncate">
                            {activeRole === 'student'
                              ? `Batch: ${u.batch_year || 'N/A'}`
                              : activeRole === 'faculty'
                              ? u.designation || 'Faculty'
                              : u.permissions_scope || 'All Depts'}
                          </p>
                        </td>

                        {/* Status Badge */}
                        <td className="py-3.5 px-3">
                          {u.is_active ? (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
                              <CheckCircle2 className="w-3 h-3" /> Active
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-rose-500/15 text-rose-400 border border-rose-500/30">
                              <XCircle className="w-3 h-3" /> Inactive
                            </span>
                          )}
                        </td>

                        {/* Actions (Hybrid: View Button + Labeled More Menu) */}
                        <td className="py-3.5 px-3 text-right">
                          <div className="flex items-center justify-end gap-1.5">
                            <button
                              type="button"
                              onClick={() => setDrawerUserId(u.id)}
                              className="px-2.5 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold flex items-center gap-1 cursor-pointer transition-colors"
                              title="View User Details"
                            >
                              <Eye className="w-3.5 h-3.5 text-emerald-400" />
                              <span>View</span>
                            </button>

                            <div className="relative">
                              <button
                                type="button"
                                onClick={() => setActiveActionMenuId(activeActionMenuId === u.id ? null : u.id)}
                                className="p-1.5 rounded-xl hover:bg-slate-800 text-slate-400 hover:text-white cursor-pointer transition-colors"
                                title="More Actions"
                              >
                                <MoreVertical className="w-4 h-4" />
                              </button>

                              {activeActionMenuId === u.id && (
                                <div
                                  className="absolute right-0 top-full mt-1 w-48 bg-slate-900 border border-slate-800 rounded-xl shadow-2xl py-1 z-50 text-left text-xs divide-y divide-slate-800/80"
                                  onMouseLeave={() => setActiveActionMenuId(null)}
                                >
                                  <div className="py-1">
                                    <button
                                      type="button"
                                      onClick={() => {
                                        setActiveActionMenuId(null);
                                        setEditProfileUser(u);
                                      }}
                                      className="w-full px-3 py-1.5 text-slate-300 hover:bg-slate-800 hover:text-white flex items-center gap-2 cursor-pointer"
                                    >
                                      <Edit2 className="w-3.5 h-3.5 text-sky-400" /> Edit Profile
                                    </button>
                                    <button
                                      type="button"
                                      onClick={() => {
                                        setActiveActionMenuId(null);
                                        setTransferUser(u);
                                      }}
                                      className="w-full px-3 py-1.5 text-slate-300 hover:bg-slate-800 hover:text-white flex items-center gap-2 cursor-pointer"
                                    >
                                      <ArrowRightLeft className="w-3.5 h-3.5 text-amber-400" /> Transfer Dept/Inst
                                    </button>
                                  </div>

                                  <div className="py-1">
                                    <button
                                      type="button"
                                      onClick={() => {
                                        setActiveActionMenuId(null);
                                        setToggleActiveUser(u);
                                      }}
                                      className="w-full px-3 py-1.5 text-slate-300 hover:bg-slate-800 hover:text-white flex items-center gap-2 cursor-pointer"
                                    >
                                      {u.is_active ? (
                                        <>
                                          <XCircle className="w-3.5 h-3.5 text-rose-400" /> Deactivate User
                                        </>
                                      ) : (
                                        <>
                                          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" /> Activate User
                                        </>
                                      )}
                                    </button>
                                    <button
                                      type="button"
                                      onClick={() => {
                                        setActiveActionMenuId(null);
                                        handleResetPassword(u);
                                      }}
                                      className="w-full px-3 py-1.5 text-slate-300 hover:bg-slate-800 hover:text-white flex items-center gap-2 cursor-pointer"
                                    >
                                      <KeyRound className="w-3.5 h-3.5 text-indigo-400" /> Reset Password
                                    </button>
                                    <button
                                      type="button"
                                      onClick={() => {
                                        setActiveActionMenuId(null);
                                        handleRevokeSessions(u);
                                      }}
                                      className="w-full px-3 py-1.5 text-slate-300 hover:bg-slate-800 hover:text-white flex items-center gap-2 cursor-pointer"
                                    >
                                      <LogOut className="w-3.5 h-3.5 text-amber-400" /> Revoke Sessions
                                    </button>
                                  </div>
                                </div>
                              )}
                            </div>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            {/* Mobile Stacked Cards (Visible on small screens) */}
            <div className="block md:hidden divide-y divide-slate-800/80">
              {users.map((u) => (
                <div key={u.id} className="p-4 space-y-3">
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <p className="font-bold text-white text-sm">{u.full_name}</p>
                      <p className="text-xs font-mono text-slate-400">{u.email}</p>
                    </div>
                    {u.is_active ? (
                      <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
                        Active
                      </span>
                    ) : (
                      <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-rose-500/15 text-rose-400 border border-rose-500/30">
                        Inactive
                      </span>
                    )}
                  </div>

                  <div className="grid grid-cols-2 gap-2 p-2.5 bg-slate-950 rounded-xl text-xs font-mono">
                    <div>
                      <span className="text-slate-500 text-[10px] block">ID:</span>
                      <span className="text-slate-300">{u.identifier || 'N/A'}</span>
                    </div>
                    <div>
                      <span className="text-slate-500 text-[10px] block">Department:</span>
                      <span className="text-slate-300 truncate block">{u.department || 'General'}</span>
                    </div>
                  </div>

                  <div className="flex items-center justify-end gap-2 pt-1">
                    <button
                      type="button"
                      onClick={() => setDrawerUserId(u.id)}
                      className="px-3 py-1.5 rounded-xl bg-slate-800 text-slate-200 text-xs font-semibold flex items-center gap-1"
                    >
                      <Eye className="w-3.5 h-3.5 text-emerald-400" /> View
                    </button>
                    <button
                      type="button"
                      onClick={() => handleResetPassword(u)}
                      className="px-3 py-1.5 rounded-xl bg-slate-800 text-slate-300 text-xs font-semibold flex items-center gap-1"
                    >
                      <KeyRound className="w-3.5 h-3.5 text-indigo-400" /> Reset
                    </button>
                  </div>
                </div>
              ))}
            </div>

            {/* Pagination Controls Footer */}
            <div className="p-4 bg-slate-950/60 border-t border-slate-800 flex flex-col sm:flex-row items-center justify-between gap-3 text-xs text-slate-400">
              <div className="flex items-center gap-2">
                <span>Showing page {page} of {totalPages}</span>
                <span>({totalCount} records total)</span>
              </div>

              <div className="flex items-center gap-3">
                <div className="flex items-center gap-1.5">
                  <span>Rows per page:</span>
                  <select
                    value={pageSize}
                    onChange={(e) => {
                      setPageSize(Number(e.target.value));
                      setPage(1);
                    }}
                    className="px-2 py-1 bg-slate-900 border border-slate-800 rounded-lg text-slate-300 focus:outline-none"
                  >
                    <option value={10}>10</option>
                    <option value={25}>25</option>
                    <option value={50}>50</option>
                    <option value={100}>100</option>
                  </select>
                </div>

                <div className="flex items-center gap-1">
                  <button
                    type="button"
                    disabled={page <= 1}
                    onClick={() => setPage((p) => Math.max(1, p - 1))}
                    className="p-1.5 rounded-lg bg-slate-900 border border-slate-800 disabled:opacity-40 hover:bg-slate-800 text-slate-300 cursor-pointer disabled:cursor-not-allowed"
                  >
                    <ChevronLeft className="w-4 h-4" />
                  </button>
                  <button
                    type="button"
                    disabled={page >= totalPages}
                    onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                    className="p-1.5 rounded-lg bg-slate-900 border border-slate-800 disabled:opacity-40 hover:bg-slate-800 text-slate-300 cursor-pointer disabled:cursor-not-allowed"
                  >
                    <ChevronRight className="w-4 h-4" />
                  </button>
                </div>
              </div>
            </div>
          </>
        )}
      </div>

      {/* User Details Drawer Modal */}
      {drawerUserId && (
        <UserDetailsDrawer
          userId={drawerUserId}
          saFetch={saFetch}
          onClose={() => setDrawerUserId(null)}
        />
      )}

      {/* Create User Modal */}
      {createUserOpen && (
        <CreateUserModal
          saFetch={saFetch}
          institutes={institutes}
          onClose={() => setCreateUserOpen(false)}
          onSuccess={() => {
            setCreateUserOpen(false);
            fetchUsers();
          }}
          onTriggerReauth={onTriggerReauth}
        />
      )}

      {/* Edit Profile Modal */}
      {editProfileUser && (
        <EditProfileModal
          user={editProfileUser}
          saFetch={saFetch}
          onClose={() => setEditProfileUser(null)}
          onSuccess={() => {
            setEditProfileUser(null);
            fetchUsers();
          }}
          onTriggerReauth={onTriggerReauth}
        />
      )}

      {/* Transfer Dept/Institute Modal */}
      {transferUser && (
        <TransferUserModal
          user={transferUser}
          institutes={institutes}
          saFetch={saFetch}
          onClose={() => setTransferUser(null)}
          onSuccess={() => {
            setTransferUser(null);
            fetchUsers();
          }}
          onTriggerReauth={onTriggerReauth}
        />
      )}

      {/* Activate / Deactivate Confirmation Modal */}
      {toggleActiveUser && (
        <ToggleActiveModal
          user={toggleActiveUser}
          saFetch={saFetch}
          onClose={() => setToggleActiveUser(null)}
          onSuccess={() => {
            setToggleActiveUser(null);
            fetchUsers();
          }}
        />
      )}

      {/* Reset Password Temporary Key Display Modal */}
      {resetPwdResult && (
        <TemporaryPasswordModal
          user={resetPwdResult.user}
          tempPass={resetPwdResult.tempPass}
          onClose={() => setResetPwdResult(null)}
        />
      )}

      {/* Bulk Action Confirmation Modal */}
      {bulkActionModal && (
        <BulkActionModal
          action={bulkActionModal.action}
          title={bulkActionModal.title}
          userCount={selectAllAcrossPages ? totalCount : selectedIds.length}
          userRole={activeRole}
          onClose={() => setBulkActionModal(null)}
          onConfirm={async (payload) => {
            const execute = async () => {
              try {
                const res = await saFetch('users/bulk-action/', {
                  method: 'POST',
                  body: JSON.stringify({
                    action: bulkActionModal.action,
                    user_ids: selectedIds,
                    select_all: selectAllAcrossPages,
                    filters: { role: activeRole },
                    payload,
                  }),
                });
                const body = await res.json();
                if (res.ok) {
                  alert(`Bulk ${bulkActionModal.action} complete: ${body.succeeded} succeeded, ${body.failed} failed.`);
                  setSelectedIds([]);
                  setSelectAllAcrossPages(false);
                  setBulkActionModal(null);
                  fetchUsers();
                } else {
                  alert(`Error: ${body.message}`);
                }
              } catch (err: any) {
                alert(`Error: ${err.message}`);
              }
            };

            if (['deactivate', 'move_department'].includes(bulkActionModal.action)) {
              onTriggerReauth(execute);
            } else {
              execute();
            }
          }}
        />
      )}
    </div>
  );
}

// ==============================================================================
// SUBCOMPONENTS
// ==============================================================================

function RoleTabButton({
  active,
  onClick,
  icon,
  label,
  count,
}: {
  active: boolean;
  onClick: () => void;
  icon: React.ReactNode;
  label: string;
  count: number;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`inline-flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold cursor-pointer transition-all ${
        active
          ? 'bg-emerald-600 text-white shadow-md'
          : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60'
      }`}
    >
      <span>{icon}</span>
      <span>{label}</span>
      <span
        className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
          active ? 'bg-emerald-800/80 text-white' : 'bg-slate-800 text-slate-400'
        }`}
      >
        {count}
      </span>
    </button>
  );
}

function UserDetailsDrawer({
  userId,
  saFetch,
  onClose,
}: {
  userId: number;
  saFetch: (endpoint: string) => Promise<Response>;
  onClose: () => void;
}) {
  const [data, setData] = useState<any | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    saFetch(`users/${userId}/drawer/`).then(async (res) => {
      if (res.ok) {
        const body = await res.json();
        setData(body.data);
      }
      setLoading(false);
    });
  }, [userId, saFetch]);

  return (
    <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-xs flex justify-end">
      <div className="w-full max-w-lg bg-slate-900 border-l border-slate-800 h-full overflow-y-auto p-6 space-y-6 text-slate-100 shadow-2xl">
        <div className="flex items-center justify-between border-b border-slate-800 pb-4">
          <div>
            <h2 className="text-base font-bold text-white">User Profile & Activity</h2>
            <p className="text-xs text-slate-400">Detailed account record & historical events</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-xl hover:bg-slate-800 text-slate-400 hover:text-white cursor-pointer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {loading || !data ? (
          <div className="flex flex-col items-center justify-center p-12 text-slate-400 space-y-2">
            <RefreshCw className="w-6 h-6 animate-spin text-emerald-400" />
            <p className="text-xs font-mono">Loading user record...</p>
          </div>
        ) : (
          <div className="space-y-6 text-xs">
            {/* Profile Overview Card */}
            <div className="p-4 bg-slate-950 rounded-2xl border border-slate-800 space-y-3">
              <div className="flex items-start justify-between">
                <div>
                  <h3 className="text-sm font-bold text-white">
                    {data.profile.first_name} {data.profile.last_name}
                  </h3>
                  <p className="font-mono text-slate-400 text-xs">{data.profile.email}</p>
                </div>
                {data.profile.is_active ? (
                  <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
                    Active
                  </span>
                ) : (
                  <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-rose-500/15 text-rose-400 border border-rose-500/30">
                    Inactive
                  </span>
                )}
              </div>

              <div className="grid grid-cols-2 gap-2 text-[11px] font-mono pt-2 border-t border-slate-800/80">
                <div>
                  <span className="text-slate-500 block">Identifier:</span>
                  <span className="text-emerald-400">{data.profile.identifier}</span>
                </div>
                <div>
                  <span className="text-slate-500 block">Role:</span>
                  <span className="uppercase text-slate-200">{data.profile.role}</span>
                </div>
                <div>
                  <span className="text-slate-500 block">Institution:</span>
                  <span className="text-slate-200 truncate block">{data.profile.institution.name}</span>
                </div>
                <div>
                  <span className="text-slate-500 block">Department:</span>
                  <span className="text-slate-200">{data.profile.department}</span>
                </div>
              </div>
            </div>

            {/* Activity Summary Section */}
            <div>
              <h4 className="text-xs font-bold text-slate-300 uppercase tracking-wider mb-2">
                Operational Summary
              </h4>
              <div className="grid grid-cols-2 gap-3">
                {data.profile.role === 'student' && (
                  <>
                    <div className="p-3 bg-slate-950 rounded-xl border border-slate-800">
                      <span className="text-slate-500 text-[10px] block">Exams Attempted</span>
                      <span className="text-lg font-bold text-white">
                        {data.activity_summary.total_attempts || 0}
                      </span>
                    </div>
                    <div className="p-3 bg-slate-950 rounded-xl border border-slate-800">
                      <span className="text-slate-500 text-[10px] block">Average Score</span>
                      <span className="text-lg font-bold text-emerald-400">
                        {data.activity_summary.average_score || 0}%
                      </span>
                    </div>
                    <div className="p-3 bg-slate-950 rounded-xl border border-slate-800 col-span-2">
                      <span className="text-slate-500 text-[10px] block">Flagged Violations</span>
                      <span className="text-sm font-semibold text-rose-400">
                        {data.activity_summary.total_violations || 0} incident(s) recorded
                      </span>
                    </div>
                  </>
                )}

                {data.profile.role === 'faculty' && (
                  <>
                    <div className="p-3 bg-slate-950 rounded-xl border border-slate-800">
                      <span className="text-slate-500 text-[10px] block">Total Exams</span>
                      <span className="text-lg font-bold text-white">
                        {data.activity_summary.total_exams_created || 0}
                      </span>
                    </div>
                    <div className="p-3 bg-slate-950 rounded-xl border border-slate-800">
                      <span className="text-slate-500 text-[10px] block">Live Now</span>
                      <span className="text-lg font-bold text-emerald-400">
                        {data.activity_summary.live_exams || 0}
                      </span>
                    </div>
                  </>
                )}

                {data.profile.role === 'admin' && (
                  <>
                    <div className="p-3 bg-slate-950 rounded-xl border border-slate-800">
                      <span className="text-slate-500 text-[10px] block">Total Students</span>
                      <span className="text-lg font-bold text-white">
                        {data.activity_summary.total_students || 0}
                      </span>
                    </div>
                    <div className="p-3 bg-slate-950 rounded-xl border border-slate-800">
                      <span className="text-slate-500 text-[10px] block">Total Faculty</span>
                      <span className="text-lg font-bold text-white">
                        {data.activity_summary.total_faculty || 0}
                      </span>
                    </div>
                  </>
                )}
              </div>
            </div>

            {/* Notifications Sent to this User */}
            <div>
              <h4 className="text-xs font-bold text-slate-300 uppercase tracking-wider mb-2">
                Recent Notifications ({data.notifications?.length || 0})
              </h4>
              <div className="space-y-2">
                {(data.notifications || []).length === 0 ? (
                  <p className="text-slate-500 text-xs italic">No notifications dispatched to this account.</p>
                ) : (
                  data.notifications.map((n: any) => (
                    <div key={n.id} className="p-3 bg-slate-950 rounded-xl border border-slate-800 space-y-1">
                      <div className="flex items-center justify-between text-[11px]">
                        <span className="font-semibold text-white">{n.title}</span>
                        <span className="text-slate-500">{new Date(n.created_at).toLocaleDateString()}</span>
                      </div>
                      <p className="text-slate-400 text-[11px] leading-relaxed">{n.message}</p>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function CreateUserModal({
  saFetch,
  institutes,
  onClose,
  onSuccess,
  onTriggerReauth,
}: {
  saFetch: (endpoint: string, options?: RequestInit) => Promise<Response>;
  institutes: any[];
  onClose: () => void;
  onSuccess: () => void;
  onTriggerReauth: (cb?: () => void) => void;
}) {
  const [role, setRole] = useState<'student' | 'faculty' | 'admin'>('student');
  const [email, setEmail] = useState('');
  const [firstName, setFirstName] = useState('');
  const [lastName, setLastName] = useState('');
  const [instId, setInstId] = useState(institutes[0]?.id || '');
  const [department, setDepartment] = useState('Computer Engineering');
  const [designation, setDesignation] = useState('Assistant Professor');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    const proceed = async () => {
      try {
        setLoading(true);
        const res = await saFetch('users/create/', {
          method: 'POST',
          body: JSON.stringify({
            role,
            email,
            first_name: firstName,
            last_name: lastName,
            institution_id: instId ? Number(instId) : null,
            department,
            designation,
          }),
        });
        const data = await res.json();
        if (res.ok) {
          alert(`User created! Temporary Password: ${data.temporary_password}`);
          onSuccess();
        } else {
          setError(data.message || 'Creation failed.');
        }
      } catch (err: any) {
        setError(err.message || 'Network error.');
      } finally {
        setLoading(false);
      }
    };

    if (role === 'admin') {
      onTriggerReauth(proceed);
    } else {
      proceed();
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-xs flex items-center justify-center p-4">
      <div className="w-full max-w-lg bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden shadow-2xl p-6 text-slate-100 space-y-4">
        <div className="flex items-center justify-between border-b border-slate-800 pb-3">
          <h3 className="text-sm font-bold text-white">Create New User Account</h3>
          <button type="button" onClick={onClose} className="text-slate-400 hover:text-white cursor-pointer">
            <X className="w-4 h-4" />
          </button>
        </div>

        {error && <p className="text-rose-400 text-xs bg-rose-500/10 p-2.5 rounded-xl border border-rose-500/20">{error}</p>}

        <form onSubmit={handleSubmit} className="space-y-3.5 text-xs">
          <div>
            <label className="block text-slate-300 font-semibold mb-1">User Role *</label>
            <div className="grid grid-cols-3 gap-2">
              {(['student', 'faculty', 'admin'] as const).map((r) => (
                <button
                  key={r}
                  type="button"
                  onClick={() => setRole(r)}
                  className={`py-2 rounded-xl border text-xs font-semibold uppercase tracking-wider cursor-pointer transition-all ${
                    role === r
                      ? 'bg-emerald-600 text-white border-emerald-500'
                      : 'bg-slate-950 border-slate-800 text-slate-400 hover:text-white'
                  }`}
                >
                  {r}
                </button>
              ))}
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-slate-300 font-semibold mb-1">First Name *</label>
              <input
                type="text"
                required
                value={firstName}
                onChange={(e) => setFirstName(e.target.value)}
                className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-white"
              />
            </div>
            <div>
              <label className="block text-slate-300 font-semibold mb-1">Last Name *</label>
              <input
                type="text"
                required
                value={lastName}
                onChange={(e) => setLastName(e.target.value)}
                className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-white"
              />
            </div>
          </div>

          <div>
            <label className="block text-slate-300 font-semibold mb-1">Email Address *</label>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="user@university.edu"
              className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-white font-mono"
            />
          </div>

          <div>
            <label className="block text-slate-300 font-semibold mb-1">Institution *</label>
            <select
              value={instId}
              onChange={(e) => setInstId(e.target.value)}
              className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-white cursor-pointer"
            >
              {institutes.map((inst) => (
                <option key={inst.id} value={inst.id}>
                  {inst.name} ({inst.code})
                </option>
              ))}
            </select>
          </div>

          {role !== 'admin' && (
            <div>
              <label className="block text-slate-300 font-semibold mb-1">Department *</label>
              <input
                type="text"
                required
                value={department}
                onChange={(e) => setDepartment(e.target.value)}
                className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-white"
              />
            </div>
          )}

          {role === 'faculty' && (
            <div>
              <label className="block text-slate-300 font-semibold mb-1">Designation</label>
              <input
                type="text"
                value={designation}
                onChange={(e) => setDesignation(e.target.value)}
                className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-white"
              />
            </div>
          )}

          <div className="flex items-center justify-end gap-2 pt-3 border-t border-slate-800">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 rounded-xl border border-slate-800 text-slate-300 cursor-pointer"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading}
              className="px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-bold cursor-pointer transition-colors"
            >
              {loading ? 'Creating...' : 'Create Account'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function EditProfileModal({
  user,
  saFetch,
  onClose,
  onSuccess,
  onTriggerReauth,
}: {
  user: any;
  saFetch: (endpoint: string, options?: RequestInit) => Promise<Response>;
  onClose: () => void;
  onSuccess: () => void;
  onTriggerReauth: (cb?: () => void) => void;
}) {
  const [firstName, setFirstName] = useState(user.first_name || user.full_name?.split(' ')[0] || '');
  const [lastName, setLastName] = useState(user.last_name || user.full_name?.split(' ')[1] || '');
  const [email, setEmail] = useState(user.email);
  const [loading, setLoading] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onTriggerReauth(async () => {
      try {
        setLoading(true);
        const res = await saFetch(`users/${user.id}/update-profile/`, {
          method: 'POST',
          body: JSON.stringify({ first_name: firstName, last_name: lastName, email }),
        });
        if (res.ok) {
          onSuccess();
        } else {
          const body = await res.json();
          alert(`Error: ${body.message}`);
        }
      } catch (err: any) {
        alert(`Error: ${err.message}`);
      } finally {
        setLoading(false);
      }
    });
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-xs flex items-center justify-center p-4">
      <div className="w-full max-w-md bg-slate-900 border border-slate-800 rounded-2xl p-6 text-slate-100 space-y-4">
        <h3 className="text-sm font-bold text-white border-b border-slate-800 pb-3">
          Edit Profile: {user.username}
        </h3>
        <p className="text-xs text-slate-400">
          Note: Department and Institution changes require the audited Transfer action.
        </p>
        <form onSubmit={handleSubmit} className="space-y-3 text-xs">
          <div>
            <label className="block text-slate-300 font-semibold mb-1">First Name</label>
            <input
              type="text"
              value={firstName}
              onChange={(e) => setFirstName(e.target.value)}
              className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-white"
            />
          </div>
          <div>
            <label className="block text-slate-300 font-semibold mb-1">Last Name</label>
            <input
              type="text"
              value={lastName}
              onChange={(e) => setLastName(e.target.value)}
              className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-white"
            />
          </div>
          <div>
            <label className="block text-slate-300 font-semibold mb-1">Email</label>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-white font-mono"
            />
          </div>
          <div className="flex items-center justify-end gap-2 pt-3 border-t border-slate-800">
            <button type="button" onClick={onClose} className="px-4 py-2 rounded-xl border border-slate-800 text-slate-300">
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading}
              className="px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-bold"
            >
              {loading ? 'Saving...' : 'Save Profile'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function TransferUserModal({
  user,
  institutes,
  saFetch,
  onClose,
  onSuccess,
  onTriggerReauth,
}: {
  user: any;
  institutes: any[];
  saFetch: (endpoint: string, options?: RequestInit) => Promise<Response>;
  onClose: () => void;
  onSuccess: () => void;
  onTriggerReauth: (cb?: () => void) => void;
}) {
  const [instId, setInstId] = useState(user.institution?.id || institutes[0]?.id || '');
  const [department, setDepartment] = useState('');
  const [reason, setReason] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!department || !reason) {
      alert('Department and transfer justification reason are mandatory.');
      return;
    }

    onTriggerReauth(async () => {
      try {
        setLoading(true);
        const res = await saFetch(`users/${user.id}/transfer/`, {
          method: 'POST',
          body: JSON.stringify({
            institution_id: instId ? Number(instId) : null,
            department,
            reason,
          }),
        });
        if (res.ok) {
          alert('User transferred successfully.');
          onSuccess();
        } else {
          const body = await res.json();
          alert(`Transfer error: ${body.message}`);
        }
      } catch (err: any) {
        alert(`Error: ${err.message}`);
      } finally {
        setLoading(false);
      }
    });
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-xs flex items-center justify-center p-4">
      <div className="w-full max-w-md bg-slate-900 border border-slate-800 rounded-2xl p-6 text-slate-100 space-y-4">
        <h3 className="text-sm font-bold text-white border-b border-slate-800 pb-3 flex items-center gap-2">
          <ArrowRightLeft className="w-4 h-4 text-amber-400" /> Transfer Organization
        </h3>
        <p className="text-xs text-slate-400 leading-relaxed">
          Reassign <strong>{user.full_name}</strong> to a different department or institution. This high-risk action is permanently audited.
        </p>

        <form onSubmit={handleSubmit} className="space-y-3.5 text-xs">
          <div>
            <label className="block text-slate-300 font-semibold mb-1">Target Institution *</label>
            <select
              value={instId}
              onChange={(e) => setInstId(e.target.value)}
              className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-white"
            >
              {institutes.map((inst) => (
                <option key={inst.id} value={inst.id}>
                  {inst.name} ({inst.code})
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-slate-300 font-semibold mb-1">New Department *</label>
            <input
              type="text"
              required
              placeholder="e.g. Electrical Engineering"
              value={department}
              onChange={(e) => setDepartment(e.target.value)}
              className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-white"
            />
          </div>

          <div>
            <label className="block text-slate-300 font-semibold mb-1">Justification Reason *</label>
            <textarea
              required
              rows={2}
              placeholder="Explain administrative reason for transfer..."
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-white"
            />
          </div>

          <div className="flex items-center justify-end gap-2 pt-3 border-t border-slate-800">
            <button type="button" onClick={onClose} className="px-4 py-2 rounded-xl border border-slate-800 text-slate-300">
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading}
              className="px-4 py-2 rounded-xl bg-amber-600 hover:bg-amber-500 text-white font-bold"
            >
              {loading ? 'Transferring...' : 'Execute Transfer'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function ToggleActiveModal({
  user,
  saFetch,
  onClose,
  onSuccess,
}: {
  user: any;
  saFetch: (endpoint: string, options?: RequestInit) => Promise<Response>;
  onClose: () => void;
  onSuccess: () => void;
}) {
  const [loading, setLoading] = useState(false);
  const nextStatus = !user.is_active;

  const handleConfirm = async () => {
    try {
      setLoading(true);
      const res = await saFetch(`users/${user.id}/toggle-active/`, { method: 'POST' });
      if (res.ok) {
        onSuccess();
      } else {
        const body = await res.json();
        alert(`Error: ${body.message}`);
      }
    } catch (err: any) {
      alert(`Error: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-xs flex items-center justify-center p-4">
      <div className="w-full max-w-md bg-slate-900 border border-slate-800 rounded-2xl p-6 text-slate-100 space-y-4">
        <h3 className="text-sm font-bold text-white border-b border-slate-800 pb-3 flex items-center gap-2">
          <AlertTriangle className={`w-4 h-4 ${nextStatus ? 'text-emerald-400' : 'text-rose-400'}`} />
          {nextStatus ? 'Activate User' : 'Deactivate User'}
        </h3>
        <p className="text-xs text-slate-300 leading-relaxed">
          Are you sure you want to {nextStatus ? 'activate' : 'deactivate'} account for{' '}
          <strong>{user.full_name}</strong> ({user.email})?
        </p>

        {!nextStatus && (
          <div className="p-3 bg-amber-500/10 border border-amber-500/20 rounded-xl text-xs text-amber-300">
            Deactivating this user blocks login immediately and suspends exam access or paper publishing rights.
          </div>
        )}

        <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-800">
          <button type="button" onClick={onClose} className="px-4 py-2 rounded-xl border border-slate-800 text-slate-300">
            Cancel
          </button>
          <button
            type="button"
            disabled={loading}
            onClick={handleConfirm}
            className={`px-4 py-2 rounded-xl text-white font-bold cursor-pointer ${
              nextStatus ? 'bg-emerald-600 hover:bg-emerald-500' : 'bg-rose-600 hover:bg-rose-500'
            }`}
          >
            {loading ? 'Processing...' : nextStatus ? 'Confirm Activation' : 'Confirm Deactivation'}
          </button>
        </div>
      </div>
    </div>
  );
}

function TemporaryPasswordModal({
  user,
  tempPass,
  onClose,
}: {
  user: any;
  tempPass: string;
  onClose: () => void;
}) {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(tempPass);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-xs flex items-center justify-center p-4">
      <div className="w-full max-w-md bg-slate-900 border border-slate-800 rounded-2xl p-6 text-slate-100 space-y-4 shadow-2xl">
        <h3 className="text-sm font-bold text-white border-b border-slate-800 pb-3 flex items-center gap-2">
          <KeyRound className="w-4 h-4 text-emerald-400" /> Temporary Credentials Generated
        </h3>
        <p className="text-xs text-slate-300 leading-relaxed">
          Password for <strong>{user.email}</strong> was reset. Provide this temporary password to the user. It is shown only once and is never stored in plain text.
        </p>

        <div className="flex items-center justify-between p-3.5 bg-slate-950 border border-slate-800 rounded-xl font-mono text-sm text-emerald-400">
          <span>{tempPass}</span>
          <button
            type="button"
            onClick={handleCopy}
            className="p-1.5 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white cursor-pointer"
            title="Copy Password"
          >
            {copied ? <Check className="w-4 h-4 text-emerald-400" /> : <Copy className="w-4 h-4" />}
          </button>
        </div>

        <button
          type="button"
          onClick={onClose}
          className="w-full py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-white font-semibold text-xs cursor-pointer"
        >
          Close & Acknowledge
        </button>
      </div>
    </div>
  );
}

function BulkActionModal({
  action,
  title,
  userCount,
  userRole,
  onClose,
  onConfirm,
}: {
  action: string;
  title: string;
  userCount: number;
  userRole: string;
  onClose: () => void;
  onConfirm: (payload: any) => Promise<void>;
}) {
  const [department, setDepartment] = useState('');
  const [reason, setReason] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    await onConfirm({ department, reason });
    setLoading(false);
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-xs flex items-center justify-center p-4">
      <div className="w-full max-w-md bg-slate-900 border border-slate-800 rounded-2xl p-6 text-slate-100 space-y-4">
        <h3 className="text-sm font-bold text-white border-b border-slate-800 pb-3 flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 text-amber-400" /> {title}
        </h3>
        <p className="text-xs text-slate-300 leading-relaxed">
          You are about to execute <strong>{action}</strong> on <strong>{userCount}</strong> {userRole}(s).
        </p>

        <form onSubmit={handleSubmit} className="space-y-3.5 text-xs">
          {action === 'move_department' && (
            <div>
              <label className="block text-slate-300 font-semibold mb-1">New Target Department *</label>
              <input
                type="text"
                required
                placeholder="e.g. Electrical Engineering"
                value={department}
                onChange={(e) => setDepartment(e.target.value)}
                className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-white"
              />
            </div>
          )}

          <div>
            <label className="block text-slate-300 font-semibold mb-1">Audit Justification *</label>
            <textarea
              required
              rows={2}
              placeholder="Reason for this bulk action..."
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-white"
            />
          </div>

          <div className="flex items-center justify-end gap-2 pt-3 border-t border-slate-800">
            <button type="button" onClick={onClose} className="px-4 py-2 rounded-xl border border-slate-800 text-slate-300">
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading}
              className="px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-bold"
            >
              {loading ? 'Executing...' : 'Confirm Bulk Action'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

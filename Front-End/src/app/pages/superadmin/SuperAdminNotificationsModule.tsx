import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  Bell,
  Send,
  Calendar,
  Users,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  RefreshCw,
  Search,
  Filter,
  Plus,
  Clock,
  ExternalLink,
  ChevronLeft,
  ChevronRight,
  Info,
  Building2,
  GraduationCap,
  Sparkles,
  Eye,
  Check,
  ShieldAlert,
} from 'lucide-react';

interface CampaignItem {
  id: number;
  title: string;
  message: string;
  notification_type: 'info' | 'warning' | 'success' | 'error';
  link: string;
  target_audience: string;
  target_role: string;
  target_institute_name: string;
  target_department: string;
  status: 'draft' | 'scheduled' | 'sending' | 'completed' | 'failed' | 'cancelled';
  recipients_count: number;
  delivered_count: number;
  read_count: number;
  read_percent: number;
  scheduled_at: string | null;
  dispatched_at: string | null;
  created_by: string;
  created_at: string;
}

interface SuperAdminNotificationsModuleProps {
  saFetch: (endpoint: string, options?: RequestInit) => Promise<Response>;
  onTriggerReauth: (cb?: () => void) => void;
}

export function SuperAdminNotificationsModule({ saFetch }: SuperAdminNotificationsModuleProps) {
  const [campaigns, setCampaigns] = useState<CampaignItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [totalItems, setTotalItems] = useState(0);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');

  const [kpis, setKpis] = useState({
    total_campaigns: 0,
    total_notifications_sent: 0,
    scheduled_count: 0,
    smtp_configured: false,
  });

  // Compose Modal State
  const [composeModalOpen, setComposeModalOpen] = useState(false);
  const [title, setTitle] = useState('');
  const [message, setMessage] = useState('');
  const [notifType, setNotifType] = useState<'info' | 'warning' | 'success' | 'error'>('info');
  const [link, setLink] = useState('');
  const [targetAudience, setTargetAudience] = useState('all');
  const [targetRole, setTargetRole] = useState('student');
  const [targetInstituteId, setTargetInstituteId] = useState<string>('');
  const [targetDepartment, setTargetDepartment] = useState('');
  const [isScheduled, setIsScheduled] = useState(false);
  const [scheduledAt, setScheduledAt] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [composeError, setComposeError] = useState('');

  // Audience Preview State
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewData, setPreviewData] = useState<{ total_recipients: number; sample_recipients: any[] } | null>(null);

  // Institutes list for selector
  const [institutes, setInstitutes] = useState<any[]>([]);

  // Fetch Campaigns
  const fetchCampaigns = useCallback(async () => {
    try {
      setLoading(true);
      const params = new URLSearchParams({
        page: String(page),
        page_size: '10',
        search,
        status: statusFilter,
      });
      const res = await saFetch(`notifications/campaigns/?${params.toString()}`);
      if (res.ok) {
        const body = await res.json();
        setCampaigns(body.campaigns || []);
        setTotalPages(body.pagination?.total_pages || 1);
        setTotalItems(body.pagination?.total_items || 0);
        if (body.kpis) {
          setKpis(body.kpis);
        }
      }
    } catch (err) {
      console.error('Failed to fetch campaigns:', err);
    } finally {
      setLoading(false);
    }
  }, [page, search, statusFilter, saFetch]);

  useEffect(() => {
    fetchCampaigns();
  }, [fetchCampaigns]);

  // Load Institutes for audience selector
  useEffect(() => {
    saFetch('institutes/')
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (data && data.data) {
          setInstitutes(data.data);
        }
      })
      .catch(() => {});
  }, [saFetch]);

  // Audience Live Preview Debounce
  useEffect(() => {
    if (!composeModalOpen) return;
    const timer = setTimeout(async () => {
      setPreviewLoading(true);
      try {
        const res = await saFetch('notifications/audience-preview/', {
          method: 'POST',
          body: JSON.stringify({
            target_audience: targetAudience,
            target_role: targetAudience === 'role' ? targetRole : '',
            target_institute_id: targetAudience === 'institute' ? Number(targetInstituteId) || null : null,
            target_department: targetAudience === 'department' ? targetDepartment : '',
          }),
        });
        if (res.ok) {
          const d = await res.json();
          setPreviewData(d);
        }
      } catch {}
      finally {
        setPreviewLoading(false);
      }
    }, 300);

    return () => clearTimeout(timer);
  }, [composeModalOpen, targetAudience, targetRole, targetInstituteId, targetDepartment, saFetch]);

  // Handle Create Campaign
  const handleCreateCampaign = async (e: React.FormEvent) => {
    e.preventDefault();
    setComposeError('');
    setSubmitting(true);

    try {
      const payload: any = {
        title: title.trim(),
        message: message.trim(),
        notification_type: notifType,
        link: link.trim(),
        target_audience: targetAudience,
      };

      if (targetAudience === 'role') payload.target_role = targetRole;
      if (targetAudience === 'institute' && targetInstituteId) payload.target_institute_id = Number(targetInstituteId);
      if (targetAudience === 'department') payload.target_department = targetDepartment.trim();
      if (isScheduled && scheduledAt) payload.scheduled_at = new Date(scheduledAt).toISOString();

      const res = await saFetch('notifications/campaigns/', {
        method: 'POST',
        body: JSON.stringify(payload),
      });
      const data = await res.json();

      if (res.ok || res.status === 201) {
        setComposeModalOpen(false);
        resetForm();
        fetchCampaigns();
      } else {
        setComposeError(data.message || 'Failed to create campaign.');
      }
    } catch (err: any) {
      setComposeError(err.message || 'Network error.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleCancelCampaign = async (campaign: CampaignItem) => {
    if (!window.confirm(`Are you sure you want to cancel the scheduled campaign "${campaign.title}"?`)) {
      return;
    }
    try {
      const res = await saFetch(`notifications/campaigns/${campaign.id}/cancel/`, { method: 'POST' });
      if (res.ok) {
        fetchCampaigns();
      } else {
        const d = await res.json();
        alert(d.message || 'Failed to cancel campaign.');
      }
    } catch {
      alert('Network error.');
    }
  };

  const resetForm = () => {
    setTitle('');
    setMessage('');
    setNotifType('info');
    setLink('');
    setTargetAudience('all');
    setTargetRole('student');
    setTargetInstituteId('');
    setTargetDepartment('');
    setIsScheduled(false);
    setScheduledAt('');
    setComposeError('');
    setPreviewData(null);
  };

  return (
    <div className="space-y-6 min-w-0 max-w-full">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800/80 pb-5">
        <div>
          <div className="flex items-center gap-2.5">
            <h1 className="text-xl sm:text-2xl font-bold text-white tracking-tight">Notification Campaigns</h1>
            <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" /> Bell In-App Active
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Targeted institutional broadcasts • Cross-role audience builder • Real-time read rate tracking
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={fetchCampaigns}
            className="inline-flex items-center gap-2 px-3.5 py-2 rounded-xl bg-slate-900 hover:bg-slate-800 border border-slate-700/80 text-xs font-semibold text-slate-200 cursor-pointer transition-all"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            <span>Refresh</span>
          </button>
          <button
            onClick={() => {
              resetForm();
              setComposeModalOpen(true);
            }}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold shadow-md shadow-emerald-950/40 cursor-pointer transition-all"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>New Campaign</span>
          </button>
        </div>
      </div>

      {/* Email Backend Disabled Explanation Banner */}
      <div className="p-4 rounded-2xl bg-amber-500/10 border border-amber-500/30 text-amber-300 text-xs flex items-start gap-3">
        <Info className="w-4 h-4 shrink-0 mt-0.5 text-amber-400" />
        <div className="space-y-0.5">
          <p className="font-bold">Email Dispatch Note (Console Backend Active)</p>
          <p className="text-[11px] text-amber-200/90 leading-relaxed">
            The platform email backend is configured to local console output (SMTP host is empty in <code>.env</code>).
            All campaign dispatches are instantly delivered in-app directly to each student, faculty, and admin bell indicator with zero latency.
          </p>
        </div>
      </div>

      {/* KPI Stat Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3.5">
        <div className="p-4 rounded-2xl bg-slate-900/60 border border-slate-800 space-y-1">
          <div className="flex items-center justify-between text-slate-400 text-xs">
            <span>Total Broadcasts</span>
            <Send className="w-4 h-4 text-emerald-400" />
          </div>
          <p className="text-xl font-extrabold text-white">{kpis.total_campaigns}</p>
          <p className="text-[10px] text-slate-400 font-mono">Platform announcements</p>
        </div>

        <div className="p-4 rounded-2xl bg-slate-900/60 border border-slate-800 space-y-1">
          <div className="flex items-center justify-between text-slate-400 text-xs">
            <span>In-App Delivered</span>
            <CheckCircle2 className="w-4 h-4 text-sky-400" />
          </div>
          <p className="text-xl font-extrabold text-white">{kpis.total_notifications_sent.toLocaleString()}</p>
          <p className="text-[10px] text-slate-400 font-mono">Bell inbox entries</p>
        </div>

        <div className="p-4 rounded-2xl bg-slate-900/60 border border-slate-800 space-y-1">
          <div className="flex items-center justify-between text-slate-400 text-xs">
            <span>Scheduled Campaigns</span>
            <Calendar className="w-4 h-4 text-amber-400" />
          </div>
          <p className="text-xl font-extrabold text-white">{kpis.scheduled_count}</p>
          <p className="text-[10px] text-slate-400 font-mono">Awaiting dispatch</p>
        </div>

        <div className="p-4 rounded-2xl bg-slate-900/60 border border-slate-800 space-y-1">
          <div className="flex items-center justify-between text-slate-400 text-xs">
            <span>Active Channel</span>
            <Bell className="w-4 h-4 text-purple-400" />
          </div>
          <p className="text-xs font-bold text-white uppercase font-mono">In-App Bell Only</p>
          <p className="text-[10px] text-slate-400 font-mono">SMTP disabled</p>
        </div>
      </div>

      {/* Filter / Search Bar */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3">
        <div className="relative flex-1">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }}
            placeholder="Search campaigns by title, message snippet, or creator..."
            className="w-full pl-9 pr-4 py-2 bg-slate-900 border border-slate-800 rounded-xl text-xs text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-emerald-500/50"
          />
        </div>

        <div className="flex items-center gap-2">
          <select
            value={statusFilter}
            onChange={(e) => {
              setStatusFilter(e.target.value);
              setPage(1);
            }}
            className="px-3 py-2 bg-slate-900 border border-slate-800 rounded-xl text-xs text-slate-300 focus:outline-none focus:ring-2 focus:ring-emerald-500/50"
          >
            <option value="all">All Statuses</option>
            <option value="completed">Completed Only</option>
            <option value="scheduled">Scheduled Only</option>
            <option value="sending">Sending (In-Flight)</option>
            <option value="cancelled">Cancelled</option>
          </select>
        </div>
      </div>

      {/* Campaigns Table (Zero Overflow Fixed Layout) */}
      <div className="bg-slate-900/70 border border-slate-800 rounded-3xl overflow-hidden shadow-xl">
        <div className="hidden md:block overflow-hidden">
          <table className="w-full text-left text-xs table-fixed">
            <colgroup>
              <col className="w-[32%]" />
              <col className="w-[20%]" />
              <col className="w-[14%]" />
              <col className="w-[12%]" />
              <col className="w-[12%]" />
              <col className="w-[10%]" />
            </colgroup>
            <thead className="bg-slate-950/80 text-slate-400 text-[10px] uppercase font-bold tracking-wider border-b border-slate-800">
              <tr>
                <th className="py-3 px-4">Title & Type</th>
                <th className="py-3 px-3">Target Audience</th>
                <th className="py-3 px-3">Delivery Rate</th>
                <th className="py-3 px-3">Read Rate</th>
                <th className="py-3 px-3">Status</th>
                <th className="py-3 px-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {campaigns.map((c) => (
                <tr key={c.id} className="hover:bg-slate-800/30 transition-colors">
                  {/* Title & Type */}
                  <td className="py-3.5 px-4 min-w-0">
                    <div className="flex items-center gap-2">
                      <span
                        className={`w-2 h-2 rounded-full shrink-0 ${
                          c.notification_type === 'warning'
                            ? 'bg-amber-400'
                            : c.notification_type === 'error'
                            ? 'bg-rose-400'
                            : c.notification_type === 'success'
                            ? 'bg-emerald-400'
                            : 'bg-sky-400'
                        }`}
                      />
                      <p className="font-bold text-white truncate" title={c.title}>
                        {c.title}
                      </p>
                    </div>
                    <p className="text-[11px] text-slate-400 truncate mt-0.5" title={c.message}>
                      {c.message}
                    </p>
                  </td>

                  {/* Audience */}
                  <td className="py-3.5 px-3 min-w-0">
                    <p className="font-semibold text-slate-200 capitalize truncate">
                      {c.target_audience === 'role'
                        ? `${c.target_role}s`
                        : c.target_audience === 'institute'
                        ? c.target_institute_name
                        : c.target_audience === 'department'
                        ? c.target_department
                        : 'All Users'}
                    </p>
                    <p className="text-[11px] text-slate-400 font-mono">
                      {c.recipients_count.toLocaleString()} recipients
                    </p>
                  </td>

                  {/* Delivery */}
                  <td className="py-3.5 px-3 min-w-0 font-mono text-slate-300">
                    <p className="font-bold text-emerald-400">
                      {c.delivered_count} / {c.recipients_count}
                    </p>
                    <p className="text-[10px] text-slate-400">
                      {c.dispatched_at ? new Date(c.dispatched_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : 'Pending'}
                    </p>
                  </td>

                  {/* Read Rate */}
                  <td className="py-3.5 px-3 min-w-0">
                    <div className="space-y-1">
                      <div className="flex justify-between text-[11px] font-mono">
                        <span className="text-white font-bold">{c.read_percent}%</span>
                        <span className="text-slate-400">({c.read_count})</span>
                      </div>
                      <div className="w-full bg-slate-800 rounded-full h-1.5 overflow-hidden">
                        <div
                          className="bg-emerald-500 h-full rounded-full transition-all"
                          style={{ width: `${Math.min(100, c.read_percent)}%` }}
                        />
                      </div>
                    </div>
                  </td>

                  {/* Status */}
                  <td className="py-3.5 px-3 min-w-0">
                    <span
                      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider ${
                        c.status === 'completed'
                          ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                          : c.status === 'scheduled'
                          ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                          : c.status === 'sending'
                          ? 'bg-sky-500/10 text-sky-400 border border-sky-500/20 animate-pulse'
                          : 'bg-slate-800 text-slate-400 border border-slate-700'
                      }`}
                    >
                      {c.status}
                    </span>
                  </td>

                  {/* Actions */}
                  <td className="py-3.5 px-4 text-right min-w-0">
                    {c.status === 'scheduled' && (
                      <button
                        onClick={() => handleCancelCampaign(c)}
                        className="px-2.5 py-1 rounded-lg border border-rose-500/30 text-rose-300 hover:bg-rose-500/10 text-[11px] font-semibold cursor-pointer transition-colors"
                      >
                        Cancel
                      </button>
                    )}
                  </td>
                </tr>
              ))}
              {campaigns.length === 0 && !loading && (
                <tr>
                  <td colSpan={6} className="py-12 text-center text-slate-500">
                    No notification campaigns created yet. Click "New Campaign" to broadcast.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {/* Mobile Cards */}
        <div className="md:hidden divide-y divide-slate-800/80">
          {campaigns.map((c) => (
            <div key={c.id} className="p-4 space-y-2.5 text-xs">
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <p className="font-bold text-white text-xs truncate">{c.title}</p>
                  <p className="text-[11px] text-slate-400 line-clamp-2 mt-0.5">{c.message}</p>
                </div>
                <span
                  className={`px-2 py-0.5 rounded-full text-[10px] font-bold uppercase shrink-0 ${
                    c.status === 'completed'
                      ? 'bg-emerald-500/10 text-emerald-400'
                      : 'bg-amber-500/10 text-amber-400'
                  }`}
                >
                  {c.status}
                </span>
              </div>

              <div className="flex justify-between items-center text-[11px] text-slate-400 pt-1">
                <span>Audience: <strong className="text-slate-200">{c.target_audience}</strong></span>
                <span>Read: <strong className="text-emerald-400">{c.read_percent}%</strong> ({c.read_count})</span>
              </div>

              {c.status === 'scheduled' && (
                <div className="pt-2 border-t border-slate-800 flex justify-end">
                  <button
                    onClick={() => handleCancelCampaign(c)}
                    className="px-2.5 py-1 rounded-lg bg-rose-500/10 text-rose-300 border border-rose-500/30 text-[11px]"
                  >
                    Cancel Scheduled Campaign
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>

        {/* Pagination Footer */}
        <div className="p-4 bg-slate-950/60 border-t border-slate-800 flex items-center justify-between text-xs text-slate-400">
          <span>
            Page {page} of {totalPages} ({totalItems} total broadcasts)
          </span>
          <div className="flex items-center gap-1">
            <button
              disabled={page <= 1}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              className="p-1.5 rounded-lg bg-slate-800 border border-slate-700 text-slate-300 disabled:opacity-40 cursor-pointer"
            >
              <ChevronLeft className="w-3.5 h-3.5" />
            </button>
            <button
              disabled={page >= totalPages}
              onClick={() => setPage((p) => p + 1)}
              className="p-1.5 rounded-lg bg-slate-800 border border-slate-700 text-slate-300 disabled:opacity-40 cursor-pointer"
            >
              <ChevronRight className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </div>

      {/* Compose Campaign Modal */}
      {composeModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="w-full max-w-2xl bg-slate-900 border border-slate-800 rounded-3xl p-6 text-slate-100 shadow-2xl space-y-4 max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center gap-3">
                <div className="p-2.5 rounded-2xl bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                  <Send className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-base font-bold text-white">Create Broadcast Campaign</h3>
                  <p className="text-xs text-slate-400">Target audience builder with real-time recipient resolution</p>
                </div>
              </div>
            </div>

            {composeError && (
              <div className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs">
                {composeError}
              </div>
            )}

            <form onSubmit={handleCreateCampaign} className="space-y-4 text-xs">
              {/* Title & Type */}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div className="sm:col-span-2">
                  <label className="block text-slate-300 font-semibold mb-1">Campaign Title *</label>
                  <input
                    type="text"
                    required
                    value={title}
                    onChange={(e) => setTitle(e.target.value)}
                    placeholder="e.g. System Maintenance Notice or Exam Guidelines Released"
                    className="w-full px-3.5 py-2.5 bg-slate-950 border border-slate-800 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-emerald-500/40"
                  />
                </div>
                <div>
                  <label className="block text-slate-300 font-semibold mb-1">Tone / Type</label>
                  <select
                    value={notifType}
                    onChange={(e: any) => setNotifType(e.target.value)}
                    className="w-full px-3 py-2.5 bg-slate-950 border border-slate-800 rounded-xl text-white focus:outline-none focus:ring-2 focus:ring-emerald-500/40"
                  >
                    <option value="info">Info (Blue)</option>
                    <option value="warning">Warning (Amber)</option>
                    <option value="success">Success (Green)</option>
                    <option value="error">Critical Alert (Red)</option>
                  </select>
                </div>
              </div>

              {/* Message Body */}
              <div>
                <label className="block text-slate-300 font-semibold mb-1">Message Content *</label>
                <textarea
                  rows={3}
                  required
                  value={message}
                  onChange={(e) => setMessage(e.target.value)}
                  placeholder="Type the message body that users will see in their notification drawer..."
                  className="w-full px-3.5 py-2.5 bg-slate-950 border border-slate-800 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-emerald-500/40"
                />
              </div>

              {/* Link / URL */}
              <div>
                <label className="block text-slate-300 font-semibold mb-1">Action Link (Optional)</label>
                <input
                  type="text"
                  value={link}
                  onChange={(e) => setLink(e.target.value)}
                  placeholder="e.g. /exams or /question-bank"
                  className="w-full px-3.5 py-2 bg-slate-950 border border-slate-800 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-emerald-500/40 font-mono"
                />
              </div>

              {/* Audience Builder */}
              <div className="p-4 bg-slate-950/80 border border-slate-800 rounded-2xl space-y-3">
                <p className="font-bold text-slate-200 flex items-center gap-2">
                  <Users className="w-4 h-4 text-emerald-400" /> Target Audience Builder
                </p>

                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                  {[
                    { key: 'all', label: 'All Users' },
                    { key: 'role', label: 'By Role' },
                    { key: 'institute', label: 'By Institute' },
                    { key: 'department', label: 'By Department' },
                  ].map((opt) => (
                    <button
                      key={opt.key}
                      type="button"
                      onClick={() => setTargetAudience(opt.key)}
                      className={`py-2 px-3 rounded-xl border text-center font-medium cursor-pointer transition-all ${
                        targetAudience === opt.key
                          ? 'bg-emerald-500/20 border-emerald-500/50 text-emerald-300 font-bold'
                          : 'bg-slate-900 border-slate-800 text-slate-400 hover:text-white'
                      }`}
                    >
                      {opt.label}
                    </button>
                  ))}
                </div>

                {/* Sub-selector for Role */}
                {targetAudience === 'role' && (
                  <div className="pt-2 flex items-center gap-2">
                    <label className="text-slate-400 text-xs">Target Role:</label>
                    <select
                      value={targetRole}
                      onChange={(e) => setTargetRole(e.target.value)}
                      className="px-3 py-1.5 bg-slate-900 border border-slate-800 rounded-xl text-white"
                    >
                      <option value="student">Students Only</option>
                      <option value="faculty">Faculty Only</option>
                      <option value="admin">Institute Admins Only</option>
                    </select>
                  </div>
                )}

                {/* Sub-selector for Institute */}
                {targetAudience === 'institute' && (
                  <div className="pt-2 space-y-1">
                    <label className="text-slate-400 text-xs">Select Institute:</label>
                    <select
                      value={targetInstituteId}
                      onChange={(e) => setTargetInstituteId(e.target.value)}
                      className="w-full px-3 py-2 bg-slate-900 border border-slate-800 rounded-xl text-white"
                    >
                      <option value="">-- Choose Institute --</option>
                      {institutes.map((inst) => (
                        <option key={inst.id} value={inst.id}>
                          {inst.name} ({inst.code})
                        </option>
                      ))}
                    </select>
                  </div>
                )}

                {/* Sub-selector for Department */}
                {targetAudience === 'department' && (
                  <div className="pt-2 space-y-1">
                    <label className="text-slate-400 text-xs">Department Name:</label>
                    <input
                      type="text"
                      value={targetDepartment}
                      onChange={(e) => setTargetDepartment(e.target.value)}
                      placeholder="e.g. Computer Engineering, Information Technology, Physics"
                      className="w-full px-3 py-2 bg-slate-900 border border-slate-800 rounded-xl text-white"
                    />
                  </div>
                )}

                {/* Live Preview Count & Sample Recipients Pill */}
                <div className="pt-2 border-t border-slate-800/80 flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-[11px]">
                  <div className="flex items-center gap-2">
                    <span className="text-slate-400">Resolved Audience:</span>
                    <span className="px-2.5 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 font-bold font-mono">
                      {previewLoading ? 'Resolving...' : `${previewData?.total_recipients ?? 0} recipients`}
                    </span>
                  </div>

                  {previewData?.sample_recipients && previewData.sample_recipients.length > 0 && (
                    <span className="text-slate-400 font-mono truncate">
                      Sample: {previewData.sample_recipients.map((s) => s.username).join(', ')}
                    </span>
                  )}
                </div>
              </div>

              {/* Scheduling Options */}
              <div className="p-3.5 bg-slate-950/60 border border-slate-800 rounded-2xl space-y-2.5">
                <div className="flex items-center justify-between">
                  <label className="font-semibold text-slate-300 flex items-center gap-2">
                    <Calendar className="w-4 h-4 text-amber-400" /> Schedule for Future Dispatch
                  </label>
                  <input
                    type="checkbox"
                    checked={isScheduled}
                    onChange={(e) => setIsScheduled(e.target.checked)}
                    className="w-4 h-4 rounded-sm accent-emerald-500 cursor-pointer"
                  />
                </div>

                {isScheduled && (
                  <div className="pt-1">
                    <label className="block text-[11px] text-slate-400 mb-1">Dispatch Datetime *</label>
                    <input
                      type="datetime-local"
                      required={isScheduled}
                      value={scheduledAt}
                      onChange={(e) => setScheduledAt(e.target.value)}
                      className="w-full px-3 py-2 bg-slate-900 border border-slate-800 rounded-xl text-white text-xs"
                    />
                  </div>
                )}
              </div>

              <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-800">
                <button
                  type="button"
                  onClick={() => setComposeModalOpen(false)}
                  className="px-4 py-2 rounded-xl border border-slate-800 text-slate-400 hover:text-white cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting || !title.trim() || !message.trim()}
                  className="px-5 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-bold disabled:opacity-40 cursor-pointer transition-all"
                >
                  {submitting
                    ? 'Processing...'
                    : isScheduled
                    ? 'Schedule Campaign'
                    : 'Dispatch Now'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

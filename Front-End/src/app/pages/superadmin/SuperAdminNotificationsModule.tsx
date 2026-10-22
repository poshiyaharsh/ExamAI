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
  Mail,
  MailCheck,
  Layers,
  HelpCircle,
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
  show_popup?: boolean;
  send_email?: boolean;
  channels?: string[];
  email_sent_count?: number;
  email_failed_count?: number;
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

  const [kpis, setKpis] = useState<{
    total_campaigns: number;
    total_notifications_sent: number;
    scheduled_count: number;
    smtp_configured: boolean;
    email_status?: {
      is_configured: boolean;
      backend: string;
      provider: string;
      host: string;
      port: number;
      from_email: string;
      use_tls: boolean;
      use_ssl: boolean;
      daily_limit: number;
      sent_today: number;
      remaining_today: number;
      quota_reached: boolean;
    };
  }>({
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
  const [showPopup, setShowPopup] = useState(false);
  const [sendEmail, setSendEmail] = useState(false);
  const [isScheduled, setIsScheduled] = useState(false);
  const [scheduledAt, setScheduledAt] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [composeError, setComposeError] = useState('');

  // Audience Preview State
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewData, setPreviewData] = useState<{ total_recipients: number; sample_recipients: any[]; email_status_banner?: string } | null>(null);

  // Email Diagnostics & Test Modal State
  const [emailModalOpen, setEmailModalOpen] = useState(false);
  const [testEmailTo, setTestEmailTo] = useState('');
  const [testEmailLoading, setTestEmailLoading] = useState(false);
  const [testEmailResult, setTestEmailResult] = useState<{ status: 'success' | 'error'; message: string; data?: any } | null>(null);

  // Pop-Up Live Preview in Super Admin Console
  const [previewPopupOpen, setPreviewPopupOpen] = useState(false);

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
        show_popup: showPopup,
        send_email: sendEmail,
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
    setShowPopup(false);
    setSendEmail(false);
    setIsScheduled(false);
    setScheduledAt('');
    setComposeError('');
    setPreviewData(null);
  };

  const handleSendTestEmail = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!testEmailTo.trim() || !testEmailTo.includes('@')) {
      setTestEmailResult({ status: 'error', message: 'Please enter a valid recipient email address.' });
      return;
    }
    setTestEmailLoading(true);
    setTestEmailResult(null);
    try {
      const res = await saFetch('notifications/send-test-email/', {
        method: 'POST',
        body: JSON.stringify({ to: testEmailTo.trim() }),
      });
      const data = await res.json();
      if (res.ok) {
        setTestEmailResult({
          status: 'success',
          message: data.message || 'Test email dispatched successfully.',
          data: data.data,
        });
        fetchCampaigns();
      } else {
        setTestEmailResult({
          status: 'error',
          message: data.message || 'Failed to dispatch test email.',
        });
      }
    } catch (err: any) {
      setTestEmailResult({
        status: 'error',
        message: err.message || 'Network communication failure.',
      });
    } finally {
      setTestEmailLoading(false);
    }
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

        <div className="flex flex-wrap items-center gap-2">
          <button
            onClick={() => {
              setTestEmailResult(null);
              setEmailModalOpen(true);
            }}
            className="inline-flex items-center gap-2 px-3.5 py-2 rounded-xl bg-slate-900 hover:bg-slate-800 border border-slate-700/80 text-xs font-semibold text-sky-300 cursor-pointer transition-all"
          >
            <Mail className="w-3.5 h-3.5 text-sky-400" />
            <span>Email Diagnostics</span>
          </button>
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

      {/* Dynamic Email Delivery Status Banner */}
      {kpis.email_status?.is_configured ? (
        <div className="p-4 rounded-2xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 text-xs flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
          <div className="flex items-start gap-3">
            <MailCheck className="w-4 h-4 shrink-0 mt-0.5 text-emerald-400" />
            <div className="space-y-0.5">
              <p className="font-bold flex items-center gap-2">
                Real Outbound Email Active • Provider: {kpis.email_status.provider}
                <span className="px-2 py-0.2 rounded-md bg-emerald-500/20 text-emerald-300 font-mono text-[10px]">
                  {kpis.email_status.sent_today} / {kpis.email_status.daily_limit} Daily Quota Used
                </span>
              </p>
              <p className="text-[11px] text-emerald-200/90 leading-relaxed">
                SMTP server connected via {kpis.email_status.host}:{kpis.email_status.port} (Sender: {kpis.email_status.from_email}).
                Broadcast campaigns with outbound email enabled will deliver directly to user inboxes.
              </p>
            </div>
          </div>
          <button
            onClick={() => setEmailModalOpen(true)}
            className="shrink-0 px-3 py-1.5 rounded-xl bg-emerald-500/20 hover:bg-emerald-500/30 border border-emerald-500/40 text-emerald-200 font-bold text-[11px] transition-colors cursor-pointer"
          >
            Test Delivery
          </button>
        </div>
      ) : (
        <div className="p-4 rounded-2xl bg-amber-500/10 border border-amber-500/30 text-amber-300 text-xs flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
          <div className="flex items-start gap-3">
            <Info className="w-4 h-4 shrink-0 mt-0.5 text-amber-400" />
            <div className="space-y-0.5">
              <p className="font-bold">Email Dispatch Note (Console Backend Fallback Active)</p>
              <p className="text-[11px] text-amber-200/90 leading-relaxed">
                SMTP credentials are unset in <code>.env</code>. The platform automatically falls back to console simulation without failing.
                In-app bell notifications and first-time dialog popups deliver with zero latency.
              </p>
            </div>
          </div>
          <button
            onClick={() => setEmailModalOpen(true)}
            className="shrink-0 px-3 py-1.5 rounded-xl bg-amber-500/20 hover:bg-amber-500/30 border border-amber-500/40 text-amber-200 font-bold text-[11px] transition-colors cursor-pointer"
          >
            Setup Guide & Test
          </button>
        </div>
      )}

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
          <p className="text-[10px] text-slate-400 font-mono">Bell & Pop-up entries</p>
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
            <span>Active Channels</span>
            <Layers className="w-4 h-4 text-purple-400" />
          </div>
          <p className="text-xs font-bold text-white uppercase font-mono truncate">
            {kpis.email_status?.is_configured ? 'Bell + Pop-Up + Email' : 'Bell + Pop-Up'}
          </p>
          <p className="text-[10px] text-slate-400 font-mono truncate">
            {kpis.email_status?.is_configured ? `SMTP: ${kpis.email_status.provider}` : 'SMTP: Local Console'}
          </p>
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

              {/* Multi-Channel Delivery Options (Pop-Up & Real Email) */}
              <div className="p-4 bg-slate-950/80 border border-slate-800 rounded-2xl space-y-3.5">
                <p className="font-bold text-slate-200 flex items-center gap-2">
                  <Layers className="w-4 h-4 text-emerald-400" /> Additional Delivery Channels
                </p>

                {/* Pop-Up Modal Toggle */}
                <div className="p-3 rounded-xl bg-slate-900 border border-slate-800 flex items-start justify-between gap-3">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-white">First-Time Dialog Pop-Up</span>
                      <span className="px-2 py-0.5 rounded-full text-[9px] font-bold bg-purple-500/20 text-purple-300 border border-purple-500/30 uppercase">
                        High Priority
                      </span>
                    </div>
                    <p className="text-[11px] text-slate-400 leading-relaxed">
                      Pops up in the center of the user's screen upon their next visit. Exam attempts are automatically shielded from interruption.
                    </p>
                    {title.trim() && message.trim() && (
                      <button
                        type="button"
                        onClick={() => setPreviewPopupOpen(true)}
                        className="inline-flex items-center gap-1 text-[11px] font-bold text-purple-400 hover:text-purple-300 cursor-pointer pt-0.5 transition-colors"
                      >
                        <Eye className="w-3.5 h-3.5" />
                        <span>Preview how pop-up looks to users</span>
                      </button>
                    )}
                  </div>
                  <input
                    type="checkbox"
                    checked={showPopup}
                    onChange={(e) => setShowPopup(e.target.checked)}
                    className="w-4 h-4 mt-1 rounded-sm accent-purple-500 cursor-pointer shrink-0"
                  />
                </div>

                {/* Outbound Email Dispatch Toggle */}
                <div className="p-3 rounded-xl bg-slate-900 border border-slate-800 flex items-start justify-between gap-3">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-white">Dispatch Outbound Email</span>
                      <span
                        className={`px-2 py-0.5 rounded-full text-[9px] font-bold border uppercase ${
                          kpis.email_status?.is_configured
                            ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30'
                            : 'bg-amber-500/20 text-amber-300 border-amber-500/30'
                        }`}
                      >
                        {kpis.email_status?.is_configured
                          ? `Active (${kpis.email_status.provider})`
                          : 'Console Fallback'}
                      </span>
                    </div>
                    <p className="text-[11px] text-slate-400 leading-relaxed">
                      Sends an email to each resolved recipient with a valid address.
                      {kpis.email_status?.is_configured ? (
                        <> Daily quota: <strong>{kpis.email_status.remaining_today}</strong> remaining of {kpis.email_status.daily_limit}.</>
                      ) : (
                        <> (Console mode active: outputs will print to backend server terminal without sending real emails).</>
                      )}
                    </p>
                  </div>
                  <input
                    type="checkbox"
                    checked={sendEmail}
                    onChange={(e) => setSendEmail(e.target.checked)}
                    className="w-4 h-4 mt-1 rounded-sm accent-emerald-500 cursor-pointer shrink-0"
                  />
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

      {/* Pop-Up Live Preview Modal (Simulating Student/Faculty View) */}
      {previewPopupOpen && (
        <div className="fixed inset-0 z-60 bg-black/85 backdrop-blur-md flex items-center justify-center p-4">
          <div className="w-full max-w-lg bg-slate-900 border border-purple-500/40 rounded-3xl p-6 sm:p-7 shadow-2xl text-slate-100 relative overflow-hidden space-y-4">
            <div className="flex items-start justify-between gap-3">
              <div className="flex items-center gap-3">
                <div className="p-3 rounded-2xl bg-purple-500/10 border border-purple-500/30 text-purple-400">
                  <Sparkles className="w-5 h-5" />
                </div>
                <div>
                  <span className="inline-block px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider bg-purple-500/20 text-purple-300 border border-purple-500/30">
                    Live Preview (User View)
                  </span>
                  <h3 className="text-base font-bold text-white mt-1">{title || 'Sample Title'}</h3>
                </div>
              </div>
              <button
                onClick={() => setPreviewPopupOpen(false)}
                className="p-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-400"
              >
                ✕
              </button>
            </div>
            <p className="text-xs text-slate-300 leading-relaxed whitespace-pre-line bg-slate-950/60 p-4 rounded-2xl border border-slate-800">
              {message || 'Your broadcast message content will appear here...'}
            </p>
            {link && (
              <div className="text-xs text-sky-400 flex items-center gap-1 font-mono">
                <span>Link target:</span> <u>{link}</u>
              </div>
            )}
            <div className="flex justify-end gap-2 pt-2 border-t border-slate-800">
              <button
                type="button"
                onClick={() => setPreviewPopupOpen(false)}
                className="px-4 py-2 rounded-xl bg-purple-600 hover:bg-purple-500 text-white font-bold text-xs cursor-pointer"
              >
                Close Preview
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Email Diagnostics & Test Email Modal */}
      {emailModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="w-full max-w-xl bg-slate-900 border border-slate-800 rounded-3xl p-6 text-slate-100 shadow-2xl space-y-4 max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center gap-3">
                <div className="p-2.5 rounded-2xl bg-sky-500/10 text-sky-400 border border-sky-500/20">
                  <Mail className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-base font-bold text-white">Email Delivery Diagnostics</h3>
                  <p className="text-xs text-slate-400">SMTP configuration status, daily quotas, and test dispatch</p>
                </div>
              </div>
              <button
                onClick={() => setEmailModalOpen(false)}
                className="p-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-400"
              >
                ✕
              </button>
            </div>

            {/* Diagnostics Cards */}
            <div className="grid grid-cols-2 gap-3 text-xs">
              <div className="p-3 bg-slate-950 rounded-2xl border border-slate-800 space-y-1">
                <span className="text-slate-400 text-[11px]">Active Provider</span>
                <p className="font-bold text-white truncate">
                  {kpis.email_status?.provider || (kpis.smtp_configured ? 'SMTP' : 'Console Simulation')}
                </p>
              </div>

              <div className="p-3 bg-slate-950 rounded-2xl border border-slate-800 space-y-1">
                <span className="text-slate-400 text-[11px]">Backend Class</span>
                <p className="font-mono text-[11px] text-slate-300 truncate" title={kpis.email_status?.backend}>
                  {kpis.email_status?.backend ? kpis.email_status.backend.split('.').pop() : 'ConsoleBackend'}
                </p>
              </div>

              <div className="p-3 bg-slate-950 rounded-2xl border border-slate-800 space-y-1">
                <span className="text-slate-400 text-[11px]">Daily Quota</span>
                <p className="font-bold text-emerald-400">
                  {kpis.email_status ? `${kpis.email_status.remaining_today} remaining` : '300 / day'}
                </p>
                <p className="text-[10px] text-slate-500">
                  {kpis.email_status ? `${kpis.email_status.sent_today} sent today` : '0 sent today'}
                </p>
              </div>

              <div className="p-3 bg-slate-950 rounded-2xl border border-slate-800 space-y-1">
                <span className="text-slate-400 text-[11px]">Default Sender (From)</span>
                <p className="font-mono text-[11px] text-slate-300 truncate" title={kpis.email_status?.from_email}>
                  {kpis.email_status?.from_email || 'noreply@examai.local'}
                </p>
              </div>
            </div>

            {/* Test Email Form */}
            <div className="p-4 bg-slate-950/80 border border-slate-800 rounded-2xl space-y-3">
              <p className="font-bold text-slate-200 flex items-center gap-2 text-xs">
                <Send className="w-4 h-4 text-sky-400" /> Send Diagnostic Test Email
              </p>
              <form onSubmit={handleSendTestEmail} className="space-y-3">
                <div>
                  <label className="block text-[11px] text-slate-400 mb-1">Recipient Address *</label>
                  <input
                    type="email"
                    required
                    value={testEmailTo}
                    onChange={(e) => setTestEmailTo(e.target.value)}
                    placeholder="Enter your email e.g. you@example.com"
                    className="w-full px-3.5 py-2 bg-slate-900 border border-slate-800 rounded-xl text-white text-xs placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-sky-500/40"
                  />
                </div>

                <div className="flex items-center justify-between">
                  <p className="text-[10px] text-slate-500">
                    CLI Equivalent: <code>python manage.py test_email --to &lt;email&gt;</code>
                  </p>
                  <button
                    type="submit"
                    disabled={testEmailLoading || !testEmailTo.trim()}
                    className="px-4 py-2 rounded-xl bg-sky-600 hover:bg-sky-500 text-white font-bold text-xs disabled:opacity-40 transition-colors cursor-pointer"
                  >
                    {testEmailLoading ? 'Dispatching...' : 'Send Test'}
                  </button>
                </div>
              </form>

              {testEmailResult && (
                <div
                  className={`p-3 rounded-xl border text-xs ${
                    testEmailResult.status === 'success'
                      ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300'
                      : 'bg-rose-500/10 border-rose-500/30 text-rose-300'
                  }`}
                >
                  <p className="font-bold">{testEmailResult.message}</p>
                  {testEmailResult.data?.is_console && (
                    <p className="text-[11px] text-slate-400 mt-1">
                      Note: Console mode is active. The email body was printed to the terminal running the Django backend.
                    </p>
                  )}
                </div>
              )}
            </div>

            {/* Free Provider Guide Box */}
            <div className="p-3.5 bg-slate-950/40 rounded-2xl border border-slate-800 text-[11px] text-slate-400 space-y-1">
              <p className="font-bold text-slate-300">How to configure free real email delivery:</p>
              <ul className="list-disc list-inside space-y-0.5 text-slate-400">
                <li><strong>Brevo (Recommended):</strong> 300 emails/day free forever. Set <code>EMAIL_HOST=smtp-relay.brevo.com</code> in <code>.env</code>.</li>
                <li><strong>Gmail:</strong> 500 emails/day free. Turn on 2-Step Verification & create an App Password.</li>
                <li><strong>Mailjet:</strong> 200 emails/day free. Set <code>EMAIL_HOST=in-v3.mailjet.com</code> in <code>.env</code>.</li>
                <li>See <code>docs/email-setup.md</code> for the complete setup tutorial.</li>
              </ul>
            </div>

            <div className="flex justify-end pt-2 border-t border-slate-800">
              <button
                onClick={() => setEmailModalOpen(false)}
                className="px-4 py-2 rounded-xl border border-slate-800 text-slate-400 hover:text-white text-xs cursor-pointer"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

    </div>
  );
}

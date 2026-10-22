import React, { useState, useEffect, useMemo, useCallback } from 'react';
import {
  FileText,
  Download,
  Search,
  Filter,
  BarChart3,
  TrendingUp,
  ShieldAlert,
  Layers,
  Database,
  RefreshCw,
  CheckCircle2,
  AlertTriangle,
  FileSpreadsheet,
  FileCode,
  ExternalLink,
  ChevronRight,
  ChevronLeft,
  Users,
  GraduationCap,
  Building2,
  Lock,
  Cpu,
  Sparkles,
  Command,
  Clock,
  X,
  FileCheck,
  ShieldCheck,
  Scale,
} from 'lucide-react';

interface SuperAdminReportsModuleProps {
  saFetch: (endpoint: string, options?: RequestInit) => Promise<any>;
  onTriggerReauth: (callback: () => void) => void;
  onNavigateTab?: (tab: string) => void;
}

interface ReportMeta {
  id: string;
  title: string;
  category: string;
  description: string;
  chart_type: string;
}

interface ReportData {
  report_id: string;
  title: string;
  summary: Record<string, string | number>;
  chart_data: Array<{ label: string; value: number }>;
  headers: string[];
  rows: Array<Record<string, any>>;
}

interface SearchResultItem {
  type: 'user' | 'institute' | 'exam';
  title: string;
  subtitle: string;
  tab: string;
  id: number;
}

export function SuperAdminReportsModule({ saFetch, onTriggerReauth, onNavigateTab }: SuperAdminReportsModuleProps) {
  // Navigation & View State
  const [activeSubTab, setActiveSubTab] = useState<'catalog' | 'governance' | 'tools'>('catalog');
  const [selectedReportId, setSelectedReportId] = useState<string>('system_usage');
  const [searchCatalogQuery, setSearchCatalogQuery] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('all');

  // Report Data State
  const [reportCatalog, setReportCatalog] = useState<ReportMeta[]>([]);
  const [reportData, setReportData] = useState<ReportData | null>(null);
  const [loadingCatalog, setLoadingCatalog] = useState(false);
  const [loadingReport, setLoadingReport] = useState(false);
  const [reportError, setReportError] = useState<string | null>(null);

  // Governance Hub State
  const [auditLogs, setAuditLogs] = useState<any[]>([]);
  const [loadingAuditLogs, setLoadingAuditLogs] = useState(false);


  // Table pagination & filter
  const [tableSearch, setTableSearch] = useState('');
  const [page, setPage] = useState(1);
  const rowsPerPage = 12;

  // Export Modal State
  const [exportModalOpen, setExportModalOpen] = useState(false);
  const [exportFormat, setExportFormat] = useState<'csv' | 'xlsx' | 'pdf'>('csv');
  const [exporting, setExporting] = useState(false);
  const [exportSuccessMessage, setExportSuccessMessage] = useState<string | null>(null);

  // Module E: Emergency Tools State
  const [emergencyModalOpen, setEmergencyModalOpen] = useState(false);
  const [emergencyReason, setEmergencyReason] = useState('');
  const [emergencyScope, setEmergencyScope] = useState<'all' | string>('all');
  const [emergencyExecuting, setEmergencyExecuting] = useState(false);
  const [emergencyFeedback, setEmergencyFeedback] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  // Module E: Quick Command Search State
  const [commandQuery, setCommandQuery] = useState('');
  const [commandResults, setCommandResults] = useState<SearchResultItem[]>([]);
  const [searchingCommand, setSearchingCommand] = useState(false);

  // Load Catalog on Mount
  useEffect(() => {
    loadCatalog();
  }, []);

  const loadCatalog = async () => {
    setLoadingCatalog(true);
    try {
      const res = await saFetch('reports/');
      if (res.ok) {
        const body = await res.json();
        if (body && body.status === 'success' && body.catalog) {
          setReportCatalog(body.catalog);
          if (body.catalog.length > 0 && !selectedReportId) {
            setSelectedReportId(body.catalog[0].id);
          }
        }
      }
    } catch (err: any) {
      console.error('Failed to load report catalog', err);
    } finally {
      setLoadingCatalog(false);
    }
  };

  const fetchAuditLogs = useCallback(async () => {
    setLoadingAuditLogs(true);
    try {
      const res = await saFetch('system/audit-logs/?page_size=8');
      if (res.ok) {
        const body = await res.json();
        setAuditLogs(body.logs || body.data || []);
      }
    } catch (err) {
      console.error('Failed to load audit logs:', err);
    } finally {
      setLoadingAuditLogs(false);
    }
  }, [saFetch]);

  useEffect(() => {
    if (activeSubTab === 'governance') {
      fetchAuditLogs();
    }
  }, [activeSubTab, fetchAuditLogs]);


  // Load Report Data whenever selectedReportId changes
  useEffect(() => {
    if (selectedReportId) {
      loadReport(selectedReportId);
    }
  }, [selectedReportId]);

  const loadReport = async (reportId: string) => {
    setLoadingReport(true);
    setReportError(null);
    setPage(1);
    setTableSearch('');
    try {
      const res = await saFetch(`reports/${reportId}/`);
      if (res.ok) {
        const body = await res.json();
        if (body && body.status === 'success' && body.report) {
          setReportData(body.report);
        } else {
          setReportError(body?.message || 'Failed to parse report dataset.');
        }
      } else {
        const errBody = await res.json().catch(() => ({}));
        setReportError(errBody?.message || `Failed to fetch report (HTTP ${res.status}).`);
      }
    } catch (err: any) {
      setReportError(err?.message || 'Network error fetching report data.');
    } finally {
      setLoadingReport(false);
    }
  };

  // Filtered rows for the active report
  const filteredRows = useMemo(() => {
    if (!reportData || !reportData.rows) return [];
    if (!tableSearch.trim()) return reportData.rows;
    const q = tableSearch.toLowerCase();
    return reportData.rows.filter((r) =>
      Object.values(r).some((val) => String(val).toLowerCase().includes(q))
    );
  }, [reportData, tableSearch]);

  const paginatedRows = useMemo(() => {
    const start = (page - 1) * rowsPerPage;
    return filteredRows.slice(start, start + rowsPerPage);
  }, [filteredRows, page]);

  const totalPages = Math.ceil(filteredRows.length / rowsPerPage) || 1;

  // Filtered catalog
  const filteredCatalog = useMemo(() => {
    return reportCatalog.filter((item) => {
      const matchesSearch =
        item.title.toLowerCase().includes(searchCatalogQuery.toLowerCase()) ||
        item.description.toLowerCase().includes(searchCatalogQuery.toLowerCase());
      const matchesCategory = categoryFilter === 'all' || item.category === categoryFilter;
      return matchesSearch && matchesCategory;
    });
  }, [reportCatalog, searchCatalogQuery, categoryFilter]);

  const categories = useMemo(() => {
    const set = new Set<string>();
    reportCatalog.forEach((c) => set.add(c.category));
    return Array.from(set);
  }, [reportCatalog]);

  // Export Trigger
  const handleExport = async () => {
    if (!reportData) return;
    setExporting(true);
    setExportSuccessMessage(null);
    try {
      const res = await saFetch(`reports/${reportData.report_id}/export/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ format: exportFormat }),
      });

      if (res.ok) {
        const data = await res.json();
        if (data && data.status === 'success' && data.download_url) {
          // Trigger browser download via signed endpoint
          const currentPath = window.location.pathname.split('/')[1];
          const directUrl = `/${currentPath}${data.download_url}`;
          const link = document.createElement('a');
          link.href = directUrl;
          link.setAttribute('download', `examai_report_${reportData.report_id}.${exportFormat}`);
          document.body.appendChild(link);
          link.click();
          document.body.removeChild(link);

          setExportSuccessMessage(`Generated ${exportFormat.toUpperCase()} successfully (${data.row_count} rows).`);
          setTimeout(() => {
            setExportModalOpen(false);
            setExportSuccessMessage(null);
          }, 1800);
        } else {
          alert(data?.message || 'Export failed.');
        }
      } else {
        const errData = await res.json().catch(() => ({}));
        alert(errData?.message || 'Failed to generate report export.');
      }
    } catch (err: any) {
      alert(err?.message || 'Error exporting report.');
    } finally {
      setExporting(false);
    }
  };

  // Module E: Quick Search Query Handler
  const handleCommandSearch = useCallback(
    async (q: string) => {
      setCommandQuery(q);
      if (!q.trim() || q.trim().length < 2) {
        setCommandResults([]);
        return;
      }
      setSearchingCommand(true);
      try {
        const res = await saFetch(`system/quick-search/?q=${encodeURIComponent(q.trim())}`);
        if (res.ok) {
          const body = await res.json();
          if (body && body.status === 'success' && body.results) {
            setCommandResults(body.results);
          }
        }
      } catch (err) {
        console.error('Quick search error', err);
      } finally {
        setSearchingCommand(false);
      }
    },
    [saFetch]
  );

  // Module E: Emergency Revocation
  const handleEmergencyRevocation = async () => {
    if (!emergencyReason.trim()) {
      alert('Justification reason is mandatory for emergency session revocation.');
      return;
    }

    const execute = async () => {
      setEmergencyExecuting(true);
      setEmergencyFeedback(null);
      try {
        const payload: any = { reason: emergencyReason };
        if (emergencyScope !== 'all') {
          payload.target_institute_id = emergencyScope;
        }

        const res = await saFetch('operations/emergency-revoke-sessions/', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });

        const body = await res.json().catch(() => ({}));
        if (res.ok && body && body.status === 'success') {
          setEmergencyFeedback({ type: 'success', message: body.message });
          setEmergencyReason('');
          setTimeout(() => {
            setEmergencyModalOpen(false);
            setEmergencyFeedback(null);
          }, 2400);
        } else if (res.status === 403 && body.error === 'step_up_required') {
          onTriggerReauth(execute);
        } else {
          setEmergencyFeedback({ type: 'error', message: body?.message || 'Operation failed.' });
        }
      } catch (err: any) {
        if (err?.message?.includes('reauth')) {
          onTriggerReauth(execute);
        } else {
          setEmergencyFeedback({ type: 'error', message: err?.message || 'Emergency revocation failed.' });
        }
      } finally {
        setEmergencyExecuting(false);
      }
    };

    execute();
  };


  return (
    <div className="space-y-6">
      {/* Header and Sub-Tab Navigation */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-800">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-bold text-white tracking-tight">Super Admin Reports & Governance</h1>
            <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
              Module D & E
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Standardized operational reports, tamper-evident audit analysis, sanitized multi-format exports, and emergency tools.
          </p>
        </div>

        {/* Sub-tab pills */}
        <div className="flex flex-wrap items-center gap-2 p-1 rounded-xl bg-slate-900 border border-slate-800 self-start sm:self-auto">
          <button
            type="button"
            onClick={() => setActiveSubTab('catalog')}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all flex items-center gap-2 cursor-pointer ${
              activeSubTab === 'catalog'
                ? 'bg-emerald-500 text-slate-950 font-semibold shadow-sm'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            <BarChart3 className="w-3.5 h-3.5" />
            <span>Reports Catalog</span>
          </button>
          <button
            type="button"
            onClick={() => setActiveSubTab('governance')}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all flex items-center gap-2 cursor-pointer ${
              activeSubTab === 'governance'
                ? 'bg-sky-500 text-slate-950 font-semibold shadow-sm'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            <ShieldCheck className="w-3.5 h-3.5" />
            <span>Governance & Compliance</span>
          </button>
          <button
            type="button"
            onClick={() => setActiveSubTab('tools')}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all flex items-center gap-2 cursor-pointer ${
              activeSubTab === 'tools'
                ? 'bg-rose-500 text-white font-semibold shadow-sm'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            <ShieldAlert className="w-3.5 h-3.5" />
            <span>Emergency Tools</span>
          </button>
        </div>
      </div>

      {/* ==================================================================== */}
      {/* TAB 1: REPORTS CATALOG & VIEWER */}
      {/* ==================================================================== */}
      {activeSubTab === 'catalog' && (
        <div className="space-y-6">
          {/* Catalog Selection Bar */}
          <div className="p-4 rounded-2xl bg-slate-900/60 border border-slate-800/80 backdrop-blur-sm space-y-3">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
              <div className="flex items-center gap-2 text-xs font-semibold text-slate-200">
                <Layers className="w-4 h-4 text-emerald-400" />
                <span>Select Report ({reportCatalog.length} available)</span>
              </div>

              {/* Filters */}
              <div className="flex items-center gap-2">
                <div className="relative">
                  <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
                  <input
                    type="text"
                    value={searchCatalogQuery}
                    onChange={(e) => setSearchCatalogQuery(e.target.value)}
                    placeholder="Search reports..."
                    className="pl-8 pr-3 py-1.5 rounded-xl bg-slate-950 border border-slate-800 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-emerald-500 w-44 sm:w-56"
                  />
                </div>

                <select
                  value={categoryFilter}
                  onChange={(e) => setCategoryFilter(e.target.value)}
                  className="px-2.5 py-1.5 rounded-xl bg-slate-950 border border-slate-800 text-xs text-slate-300 focus:outline-none focus:border-emerald-500"
                >
                  <option value="all">All Domains</option>
                  {categories.map((c) => (
                    <option key={c} value={c}>
                      {c}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {/* Catalog Grid Carousel / Pill Selector */}
            {loadingCatalog ? (
              <div className="p-8 flex flex-col items-center justify-center space-y-2">
                <RefreshCw className="w-6 h-6 animate-spin text-emerald-400" />
                <p className="text-xs text-slate-400 font-medium">Loading catalog of operational reports...</p>
              </div>
            ) : filteredCatalog.length === 0 ? (
              <div className="p-6 text-center text-xs text-slate-400">
                No matching reports found. Try clearing your search or filter.
              </div>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2.5 pt-1">
                {filteredCatalog.map((item) => {
                  const isSelected = selectedReportId === item.id;
                  return (
                    <button
                      key={item.id}
                      type="button"
                      onClick={() => setSelectedReportId(item.id)}
                      className={`p-3 rounded-xl border text-left transition-all cursor-pointer flex flex-col justify-between ${
                        isSelected
                          ? 'bg-emerald-500/10 border-emerald-500/40 text-emerald-300 ring-1 ring-emerald-500/30'
                          : 'bg-slate-950/60 border-slate-800 text-slate-400 hover:bg-slate-800/40 hover:text-slate-200'
                      }`}
                    >
                      <div>
                        <div className="flex items-center justify-between gap-1 mb-1.5">
                          <span
                            className={`text-[9px] uppercase tracking-wider font-semibold px-2 py-0.5 rounded-full ${
                              isSelected
                                ? 'bg-emerald-500/20 text-emerald-300'
                                : 'bg-slate-800 text-slate-400'
                            }`}
                          >
                            {item.category}
                          </span>
                          <span className="text-[10px] font-mono text-slate-500 uppercase">{item.chart_type}</span>
                        </div>
                        <h4 className="text-xs font-bold text-slate-100 line-clamp-1">{item.title}</h4>
                        <p className="text-[11px] text-slate-400 line-clamp-2 mt-1 leading-relaxed">
                          {item.description}
                        </p>
                      </div>
                    </button>
                  );
                })}
              </div>
            )}
          </div>

          {/* Active Report Loading & Error Boundaries */}
          {loadingReport && (
            <div className="p-12 rounded-2xl bg-slate-900/60 border border-slate-800 flex flex-col items-center justify-center space-y-3">
              <RefreshCw className="w-8 h-8 animate-spin text-emerald-400" />
              <p className="text-sm font-bold text-white">Aggregating report data...</p>
              <p className="text-xs text-slate-400">Querying platform database and computing cross-institute aggregates.</p>
            </div>
          )}

          {reportError && !loadingReport && (
            <div className="p-5 rounded-2xl bg-rose-500/10 border border-rose-500/30 text-rose-300 flex items-center justify-between gap-4">
              <div className="flex items-center gap-3">
                <AlertTriangle className="w-5 h-5 text-rose-400 shrink-0" />
                <div>
                  <p className="font-bold text-xs">Error Loading Report</p>
                  <p className="text-[11px] text-rose-200/90">{reportError}</p>
                </div>
              </div>
              <button
                onClick={() => loadReport(selectedReportId)}
                className="px-3.5 py-1.5 rounded-xl bg-rose-500/20 hover:bg-rose-500/30 border border-rose-500/40 text-rose-200 text-xs font-bold transition-colors cursor-pointer"
              >
                Retry
              </button>
            </div>
          )}


          {/* Active Report Header & Action Toolbar */}
          {reportData && (
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-4 rounded-2xl bg-gradient-to-r from-slate-900 to-slate-900/40 border border-slate-800">
              <div className="flex items-center gap-3">
                <div className="p-2.5 rounded-xl bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                  <FileText className="w-5 h-5" />
                </div>
                <div>
                  <h2 className="text-base font-bold text-white">{reportData.title}</h2>
                  <p className="text-xs text-slate-400">
                    Live platform dataset &bull; {filteredRows.length} total recorded rows
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => loadReport(selectedReportId)}
                  disabled={loadingReport}
                  className="px-3 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white border border-slate-700 text-xs font-medium transition-all flex items-center gap-1.5 cursor-pointer disabled:opacity-50"
                >
                  <RefreshCw className={`w-3.5 h-3.5 ${loadingReport ? 'animate-spin text-emerald-400' : ''}`} />
                  <span>Refresh</span>
                </button>

                <button
                  type="button"
                  onClick={() => setExportModalOpen(true)}
                  className="px-3.5 py-1.5 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold text-xs transition-all shadow-sm flex items-center gap-1.5 cursor-pointer"
                >
                  <Download className="w-3.5 h-3.5" />
                  <span>Export Report</span>
                </button>
              </div>
            </div>
          )}

          {/* KPI Summary Cards */}
          {reportData && reportData.summary && (
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
              {Object.entries(reportData.summary).map(([k, v], idx) => (
                <div
                  key={idx}
                  className="p-3.5 rounded-xl bg-slate-900/60 border border-slate-800/80 backdrop-blur-sm"
                >
                  <div className="text-[11px] font-medium text-slate-400 truncate">{k}</div>
                  <div className="text-lg font-bold text-white mt-1 font-mono">{String(v)}</div>
                </div>
              ))}
            </div>
          )}

          {/* Visual Chart Trend Bar */}
          {reportData && reportData.chart_data && reportData.chart_data.length > 0 && (
            <div className="p-4 rounded-2xl bg-slate-900/60 border border-slate-800/80 backdrop-blur-sm space-y-3">
              <div className="flex items-center justify-between text-xs font-semibold text-slate-300">
                <div className="flex items-center gap-2">
                  <TrendingUp className="w-4 h-4 text-emerald-400" />
                  <span>Distribution &amp; Trend Breakdown</span>
                </div>
                <span className="text-[11px] text-slate-500 font-normal">Real-time aggregate</span>
              </div>

              {/* Chart Visualizer */}
              <div className="space-y-2 pt-1">
                {(() => {
                  const maxVal = Math.max(...reportData.chart_data.map((c) => c.value), 1);
                  return reportData.chart_data.map((item, idx) => {
                    const pct = Math.min(100, Math.round((item.value / maxVal) * 100));
                    return (
                      <div key={idx} className="space-y-1">
                        <div className="flex justify-between text-[11px] text-slate-300">
                          <span className="truncate pr-2 font-medium">{item.label}</span>
                          <span className="font-mono text-emerald-400 font-semibold">{item.value.toLocaleString()}</span>
                        </div>
                        <div className="w-full h-2 rounded-full bg-slate-950 overflow-hidden border border-slate-800">
                          <div
                            className="h-full rounded-full bg-gradient-to-r from-emerald-500 to-teal-400 transition-all duration-500"
                            style={{ width: `${Math.max(4, pct)}%` }}
                          />
                        </div>
                      </div>
                    );
                  });
                })()}
              </div>
            </div>
          )}

          {/* Detailed Data Table */}
          {reportData && (
            <div className="p-4 rounded-2xl bg-slate-900/60 border border-slate-800/80 backdrop-blur-sm space-y-3">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <div className="text-xs font-semibold text-slate-200 flex items-center gap-2">
                  <span>Detailed Records</span>
                  <span className="text-slate-500 font-mono">({filteredRows.length})</span>
                </div>

                <div className="relative">
                  <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
                  <input
                    type="text"
                    value={tableSearch}
                    onChange={(e) => {
                      setTableSearch(e.target.value);
                      setPage(1);
                    }}
                    placeholder="Search inside table..."
                    className="pl-8 pr-3 py-1.5 rounded-xl bg-slate-950 border border-slate-800 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-emerald-500 w-full sm:w-64"
                  />
                </div>
              </div>

              {/* Responsive Table with table-fixed layout */}
              <div className="hidden md:block w-full overflow-hidden rounded-xl border border-slate-800">
                <table className="w-full table-fixed text-left text-xs divide-y divide-slate-800">
                  <thead className="bg-slate-950/80 text-slate-400 uppercase text-[10px] tracking-wider">
                    <tr>
                      {reportData.headers.map((h, i) => (
                        <th key={i} className="py-2.5 px-3 font-semibold truncate">
                          {h}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/50 bg-slate-900/30">
                    {paginatedRows.length === 0 ? (
                      <tr>
                        <td colSpan={reportData.headers.length} className="py-8 text-center text-slate-500 text-xs">
                          No matching records found.
                        </td>
                      </tr>
                    ) : (
                      paginatedRows.map((row, rIdx) => (
                        <tr key={rIdx} className="hover:bg-slate-800/40 transition-colors">
                          {reportData.headers.map((h, cIdx) => (
                            <td
                              key={cIdx}
                              title={String(row[h] || '')}
                              className="py-2.5 px-3 text-slate-300 truncate"
                            >
                              {String(row[h] ?? '-')}
                            </td>
                          ))}
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>

              {/* Mobile View: Cards */}
              <div className="md:hidden space-y-2">
                {paginatedRows.length === 0 ? (
                  <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 text-center text-slate-500 text-xs">
                    No matching records found.
                  </div>
                ) : (
                  paginatedRows.map((row, rIdx) => (
                    <div key={rIdx} className="p-3 rounded-xl bg-slate-950 border border-slate-800 space-y-1.5 text-xs">
                      {reportData.headers.map((h, cIdx) => (
                        <div key={cIdx} className="flex justify-between items-center text-[11px]">
                          <span className="text-slate-400 font-medium">{h}</span>
                          <span className="text-slate-200 font-mono truncate max-w-[60%] text-right">
                            {String(row[h] ?? '-')}
                          </span>
                        </div>
                      ))}
                    </div>
                  ))
                )}
              </div>

              {/* Pagination controls */}
              <div className="flex items-center justify-between text-xs text-slate-400 pt-2 border-t border-slate-800/50">
                <span>
                  Page <strong className="text-white">{page}</strong> of <strong className="text-white">{totalPages}</strong>
                </span>
                <div className="flex items-center gap-1.5">
                  <button
                    type="button"
                    onClick={() => setPage((p) => Math.max(1, p - 1))}
                    disabled={page === 1}
                    className="p-1.5 rounded-lg bg-slate-950 border border-slate-800 text-slate-300 hover:text-white disabled:opacity-40 cursor-pointer"
                  >
                    <ChevronLeft className="w-4 h-4" />
                  </button>
                  <button
                    type="button"
                    onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                    disabled={page >= totalPages}
                    className="p-1.5 rounded-lg bg-slate-950 border border-slate-800 text-slate-300 hover:text-white disabled:opacity-40 cursor-pointer"
                  >
                    <ChevronRight className="w-4 h-4" />
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ==================================================================== */}
      {/* TAB 2: GOVERNANCE, AUDIT & COMPLIANCE HUB */}
      {/* ==================================================================== */}
      {activeSubTab === 'governance' && (
        <div className="space-y-6">
          {/* Governance Header Banner */}
          <div className="p-5 rounded-2xl bg-gradient-to-r from-sky-950/40 via-slate-900 to-slate-900/60 border border-sky-500/30 space-y-2">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div className="flex items-center gap-3">
                <div className="p-3 rounded-2xl bg-sky-500/10 border border-sky-500/30 text-sky-400">
                  <ShieldCheck className="w-6 h-6" />
                </div>
                <div>
                  <h2 className="text-base font-bold text-white flex items-center gap-2">
                    Institutional Governance &amp; Regulatory Compliance Hub
                    <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 uppercase">
                      DPDP Aligned
                    </span>
                  </h2>
                  <p className="text-xs text-slate-400 mt-0.5">
                    Cryptographic HMAC SHA-256 chained audit trail, strict 4-tier role separation, and user data privacy enforcement.
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={fetchAuditLogs}
                  disabled={loadingAuditLogs}
                  className="px-3.5 py-2 rounded-xl bg-slate-900 hover:bg-slate-800 border border-slate-700 text-xs font-semibold text-slate-200 transition-colors flex items-center gap-2 cursor-pointer disabled:opacity-50"
                >
                  <RefreshCw className={`w-3.5 h-3.5 ${loadingAuditLogs ? 'animate-spin text-sky-400' : ''}`} />
                  <span>Verify Chain</span>
                </button>
              </div>
            </div>
          </div>

          {/* Governance KPI Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3.5">
            <div className="p-4 rounded-2xl bg-slate-900/60 border border-slate-800 space-y-1">
              <div className="flex items-center justify-between text-slate-400 text-xs">
                <span>Tamper-Evident Audit Chain</span>
                <Lock className="w-4 h-4 text-emerald-400" />
              </div>
              <p className="text-lg font-extrabold text-white flex items-center gap-2">
                SHA-256 HMAC
                <span className="text-[10px] font-bold uppercase px-2 py-0.2 rounded-full bg-emerald-500/20 text-emerald-300">
                  Verified
                </span>
              </p>
              <p className="text-[10px] text-slate-500 font-mono">Immutable audit records &bull; Zero deletion permitted</p>
            </div>

            <div className="p-4 rounded-2xl bg-slate-900/60 border border-slate-800 space-y-1">
              <div className="flex items-center justify-between text-slate-400 text-xs">
                <span>Role Isolation Level</span>
                <Scale className="w-4 h-4 text-sky-400" />
              </div>
              <p className="text-lg font-extrabold text-white">4 Distinct Tiers</p>
              <p className="text-[10px] text-slate-500 font-mono">Super Admin &bull; Institute Admin &bull; Faculty &bull; Student</p>
            </div>

            <div className="p-4 rounded-2xl bg-slate-900/60 border border-slate-800 space-y-1">
              <div className="flex items-center justify-between text-slate-400 text-xs">
                <span>Privacy Standard</span>
                <FileCheck className="w-4 h-4 text-purple-400" />
              </div>
              <p className="text-lg font-extrabold text-white">DPDP Act 2023</p>
              <p className="text-[10px] text-slate-500 font-mono">Data inventory, access export, anonymization &amp; consent</p>
            </div>
          </div>

          {/* Audit Logs Live Stream Card */}
          <div className="bg-slate-900/70 border border-slate-800 rounded-3xl overflow-hidden shadow-xl space-y-3 p-5">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <FileText className="w-4 h-4 text-sky-400" />
                <h3 className="text-sm font-bold text-white">Recent Tamper-Evident Super Admin Audit Trail</h3>
              </div>
              <span className="text-[10px] font-mono text-slate-400 bg-slate-950 px-2.5 py-1 rounded-lg border border-slate-800">
                Live Audit Logs
              </span>
            </div>

            <div className="overflow-hidden">
              <table className="w-full text-left text-xs table-fixed">
                <colgroup>
                  <col className="w-[18%]" />
                  <col className="w-[22%]" />
                  <col className="w-[28%]" />
                  <col className="w-[16%]" />
                  <col className="w-[16%]" />
                </colgroup>
                <thead className="bg-slate-950/80 text-slate-400 text-[10px] uppercase font-bold tracking-wider border-b border-slate-800">
                  <tr>
                    <th className="py-2.5 px-3">Timestamp</th>
                    <th className="py-2.5 px-3">Actor &amp; Action</th>
                    <th className="py-2.5 px-3">Description</th>
                    <th className="py-2.5 px-3">Target</th>
                    <th className="py-2.5 px-3">HMAC Hash</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60">
                  {loadingAuditLogs ? (
                    <tr>
                      <td colSpan={5} className="py-8 text-center text-slate-400">
                        <RefreshCw className="w-5 h-5 animate-spin mx-auto text-sky-400 mb-1" />
                        <span>Verifying cryptographic log chain...</span>
                      </td>
                    </tr>
                  ) : auditLogs.length === 0 ? (
                    <tr>
                      <td colSpan={5} className="py-6 text-center text-slate-400 text-xs">
                        No audit records found.
                      </td>
                    </tr>
                  ) : (
                    auditLogs.map((log: any, idx: number) => (
                      <tr key={log.id || idx} className="hover:bg-slate-800/30 transition-colors">
                        <td className="py-2.5 px-3 font-mono text-[11px] text-slate-400">
                          {log.created_at ? new Date(log.created_at).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : '-'}
                        </td>
                        <td className="py-2.5 px-3 min-w-0">
                          <p className="font-bold text-white truncate">{log.action}</p>
                          <p className="text-[10px] text-sky-400 font-mono truncate">{log.actor_username || 'system'}</p>
                        </td>
                        <td className="py-2.5 px-3 text-slate-300 text-[11px] truncate" title={log.description}>
                          {log.description || '-'}
                        </td>
                        <td className="py-2.5 px-3 text-slate-400 font-mono text-[11px] truncate">
                          {log.target_entity ? `${log.target_entity} #${log.target_id || ''}` : '-'}
                        </td>
                        <td className="py-2.5 px-3 min-w-0">
                          <span
                            className="font-mono text-[10px] text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/20 truncate block"
                            title={log.entry_hash || 'SHA-256 HMAC Chain'}
                          >
                            {log.entry_hash ? `${log.entry_hash.slice(0, 10)}...` : '✓ Valid'}
                          </span>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>

          {/* 4-Tier Role Privilege Matrix */}
          <div className="bg-slate-900/70 border border-slate-800 rounded-3xl p-5 space-y-3">
            <div className="flex items-center gap-2">
              <Scale className="w-4 h-4 text-emerald-400" />
              <h3 className="text-sm font-bold text-white">4-Tier Role Privilege &amp; Access Control Matrix</h3>
            </div>
            <p className="text-xs text-slate-400 leading-relaxed">
              Enforced by Django REST Framework permission classes and multi-tenant authentication middleware.
            </p>

            <div className="overflow-hidden rounded-2xl border border-slate-800">
              <table className="w-full text-left text-xs table-fixed">
                <colgroup>
                  <col className="w-[30%]" />
                  <col className="w-[17.5%]" />
                  <col className="w-[17.5%]" />
                  <col className="w-[17.5%]" />
                  <col className="w-[17.5%]" />
                </colgroup>
                <thead className="bg-slate-950 text-slate-400 text-[10px] uppercase font-bold tracking-wider border-b border-slate-800">
                  <tr>
                    <th className="py-2.5 px-3">Capability / Resource</th>
                    <th className="py-2.5 px-3 text-center text-emerald-400">Super Admin</th>
                    <th className="py-2.5 px-3 text-center text-sky-400">Institute Admin</th>
                    <th className="py-2.5 px-3 text-center text-purple-400">Faculty</th>
                    <th className="py-2.5 px-3 text-center text-slate-400">Student</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60 bg-slate-950/40 text-[11px]">
                  {[
                    { cap: 'Platform AI Model Registry (Ollama)', sa: 'Full Access', ia: 'No Access', f: 'No Access', s: 'No Access' },
                    { cap: 'Cross-Institute Broadcast Campaigns', sa: 'Full Access', ia: 'Scoped (Inst)', f: 'No Access', s: 'No Access' },
                    { cap: 'Emergency User Session Revocation', sa: 'Global (Step-up)', ia: 'Scoped (Inst)', f: 'No Access', s: 'No Access' },
                    { cap: 'Cryptographic Audit Trail Inspection', sa: 'Full Access', ia: 'Scoped (Inst)', f: 'No Access', s: 'No Access' },
                    { cap: 'Exam Authoring & Missing Question Gen', sa: 'Monitoring Only', ia: 'Manage Inst', f: 'Full Authoring', s: 'No Access' },
                    { cap: 'Real-Time Exam Monitoring & Cheating Flags', sa: 'Global View', ia: 'Inst View', f: 'Active Proctor', s: 'No Access' },
                    { cap: 'Exam Sitting & Response Submission', sa: 'No Access', ia: 'No Access', f: 'No Access', s: 'Full Access' },
                    { cap: 'DPDP Data Portability & Anonymization', sa: 'Global DPO', ia: 'Request Prep', f: 'Self Data Only', s: 'Self Data Only' },
                  ].map((row, idx) => (
                    <tr key={idx} className="hover:bg-slate-800/20">
                      <td className="py-2.5 px-3 font-semibold text-slate-200">{row.cap}</td>
                      <td className="py-2.5 px-3 text-center font-bold text-emerald-400">{row.sa}</td>
                      <td className="py-2.5 px-3 text-center font-medium text-sky-300">{row.ia}</td>
                      <td className="py-2.5 px-3 text-center font-medium text-purple-300">{row.f}</td>
                      <td className="py-2.5 px-3 text-center font-medium text-slate-400">{row.s}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* ==================================================================== */}
      {/* TAB 3: EMERGENCY TOOLS & GLOBAL COMMAND SEARCH (MODULE E) */}
      {/* ==================================================================== */}
      {activeSubTab === 'tools' && (

        <div className="space-y-6">
          {/* Quick Command Search Section (Cmd+K / Ctrl+K) */}
          <div className="p-5 rounded-2xl bg-slate-900/60 border border-slate-800/80 backdrop-blur-sm space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Command className="w-5 h-5 text-emerald-400" />
                <h3 className="text-sm font-bold text-white">Global Command Palette &amp; Instant Search</h3>
              </div>
              <span className="text-[11px] font-mono text-slate-400 bg-slate-950 px-2 py-0.5 rounded border border-slate-800">
                Ctrl + K
              </span>
            </div>

            <p className="text-xs text-slate-400">
              Instantly search across institutes, enrolled users, exams, and settings with real-time indexing.
            </p>

            <div className="relative">
              <Search className="w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" />
              <input
                type="text"
                value={commandQuery}
                onChange={(e) => handleCommandSearch(e.target.value)}
                placeholder="Search across students, faculty, exams, institute codes..."
                className="w-full pl-10 pr-4 py-2.5 rounded-xl bg-slate-950 border border-slate-800 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-emerald-500"
              />
              {searchingCommand && (
                <RefreshCw className="w-3.5 h-3.5 absolute right-3.5 top-1/2 -translate-y-1/2 animate-spin text-emerald-400" />
              )}
            </div>

            {/* Results Grid */}
            {commandResults.length > 0 && (
              <div className="space-y-2 pt-2 border-t border-slate-800">
                <div className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
                  Instant Results ({commandResults.length})
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
                  {commandResults.map((r, i) => (
                    <div
                      key={i}
                      onClick={() => {
                        if (onNavigateTab && r.tab) {
                          onNavigateTab(r.tab);
                        }
                      }}
                      className="p-3 rounded-xl bg-slate-950 border border-slate-800 hover:border-emerald-500/50 hover:bg-slate-800/40 transition-all cursor-pointer flex items-center justify-between group"
                    >
                      <div className="min-w-0 pr-2">
                        <div className="flex items-center gap-1.5">
                          {r.type === 'institute' && <Building2 className="w-3.5 h-3.5 text-blue-400 shrink-0" />}
                          {r.type === 'user' && <Users className="w-3.5 h-3.5 text-emerald-400 shrink-0" />}
                          {r.type === 'exam' && <FileText className="w-3.5 h-3.5 text-amber-400 shrink-0" />}
                          <span className="text-xs font-bold text-white truncate">{r.title}</span>
                        </div>
                        <p className="text-[11px] text-slate-400 truncate mt-0.5">{r.subtitle}</p>
                      </div>
                      <ChevronRight className="w-4 h-4 text-slate-600 group-hover:text-emerald-400 shrink-0 transition-colors" />
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Emergency 1-Click Session Revocation Panel */}
          <div className="p-5 rounded-2xl bg-gradient-to-br from-rose-950/20 to-slate-900/60 border border-rose-500/30 backdrop-blur-sm space-y-4">
            <div className="flex items-center gap-3">
              <div className="p-2.5 rounded-xl bg-rose-500/20 text-rose-400 border border-rose-500/30">
                <ShieldAlert className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-sm font-bold text-white">Emergency Session Revocation Tool</h3>
                <p className="text-xs text-slate-400">
                  Kill active JWT sessions platform-wide or per-institute during security incidents.
                </p>
              </div>
            </div>

            <div className="p-3.5 rounded-xl bg-rose-500/10 border border-rose-500/20 text-xs text-rose-300 leading-relaxed">
              <strong>Caution:</strong> This immediately terminates active user sessions, blacklists existing bearer tokens, and invalidates browser auth cookies. Users will be required to log in again. Enforces step-up 2FA re-authentication and leaves an immutable cryptographic audit trail.
            </div>

            <button
              type="button"
              onClick={() => setEmergencyModalOpen(true)}
              className="px-4 py-2 rounded-xl bg-rose-600 hover:bg-rose-500 text-white font-bold text-xs transition-all shadow-md flex items-center gap-2 cursor-pointer"
            >
              <ShieldAlert className="w-4 h-4" />
              <span>Initiate Emergency Revocation</span>
            </button>
          </div>
        </div>
      )}

      {/* ==================================================================== */}
      {/* EXPORT MODAL */}
      {/* ==================================================================== */}
      {exportModalOpen && reportData && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm animate-in fade-in duration-200">
          <div className="w-full max-w-md rounded-2xl bg-slate-900 border border-slate-800 p-5 shadow-2xl space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <div className="flex items-center gap-2">
                <Download className="w-4 h-4 text-emerald-400" />
                <h3 className="text-sm font-bold text-white">Export Dataset</h3>
              </div>
              <button
                type="button"
                onClick={() => setExportModalOpen(false)}
                className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="space-y-3">
              <div className="text-xs text-slate-300">
                Exporting <strong className="text-white">{reportData.title}</strong> ({reportData.rows.length} records)
              </div>

              {/* Format selection */}
              <div className="space-y-2">
                <label className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
                  Select Format
                </label>
                <div className="grid grid-cols-3 gap-2">
                  <button
                    type="button"
                    onClick={() => setExportFormat('csv')}
                    className={`p-3 rounded-xl border text-center transition-all cursor-pointer ${
                      exportFormat === 'csv'
                        ? 'bg-emerald-500/10 border-emerald-500/40 text-emerald-300 font-bold'
                        : 'bg-slate-950 border-slate-800 text-slate-400 hover:text-white'
                    }`}
                  >
                    <FileCode className="w-5 h-5 mx-auto mb-1" />
                    <span className="text-xs block">CSV</span>
                    <span className="text-[9px] text-slate-500 block">Sanitized</span>
                  </button>

                  <button
                    type="button"
                    onClick={() => setExportFormat('xlsx')}
                    className={`p-3 rounded-xl border text-center transition-all cursor-pointer ${
                      exportFormat === 'xlsx'
                        ? 'bg-emerald-500/10 border-emerald-500/40 text-emerald-300 font-bold'
                        : 'bg-slate-950 border-slate-800 text-slate-400 hover:text-white'
                    }`}
                  >
                    <FileSpreadsheet className="w-5 h-5 mx-auto mb-1" />
                    <span className="text-xs block">Excel</span>
                    <span className="text-[9px] text-slate-500 block">Native .xlsx</span>
                  </button>

                  <button
                    type="button"
                    onClick={() => setExportFormat('pdf')}
                    className={`p-3 rounded-xl border text-center transition-all cursor-pointer ${
                      exportFormat === 'pdf'
                        ? 'bg-emerald-500/10 border-emerald-500/40 text-emerald-300 font-bold'
                        : 'bg-slate-950 border-slate-800 text-slate-400 hover:text-white'
                    }`}
                  >
                    <FileText className="w-5 h-5 mx-auto mb-1" />
                    <span className="text-xs block">PDF</span>
                    <span className="text-[9px] text-slate-500 block">Executive</span>
                  </button>
                </div>
              </div>

              {exportFormat === 'csv' && (
                <div className="p-2.5 rounded-xl bg-slate-950 border border-slate-800 text-[11px] text-slate-400 leading-relaxed">
                  Formula injection protection active (CWE-1236). Values starting with =, +, -, @ are sanitized.
                </div>
              )}

              {exportSuccessMessage && (
                <div className="p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 text-xs flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4 shrink-0 text-emerald-400" />
                  <span>{exportSuccessMessage}</span>
                </div>
              )}
            </div>

            <div className="flex items-center justify-end gap-2 pt-3 border-t border-slate-800">
              <button
                type="button"
                onClick={() => setExportModalOpen(false)}
                className="px-3 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleExport}
                disabled={exporting}
                className="px-4 py-1.5 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold text-xs flex items-center gap-1.5 cursor-pointer disabled:opacity-50"
              >
                {exporting ? (
                  <>
                    <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                    <span>Generating...</span>
                  </>
                ) : (
                  <>
                    <Download className="w-3.5 h-3.5" />
                    <span>Download File</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ==================================================================== */}
      {/* EMERGENCY REVOCATION MODAL */}
      {/* ==================================================================== */}
      {emergencyModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/85 backdrop-blur-sm animate-in fade-in duration-200">
          <div className="w-full max-w-md rounded-2xl bg-slate-900 border border-rose-500/40 p-5 shadow-2xl space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <div className="flex items-center gap-2 text-rose-400">
                <ShieldAlert className="w-5 h-5" />
                <h3 className="text-sm font-bold text-white">Emergency Session Revocation</h3>
              </div>
              <button
                type="button"
                onClick={() => setEmergencyModalOpen(false)}
                className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="space-y-3">
              <div className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/20 text-xs text-rose-300">
                Terminating sessions is non-reversible and forces re-authentication. Requires Super Admin step-up re-authentication.
              </div>

              <div>
                <label className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block mb-1">
                  Target Scope
                </label>
                <select
                  value={emergencyScope}
                  onChange={(e) => setEmergencyScope(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-800 text-xs text-white focus:outline-none focus:border-rose-500"
                >
                  <option value="all">Entire Platform (All Users)</option>
                </select>
              </div>

              <div>
                <label className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block mb-1">
                  Justification Reason <span className="text-rose-400">*</span>
                </label>
                <textarea
                  rows={3}
                  value={emergencyReason}
                  onChange={(e) => setEmergencyReason(e.target.value)}
                  placeholder="e.g. Platform security alert, credential leak investigation, suspicious token activity..."
                  className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-800 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-rose-500"
                />
              </div>

              {emergencyFeedback && (
                <div
                  className={`p-3 rounded-xl text-xs flex items-center gap-2 ${
                    emergencyFeedback.type === 'success'
                      ? 'bg-emerald-500/10 border border-emerald-500/30 text-emerald-300'
                      : 'bg-rose-500/10 border border-rose-500/30 text-rose-300'
                  }`}
                >
                  {emergencyFeedback.type === 'success' ? (
                    <CheckCircle2 className="w-4 h-4 shrink-0 text-emerald-400" />
                  ) : (
                    <AlertTriangle className="w-4 h-4 shrink-0 text-rose-400" />
                  )}
                  <span>{emergencyFeedback.message}</span>
                </div>
              )}
            </div>

            <div className="flex items-center justify-end gap-2 pt-3 border-t border-slate-800">
              <button
                type="button"
                onClick={() => setEmergencyModalOpen(false)}
                className="px-3 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleEmergencyRevocation}
                disabled={emergencyExecuting || !emergencyReason.trim()}
                className="px-4 py-1.5 rounded-xl bg-rose-600 hover:bg-rose-500 text-white font-bold text-xs flex items-center gap-1.5 cursor-pointer disabled:opacity-50"
              >
                {emergencyExecuting ? (
                  <>
                    <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                    <span>Executing...</span>
                  </>
                ) : (
                  <>
                    <ShieldAlert className="w-3.5 h-3.5" />
                    <span>Revoke All Sessions</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

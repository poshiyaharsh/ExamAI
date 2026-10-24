import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  Sparkles,
  Cpu,
  HardDrive,
  Download,
  Trash2,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  RefreshCw,
  Play,
  Star,
  Check,
  Search,
  ExternalLink,
  Layers,
  Activity,
  Zap,
  Info,
  Clock,
} from 'lucide-react';

interface AIModelItem {
  id: number;
  name: string;
  display_name: string;
  family: string;
  parameter_size: string;
  quantization_level: string;
  size_bytes: number;
  size_mb: number;
  context_window: number;
  is_enabled: boolean;
  is_default: boolean;
  status: 'ready' | 'pulling' | 'failed' | 'offline';
  is_active_in_vram: boolean;
  pull_progress_percent: number;
  pull_status_message: string;
  last_tested_at: string | null;
  last_test_latency_ms: number | null;
  last_test_success: boolean | null;
  last_test_error: string;
  notes: string;
  created_at: string;
}

interface CatalogModelItem {
  name: string;
  display_name: string;
  parameter_size: string;
  family: string;
  size_approx: string;
  min_ram_gb: number;
  description: string;
}

interface SuperAdminAIModuleProps {
  saFetch: (endpoint: string, options?: RequestInit) => Promise<Response>;
  onTriggerReauth: (cb?: () => void) => void;
}

export function SuperAdminAIModule({ saFetch, onTriggerReauth }: SuperAdminAIModuleProps) {
  const [models, setModels] = useState<AIModelItem[]>([]);
  const [catalog, setCatalog] = useState<CatalogModelItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [ollamaOnline, setOllamaOnline] = useState(true);
  const [ollamaUrl, setOllamaUrl] = useState('http://127.0.0.1:11434');
  const [runningCount, setRunningCount] = useState(0);
  const [totalDiskGb, setTotalDiskGb] = useState(0);
  const [capacityAlerts, setCapacityAlerts] = useState<any[]>([]);

  // Pull Custom Model Modal
  const [pullModalOpen, setPullModalOpen] = useState(false);
  const [pullModelTag, setPullModelTag] = useState('');
  const [pullSubmitting, setPullSubmitting] = useState(false);
  const [pullError, setPullError] = useState('');

  // Benchmark / Test States
  const [testingModelId, setTestingModelId] = useState<number | null>(null);
  const [testResultModal, setTestResultModal] = useState<{ open: boolean; data?: any }>({ open: false });

  // Delete Confirm Modal
  const [deleteModal, setDeleteModal] = useState<{ open: boolean; model?: AIModelItem }>({ open: false });
  const [deleteLoading, setDeleteLoading] = useState(false);
  const [deleteError, setDeleteError] = useState('');

  // Polling interval ref for active pulls
  const pollingRef = useRef<number | null>(null);

  const fetchAIStatus = useCallback(async (isSilent = false) => {
    try {
      if (!isSilent) setRefreshing(true);
      const res = await saFetch('ai/models/');
      if (res.ok) {
        const data = await res.json();
        setModels(data.models || []);
        setCatalog(data.catalog || []);
        setOllamaOnline(Boolean(data.ollama_online));
        setOllamaUrl(data.ollama_base_url || 'http://127.0.0.1:11434');
        setRunningCount(data.running_models_count || 0);
        setTotalDiskGb(data.total_disk_gb || 0);
        setCapacityAlerts(data.capacity_alerts || []);
      }
    } catch (err) {
      console.error('Failed to fetch AI models status:', err);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [saFetch]);

  useEffect(() => {
    fetchAIStatus();
  }, [fetchAIStatus]);

  // Dynamic live polling while any model is in 'pulling' status
  useEffect(() => {
    const hasPulling = models.some((m) => m.status === 'pulling');
    if (hasPulling) {
      pollingRef.current = window.setInterval(() => {
        fetchAIStatus(true);
      }, 2500);
    } else if (pollingRef.current) {
      clearInterval(pollingRef.current);
      pollingRef.current = null;
    }
    return () => {
      if (pollingRef.current) {
        clearInterval(pollingRef.current);
      }
    };
  }, [models, fetchAIStatus]);

  // Handle Enable/Disable Toggle
  const handleToggle = async (model: AIModelItem) => {
    const nextState = !model.is_enabled;
    try {
      const res = await saFetch(`ai/models/${model.id}/toggle/`, {
        method: 'POST',
        body: JSON.stringify({ is_enabled: nextState }),
      });
      if (res.ok) {
        fetchAIStatus(true);
      } else {
        const d = await res.json();
        alert(d.message || 'Failed to toggle model.');
      }
    } catch {
      alert('Network error while toggling model.');
    }
  };

  // Handle Set Default
  const handleSetDefault = async (model: AIModelItem) => {
    if (model.is_default) return;
    try {
      const res = await saFetch(`ai/models/${model.id}/default/`, { method: 'POST' });
      if (res.ok) {
        fetchAIStatus(true);
      } else {
        const d = await res.json();
        alert(d.message || 'Failed to set default model.');
      }
    } catch {
      alert('Network error while setting default model.');
    }
  };

  // Handle Benchmark Test
  const handleRunTest = async (model: AIModelItem) => {
    setTestingModelId(model.id);
    try {
      const res = await saFetch(`ai/models/${model.id}/test/`, { method: 'POST' });
      const d = await res.json();
      setTestResultModal({ open: true, data: d });
      fetchAIStatus(true);
    } catch (err: any) {
      alert('Test request failed: ' + err.message);
    } finally {
      setTestingModelId(null);
    }
  };

  // Handle Pull Request
  const handleInitiatePull = async (modelName: string) => {
    setPullError('');
    setPullSubmitting(true);
    try {
      const res = await saFetch('ai/models/', {
        method: 'POST',
        body: JSON.stringify({ name: modelName.trim() }),
      });
      const data = await res.json();
      if (res.ok || res.status === 202) {
        setPullModalOpen(false);
        setPullModelTag('');
        fetchAIStatus(true);
      } else {
        setPullError(data.message || 'Download initiation failed.');
      }
    } catch (err: any) {
      setPullError(err.message || 'Network error.');
    } finally {
      setPullSubmitting(false);
    }
  };

  // Handle Delete with Step-Up Re-Authentication
  const handleDeleteConfirm = () => {
    if (!deleteModal.model) return;
    const model = deleteModal.model;

    onTriggerReauth(async () => {
      setDeleteLoading(true);
      setDeleteError('');
      try {
        const res = await saFetch(`ai/models/${model.id}/delete/`, { method: 'POST' });
        const d = await res.json();
        if (res.ok) {
          setDeleteModal({ open: false });
          fetchAIStatus(true);
        } else {
          setDeleteError(d.message || 'Delete operation rejected.');
        }
      } catch (err: any) {
        setDeleteError(err.message || 'Network error.');
      } finally {
        setDeleteLoading(false);
      }
    });
  };

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center p-16 text-slate-400 space-y-3">
        <RefreshCw className="w-8 h-8 animate-spin text-emerald-400" />
        <p className="text-xs font-mono">Connecting to Ollama & AI Model Registry...</p>
      </div>
    );
  }

  const enabledCount = models.filter((m) => m.is_enabled).length;

  return (
    <div className="space-y-6 min-w-0 max-w-full">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800/80 pb-5">
        <div>
          <div className="flex items-center gap-2.5">
            <h1 className="text-xl sm:text-2xl font-bold text-white tracking-tight">AI & Inference Operations</h1>
            <span
              className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider ${
                ollamaOnline
                  ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                  : 'bg-rose-500/10 text-rose-400 border border-rose-500/20 animate-pulse'
              }`}
            >
              <span className={`w-1.5 h-1.5 rounded-full ${ollamaOnline ? 'bg-emerald-400' : 'bg-rose-400'}`} />
              {ollamaOnline ? 'Ollama Online' : 'Ollama Unreachable'}
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Dynamic local Ollama model lifecycle • Zero-code model activation • Live generation routing
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => fetchAIStatus(false)}
            disabled={refreshing}
            className="inline-flex items-center gap-2 px-3.5 py-2 rounded-xl bg-slate-900 hover:bg-slate-800 border border-slate-700/80 text-xs font-semibold text-slate-200 disabled:opacity-50 cursor-pointer transition-all"
            title="Synchronize registry with Ollama runtime"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? 'animate-spin text-emerald-400' : ''}`} />
            <span>Sync Ollama</span>
          </button>
          <button
            onClick={() => {
              setPullModelTag('');
              setPullError('');
              setPullModalOpen(true);
            }}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold shadow-md shadow-emerald-950/40 cursor-pointer transition-all"
          >
            <Download className="w-3.5 h-3.5" />
            <span>Pull New Model</span>
          </button>
        </div>
      </div>

      {/* Capacity & System Alerts */}
      {capacityAlerts.map((alert, idx) => (
        <div
          key={idx}
          className={`p-4 rounded-2xl border flex items-start gap-3.5 text-xs ${
            alert.severity === 'critical'
              ? 'bg-rose-500/10 border-rose-500/30 text-rose-300'
              : 'bg-amber-500/10 border-amber-500/30 text-amber-300'
          }`}
        >
          <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
          <div className="min-w-0 flex-1">
            <p className="font-bold">{alert.title}</p>
            <p className="text-[11px] opacity-90 mt-0.5">{alert.message}</p>
          </div>
        </div>
      ))}

      {/* Operational Metric KPI Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3.5">
        <div className="p-4 rounded-2xl bg-slate-900/60 border border-slate-800 space-y-1">
          <div className="flex items-center justify-between text-slate-400 text-xs">
            <span>Installed Models</span>
            <Sparkles className="w-4 h-4 text-emerald-400" />
          </div>
          <p className="text-xl font-extrabold text-white">{models.length}</p>
          <p className="text-[10px] text-slate-400 font-mono">{enabledCount} enabled for exams</p>
        </div>

        <div className="p-4 rounded-2xl bg-slate-900/60 border border-slate-800 space-y-1">
          <div className="flex items-center justify-between text-slate-400 text-xs">
            <span>Running in VRAM/RAM</span>
            <Activity className="w-4 h-4 text-sky-400" />
          </div>
          <p className="text-xl font-extrabold text-white">{runningCount}</p>
          <p className="text-[10px] text-slate-400 font-mono">Warm model instances</p>
        </div>

        <div className="p-4 rounded-2xl bg-slate-900/60 border border-slate-800 space-y-1">
          <div className="flex items-center justify-between text-slate-400 text-xs">
            <span>Disk Space Used</span>
            <HardDrive className="w-4 h-4 text-purple-400" />
          </div>
          <p className="text-xl font-extrabold text-white">{totalDiskGb} GB</p>
          <p className="text-[10px] text-slate-400 font-mono">Ollama model layers</p>
        </div>

        <div className="p-4 rounded-2xl bg-slate-900/60 border border-slate-800 space-y-1">
          <div className="flex items-center justify-between text-slate-400 text-xs">
            <span>Endpoint Base</span>
            <Cpu className="w-4 h-4 text-amber-400" />
          </div>
          <p className="text-xs font-mono font-bold text-slate-200 truncate" title={ollamaUrl}>
            {ollamaUrl}
          </p>
          <p className="text-[10px] text-emerald-400 font-mono">HTTP JSON streaming</p>
        </div>
      </div>

      {/* Installed Models Section */}
      <div className="bg-slate-900/70 border border-slate-800 rounded-3xl overflow-hidden shadow-xl">
        <div className="p-4 sm:p-5 border-b border-slate-800/80 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <h2 className="text-sm sm:text-base font-bold text-white flex items-center gap-2">
              <Layers className="w-4 h-4 text-emerald-400" /> Platform AI Model Registry ({models.length})
            </h2>
            <p className="text-[11px] text-slate-400 mt-0.5">
              Enabled models are immediately usable by faculty paper generators without server redeploys.
            </p>
          </div>
          <div className="text-right">
            <span className="text-[11px] text-slate-400 font-mono">
              Primary Default:{' '}
              <strong className="text-emerald-400">
                {models.find((m) => m.is_default)?.name || 'None Selected'}
              </strong>
            </span>
          </div>
        </div>

        {/* Desktop Fixed Table (Zero Horizontal Scrollbar) */}
        <div className="hidden md:block overflow-hidden">
          <table className="w-full text-left text-xs table-fixed">
            <colgroup>
              <col className="w-[30%]" />
              <col className="w-[18%]" />
              <col className="w-[14%]" />
              <col className="w-[14%]" />
              <col className="w-[12%]" />
              <col className="w-[12%]" />
            </colgroup>
            <thead className="bg-slate-950/80 text-slate-400 text-[10px] uppercase font-bold tracking-wider border-b border-slate-800">
              <tr>
                <th className="py-3 px-4">Model & Family</th>
                <th className="py-3 px-3">Specs / Context</th>
                <th className="py-3 px-3">Disk Size</th>
                <th className="py-3 px-3">Status</th>
                <th className="py-3 px-3">Default</th>
                <th className="py-3 px-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {models.map((m) => (
                <tr key={m.id} className="hover:bg-slate-800/30 transition-colors">
                  {/* Model Name */}
                  <td className="py-3.5 px-4 min-w-0">
                    <div className="flex items-center gap-2">
                      {m.is_default && (
                        <span title="System Default Model" className="inline-flex shrink-0">
                          <Star className="w-3.5 h-3.5 text-amber-400 fill-amber-400" />
                        </span>
                      )}
                      <p className="font-bold text-white text-xs truncate" title={m.name}>
                        {m.name}
                      </p>
                    </div>
                    <div className="flex items-center gap-2 mt-0.5 text-[11px] text-slate-400 font-mono">
                      <span>{m.family ? m.family.toUpperCase() : 'GGUF'}</span>
                      {m.is_active_in_vram && (
                        <span className="inline-flex items-center gap-1 text-[10px] text-sky-400 bg-sky-500/10 px-1.5 py-0.2 rounded-sm border border-sky-500/20">
                          <Activity className="w-2.5 h-2.5" /> In VRAM
                        </span>
                      )}
                    </div>
                  </td>

                  {/* Specs */}
                  <td className="py-3.5 px-3 min-w-0 text-slate-300">
                    <p className="font-semibold text-white truncate">
                      {m.parameter_size || 'Unknown'} • {m.quantization_level || 'Q4'}
                    </p>
                    <p className="text-[11px] text-slate-400 font-mono truncate">
                      Ctx: {m.context_window?.toLocaleString()} tokens
                    </p>
                  </td>

                  {/* Disk Size */}
                  <td className="py-3.5 px-3 min-w-0 font-mono text-slate-300">
                    <p className="font-bold text-slate-200">{m.size_mb ? `${m.size_mb} MB` : 'Estimating'}</p>
                    <p className="text-[10px] text-slate-500">
                      {m.size_mb ? `${(m.size_mb / 1024).toFixed(2)} GB` : '-'}
                    </p>
                  </td>

                  {/* Status & Progress */}
                  <td className="py-3.5 px-3 min-w-0">
                    {m.status === 'pulling' ? (
                      <div className="space-y-1">
                        <span className="inline-flex items-center gap-1 text-[10px] font-bold text-amber-400 animate-pulse">
                          <RefreshCw className="w-3 h-3 animate-spin" /> Pulling ({m.pull_progress_percent}%)
                        </span>
                        <div className="w-full bg-slate-800 rounded-full h-1.5 overflow-hidden">
                          <div
                            className="bg-amber-400 h-full rounded-full transition-all duration-300"
                            style={{ width: `${m.pull_progress_percent}%` }}
                          />
                        </div>
                      </div>
                    ) : m.status === 'ready' ? (
                      <span className="inline-flex items-center gap-1 text-[11px] font-medium text-emerald-400">
                        <CheckCircle2 className="w-3.5 h-3.5 shrink-0" /> Ready
                      </span>
                    ) : m.status === 'failed' ? (
                      <span className="inline-flex items-center gap-1 text-[11px] font-medium text-rose-400" title={m.pull_status_message}>
                        <XCircle className="w-3.5 h-3.5 shrink-0" /> Failed
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 text-[11px] font-medium text-slate-400">
                        Offline
                      </span>
                    )}
                  </td>

                  {/* Default Radio / Button */}
                  <td className="py-3.5 px-3 min-w-0">
                    {m.is_default ? (
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-500/10 text-amber-400 border border-amber-500/30">
                        <Star className="w-3 h-3 fill-amber-400" /> Default
                      </span>
                    ) : (
                      <button
                        onClick={() => handleSetDefault(m)}
                        disabled={!m.is_enabled || m.status !== 'ready'}
                        className="text-[11px] text-slate-400 hover:text-amber-400 disabled:opacity-30 cursor-pointer transition-colors"
                      >
                        Make Default
                      </button>
                    )}
                  </td>

                  {/* Actions */}
                  <td className="py-3.5 px-4 text-right min-w-0">
                    <div className="inline-flex items-center gap-1.5 justify-end">
                      {/* Enable/Disable Toggle */}
                      <button
                        onClick={() => handleToggle(m)}
                        disabled={m.status !== 'ready'}
                        title={m.is_enabled ? 'Disable Model' : 'Enable Model'}
                        className={`px-2 py-1 rounded-lg text-[10px] font-bold uppercase tracking-wider border cursor-pointer transition-all ${
                          m.is_enabled
                            ? 'bg-emerald-500/15 border-emerald-500/30 text-emerald-300 hover:bg-emerald-500/25'
                            : 'bg-slate-800/80 border-slate-700 text-slate-400 hover:text-slate-200'
                        }`}
                      >
                        {m.is_enabled ? 'Active' : 'Disabled'}
                      </button>

                      {/* Benchmark Ping */}
                      <button
                        onClick={() => handleRunTest(m)}
                        disabled={testingModelId === m.id || m.status !== 'ready'}
                        title="Run Benchmark Connectivity Test"
                        className="p-1.5 rounded-lg border border-slate-700 text-slate-300 hover:text-sky-400 hover:bg-slate-800 disabled:opacity-40 cursor-pointer transition-colors"
                      >
                        <Play className={`w-3.5 h-3.5 ${testingModelId === m.id ? 'animate-spin' : ''}`} />
                      </button>

                      {/* Delete */}
                      <button
                        onClick={() => setDeleteModal({ open: true, model: m })}
                        disabled={m.is_default || m.status === 'pulling'}
                        title={m.is_default ? 'Cannot delete default model' : 'Delete Model from Disk'}
                        className="p-1.5 rounded-lg border border-slate-800 text-slate-500 hover:text-rose-400 hover:border-rose-500/30 hover:bg-rose-500/10 disabled:opacity-20 cursor-pointer transition-colors"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
              {models.length === 0 && (
                <tr>
                  <td colSpan={6} className="py-12 text-center text-slate-500">
                    No models registered in Ollama. Pull a model from the catalog below.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {/* Mobile Responsive Cards */}
        <div className="md:hidden divide-y divide-slate-800/80">
          {models.map((m) => (
            <div key={m.id} className="p-4 space-y-3">
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <div className="flex items-center gap-1.5">
                    {m.is_default && <Star className="w-3.5 h-3.5 text-amber-400 fill-amber-400 shrink-0" />}
                    <p className="font-bold text-white text-xs truncate">{m.name}</p>
                  </div>
                  <p className="text-[11px] text-slate-400 font-mono mt-0.5">
                    {m.family || 'GGUF'} • {m.parameter_size || '3B'} • {m.size_mb} MB
                  </p>
                </div>
                <button
                  onClick={() => handleToggle(m)}
                  className={`px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider border ${
                    m.is_enabled
                      ? 'bg-emerald-500/15 border-emerald-500/30 text-emerald-300'
                      : 'bg-slate-800 border-slate-700 text-slate-400'
                  }`}
                >
                  {m.is_enabled ? 'Active' : 'Disabled'}
                </button>
              </div>

              {m.status === 'pulling' && (
                <div className="space-y-1">
                  <div className="flex justify-between text-[10px] text-amber-300">
                    <span>Pulling Layer</span>
                    <span>{m.pull_progress_percent}%</span>
                  </div>
                  <div className="w-full bg-slate-800 rounded-full h-1.5 overflow-hidden">
                    <div className="bg-amber-400 h-full rounded-full" style={{ width: `${m.pull_progress_percent}%` }} />
                  </div>
                </div>
              )}

              <div className="flex items-center justify-between pt-2 border-t border-slate-800/60 text-xs">
                {m.is_default ? (
                  <span className="text-amber-400 font-bold text-[11px]">Primary Default</span>
                ) : (
                  <button
                    onClick={() => handleSetDefault(m)}
                    className="text-[11px] text-slate-400 hover:text-amber-400"
                  >
                    Set as Default
                  </button>
                )}

                <div className="flex items-center gap-2">
                  <button
                    onClick={() => handleRunTest(m)}
                    className="p-1.5 rounded-lg border border-slate-700 text-slate-300 hover:text-sky-400"
                  >
                    <Play className="w-3.5 h-3.5" />
                  </button>
                  <button
                    onClick={() => setDeleteModal({ open: true, model: m })}
                    disabled={m.is_default}
                    className="p-1.5 rounded-lg border border-slate-800 text-slate-500 hover:text-rose-400 disabled:opacity-20"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Free Online Models Catalog (Official Ollama Library) */}
      <div className="space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
          <div>
            <h2 className="text-sm sm:text-base font-bold text-white flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-amber-400" /> Free Open-Source Models Library
            </h2>
            <p className="text-xs text-slate-400 mt-0.5">
              1-click installation from the official Ollama registry directly to your local hardware.
            </p>
          </div>
          <a
            href="https://ollama.com/library"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1.5 text-xs text-emerald-400 hover:underline"
          >
            <span>Explore all 200+ models on Ollama.com</span>
            <ExternalLink className="w-3 h-3" />
          </a>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {catalog.map((cat) => {
            const isInstalled = models.some((m) => m.name === cat.name || m.name.startsWith(cat.name));
            const isPulling = models.some((m) => m.name === cat.name && m.status === 'pulling');

            return (
              <div
                key={cat.name}
                className="p-5 rounded-2xl bg-slate-900/60 border border-slate-800 hover:border-slate-700 transition-all flex flex-col justify-between space-y-3"
              >
                <div>
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <h3 className="font-bold text-white text-sm">{cat.display_name}</h3>
                      <p className="text-[11px] font-mono text-emerald-400 mt-0.5">tag: {cat.name}</p>
                    </div>
                    <span className="px-2 py-0.5 rounded-md bg-slate-800 text-[10px] font-mono text-slate-300 border border-slate-700">
                      {cat.parameter_size}
                    </span>
                  </div>

                  <p className="text-xs text-slate-400 mt-2 line-clamp-2 leading-relaxed">{cat.description}</p>
                </div>

                <div className="pt-3 border-t border-slate-800/80 flex items-center justify-between text-xs">
                  <div className="text-[11px] text-slate-400 font-mono">
                    <span>{cat.size_approx}</span> • <span>≥{cat.min_ram_gb}GB RAM</span>
                  </div>

                  {isPulling ? (
                    <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-amber-500/10 text-amber-400 border border-amber-500/30 text-xs font-semibold animate-pulse">
                      <RefreshCw className="w-3 h-3 animate-spin" /> Pulling...
                    </span>
                  ) : isInstalled ? (
                    <span className="inline-flex items-center gap-1 px-3 py-1.5 rounded-xl bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 text-xs font-bold">
                      <Check className="w-3.5 h-3.5" /> Installed
                    </span>
                  ) : (
                    <button
                      onClick={() => handleInitiatePull(cat.name)}
                      disabled={pullSubmitting}
                      className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl bg-slate-800 hover:bg-emerald-600 text-slate-200 hover:text-white border border-slate-700 text-xs font-bold transition-all cursor-pointer"
                    >
                      <Download className="w-3 h-3" />
                      <span>Pull Model</span>
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Pull Custom Model Modal */}
      {pullModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="w-full max-w-md bg-slate-900 border border-slate-800 rounded-3xl p-6 text-slate-100 shadow-2xl space-y-4">
            <div className="flex items-center gap-3">
              <div className="p-2.5 rounded-2xl bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                <Download className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-base font-bold text-white">Pull Ollama Model</h3>
                <p className="text-xs text-slate-400">Download any free open model from the Ollama library</p>
              </div>
            </div>

            {pullError && (
              <div className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs">
                {pullError}
              </div>
            )}

            <form
              onSubmit={(e) => {
                e.preventDefault();
                if (pullModelTag.trim()) handleInitiatePull(pullModelTag);
              }}
              className="space-y-3.5 text-xs"
            >
              <div>
                <label className="block text-slate-300 font-semibold mb-1.5">Model Tag *</label>
                <input
                  type="text"
                  required
                  value={pullModelTag}
                  onChange={(e) => setPullModelTag(e.target.value)}
                  placeholder="e.g. deepseek-r1:1.5b, llama3.2:1b, or mistral:latest"
                  className="w-full px-3.5 py-2.5 bg-slate-950 border border-slate-800 rounded-xl text-white placeholder-slate-500 font-mono text-xs focus:outline-none focus:ring-2 focus:ring-emerald-500/40"
                />
                <p className="text-[11px] text-slate-500 mt-1">
                  Format: <code>&lt;model-name&gt;:&lt;tag&gt;</code> (defaults to <code>:latest</code> if tag omitted)
                </p>
              </div>

              <div className="p-3 rounded-xl bg-slate-950 border border-slate-800 text-[11px] text-slate-400 space-y-1">
                <p className="font-semibold text-slate-300 flex items-center gap-1">
                  <Info className="w-3.5 h-3.5 text-emerald-400" /> Background Execution
                </p>
                <p>
                  The model layers will download in the background via Ollama's daemon. You can track progress in real-time on this console.
                </p>
              </div>

              <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-800">
                <button
                  type="button"
                  onClick={() => setPullModalOpen(false)}
                  className="px-4 py-2 rounded-xl border border-slate-800 text-slate-400 hover:text-white cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={pullSubmitting || !pullModelTag.trim()}
                  className="px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-bold disabled:opacity-40 cursor-pointer"
                >
                  {pullSubmitting ? 'Starting...' : 'Start Download'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Benchmark Test Result Modal */}
      {testResultModal.open && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="w-full max-w-sm bg-slate-900 border border-slate-800 rounded-3xl p-6 text-slate-100 shadow-2xl space-y-4">
            <div className="flex items-center gap-3">
              <div
                className={`p-2.5 rounded-2xl border ${
                  testResultModal.data?.status === 'success'
                    ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                    : 'bg-rose-500/10 text-rose-400 border-rose-500/20'
                }`}
              >
                <Zap className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-base font-bold text-white">Model Connectivity Benchmark</h3>
                <p className="text-xs text-slate-400 font-mono">
                  {testResultModal.data?.result?.model_name || 'Ollama Benchmark'}
                </p>
              </div>
            </div>

            <div className="p-4 rounded-2xl bg-slate-950 border border-slate-800 space-y-2.5 text-xs">
              <div className="flex justify-between items-center">
                <span className="text-slate-400">Health Status:</span>
                <span
                  className={`font-bold ${
                    testResultModal.data?.result?.success ? 'text-emerald-400' : 'text-rose-400'
                  }`}
                >
                  {testResultModal.data?.result?.success ? 'OPERATIONAL' : 'FAILED'}
                </span>
              </div>
              <div className="flex justify-between items-center font-mono">
                <span className="text-slate-400">Round-Trip Latency:</span>
                <span className="text-white font-bold">{testResultModal.data?.result?.latency_ms} ms</span>
              </div>
              {testResultModal.data?.result?.response_text && (
                <div className="pt-2 border-t border-slate-900">
                  <p className="text-[11px] text-slate-400">Inference Response:</p>
                  <p className="text-emerald-300 font-mono text-[11px] bg-slate-900 p-2 rounded-lg mt-1">
                    "{testResultModal.data?.result?.response_text}"
                  </p>
                </div>
              )}
              {testResultModal.data?.result?.error && (
                <div className="pt-2 border-t border-slate-900">
                  <p className="text-[11px] text-rose-400">Error:</p>
                  <p className="text-rose-300 font-mono text-[10px] break-all">{testResultModal.data?.result?.error}</p>
                </div>
              )}
            </div>

            <button
              onClick={() => setTestResultModal({ open: false })}
              className="w-full py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-white font-semibold text-xs cursor-pointer"
            >
              Dismiss
            </button>
          </div>
        </div>
      )}

      {/* Delete Model Confirmation Modal (Requires Step-Up Reauth) */}
      {deleteModal.open && deleteModal.model && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="w-full max-w-sm bg-slate-900 border border-slate-800 rounded-3xl p-6 text-slate-100 shadow-2xl space-y-4 text-xs">
            <div className="flex items-center gap-3">
              <div className="p-2.5 rounded-2xl bg-rose-500/10 text-rose-400 border border-rose-500/20">
                <Trash2 className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-base font-bold text-white">Delete AI Model</h3>
                <p className="text-slate-400 text-[11px]">Step-up credential verification required</p>
              </div>
            </div>

            {deleteError && (
              <div className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs">
                {deleteError}
              </div>
            )}

            <p className="text-slate-300 leading-relaxed">
              Are you sure you want to delete <strong className="text-white font-mono">{deleteModal.model.name}</strong>?
              This will free up <strong>{deleteModal.model.size_mb} MB</strong> from disk and permanently remove it from
              Ollama.
            </p>

            <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-800">
              <button
                type="button"
                onClick={() => setDeleteModal({ open: false })}
                className="px-4 py-2 rounded-xl border border-slate-800 text-slate-400 hover:text-white cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleDeleteConfirm}
                disabled={deleteLoading}
                className="px-4 py-2 rounded-xl bg-rose-600 hover:bg-rose-500 text-white font-bold cursor-pointer transition-colors"
              >
                {deleteLoading ? 'Deleting...' : 'Authorize & Delete'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

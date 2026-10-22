import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  ShieldAlert,
  ShieldCheck,
  Server,
  Database,
  Cpu,
  HardDrive,
  Users,
  Building2,
  GraduationCap,
  BookOpen,
  FileText,
  AlertTriangle,
  Lock,
  Unlock,
  KeyRound,
  RefreshCw,
  LogOut,
  Eye,
  MoreHorizontal,
  Download,
  Trash2,
  CheckCircle2,
  XCircle,
  Clock,
  Search,
  Filter,
  Plus,
  ArrowRightLeft,
  Copy,
  Check,
  ChevronLeft,
  ChevronRight,
  Sparkles,
} from 'lucide-react';
import { SuperAdminUsersModule } from './superadmin/SuperAdminUsersModule';

interface SuperAdminUser {
  username: string;
  email: string;
  is_totp_enrolled: boolean;
  last_login_at: string | null;
  last_login_ip: string | null;
  is_reauth_valid: boolean;
  remaining_recovery_codes: number;
}

export function SuperAdminGateway() {
  const { secretSlug } = useParams<{ secretSlug: string }>();
  const navigate = useNavigate();

  // Obscurity safety: If slug is missing or less than 16 chars, hide portal completely
  if (!secretSlug || secretSlug.length < 16) {
    return (
      <div className="min-h-screen bg-slate-50 flex flex-col items-center justify-center p-6 text-center">
        <h1 className="text-4xl font-extrabold text-slate-800 tracking-tight mb-2">404</h1>
        <p className="text-slate-500 text-sm">The requested page could not be found.</p>
      </div>
    );
  }

  return <SuperAdminConsoleRoot secretSlug={secretSlug} />;
}

function SuperAdminConsoleRoot({ secretSlug }: { secretSlug: string }) {
  const [token, setToken] = useState<string | null>(() => sessionStorage.getItem(`sa_token_${secretSlug}`));
  const [user, setUser] = useState<SuperAdminUser | null>(null);
  const [loading, setLoading] = useState(true);

  // Authenticated fetch wrapper for superadmin API calls
  const saFetch = useCallback(
    async (endpoint: string, options: RequestInit = {}) => {
      const cleanEndpoint = endpoint.startsWith('/') ? endpoint.slice(1) : endpoint;
      const backendBase =
        (import.meta as { env?: { VITE_API_BASE_URL?: string } }).env?.VITE_API_BASE_URL ||
        (typeof window !== 'undefined' && window.location.hostname
          ? `${window.location.protocol}//${window.location.hostname}:8000`
          : 'http://127.0.0.1:8000');
      const url = `${backendBase}/${secretSlug}/api/${cleanEndpoint}`;
      const headers = new Headers(options.headers || {});
      if (token) {
        headers.set('Authorization', `Bearer ${token}`);
      }
      headers.set('Content-Type', 'application/json');

      const response = await fetch(url, { ...options, headers });
      if (response.status === 404) {
        throw new Error('Endpoint not found');
      }
      return response;
    },
    [secretSlug, token]
  );

  const fetchCurrentUser = useCallback(async () => {
    if (!token) {
      setLoading(false);
      return;
    }
    try {
      const res = await saFetch('auth/me/');
      if (res.ok) {
        const data = await res.json();
        setUser(data.user);
      } else {
        sessionStorage.removeItem(`sa_token_${secretSlug}`);
        setToken(null);
        setUser(null);
      }
    } catch {
      sessionStorage.removeItem(`sa_token_${secretSlug}`);
      setToken(null);
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, [token, saFetch, secretSlug]);

  useEffect(() => {
    fetchCurrentUser();
  }, [fetchCurrentUser]);

  const handleLoginSuccess = (newToken: string, newUser: SuperAdminUser) => {
    sessionStorage.setItem(`sa_token_${secretSlug}`, newToken);
    setToken(newToken);
    setUser(newUser);
  };

  const handleLogout = async () => {
    try {
      await saFetch('auth/logout/', { method: 'POST' });
    } catch {}
    sessionStorage.removeItem(`sa_token_${secretSlug}`);
    setToken(null);
    setUser(null);
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-900 flex flex-col items-center justify-center p-6 text-white space-y-4">
        <div className="w-10 h-10 border-4 border-emerald-500/30 border-t-emerald-500 rounded-full animate-spin" />
        <p className="text-xs font-mono text-slate-400 tracking-wider uppercase">Validating Platform Credentials...</p>
      </div>
    );
  }

  if (!token || !user) {
    return <SuperAdminLogin secretSlug={secretSlug} onLoginSuccess={handleLoginSuccess} saFetch={saFetch} />;
  }

  return (
    <SuperAdminDashboardLayout
      secretSlug={secretSlug}
      user={user}
      onLogout={handleLogout}
      saFetch={saFetch}
      onRefreshUser={fetchCurrentUser}
    />
  );
}

// ==============================================================================
// LOGIN & 2FA ENROLLMENT
// ==============================================================================

function SuperAdminLogin({
  secretSlug,
  onLoginSuccess,
  saFetch,
}: {
  secretSlug: string;
  onLoginSuccess: (token: string, user: SuperAdminUser) => void;
  saFetch: (endpoint: string, options?: RequestInit) => Promise<Response>;
}) {
  const [username, setUsername] = useState('harshposhiya');
  const [password, setPassword] = useState('');
  const [totpCode, setTotpCode] = useState('');
  const [recoveryCode, setRecoveryCode] = useState('');
  const [isRecoveryMode, setIsRecoveryMode] = useState(false);

  // 2FA Enrollment Mode
  const [enrollmentData, setEnrollmentData] = useState<{
    totp_secret: string;
    totp_uri: string;
    temp_token: string;
  } | null>(null);
  const [enrollmentConfirmCode, setEnrollmentConfirmCode] = useState('');

  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [copiedKey, setCopiedKey] = useState(false);

  const handlePrimaryLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const payload: Record<string, string> = { username, password };
      if (isRecoveryMode && recoveryCode) {
        payload.recovery_code = recoveryCode.trim();
      } else if (totpCode) {
        payload.totp_code = totpCode.trim();
      }

      const res = await saFetch('auth/login/', {
        method: 'POST',
        body: JSON.stringify(payload),
      });

      const data = await res.json();
      if (res.status === 423) {
        setError(data.message || 'Account is temporarily locked.');
      } else if (data.status === 'enrollment_required') {
        setEnrollmentData(data);
      } else if (data.status === '2fa_required') {
        // Prompt for 2FA code
      } else if (data.status === 'success' && data.token) {
        onLoginSuccess(data.token, data.user);
      } else {
        setError(data.message || 'Invalid credentials.');
      }
    } catch (err: any) {
      setError(err.message || 'Login failed. Please check network connection.');
    } finally {
      setLoading(false);
    }
  };

  const handleConfirmEnrollment = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!enrollmentData) return;
    setError('');
    setLoading(true);

    try {
      const res = await saFetch('auth/2fa/enroll/', {
        method: 'POST',
        headers: { Authorization: `Bearer ${enrollmentData.temp_token}` },
        body: JSON.stringify({ totp_code: enrollmentConfirmCode.trim() }),
      });
      const data = await res.json();
      if (res.ok && data.status === 'success') {
        // Complete login
        onLoginSuccess(enrollmentData.temp_token, {
          username,
          email: 'harshposhiya92@gmail.com',
          is_totp_enrolled: true,
          last_login_at: new Date().toISOString(),
          last_login_ip: '127.0.0.1',
          is_reauth_valid: true,
          remaining_recovery_codes: 8,
        });
      } else {
        setError(data.message || 'Verification failed. Please check the code.');
      }
    } catch (err: any) {
      setError(err.message || '2FA enrollment confirmation failed.');
    } finally {
      setLoading(false);
    }
  };

  const handleCopyKey = () => {
    if (enrollmentData?.totp_secret) {
      navigator.clipboard.writeText(enrollmentData.totp_secret);
      setCopiedKey(true);
      setTimeout(() => setCopiedKey(false), 2000);
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 flex flex-col items-center justify-center p-4 selection:bg-emerald-500 selection:text-white">
      <div className="w-full max-w-md bg-slate-900 border border-slate-800 rounded-3xl p-8 shadow-2xl space-y-6 text-slate-100">
        <div className="text-center space-y-2">
          <div className="inline-flex p-3 rounded-2xl bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 mb-1">
            <ShieldAlert className="w-8 h-8" />
          </div>
          <h1 className="text-xl font-bold tracking-tight text-white">Super Admin Console</h1>
          <p className="text-xs text-slate-400 font-mono">ExamAI Platform Control Plane</p>
        </div>

        {error && (
          <div className="p-3.5 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 shrink-0 text-rose-400" />
            <p className="leading-snug">{error}</p>
          </div>
        )}

        {!enrollmentData ? (
          <form onSubmit={handlePrimaryLogin} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1.5">Username</label>
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
                className="w-full px-3.5 py-2.5 bg-slate-800/80 border border-slate-700 rounded-xl text-xs text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-emerald-500/50"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1.5">Password</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                placeholder="••••••••••••"
                className="w-full px-3.5 py-2.5 bg-slate-800/80 border border-slate-700 rounded-xl text-xs text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-emerald-500/50"
              />
            </div>

            {!isRecoveryMode ? (
              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <label className="text-xs font-semibold text-slate-300">Authenticator Code (6-Digits)</label>
                  <button
                    type="button"
                    onClick={() => setIsRecoveryMode(true)}
                    className="text-[11px] text-emerald-400 hover:underline cursor-pointer"
                  >
                    Use Recovery Code
                  </button>
                </div>
                <input
                  type="text"
                  maxLength={6}
                  value={totpCode}
                  onChange={(e) => setTotpCode(e.target.value.replace(/\D/g, ''))}
                  placeholder="e.g. 123456"
                  className="w-full px-3.5 py-2.5 bg-slate-800/80 border border-slate-700 rounded-xl text-xs font-mono text-center tracking-widest text-emerald-300 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-emerald-500/50"
                />
              </div>
            ) : (
              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <label className="text-xs font-semibold text-slate-300">One-Time Recovery Code</label>
                  <button
                    type="button"
                    onClick={() => setIsRecoveryMode(false)}
                    className="text-[11px] text-emerald-400 hover:underline cursor-pointer"
                  >
                    Use Authenticator Code
                  </button>
                </div>
                <input
                  type="text"
                  value={recoveryCode}
                  onChange={(e) => setRecoveryCode(e.target.value.toUpperCase())}
                  placeholder="XXXX-XXXX"
                  className="w-full px-3.5 py-2.5 bg-slate-800/80 border border-slate-700 rounded-xl text-xs font-mono text-center tracking-widest text-amber-300 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-amber-500/50"
                />
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full mt-2 py-3 px-4 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white font-bold text-xs rounded-xl shadow-lg shadow-emerald-950 transition-all cursor-pointer flex items-center justify-center gap-2"
            >
              {loading ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Lock className="w-4 h-4" />}
              <span>{loading ? 'Authenticating...' : 'Authenticate & Unlock Console'}</span>
            </button>
          </form>
        ) : (
          <form onSubmit={handleConfirmEnrollment} className="space-y-4">
            <div className="p-4 rounded-2xl bg-emerald-500/10 border border-emerald-500/20 text-xs space-y-3">
              <p className="font-bold text-emerald-300">Step 1: Enroll in Authenticator App</p>
              <p className="text-slate-300 text-[11px] leading-relaxed">
                Add your secret key manually to Google Authenticator, 1Password, or Authy:
              </p>
              <div className="flex items-center gap-2">
                <code className="flex-1 bg-slate-950 p-2.5 rounded-xl border border-slate-800 font-mono text-xs text-emerald-400 select-all truncate">
                  {enrollmentData.totp_secret}
                </code>
                <button
                  type="button"
                  onClick={handleCopyKey}
                  className="p-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 cursor-pointer"
                  title="Copy Secret"
                >
                  {copiedKey ? <Check className="w-4 h-4 text-emerald-400" /> : <Copy className="w-4 h-4" />}
                </button>
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                Step 2: Enter 6-Digit Code from App
              </label>
              <input
                type="text"
                maxLength={6}
                value={enrollmentConfirmCode}
                onChange={(e) => setEnrollmentConfirmCode(e.target.value.replace(/\D/g, ''))}
                placeholder="000000"
                required
                className="w-full px-3.5 py-2.5 bg-slate-800/80 border border-slate-700 rounded-xl text-xs font-mono text-center tracking-widest text-emerald-300 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-emerald-500/50"
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full py-3 px-4 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white font-bold text-xs rounded-xl shadow-lg transition-all cursor-pointer flex items-center justify-center gap-2"
            >
              {loading ? <RefreshCw className="w-4 h-4 animate-spin" /> : <ShieldCheck className="w-4 h-4" />}
              <span>{loading ? 'Verifying Code...' : 'Complete 2FA Enrollment'}</span>
            </button>
          </form>
        )}

        <div className="pt-2 text-center border-t border-slate-800">
          <p className="text-[10px] text-slate-500 font-mono">
            Access strictly restricted to Platform Owner • All access attempts audited
          </p>
        </div>
      </div>
    </div>
  );
}

// ==============================================================================
// SUPER ADMIN DASHBOARD LAYOUT & TABS
// ==============================================================================

type ConsoleTab = 'dashboard' | 'institutes' | 'users' | 'exams' | 'ai' | 'security' | 'data';

function SuperAdminDashboardLayout({
  secretSlug,
  user,
  onLogout,
  saFetch,
  onRefreshUser,
}: {
  secretSlug: string;
  user: SuperAdminUser;
  onLogout: () => void;
  saFetch: (endpoint: string, options?: RequestInit) => Promise<Response>;
  onRefreshUser: () => void;
}) {
  const [activeTab, setActiveTab] = useState<ConsoleTab>('dashboard');
  const [reauthModalOpen, setReauthModalOpen] = useState(false);
  const [reauthSuccessCallback, setReauthSuccessCallback] = useState<(() => void) | null>(null);

  const triggerReauth = (callback?: () => void) => {
    if (callback) setReauthSuccessCallback(() => callback);
    setReauthModalOpen(true);
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col md:flex-row min-w-0 max-w-full font-sans antialiased">
      {/* Sidebar */}
      <aside className="w-full md:w-64 bg-slate-900 border-r border-slate-800 flex flex-col shrink-0">
        <div className="p-5 border-b border-slate-800 flex items-center gap-3">
          <div className="p-2 rounded-xl bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 shrink-0">
            <ShieldCheck className="w-5 h-5" />
          </div>
          <div className="min-w-0 flex-1">
            <h2 className="text-sm font-bold text-white truncate">Super Admin</h2>
            <p className="text-[11px] font-mono text-emerald-400 truncate">{user.username}</p>
          </div>
        </div>

        {/* Navigation items */}
        <nav className="p-3 space-y-1 flex-1 overflow-y-auto">
          <SidebarNavButton
            active={activeTab === 'dashboard'}
            onClick={() => setActiveTab('dashboard')}
            icon={<Cpu className="w-4 h-4" />}
            label="Dashboard & Health"
          />
          <SidebarNavButton
            active={activeTab === 'institutes'}
            onClick={() => setActiveTab('institutes')}
            icon={<Building2 className="w-4 h-4" />}
            label="Institutes"
          />
          <SidebarNavButton
            active={activeTab === 'users'}
            onClick={() => setActiveTab('users')}
            icon={<Users className="w-4 h-4" />}
            label="Users Directory"
          />
          <SidebarNavButton
            active={activeTab === 'exams'}
            onClick={() => setActiveTab('exams')}
            icon={<FileText className="w-4 h-4" />}
            label="Exams Overview"
          />
          <SidebarNavButton
            active={activeTab === 'ai'}
            onClick={() => setActiveTab('ai')}
            icon={<Sparkles className="w-4 h-4" />}
            label="AI & Generation"
          />
          <SidebarNavButton
            active={activeTab === 'security'}
            onClick={() => setActiveTab('security')}
            icon={<Lock className="w-4 h-4" />}
            label="System & Security"
          />
          <SidebarNavButton
            active={activeTab === 'data'}
            onClick={() => setActiveTab('data')}
            icon={<Database className="w-4 h-4" />}
            label="Data & Backups"
          />
        </nav>

        {/* Bottom Status & Logout */}
        <div className="p-4 border-t border-slate-800 space-y-3 bg-slate-900/60">
          <div className="flex items-center justify-between text-[11px] text-slate-400">
            <span>2FA Authenticated</span>
            <span className="inline-flex items-center gap-1 text-emerald-400 font-medium">
              <CheckCircle2 className="w-3.5 h-3.5" /> Enrolled
            </span>
          </div>

          <button
            type="button"
            onClick={onLogout}
            className="w-full py-2 px-3 rounded-xl bg-slate-800 hover:bg-rose-500/20 text-slate-300 hover:text-rose-300 border border-slate-700/80 text-xs font-semibold transition-all flex items-center justify-center gap-2 cursor-pointer"
          >
            <LogOut className="w-3.5 h-3.5" />
            <span>Terminate Session</span>
          </button>
        </div>
      </aside>

      {/* Main Content Area */}
      <main className="flex-1 min-w-0 max-w-full overflow-y-auto bg-slate-950 p-4 sm:p-6 lg:p-8">
        {activeTab === 'dashboard' && <SuperAdminDashboardTab saFetch={saFetch} onTriggerReauth={triggerReauth} />}
        {activeTab === 'institutes' && <SuperAdminInstitutesTab saFetch={saFetch} onTriggerReauth={triggerReauth} />}
        {activeTab === 'users' && <SuperAdminUsersModule saFetch={saFetch} onTriggerReauth={triggerReauth} />}
        {activeTab === 'exams' && <SuperAdminExamsTab saFetch={saFetch} onTriggerReauth={triggerReauth} />}
        {activeTab === 'ai' && <SuperAdminAITab saFetch={saFetch} onTriggerReauth={triggerReauth} />}
        {activeTab === 'security' && <SuperAdminSecurityTab saFetch={saFetch} onTriggerReauth={triggerReauth} onRefreshUser={onRefreshUser} />}
        {activeTab === 'data' && <SuperAdminDataTab saFetch={saFetch} onTriggerReauth={triggerReauth} />}
      </main>

      {/* Step-Up Re-Authentication Modal */}
      {reauthModalOpen && (
        <ReauthModal
          saFetch={saFetch}
          onClose={() => setReauthModalOpen(false)}
          onSuccess={() => {
            setReauthModalOpen(false);
            onRefreshUser();
            if (reauthSuccessCallback) {
              reauthSuccessCallback();
              setReauthSuccessCallback(null);
            }
          }}
        />
      )}
    </div>
  );
}

function SidebarNavButton({
  active,
  onClick,
  icon,
  label,
}: {
  active: boolean;
  onClick: () => void;
  icon: React.ReactNode;
  label: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`w-full flex items-center gap-3 px-3.5 py-2.5 rounded-xl text-xs font-medium transition-all cursor-pointer ${
        active
          ? 'bg-emerald-500/15 text-emerald-400 font-semibold border border-emerald-500/30 shadow-xs'
          : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60'
      }`}
    >
      <span className={active ? 'text-emerald-400' : 'text-slate-400'}>{icon}</span>
      <span className="truncate">{label}</span>
    </button>
  );
}

// ==============================================================================
// TAB 1: DASHBOARD & SYSTEM HEALTH
// ==============================================================================

function SuperAdminDashboardTab({
  saFetch,
  onTriggerReauth,
}: {
  saFetch: (endpoint: string, options?: RequestInit) => Promise<Response>;
  onTriggerReauth: (cb?: () => void) => void;
}) {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  const fetchDashboard = useCallback(async () => {
    try {
      setLoading(true);
      const res = await saFetch('dashboard/');
      if (res.ok) {
        setData(await res.json());
      }
    } catch {}
    finally {
      setLoading(false);
    }
  }, [saFetch]);

  useEffect(() => {
    fetchDashboard();
  }, [fetchDashboard]);

  if (loading) {
    return (
      <div className="flex items-center justify-center p-12 text-slate-400">
        <RefreshCw className="w-6 h-6 animate-spin text-emerald-500" />
      </div>
    );
  }

  const totals = data?.totals || {};
  const health = data?.health || {};

  return (
    <div className="space-y-6 min-w-0 max-w-full">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800/80 pb-5">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold text-white tracking-tight">System Operations Center</h1>
          <p className="text-xs text-slate-400 mt-1">Cross-Institute platform metrics & infrastructure health</p>
        </div>
        <button
          onClick={fetchDashboard}
          className="inline-flex items-center gap-2 px-3.5 py-2 rounded-xl bg-slate-900 hover:bg-slate-800 border border-slate-700/80 text-xs font-semibold text-slate-200 cursor-pointer"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          <span>Refresh Metrics</span>
        </button>
      </div>

      {/* Platform Totals Grid */}
      <div className="grid grid-cols-2 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard label="Total Institutes" value={totals.total_institutes} sub={`${totals.active_institutes} Active`} icon={<Building2 className="w-4 h-4 text-emerald-400" />} />
        <MetricCard label="Total Faculty" value={totals.total_faculty} sub={`${totals.active_faculty} Active`} icon={<GraduationCap className="w-4 h-4 text-sky-400" />} />
        <MetricCard label="Total Students" value={totals.total_students} sub={`${totals.active_students} Active`} icon={<Users className="w-4 h-4 text-indigo-400" />} />
        <MetricCard label="Live Exams Now" value={totals.live_exams_now} sub={`${totals.attempts_today} Attempts Today`} icon={<Clock className="w-4 h-4 text-amber-400" />} />
      </div>

      {/* Infrastructure Health Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* MySQL Health */}
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-slate-300 flex items-center gap-2">
              <Database className="w-4 h-4 text-emerald-400" /> MySQL Database
            </span>
            <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider ${
              health.database?.status === 'healthy' ? 'bg-emerald-500/20 text-emerald-300' : 'bg-rose-500/20 text-rose-300'
            }`}>
              {health.database?.status || 'Unknown'}
            </span>
          </div>
          <p className="text-2xl font-bold font-mono text-white">{health.database?.latency_ms ?? 0} <span className="text-xs text-slate-400 font-normal">ms latency</span></p>
          <p className="text-[11px] text-slate-400">Strict transactional engine with isolation</p>
        </div>

        {/* Ollama AI Health */}
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-slate-300 flex items-center gap-2">
              <Cpu className="w-4 h-4 text-sky-400" /> Ollama Local AI
            </span>
            <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider ${
              health.ollama?.reachable ? 'bg-emerald-500/20 text-emerald-300' : 'bg-rose-500/20 text-rose-300'
            }`}>
              {health.ollama?.reachable ? 'Connected' : 'Unreachable'}
            </span>
          </div>
          <p className="text-xs font-mono text-slate-200 truncate">{health.ollama?.default_model || 'None'}</p>
          <p className="text-[11px] text-slate-400">{health.ollama?.installed_models?.length || 0} models installed locally</p>
        </div>

        {/* Disk & Queue */}
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-slate-300 flex items-center gap-2">
              <HardDrive className="w-4 h-4 text-indigo-400" /> Server Storage
            </span>
            <span className="text-[11px] font-mono text-slate-300">{health.disk?.free_gb ?? 0} GB Free</span>
          </div>
          <p className="text-2xl font-bold font-mono text-white">{health.disk?.total_gb ?? 0} <span className="text-xs text-slate-400 font-normal">GB Capacity</span></p>
          <p className="text-[11px] text-slate-400">{health.active_jobs ?? 0} active background paper jobs</p>
        </div>
      </div>

      {/* Recent Audit Stream */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 space-y-4">
        <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400">Recent Super Admin Audit Events</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs text-slate-300">
            <thead>
              <tr className="border-b border-slate-800 text-slate-400 font-semibold">
                <th className="py-2.5 px-3">Timestamp</th>
                <th className="py-2.5 px-3">Actor</th>
                <th className="py-2.5 px-3">Action</th>
                <th className="py-2.5 px-3">Entity</th>
                <th className="py-2.5 px-3">IP Address</th>
                <th className="py-2.5 px-3">Description</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {(data?.recent_audits || []).map((audit: any) => (
                <tr key={audit.id} className="hover:bg-slate-800/30">
                  <td className="py-2.5 px-3 font-mono text-slate-400 text-[11px]">
                    {new Date(audit.created_at).toLocaleString()}
                  </td>
                  <td className="py-2.5 px-3 font-medium text-emerald-400">{audit.actor_username}</td>
                  <td className="py-2.5 px-3 font-mono text-[11px] text-slate-200">{audit.action}</td>
                  <td className="py-2.5 px-3 text-slate-400">{audit.target_entity || '-'}</td>
                  <td className="py-2.5 px-3 font-mono text-slate-400 text-[11px]">{audit.ip_address}</td>
                  <td className="py-2.5 px-3 text-slate-300 truncate max-w-xs">{audit.description}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function MetricCard({
  label,
  value,
  sub,
  icon,
}: {
  label: string;
  value: any;
  sub: string;
  icon: React.ReactNode;
}) {
  return (
    <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 space-y-2">
      <div className="flex items-center justify-between text-slate-400">
        <span className="text-xs font-semibold">{label}</span>
        {icon}
      </div>
      <p className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">{value ?? 0}</p>
      <p className="text-[11px] text-slate-400 truncate">{sub}</p>
    </div>
  );
}

// ==============================================================================
// TAB 2: INSTITUTES MANAGEMENT
// ==============================================================================

function SuperAdminInstitutesTab({
  saFetch,
  onTriggerReauth,
}: {
  saFetch: (endpoint: string, options?: RequestInit) => Promise<Response>;
  onTriggerReauth: (cb?: () => void) => void;
}) {
  const [institutes, setInstitutes] = useState<any[]>([]);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [totalPages, setTotalPages] = useState(1);
  const [totalCount, setTotalCount] = useState(0);
  const [loading, setLoading] = useState(true);

  // Detail Modal
  const [selectedInst, setSelectedInst] = useState<any | null>(null);
  const [createModalOpen, setCreateModalOpen] = useState(false);

  const fetchInstitutes = useCallback(async () => {
    try {
      setLoading(true);
      const params = new URLSearchParams({
        page: String(page),
        page_size: String(pageSize),
        search,
        status: statusFilter,
      });
      const res = await saFetch(`institutes/?${params.toString()}`);
      if (res.ok) {
        const body = await res.json();
        setInstitutes(body.data || []);
        setTotalPages(body.pagination?.total_pages || 1);
        setTotalCount(body.pagination?.total_count || 0);
      }
    } catch {}
    finally {
      setLoading(false);
    }
  }, [page, pageSize, search, statusFilter, saFetch]);

  useEffect(() => {
    fetchInstitutes();
  }, [fetchInstitutes]);

  const handleToggleStatus = async (inst: any) => {
    const action = inst.status === 'active' ? 'suspend' : 'activate';
    onTriggerReauth(async () => {
      try {
        const res = await saFetch(`institutes/${inst.id}/status/`, {
          method: 'POST',
          body: JSON.stringify({ reason: `Administrative ${action} requested via Super Admin Console.` }),
        });
        if (res.ok) {
          fetchInstitutes();
        }
      } catch {}
    });
  };

  return (
    <div className="space-y-5 min-w-0 max-w-full">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800 pb-5">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold text-white tracking-tight">Institutes Directory</h1>
          <p className="text-xs text-slate-400 mt-1">Cross-institute tenancy management & administrative access</p>
        </div>
        <button
          onClick={() => setCreateModalOpen(true)}
          className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs shadow-md transition-all cursor-pointer"
        >
          <Plus className="w-4 h-4" />
          <span>Add Institution</span>
        </button>
      </div>

      {/* Filters */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-4 flex flex-col sm:flex-row items-center gap-3">
        <div className="relative flex-1 w-full">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
          <input
            type="text"
            placeholder="Search by institute name, code, or city..."
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }}
            className="w-full pl-9 pr-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-emerald-500/40"
          />
        </div>
        <select
          value={statusFilter}
          onChange={(e) => {
            setStatusFilter(e.target.value);
            setPage(1);
          }}
          className="w-full sm:w-auto px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-xs text-slate-300 focus:outline-none"
        >
          <option value="all">All Statuses</option>
          <option value="active">Active</option>
          <option value="suspended">Suspended</option>
        </select>
      </div>

      {/* Institutes Table */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs text-slate-300">
            <thead className="bg-slate-950/70 text-slate-400 uppercase tracking-wider text-[11px] border-b border-slate-800">
              <tr>
                <th className="py-3 px-4">Institute</th>
                <th className="py-3 px-4">Admin Contact</th>
                <th className="py-3 px-4">Faculty</th>
                <th className="py-3 px-4">Students</th>
                <th className="py-3 px-4">Exams</th>
                <th className="py-3 px-4">Status</th>
                <th className="py-3 px-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {institutes.map((inst) => (
                <tr key={inst.id} className="hover:bg-slate-800/40">
                  <td className="py-3.5 px-4">
                    <p className="font-bold text-white text-sm">{inst.name}</p>
                    <p className="text-[11px] font-mono text-emerald-400">{inst.code}</p>
                  </td>
                  <td className="py-3.5 px-4">
                    <p className="text-slate-200 font-medium">{inst.admin_name}</p>
                    <p className="text-[11px] text-slate-400 font-mono">{inst.admin_email}</p>
                  </td>
                  <td className="py-3.5 px-4 font-mono">{inst.faculty_count}</td>
                  <td className="py-3.5 px-4 font-mono">{inst.students_count}</td>
                  <td className="py-3.5 px-4 font-mono">{inst.exams_count}</td>
                  <td className="py-3.5 px-4">
                    <span
                      className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider ${
                        inst.status === 'active'
                          ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                          : 'bg-rose-500/20 text-rose-300 border border-rose-500/30'
                      }`}
                    >
                      {inst.status}
                    </span>
                  </td>
                  <td className="py-3.5 px-4 text-right">
                    <div className="flex items-center justify-end gap-2">
                      <button
                        onClick={() => setSelectedInst(inst)}
                        className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold border border-slate-700 cursor-pointer"
                      >
                        <Eye className="w-3.5 h-3.5 text-slate-400" />
                        <span>View</span>
                      </button>
                      <button
                        onClick={() => handleToggleStatus(inst)}
                        className={`p-1.5 rounded-lg border text-xs cursor-pointer ${
                          inst.status === 'active'
                            ? 'bg-amber-500/10 border-amber-500/30 text-amber-300 hover:bg-amber-500/20'
                            : 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300 hover:bg-emerald-500/20'
                        }`}
                        title={inst.status === 'active' ? 'Suspend Institute' : 'Activate Institute'}
                      >
                        {inst.status === 'active' ? <Lock className="w-3.5 h-3.5" /> : <Unlock className="w-3.5 h-3.5" />}
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
              {institutes.length === 0 && !loading && (
                <tr>
                  <td colSpan={7} className="py-8 text-center text-slate-500">
                    No institutions match the current filters.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {/* Server-Side Pagination */}
        <div className="p-4 border-t border-slate-800 flex flex-col sm:flex-row items-center justify-between gap-3 text-xs text-slate-400">
          <span>Total: {totalCount} institutes (Page {page} of {totalPages})</span>
          <div className="flex items-center gap-2">
            <select
              value={pageSize}
              onChange={(e) => {
                setPageSize(Number(e.target.value));
                setPage(1);
              }}
              className="bg-slate-950 border border-slate-800 rounded-lg px-2 py-1 text-slate-300 text-xs"
            >
              <option value={10}>10 per page</option>
              <option value={25}>25 per page</option>
              <option value={50}>50 per page</option>
              <option value={100}>100 per page</option>
            </select>
            <button
              disabled={page <= 1}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              className="p-1.5 rounded-lg border border-slate-800 hover:bg-slate-800 disabled:opacity-40 cursor-pointer"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            <button
              disabled={page >= totalPages}
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              className="p-1.5 rounded-lg border border-slate-800 hover:bg-slate-800 disabled:opacity-40 cursor-pointer"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>

      {/* Add Institution Modal */}
      {createModalOpen && (
        <CreateInstitutionModal
          saFetch={saFetch}
          onClose={() => setCreateModalOpen(false)}
          onSuccess={() => {
            setCreateModalOpen(false);
            fetchInstitutes();
          }}
        />
      )}

      {/* Details Modal */}
      {selectedInst && (
        <InstitutionDetailModal
          instId={selectedInst.id}
          saFetch={saFetch}
          onClose={() => setSelectedInst(null)}
        />
      )}
    </div>
  );
}

function CreateInstitutionModal({
  saFetch,
  onClose,
  onSuccess,
}: {
  saFetch: (endpoint: string, options?: RequestInit) => Promise<Response>;
  onClose: () => void;
  onSuccess: () => void;
}) {
  const [name, setName] = useState('');
  const [adminEmail, setAdminEmail] = useState('');
  const [adminFirstName, setAdminFirstName] = useState('');
  const [adminLastName, setAdminLastName] = useState('');
  const [adminPassword, setAdminPassword] = useState('');
  const [city, setCity] = useState('');
  const [state, setState] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const res = await saFetch('institutes/', {
        method: 'POST',
        body: JSON.stringify({
          institution_name: name,
          admin_email: adminEmail,
          admin_first_name: adminFirstName,
          admin_last_name: adminLastName,
          admin_password: adminPassword,
          city,
          state,
        }),
      });
      const data = await res.json();
      if (res.ok) {
        onSuccess();
      } else {
        setError(data.message || 'Failed to create institution.');
      }
    } catch (err: any) {
      setError(err.message || 'Creation error.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-xs flex items-center justify-center p-4">
      <div className="w-full max-w-lg bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden shadow-2xl text-slate-100">
        <div className="p-5 border-b border-slate-800 flex items-center justify-between">
          <h3 className="text-sm font-bold text-white">Create New Institution</h3>
          <button onClick={onClose} className="text-slate-400 hover:text-white text-xs cursor-pointer">
            Close
          </button>
        </div>
        <form onSubmit={handleSubmit} className="p-5 space-y-4 text-xs">
          {error && <p className="text-rose-400">{error}</p>}
          <div>
            <label className="block text-slate-300 font-semibold mb-1">Institution Name *</label>
            <input
              type="text"
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Stanford University"
              className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-white"
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-slate-300 font-semibold mb-1">Admin First Name</label>
              <input
                type="text"
                value={adminFirstName}
                onChange={(e) => setAdminFirstName(e.target.value)}
                className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-white"
              />
            </div>
            <div>
              <label className="block text-slate-300 font-semibold mb-1">Admin Last Name</label>
              <input
                type="text"
                value={adminLastName}
                onChange={(e) => setAdminLastName(e.target.value)}
                className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-white"
              />
            </div>
          </div>
          <div>
            <label className="block text-slate-300 font-semibold mb-1">Admin Email *</label>
            <input
              type="email"
              required
              value={adminEmail}
              onChange={(e) => setAdminEmail(e.target.value)}
              placeholder="admin@college.edu"
              className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-white font-mono"
            />
          </div>
          <div>
            <label className="block text-slate-300 font-semibold mb-1">Initial Password *</label>
            <input
              type="password"
              required
              value={adminPassword}
              onChange={(e) => setAdminPassword(e.target.value)}
              className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-white font-mono"
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-slate-300 font-semibold mb-1">City</label>
              <input
                type="text"
                value={city}
                onChange={(e) => setCity(e.target.value)}
                className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-white"
              />
            </div>
            <div>
              <label className="block text-slate-300 font-semibold mb-1">State</label>
              <input
                type="text"
                value={state}
                onChange={(e) => setState(e.target.value)}
                className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-white"
              />
            </div>
          </div>
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
              className="px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-bold cursor-pointer"
            >
              {loading ? 'Creating...' : 'Create Institution'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function InstitutionDetailModal({
  instId,
  saFetch,
  onClose,
}: {
  instId: number;
  saFetch: (endpoint: string) => Promise<Response>;
  onClose: () => void;
}) {
  const [data, setData] = useState<any | null>(null);

  useEffect(() => {
    saFetch(`institutes/${instId}/`).then(async (res) => {
      if (res.ok) {
        const body = await res.json();
        setData(body.data);
      }
    });
  }, [instId, saFetch]);

  return (
    <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-xs flex items-center justify-center p-4">
      <div className="w-full max-w-lg bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden shadow-2xl p-6 text-slate-100 space-y-4">
        <div className="flex items-center justify-between border-b border-slate-800 pb-3">
          <h3 className="text-base font-bold text-white">{data?.name || 'Loading Details...'}</h3>
          <button onClick={onClose} className="text-slate-400 hover:text-white text-xs cursor-pointer">
            Close
          </button>
        </div>
        {data && (
          <div className="space-y-3 text-xs">
            <div className="grid grid-cols-2 gap-2 p-3 rounded-xl bg-slate-950 font-mono text-[11px]">
              <div>Code: <span className="text-emerald-400">{data.code}</span></div>
              <div>Status: <span className="uppercase text-slate-300">{data.status}</span></div>
              <div>City: <span className="text-slate-300">{data.city || 'N/A'}</span></div>
              <div>State: <span className="text-slate-300">{data.state || 'N/A'}</span></div>
            </div>
            <div>
              <p className="font-semibold text-slate-300 mb-1">Standard Departments ({data.departments?.length || 0}):</p>
              <div className="flex flex-wrap gap-1.5">
                {(data.departments || []).map((d: any) => (
                  <span key={d.id} className="px-2.5 py-1 rounded-lg bg-slate-800 text-[11px] text-slate-300 border border-slate-700">
                    {d.department_name}
                  </span>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ==============================================================================
// TAB 3: USERS DIRECTORY
// ==============================================================================

function SuperAdminUsersTab({
  saFetch,
  onTriggerReauth,
}: {
  saFetch: (endpoint: string, options?: RequestInit) => Promise<Response>;
  onTriggerReauth: (cb?: () => void) => void;
}) {
  const [users, setUsers] = useState<any[]>([]);
  const [search, setSearch] = useState('');
  const [roleFilter, setRoleFilter] = useState('all');
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [totalPages, setTotalPages] = useState(1);
  const [totalCount, setTotalCount] = useState(0);
  const [loading, setLoading] = useState(true);

  // Modals
  const [resetPwdModal, setResetPwdModal] = useState<{ open: boolean; user: any | null; resultPass?: string }>({
    open: false,
    user: null,
  });
  const [transferModal, setTransferModal] = useState<{ open: boolean; user: any | null }>({
    open: false,
    user: null,
  });

  const fetchUsers = useCallback(async () => {
    try {
      setLoading(true);
      const params = new URLSearchParams({
        page: String(page),
        page_size: String(pageSize),
        search,
        role: roleFilter,
      });
      const res = await saFetch(`users/?${params.toString()}`);
      if (res.ok) {
        const body = await res.json();
        setUsers(body.data || []);
        setTotalPages(body.pagination?.total_pages || 1);
        setTotalCount(body.pagination?.total_count || 0);
      }
    } catch {}
    finally {
      setLoading(false);
    }
  }, [page, pageSize, search, roleFilter, saFetch]);

  useEffect(() => {
    fetchUsers();
  }, [fetchUsers]);

  const handleResetPassword = (targetUser: any) => {
    onTriggerReauth(async () => {
      try {
        const res = await saFetch(`users/${targetUser.id}/reset-password/`, {
          method: 'POST',
          body: JSON.stringify({ reason: 'Super Admin Administrative Password Reset' }),
        });
        const data = await res.json();
        if (res.ok) {
          setResetPwdModal({ open: true, user: targetUser, resultPass: data.temporary_password });
        }
      } catch {}
    });
  };

  return (
    <div className="space-y-5 min-w-0 max-w-full">
      <div className="border-b border-slate-800 pb-5">
        <h1 className="text-xl sm:text-2xl font-bold text-white tracking-tight">Global Users Directory</h1>
        <p className="text-xs text-slate-400 mt-1">Cross-institute students, faculty, and administrators directory</p>
      </div>

      {/* Filter controls */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-4 flex flex-col sm:flex-row items-center gap-3">
        <div className="relative flex-1 w-full">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
          <input
            type="text"
            placeholder="Search by name, email, student ID, or employee ID..."
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }}
            className="w-full pl-9 pr-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-emerald-500/40"
          />
        </div>
        <select
          value={roleFilter}
          onChange={(e) => {
            setRoleFilter(e.target.value);
            setPage(1);
          }}
          className="w-full sm:w-auto px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-xs text-slate-300 focus:outline-none"
        >
          <option value="all">All Roles</option>
          <option value="student">Students</option>
          <option value="faculty">Faculty</option>
          <option value="admin">Institute Admins</option>
        </select>
      </div>

      {/* Users table */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs text-slate-300">
            <thead className="bg-slate-950/70 text-slate-400 uppercase tracking-wider text-[11px] border-b border-slate-800">
              <tr>
                <th className="py-3 px-4">User</th>
                <th className="py-3 px-4">Role</th>
                <th className="py-3 px-4">Identifier</th>
                <th className="py-3 px-4">Department</th>
                <th className="py-3 px-4">Institution</th>
                <th className="py-3 px-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {users.map((u) => (
                <tr key={u.id} className="hover:bg-slate-800/40">
                  <td className="py-3.5 px-4">
                    <p className="font-bold text-white text-sm">{u.full_name}</p>
                    <p className="text-[11px] font-mono text-slate-400">{u.email}</p>
                  </td>
                  <td className="py-3.5 px-4">
                    <span
                      className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider ${
                        u.role === 'admin'
                          ? 'bg-amber-500/20 text-amber-300'
                          : u.role === 'faculty'
                          ? 'bg-sky-500/20 text-sky-300'
                          : 'bg-emerald-500/20 text-emerald-300'
                      }`}
                    >
                      {u.role}
                    </span>
                  </td>
                  <td className="py-3.5 px-4 font-mono text-slate-300">{u.identifier || '-'}</td>
                  <td className="py-3.5 px-4 text-slate-300">{u.department}</td>
                  <td className="py-3.5 px-4 text-slate-300 truncate max-w-xs">{u.institution?.name}</td>
                  <td className="py-3.5 px-4 text-right">
                    <div className="flex items-center justify-end gap-2">
                      <button
                        onClick={() => handleResetPassword(u)}
                        className="p-1.5 rounded-lg border border-slate-800 hover:bg-slate-800 text-slate-300 hover:text-white cursor-pointer"
                        title="Reset User Password"
                      >
                        <KeyRound className="w-3.5 h-3.5 text-amber-400" />
                      </button>
                      <button
                        onClick={() => setTransferModal({ open: true, user: u })}
                        className="p-1.5 rounded-lg border border-slate-800 hover:bg-slate-800 text-slate-300 hover:text-white cursor-pointer"
                        title="Transfer Department"
                      >
                        <ArrowRightLeft className="w-3.5 h-3.5 text-sky-400" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        <div className="p-4 border-t border-slate-800 flex items-center justify-between text-xs text-slate-400">
          <span>Total: {totalCount} users</span>
          <div className="flex items-center gap-2">
            <button
              disabled={page <= 1}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              className="p-1.5 rounded-lg border border-slate-800 hover:bg-slate-800 disabled:opacity-40 cursor-pointer"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            <span>{page} / {totalPages}</span>
            <button
              disabled={page >= totalPages}
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              className="p-1.5 rounded-lg border border-slate-800 hover:bg-slate-800 disabled:opacity-40 cursor-pointer"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>

      {/* Password Reset Result Modal */}
      {resetPwdModal.open && resetPwdModal.resultPass && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="w-full max-w-md bg-slate-900 border border-slate-800 rounded-2xl p-6 text-slate-100 space-y-4">
            <h3 className="text-sm font-bold text-white flex items-center gap-2">
              <KeyRound className="w-4 h-4 text-emerald-400" /> Password Reset Generated
            </h3>
            <p className="text-xs text-slate-400">
              Temporary password for <strong className="text-white">{resetPwdModal.user?.email}</strong>:
            </p>
            <div className="p-3 bg-slate-950 border border-slate-800 rounded-xl font-mono text-sm text-emerald-300 text-center select-all font-bold">
              {resetPwdModal.resultPass}
            </div>
            <button
              onClick={() => setResetPwdModal({ open: false, user: null })}
              className="w-full py-2 bg-emerald-600 hover:bg-emerald-500 rounded-xl text-xs font-bold text-white cursor-pointer"
            >
              Done
            </button>
          </div>
        </div>
      )}

      {/* Transfer Modal */}
      {transferModal.open && transferModal.user && (
        <TransferUserModal
          user={transferModal.user}
          saFetch={saFetch}
          onTriggerReauth={onTriggerReauth}
          onClose={() => setTransferModal({ open: false, user: null })}
          onSuccess={() => {
            setTransferModal({ open: false, user: null });
            fetchUsers();
          }}
        />
      )}
    </div>
  );
}

function TransferUserModal({
  user,
  saFetch,
  onTriggerReauth,
  onClose,
  onSuccess,
}: {
  user: any;
  saFetch: (endpoint: string, options?: RequestInit) => Promise<Response>;
  onTriggerReauth: (cb?: () => void) => void;
  onClose: () => void;
  onSuccess: () => void;
}) {
  const [newDepartment, setNewDepartment] = useState('');
  const [reason, setReason] = useState('');
  const [error, setError] = useState('');

  const handleTransfer = () => {
    if (!newDepartment || !reason) {
      setError('Please provide department and reason.');
      return;
    }
    onTriggerReauth(async () => {
      try {
        const res = await saFetch(`users/${user.id}/transfer/`, {
          method: 'POST',
          body: JSON.stringify({ department: newDepartment, reason }),
        });
        if (res.ok) {
          onSuccess();
        } else {
          const body = await res.json();
          setError(body.message || 'Transfer failed.');
        }
      } catch (err: any) {
        setError(err.message || 'Error occurred during transfer.');
      }
    });
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-xs flex items-center justify-center p-4">
      <div className="w-full max-w-md bg-slate-900 border border-slate-800 rounded-2xl p-6 text-slate-100 space-y-4 text-xs">
        <h3 className="text-sm font-bold text-white flex items-center gap-2">
          <ArrowRightLeft className="w-4 h-4 text-sky-400" /> Transfer Department
        </h3>
        {error && <p className="text-rose-400">{error}</p>}
        <p className="text-slate-400">
          Target: <strong className="text-white">{user.full_name}</strong> ({user.email})
        </p>
        <div>
          <label className="block text-slate-300 font-semibold mb-1">New Department *</label>
          <input
            type="text"
            required
            value={newDepartment}
            onChange={(e) => setNewDepartment(e.target.value)}
            placeholder="e.g. Information Technology"
            className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-white"
          />
        </div>
        <div>
          <label className="block text-slate-300 font-semibold mb-1">Justification Reason *</label>
          <textarea
            rows={3}
            required
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="Document reason for permanent audit trail..."
            className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-white"
          />
        </div>
        <div className="flex justify-end gap-2 pt-2 border-t border-slate-800">
          <button onClick={onClose} className="px-3.5 py-1.5 rounded-xl border border-slate-800 text-slate-400 cursor-pointer">
            Cancel
          </button>
          <button onClick={handleTransfer} className="px-3.5 py-1.5 rounded-xl bg-sky-600 hover:bg-sky-500 text-white font-bold cursor-pointer">
            Authorize Transfer
          </button>
        </div>
      </div>
    </div>
  );
}

// ==============================================================================
// TAB 4: EXAMS OVERVIEW
// ==============================================================================

function SuperAdminExamsTab({
  saFetch,
  onTriggerReauth,
}: {
  saFetch: (endpoint: string, options?: RequestInit) => Promise<Response>;
  onTriggerReauth: (cb?: () => void) => void;
}) {
  const [exams, setExams] = useState<any[]>([]);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [shortfallOnly, setShortfallOnly] = useState(false);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [loading, setLoading] = useState(true);

  const fetchExams = useCallback(async () => {
    try {
      setLoading(true);
      const params = new URLSearchParams({
        page: String(page),
        page_size: '10',
        search,
        status: statusFilter,
        shortfall_only: String(shortfallOnly),
      });
      const res = await saFetch(`exams/?${params.toString()}`);
      if (res.ok) {
        const body = await res.json();
        setExams(body.data || []);
        setTotalPages(body.pagination?.total_pages || 1);
      }
    } catch {}
    finally {
      setLoading(false);
    }
  }, [page, search, statusFilter, shortfallOnly, saFetch]);

  useEffect(() => {
    fetchExams();
  }, [fetchExams]);

  const handleForceClose = (exam: any) => {
    const reason = window.prompt(`Enter mandatory reason to force-close exam "${exam.title}":`);
    if (!reason) return;

    onTriggerReauth(async () => {
      try {
        const res = await saFetch(`exams/${exam.id}/force-close/`, {
          method: 'POST',
          body: JSON.stringify({ reason }),
        });
        if (res.ok) {
          fetchExams();
        }
      } catch {}
    });
  };

  return (
    <div className="space-y-5 min-w-0 max-w-full">
      <div className="border-b border-slate-800 pb-5">
        <h1 className="text-xl sm:text-2xl font-bold text-white tracking-tight">Global Exams Manager</h1>
        <p className="text-xs text-slate-400 mt-1">Cross-institute examination schedules, blueprint validation, and live supervision</p>
      </div>

      {/* Filters */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-4 flex flex-col sm:flex-row items-center gap-3">
        <div className="relative flex-1 w-full">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
          <input
            type="text"
            placeholder="Search by exam title, subject, department, or institute..."
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }}
            className="w-full pl-9 pr-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-emerald-500/40"
          />
        </div>
        <select
          value={statusFilter}
          onChange={(e) => {
            setStatusFilter(e.target.value);
            setPage(1);
          }}
          className="w-full sm:w-auto px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-xs text-slate-300 focus:outline-none"
        >
          <option value="all">All Statuses</option>
          <option value="draft">Draft</option>
          <option value="published">Published</option>
          <option value="closed">Closed</option>
          <option value="failed">Failed</option>
        </select>
        <label className="flex items-center gap-2 text-xs text-slate-300 cursor-pointer select-none">
          <input
            type="checkbox"
            checked={shortfallOnly}
            onChange={(e) => {
              setShortfallOnly(e.target.checked);
              setPage(1);
            }}
            className="rounded-sm border-slate-700 bg-slate-950 text-emerald-500"
          />
          <span>Shortfall Only</span>
        </label>
      </div>

      {/* Table */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs text-slate-300">
            <thead className="bg-slate-950/70 text-slate-400 uppercase tracking-wider text-[11px] border-b border-slate-800">
              <tr>
                <th className="py-3 px-4">Exam Title</th>
                <th className="py-3 px-4">Subject / Dept</th>
                <th className="py-3 px-4">Institution</th>
                <th className="py-3 px-4">Target vs Actual</th>
                <th className="py-3 px-4">Status</th>
                <th className="py-3 px-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {exams.map((e) => (
                <tr key={e.id} className="hover:bg-slate-800/40">
                  <td className="py-3.5 px-4">
                    <p className="font-bold text-white text-sm">{e.title}</p>
                    <p className="text-[11px] text-slate-400 font-mono">By {e.created_by}</p>
                  </td>
                  <td className="py-3.5 px-4">
                    <p className="text-slate-200">{e.subject}</p>
                    <p className="text-[11px] text-slate-400">{e.department}</p>
                  </td>
                  <td className="py-3.5 px-4 text-slate-300">{e.institution?.name}</td>
                  <td className="py-3.5 px-4 font-mono">
                    <span className="text-emerald-400 font-bold">{e.total_marks}</span> / {e.target_total_marks ?? '-'}
                    {e.marks_shortfall > 0 && (
                      <span className="ml-2 px-1.5 py-0.5 rounded-sm bg-rose-500/20 text-rose-300 text-[10px]">
                        -{e.marks_shortfall} short
                      </span>
                    )}
                  </td>
                  <td className="py-3.5 px-4">
                    <span className="px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider bg-slate-800 text-slate-200">
                      {e.status}
                    </span>
                  </td>
                  <td className="py-3.5 px-4 text-right">
                    {e.status === 'published' && (
                      <button
                        onClick={() => handleForceClose(e)}
                        className="px-2.5 py-1 rounded-lg bg-rose-500/10 hover:bg-rose-500/20 text-rose-300 border border-rose-500/30 text-xs font-semibold cursor-pointer"
                        title="Emergency Force-Close"
                      >
                        Force Close
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

// ==============================================================================
// TAB 5: AI & GENERATION ENGINE
// ==============================================================================

function SuperAdminAITab({
  saFetch,
  onTriggerReauth,
}: {
  saFetch: (endpoint: string, options?: RequestInit) => Promise<Response>;
  onTriggerReauth: (cb?: () => void) => void;
}) {
  return (
    <div className="space-y-6 min-w-0 max-w-full">
      <div className="border-b border-slate-800 pb-5">
        <h1 className="text-xl sm:text-2xl font-bold text-white tracking-tight">AI & Generation Infrastructure</h1>
        <p className="text-xs text-slate-400 mt-1">Ollama local inference service, model routing, and generation queues</p>
      </div>

      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 space-y-4">
        <h3 className="text-sm font-bold text-white flex items-center gap-2">
          <Cpu className="w-4 h-4 text-emerald-400" /> Active Local Inference Provider
        </h3>
        <p className="text-xs text-slate-300 leading-relaxed">
          ExamAI leverages a local <strong>Ollama instance</strong> running on <code>http://127.0.0.1:11434</code> with fallback model failover and batching optimizations.
        </p>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs font-mono">
          <div className="p-3 bg-slate-950 rounded-xl border border-slate-800">
            <span className="text-slate-400">Primary Objective Model:</span> <span className="text-emerald-400 font-bold">qwen2.5:3b-instruct</span>
          </div>
          <div className="p-3 bg-slate-950 rounded-xl border border-slate-800">
            <span className="text-slate-400">Primary Subjective Model:</span> <span className="text-emerald-400 font-bold">qwen2.5:3b-instruct</span>
          </div>
        </div>
      </div>
    </div>
  );
}

// ==============================================================================
// TAB 6: SYSTEM & SECURITY CENTER
// ==============================================================================

function SuperAdminSecurityTab({
  saFetch,
  onTriggerReauth,
  onRefreshUser,
}: {
  saFetch: (endpoint: string, options?: RequestInit) => Promise<Response>;
  onTriggerReauth: (cb?: () => void) => void;
  onRefreshUser: () => void;
}) {
  const [maintenance, setMaintenance] = useState<{ enabled: boolean; message: string }>({ enabled: false, message: '' });
  const [logs, setLogs] = useState<any[]>([]);
  const [loadingLogs, setLoadingLogs] = useState(true);

  const fetchSettings = useCallback(async () => {
    try {
      const res = await saFetch('system/settings/');
      if (res.ok) {
        const body = await res.json();
        setMaintenance(body.settings?.maintenance_mode || { enabled: false, message: '' });
      }
    } catch {}
  }, [saFetch]);

  const fetchLogs = useCallback(async () => {
    try {
      setLoadingLogs(true);
      const res = await saFetch('system/audit-logs/?page_size=50');
      if (res.ok) {
        const body = await res.json();
        setLogs(body.data || []);
      }
    } catch {}
    finally {
      setLoadingLogs(false);
    }
  }, [saFetch]);

  useEffect(() => {
    fetchSettings();
    fetchLogs();
  }, [fetchSettings, fetchLogs]);

  const handleToggleMaintenance = () => {
    const nextState = !maintenance.enabled;
    const msg = nextState ? window.prompt('Enter platform maintenance message:', 'ExamAI is undergoing scheduled platform maintenance. Please check back shortly.') : '';
    if (nextState && msg === null) return;

    onTriggerReauth(async () => {
      try {
        const res = await saFetch('system/settings/', {
          method: 'POST',
          body: JSON.stringify({
            key: 'maintenance_mode',
            value: { enabled: nextState, message: msg || '' },
          }),
        });
        if (res.ok) {
          setMaintenance({ enabled: nextState, message: msg || '' });
        }
      } catch {}
    });
  };

  const handleExportCSV = async () => {
    try {
      const res = await saFetch('system/audit-logs/?export=csv');
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `superadmin_audit_${Date.now()}.csv`;
      document.body.appendChild(a);
      a.click();
      a.remove();
    } catch {}
  };

  return (
    <div className="space-y-6 min-w-0 max-w-full">
      <div className="border-b border-slate-800 pb-5">
        <h1 className="text-xl sm:text-2xl font-bold text-white tracking-tight">System & Security Center</h1>
        <p className="text-xs text-slate-400 mt-1">Platform maintenance mode, security audits, and access enforcement</p>
      </div>

      {/* Maintenance Mode Card */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 flex flex-col sm:flex-row items-center justify-between gap-4">
        <div className="space-y-1">
          <h3 className="text-sm font-bold text-white flex items-center gap-2">
            <ShieldAlert className="w-4 h-4 text-amber-400" /> Platform Maintenance Mode
          </h3>
          <p className="text-xs text-slate-400 max-w-xl">
            When enabled, all standard user requests receive a friendly 503 Service Unavailable page. The Super Admin Console remains fully accessible.
          </p>
        </div>
        <button
          onClick={handleToggleMaintenance}
          className={`px-4 py-2.5 rounded-xl font-bold text-xs transition-all cursor-pointer ${
            maintenance.enabled
              ? 'bg-rose-600 hover:bg-rose-500 text-white shadow-lg shadow-rose-950'
              : 'bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700'
          }`}
        >
          {maintenance.enabled ? 'Disable Maintenance' : 'Activate Maintenance Mode'}
        </button>
      </div>

      {/* Audit Log Table */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400">
            Immutable Super Admin Audit Trail
          </h3>
          <button
            onClick={handleExportCSV}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold border border-slate-700 cursor-pointer"
          >
            <Download className="w-3.5 h-3.5" />
            <span>Export CSV</span>
          </button>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs text-slate-300">
            <thead className="bg-slate-950/70 text-slate-400 uppercase tracking-wider text-[11px] border-b border-slate-800">
              <tr>
                <th className="py-2.5 px-3">Timestamp</th>
                <th className="py-2.5 px-3">Action</th>
                <th className="py-2.5 px-3">Entity</th>
                <th className="py-2.5 px-3">IP Address</th>
                <th className="py-2.5 px-3">Description</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {logs.map((l) => (
                <tr key={l.id} className="hover:bg-slate-800/30">
                  <td className="py-2.5 px-3 font-mono text-[11px] text-slate-400">
                    {new Date(l.created_at).toLocaleString()}
                  </td>
                  <td className="py-2.5 px-3 font-mono font-bold text-emerald-400 text-[11px]">{l.action}</td>
                  <td className="py-2.5 px-3 text-slate-400">{l.target_entity}</td>
                  <td className="py-2.5 px-3 font-mono text-slate-400 text-[11px]">{l.ip_address}</td>
                  <td className="py-2.5 px-3 text-slate-300 truncate max-w-sm">{l.description}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

// ==============================================================================
// TAB 7: DATA & BACKUPS
// ==============================================================================

function SuperAdminDataTab({
  saFetch,
  onTriggerReauth,
}: {
  saFetch: (endpoint: string, options?: RequestInit) => Promise<Response>;
  onTriggerReauth: (cb?: () => void) => void;
}) {
  const [backups, setBackups] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);

  const fetchBackups = useCallback(async () => {
    try {
      setLoading(true);
      const res = await saFetch('data/backups/');
      if (res.ok) {
        const body = await res.json();
        setBackups(body.backups || []);
      }
    } catch {}
    finally {
      setLoading(false);
    }
  }, [saFetch]);

  useEffect(() => {
    fetchBackups();
  }, [fetchBackups]);

  const handleCreateBackup = () => {
    onTriggerReauth(async () => {
      try {
        setCreating(true);
        const res = await saFetch('data/backups/', { method: 'POST' });
        if (res.ok) {
          fetchBackups();
        }
      } catch {}
      finally {
        setCreating(false);
      }
    });
  };

  return (
    <div className="space-y-6 min-w-0 max-w-full">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800 pb-5">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold text-white tracking-tight">Data Management & Disaster Recovery</h1>
          <p className="text-xs text-slate-400 mt-1">Automated database dump archives and dry-run cleanup reports</p>
        </div>
        <button
          onClick={handleCreateBackup}
          disabled={creating}
          className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white font-bold text-xs shadow-md transition-all cursor-pointer"
        >
          {creating ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Database className="w-4 h-4" />}
          <span>{creating ? 'Creating Dump...' : 'Create Instant Backup'}</span>
        </button>
      </div>

      {/* Backups List */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 space-y-4">
        <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400">
          Saved Database Archives (Stored Outside Project)
        </h3>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs text-slate-300">
            <thead className="bg-slate-950/70 text-slate-400 uppercase tracking-wider text-[11px] border-b border-slate-800">
              <tr>
                <th className="py-2.5 px-3">Archive File</th>
                <th className="py-2.5 px-3">File Size</th>
                <th className="py-2.5 px-3">Created At</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {backups.map((b) => (
                <tr key={b.filename} className="hover:bg-slate-800/30">
                  <td className="py-2.5 px-3 font-mono text-emerald-400 font-bold">{b.filename}</td>
                  <td className="py-2.5 px-3 font-mono">{b.size_mb} MB</td>
                  <td className="py-2.5 px-3 text-slate-400 font-mono text-[11px]">
                    {new Date(b.created_at).toLocaleString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

// ==============================================================================
// STEP-UP RE-AUTHENTICATION MODAL
// ==============================================================================

function ReauthModal({
  saFetch,
  onClose,
  onSuccess,
}: {
  saFetch: (endpoint: string, options?: RequestInit) => Promise<Response>;
  onClose: () => void;
  onSuccess: () => void;
}) {
  const [password, setPassword] = useState('');
  const [totpCode, setTotpCode] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const res = await saFetch('auth/reauth/', {
        method: 'POST',
        body: JSON.stringify({ password, totp_code: totpCode.trim() }),
      });
      const data = await res.json();
      if (res.ok && data.status === 'success') {
        onSuccess();
      } else {
        setError(data.message || 'Re-authentication failed.');
      }
    } catch (err: any) {
      setError(err.message || 'Network error.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/75 backdrop-blur-xs flex items-center justify-center p-4">
      <div className="w-full max-w-sm bg-slate-900 border border-slate-800 rounded-3xl p-6 text-slate-100 shadow-2xl space-y-4">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-amber-500/10 text-amber-400 border border-amber-500/20">
            <Lock className="w-5 h-5" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-white">Step-Up Re-Authentication</h3>
            <p className="text-[11px] text-slate-400">High-risk action requires credential confirmation</p>
          </div>
        </div>

        {error && <p className="text-rose-400 text-xs">{error}</p>}

        <form onSubmit={handleSubmit} className="space-y-3.5 text-xs">
          <div>
            <label className="block text-slate-300 font-semibold mb-1">Super Admin Password</label>
            <input
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••••••"
              className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-white"
            />
          </div>

          <div>
            <label className="block text-slate-300 font-semibold mb-1">Authenticator Code (6-Digits)</label>
            <input
              type="text"
              maxLength={6}
              required
              value={totpCode}
              onChange={(e) => setTotpCode(e.target.value.replace(/\D/g, ''))}
              placeholder="000000"
              className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-emerald-400 font-mono tracking-widest text-center"
            />
          </div>

          <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-800">
            <button type="button" onClick={onClose} className="px-3.5 py-1.5 rounded-xl border border-slate-800 text-slate-400 cursor-pointer">
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading}
              className="px-4 py-1.5 rounded-xl bg-amber-600 hover:bg-amber-500 text-white font-bold cursor-pointer"
            >
              {loading ? 'Verifying...' : 'Authorize Action'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

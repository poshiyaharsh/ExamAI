import React, { useState, useEffect, useCallback } from 'react';
import { useLocation } from 'react-router-dom';
import {
  Bell,
  AlertTriangle,
  Info,
  CheckCircle2,
  XCircle,
  ExternalLink,
  ChevronRight,
  ChevronLeft,
  X,
  Sparkles,
} from 'lucide-react';
import { notificationApi, AppNotification } from '../../services/api';
import { useAuth } from '../context/useAuth';

export function NotificationPopupManager() {
  const { session } = useAuth();
  const user = session?.user;
  const location = useLocation();
  const [popups, setPopups] = useState<AppNotification[]>([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [isOpen, setIsOpen] = useState(false);
  const [dismissing, setDismissing] = useState(false);

  // Suppress popups during active exam attempts to prevent distraction or violation triggering
  const isExamInProgress =
    location.pathname.includes('/exam') ||
    location.pathname.includes('/attempt') ||
    sessionStorage.getItem('active_exam_in_progress') === 'true';

  const fetchPendingPopups = useCallback(async () => {
    if (!user || isExamInProgress) {
      setIsOpen(false);
      return;
    }

    try {
      const data = await notificationApi.getPopups();
      if (data && data.popups && data.popups.length > 0) {
        setPopups(data.popups);
        setCurrentIndex(0);
        setIsOpen(true);
      } else {
        setPopups([]);
        setIsOpen(false);
      }
    } catch {
      // Gracefully ignore fetch errors for offline or unauthenticated scenarios
    }
  }, [user, isExamInProgress]);

  useEffect(() => {
    fetchPendingPopups();
  }, [fetchPendingPopups, location.pathname]);

  // Keyboard accessibility: Escape to dismiss current
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (!isOpen) return;
      if (e.key === 'Escape') {
        handleDismissCurrent();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, currentIndex, popups]);

  const handleDismissCurrent = async () => {
    const current = popups[currentIndex];
    if (!current) return;

    setDismissing(true);
    try {
      await notificationApi.dismissPopup(current.id);
      const remaining = popups.filter((_, idx) => idx !== currentIndex);
      if (remaining.length === 0) {
        setIsOpen(false);
        setPopups([]);
      } else {
        setPopups(remaining);
        setCurrentIndex((prev) => (prev >= remaining.length ? 0 : prev));
      }
    } catch (err) {
      console.error('Failed to dismiss popup:', err);
    } finally {
      setDismissing(false);
    }
  };

  const handleDismissAll = async () => {
    setDismissing(true);
    try {
      await notificationApi.dismissAllPopups();
      setIsOpen(false);
      setPopups([]);
    } catch (err) {
      console.error('Failed to dismiss all popups:', err);
    } finally {
      setDismissing(false);
    }
  };

  if (!isOpen || popups.length === 0 || isExamInProgress) {
    return null;
  }

  const current = popups[currentIndex];
  if (!current) return null;

  const typeConfig = {
    warning: {
      border: 'border-amber-500/40',
      bg: 'bg-amber-500/10',
      badge: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
      icon: AlertTriangle,
      iconColor: 'text-amber-400',
      tag: 'Platform Warning',
    },
    error: {
      border: 'border-rose-500/40',
      bg: 'bg-rose-500/10',
      badge: 'bg-rose-500/20 text-rose-400 border-rose-500/30',
      icon: XCircle,
      iconColor: 'text-rose-400',
      tag: 'Urgent Announcement',
    },
    success: {
      border: 'border-emerald-500/40',
      bg: 'bg-emerald-500/10',
      badge: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
      icon: CheckCircle2,
      iconColor: 'text-emerald-400',
      tag: 'System Update',
    },
    info: {
      border: 'border-sky-500/40',
      bg: 'bg-sky-500/10',
      badge: 'bg-sky-500/20 text-sky-400 border-sky-500/30',
      icon: Info,
      iconColor: 'text-sky-400',
      tag: 'System Announcement',
    },
  }[current.type || 'info'] || {
    border: 'border-sky-500/40',
    bg: 'bg-sky-500/10',
    badge: 'bg-sky-500/20 text-sky-400 border-sky-500/30',
    icon: Bell,
    iconColor: 'text-sky-400',
    tag: 'Announcement',
  };

  const IconComponent = typeConfig.icon;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="notification-popup-title"
      className="fixed inset-0 z-9999 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-md animate-fade-in"
    >
      <div
        className={`w-full max-w-lg bg-slate-900 border ${typeConfig.border} rounded-3xl p-6 sm:p-7 shadow-2xl text-slate-100 relative overflow-hidden transition-all transform scale-100`}
      >
        {/* Glow ambient background effect */}
        <div
          className={`absolute -top-24 -right-24 w-48 h-48 rounded-full ${typeConfig.bg} blur-3xl pointer-events-none`}
        />

        {/* Top Header & Multi-popup stepper */}
        <div className="flex items-start justify-between gap-4 mb-4 relative z-10">
          <div className="flex items-center gap-3">
            <div className={`p-3 rounded-2xl ${typeConfig.bg} border ${typeConfig.border} shrink-0`}>
              <IconComponent className={`w-5 h-5 ${typeConfig.iconColor}`} />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider border ${typeConfig.badge}`}>
                  <Sparkles className="w-3 h-3" />
                  {typeConfig.tag}
                </span>
                {popups.length > 1 && (
                  <span className="text-[11px] font-mono font-bold text-slate-400 bg-slate-800/80 px-2 py-0.5 rounded-md border border-slate-700">
                    {currentIndex + 1} of {popups.length}
                  </span>
                )}
              </div>
              <h2
                id="notification-popup-title"
                className="text-base sm:text-lg font-bold text-white mt-1 leading-snug line-clamp-2"
              >
                {current.title}
              </h2>
            </div>
          </div>

          <button
            onClick={handleDismissCurrent}
            disabled={dismissing}
            aria-label="Close notification"
            className="p-1.5 rounded-xl bg-slate-800/80 hover:bg-slate-700 text-slate-400 hover:text-white transition-colors cursor-pointer border border-slate-700/60"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Message Body */}
        <div className="relative z-10 py-2">
          <p className="text-xs sm:text-sm text-slate-300 leading-relaxed whitespace-pre-line font-normal max-h-56 overflow-y-auto pr-1">
            {current.message}
          </p>

          {/* Action Link if provided */}
          {current.link && (
            <div className="mt-4 pt-3 border-t border-slate-800/80 flex items-center justify-between">
              <span className="text-[11px] text-slate-400">Attached Link:</span>
              <a
                href={current.link}
                target={current.link.startsWith('http') ? '_blank' : '_self'}
                rel="noreferrer"
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-sky-500/10 hover:bg-sky-500/20 text-sky-400 border border-sky-500/30 text-xs font-semibold transition-colors"
              >
                <span>Visit Link</span>
                <ExternalLink className="w-3.5 h-3.5" />
              </a>
            </div>
          )}
        </div>

        {/* Action Controls & Navigation Footer */}
        <div className="relative z-10 mt-6 pt-4 border-t border-slate-800 flex flex-col sm:flex-row items-center justify-between gap-3 text-xs">
          {popups.length > 1 ? (
            <div className="flex items-center gap-1 w-full sm:w-auto justify-between sm:justify-start">
              <button
                disabled={currentIndex === 0 || dismissing}
                onClick={() => setCurrentIndex((prev) => Math.max(0, prev - 1))}
                className="p-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 disabled:opacity-30 border border-slate-700 transition-colors"
              >
                <ChevronLeft className="w-4 h-4" />
              </button>
              <button
                disabled={currentIndex >= popups.length - 1 || dismissing}
                onClick={() => setCurrentIndex((prev) => Math.min(popups.length - 1, prev + 1))}
                className="p-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 disabled:opacity-30 border border-slate-700 transition-colors"
              >
                <ChevronRight className="w-4 h-4" />
              </button>
              <button
                disabled={dismissing}
                onClick={handleDismissAll}
                className="text-[11px] text-slate-400 hover:text-slate-200 underline ml-2 transition-colors cursor-pointer"
              >
                Dismiss All ({popups.length})
              </button>
            </div>
          ) : (
            <div />
          )}

          <div className="flex items-center gap-2 w-full sm:w-auto justify-end">
            <button
              onClick={handleDismissCurrent}
              disabled={dismissing}
              className="w-full sm:w-auto px-5 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-bold shadow-lg shadow-emerald-950/40 transition-all cursor-pointer disabled:opacity-50 text-center"
            >
              {dismissing ? 'Dismissing...' : 'Acknowledge & Dismiss'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

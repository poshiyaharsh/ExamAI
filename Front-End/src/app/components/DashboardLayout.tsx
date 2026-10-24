import { useEffect, useMemo, useState, useRef, ReactNode } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "motion/react";
import {
  Brain,
  Menu,
  LogOut,
  Bell,
  Settings,
  User,
  ChevronLeft,
  CheckCircle2,
  AlertCircle,
  Info,
  Check,
} from "lucide-react";
import { toast } from "sonner";
import { useAuth } from "../context/useAuth";
import { ADMIN_SIDEBAR_ITEMS, AdminSidebar } from "./AdminSidebar";
import { authApi, notificationApi, type AppNotification } from "../../services/api";

interface DashboardLayoutProps {
  children: ReactNode;
  menuItems?: Array<{
    icon: any;
    label: string;
    path: string;
  }>;
  userRole: string;
}

export function DashboardLayout({ children, menuItems, userRole }: DashboardLayoutProps) {
  const [sidebarOpen, setSidebarOpen] = useState(() => {
    if (typeof window === "undefined") return true;
    const storedValue = window.localStorage.getItem(`examai-${userRole.toLowerCase()}-sidebar-open`);
    return storedValue ? storedValue === "true" : true;
  });
  const location = useLocation();
  const navigate = useNavigate();
  const { session, clearAuthenticatedSession } = useAuth();
  const isAdminLayout = userRole.toLowerCase() === "admin";
  const sidebarItems = isAdminLayout ? ADMIN_SIDEBAR_ITEMS : menuItems ?? [];
  const dashboardPath = sidebarItems[0]?.path || "/";

  useEffect(() => {
    window.localStorage.setItem(`examai-${userRole.toLowerCase()}-sidebar-open`, String(sidebarOpen));
  }, [sidebarOpen, userRole]);

  const pageTitle = useMemo(() => {
    const sortedItems = [...sidebarItems].sort((a, b) => b.path.length - a.path.length);
    const matchedItem = sortedItems.find((item) => {
      return location.pathname === item.path || location.pathname.startsWith(`${item.path}/`);
    });

    return matchedItem?.label || `${userRole} Dashboard`;
  }, [location.pathname, sidebarItems, userRole]);

  useEffect(() => {
    document.title = `${pageTitle} | ExamAI`;
  }, [pageTitle]);

  const fullName = [session?.user.first_name, session?.user.last_name]
    .filter(Boolean)
    .join(" ")
    .trim();
  const displayName = fullName || session?.user.email?.split("@")[0] || "User";
  const displayEmail = session?.user.email || "";
  const institutionName =
    session?.user.institution?.institution_name ||
    session?.user.institution?.name ||
    "";

  // Notifications State & Polling
  const [notifications, setNotifications] = useState<AppNotification[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [showNotifications, setShowNotifications] = useState(false);
  const prevCountRef = useRef(0);

  const fetchNotifications = async () => {
    if (!session?.access) {
      return;
    }
    try {
      const data = await notificationApi.getNotifications();
      const list = data.notifications || [];
      const unread = data.unread_count || 0;
      setNotifications(list);
      setUnreadCount(unread);

      const prevCount = prevCountRef.current;
      if (unread > prevCount && prevCount > 0) {
        const newest = list[0];
        if (newest && !newest.is_read) {
          if (newest.type === "success") {
            toast.success(newest.title, {
              description: newest.message,
              action: newest.link ? { label: "View", onClick: () => navigate(newest.link!) } : undefined,
            });
          } else if (newest.type === "error") {
            toast.error(newest.title, { description: newest.message });
          } else {
            toast.info(newest.title, { description: newest.message });
          }
        }
      }
      prevCountRef.current = unread;
    } catch (err: any) {
      if (err?.response?.status === 401 || err?.response?.status === 403) {
        // Stop polling on auth failure
        return;
      }
      // Ignore background poll errors
    }
  };

  useEffect(() => {
    if (!session?.access) {
      return;
    }
    let interval: number | null = null;

    const startPolling = () => {
      if (interval === null) {
        interval = window.setInterval(() => {
          if (document.visibilityState === "visible") {
            void fetchNotifications();
          }
        }, 12000);
      }
    };

    const stopPolling = () => {
      if (interval !== null) {
        clearInterval(interval);
        interval = null;
      }
    };

    const handleVisibilityChange = () => {
      if (document.visibilityState === "visible") {
        void fetchNotifications();
        startPolling();
      } else {
        stopPolling();
      }
    };

    if (document.visibilityState === "visible") {
      void fetchNotifications();
      startPolling();
    }

    document.addEventListener("visibilitychange", handleVisibilityChange);
    return () => {
      stopPolling();
      document.removeEventListener("visibilitychange", handleVisibilityChange);
    };
  }, [session?.access]);

  const handleMarkAllRead = async () => {
    try {
      await notificationApi.markAllAsRead();
      setUnreadCount(0);
      setNotifications((prev) => prev.map((n) => ({ ...n, is_read: true })));
    } catch {
      // Ignore
    }
  };

  const handleNotificationClick = async (notif: AppNotification) => {
    if (!notif.is_read) {
      try {
        await notificationApi.markAsRead(notif.id);
        setUnreadCount((c) => Math.max(0, c - 1));
        setNotifications((prev) => prev.map((n) => (n.id === notif.id ? { ...n, is_read: true } : n)));
      } catch {
        // Ignore
      }
    }
    setShowNotifications(false);
    if (notif.link) {
      navigate(notif.link);
    }
  };

  const handleLogout = async () => {
    try {
      await authApi.logout();
    } catch {
      // Fallback
    }
    clearAuthenticatedSession();
    navigate("/", { replace: true });
  };

  return (
    <div className="min-h-screen bg-muted/30">
      {/* Sidebar */}
      <AnimatePresence>
        {sidebarOpen && (
          isAdminLayout ? (
            <AdminSidebar
              open={sidebarOpen}
              onLogout={handleLogout}
              displayName={displayName}
              displayEmail={displayEmail}
              institutionName={institutionName}
            />
          ) : (
            <motion.aside
              initial={{ x: -280 }}
              animate={{ x: 0 }}
              exit={{ x: -280 }}
              transition={{ type: "spring", damping: 25 }}
              className="fixed left-0 top-0 h-full w-70 bg-sidebar border-r border-sidebar-border z-40"
            >
              <div className="flex flex-col h-full">
                <div className="p-6 border-b border-sidebar-border">
                  <Link to="/" className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-primary to-secondary flex items-center justify-center">
                      <Brain className="w-6 h-6 text-white" />
                    </div>
                    <div className="min-w-0">
                      <div className="font-semibold text-sidebar-foreground">ExamAI</div>
                      <div className="text-xs text-muted-foreground flex items-center gap-1 truncate">
                        <span>{userRole}</span>
                        {institutionName && (
                          <span className="text-[11px] text-primary font-medium truncate max-w-[140px]" title={institutionName}>
                            • {institutionName}
                          </span>
                        )}
                      </div>
                    </div>
                  </Link>
                </div>

                <nav className="flex-1 p-4 space-y-1 overflow-y-auto">
                  {sidebarItems.map((item, index) => {
                    const isActive = location.pathname === item.path;
                    return (
                      <Link key={index} to={item.path}>
                        <div
                          className={`flex items-center gap-3 px-4 py-2.5 rounded-lg text-sm font-medium transition-all ${
                            isActive
                              ? "bg-gradient-to-r from-primary to-secondary text-white shadow-sm"
                              : "text-sidebar-foreground hover:bg-sidebar-accent/70 hover:text-foreground"
                          }`}
                        >
                          <item.icon className="w-4 h-4 shrink-0" />
                          <span>{item.label}</span>
                        </div>
                      </Link>
                    );
                  })}
                </nav>

                <div className="p-4 border-t border-sidebar-border">
                  <div className="flex items-center gap-3 px-4 py-3 rounded-lg hover:bg-sidebar-accent/50 transition-colors">
                    <div className="w-8 h-8 rounded-full bg-gradient-to-br from-primary to-secondary flex items-center justify-center">
                      <User className="w-4 h-4 text-white" />
                    </div>
                    <div className="flex-1 text-sm">
                      <div className="font-medium text-sidebar-foreground">{displayName}</div>
                      <div className="text-xs text-muted-foreground">{displayEmail}</div>
                    </div>
                    <button
                      type="button"
                      onClick={handleLogout}
                      className="inline-flex items-center gap-2 rounded-md px-2 py-1 text-xs font-medium text-sidebar-foreground hover:bg-sidebar-accent"
                      aria-label="Logout"
                      title="Logout"
                    >
                      <LogOut className="w-4 h-4 text-muted-foreground" />
                    </button>
                  </div>
                </div>
              </div>
            </motion.aside>
          )
        )}
      </AnimatePresence>

      {/* Mobile Backdrop */}
      <AnimatePresence>
        {sidebarOpen && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/40 backdrop-blur-xs z-30 lg:hidden"
            onClick={() => setSidebarOpen(false)}
            aria-hidden="true"
          />
        )}
      </AnimatePresence>

      {/* Main Content */}
      <div className={`transition-all duration-300 min-w-0 max-w-full ${sidebarOpen ? "lg:ml-70 ml-0" : "ml-0"}`}>
        {/* Top Bar */}
        <header className="sticky top-0 z-20 bg-white border-b border-border">
          <div className="px-3 sm:px-6 py-3 sm:py-4 flex items-center justify-between gap-2 min-w-0">
            <div className="flex items-center gap-2 sm:gap-4 min-w-0">
              <button
                onClick={() => setSidebarOpen(!sidebarOpen)}
                className="p-1.5 sm:p-2 rounded-lg hover:bg-accent transition-colors shrink-0"
                aria-label={sidebarOpen ? "Collapse sidebar" : "Expand sidebar"}
              >
                {sidebarOpen ? <ChevronLeft className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
              </button>
              <Link to={dashboardPath} className="flex items-center gap-2 sm:gap-3 min-w-0">
                <div className="w-7 h-7 sm:w-8 sm:h-8 rounded-lg bg-gradient-to-br from-primary to-secondary flex items-center justify-center shrink-0">
                  <Brain className="w-4 h-4 text-white" />
                </div>
                <div className="min-w-0">
                  <div className="flex items-center gap-1.5 sm:gap-2">
                    <p className="text-xs sm:text-sm font-semibold text-foreground leading-tight">ExamAI</p>
                    {institutionName && (
                      <span className="hidden sm:inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-medium bg-primary/10 text-primary border border-primary/20 truncate max-w-[120px]">
                        {institutionName}
                      </span>
                    )}
                  </div>
                  <p className="text-[11px] sm:text-xs text-muted-foreground leading-tight truncate">{pageTitle}</p>
                </div>
              </Link>
            </div>
            <div className="flex items-center gap-4">
              {/* Notification Bell & Dropdown */}
              <div className="relative">
                <button
                  type="button"
                  onClick={() => setShowNotifications(!showNotifications)}
                  className="p-2 rounded-lg hover:bg-accent transition-colors relative"
                  title="Notifications"
                >
                  <Bell className="w-5 h-5 text-foreground" />
                  {unreadCount > 0 && (
                    <span className="absolute top-1 right-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-rose-600 px-1 text-[10px] font-bold text-white shadow-xs">
                      {unreadCount > 9 ? "9+" : unreadCount}
                    </span>
                  )}
                </button>

                {showNotifications && (
                  <div className="absolute right-0 mt-2 w-80 sm:w-96 rounded-2xl border border-border bg-white shadow-2xl z-50 overflow-hidden animate-in fade-in zoom-in-95 duration-150">
                    <div className="px-4 py-3 border-b border-border bg-muted/30 flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-sm text-foreground">Notifications</span>
                        {unreadCount > 0 && (
                          <span className="bg-primary/10 text-primary text-[11px] font-bold px-2 py-0.5 rounded-full">
                            {unreadCount} new
                          </span>
                        )}
                      </div>
                      {unreadCount > 0 && (
                        <button
                          type="button"
                          onClick={handleMarkAllRead}
                          className="text-xs text-primary hover:underline font-medium"
                        >
                          Mark all as read
                        </button>
                      )}
                    </div>

                    <div className="max-h-80 overflow-y-auto divide-y divide-border/60">
                      {notifications.length === 0 ? (
                        <div className="py-8 text-center text-xs text-muted-foreground">
                          No notifications yet.
                        </div>
                      ) : (
                        notifications.map((notif) => (
                          <div
                            key={notif.id}
                            onClick={() => handleNotificationClick(notif)}
                            className={`p-3.5 hover:bg-muted/40 cursor-pointer transition-colors flex items-start gap-3 ${
                              !notif.is_read ? "bg-primary/5" : ""
                            }`}
                          >
                            <div className="mt-0.5 shrink-0">
                              {notif.type === "success" ? (
                                <CheckCircle2 className="h-4 w-4 text-emerald-600" />
                              ) : notif.type === "error" ? (
                                <AlertCircle className="h-4 w-4 text-rose-600" />
                              ) : (
                                <Info className="h-4 w-4 text-blue-600" />
                              )}
                            </div>
                            <div className="min-w-0 flex-1 space-y-0.5">
                              <p className={`text-xs ${!notif.is_read ? "font-bold text-foreground" : "font-medium text-foreground/80"}`}>
                                {notif.title}
                              </p>
                              <p className="text-[11px] text-muted-foreground line-clamp-2 leading-relaxed">
                                {notif.message}
                              </p>
                            </div>
                            {!notif.is_read && (
                              <span className="w-2 h-2 rounded-full bg-primary shrink-0 mt-1" />
                            )}
                          </div>
                        ))
                      )}
                    </div>
                  </div>
                )}
              </div>

              <button
                type="button"
                onClick={() => navigate(isAdminLayout ? "/admin/settings" : userRole.toLowerCase() === "student" ? "/student/settings" : "/faculty/settings")}
                className="p-2 rounded-lg hover:bg-accent transition-colors"
                title="Settings"
              >
                <Settings className="w-5 h-5 text-foreground" />
              </button>
            </div>
          </div>
        </header>

        {/* Page Content */}
        <main className="p-3.5 sm:p-6 min-w-0 max-w-full">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4 }}
            className="min-w-0 max-w-full"
          >
            {children}
          </motion.div>
        </main>
      </div>
    </div>
  );
}

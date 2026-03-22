import { useEffect, useMemo, useState, ReactNode } from "react";
import { Link, useLocation, useNavigate } from "react-router";
import { motion, AnimatePresence } from "motion/react";
import {
  Brain,
  Menu,
  LogOut,
  Bell,
  Settings,
  User,
  ChevronLeft
} from "lucide-react";
import { authStorage } from "../../services/auth";

interface DashboardLayoutProps {
  children: ReactNode;
  menuItems: Array<{
    icon: any;
    label: string;
    path: string;
  }>;
  userRole: string;
}

export function DashboardLayout({ children, menuItems, userRole }: DashboardLayoutProps) {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const location = useLocation();
  const navigate = useNavigate();
  const session = authStorage.getSession();
  const dashboardPath = menuItems[0]?.path || "/";

  const pageTitle = useMemo(() => {
    const sortedItems = [...menuItems].sort((a, b) => b.path.length - a.path.length);
    const matchedItem = sortedItems.find((item) => {
      return location.pathname === item.path || location.pathname.startsWith(`${item.path}/`);
    });

    return matchedItem?.label || `${userRole} Dashboard`;
  }, [location.pathname, menuItems, userRole]);

  useEffect(() => {
    document.title = `${pageTitle} | ExamAI`;
  }, [pageTitle]);

  const fullName = [session?.user.first_name, session?.user.last_name]
    .filter(Boolean)
    .join(" ")
    .trim();
  const displayName = fullName || session?.user.email?.split("@")[0] || "User";
  const displayEmail = session?.user.email || "";

  const handleLogout = () => {
    authStorage.clearSession();
    navigate("/", { replace: true });
  };

  return (
    <div className="min-h-screen bg-muted/30">
      {/* Sidebar */}
      <AnimatePresence>
        {sidebarOpen && (
          <motion.aside
            initial={{ x: -280 }}
            animate={{ x: 0 }}
            exit={{ x: -280 }}
            transition={{ type: "spring", damping: 25 }}
            className="fixed left-0 top-0 h-full w-70 bg-sidebar border-r border-sidebar-border z-40"
          >
            <div className="flex flex-col h-full">
              {/* Logo */}
              <div className="p-6 border-b border-sidebar-border">
                <Link to="/" className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-primary to-secondary flex items-center justify-center">
                    <Brain className="w-6 h-6 text-white" />
                  </div>
                  <div>
                    <div className="font-semibold text-sidebar-foreground">ExamAI</div>
                    <div className="text-xs text-muted-foreground">{userRole}</div>
                  </div>
                </Link>
              </div>

              {/* Menu Items */}
              <nav className="flex-1 p-4 space-y-1 overflow-y-auto">
                {menuItems.map((item, index) => {
                  const isActive = location.pathname === item.path;
                  return (
                    <Link key={index} to={item.path}>
                      <div
                        className={`flex items-center gap-3 px-4 py-3 rounded-lg transition-all ${
                          isActive
                            ? "bg-sidebar-accent text-sidebar-accent-foreground"
                            : "text-sidebar-foreground hover:bg-sidebar-accent/50"
                        }`}
                      >
                        <item.icon className="w-5 h-5" />
                        <span>{item.label}</span>
                      </div>
                    </Link>
                  );
                })}
              </nav>

              {/* User Section */}
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
        )}
      </AnimatePresence>

      {/* Main Content */}
      <div className={`transition-all duration-300 ${sidebarOpen ? "ml-70" : "ml-0"}`}>
        {/* Top Bar */}
        <header className="sticky top-0 z-30 bg-white border-b border-border">
          <div className="px-6 py-4 flex items-center justify-between">
            <div className="flex items-center gap-4">
              <button
                onClick={() => setSidebarOpen(!sidebarOpen)}
                className="p-2 rounded-lg hover:bg-accent transition-colors"
              >
                {sidebarOpen ? <ChevronLeft className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
              </button>
              <Link to={dashboardPath} className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-primary to-secondary flex items-center justify-center">
                  <Brain className="w-4 h-4 text-white" />
                </div>
                <div className="min-w-0">
                  <p className="text-sm font-semibold text-foreground leading-tight">ExamAI</p>
                  <p className="text-xs text-muted-foreground leading-tight truncate">{pageTitle}</p>
                </div>
              </Link>
            </div>
            <div className="flex items-center gap-4">
              <button className="p-2 rounded-lg hover:bg-accent transition-colors relative">
                <Bell className="w-5 h-5" />
                <span className="absolute top-1 right-1 w-2 h-2 bg-destructive rounded-full"></span>
              </button>
              <button className="p-2 rounded-lg hover:bg-accent transition-colors">
                <Settings className="w-5 h-5" />
              </button>
            </div>
          </div>
        </header>

        {/* Page Content */}
        <main className="p-6">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4 }}
          >
            {children}
          </motion.div>
        </main>
      </div>
    </div>
  );
}

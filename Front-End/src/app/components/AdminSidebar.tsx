import { Link, NavLink } from "react-router";
import { motion } from "motion/react";
import { LayoutDashboard, FileText, Users, Database, Settings, LogOut, User } from "lucide-react";

export const ADMIN_SIDEBAR_ITEMS = [
  { label: "Dashboard", path: "/admin", icon: LayoutDashboard },
  { label: "Exams", path: "/admin/exams", icon: FileText },
  { label: "Students", path: "/admin/students", icon: Users },
  { label: "Faculty", path: "/admin/faculty", icon: Users },
  { label: "Question Bank", path: "/admin/question-bank", icon: Database },
  { label: "Settings", path: "/admin/settings", icon: Settings },
] as const;

export interface AdminSidebarProps {
  open: boolean;
  onLogout: () => void;
  displayName: string;
  displayEmail: string;
}

export function AdminSidebar({ open, onLogout, displayName, displayEmail }: AdminSidebarProps) {
  return (
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
              <LayoutDashboard className="w-6 h-6 text-white" />
            </div>
            <div>
              <div className="font-semibold text-sidebar-foreground">ExamAI</div>
              <div className="text-xs text-muted-foreground">Admin</div>
            </div>
          </Link>
        </div>

        <nav className="flex-1 p-4 space-y-1 overflow-y-auto">
          {ADMIN_SIDEBAR_ITEMS.map((item) => (
            <NavLink key={item.path} to={item.path} end>
              {({ isActive }) => (
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
              )}
            </NavLink>
          ))}
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
              onClick={onLogout}
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
  );
}
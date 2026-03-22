import { useState } from "react";
import { DashboardLayout } from "../components/DashboardLayout";
import { LayoutDashboard, FileText, TrendingUp, Settings, User, Bell, Lock, Globe } from "lucide-react";

const menuItems = [
  { icon: LayoutDashboard, label: "Dashboard", path: "/student" },
  { icon: FileText, label: "Exams", path: "/student/exams" },
  { icon: TrendingUp, label: "Performance", path: "/student/performance" },
  { icon: Settings, label: "Settings", path: "/student/settings" }
];

export function StudentSettings() {
  const [emailNotifications, setEmailNotifications] = useState(true);
  const [examReminders, setExamReminders] = useState(true);
  const [resultNotifications, setResultNotifications] = useState(true);

  return (
    <DashboardLayout menuItems={menuItems} userRole="Student">
      <div className="space-y-6">
        {/* Header */}
        <div>
          <h1 className="text-3xl font-bold text-foreground mb-2">Settings</h1>
          <p className="text-muted-foreground">Manage your account preferences</p>
        </div>

        {/* Profile Settings */}
        <div className="bg-white rounded-xl shadow-sm border border-border">
          <div className="p-6 border-b border-border flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-primary to-secondary flex items-center justify-center">
              <User className="w-5 h-5 text-white" />
            </div>
            <h3 className="font-semibold">Profile Information</h3>
          </div>
          <div className="p-6 space-y-4">
            <div className="grid md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm text-muted-foreground mb-2">Full Name</label>
                <input
                  type="text"
                  defaultValue="John Doe"
                  className="w-full px-4 py-2 rounded-lg border border-border bg-input-background focus:outline-none focus:ring-2 focus:ring-ring"
                />
              </div>
              <div>
                <label className="block text-sm text-muted-foreground mb-2">Email</label>
                <input
                  type="email"
                  defaultValue="john.doe@university.edu"
                  className="w-full px-4 py-2 rounded-lg border border-border bg-input-background focus:outline-none focus:ring-2 focus:ring-ring"
                />
              </div>
            </div>
            <div className="grid md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm text-muted-foreground mb-2">Student ID</label>
                <input
                  type="text"
                  defaultValue="STU-2023-1234"
                  disabled
                  className="w-full px-4 py-2 rounded-lg border border-border bg-muted text-muted-foreground"
                />
              </div>
              <div>
                <label className="block text-sm text-muted-foreground mb-2">Department</label>
                <input
                  type="text"
                  defaultValue="Computer Science"
                  disabled
                  className="w-full px-4 py-2 rounded-lg border border-border bg-muted text-muted-foreground"
                />
              </div>
            </div>
            <div className="pt-4">
              <button className="px-6 py-2 rounded-lg bg-gradient-to-r from-primary to-secondary text-white hover:opacity-90 transition-opacity">
                Save Changes
              </button>
            </div>
          </div>
        </div>

        {/* Notification Settings */}
        <div className="bg-white rounded-xl shadow-sm border border-border">
          <div className="p-6 border-b border-border flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-primary to-secondary flex items-center justify-center">
              <Bell className="w-5 h-5 text-white" />
            </div>
            <h3 className="font-semibold">Notifications</h3>
          </div>
          <div className="p-6 space-y-4">
            <div className="flex items-center justify-between py-3 border-b border-border">
              <div>
                <div className="font-medium text-foreground">Email Notifications</div>
                <div className="text-sm text-muted-foreground">Receive exam updates via email</div>
              </div>
              <button
                onClick={() => setEmailNotifications(!emailNotifications)}
                className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                  emailNotifications ? "bg-primary" : "bg-switch-background"
                }`}
              >
                <span
                  className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                    emailNotifications ? "translate-x-6" : "translate-x-1"
                  }`}
                />
              </button>
            </div>

            <div className="flex items-center justify-between py-3 border-b border-border">
              <div>
                <div className="font-medium text-foreground">Exam Reminders</div>
                <div className="text-sm text-muted-foreground">Get reminded about upcoming exams</div>
              </div>
              <button
                onClick={() => setExamReminders(!examReminders)}
                className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                  examReminders ? "bg-primary" : "bg-switch-background"
                }`}
              >
                <span
                  className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                    examReminders ? "translate-x-6" : "translate-x-1"
                  }`}
                />
              </button>
            </div>

            <div className="flex items-center justify-between py-3">
              <div>
                <div className="font-medium text-foreground">Result Notifications</div>
                <div className="text-sm text-muted-foreground">Notify when results are published</div>
              </div>
              <button
                onClick={() => setResultNotifications(!resultNotifications)}
                className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                  resultNotifications ? "bg-primary" : "bg-switch-background"
                }`}
              >
                <span
                  className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                    resultNotifications ? "translate-x-6" : "translate-x-1"
                  }`}
                />
              </button>
            </div>
          </div>
        </div>

        {/* Security Settings */}
        <div className="bg-white rounded-xl shadow-sm border border-border">
          <div className="p-6 border-b border-border flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-primary to-secondary flex items-center justify-center">
              <Lock className="w-5 h-5 text-white" />
            </div>
            <h3 className="font-semibold">Security</h3>
          </div>
          <div className="p-6 space-y-4">
            <div>
              <label className="block text-sm text-muted-foreground mb-2">Current Password</label>
              <input
                type="password"
                placeholder="••••••••"
                className="w-full px-4 py-2 rounded-lg border border-border bg-input-background focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </div>
            <div className="grid md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm text-muted-foreground mb-2">New Password</label>
                <input
                  type="password"
                  placeholder="••••••••"
                  className="w-full px-4 py-2 rounded-lg border border-border bg-input-background focus:outline-none focus:ring-2 focus:ring-ring"
                />
              </div>
              <div>
                <label className="block text-sm text-muted-foreground mb-2">Confirm Password</label>
                <input
                  type="password"
                  placeholder="••••••••"
                  className="w-full px-4 py-2 rounded-lg border border-border bg-input-background focus:outline-none focus:ring-2 focus:ring-ring"
                />
              </div>
            </div>
            <div className="pt-4">
              <button className="px-6 py-2 rounded-lg bg-gradient-to-r from-primary to-secondary text-white hover:opacity-90 transition-opacity">
                Update Password
              </button>
            </div>
          </div>
        </div>

        {/* Preferences */}
        <div className="bg-white rounded-xl shadow-sm border border-border">
          <div className="p-6 border-b border-border flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-primary to-secondary flex items-center justify-center">
              <Globe className="w-5 h-5 text-white" />
            </div>
            <h3 className="font-semibold">Preferences</h3>
          </div>
          <div className="p-6 space-y-4">
            <div>
              <label className="block text-sm text-muted-foreground mb-2">Language</label>
              <select className="w-full md:w-64 px-4 py-2 rounded-lg border border-border bg-input-background focus:outline-none focus:ring-2 focus:ring-ring">
                <option>English</option>
                <option>Spanish</option>
                <option>French</option>
                <option>German</option>
              </select>
            </div>
            <div>
              <label className="block text-sm text-muted-foreground mb-2">Time Zone</label>
              <select className="w-full md:w-64 px-4 py-2 rounded-lg border border-border bg-input-background focus:outline-none focus:ring-2 focus:ring-ring">
                <option>UTC-05:00 (Eastern Time)</option>
                <option>UTC-06:00 (Central Time)</option>
                <option>UTC-07:00 (Mountain Time)</option>
                <option>UTC-08:00 (Pacific Time)</option>
              </select>
            </div>
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
}

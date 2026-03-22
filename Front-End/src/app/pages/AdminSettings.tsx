import { useState } from "react";
import { DashboardLayout } from "../components/DashboardLayout";
import { LayoutDashboard, FileText, Users, Database, Settings, Building, Bell, Shield, Globe } from "lucide-react";

const menuItems = [
  { icon: LayoutDashboard, label: "Dashboard", path: "/admin" },
  { icon: FileText, label: "Exams", path: "/admin/exams" },
  { icon: Users, label: "Students", path: "/admin/students" },
  { icon: Database, label: "Question Bank", path: "/question-bank" },
  { icon: Settings, label: "Settings", path: "/admin/settings" }
];

export function AdminSettings() {
  const [institutionSettings, setInstitutionSettings] = useState({
    name: "University of Technology",
    code: "UOT-2024",
    address: "123 University Avenue, Tech City",
    phone: "+1 (555) 123-4567",
    email: "admin@university.edu"
  });

  const [examSettings, setExamSettings] = useState({
    defaultDuration: "90",
    autoSubmit: true,
    allowLateSubmission: false,
    proctoring: true
  });

  const [notifications, setNotifications] = useState({
    emailNotifications: true,
    examAlerts: true,
    studentRegistration: true,
    systemUpdates: false
  });

  const [securitySettings, setSecuritySettings] = useState({
    twoFactorAuth: false,
    sessionTimeout: "30",
    passwordExpiry: "90"
  });

  return (
    <DashboardLayout menuItems={menuItems} userRole="Admin">
      <div className="space-y-6">
        {/* Header */}
        <div>
          <h1 className="text-3xl font-bold text-foreground mb-2">Settings</h1>
          <p className="text-muted-foreground">Manage institution and system settings</p>
        </div>

        <div className="grid lg:grid-cols-3 gap-6">
          {/* Sidebar Navigation */}
          <div className="lg:col-span-1">
            <div className="bg-white rounded-xl p-4 shadow-sm border border-border sticky top-6">
              <nav className="space-y-1">
                {[
                  { icon: Building, label: "Institution", id: "institution" },
                  { icon: FileText, label: "Exam Settings", id: "exam" },
                  { icon: Bell, label: "Notifications", id: "notifications" },
                  { icon: Shield, label: "Security", id: "security" }
                ].map((item) => (
                  <button
                    key={item.id}
                    className="w-full flex items-center gap-3 px-4 py-3 rounded-lg hover:bg-muted transition-colors text-left"
                  >
                    <item.icon className="w-5 h-5 text-muted-foreground" />
                    <span className="font-medium">{item.label}</span>
                  </button>
                ))}
              </nav>
            </div>
          </div>

          {/* Main Content */}
          <div className="lg:col-span-2 space-y-6">
            {/* Institution Settings */}
            <div className="bg-white rounded-xl p-6 shadow-sm border border-border">
              <div className="flex items-center gap-3 mb-6">
                <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-primary to-secondary flex items-center justify-center">
                  <Building className="w-5 h-5 text-white" />
                </div>
                <h2 className="text-xl font-semibold">Institution Information</h2>
              </div>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium mb-2">Institution Name</label>
                  <input
                    type="text"
                    value={institutionSettings.name}
                    onChange={(e) => setInstitutionSettings({ ...institutionSettings, name: e.target.value })}
                    className="w-full px-4 py-2.5 rounded-lg border border-border focus:outline-none focus:ring-2 focus:ring-primary/20 transition-all"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-2">Institution Code</label>
                  <input
                    type="text"
                    value={institutionSettings.code}
                    disabled
                    className="w-full px-4 py-2.5 rounded-lg border border-border bg-muted cursor-not-allowed"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-2">Address</label>
                  <input
                    type="text"
                    value={institutionSettings.address}
                    onChange={(e) => setInstitutionSettings({ ...institutionSettings, address: e.target.value })}
                    className="w-full px-4 py-2.5 rounded-lg border border-border focus:outline-none focus:ring-2 focus:ring-primary/20 transition-all"
                  />
                </div>
                <div className="grid sm:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium mb-2">Phone</label>
                    <input
                      type="tel"
                      value={institutionSettings.phone}
                      onChange={(e) => setInstitutionSettings({ ...institutionSettings, phone: e.target.value })}
                      className="w-full px-4 py-2.5 rounded-lg border border-border focus:outline-none focus:ring-2 focus:ring-primary/20 transition-all"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-2">Email</label>
                    <input
                      type="email"
                      value={institutionSettings.email}
                      onChange={(e) => setInstitutionSettings({ ...institutionSettings, email: e.target.value })}
                      className="w-full px-4 py-2.5 rounded-lg border border-border focus:outline-none focus:ring-2 focus:ring-primary/20 transition-all"
                    />
                  </div>
                </div>
                <div className="pt-4">
                  <button className="px-6 py-2.5 rounded-lg bg-gradient-to-r from-primary to-secondary text-white font-semibold hover:shadow-lg transition-all">
                    Save Changes
                  </button>
                </div>
              </div>
            </div>

            {/* Exam Settings */}
            <div className="bg-white rounded-xl p-6 shadow-sm border border-border">
              <div className="flex items-center gap-3 mb-6">
                <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-primary to-secondary flex items-center justify-center">
                  <FileText className="w-5 h-5 text-white" />
                </div>
                <h2 className="text-xl font-semibold">Exam Settings</h2>
              </div>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium mb-2">Default Exam Duration (minutes)</label>
                  <select
                    value={examSettings.defaultDuration}
                    onChange={(e) => setExamSettings({ ...examSettings, defaultDuration: e.target.value })}
                    className="w-full px-4 py-2.5 rounded-lg border border-border focus:outline-none focus:ring-2 focus:ring-primary/20 transition-all"
                  >
                    <option value="45">45 minutes</option>
                    <option value="60">60 minutes</option>
                    <option value="90">90 minutes</option>
                    <option value="120">120 minutes</option>
                    <option value="180">180 minutes</option>
                  </select>
                </div>
                {Object.entries({
                  autoSubmit: "Auto-submit on Time Up",
                  allowLateSubmission: "Allow Late Submissions",
                  proctoring: "Enable Proctoring"
                }).map(([key, label]) => (
                  <label key={key} className="flex items-center justify-between cursor-pointer">
                    <div>
                      <p className="font-medium">{label}</p>
                      <p className="text-sm text-muted-foreground">
                        {key === "autoSubmit" && "Automatically submit exam when time expires"}
                        {key === "allowLateSubmission" && "Allow students to submit after deadline"}
                        {key === "proctoring" && "Enable AI-powered exam proctoring"}
                      </p>
                    </div>
                    <div className="relative">
                      <input
                        type="checkbox"
                        checked={examSettings[key as keyof typeof examSettings] as boolean}
                        onChange={(e) => setExamSettings({
                          ...examSettings,
                          [key]: e.target.checked
                        })}
                        className="sr-only peer"
                      />
                      <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-primary/20 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-primary"></div>
                    </div>
                  </label>
                ))}
              </div>
            </div>

            {/* Notification Settings */}
            <div className="bg-white rounded-xl p-6 shadow-sm border border-border">
              <div className="flex items-center gap-3 mb-6">
                <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-primary to-secondary flex items-center justify-center">
                  <Bell className="w-5 h-5 text-white" />
                </div>
                <h2 className="text-xl font-semibold">Notification Preferences</h2>
              </div>
              <div className="space-y-4">
                {Object.entries({
                  emailNotifications: "Email Notifications",
                  examAlerts: "Exam Alerts",
                  studentRegistration: "Student Registration Alerts",
                  systemUpdates: "System Updates"
                }).map(([key, label]) => (
                  <label key={key} className="flex items-center justify-between cursor-pointer">
                    <div>
                      <p className="font-medium">{label}</p>
                      <p className="text-sm text-muted-foreground">
                        {key === "emailNotifications" && "Receive email notifications for important events"}
                        {key === "examAlerts" && "Get alerts for exam scheduling and completion"}
                        {key === "studentRegistration" && "Alert when new students register"}
                        {key === "systemUpdates" && "Stay informed about system changes"}
                      </p>
                    </div>
                    <div className="relative">
                      <input
                        type="checkbox"
                        checked={notifications[key as keyof typeof notifications]}
                        onChange={(e) => setNotifications({
                          ...notifications,
                          [key]: e.target.checked
                        })}
                        className="sr-only peer"
                      />
                      <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-primary/20 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-primary"></div>
                    </div>
                  </label>
                ))}
              </div>
            </div>

            {/* Security Settings */}
            <div className="bg-white rounded-xl p-6 shadow-sm border border-border">
              <div className="flex items-center gap-3 mb-6">
                <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-primary to-secondary flex items-center justify-center">
                  <Shield className="w-5 h-5 text-white" />
                </div>
                <h2 className="text-xl font-semibold">Security Settings</h2>
              </div>
              <div className="space-y-4">
                <label className="flex items-center justify-between cursor-pointer">
                  <div>
                    <p className="font-medium">Two-Factor Authentication</p>
                    <p className="text-sm text-muted-foreground">Require 2FA for all admin accounts</p>
                  </div>
                  <div className="relative">
                    <input
                      type="checkbox"
                      checked={securitySettings.twoFactorAuth}
                      onChange={(e) => setSecuritySettings({
                        ...securitySettings,
                        twoFactorAuth: e.target.checked
                      })}
                      className="sr-only peer"
                    />
                    <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-primary/20 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-primary"></div>
                  </div>
                </label>
                <div>
                  <label className="block text-sm font-medium mb-2">Session Timeout (minutes)</label>
                  <select
                    value={securitySettings.sessionTimeout}
                    onChange={(e) => setSecuritySettings({ ...securitySettings, sessionTimeout: e.target.value })}
                    className="w-full px-4 py-2.5 rounded-lg border border-border focus:outline-none focus:ring-2 focus:ring-primary/20 transition-all"
                  >
                    <option value="15">15 minutes</option>
                    <option value="30">30 minutes</option>
                    <option value="60">60 minutes</option>
                    <option value="120">120 minutes</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium mb-2">Password Expiry (days)</label>
                  <select
                    value={securitySettings.passwordExpiry}
                    onChange={(e) => setSecuritySettings({ ...securitySettings, passwordExpiry: e.target.value })}
                    className="w-full px-4 py-2.5 rounded-lg border border-border focus:outline-none focus:ring-2 focus:ring-primary/20 transition-all"
                  >
                    <option value="30">30 days</option>
                    <option value="60">60 days</option>
                    <option value="90">90 days</option>
                    <option value="never">Never</option>
                  </select>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
}

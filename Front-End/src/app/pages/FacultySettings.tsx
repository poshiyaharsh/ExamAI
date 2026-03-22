import axios from "axios";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router";
import { DashboardLayout } from "../components/DashboardLayout";
import { LayoutDashboard, FileText, History, Settings, User, Bell, Lock, Eye, EyeOff } from "lucide-react";
import { authAccountApi, facultyProfileApi } from "../../services/api";
import { authStorage } from "../../services/auth";

const menuItems = [
  { icon: LayoutDashboard, label: "Dashboard", path: "/faculty" },
  { icon: FileText, label: "Generate Paper", path: "/faculty/generate" },
  { icon: History, label: "Exam History", path: "/faculty/history" },
  { icon: Settings, label: "Settings", path: "/faculty/settings" }
];

export function FacultySettings() {
  const navigate = useNavigate();
  const [profile, setProfile] = useState({
    name: "",
    email: "",
    department: "",
    employeeId: ""
  });
  const [profileLoading, setProfileLoading] = useState(true);
  const [savingProfile, setSavingProfile] = useState(false);
  const [profileError, setProfileError] = useState("");
  const [profileSuccess, setProfileSuccess] = useState("");

  const [notifications, setNotifications] = useState({
    emailNotifications: true,
    examReminders: true,
    studentSubmissions: false,
    systemUpdates: true
  });

  const [preferences, setPreferences] = useState({
    defaultDuration: "60",
    defaultDifficulty: "medium",
    autoSave: true,
    theme: "light"
  });
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [changingPassword, setChangingPassword] = useState(false);
  const [passwordError, setPasswordError] = useState("");
  const [passwordSuccess, setPasswordSuccess] = useState("");
  const [showCurrentPassword, setShowCurrentPassword] = useState(false);
  const [showNewPassword, setShowNewPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);

  const departmentOptions = [
    "Computer Science",
    "Information Technology",
    "Electronics and Communication",
    "Mechanical Engineering",
    "Civil Engineering",
    "Electrical Engineering",
    "Business Administration",
    "Commerce",
    "Mathematics",
    "Physics",
    "Chemistry",
  ];

  useEffect(() => {
    let isMounted = true;

    const loadProfile = async () => {
      setProfileLoading(true);
      setProfileError("");
      setProfileSuccess("");

      try {
        const response = await facultyProfileApi.getProfile();
        if (!isMounted) {
          return;
        }

        setProfile({
          name: response.data.full_name || "",
          email: response.data.email || "",
          department: response.data.department || "",
          employeeId: response.data.employee_id || "",
        });
      } catch (requestError) {
        if (!isMounted) {
          return;
        }

        if (axios.isAxiosError(requestError)) {
          if (requestError.response?.status === 401) {
            authStorage.clearSession();
            navigate("/login", { replace: true });
            return;
          }

          const apiError = requestError.response?.data as Record<string, unknown> | undefined;
          const apiMessage =
            typeof apiError?.message === "string"
              ? apiError.message
              : typeof apiError?.detail === "string"
                ? apiError.detail
                : "Unable to fetch profile. Please try again.";
          setProfileError(apiMessage);
        } else {
          setProfileError("Unable to fetch profile. Please try again.");
        }
      } finally {
        if (isMounted) {
          setProfileLoading(false);
        }
      }
    };

    void loadProfile();

    return () => {
      isMounted = false;
    };
  }, [navigate]);

  const handleSaveProfile = async () => {
    setProfileError("");
    setProfileSuccess("");

    const cleanedDepartment = profile.department.trim();
    if (!cleanedDepartment) {
      setProfileError("Department must not be empty.");
      return;
    }

    setSavingProfile(true);
    try {
      const response = await facultyProfileApi.updateProfile(cleanedDepartment);
      setProfile((prev) => ({
        ...prev,
        department: response.data.department || cleanedDepartment,
      }));
      setProfileSuccess(response.message || "Department updated successfully.");
    } catch (requestError) {
      if (axios.isAxiosError(requestError)) {
        if (requestError.response?.status === 401) {
          authStorage.clearSession();
          navigate("/login", { replace: true });
          return;
        }

        const apiError = requestError.response?.data as Record<string, unknown> | undefined;
        const apiMessage =
          typeof apiError?.message === "string"
            ? apiError.message
            : Array.isArray(apiError?.department) && typeof apiError.department[0] === "string"
              ? apiError.department[0]
              : typeof apiError?.detail === "string"
                ? apiError.detail
                : "Unable to update department. Please try again.";
        setProfileError(apiMessage);
      } else {
        setProfileError("Unable to update department. Please try again.");
      }
    } finally {
      setSavingProfile(false);
    }
  };

  const handlePasswordUpdate = async () => {
    setPasswordError("");
    setPasswordSuccess("");

    if (!currentPassword || !newPassword || !confirmPassword) {
      setPasswordError("All password fields are required.");
      return;
    }

    if (newPassword.length < 8) {
      setPasswordError("New password must be at least 8 characters long.");
      return;
    }

    const hasLetter = /[A-Za-z]/.test(newPassword);
    const hasNumber = /\d/.test(newPassword);
    if (!hasLetter || !hasNumber) {
      setPasswordError("New password must include at least one letter and one number.");
      return;
    }

    if (newPassword !== confirmPassword) {
      setPasswordError("Confirm Password must match New Password.");
      return;
    }

    setChangingPassword(true);
    try {
      const response = await authAccountApi.changePassword({
        current_password: currentPassword,
        new_password: newPassword,
      });
      setPasswordSuccess(response.message || "Password updated successfully.");
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
    } catch (requestError) {
      if (axios.isAxiosError(requestError)) {
        if (requestError.response?.status === 401) {
          authStorage.clearSession();
          navigate("/login", { replace: true });
          return;
        }

        const apiError = requestError.response?.data as Record<string, unknown> | undefined;
        const apiMessage =
          typeof apiError?.message === "string"
            ? apiError.message
            : Array.isArray(apiError?.new_password) && typeof apiError.new_password[0] === "string"
              ? apiError.new_password[0]
              : Array.isArray(apiError?.current_password) && typeof apiError.current_password[0] === "string"
                ? apiError.current_password[0]
                : typeof apiError?.detail === "string"
                  ? apiError.detail
                  : "Unable to update password. Please try again.";
        setPasswordError(apiMessage);
      } else {
        setPasswordError("Unable to update password. Please try again.");
      }
    } finally {
      setChangingPassword(false);
    }
  };

  return (
    <DashboardLayout menuItems={menuItems} userRole="Faculty">
      <div className="space-y-6">
        {/* Header */}
        <div>
          <h1 className="text-3xl font-bold text-foreground mb-2">Settings</h1>
          <p className="text-muted-foreground">Manage your account and preferences</p>
        </div>

        <div className="grid lg:grid-cols-3 gap-6">
          {/* Sidebar Navigation */}
          <div className="lg:col-span-1">
            <div className="bg-white rounded-xl p-4 shadow-sm border border-border sticky top-6">
              <nav className="space-y-1">
                {[
                  { icon: User, label: "Profile", id: "profile" },
                  { icon: Bell, label: "Notifications", id: "notifications" },
                  { icon: Settings, label: "Preferences", id: "preferences" },
                  { icon: Lock, label: "Security", id: "security" }
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
            {/* Profile Section */}
            <div className="bg-white rounded-xl p-6 shadow-sm border border-border">
              <div className="flex items-center gap-3 mb-6">
                <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-primary to-secondary flex items-center justify-center">
                  <User className="w-5 h-5 text-white" />
                </div>
                <h2 className="text-xl font-semibold">Profile Information</h2>
              </div>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium mb-2">Full Name</label>
                  <input
                    type="text"
                    value={profileLoading ? "Loading..." : profile.name}
                    disabled
                    className="w-full px-4 py-2.5 rounded-lg border border-border bg-muted cursor-not-allowed"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-2">Email</label>
                  <input
                    type="email"
                    value={profileLoading ? "Loading..." : profile.email}
                    disabled
                    className="w-full px-4 py-2.5 rounded-lg border border-border bg-muted cursor-not-allowed"
                  />
                </div>
                <div className="grid sm:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium mb-2">Department</label>
                    <select
                      value={profile.department}
                      onChange={(e) => setProfile({ ...profile, department: e.target.value })}
                      disabled={profileLoading || savingProfile}
                      className="w-full px-4 py-2.5 rounded-lg border border-border focus:outline-none focus:ring-2 focus:ring-primary/20 transition-all"
                    >
                      <option value="">Select Department</option>
                      {departmentOptions.map((department) => (
                        <option key={department} value={department}>
                          {department}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-2">Employee ID</label>
                    <input
                      type="text"
                      value={profileLoading ? "Loading..." : profile.employeeId}
                      disabled
                      className="w-full px-4 py-2.5 rounded-lg border border-border bg-muted cursor-not-allowed"
                    />
                  </div>
                </div>
                {profileError && <p className="text-sm text-destructive">{profileError}</p>}
                {profileSuccess && <p className="text-sm text-green-600">{profileSuccess}</p>}
                <div className="pt-4">
                  <button
                    onClick={handleSaveProfile}
                    disabled={profileLoading || savingProfile}
                    className="px-6 py-2.5 rounded-lg bg-gradient-to-r from-primary to-secondary text-white font-semibold hover:shadow-lg transition-all disabled:opacity-60 disabled:cursor-not-allowed"
                  >
                    {savingProfile ? "Saving..." : "Save Changes"}
                  </button>
                </div>
              </div>
            </div>

            {/* Notifications Section */}
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
                  examReminders: "Exam Reminders",
                  studentSubmissions: "Student Submission Alerts",
                  systemUpdates: "System Updates"
                }).map(([key, label]) => (
                  <label key={key} className="flex items-center justify-between cursor-pointer">
                    <div>
                      <p className="font-medium">{label}</p>
                      <p className="text-sm text-muted-foreground">
                        {key === "emailNotifications" && "Receive email notifications for important updates"}
                        {key === "examReminders" && "Get reminded about upcoming exams"}
                        {key === "studentSubmissions" && "Alert when students submit exams"}
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

            {/* Preferences Section */}
            <div className="bg-white rounded-xl p-6 shadow-sm border border-border">
              <div className="flex items-center gap-3 mb-6">
                <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-primary to-secondary flex items-center justify-center">
                  <Settings className="w-5 h-5 text-white" />
                </div>
                <h2 className="text-xl font-semibold">Exam Preferences</h2>
              </div>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium mb-2">Default Exam Duration (minutes)</label>
                  <select
                    value={preferences.defaultDuration}
                    onChange={(e) => setPreferences({ ...preferences, defaultDuration: e.target.value })}
                    className="w-full px-4 py-2.5 rounded-lg border border-border focus:outline-none focus:ring-2 focus:ring-primary/20 transition-all"
                  >
                    <option value="30">30 minutes</option>
                    <option value="45">45 minutes</option>
                    <option value="60">60 minutes</option>
                    <option value="90">90 minutes</option>
                    <option value="120">120 minutes</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium mb-2">Default Difficulty Level</label>
                  <select
                    value={preferences.defaultDifficulty}
                    onChange={(e) => setPreferences({ ...preferences, defaultDifficulty: e.target.value })}
                    className="w-full px-4 py-2.5 rounded-lg border border-border focus:outline-none focus:ring-2 focus:ring-primary/20 transition-all"
                  >
                    <option value="easy">Easy</option>
                    <option value="medium">Medium</option>
                    <option value="hard">Hard</option>
                  </select>
                </div>
                <label className="flex items-center justify-between cursor-pointer">
                  <div>
                    <p className="font-medium">Auto-save Progress</p>
                    <p className="text-sm text-muted-foreground">Automatically save your work while creating exams</p>
                  </div>
                  <div className="relative">
                    <input
                      type="checkbox"
                      checked={preferences.autoSave}
                      onChange={(e) => setPreferences({
                        ...preferences,
                        autoSave: e.target.checked
                      })}
                      className="sr-only peer"
                    />
                    <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-primary/20 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-primary"></div>
                  </div>
                </label>
              </div>
            </div>

            {/* Security Section */}
            <div className="bg-white rounded-xl p-6 shadow-sm border border-border">
              <div className="flex items-center gap-3 mb-6">
                <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-primary to-secondary flex items-center justify-center">
                  <Lock className="w-5 h-5 text-white" />
                </div>
                <h2 className="text-xl font-semibold">Security</h2>
              </div>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium mb-2">Current Password</label>
                  <div className="relative">
                    <input
                      type={showCurrentPassword ? "text" : "password"}
                      placeholder="Enter current password"
                      value={currentPassword}
                      onChange={(event) => setCurrentPassword(event.target.value)}
                      className="w-full px-4 py-2.5 rounded-lg border border-border focus:outline-none focus:ring-2 focus:ring-primary/20 transition-all pr-10"
                    />
                    <button
                      type="button"
                      onClick={() => setShowCurrentPassword((prev) => !prev)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground"
                    >
                      {showCurrentPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                    </button>
                  </div>
                </div>
                <div>
                  <label className="block text-sm font-medium mb-2">New Password</label>
                  <div className="relative">
                    <input
                      type={showNewPassword ? "text" : "password"}
                      placeholder="Enter new password"
                      value={newPassword}
                      onChange={(event) => setNewPassword(event.target.value)}
                      className="w-full px-4 py-2.5 rounded-lg border border-border focus:outline-none focus:ring-2 focus:ring-primary/20 transition-all pr-10"
                    />
                    <button
                      type="button"
                      onClick={() => setShowNewPassword((prev) => !prev)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground"
                    >
                      {showNewPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                    </button>
                  </div>
                </div>
                <div>
                  <label className="block text-sm font-medium mb-2">Confirm New Password</label>
                  <div className="relative">
                    <input
                      type={showConfirmPassword ? "text" : "password"}
                      placeholder="Confirm new password"
                      value={confirmPassword}
                      onChange={(event) => setConfirmPassword(event.target.value)}
                      className="w-full px-4 py-2.5 rounded-lg border border-border focus:outline-none focus:ring-2 focus:ring-primary/20 transition-all pr-10"
                    />
                    <button
                      type="button"
                      onClick={() => setShowConfirmPassword((prev) => !prev)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground"
                    >
                      {showConfirmPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                    </button>
                  </div>
                </div>
                {passwordError && <p className="text-sm text-destructive">{passwordError}</p>}
                {passwordSuccess && <p className="text-sm text-green-600">{passwordSuccess}</p>}
                <div className="pt-4">
                  <button
                    onClick={handlePasswordUpdate}
                    disabled={changingPassword}
                    className="px-6 py-2.5 rounded-lg bg-gradient-to-r from-primary to-secondary text-white font-semibold hover:shadow-lg transition-all disabled:opacity-60 disabled:cursor-not-allowed"
                  >
                    {changingPassword ? "Updating..." : "Update Password"}
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
}

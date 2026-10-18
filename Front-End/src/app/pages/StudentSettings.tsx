import axios from "axios";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { DashboardLayout } from "../components/DashboardLayout";
import { LayoutDashboard, FileText, TrendingUp, Settings, User, Bell, Lock, Eye, EyeOff } from "lucide-react";
import { authAccountApi, studentProfileApi } from "../../services/api";
import { authStorage } from "../../services/auth";

const menuItems = [
  { icon: LayoutDashboard, label: "Dashboard", path: "/student" },
  { icon: FileText, label: "Exams", path: "/student/exams" },
  { icon: TrendingUp, label: "Performance", path: "/student/performance" },
  { icon: Settings, label: "Settings", path: "/student/settings" }
];

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

function extractApiErrorMessage(apiError: unknown): string | null {
  if (!apiError || typeof apiError !== "object") {
    return null;
  }

  const record = apiError as Record<string, unknown>;

  if (typeof record.detail === "string") {
    return record.detail;
  }

  if (typeof record.message === "string") {
    return record.message;
  }

  const firstFieldError = Object.values(record).find((value) => {
    if (typeof value === "string") {
      return true;
    }
    return Array.isArray(value) && typeof value[0] === "string";
  });

  if (typeof firstFieldError === "string") {
    return firstFieldError;
  }

  if (Array.isArray(firstFieldError) && typeof firstFieldError[0] === "string") {
    return firstFieldError[0];
  }

  return null;
}

export function StudentSettings() {
  const navigate = useNavigate();
  const [profileLoading, setProfileLoading] = useState(true);
  const [savingProfile, setSavingProfile] = useState(false);
  const [profileError, setProfileError] = useState("");
  const [profileSuccess, setProfileSuccess] = useState("");
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [studentId, setStudentId] = useState("");
  const [department, setDepartment] = useState("");
  const [institutionName, setInstitutionName] = useState("");

  const [emailNotifications, setEmailNotifications] = useState(true);
  const [examReminders, setExamReminders] = useState(true);
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [changingPassword, setChangingPassword] = useState(false);
  const [passwordError, setPasswordError] = useState("");
  const [passwordSuccess, setPasswordSuccess] = useState("");
  const [showCurrentPassword, setShowCurrentPassword] = useState(false);
  const [showNewPassword, setShowNewPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);

  useEffect(() => {
    let isMounted = true;

    const loadProfile = async () => {
      setProfileLoading(true);
      setProfileError("");

      try {
        const response = await studentProfileApi.getProfile();
        if (!isMounted) {
          return;
        }

        setFullName(response.data.full_name || "");
        setEmail(response.data.email || "");
        setStudentId(response.data.student_id || "");
        setDepartment(response.data.department || "");
        setInstitutionName(response.data.institution?.institution_name || "");
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

          const extracted = extractApiErrorMessage(requestError.response?.data);
          setProfileError(extracted ?? "Unable to fetch profile. Please try again.");
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

  const handleProfileSave = async () => {
    setProfileError("");
    setProfileSuccess("");

    const cleanedDepartment = department.trim();
    if (!cleanedDepartment) {
      setProfileError("Department must not be empty.");
      return;
    }

    setSavingProfile(true);
    try {
      const response = await studentProfileApi.updateProfile(cleanedDepartment);
      setDepartment(response.data.department || cleanedDepartment);
      setProfileSuccess(response.message || "Department updated successfully.");
    } catch (requestError) {
      if (axios.isAxiosError(requestError)) {
        if (requestError.response?.status === 401) {
          authStorage.clearSession();
          navigate("/login", { replace: true });
          return;
        }

        const extracted = extractApiErrorMessage(requestError.response?.data);
        setProfileError(extracted ?? "Unable to update department. Please try again.");
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

        const extracted = extractApiErrorMessage(requestError.response?.data);
        setPasswordError(extracted ?? "Unable to update password. Please try again.");
      } else {
        setPasswordError("Unable to update password. Please try again.");
      }
    } finally {
      setChangingPassword(false);
    }
  };

  return (
    <DashboardLayout menuItems={menuItems} userRole="Student">
      <div className="space-y-6">
        {/* Header */}
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold text-foreground mb-1">Settings</h1>
          <p className="text-xs sm:text-sm text-muted-foreground">Manage your account preferences</p>
        </div>

        {/* Profile Settings */}
        <div className="bg-white rounded-xl shadow-sm border border-border overflow-hidden">
          <div className="p-5 sm:p-6 border-b border-border flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-primary to-secondary flex items-center justify-center text-white shadow-xs">
              <User className="w-5 h-5" />
            </div>
            <h3 className="font-semibold text-lg text-foreground">Profile Information</h3>
          </div>
          <div className="p-5 sm:p-6 space-y-3.5">
            <div className="grid md:grid-cols-2 gap-3.5">
              <div>
                <label className="block text-xs font-medium text-foreground mb-1.5">Full Name</label>
                <input
                  type="text"
                  value={profileLoading ? "Loading..." : fullName}
                  disabled
                  className="w-full px-3.5 py-2 rounded-lg border border-border bg-muted/50 text-muted-foreground text-sm cursor-not-allowed"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-foreground mb-1.5">Email</label>
                <input
                  type="email"
                  value={profileLoading ? "Loading..." : email}
                  disabled
                  className="w-full px-3.5 py-2 rounded-lg border border-border bg-muted/50 text-muted-foreground text-sm cursor-not-allowed"
                />
              </div>
            </div>
            <div className="grid md:grid-cols-2 gap-3.5">
              <div>
                <label className="block text-xs font-medium text-foreground mb-1.5">Student ID</label>
                <input
                  type="text"
                  value={profileLoading ? "Loading..." : studentId}
                  disabled
                  className="w-full px-3.5 py-2 rounded-lg border border-border bg-muted/50 text-muted-foreground text-sm cursor-not-allowed"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-foreground mb-1.5 flex items-center justify-between">
                  <span>Department</span>
                  {department && department !== "Unassigned" && (
                    <span className="inline-flex items-center gap-1 text-[11px] text-muted-foreground font-normal">
                      <Lock className="w-3 h-3 text-muted-foreground" />
                      Locked
                    </span>
                  )}
                </label>
                {department && department !== "Unassigned" ? (
                  <div>
                    <div className="relative">
                      <input
                        type="text"
                        value={profileLoading ? "Loading..." : department}
                        disabled
                        className="w-full px-3.5 py-2 pl-9 rounded-lg border border-border bg-muted/40 text-foreground text-sm cursor-not-allowed font-medium"
                      />
                      <Lock className="w-4 h-4 text-muted-foreground absolute left-3 top-1/2 -translate-y-1/2" />
                    </div>
                    <p className="text-[11px] text-muted-foreground mt-1 flex items-center gap-1">
                      Department cannot be changed. Contact admin.
                    </p>
                  </div>
                ) : (
                  <div>
                    <select
                      value={department}
                      onChange={(event) => setDepartment(event.target.value)}
                      disabled={profileLoading || savingProfile}
                      className="w-full px-3.5 py-2 rounded-lg border border-border bg-input-background text-sm focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-all disabled:bg-muted/50 disabled:text-muted-foreground"
                    >
                      <option value="">Select Department (Required)</option>
                      {departmentOptions.map((item) => (
                        <option key={item} value={item}>
                          {item}
                        </option>
                      ))}
                    </select>
                    <p className="text-[11px] text-amber-600 mt-1">
                      Pick your department once. Once saved, it will be locked permanently.
                    </p>
                  </div>
                )}
              </div>
            </div>
            <div>
              <label className="block text-xs font-medium text-foreground mb-1.5">Institution</label>
              <input
                type="text"
                value={profileLoading ? "Loading..." : institutionName}
                disabled
                className="w-full px-3.5 py-2 rounded-lg border border-border bg-muted/50 text-muted-foreground text-sm cursor-not-allowed"
              />
            </div>
            {profileError && <p className="text-xs sm:text-sm text-destructive font-medium">{profileError}</p>}
            {profileSuccess && <p className="text-xs sm:text-sm text-emerald-600 font-medium">{profileSuccess}</p>}
            {(!department || department === "Unassigned") && (
              <div className="pt-2">
                <button
                  onClick={handleProfileSave}
                  disabled={profileLoading || savingProfile || !department || department === "Unassigned"}
                  className="px-5 py-2.5 rounded-lg bg-gradient-to-r from-primary to-secondary text-white font-medium text-sm hover:opacity-90 shadow-md transition-all disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {savingProfile ? "Saving..." : "Lock & Save Department"}
                </button>
              </div>
            )}
          </div>
        </div>

        {/* Notification Settings */}
        <div className="bg-white rounded-xl shadow-sm border border-border overflow-hidden">
          <div className="p-5 sm:p-6 border-b border-border flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-primary to-secondary flex items-center justify-center text-white shadow-xs">
              <Bell className="w-5 h-5" />
            </div>
            <h3 className="font-semibold text-lg text-foreground">Notifications</h3>
          </div>
          <div className="p-5 sm:p-6 space-y-3">
            <div className="flex items-center justify-between py-2 border-b border-border">
              <div>
                <div className="text-sm font-medium text-foreground">Email Notifications</div>
                <div className="text-xs text-muted-foreground">Receive exam updates via email</div>
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

            <div className="flex items-center justify-between py-2">
              <div>
                <div className="text-sm font-medium text-foreground">Exam Reminders</div>
                <div className="text-xs text-muted-foreground">Get reminded about upcoming exams</div>
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
          </div>
        </div>

        {/* Security Settings */}
        <div className="bg-white rounded-xl shadow-sm border border-border overflow-hidden">
          <div className="p-5 sm:p-6 border-b border-border flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-primary to-secondary flex items-center justify-center text-white shadow-xs">
              <Lock className="w-5 h-5" />
            </div>
            <h3 className="font-semibold text-lg text-foreground">Security</h3>
          </div>
          <div className="p-5 sm:p-6 space-y-3.5">
            <div>
              <label className="block text-xs font-medium text-foreground mb-1.5">Current Password</label>
              <div className="relative">
                <input
                  type={showCurrentPassword ? "text" : "password"}
                  placeholder="••••••••"
                  value={currentPassword}
                  onChange={(event) => setCurrentPassword(event.target.value)}
                  className="w-full px-3.5 py-2 rounded-lg border border-border bg-input-background text-sm focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-all pr-10"
                />
                <button
                  type="button"
                  onClick={() => setShowCurrentPassword((prev) => !prev)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
                >
                  {showCurrentPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>
            <div className="grid md:grid-cols-2 gap-3.5">
              <div>
                <label className="block text-xs font-medium text-foreground mb-1.5">New Password</label>
                <div className="relative">
                  <input
                    type={showNewPassword ? "text" : "password"}
                    placeholder="••••••••"
                    value={newPassword}
                    onChange={(event) => setNewPassword(event.target.value)}
                    className="w-full px-3.5 py-2 rounded-lg border border-border bg-input-background text-sm focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-all pr-10"
                  />
                  <button
                    type="button"
                    onClick={() => setShowNewPassword((prev) => !prev)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
                  >
                    {showNewPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>
              <div>
                <label className="block text-xs font-medium text-foreground mb-1.5">Confirm Password</label>
                <div className="relative">
                  <input
                    type={showConfirmPassword ? "text" : "password"}
                    placeholder="••••••••"
                    value={confirmPassword}
                    onChange={(event) => setConfirmPassword(event.target.value)}
                    className="w-full px-3.5 py-2 rounded-lg border border-border bg-input-background text-sm focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-all pr-10"
                  />
                  <button
                    type="button"
                    onClick={() => setShowConfirmPassword((prev) => !prev)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
                  >
                    {showConfirmPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>
            </div>
            {passwordError && <p className="text-xs sm:text-sm text-destructive font-medium">{passwordError}</p>}
            {passwordSuccess && <p className="text-xs sm:text-sm text-emerald-600 font-medium">{passwordSuccess}</p>}
            <div className="pt-2">
              <button
                onClick={handlePasswordUpdate}
                disabled={changingPassword}
                className="px-5 py-2.5 rounded-lg bg-gradient-to-r from-primary to-secondary text-white font-medium text-sm hover:opacity-90 shadow-md transition-all disabled:cursor-not-allowed disabled:opacity-60"
              >
                {changingPassword ? "Updating..." : "Update Password"}
              </button>
            </div>
          </div>
        </div>

      </div>
    </DashboardLayout>
  );
}

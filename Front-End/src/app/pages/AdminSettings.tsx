import axios from "axios";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { DashboardLayout } from "../components/DashboardLayout";
import { Building, Bell, Shield, Globe, FileText } from "lucide-react";
import { adminInstitutionApi } from "../../services/api";
import { authStorage } from "../../services/auth";

export function AdminSettings() {
  const navigate = useNavigate();
  const [institutionSettings, setInstitutionSettings] = useState({
    name: "",
    code: "",
    address: "",
    phone: "",
    email: ""
  });
  const [institutionExists, setInstitutionExists] = useState(false);
  const [institutionLoading, setInstitutionLoading] = useState(true);
  const [institutionSaving, setInstitutionSaving] = useState(false);
  const [institutionError, setInstitutionError] = useState("");
  const [institutionSuccess, setInstitutionSuccess] = useState("");

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

  useEffect(() => {
    let isMounted = true;

    const loadInstitution = async () => {
      setInstitutionLoading(true);
      setInstitutionError("");
      setInstitutionSuccess("");

      try {
        const response = await adminInstitutionApi.getInstitution();
        if (!isMounted) {
          return;
        }

        setInstitutionExists(response.exists);
        setInstitutionSettings({
          name: response.data.institution_name || "",
          code: response.data.institution_code || "",
          address: response.data.address || "",
          phone: response.data.phone || "",
          email: response.data.email || "",
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
          const message =
            typeof apiError?.message === "string"
              ? apiError.message
              : typeof apiError?.detail === "string"
                ? apiError.detail
                : "Unable to fetch institution information. Please try again.";
          setInstitutionError(message);
        } else {
          setInstitutionError("Unable to fetch institution information. Please try again.");
        }
      } finally {
        if (isMounted) {
          setInstitutionLoading(false);
        }
      }
    };

    void loadInstitution();

    return () => {
      isMounted = false;
    };
  }, [navigate]);

  const handleSaveInstitution = async () => {
    setInstitutionError("");
    setInstitutionSuccess("");

    const institutionName = institutionSettings.name.trim();
    const phone = institutionSettings.phone.trim();

    if (!institutionName) {
      setInstitutionError("Institution Name is required.");
      return;
    }

    const phonePattern = /^\+?[0-9()\-\s]{7,20}$/;
    if (phone && !phonePattern.test(phone)) {
      setInstitutionError("Enter a valid phone number.");
      return;
    }

    setInstitutionSaving(true);
    try {
      const payload = {
        institution_name: institutionName,
        address: institutionSettings.address,
        phone,
      };

      const response = institutionExists
        ? await adminInstitutionApi.updateInstitution(payload)
        : await adminInstitutionApi.createInstitution(payload);

      setInstitutionExists(true);
      setInstitutionSettings({
        name: response.data.institution_name || "",
        code: response.data.institution_code || "",
        address: response.data.address || "",
        phone: response.data.phone || "",
        email: response.data.email || "",
      });
      setInstitutionSuccess(response.message || "Institution information saved successfully.");
    } catch (requestError) {
      if (axios.isAxiosError(requestError)) {
        if (requestError.response?.status === 401) {
          authStorage.clearSession();
          navigate("/login", { replace: true });
          return;
        }

        const apiError = requestError.response?.data as Record<string, unknown> | undefined;
        const message =
          typeof apiError?.message === "string"
            ? apiError.message
            : Array.isArray(apiError?.phone) && typeof apiError.phone[0] === "string"
              ? apiError.phone[0]
              : Array.isArray(apiError?.institution_name) && typeof apiError.institution_name[0] === "string"
                ? apiError.institution_name[0]
                : typeof apiError?.detail === "string"
                  ? apiError.detail
                  : "Unable to save institution information. Please try again.";
        setInstitutionError(message);
      } else {
        setInstitutionError("Unable to save institution information. Please try again.");
      }
    } finally {
      setInstitutionSaving(false);
    }
  };

  return (
    <DashboardLayout userRole="Admin">
      <div className="space-y-6">
        {/* Header */}
        <div>
          <h1 className="text-3xl font-bold text-foreground mb-2">Settings</h1>
          <p className="text-muted-foreground">Manage institution and system settings</p>
        </div>

        <div className="grid gap-6">
          {/* Main Content - full width (removed left settings submenu) */}
          <div className="space-y-6">
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
                    disabled={institutionLoading || institutionSaving}
                    className="w-full px-4 py-2.5 rounded-lg border border-border focus:outline-none focus:ring-2 focus:ring-primary/20 transition-all"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-2">Institution Code</label>
                  <input
                    type="text"
                    value={institutionLoading ? "Loading..." : institutionSettings.code}
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
                    disabled={institutionLoading || institutionSaving}
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
                      disabled={institutionLoading || institutionSaving}
                      className="w-full px-4 py-2.5 rounded-lg border border-border focus:outline-none focus:ring-2 focus:ring-primary/20 transition-all"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-2">Email</label>
                    <input
                      type="email"
                      value={institutionLoading ? "Loading..." : institutionSettings.email}
                      disabled
                      className="w-full px-4 py-2.5 rounded-lg border border-border bg-muted cursor-not-allowed"
                    />
                  </div>
                </div>
                {institutionError && <p className="text-sm text-destructive">{institutionError}</p>}
                {institutionSuccess && <p className="text-sm text-green-600">{institutionSuccess}</p>}
                <div className="pt-4">
                  <button
                    onClick={handleSaveInstitution}
                    disabled={institutionLoading || institutionSaving}
                    className="px-6 py-2.5 rounded-lg bg-gradient-to-r from-primary to-secondary text-white font-semibold hover:shadow-lg transition-all disabled:opacity-60 disabled:cursor-not-allowed"
                  >
                    {institutionSaving ? "Saving..." : "Save Changes"}
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

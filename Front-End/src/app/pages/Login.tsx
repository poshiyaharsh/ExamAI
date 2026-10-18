import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "motion/react";
import { Brain, Eye, EyeOff, User, Mail, Lock, Building2, GraduationCap, Briefcase, Shield, CheckCircle2 } from "lucide-react";
import axios from "axios";

import { authApi, institutionsApi, departmentsApi, type DepartmentOption, type InstitutionOption, type UserRole } from "../../services/api";
import { useAuth } from "../context/useAuth";

function extractApiErrorMessage(apiError: unknown): string | null {
  if (!apiError) {
    return null;
  }

  if (typeof apiError === "string") {
    return apiError;
  }

  if (typeof apiError !== "object") {
    return null;
  }

  const record = apiError as Record<string, unknown>;

  if (typeof record.detail === "string") {
    return record.detail;
  }

  if (typeof record.message === "string") {
    return record.message;
  }

  if (Array.isArray(record.non_field_errors) && typeof record.non_field_errors[0] === "string") {
    return record.non_field_errors[0];
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

export function Login() {
  const navigate = useNavigate();
  const { setAuthenticatedSession } = useAuth();
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [role, setRole] = useState<UserRole>("student");
  const [isLogin, setIsLogin] = useState(true);
  const [acceptTerms, setAcceptTerms] = useState(false);
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [institutions, setInstitutions] = useState<InstitutionOption[]>([]);
  const [selectedInstitutionId, setSelectedInstitutionId] = useState("");
  const [institutionsLoading, setInstitutionsLoading] = useState(false);
  const [departments, setDepartments] = useState<DepartmentOption[]>([]);
  const [selectedDepartment, setSelectedDepartment] = useState("");
  const [departmentsLoading, setDepartmentsLoading] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [successMessage, setSuccessMessage] = useState("");

  useEffect(() => {
    document.title = `${isLogin ? "Sign In" : "Sign Up"} | ExamAI`;
  }, [isLogin]);

  useEffect(() => {
    let isMounted = true;

    const loadInstitutions = async () => {
      setInstitutionsLoading(true);
      try {
        const response = await institutionsApi.getInstitutions();
        if (!isMounted) {
          return;
        }
        setInstitutions(response.data || []);
      } catch {
        if (!isMounted) {
          return;
        }
        setInstitutions([]);
      } finally {
        if (isMounted) {
          setInstitutionsLoading(false);
        }
      }
    };

    void loadInstitutions();

    return () => {
      isMounted = false;
    };
  }, []);

  useEffect(() => {
    if (isLogin || (role !== "student" && role !== "faculty")) {
      return;
    }

    let isMounted = true;
    const loadDepartments = async () => {
      setDepartmentsLoading(true);
      try {
        const instId = selectedInstitutionId ? Number(selectedInstitutionId) : undefined;
        const response = await departmentsApi.getDepartments(instId);
        if (isMounted) {
          setDepartments(response.data || []);
          // Reset selected department if it is not in the new list
          if (selectedDepartment && response.data && !response.data.some((d) => d.department_name === selectedDepartment)) {
            setSelectedDepartment("");
          }
        }
      } catch {
        if (isMounted) {
          setDepartments([]);
        }
      } finally {
        if (isMounted) {
          setDepartmentsLoading(false);
        }
      }
    };

    void loadDepartments();

    return () => {
      isMounted = false;
    };
  }, [isLogin, role, selectedInstitutionId]);

  const navigateByRole = (userRole: UserRole) => {
    switch (userRole) {
      case "admin":
        navigate("/admin");
        break;
      case "faculty":
        navigate("/faculty");
        break;
      default:
        navigate("/student");
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setSuccessMessage("");

    if (!isLogin) {
      if ((role === "student" || role === "faculty")) {
        if (!selectedInstitutionId) {
          setError("Please select an institution.");
          return;
        }
        if (!selectedDepartment) {
          setError("Please select your department.");
          return;
        }
      }

      if (password !== confirmPassword) {
        setError("Passwords do not match.");
        return;
      }

      if (!acceptTerms) {
        setError("Please accept Terms of Service and Privacy Policy.");
        return;
      }
    }

    setLoading(true);

    try {
      if (isLogin) {
        const response = await authApi.login(role, {
          email,
          password,
        });
        setAuthenticatedSession({
          access: response.tokens.access,
          refresh: response.tokens.refresh,
          role: response.user.role,
          user: {
            id: response.user.id,
            first_name: response.user.first_name,
            last_name: response.user.last_name,
            email: response.user.email,
          },
        });
        setSuccessMessage(response.message);
        navigateByRole(response.user.role);
      } else {
        const response = await authApi.signup(role, {
          first_name: firstName,
          last_name: lastName,
          email,
          password,
          institution_id:
            role === "student" || role === "faculty"
              ? Number(selectedInstitutionId)
              : undefined,
          department:
            role === "student" || role === "faculty"
              ? selectedDepartment
              : undefined,
        });
        setAuthenticatedSession({
          access: response.tokens.access,
          refresh: response.tokens.refresh,
          role: response.user.role,
          user: {
            id: response.user.id,
            first_name: response.user.first_name,
            last_name: response.user.last_name,
            email: response.user.email,
          },
        });
        setSuccessMessage(response.message);
        navigateByRole(response.user.role);
      }
    } catch (requestError) {
      if (axios.isAxiosError(requestError)) {
        if (!requestError.response) {
          setError("Cannot connect to backend server. Start Django on http://127.0.0.1:8000 and try again.");
          return;
        }

        const apiError = requestError.response?.data;
        const extracted = extractApiErrorMessage(apiError);
        setError(extracted ?? "Authentication failed. Please try again.");
      } else {
        setError("Something went wrong. Please try again.");
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-primary via-secondary to-primary flex items-center justify-center p-3 sm:p-5">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6 }}
        className="w-full max-w-[460px]"
      >
        {/* Logo */}
        <div className="text-center mb-3 sm:mb-4">
          <Link to="/" className="inline-block">
            <div className="inline-flex items-center gap-2 mb-1.5">
              <div className="w-9 h-9 rounded-lg bg-white flex items-center justify-center shadow-sm">
                <Brain className="w-5 h-5 text-primary" />
              </div>
              <span className="text-xl sm:text-2xl font-bold text-white tracking-tight">ExamAI</span>
            </div>
          </Link>
          <h1 className="text-2xl sm:text-3xl font-bold text-white">
            {isLogin ? "Welcome Back" : "Create Your Account"}
          </h1>
          <p className="text-xs sm:text-sm text-indigo-100 mt-0.5">
            {isLogin ? "Sign in to continue to ExamAI Platform" : "Join the AI-powered exam management platform"}
          </p>
        </div>

        {/* Login/Signup Card */}
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: 0.2 }}
          className="bg-white rounded-2xl shadow-2xl p-5 sm:p-6"
        >
          <form onSubmit={handleSubmit} className="space-y-3 sm:space-y-3.5">
            {/* Role Selector */}
            <div>
              <label className="block text-xs sm:text-sm font-medium mb-1.5 text-foreground flex items-center gap-1.5">
                <Shield className="w-3.5 h-3.5 text-primary" />
                Select Your Role
              </label>
              <div className="grid grid-cols-3 gap-2.5">
                {[
                  { value: "student", label: "Student", icon: GraduationCap },
                  { value: "faculty", label: "Faculty", icon: Briefcase },
                  { value: "admin", label: "Admin", icon: Building2 }
                ].map((roleOption) => (
                  <motion.button
                    key={roleOption.value}
                    type="button"
                    onClick={() => setRole(roleOption.value as UserRole)}
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.98 }}
                    className={`py-2 px-3 rounded-lg border-2 transition-all flex flex-col items-center justify-center ${
                      role === roleOption.value
                        ? "border-primary bg-primary/5"
                        : "border-border hover:border-primary/50"
                    }`}
                  >
                    <roleOption.icon className={`w-5 h-5 mx-auto mb-1 ${role === roleOption.value ? "text-primary" : "text-muted-foreground"}`} />
                    <div className={`text-xs sm:text-sm font-medium ${role === roleOption.value ? "text-primary" : "text-foreground"}`}>
                      {roleOption.label}
                    </div>
                  </motion.button>
                ))}
              </div>
            </div>

            {!isLogin && (role === "student" || role === "faculty") && (
              <div>
                <label className="block text-xs sm:text-sm font-medium mb-1 text-foreground flex items-center gap-1.5">
                  <Building2 className="w-3.5 h-3.5 text-primary" />
                  Institution
                </label>
                <select
                  value={selectedInstitutionId}
                  onChange={(event) => setSelectedInstitutionId(event.target.value)}
                  disabled={institutionsLoading}
                  className="w-full px-3.5 py-2 rounded-lg bg-input-background border border-border text-sm focus:outline-none focus:ring-2 focus:ring-primary transition-all"
                  required
                >
                  <option value="">{institutionsLoading ? "Loading institutions..." : "Select institution"}</option>
                  {institutions.map((institution) => (
                    <option key={institution.id} value={institution.id}>
                      {institution.institution_name} ({institution.institution_code})
                    </option>
                  ))}
                </select>
              </div>
            )}

            {!isLogin && (role === "student" || role === "faculty") && (
              <div>
                <label className="block text-xs sm:text-sm font-medium mb-1 text-foreground flex items-center gap-1.5">
                  <GraduationCap className="w-3.5 h-3.5 text-primary" />
                  Department
                </label>
                <select
                  value={selectedDepartment}
                  onChange={(event) => setSelectedDepartment(event.target.value)}
                  disabled={departmentsLoading}
                  className="w-full px-3.5 py-2 rounded-lg bg-input-background border border-border text-sm focus:outline-none focus:ring-2 focus:ring-primary transition-all"
                  required
                >
                  <option value="">
                    {departmentsLoading
                      ? "Loading departments..."
                      : selectedInstitutionId
                      ? "Select department"
                      : "Select an institution first"}
                  </option>
                  {departments.map((dept) => (
                    <option key={dept.id} value={dept.department_name}>
                      {dept.department_name}
                    </option>
                  ))}
                </select>
                <p className="text-[11px] text-muted-foreground mt-1">
                  Note: Department is permanent and cannot be changed after sign-up.
                </p>
              </div>
            )}

            <AnimatePresence mode="wait">
              {!isLogin && (
                <motion.div
                  key="signup-fields"
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: "auto" }}
                  exit={{ opacity: 0, height: 0 }}
                  transition={{ duration: 0.2 }}
                  className="grid grid-cols-2 gap-3"
                >
                  {/* Full Name */}
                  <div>
                    <label className="block text-xs sm:text-sm font-medium mb-1 text-foreground flex items-center gap-1.5">
                      <User className="w-3.5 h-3.5 text-primary" />
                      First Name
                    </label>
                    <input
                      type="text"
                      placeholder="John"
                      value={firstName}
                      onChange={(e) => setFirstName(e.target.value)}
                      className="w-full px-3.5 py-2 rounded-lg bg-input-background border border-border text-sm focus:outline-none focus:ring-2 focus:ring-primary transition-all"
                      required={!isLogin}
                    />
                  </div>
                  <div>
                    <label className="block text-xs sm:text-sm font-medium mb-1 text-foreground">
                      Last Name
                    </label>
                    <input
                      type="text"
                      placeholder="Doe"
                      value={lastName}
                      onChange={(e) => setLastName(e.target.value)}
                      className="w-full px-3.5 py-2 rounded-lg bg-input-background border border-border text-sm focus:outline-none focus:ring-2 focus:ring-primary transition-all"
                      required={!isLogin}
                    />
                  </div>
                </motion.div>
              )}
            </AnimatePresence>

            {/* Email */}
            <div>
              <label className="block text-xs sm:text-sm font-medium mb-1 text-foreground flex items-center gap-1.5">
                <Mail className="w-3.5 h-3.5 text-primary" />
                Email Address
              </label>
              <input
                type="email"
                placeholder="you@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full px-3.5 py-2 rounded-lg bg-input-background border border-border text-sm focus:outline-none focus:ring-2 focus:ring-primary transition-all"
                required
              />
            </div>

            {/* Password & Confirm Password */}
            <div className={!isLogin ? "grid grid-cols-1 sm:grid-cols-2 gap-3" : ""}>
              <div>
                <label className="block text-xs sm:text-sm font-medium mb-1 text-foreground flex items-center gap-1.5">
                  <Lock className="w-3.5 h-3.5 text-primary" />
                  Password
                </label>
                <div className="relative">
                  <input
                    type={showPassword ? "text" : "password"}
                    placeholder="••••••••"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="w-full px-3.5 py-2 rounded-lg bg-input-background border border-border text-sm focus:outline-none focus:ring-2 focus:ring-primary transition-all pr-10"
                    required
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
                  >
                    {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>

              {!isLogin && (
                <div>
                  <label className="block text-xs sm:text-sm font-medium mb-1 text-foreground flex items-center gap-1.5">
                    <Lock className="w-3.5 h-3.5 text-primary" />
                    Confirm Password
                  </label>
                  <div className="relative">
                    <input
                      type={showConfirmPassword ? "text" : "password"}
                      placeholder="••••••••"
                      value={confirmPassword}
                      onChange={(e) => setConfirmPassword(e.target.value)}
                      className="w-full px-3.5 py-2 rounded-lg bg-input-background border border-border text-sm focus:outline-none focus:ring-2 focus:ring-primary transition-all pr-10"
                      required={!isLogin}
                    />
                    <button
                      type="button"
                      onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
                    >
                      {showConfirmPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                    </button>
                  </div>
                </div>
              )}
            </div>

            {!isLogin && (
              <p className="text-[11px] text-muted-foreground -mt-1">
                Must be at least 8 characters with uppercase, lowercase, and numbers
              </p>
            )}

            {/* Terms and Conditions (Signup only) */}
            {!isLogin && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="flex items-center gap-2.5 p-2.5 bg-muted/30 rounded-lg"
              >
                <input
                  type="checkbox"
                  id="terms"
                  checked={acceptTerms}
                  onChange={(e) => setAcceptTerms(e.target.checked)}
                  className="w-4 h-4 accent-primary shrink-0 cursor-pointer"
                  required={!isLogin}
                />
                <label htmlFor="terms" className="text-xs text-muted-foreground cursor-pointer leading-tight">
                  I agree to the{" "}
                  <a href="#" className="text-primary hover:text-secondary transition-colors font-medium">
                    Terms of Service
                  </a>{" "}
                  and{" "}
                  <a href="#" className="text-primary hover:text-secondary transition-colors font-medium">
                    Privacy Policy
                  </a>
                  .
                </label>
              </motion.div>
            )}

            {/* Forgot Password */}
            {isLogin && (
              <div className="flex justify-end">
                <Link
                  to="/forgot-password"
                  className="text-xs sm:text-sm text-primary hover:text-secondary transition-colors"
                >
                  Forgot Password?
                </Link>
              </div>
            )}

            {error && (
              <div className="rounded-lg border border-red-200 bg-red-50 px-3.5 py-2 text-xs sm:text-sm text-red-700">
                {error}
              </div>
            )}

            {successMessage && (
              <div className="rounded-lg border border-green-200 bg-green-50 px-3.5 py-2 text-xs sm:text-sm text-green-700">
                {successMessage}
              </div>
            )}

            {/* Submit Button */}
            <motion.button
              type="submit"
              disabled={loading}
              whileHover={{ scale: 1.01 }}
              whileTap={{ scale: 0.99 }}
              className="w-full py-2.5 rounded-lg bg-gradient-to-r from-primary to-secondary text-white hover:opacity-90 transition-opacity flex items-center justify-center gap-2 text-sm sm:text-base font-medium disabled:cursor-not-allowed disabled:opacity-70 shadow-md"
            >
              {!isLogin && <CheckCircle2 className="w-4 h-4" />}
              {loading ? "Please wait..." : isLogin ? "Sign In" : "Create Account"}
            </motion.button>

            {/* Toggle Login/Register */}
            <div className="text-center text-xs sm:text-sm text-muted-foreground pt-0.5">
              {isLogin ? "Don't have an account? " : "Already have an account? "}
              <button
                type="button"
                onClick={() => setIsLogin(!isLogin)}
                className="text-primary hover:text-secondary transition-colors font-semibold"
              >
                {isLogin ? "Sign up" : "Sign in"}
              </button>
            </div>
          </form>
        </motion.div>

        {/* Back to Home */}
        <div className="text-center mt-3 sm:mt-4">
          <Link to="/" className="text-xs sm:text-sm text-white hover:text-indigo-100 transition-colors">
            ← Back to Home
          </Link>
        </div>
      </motion.div>
    </div>
  );
}

import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router";
import { motion, AnimatePresence } from "motion/react";
import { Brain, Eye, EyeOff, User, Mail, Lock, Building2, GraduationCap, Briefcase, Shield, CheckCircle2 } from "lucide-react";
import axios from "axios";

import { authApi, institutionsApi, type InstitutionOption, type UserRole } from "../../services/api";
import { authStorage } from "../../services/auth";

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
      if ((role === "student" || role === "faculty") && !selectedInstitutionId) {
        setError("Please select an institution.");
        return;
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
        authStorage.setSession({
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
        });
        authStorage.setSession({
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
    <div className="min-h-screen bg-gradient-to-br from-primary via-secondary to-primary flex items-center justify-center p-6">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6 }}
        className="w-full max-w-2xl"
      >
        {/* Logo */}
        <div className="text-center mb-8">
          <Link to="/">
            <div className="inline-flex items-center gap-3 mb-4">
              <div className="w-12 h-12 rounded-xl bg-white flex items-center justify-center">
                <Brain className="w-7 h-7 text-primary" />
              </div>
              <span className="text-2xl font-bold text-white">ExamAI</span>
            </div>
          </Link>
          <h1 className="text-3xl font-bold text-white mb-2">
            {isLogin ? "Welcome Back" : "Create Your Account"}
          </h1>
          <p className="text-indigo-100">
            {isLogin ? "Sign in to continue to ExamAI Platform" : "Join the AI-powered exam management platform"}
          </p>
        </div>

        {/* Login/Signup Card */}
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: 0.2 }}
          className="bg-white rounded-2xl shadow-2xl p-8 max-h-[85vh] overflow-y-auto"
        >
          <form onSubmit={handleSubmit} className="space-y-5">
            {/* Role Selector */}
            <div>
              <label className="block text-sm font-medium mb-2 text-foreground flex items-center gap-2">
                <Shield className="w-4 h-4 text-primary" />
                Select Your Role
              </label>
              <div className="grid grid-cols-3 gap-3">
                {[
                  { value: "student", label: "Student", icon: GraduationCap },
                  { value: "faculty", label: "Faculty", icon: Briefcase },
                  { value: "admin", label: "Admin", icon: Building2 }
                ].map((roleOption) => (
                  <motion.button
                    key={roleOption.value}
                    type="button"
                    onClick={() => setRole(roleOption.value)}
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.98 }}
                    className={`p-4 rounded-lg border-2 transition-all ${
                      role === roleOption.value
                        ? "border-primary bg-primary/5"
                        : "border-border hover:border-primary/50"
                    }`}
                  >
                    <roleOption.icon className={`w-6 h-6 mx-auto mb-2 ${role === roleOption.value ? "text-primary" : "text-muted-foreground"}`} />
                    <div className={`text-sm font-medium ${role === roleOption.value ? "text-primary" : "text-foreground"}`}>
                      {roleOption.label}
                    </div>
                  </motion.button>
                ))}
              </div>
            </div>

            {!isLogin && (role === "student" || role === "faculty") && (
              <div>
                <label className="block text-sm font-medium mb-2 text-foreground flex items-center gap-2">
                  <Building2 className="w-4 h-4 text-primary" />
                  Institution
                </label>
                <select
                  value={selectedInstitutionId}
                  onChange={(event) => setSelectedInstitutionId(event.target.value)}
                  disabled={institutionsLoading}
                  className="w-full px-4 py-3 rounded-lg bg-input-background border border-border focus:outline-none focus:ring-2 focus:ring-primary transition-all"
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

            <AnimatePresence mode="wait">
              {!isLogin && (
                <motion.div
                  key="signup-fields"
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: "auto" }}
                  exit={{ opacity: 0, height: 0 }}
                  transition={{ duration: 0.3 }}
                  className="space-y-5"
                >
                  {/* Full Name */}
                  <div className="grid md:grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium mb-2 text-foreground flex items-center gap-2">
                        <User className="w-4 h-4 text-primary" />
                        First Name
                      </label>
                      <input
                        type="text"
                        placeholder="John"
                        value={firstName}
                        onChange={(e) => setFirstName(e.target.value)}
                        className="w-full px-4 py-3 rounded-lg bg-input-background border border-border focus:outline-none focus:ring-2 focus:ring-primary transition-all"
                        required={!isLogin}
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium mb-2 text-foreground">
                        Last Name
                      </label>
                      <input
                        type="text"
                        placeholder="Doe"
                        value={lastName}
                        onChange={(e) => setLastName(e.target.value)}
                        className="w-full px-4 py-3 rounded-lg bg-input-background border border-border focus:outline-none focus:ring-2 focus:ring-primary transition-all"
                        required={!isLogin}
                      />
                    </div>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>

            {/* Email */}
            <div>
              <label className="block text-sm font-medium mb-2 text-foreground flex items-center gap-2">
                <Mail className="w-4 h-4 text-primary" />
                Email Address
              </label>
              <input
                type="email"
                placeholder="you@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full px-4 py-3 rounded-lg bg-input-background border border-border focus:outline-none focus:ring-2 focus:ring-primary transition-all"
                required
              />
            </div>

            {/* Password */}
            <div>
              <label className="block text-sm font-medium mb-2 text-foreground flex items-center gap-2">
                <Lock className="w-4 h-4 text-primary" />
                Password
              </label>
              <div className="relative">
                <input
                  type={showPassword ? "text" : "password"}
                  placeholder="••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full px-4 py-3 rounded-lg bg-input-background border border-border focus:outline-none focus:ring-2 focus:ring-primary transition-all pr-12"
                  required
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
                >
                  {showPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                </button>
              </div>
              {!isLogin && (
                <p className="text-xs text-muted-foreground mt-1">
                  Must be at least 8 characters with uppercase, lowercase, and numbers
                </p>
              )}
            </div>

            {/* Confirm Password (Signup only) */}
            {!isLogin && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: "auto" }}
                exit={{ opacity: 0, height: 0 }}
              >
                <label className="block text-sm font-medium mb-2 text-foreground flex items-center gap-2">
                  <Lock className="w-4 h-4 text-primary" />
                  Confirm Password
                </label>
                <div className="relative">
                  <input
                    type={showConfirmPassword ? "text" : "password"}
                    placeholder="••••••••"
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    className="w-full px-4 py-3 rounded-lg bg-input-background border border-border focus:outline-none focus:ring-2 focus:ring-primary transition-all pr-12"
                    required={!isLogin}
                  />
                  <button
                    type="button"
                    onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
                  >
                    {showConfirmPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                  </button>
                </div>
              </motion.div>
            )}

            {/* Terms and Conditions (Signup only) */}
            {!isLogin && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="flex items-start gap-3 p-4 bg-muted/30 rounded-lg"
              >
                <input
                  type="checkbox"
                  id="terms"
                  checked={acceptTerms}
                  onChange={(e) => setAcceptTerms(e.target.checked)}
                  className="mt-1 w-4 h-4 accent-primary cursor-pointer"
                  required={!isLogin}
                />
                <label htmlFor="terms" className="text-sm text-muted-foreground cursor-pointer">
                  I agree to the{" "}
                  <a href="#" className="text-primary hover:text-secondary transition-colors">
                    Terms of Service
                  </a>{" "}
                  and{" "}
                  <a href="#" className="text-primary hover:text-secondary transition-colors">
                    Privacy Policy
                  </a>
                  . I understand this platform is for educational purposes and will be used responsibly.
                </label>
              </motion.div>
            )}

            {/* Forgot Password */}
            {isLogin && (
              <div className="flex justify-end">
                <Link
                  to="/forgot-password"
                  className="text-sm text-primary hover:text-secondary transition-colors"
                >
                  Forgot Password?
                </Link>
              </div>
            )}

            {error && (
              <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                {error}
              </div>
            )}

            {successMessage && (
              <div className="rounded-lg border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-700">
                {successMessage}
              </div>
            )}

            {/* Submit Button */}
            <motion.button
              type="submit"
              disabled={loading}
              whileHover={{ scale: 1.01 }}
              whileTap={{ scale: 0.99 }}
              className="w-full py-3 rounded-lg bg-gradient-to-r from-primary to-secondary text-white hover:opacity-90 transition-opacity flex items-center justify-center gap-2 font-medium disabled:cursor-not-allowed disabled:opacity-70"
            >
              {!isLogin && <CheckCircle2 className="w-5 h-5" />}
              {loading ? "Please wait..." : isLogin ? "Sign In" : "Create Account"}
            </motion.button>

            {/* Toggle Login/Register */}
            <div className="text-center text-sm text-muted-foreground">
              {isLogin ? "Don't have an account? " : "Already have an account? "}
              <button
                type="button"
                onClick={() => setIsLogin(!isLogin)}
                className="text-primary hover:text-secondary transition-colors font-medium"
              >
                {isLogin ? "Sign up" : "Sign in"}
              </button>
            </div>
          </form>
        </motion.div>

        {/* Back to Home */}
        <div className="text-center mt-6">
          <Link to="/" className="text-white hover:text-indigo-100 transition-colors">
            ← Back to Home
          </Link>
        </div>
      </motion.div>
    </div>
  );
}

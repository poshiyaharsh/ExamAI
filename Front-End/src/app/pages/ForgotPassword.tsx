import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { motion } from "motion/react";
import { Brain, Eye, EyeOff, Lock, Mail, Shield } from "lucide-react";
import axios from "axios";

import { forgotPasswordApi } from "../../services/api";

type ForgotStep = "request" | "verify" | "reset" | "done";

function extractApiErrorMessage(apiError: unknown): string | null {
  if (!apiError || typeof apiError !== "object") {
    return null;
  }

  const record = apiError as Record<string, unknown>;

  if (typeof record.message === "string") {
    return record.message;
  }

  if (typeof record.detail === "string") {
    return record.detail;
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

export function ForgotPassword() {
  const [step, setStep] = useState<ForgotStep>("request");
  const [email, setEmail] = useState("");
  const [otp, setOtp] = useState("");
  const [resetToken, setResetToken] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [successMessage, setSuccessMessage] = useState("");
  const [debugOtp, setDebugOtp] = useState("");
  const [showNewPassword, setShowNewPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);

  useEffect(() => {
    document.title = "Forgot Password | ExamAI";
  }, []);

  const handleRequestReset = async (event: React.FormEvent) => {
    event.preventDefault();
    setError("");
    setSuccessMessage("");
    setDebugOtp("");

    const normalizedEmail = email.trim().toLowerCase();
    if (!normalizedEmail) {
      setError("Email is required.");
      return;
    }

    setLoading(true);
    try {
      const response = await forgotPasswordApi.requestReset(normalizedEmail);
      setEmail(normalizedEmail);
      setSuccessMessage(response.message || "Reset instructions sent to your email.");
      setDebugOtp(response.debug_otp || "");
      setStep("verify");
    } catch (requestError) {
      if (axios.isAxiosError(requestError)) {
        const extracted = extractApiErrorMessage(requestError.response?.data);
        setError(extracted ?? "Unable to send reset instructions. Please try again.");
      } else {
        setError("Unable to send reset instructions. Please try again.");
      }
    } finally {
      setLoading(false);
    }
  };

  const handleVerifyOtp = async (event: React.FormEvent) => {
    event.preventDefault();
    setError("");
    setSuccessMessage("");

    const cleanedOtp = otp.trim();
    if (!cleanedOtp) {
      setError("Verification code is required.");
      return;
    }

    if (!/^\d{6}$/.test(cleanedOtp)) {
      setError("Enter a valid 6-digit verification code.");
      return;
    }

    setLoading(true);
    try {
      const response = await forgotPasswordApi.verifyOtp(email, cleanedOtp);
      setResetToken(response.reset_token);
      setSuccessMessage(response.message || "Verification successful.");
      setStep("reset");
    } catch (requestError) {
      if (axios.isAxiosError(requestError)) {
        const extracted = extractApiErrorMessage(requestError.response?.data);
        setError(extracted ?? "Unable to verify code. Please try again.");
      } else {
        setError("Unable to verify code. Please try again.");
      }
    } finally {
      setLoading(false);
    }
  };

  const handleResetPassword = async (event: React.FormEvent) => {
    event.preventDefault();
    setError("");
    setSuccessMessage("");

    if (!newPassword || !confirmPassword) {
      setError("All password fields are required.");
      return;
    }

    if (newPassword.length < 8) {
      setError("New password must be at least 8 characters long.");
      return;
    }

    const hasLetter = /[A-Za-z]/.test(newPassword);
    const hasNumber = /\d/.test(newPassword);
    if (!hasLetter || !hasNumber) {
      setError("New password must include at least one letter and one number.");
      return;
    }

    if (newPassword !== confirmPassword) {
      setError("Confirm password must match new password.");
      return;
    }

    setLoading(true);
    try {
      const response = await forgotPasswordApi.resetPassword({
        email,
        reset_token: resetToken,
        new_password: newPassword,
        confirm_password: confirmPassword,
      });

      setSuccessMessage(response.message || "Password has been reset successfully.");
      setNewPassword("");
      setConfirmPassword("");
      setOtp("");
      setStep("done");
    } catch (requestError) {
      if (axios.isAxiosError(requestError)) {
        const extracted = extractApiErrorMessage(requestError.response?.data);
        setError(extracted ?? "Unable to reset password. Please try again.");
      } else {
        setError("Unable to reset password. Please try again.");
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
        {/* Logo & Header */}
        <div className="text-center mb-3 sm:mb-4">
          <Link to="/" className="inline-block">
            <div className="inline-flex items-center gap-2 mb-1.5">
              <div className="w-9 h-9 rounded-lg bg-white flex items-center justify-center shadow-sm">
                <Brain className="w-5 h-5 text-primary" />
              </div>
              <span className="text-xl sm:text-2xl font-bold text-white tracking-tight">ExamAI</span>
            </div>
          </Link>
          <h1 className="text-2xl sm:text-3xl font-bold text-white">Forgot Password</h1>
          <p className="text-xs sm:text-sm text-indigo-100 mt-0.5">Enter your email to receive reset instructions</p>
        </div>

        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: 0.2 }}
          className="bg-white rounded-2xl shadow-2xl p-5 sm:p-6"
        >
          {step === "request" && (
            <form onSubmit={handleRequestReset} className="space-y-3 sm:space-y-3.5">
              <div>
                <label className="block text-xs sm:text-sm font-medium mb-1 text-foreground flex items-center gap-1.5">
                  <Mail className="w-3.5 h-3.5 text-primary" />
                  Email Address
                </label>
                <input
                  type="email"
                  placeholder="you@example.com"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  className="w-full px-3.5 py-2 rounded-lg bg-input-background border border-border text-sm focus:outline-none focus:ring-2 focus:ring-primary transition-all"
                  required
                />
              </div>

              {error && <div className="rounded-lg border border-red-200 bg-red-50 px-3.5 py-2 text-xs sm:text-sm text-red-700">{error}</div>}
              {successMessage && <div className="rounded-lg border border-green-200 bg-green-50 px-3.5 py-2 text-xs sm:text-sm text-green-700">{successMessage}</div>}
              {debugOtp && (
                <div className="rounded-lg border border-blue-200 bg-blue-50 px-3.5 py-2 text-xs sm:text-sm text-blue-700">
                  Development OTP: <span className="font-semibold">{debugOtp}</span>
                </div>
              )}

              <button
                type="submit"
                disabled={loading}
                className="w-full py-2.5 rounded-lg bg-gradient-to-r from-primary to-secondary text-white hover:opacity-90 transition-opacity flex items-center justify-center gap-2 text-sm sm:text-base font-medium disabled:cursor-not-allowed disabled:opacity-70 shadow-md"
              >
                {loading ? "Please wait..." : "Send Reset Link / OTP"}
              </button>
            </form>
          )}

          {step === "verify" && (
            <form onSubmit={handleVerifyOtp} className="space-y-3 sm:space-y-3.5">
              <div>
                <label className="block text-xs sm:text-sm font-medium mb-1 text-foreground flex items-center gap-1.5">
                  <Shield className="w-3.5 h-3.5 text-primary" />
                  OTP / Verification Code
                </label>
                <input
                  type="text"
                  placeholder="Enter 6-digit code"
                  value={otp}
                  onChange={(event) => setOtp(event.target.value)}
                  className="w-full px-3.5 py-2 rounded-lg bg-input-background border border-border text-sm focus:outline-none focus:ring-2 focus:ring-primary transition-all"
                  required
                />
              </div>

              {error && <div className="rounded-lg border border-red-200 bg-red-50 px-3.5 py-2 text-xs sm:text-sm text-red-700">{error}</div>}
              {successMessage && <div className="rounded-lg border border-green-200 bg-green-50 px-3.5 py-2 text-xs sm:text-sm text-green-700">{successMessage}</div>}

              <button
                type="submit"
                disabled={loading}
                className="w-full py-2.5 rounded-lg bg-gradient-to-r from-primary to-secondary text-white hover:opacity-90 transition-opacity flex items-center justify-center gap-2 text-sm sm:text-base font-medium disabled:cursor-not-allowed disabled:opacity-70 shadow-md"
              >
                {loading ? "Please wait..." : "Verify"}
              </button>
            </form>
          )}

          {step === "reset" && (
            <form onSubmit={handleResetPassword} className="space-y-3 sm:space-y-3.5">
              <div>
                <label className="block text-xs sm:text-sm font-medium mb-1 text-foreground flex items-center gap-1.5">
                  <Lock className="w-3.5 h-3.5 text-primary" />
                  New Password
                </label>
                <div className="relative">
                  <input
                    type={showNewPassword ? "text" : "password"}
                    placeholder="••••••••"
                    value={newPassword}
                    onChange={(event) => setNewPassword(event.target.value)}
                    className="w-full px-3.5 py-2 rounded-lg bg-input-background border border-border text-sm focus:outline-none focus:ring-2 focus:ring-primary transition-all pr-10"
                    required
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
                <label className="block text-xs sm:text-sm font-medium mb-1 text-foreground flex items-center gap-1.5">
                  <Lock className="w-3.5 h-3.5 text-primary" />
                  Confirm Password
                </label>
                <div className="relative">
                  <input
                    type={showConfirmPassword ? "text" : "password"}
                    placeholder="••••••••"
                    value={confirmPassword}
                    onChange={(event) => setConfirmPassword(event.target.value)}
                    className="w-full px-3.5 py-2 rounded-lg bg-input-background border border-border text-sm focus:outline-none focus:ring-2 focus:ring-primary transition-all pr-10"
                    required
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

              {error && <div className="rounded-lg border border-red-200 bg-red-50 px-3.5 py-2 text-xs sm:text-sm text-red-700">{error}</div>}
              {successMessage && <div className="rounded-lg border border-green-200 bg-green-50 px-3.5 py-2 text-xs sm:text-sm text-green-700">{successMessage}</div>}

              <button
                type="submit"
                disabled={loading}
                className="w-full py-2.5 rounded-lg bg-gradient-to-r from-primary to-secondary text-white hover:opacity-90 transition-opacity flex items-center justify-center gap-2 text-sm sm:text-base font-medium disabled:cursor-not-allowed disabled:opacity-70 shadow-md"
              >
                {loading ? "Please wait..." : "Reset Password"}
              </button>
            </form>
          )}

          {step === "done" && (
            <div className="space-y-3 sm:space-y-3.5">
              {successMessage && <div className="rounded-lg border border-green-200 bg-green-50 px-3.5 py-2 text-xs sm:text-sm text-green-700">{successMessage}</div>}
              <p className="text-xs sm:text-sm text-muted-foreground">Your password has been updated. Use your new password to sign in.</p>
            </div>
          )}

          <div className="text-center text-xs sm:text-sm text-muted-foreground pt-1">
            <Link to="/login" className="text-primary hover:text-secondary transition-colors font-semibold">
              Back to Sign In
            </Link>
          </div>
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

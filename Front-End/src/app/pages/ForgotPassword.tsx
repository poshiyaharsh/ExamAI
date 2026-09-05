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
    <div className="min-h-screen bg-gradient-to-br from-primary via-secondary to-primary flex items-center justify-center p-6">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6 }}
        className="w-full max-w-2xl"
      >
        <div className="text-center mb-8">
          <Link to="/">
            <div className="inline-flex items-center gap-3 mb-4">
              <div className="w-12 h-12 rounded-xl bg-white flex items-center justify-center">
                <Brain className="w-7 h-7 text-primary" />
              </div>
              <span className="text-2xl font-bold text-white">ExamAI</span>
            </div>
          </Link>
          <h1 className="text-3xl font-bold text-white mb-2">Forgot Password</h1>
          <p className="text-indigo-100">Enter your email to receive reset instructions</p>
        </div>

        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: 0.2 }}
          className="bg-white rounded-2xl shadow-2xl p-8"
        >
          {step === "request" && (
            <form onSubmit={handleRequestReset} className="space-y-5">
              <div>
                <label className="block text-sm font-medium mb-2 text-foreground flex items-center gap-2">
                  <Mail className="w-4 h-4 text-primary" />
                  Email Address
                </label>
                <input
                  type="email"
                  placeholder="you@example.com"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  className="w-full px-4 py-3 rounded-lg bg-input-background border border-border focus:outline-none focus:ring-2 focus:ring-primary transition-all"
                  required
                />
              </div>

              {error && <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>}
              {successMessage && <div className="rounded-lg border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-700">{successMessage}</div>}
              {debugOtp && (
                <div className="rounded-lg border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-700">
                  Development OTP: <span className="font-semibold">{debugOtp}</span>
                </div>
              )}

              <button
                type="submit"
                disabled={loading}
                className="w-full py-3 rounded-lg bg-gradient-to-r from-primary to-secondary text-white hover:opacity-90 transition-opacity font-medium disabled:cursor-not-allowed disabled:opacity-70"
              >
                {loading ? "Please wait..." : "Send Reset Link / OTP"}
              </button>
            </form>
          )}

          {step === "verify" && (
            <form onSubmit={handleVerifyOtp} className="space-y-5">
              <div>
                <label className="block text-sm font-medium mb-2 text-foreground flex items-center gap-2">
                  <Shield className="w-4 h-4 text-primary" />
                  OTP / Verification Code
                </label>
                <input
                  type="text"
                  placeholder="Enter 6-digit code"
                  value={otp}
                  onChange={(event) => setOtp(event.target.value)}
                  className="w-full px-4 py-3 rounded-lg bg-input-background border border-border focus:outline-none focus:ring-2 focus:ring-primary transition-all"
                  required
                />
              </div>

              {error && <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>}
              {successMessage && <div className="rounded-lg border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-700">{successMessage}</div>}

              <button
                type="submit"
                disabled={loading}
                className="w-full py-3 rounded-lg bg-gradient-to-r from-primary to-secondary text-white hover:opacity-90 transition-opacity font-medium disabled:cursor-not-allowed disabled:opacity-70"
              >
                {loading ? "Please wait..." : "Verify"}
              </button>
            </form>
          )}

          {step === "reset" && (
            <form onSubmit={handleResetPassword} className="space-y-5">
              <div>
                <label className="block text-sm font-medium mb-2 text-foreground flex items-center gap-2">
                  <Lock className="w-4 h-4 text-primary" />
                  New Password
                </label>
                <div className="relative">
                  <input
                    type={showNewPassword ? "text" : "password"}
                    placeholder="••••••••"
                    value={newPassword}
                    onChange={(event) => setNewPassword(event.target.value)}
                    className="w-full px-4 py-3 rounded-lg bg-input-background border border-border focus:outline-none focus:ring-2 focus:ring-primary transition-all pr-12"
                    required
                  />
                  <button
                    type="button"
                    onClick={() => setShowNewPassword((prev) => !prev)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
                  >
                    {showNewPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                  </button>
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium mb-2 text-foreground flex items-center gap-2">
                  <Lock className="w-4 h-4 text-primary" />
                  Confirm Password
                </label>
                <div className="relative">
                  <input
                    type={showConfirmPassword ? "text" : "password"}
                    placeholder="••••••••"
                    value={confirmPassword}
                    onChange={(event) => setConfirmPassword(event.target.value)}
                    className="w-full px-4 py-3 rounded-lg bg-input-background border border-border focus:outline-none focus:ring-2 focus:ring-primary transition-all pr-12"
                    required
                  />
                  <button
                    type="button"
                    onClick={() => setShowConfirmPassword((prev) => !prev)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
                  >
                    {showConfirmPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                  </button>
                </div>
              </div>

              {error && <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>}
              {successMessage && <div className="rounded-lg border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-700">{successMessage}</div>}

              <button
                type="submit"
                disabled={loading}
                className="w-full py-3 rounded-lg bg-gradient-to-r from-primary to-secondary text-white hover:opacity-90 transition-opacity font-medium disabled:cursor-not-allowed disabled:opacity-70"
              >
                {loading ? "Please wait..." : "Reset Password"}
              </button>
            </form>
          )}

          {step === "done" && (
            <div className="space-y-5">
              {successMessage && <div className="rounded-lg border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-700">{successMessage}</div>}
              <p className="text-sm text-muted-foreground">Your password has been updated. Use your new password to sign in.</p>
            </div>
          )}

          <div className="text-center text-sm text-muted-foreground mt-6">
            <Link to="/login" className="text-primary hover:text-secondary transition-colors">
              Back to Sign In
            </Link>
          </div>
        </motion.div>
      </motion.div>
    </div>
  );
}

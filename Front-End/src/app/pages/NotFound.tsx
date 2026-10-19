import { useEffect, useRef } from "react";
import { Link, useNavigate } from "react-router-dom";
import { motion } from "motion/react";
import { BookOpen, Home, ArrowLeft, Compass } from "lucide-react";
import { useAuth } from "../context/useAuth";

// ── Animated floating particle ──────────────────────────────────────────────
function Particle({ x, y, size, delay }: { x: number; y: number; size: number; delay: number }) {
  return (
    <motion.div
      className="absolute rounded-full pointer-events-none"
      style={{
        left: `${x}%`,
        top: `${y}%`,
        width: size,
        height: size,
        background: `radial-gradient(circle, rgba(99,102,241,0.5) 0%, rgba(79,70,229,0.1) 100%)`,
      }}
      animate={{
        y: [0, -24, 0],
        opacity: [0.2, 0.7, 0.2],
        scale: [1, 1.2, 1],
      }}
      transition={{
        duration: 3 + delay,
        delay,
        repeat: Infinity,
        ease: "easeInOut",
      }}
    />
  );
}

// ── Glitchy animated 404 digits ──────────────────────────────────────────────
function GlitchDigit({ char, delay }: { char: string; delay: number }) {
  return (
    <motion.span
      className="relative inline-block select-none"
      style={{
        fontFamily: "'Inter', sans-serif",
        fontWeight: 900,
        fontSize: "clamp(5rem, 18vw, 12rem)",
        lineHeight: 1,
        color: "transparent",
        WebkitTextStroke: "2px rgba(99,102,241,0.8)",
        letterSpacing: "-0.04em",
      }}
      initial={{ opacity: 0, y: 40 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay, duration: 0.6, type: "spring", bounce: 0.4 }}
    >
      {/* Main digit */}
      <span
        style={{
          background: "linear-gradient(135deg, #6366F1 0%, #4F46E5 50%, #8B5CF6 100%)",
          WebkitBackgroundClip: "text",
          WebkitTextFillColor: "transparent",
          WebkitTextStroke: "0",
        }}
      >
        {char}
      </span>

      {/* Glitch layer 1 */}
      <motion.span
        aria-hidden
        className="absolute inset-0"
        style={{
          background: "linear-gradient(135deg, #EF4444 0%, #F97316 100%)",
          WebkitBackgroundClip: "text",
          WebkitTextFillColor: "transparent",
          WebkitTextStroke: "0",
          clipPath: "inset(45% 0 40% 0)",
          mixBlendMode: "screen",
        }}
        animate={{ x: [-3, 3, -2, 2, 0], opacity: [0, 0.8, 0, 0.6, 0] }}
        transition={{ duration: 2, delay: delay + 1, repeat: Infinity, repeatDelay: 3 }}
      >
        {char}
      </motion.span>

      {/* Glitch layer 2 */}
      <motion.span
        aria-hidden
        className="absolute inset-0"
        style={{
          background: "linear-gradient(135deg, #06B6D4 0%, #3B82F6 100%)",
          WebkitBackgroundClip: "text",
          WebkitTextFillColor: "transparent",
          WebkitTextStroke: "0",
          clipPath: "inset(60% 0 20% 0)",
          mixBlendMode: "screen",
        }}
        animate={{ x: [2, -3, 1, -2, 0], opacity: [0, 0.6, 0, 0.4, 0] }}
        transition={{ duration: 2, delay: delay + 1.3, repeat: Infinity, repeatDelay: 3 }}
      >
        {char}
      </motion.span>
    </motion.span>
  );
}

// ── Scanning beam effect ─────────────────────────────────────────────────────
function ScanBeam() {
  return (
    <motion.div
      className="absolute inset-x-0 pointer-events-none"
      style={{
        height: 2,
        background: "linear-gradient(90deg, transparent, rgba(99,102,241,0.6), rgba(139,92,246,0.6), transparent)",
        boxShadow: "0 0 12px rgba(99,102,241,0.5)",
      }}
      animate={{ top: ["0%", "100%", "0%"] }}
      transition={{ duration: 4, repeat: Infinity, ease: "linear" }}
    />
  );
}

// ── Main 404 component ───────────────────────────────────────────────────────
export function NotFound() {
  const navigate = useNavigate();
  const { session } = useAuth();

  // Derive the user's home path from their role
  const homePath = session
    ? session.role === "admin"
      ? "/admin"
      : session.role === "faculty"
      ? "/faculty"
      : "/student"
    : "/";

  const homeLabel = session
    ? `Go to ${session.role.charAt(0).toUpperCase() + session.role.slice(1)} Dashboard`
    : "Go to Homepage";

  // Randomised particle positions — stable via ref so they don't re-randomise
  const particles = useRef(
    Array.from({ length: 14 }, (_, i) => ({
      x: Math.random() * 100,
      y: Math.random() * 100,
      size: 6 + Math.random() * 18,
      delay: (i * 0.3) % 3,
    }))
  ).current;

  return (
    <div
      className="relative min-h-screen overflow-hidden flex flex-col items-center justify-center"
      style={{
        background: "linear-gradient(135deg, #0F0F1A 0%, #13131F 40%, #0A0A14 100%)",
      }}
    >
      {/* ── Background grid ── */}
      <div
        className="absolute inset-0 pointer-events-none opacity-20"
        style={{
          backgroundImage:
            "linear-gradient(rgba(99,102,241,0.15) 1px, transparent 1px), " +
            "linear-gradient(90deg, rgba(99,102,241,0.15) 1px, transparent 1px)",
          backgroundSize: "48px 48px",
        }}
      />

      {/* ── Floating particles ── */}
      {particles.map((p, i) => (
        <Particle key={i} {...p} />
      ))}

      {/* ── Radial glow behind the 404 ── */}
      <div
        className="absolute pointer-events-none"
        style={{
          width: "min(600px, 80vw)",
          height: "min(600px, 80vw)",
          borderRadius: "50%",
          background: "radial-gradient(circle, rgba(79,70,229,0.18) 0%, transparent 70%)",
          top: "50%",
          left: "50%",
          transform: "translate(-50%, -60%)",
        }}
      />

      {/* ── Main content card ── */}
      <motion.div
        className="relative z-10 flex flex-col items-center text-center px-6"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.4 }}
      >
        {/* Icon badge */}
        <motion.div
          initial={{ scale: 0, rotate: -20 }}
          animate={{ scale: 1, rotate: 0 }}
          transition={{ delay: 0.1, type: "spring", bounce: 0.5 }}
          className="mb-6 flex items-center justify-center gap-2 rounded-full px-4 py-2"
          style={{
            background: "rgba(99,102,241,0.12)",
            border: "1px solid rgba(99,102,241,0.3)",
            backdropFilter: "blur(8px)",
          }}
        >
          <Compass size={16} style={{ color: "#818CF8" }} />
          <span style={{ color: "#818CF8", fontSize: "0.75rem", fontWeight: 600, letterSpacing: "0.1em" }}>
            PAGE NOT FOUND
          </span>
        </motion.div>

        {/* 404 glitch digits */}
        <div className="relative mb-2" style={{ isolation: "isolate" }}>
          {/* Scan beam inside the 404 area */}
          <div className="absolute inset-0 overflow-hidden rounded-lg pointer-events-none">
            <ScanBeam />
          </div>
          <GlitchDigit char="4" delay={0.2} />
          <GlitchDigit char="0" delay={0.35} />
          <GlitchDigit char="4" delay={0.5} />
        </div>

        {/* Divider line */}
        <motion.div
          className="mb-6"
          style={{
            width: "min(280px, 60vw)",
            height: 1,
            background: "linear-gradient(90deg, transparent, rgba(99,102,241,0.6), transparent)",
          }}
          initial={{ scaleX: 0 }}
          animate={{ scaleX: 1 }}
          transition={{ delay: 0.7, duration: 0.6 }}
        />

        {/* Heading */}
        <motion.h1
          className="mb-3"
          style={{
            fontFamily: "'Inter', sans-serif",
            fontWeight: 700,
            fontSize: "clamp(1.25rem, 4vw, 1.75rem)",
            color: "#F9FAFB",
            lineHeight: 1.3,
          }}
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.75 }}
        >
          Oops! This page doesn't exist
        </motion.h1>

        {/* Sub-heading */}
        <motion.p
          className="mb-8 max-w-sm"
          style={{
            color: "#6B7280",
            fontSize: "clamp(0.875rem, 2.5vw, 1rem)",
            lineHeight: 1.7,
          }}
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.85 }}
        >
          The route you're looking for has been moved, deleted, or never existed.
          Let's get you back on track.
        </motion.p>

        {/* Action buttons */}
        <motion.div
          className="flex flex-col sm:flex-row gap-3"
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.95 }}
        >
          {/* Primary — home / dashboard */}
          <Link to={homePath}>
            <motion.button
              whileHover={{ scale: 1.03, y: -2 }}
              whileTap={{ scale: 0.97 }}
              className="flex items-center gap-2 px-6 py-3 rounded-xl font-semibold text-white"
              style={{
                background: "linear-gradient(135deg, #4F46E5 0%, #6366F1 100%)",
                boxShadow: "0 4px 24px rgba(79,70,229,0.4)",
                fontSize: "0.9rem",
                border: "none",
                cursor: "pointer",
                minWidth: 200,
                justifyContent: "center",
              }}
            >
              <Home size={16} />
              {homeLabel}
            </motion.button>
          </Link>

          {/* Secondary — go back */}
          <motion.button
            onClick={() => navigate(-1)}
            whileHover={{ scale: 1.03, y: -2 }}
            whileTap={{ scale: 0.97 }}
            className="flex items-center gap-2 px-6 py-3 rounded-xl font-semibold"
            style={{
              background: "rgba(99,102,241,0.1)",
              border: "1px solid rgba(99,102,241,0.3)",
              color: "#818CF8",
              fontSize: "0.9rem",
              cursor: "pointer",
              minWidth: 160,
              justifyContent: "center",
              backdropFilter: "blur(8px)",
            }}
          >
            <ArrowLeft size={16} />
            Go Back
          </motion.button>
        </motion.div>

        {/* Brand footer */}
        <motion.div
          className="mt-12 flex items-center gap-2"
          style={{ color: "#374151" }}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 1.1 }}
        >
          <BookOpen size={14} />
          <span style={{ fontSize: "0.75rem", fontWeight: 500, letterSpacing: "0.06em" }}>
            ExamAI Platform
          </span>
        </motion.div>
      </motion.div>
    </div>
  );
}

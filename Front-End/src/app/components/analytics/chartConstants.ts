import React from "react";
import { CheckCircle2, AlertTriangle, Minus, HelpCircle } from "lucide-react";

export const STRONG_THRESHOLD = 75.0;
export const AVERAGE_THRESHOLD = 50.0;
export const PASSING_THRESHOLD = 40.0;

export interface ClassificationMeta {
  code: "strong" | "average" | "needs_focus" | "no_results";
  label: string;
  badgeLabel: string;
  fill: string;
  hoverFill: string;
  stroke: string;
  badgeClass: string;
  textClass: string;
  bgClass: string;
  icon: React.ComponentType<{ className?: string }>;
}

export const CLASSIFICATION_MAP: Record<string, ClassificationMeta> = {
  strong: {
    code: "strong",
    label: "Strong (≥ 75%)",
    badgeLabel: "Strong",
    fill: "#10B981", // emerald-500
    hoverFill: "#059669",
    stroke: "#047857",
    badgeClass: "bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-400 dark:border-emerald-800",
    textClass: "text-emerald-700 dark:text-emerald-400",
    bgClass: "bg-emerald-500",
    icon: CheckCircle2,
  },
  average: {
    code: "average",
    label: "Average (50 – 74.9%)",
    badgeLabel: "Average",
    fill: "#3B82F6", // blue-500
    hoverFill: "#2563EB",
    stroke: "#1D4ED8",
    badgeClass: "bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-950/40 dark:text-blue-400 dark:border-blue-800",
    textClass: "text-blue-700 dark:text-blue-400",
    bgClass: "bg-blue-500",
    icon: Minus,
  },
  needs_focus: {
    code: "needs_focus",
    label: "Needs Focus (< 50%)",
    badgeLabel: "Needs Focus",
    fill: "#F59E0B", // amber-500
    hoverFill: "#D97706",
    stroke: "#B45309",
    badgeClass: "bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950/40 dark:text-amber-400 dark:border-amber-800",
    textClass: "text-amber-700 dark:text-amber-400",
    bgClass: "bg-amber-500",
    icon: AlertTriangle,
  },
  no_results: {
    code: "no_results",
    label: "No Graded Results",
    badgeLabel: "No Results",
    fill: "#9CA3AF", // gray-400
    hoverFill: "#6B7280",
    stroke: "#4B5563",
    badgeClass: "bg-slate-100 text-slate-700 border-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:border-slate-700",
    textClass: "text-slate-600 dark:text-slate-400",
    bgClass: "bg-slate-400",
    icon: HelpCircle,
  },
};

export function getClassificationMeta(score: number | null | undefined): ClassificationMeta {
  if (score === null || score === undefined || isNaN(score)) {
    return CLASSIFICATION_MAP.no_results;
  }
  if (score >= STRONG_THRESHOLD) {
    return CLASSIFICATION_MAP.strong;
  }
  if (score >= AVERAGE_THRESHOLD) {
    return CLASSIFICATION_MAP.average;
  }
  return CLASSIFICATION_MAP.needs_focus;
}

export function formatPercentage(val: number | null | undefined): string {
  if (val === null || val === undefined || isNaN(val)) {
    return "N/A";
  }
  return `${Number(val).toFixed(1)}%`;
}

export function truncateText(text: string, maxLen = 22): string {
  if (!text) return "";
  return text.length > maxLen ? `${text.slice(0, maxLen - 1)}…` : text;
}

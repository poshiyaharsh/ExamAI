/**
 * AI Paper Generator Constants
 * Maps frontend blueprint keys to normalized backend types and display labels.
 * Centralized API endpoints object for faculty AI paper generation.
 */

export const AI_QUESTION_TYPE_LABELS: Record<string, string> = {
  mcq: "MCQ",
  true_false: "True / False",
  fill_blank: "Fill in the Blank",
  short: "Short Answer",
  short_answer: "Short Answer",
  long: "Long Answer",
  long_answer: "Long Answer",
};

// Exact types expected by backend ai_paper_generator module
export const AI_BACKEND_QUESTION_TYPES: Record<string, string> = {
  mcq: "MCQ",
  true_false: "True/False",
  fill_blank: "Fill in the Blank",
  short: "Short Answer",
  short_answer: "Short Answer",
  long: "Long Answer",
  long_answer: "Long Answer",
};

// Backward-compatibility alias
export const aiQuestionTypeLabels = AI_QUESTION_TYPE_LABELS;

export function getQuestionTypeBackendName(key: string): string {
  const clean = String(key || "").trim().toLowerCase();
  return AI_BACKEND_QUESTION_TYPES[clean] ?? (AI_QUESTION_TYPE_LABELS[clean] ?? key);
}

export function getQuestionTypeDisplayLabel(key: string): string {
  const clean = String(key || "").trim().toLowerCase();
  return AI_QUESTION_TYPE_LABELS[clean] ?? key;
}

// Fresh-start configuration for Faculty Paper Generator wizard
export const FRESH_START = {
  restoreDraft: false,          // never restore old form data on mount
  autosaveDraft: false,         // stop saving drafts that are never restored
  showContinueReviewCard: false,// no card pointing to an old finished paper
  resumeRunningJob: true,       // keep existing progress view for a job that is running right now
};

// Central API endpoints configuration
export const AI_API_ENDPOINTS = {
  PARSE_SYLLABUS: "/api/faculty/syllabus/parse/",
  AI_MODELS: "/api/faculty/ai-models/",
  GENERATE: "/api/ai-generator/generate/",
  JOB_STATUS: (id: number | string) => `/api/ai-generator/jobs/${id}/status/`,
  JOB_DETAIL: (id: number | string) => `/api/ai-generator/jobs/${id}/`,
  JOB_CANCEL: (id: number | string) => `/api/ai-generator/jobs/${id}/cancel/`,
  JOB_ACTIVE: "/api/ai-generator/jobs/active/",
  EXPORT_PDF: (id: number | string) => `/api/ai-generator/jobs/${id}/export/pdf/`,
  EXPORT_DOCX: (id: number | string) => `/api/ai-generator/jobs/${id}/export/docx/`,
  LOGS: "/api/ai-generator/logs/",
  LOGS_DOWNLOAD: "/api/ai-generator/logs/download/",
  DRAFT: "/api/ai-generator/draft/",
};

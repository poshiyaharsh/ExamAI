/**
 * Utilities for scoping, validating, and persisting Faculty Paper Generator wizard drafts.
 */

export interface WizardDraftData {
  version: number;
  ownerId: number | string;
  updatedAt: string;
  currentStep: 1 | 2 | 3 | 4;
  examTitle: string;
  subjectName: string;
  duration: string;
  totalMarks: string;
  startsAt: string;
  endsAt: string;
  topics: string[];
  examId: number | null;
}

const WIZARD_DRAFT_VERSION = 2;
const LEGACY_STORAGE_KEY = "examai_faculty_wizard_draft";

export function formatLocalDateTime(date: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  const year = date.getFullYear();
  const month = pad(date.getMonth() + 1);
  const day = pad(date.getDate());
  const hours = pad(date.getHours());
  const minutes = pad(date.getMinutes());
  return `${year}-${month}-${day}T${hours}:${minutes}`;
}

export function getNextRoundScheduleWindow(now = new Date()): { startsAt: string; endsAt: string } {
  const start = new Date(now);
  const m = start.getMinutes();
  if (m === 0 && start.getSeconds() === 0) {
    start.setMinutes(30, 0, 0);
  } else if (m < 30) {
    start.setMinutes(30, 0, 0);
  } else {
    start.setHours(start.getHours() + 1, 0, 0, 0);
  }
  // Default window is 24 hours from start
  const end = new Date(start.getTime() + 24 * 60 * 60 * 1000);
  return {
    startsAt: formatLocalDateTime(start),
    endsAt: formatLocalDateTime(end),
  };
}

export function getScopedDraftKey(userId?: number | string | null): string {
  if (!userId) {
    return "wizard:draft:anonymous";
  }
  return `wizard:draft:${userId}`;
}

/**
 * One-time cleanup of legacy unscoped draft keys to prevent cross-account pollution.
 */
export function cleanupLegacyDrafts(): void {
  try {
    if (typeof window !== "undefined" && window.localStorage) {
      if (localStorage.getItem(LEGACY_STORAGE_KEY)) {
        localStorage.removeItem(LEGACY_STORAGE_KEY);
      }
    }
  } catch {
    // Ignore storage restrictions
  }
}

/**
 * Validates and loads a saved draft for the given user.
 * Discards expired, corrupted, or schema-invalid drafts.
 */
export function loadScopedWizardDraft(userId?: number | string | null): WizardDraftData | null {
  cleanupLegacyDrafts();
  if (!userId) return null;

  try {
    const key = getScopedDraftKey(userId);
    const raw = localStorage.getItem(key);
    if (!raw) return null;

    const parsed = JSON.parse(raw);
    if (
      !parsed ||
      typeof parsed !== "object" ||
      parsed.version !== WIZARD_DRAFT_VERSION ||
      String(parsed.ownerId) !== String(userId)
    ) {
      localStorage.removeItem(key);
      return null;
    }

    return parsed as WizardDraftData;
  } catch {
    return null;
  }
}

/**
 * Saves a wizard draft scoped strictly to the authenticated user ID.
 */
export function saveScopedWizardDraft(
  userId: number | string,
  data: Omit<WizardDraftData, "version" | "ownerId" | "updatedAt">
): void {
  if (!userId) return;

  try {
    const key = getScopedDraftKey(userId);
    const payload: WizardDraftData = {
      ...data,
      version: WIZARD_DRAFT_VERSION,
      ownerId: userId,
      updatedAt: new Date().toISOString(),
    };
    localStorage.setItem(key, JSON.stringify(payload));
  } catch {
    // Ignore storage quota errors
  }
}

/**
 * Removes the wizard draft for a specific user.
 */
export function clearScopedWizardDraft(userId?: number | string | null): void {
  if (!userId) return;
  try {
    const key = getScopedDraftKey(userId);
    localStorage.removeItem(key);
  } catch {}
}

/**
 * Clears wizard drafts on logout for the current user.
 */
export function clearWizardDraftsOnLogout(userId?: number | string | null): void {
  cleanupLegacyDrafts();
  if (userId) {
    clearScopedWizardDraft(userId);
  }
}

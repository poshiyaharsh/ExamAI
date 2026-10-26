/**
 * Utilities for scoping, validating, and persisting Faculty Paper Generator wizard drafts.
 */

export interface WizardDraftData {
  version: number;
  ownerId: number | string;
  draftId?: string;
  documentHash?: string;
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

const WIZARD_DRAFT_VERSION = 3;
const LEGACY_STORAGE_KEYS = [
  "examai_faculty_wizard_draft",
];
const DRAFT_MAX_AGE_MS = 24 * 60 * 60 * 1000; // 24 hours TTL

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

export function getScopedDraftKey(userId?: number | string | null, draftId?: string | null): string {
  if (!userId) {
    return "wizard:draft:anonymous";
  }
  return draftId ? `wizard:draft:${userId}:${draftId}` : `wizard:draft:${userId}`;
}

/**
 * Cleanup legacy unscoped or expired draft keys to prevent cross-exam pollution.
 */
export function cleanupLegacyDrafts(): void {
  try {
    if (typeof window !== "undefined" && window.localStorage) {
      for (const k of LEGACY_STORAGE_KEYS) {
        if (localStorage.getItem(k)) {
          localStorage.removeItem(k);
        }
      }
    }
  } catch {
    // Ignore storage restrictions
  }
}

/**
 * Validates and loads a saved draft for the given user.
 * Discards expired, corrupted, schema-invalid, or mismatched document drafts.
 */
export function loadScopedWizardDraft(
  userId?: number | string | null,
  draftId?: string | null,
  expectedDocHash?: string | null
): WizardDraftData | null {
  cleanupLegacyDrafts();
  if (!userId) return null;

  try {
    const key = getScopedDraftKey(userId, draftId);
    const raw = localStorage.getItem(key);
    if (!raw) return null;

    const parsed = JSON.parse(raw);
    if (
      !parsed ||
      typeof parsed !== "object" ||
      parsed.version !== WIZARD_DRAFT_VERSION ||
      String(parsed.ownerId) !== String(userId)
    ) {
      // Version mismatch or invalid owner: discard
      localStorage.removeItem(key);
      return null;
    }

    // Check expiration TTL
    const updatedTime = new Date(parsed.updatedAt || 0).getTime();
    if (isNaN(updatedTime) || Date.now() - updatedTime > DRAFT_MAX_AGE_MS) {
      localStorage.removeItem(key);
      return null;
    }

    // If expected document hash is specified, discard if document changed
    if (expectedDocHash && parsed.documentHash && parsed.documentHash !== expectedDocHash) {
      localStorage.removeItem(key);
      return null;
    }

    return parsed as WizardDraftData;
  } catch {
    return null;
  }
}

/**
 * Saves a wizard draft scoped strictly to the authenticated user ID and draft ID.
 */
export function saveScopedWizardDraft(
  userId: number | string,
  data: Omit<WizardDraftData, "version" | "ownerId" | "updatedAt">,
  draftId?: string | null
): void {
  if (!userId) return;

  try {
    const key = getScopedDraftKey(userId, draftId);
    const payload: WizardDraftData = {
      ...data,
      version: WIZARD_DRAFT_VERSION,
      ownerId: userId,
      draftId: draftId || undefined,
      updatedAt: new Date().toISOString(),
    };
    localStorage.setItem(key, JSON.stringify(payload));
  } catch {
    // Ignore storage quota errors
  }
}

/**
 * Removes the wizard draft for a specific user and draft ID.
 */
export function clearScopedWizardDraft(userId?: number | string | null, draftId?: string | null): void {
  if (!userId) return;
  try {
    const key = getScopedDraftKey(userId, draftId);
    localStorage.removeItem(key);
    // Also remove default un-suffixed key if draftId provided
    if (draftId) {
      localStorage.removeItem(getScopedDraftKey(userId));
    }
  } catch {}
}

/**
 * Clears all wizard drafts for the current user on logout or new exam initiation.
 */
export function clearWizardDraftsOnLogout(userId?: number | string | null): void {
  cleanupLegacyDrafts();
  if (!userId) return;

  try {
    const prefix = `wizard:draft:${userId}`;
    const keysToRemove: string[] = [];
    for (let i = 0; i < localStorage.length; i++) {
      const k = localStorage.key(i);
      if (k && (k === prefix || k.startsWith(`${prefix}:`))) {
        keysToRemove.push(k);
      }
    }
    for (const k of keysToRemove) {
      localStorage.removeItem(k);
    }
  } catch {}
}

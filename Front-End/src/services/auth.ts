import type { UserRole } from "./api";

export type AuthSession = {
  access: string;
  refresh: string;
  role: UserRole;
  user: {
    id: number;
    first_name: string;
    last_name: string;
    email: string;
    institution?: {
      id: number;
      institution_name?: string;
      name?: string;
      institution_code?: string;
      code?: string;
      status?: string;
    } | null;
  };
};

const AUTH_STORAGE_KEY = "exam_ai_auth";
export const AUTH_SESSION_CHANGED_EVENT = "exam_ai_auth_changed";

function emitAuthSessionChanged() {
  if (typeof window !== "undefined") {
    window.dispatchEvent(new Event(AUTH_SESSION_CHANGED_EVENT));
  }
}

function getSessionStorage(): Storage | null {
  if (typeof window === "undefined") {
    return null;
  }
  try {
    return window.sessionStorage;
  } catch {
    return null;
  }
}

// Remove legacy localStorage session if present to prevent cross-tab contamination from previous sessions
if (typeof window !== "undefined") {
  try {
    window.localStorage.removeItem(AUTH_STORAGE_KEY);
  } catch {
    // Ignore restricted storage environments
  }
}

export const authStorage = {
  getSession(): AuthSession | null {
    const storage = getSessionStorage();
    if (!storage) {
      return null;
    }

    const raw = storage.getItem(AUTH_STORAGE_KEY);
    if (!raw) {
      return null;
    }

    try {
      return JSON.parse(raw) as AuthSession;
    } catch {
      storage.removeItem(AUTH_STORAGE_KEY);
      return null;
    }
  },

  getToken(): string | null {
    return this.getSession()?.access ?? null;
  },

  getRefreshToken(): string | null {
    return this.getSession()?.refresh ?? null;
  },

  getUser(): AuthSession["user"] | null {
    return this.getSession()?.user ?? null;
  },

  getRole(): UserRole | null {
    return this.getSession()?.role ?? null;
  },

  setSession(session: AuthSession) {
    const storage = getSessionStorage();
    if (storage) {
      storage.setItem(AUTH_STORAGE_KEY, JSON.stringify(session));
    }
    emitAuthSessionChanged();
  },

  setAuth(session: AuthSession) {
    this.setSession(session);
  },

  clearSession() {
    const storage = getSessionStorage();
    if (storage) {
      storage.removeItem(AUTH_STORAGE_KEY);
    }
    emitAuthSessionChanged();
  },

  clearAuth() {
    this.clearSession();
  },
};

export const getToken = (): string | null => authStorage.getToken();
export const setAuth = (session: AuthSession): void => authStorage.setAuth(session);
export const clearAuth = (): void => authStorage.clearAuth();


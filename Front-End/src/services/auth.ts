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
  };
};

const AUTH_STORAGE_KEY = "exam_ai_auth";
export const AUTH_SESSION_CHANGED_EVENT = "exam_ai_auth_changed";

function emitAuthSessionChanged() {
  if (typeof window !== "undefined") {
    window.dispatchEvent(new Event(AUTH_SESSION_CHANGED_EVENT));
  }
}

export const authStorage = {
  getSession(): AuthSession | null {
    const raw = localStorage.getItem(AUTH_STORAGE_KEY);
    if (!raw) {
      return null;
    }

    try {
      return JSON.parse(raw) as AuthSession;
    } catch {
      localStorage.removeItem(AUTH_STORAGE_KEY);
      return null;
    }
  },
  setSession(session: AuthSession) {
    localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(session));
    emitAuthSessionChanged();
  },
  clearSession() {
    localStorage.removeItem(AUTH_STORAGE_KEY);
    emitAuthSessionChanged();
  },
};

import axios from "axios";
import { useCallback, useEffect, useMemo, useState } from "react";

import { authApi, type UserRole } from "../../services/api";
import { AUTH_SESSION_CHANGED_EVENT, authStorage, type AuthSession } from "../../services/auth";
import { AuthContext, type AuthContextValue } from "./authContextValue";

function getDashboardPathByRole(role: UserRole): string {
  switch (role) {
    case "admin":
      return "/admin";
    case "faculty":
      return "/faculty";
    default:
      return "/student";
  }
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [session, setSession] = useState<AuthSession | null>(() => authStorage.getSession());
  const [isLoading, setIsLoading] = useState(true);

  const setAuthenticatedSession = useCallback((nextSession: AuthSession) => {
    authStorage.setSession(nextSession);
    setSession(nextSession);
  }, []);

  const clearAuthenticatedSession = useCallback(() => {
    authStorage.clearSession();
    setSession(null);
  }, []);

  const syncSessionFromServer = useCallback(async () => {
    const storedSession = authStorage.getSession();
    if (!storedSession?.access) {
      setSession(null);
      setIsLoading(false);
      return;
    }

    try {
      const meResponse = await authApi.me();
      const normalizedSession: AuthSession = {
        ...storedSession,
        role: meResponse.role,
        user: {
          id: meResponse.user.id,
          first_name: meResponse.user.first_name,
          last_name: meResponse.user.last_name,
          email: meResponse.user.email,
        },
      };

      authStorage.setSession(normalizedSession);
      setSession(normalizedSession);
    } catch (error) {
      if (axios.isAxiosError(error)) {
        if (error.response?.status === 401 || error.response?.status === 403) {
          authStorage.clearSession();
          setSession(null);
        }
      }
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void syncSessionFromServer();
  }, [syncSessionFromServer]);

  useEffect(() => {
    const handleSessionChange = () => {
      setSession(authStorage.getSession());
    };

    window.addEventListener(AUTH_SESSION_CHANGED_EVENT, handleSessionChange);
    return () => {
      window.removeEventListener(AUTH_SESSION_CHANGED_EVENT, handleSessionChange);
    };
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      session,
      isLoading,
      setAuthenticatedSession,
      clearAuthenticatedSession,
      getDashboardPathByRole,
    }),
    [session, isLoading, setAuthenticatedSession, clearAuthenticatedSession]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}


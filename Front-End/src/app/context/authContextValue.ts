import { createContext } from "react";

import type { UserRole } from "../../services/api";
import type { AuthSession } from "../../services/auth";

export type AuthContextValue = {
  session: AuthSession | null;
  isLoading: boolean;
  setAuthenticatedSession: (session: AuthSession) => void;
  clearAuthenticatedSession: () => void;
  getDashboardPathByRole: (role: UserRole) => string;
};

export const AuthContext = createContext<AuthContextValue | undefined>(undefined);

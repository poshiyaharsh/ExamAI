import { Navigate, useLocation } from "react-router";

import type { UserRole } from "../../services/api";
import { authStorage } from "../../services/auth";

type ProtectedRouteProps = {
  allowedRoles: UserRole[];
  children: React.ReactNode;
};

export function ProtectedRoute({ allowedRoles, children }: ProtectedRouteProps) {
  const location = useLocation();
  const session = authStorage.getSession();

  if (!session) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }

  if (!allowedRoles.includes(session.role)) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }

  return <>{children}</>;
}

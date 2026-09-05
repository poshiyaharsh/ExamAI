import { Navigate, useLocation } from "react-router-dom";

import type { UserRole } from "../../services/api";
import { useAuth } from "../context/useAuth";

type ProtectedRouteProps = {
  allowedRoles: UserRole[];
  children: React.ReactNode;
};

export function ProtectedRoute({ allowedRoles, children }: ProtectedRouteProps) {
  const location = useLocation();
  const { session, isLoading, getDashboardPathByRole } = useAuth();

  if (isLoading) {
    return <div className="min-h-screen grid place-items-center text-muted-foreground">Loading...</div>;
  }

  if (!session) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }

  if (!allowedRoles.includes(session.role)) {
    return <Navigate to={getDashboardPathByRole(session.role)} replace />;
  }

  return <>{children}</>;
}

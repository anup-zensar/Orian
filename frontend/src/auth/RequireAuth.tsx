import { Navigate, Outlet, useLocation } from 'react-router';
import { useAuth } from './useAuth';

/**
 * Redirects to /login?next=<path> when nobody is signed in (FR-001). An explicit Sign out goes
 * to plain /login (F8). A stale id (401 after a DB reset) is handled globally (see session.ts).
 */
export function RequireAuth() {
  const { userId, wasExplicitLogout } = useAuth();
  const location = useLocation();

  if (!userId) {
    if (wasExplicitLogout()) return <Navigate to="/login" replace />;
    const next = encodeURIComponent(location.pathname + location.search + location.hash);
    return <Navigate to={`/login?next=${next}`} replace />;
  }
  return <Outlet />;
}

import { Outlet } from 'react-router';
import { EmptyState } from '../components/EmptyState';
import { ErrorState } from '../components/ErrorState';
import { LoadingState } from '../components/LoadingState';
import { useMe } from '../features/users/api';

/** UI guard only: the backend stays the real enforcer (403). Renders child routes or a 403 view. */
export function RequireRole({ roles }: { roles: string[] }) {
  const me = useMe();
  if (me.isLoading) return <LoadingState rows={3} />;
  if (me.isError) return <ErrorState error={me.error} />;
  if (!me.data || !roles.includes(me.data.user.role)) {
    return <EmptyState message="Only the Playbook admin can open Admin" />;
  }
  return <Outlet />;
}

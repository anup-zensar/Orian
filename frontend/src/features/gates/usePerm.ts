import { useMe } from '../users/api';
import { useTransitionAccess } from '../transition/api';

/** Permission check for disabled-with-reason UI: reason is null when allowed (spec 12). */
export function usePerm(
  perm: string,
  transitionId?: string,
): {
  allowed: boolean;
  reason: string | null;
  loading: boolean;
} {
  const me = useMe();
  const access = useTransitionAccess(transitionId);
  if (transitionId) {
    const reason = access.reason(perm);
    return { allowed: reason === null, reason, loading: access.loading };
  }
  if (!me.data) return { allowed: false, reason: null, loading: true };
  const allowed = me.data.permissions.includes(perm);
  return {
    allowed,
    reason: allowed ? null : (me.data.denied_reasons[perm] ?? 'You do not have permission'),
    loading: false,
  };
}

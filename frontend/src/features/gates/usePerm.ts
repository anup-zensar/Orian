import { useMe } from '../users/api';

/** Permission check for disabled-with-reason UI: reason is null when allowed (spec 12). */
export function usePerm(perm: string): {
  allowed: boolean;
  reason: string | null;
  loading: boolean;
} {
  const me = useMe();
  if (!me.data) return { allowed: false, reason: null, loading: true };
  const allowed = me.data.permissions.includes(perm);
  return {
    allowed,
    reason: allowed ? null : (me.data.denied_reasons[perm] ?? 'You do not have permission'),
    loading: false,
  };
}

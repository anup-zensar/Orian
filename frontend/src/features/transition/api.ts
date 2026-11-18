import { useQuery } from '@tanstack/react-query';
import { apiFetch } from '../../api/client';
import { transitionKey } from '../../api/queryKeys';
import { useMe } from '../users/api';
import type { components } from '../../api/schema';

/** Full transition record for the workspace header, tiering, scope and every tab (GET /transitions/{id}). */
export type TransitionDetail = components['schemas']['TransitionDetailOut'];

/** Shared by every workspace tab and the M3 pages; key ['transition', id] (see api/queryKeys.ts). */
export function useTransition(transitionId: string | undefined) {
  return useQuery({
    queryKey: transitionKey(transitionId ?? ''),
    queryFn: ({ signal }) =>
      apiFetch<TransitionDetail>(`/transitions/${encodeURIComponent(transitionId ?? '')}`, {
        signal,
      }),
    enabled: !!transitionId,
  });
}

/**
 * Per-transition permission lookup (BE#1): a permission applies on THIS transition only when the
 * user's role holds it AND the user is the person assigned to that role here. The backend sends the
 * answer as detail.access (permission code -> null when allowed, else the reason). Codes missing
 * from the map fall back to the role-level check from /me.
 */
export function useTransitionAccess(transitionId: string | undefined) {
  const detail = useTransition(transitionId);
  const me = useMe();
  const access = detail.data?.access;
  const loading = !!transitionId && (detail.isLoading || me.isLoading);
  const lookup = (perm: string): string | null => {
    if (loading || !me.data) return 'Loading your permissions';
    if (access && perm in access) return access[perm] ?? null;
    return me.data.permissions.includes(perm)
      ? null
      : (me.data.denied_reasons[perm] ?? 'You do not have permission');
  };
  return {
    loading,
    can: (perm: string) => lookup(perm) === null,
    /** null when allowed, else the denial reason. */
    reason: lookup,
  };
}

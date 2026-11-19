// Non-component helpers shared by the records tabs (styles, URL params, permission lookup).
import { useCallback } from 'react';
import { useSearchParams } from 'react-router';
import { makeStyles, tokens } from '@fluentui/react-components';
import { useMe } from '../users/api';
import { useTransitionAccess } from '../transition/api';

export const useRecordStyles = makeStyles({
  stack: { display: 'flex', flexDirection: 'column', gap: tokens.spacingVerticalL },
  row: {
    display: 'flex',
    gap: tokens.spacingHorizontalM,
    flexWrap: 'wrap',
    alignItems: 'flex-end',
  },
  form: { display: 'flex', flexDirection: 'column', gap: tokens.spacingVerticalM },
  tableWrap: { overflowX: 'auto' },
  // Last (action) column of a wide table: stays visible while the rest scrolls sideways.
  stickyEnd: {
    position: 'sticky',
    right: 0,
    zIndex: 1,
    backgroundColor: tokens.colorNeutralBackground1,
    borderLeft: `1px solid ${tokens.colorNeutralStroke2}`,
  },
  muted: { color: tokens.colorNeutralForeground3 },
  card: {
    display: 'flex',
    flexDirection: 'column',
    gap: tokens.spacingVerticalS,
    padding: tokens.spacingVerticalM,
    border: `1px solid ${tokens.colorNeutralStroke2}`,
    borderRadius: tokens.borderRadiusMedium,
    backgroundColor: tokens.colorNeutralBackground1,
  },
  cardAi: {
    borderLeft: `4px solid ${tokens.colorPaletteBerryBorderActive}`,
  },
  grid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
    gap: tokens.spacingHorizontalM,
  },
});

/** Reads/writes URL search params without touching the others (deep links, spec 12). */
export function useUrlParams() {
  const [params, setParams] = useSearchParams();
  const set = useCallback(
    (patch: Record<string, string | undefined>, replace = true) =>
      setParams(
        (prev) => {
          const next = new URLSearchParams(prev);
          for (const [k, v] of Object.entries(patch)) {
            if (v) next.set(k, v);
            else next.delete(k);
          }
          return next;
        },
        { replace },
      ),
    [setParams],
  );
  return { params, set };
}

/**
 * Permission check with the spec-12 reason (reason is empty when allowed). With a transitionId the
 * per-transition access map decides (role AND assigned on that transition); without it the
 * role-level permission does.
 */
export function usePerm(perm: string, transitionId?: string): { allowed: boolean; reason: string } {
  const me = useMe();
  const access = useTransitionAccess(transitionId);
  if (transitionId) {
    const reason = access.reason(perm);
    return { allowed: reason === null, reason: reason ?? '' };
  }
  if (!me.data) return { allowed: false, reason: 'Loading your permissions' };
  const allowed = me.data.permissions.includes(perm);
  return { allowed, reason: allowed ? '' : (me.data.denied_reasons[perm] ?? 'Not permitted') };
}

/**
 * Item-level owner exception (BE#1): the backend lets the owner of an action or item act on it when
 * their ROLE holds the permission, even if they are not assigned to the transition. Returns the
 * reason to show ('' when allowed) for a row owned by `ownerId`.
 */
export function useOwnerException(perm: string, transitionReason: string) {
  const me = useMe();
  return (ownerId: string | null | undefined): string => {
    if (!transitionReason) return '';
    if (me.data && ownerId && ownerId === me.data.user.id && me.data.permissions.includes(perm))
      return '';
    return transitionReason;
  };
}

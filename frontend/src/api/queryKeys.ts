import type { QueryClient } from '@tanstack/react-query';

/**
 * TanStack Query key conventions (PLAN.md section 4).
 *
 * - Portfolio-level lists: ['transitions', filters], ['control-tower', filters], ['dashboard'],
 *   ['insights', scope, id?], ['approvals', scope], ['drafts', filters], ['outbox', filters],
 *   ['notifications'], ['audit', filters].
 * - EVERYTHING that belongs to one transition starts with ['transition', id, ...], e.g.
 *   ['transition', id] (detail/header), ['transition', id, 'items', filters], ['transition', id,
 *   'evidence'], ['transition', id, 'readiness', gate], ['transition', id, 'scope'] …
 *   so one prefix invalidation refreshes every tab of that transition.
 */
export const transitionKey = (transitionId: string, ...rest: unknown[]) =>
  ['transition', transitionId, ...rest] as const;

/**
 * Call after ANY successful write that affects a transition (status change, evidence review, gate
 * decision, approval, draft send …). Over-invalidation is intentional: the demo must never show stale
 * readiness, RAG, approvals or notifications after a click.
 */
export function invalidateTransitionData(queryClient: QueryClient, transitionId?: string | null) {
  if (transitionId) void queryClient.invalidateQueries({ queryKey: ['transition', transitionId] });
  for (const prefix of [
    'transitions',
    'control-tower',
    'dashboard',
    'insights',
    'approvals',
    'drafts',
    'outbox',
    'notifications',
    'audit',
  ]) {
    void queryClient.invalidateQueries({ queryKey: [prefix] });
  }
}

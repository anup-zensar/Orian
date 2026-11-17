import { useQuery } from '@tanstack/react-query';
import { apiFetch } from '../../api/client';
import { transitionKey } from '../../api/queryKeys';
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

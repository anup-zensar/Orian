// Items, audit and overview hooks shared by the M4 workspace tabs and the audit page.
import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiFetch, type QueryParams } from '../../api/client';
import { invalidateTransitionData, transitionKey } from '../../api/queryKeys';
import type { components } from '../../api/schema';
import type { TransitionDetail } from '../transition/api';

type S = components['schemas'];

export type ItemOut = S['ItemOut'];
export type ItemListOut = S['ItemListOut'];
export type GateLensSummary = S['GateLensSummaryOut'];
export type ItemPatchIn = S['ItemPatchIn'];
export type BulkItemsIn = S['BulkItemsIn'];
export type BulkResult = S['BulkResultOut'];
export type AuditEventOut = S['AuditEventOut'];
export type AuditPageOut = S['AuditPageOut'];
export type GatesOverview = S['GatesOverviewOut'];
export type GateOverview = S['GateOverview'];
export type GateReviewRecord = S['GateReviewRecord'];
export type ConditionOut = S['ConditionOut'];
export type ExceptionOut = S['ExceptionOut'];
export type RiskOut = S['RiskOut'];

/** Query-string filters of GET /transitions/{id}/items (undefined/'' are dropped by apiFetch). */
export interface ItemQuery {
  gate?: string;
  all_gates?: boolean;
  lens?: string;
  source?: string;
  status?: string;
  owner?: string;
  mine?: boolean;
  applicability?: 'applies' | 'excluded' | 'to_confirm' | 'all';
  q?: string;
}

export function useItems(transitionId: string, query: ItemQuery) {
  return useQuery({
    queryKey: transitionKey(transitionId, 'items', query),
    queryFn: ({ signal }) =>
      apiFetch<ItemListOut>(`/transitions/${encodeURIComponent(transitionId)}/items`, {
        query: query as QueryParams,
        signal,
      }),
    placeholderData: keepPreviousData,
  });
}

/** PATCH /items/{id} (integer TransitionItem id). */
export function usePatchItem(transitionId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v: { id: number; body: ItemPatchIn }) =>
      apiFetch<ItemOut>(`/items/${v.id}`, { method: 'PATCH', body: v.body }),
    onSuccess: () => invalidateTransitionData(qc, transitionId),
  });
}

export function useBulkItems(transitionId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: BulkItemsIn) =>
      apiFetch<BulkResult>('/items/bulk', { method: 'POST', body }),
    onSuccess: () => invalidateTransitionData(qc, transitionId),
  });
}

/** Autonomous-mode switch (POST /transitions/{id}/autonomous-mode). */
export function useSetAutonomous(transitionId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (enabled: boolean) =>
      apiFetch<TransitionDetail>(
        `/transitions/${encodeURIComponent(transitionId)}/autonomous-mode`,
        { method: 'POST', body: { enabled } },
      ),
    onSuccess: () => invalidateTransitionData(qc, transitionId),
  });
}

/** Filters of GET /audit. */
export interface AuditQuery {
  transition_id?: string;
  actor?: string;
  actor_type?: string;
  entity?: string;
  from?: string;
  to?: string;
  limit?: number;
  offset?: number;
}

export function useAudit(query: AuditQuery, transitionId?: string) {
  return useQuery({
    // Per-transition audit lives under the transition prefix; the global page under ['audit'].
    queryKey: transitionId
      ? transitionKey(transitionId, 'audit', query)
      : (['audit', query] as const),
    queryFn: ({ signal }) =>
      apiFetch<AuditPageOut>('/audit', { query: query as QueryParams, signal }),
    placeholderData: keepPreviousData,
  });
}

export function useGatesOverview(transitionId: string) {
  return useQuery({
    queryKey: transitionKey(transitionId, 'overview', 'gates'),
    queryFn: ({ signal }) =>
      apiFetch<GatesOverview>(`/transitions/${encodeURIComponent(transitionId)}/gates`, {
        signal,
      }),
  });
}

export function useOverviewConditions(transitionId: string) {
  return useQuery({
    queryKey: transitionKey(transitionId, 'overview', 'conditions'),
    queryFn: ({ signal }) =>
      apiFetch<ConditionOut[]>(`/transitions/${encodeURIComponent(transitionId)}/conditions`, {
        signal,
      }),
  });
}

export function useOverviewExceptions(transitionId: string) {
  return useQuery({
    queryKey: transitionKey(transitionId, 'overview', 'exceptions'),
    queryFn: ({ signal }) =>
      apiFetch<ExceptionOut[]>(`/transitions/${encodeURIComponent(transitionId)}/exceptions`, {
        signal,
      }),
  });
}

export function useOverviewRisks(transitionId: string) {
  return useQuery({
    queryKey: transitionKey(transitionId, 'overview', 'risks'),
    queryFn: ({ signal }) =>
      apiFetch<RiskOut[]>(`/transitions/${encodeURIComponent(transitionId)}/risks`, { signal }),
  });
}

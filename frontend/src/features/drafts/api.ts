import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiFetch } from '../../api/client';
import { invalidateTransitionData } from '../../api/queryKeys';
import type { components } from '../../api/schema';

type S = components['schemas'];
export type Draft = S['DraftOut'];
export type DraftPatch = S['DraftPatchIn'];
export type DraftSendResult = S['DraftSendOut'];

export interface DraftFilters {
  status?: string;
  kind?: string;
  transition_id?: string;
}

export function useDrafts(filters: DraftFilters) {
  return useQuery({
    queryKey: ['drafts', filters],
    queryFn: ({ signal }) =>
      apiFetch<Draft[]>('/orion/drafts', {
        query: { status: filters.status, kind: filters.kind, transition_id: filters.transition_id },
        signal,
      }),
  });
}

export function useDraft(draftId: number | null) {
  return useQuery({
    queryKey: ['drafts', 'one', draftId],
    queryFn: ({ signal }) => apiFetch<Draft>(`/orion/drafts/${draftId}`, { signal }),
    enabled: draftId !== null,
  });
}

export function usePatchDraft() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v: { id: number; patch: DraftPatch }) =>
      apiFetch<Draft>(`/orion/drafts/${v.id}`, { method: 'PATCH', body: v.patch }),
    onSuccess: (d) => invalidateTransitionData(qc, d.transition_id),
  });
}

export function useSendDraft() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) =>
      apiFetch<DraftSendResult>(`/orion/drafts/${id}/send`, { method: 'POST' }),
    onSuccess: (r) => invalidateTransitionData(qc, r.draft.transition_id),
  });
}

export function useDiscardDraft() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => apiFetch<Draft>(`/orion/drafts/${id}/discard`, { method: 'POST' }),
    onSuccess: (d) => invalidateTransitionData(qc, d.transition_id),
  });
}

/** Orion drafts a chaser for open items; nothing is sent (BR-050). */
export function useDraftChaser(transitionId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (itemIds: string[]) =>
      apiFetch<Draft>('/orion/drafts/chaser', {
        method: 'POST',
        body: { transition_id: transitionId, item_ids: itemIds },
      }),
    onSuccess: () => invalidateTransitionData(qc, transitionId),
  });
}

export function useDraftApprovalRequest(transitionId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (gate: string) =>
      apiFetch<Draft>('/orion/drafts/approval-request', {
        method: 'POST',
        body: { transition_id: transitionId, gate },
      }),
    onSuccess: () => invalidateTransitionData(qc, transitionId),
  });
}

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiFetch } from '../../api/client';
import type { components } from '../../api/schema';

type S = components['schemas'];
export type LeadershipUpdate = S['LeadershipUpdateOut'];
export type LeadershipCreate = S['LeadershipUpdateCreateIn'];

export function useLeadershipUpdates() {
  return useQuery({
    queryKey: ['leadership-updates'],
    retry: 1, // surface an error quickly instead of 7-10 s of skeletons
    queryFn: ({ signal }) => apiFetch<LeadershipUpdate[]>('/leadership-updates', { signal }),
  });
}

export function useLeadershipUpdate(id: number | null) {
  return useQuery({
    queryKey: ['leadership-updates', 'one', id],
    queryFn: ({ signal }) => apiFetch<LeadershipUpdate>(`/leadership-updates/${id}`, { signal }),
    enabled: id !== null,
  });
}

/** Orion drafts a leadership update; nothing is sent until a person sends it (BR-050). */
export function useGenerateLeadershipUpdate() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: LeadershipCreate) =>
      apiFetch<LeadershipUpdate>('/orion/leadership-update', { method: 'POST', body }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ['leadership-updates'] }),
  });
}

export function useSendLeadershipUpdate() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v: { id: number; to: string[] }) =>
      apiFetch<LeadershipUpdate>(`/leadership-updates/${v.id}/send`, {
        method: 'POST',
        body: { to: v.to },
      }),
    onSuccess: () => {
      for (const prefix of ['leadership-updates', 'outbox', 'notifications', 'audit']) {
        void qc.invalidateQueries({ queryKey: [prefix] });
      }
    },
  });
}

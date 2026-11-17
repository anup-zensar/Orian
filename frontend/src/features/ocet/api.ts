import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ApiError, apiFetch } from '../../api/client';
import { invalidateTransitionData, transitionKey } from '../../api/queryKeys';
import type { components } from '../../api/schema';

type S = components['schemas'];
export type OcetOut = S['OcetOut'];
export type OcetLine = S['OcetLineOut'];
export type OcetLineIn = S['OcetLineIn'];
export type OcetVersion = S['OcetVersionOut'];
export type OcetCompare = S['OcetCompareOut'];
export type CompareRow = S['CompareRowOut'];
export type VarianceRow = S['VarianceRowOut'];
export type RequestInputsResult = S['RequestInputsOut'];

/** Current OCET of a transition. Resolves to null when no estimate exists yet (404). */
export function useOcet(transitionId: string) {
  return useQuery({
    queryKey: transitionKey(transitionId, 'ocet'),
    queryFn: async ({ signal }) => {
      try {
        return await apiFetch<OcetOut>(`/transitions/${encodeURIComponent(transitionId)}/ocet`, {
          signal,
        });
      } catch (e) {
        if (e instanceof ApiError && e.status === 404) return null;
        throw e;
      }
    },
    refetchOnWindowFocus: false,
  });
}

/** Every OCET write returns the refreshed OcetOut; write it into the cache, then invalidate. */
function useOcetMutation<V>(transitionId: string, fn: (v: V) => Promise<OcetOut>) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: (data) => {
      qc.setQueryData(transitionKey(transitionId, 'ocet'), data);
      invalidateTransitionData(qc, transitionId);
    },
  });
}

export function useCreateOcet(transitionId: string) {
  return useOcetMutation<void>(transitionId, () =>
    apiFetch<OcetOut>(`/transitions/${encodeURIComponent(transitionId)}/ocet`, { method: 'POST' }),
  );
}

export function useSaveLines(transitionId: string, versionId: number) {
  return useOcetMutation<{ lines: OcetLineIn[]; deleted_line_ids: number[] }>(
    transitionId,
    (body) => apiFetch<OcetOut>(`/ocet/versions/${versionId}/lines`, { method: 'PUT', body }),
  );
}

export function useSubmitVersion(transitionId: string, versionId: number) {
  return useOcetMutation<void>(transitionId, () =>
    apiFetch<OcetOut>(`/ocet/versions/${versionId}/submit`, { method: 'POST' }),
  );
}

export function useNewVersion(transitionId: string) {
  return useOcetMutation<void>(transitionId, () =>
    apiFetch<OcetOut>(`/transitions/${encodeURIComponent(transitionId)}/ocet/new-version`, {
      method: 'POST',
    }),
  );
}

export function useRequestInputs(transitionId: string, versionId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (lineIds: number[]) =>
      apiFetch<RequestInputsResult>(`/ocet/versions/${versionId}/request-inputs`, {
        method: 'POST',
        body: { line_ids: lineIds },
      }),
    onSuccess: () => invalidateTransitionData(qc, transitionId),
  });
}

export function useCompare(fromId: number | null, toId: number | null) {
  return useQuery({
    queryKey: ['ocet-compare', fromId, toId],
    queryFn: ({ signal }) =>
      apiFetch<OcetCompare>('/ocet/compare', { query: { from: fromId, to: toId }, signal }),
    enabled: fromId !== null && toId !== null,
    // Lines can change between two opens of the dialog; always refetch on open.
    staleTime: 0,
  });
}

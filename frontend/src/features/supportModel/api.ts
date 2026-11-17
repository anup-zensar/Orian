import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiFetch } from '../../api/client';
import { invalidateTransitionData, transitionKey } from '../../api/queryKeys';
import type { components } from '../../api/schema';

type S = components['schemas'];
export type SupportModel = S['SupportModelOut'];
export type Landscape = S['LandscapeIn'];
export type LandscapeComponent = S['ComponentIO'];
export type Contact = S['ContactIO'];
export type Source = S['SourceIO'];
export type ConfluenceSummary = S['ConfluenceSummaryOut'];
export type GenerateResult = S['GenerateOut'];
export type PptxResult = S['PptxOut'];
export type SupportModelListItem = S['SupportModelListItemOut'];
export type LinkedItem = S['LinkedItemOut'];

export const supportModelKey = (transitionId: string) =>
  transitionKey(transitionId, 'support-model');
/** Prefixed with 'transitions' so invalidateTransitionData also refreshes the list page. */
export const supportModelsListKey = ['transitions', 'support-models'] as const;

export function useSupportModel(transitionId: string) {
  return useQuery({
    queryKey: supportModelKey(transitionId),
    queryFn: ({ signal }) =>
      apiFetch<SupportModel>(`/transitions/${encodeURIComponent(transitionId)}/support-model`, {
        signal,
      }),
  });
}

export function useSupportModels() {
  return useQuery({
    queryKey: supportModelsListKey,
    queryFn: ({ signal }) => apiFetch<SupportModelListItem[]>('/support-models', { signal }),
  });
}

/** Confluence lookup on blur of the link field (writes nothing). */
export function useConfluenceFetch() {
  return useMutation({
    mutationFn: (url: string) =>
      apiFetch<ConfluenceSummary>('/integrations/confluence/fetch', {
        method: 'POST',
        body: { url },
      }),
  });
}

export function useSaveInputs(transitionId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v: { confluenceUrl: string; files: File[] }) => {
      const fd = new FormData();
      if (v.confluenceUrl.trim()) fd.append('confluence_url', v.confluenceUrl.trim());
      for (const f of v.files) fd.append('files', f, f.name);
      return apiFetch<SupportModel>(
        `/transitions/${encodeURIComponent(transitionId)}/support-model/inputs`,
        { method: 'POST', formData: fd },
      );
    },
    onSuccess: (data) => {
      qc.setQueryData(supportModelKey(transitionId), data);
      invalidateTransitionData(qc, transitionId);
    },
  });
}

export function useGenerate(transitionId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () =>
      apiFetch<GenerateResult>(
        `/transitions/${encodeURIComponent(transitionId)}/support-model/generate`,
        { method: 'POST' },
      ),
    onSuccess: (data) => {
      qc.setQueryData(supportModelKey(transitionId), data.support_model);
      invalidateTransitionData(qc, transitionId);
    },
  });
}

export function useSaveLandscape(transitionId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v: { id: number; landscape: Landscape }) =>
      apiFetch<SupportModel>(`/support-models/${v.id}`, {
        method: 'PUT',
        body: { landscape: v.landscape },
      }),
    onSuccess: (data) => {
      qc.setQueryData(supportModelKey(transitionId), data);
      invalidateTransitionData(qc, transitionId);
    },
  });
}

export function useSendForReview(transitionId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) =>
      apiFetch<SupportModel>(`/support-models/${id}/send-for-review`, { method: 'POST' }),
    onSuccess: (data) => {
      qc.setQueryData(supportModelKey(transitionId), data);
      invalidateTransitionData(qc, transitionId);
    },
  });
}

export function useGeneratePptx(transitionId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) =>
      apiFetch<PptxResult>(`/support-models/${id}/pptx`, { method: 'POST' }),
    onSuccess: () => invalidateTransitionData(qc, transitionId),
  });
}

export function useDraftQuestion(transitionId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v: { id: number; index: number }) =>
      apiFetch<S['QuestionDraftOut']>(`/support-models/${v.id}/questions/${v.index}/draft`, {
        method: 'POST',
      }),
    onSuccess: () => invalidateTransitionData(qc, transitionId),
  });
}

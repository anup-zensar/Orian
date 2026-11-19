import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiFetch } from '../../api/client';
import { invalidateTransitionData, transitionKey } from '../../api/queryKeys';
import type { components } from '../../api/schema';

type S = components['schemas'];

export type TransitionCreate = S['TransitionCreateIn'];
export type TransitionUpdate = S['TransitionUpdateIn'];
export type TransitionDetailOut = S['TransitionDetailOut'];
export type ServiceNowProject = S['ServiceNowProjectOut'];
export type TierProposeIn = S['TierProposeIn'];
export type TierProposal = S['TierProposalOut'];
export type TierAssessment = S['TierAssessmentOut'];
export type TierCard = S['TierCardOut'];
export type AIProfile = S['AIProfileOut'];
export type AIProfileIn = S['AIProfileIn'];
export type Scope = S['ScopeOut'];
export type ScopeRow = S['ScopeRowOut'];
export type ScopeDecision = S['ScopeDecisionIn'];
export type Launch = S['LaunchOut'];

const tid = (id: string) => encodeURIComponent(id);

/** GET /integrations/servicenow/projects/{id} (mock lookup used by the intake Fetch button). */
export function useFetchServiceNow() {
  return useMutation({
    mutationFn: (projectId: string) =>
      apiFetch<ServiceNowProject>(`/integrations/servicenow/projects/${tid(projectId.trim())}`),
  });
}

export function useCreateTransition() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: TransitionCreate) =>
      apiFetch<TransitionDetailOut>('/transitions', { method: 'POST', body }),
    onSuccess: (data) => invalidateTransitionData(queryClient, data.id),
  });
}

/** PATCH /transitions/{id}: only the fields present in the body change. */
export function useUpdateTransition(transitionId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: TransitionUpdate) =>
      apiFetch<TransitionDetailOut>(`/transitions/${tid(transitionId)}`, { method: 'PATCH', body }),
    onSuccess: () => invalidateTransitionData(queryClient, transitionId),
  });
}

/** Live BR-011 proposal; refetched on every change of the inputs (no persistence). */
export function useTierProposal(input: TierProposeIn, enabled: boolean) {
  return useQuery({
    queryKey: ['tiering-propose', input],
    queryFn: ({ signal }) =>
      apiFetch<TierProposal>('/tiering/propose', { method: 'POST', body: input, signal }),
    enabled,
    placeholderData: keepPreviousData,
  });
}

export function useProposeTier(transitionId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (answers: Record<string, boolean>) =>
      apiFetch<TierAssessment>(`/transitions/${tid(transitionId)}/tier`, {
        method: 'PUT',
        body: { answers },
      }),
    onSuccess: () => invalidateTransitionData(queryClient, transitionId),
  });
}

export function useConfirmTier(transitionId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: { tier: number; reason?: string | null }) =>
      apiFetch<TierAssessment>(`/transitions/${tid(transitionId)}/tier/confirm`, {
        method: 'POST',
        body,
      }),
    onSuccess: () => invalidateTransitionData(queryClient, transitionId),
  });
}

export function useAiProfile(transitionId: string, enabled: boolean) {
  return useQuery({
    queryKey: transitionKey(transitionId, 'ai-profile'),
    queryFn: ({ signal }) =>
      apiFetch<AIProfile>(`/transitions/${tid(transitionId)}/ai-profile`, { signal }),
    enabled,
  });
}

export function useSaveAiProfile(transitionId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: AIProfileIn) =>
      apiFetch<AIProfile>(`/transitions/${tid(transitionId)}/ai-profile`, { method: 'PUT', body }),
    onSuccess: () => invalidateTransitionData(queryClient, transitionId),
  });
}

export function useScope(transitionId: string) {
  return useQuery({
    queryKey: transitionKey(transitionId, 'scope'),
    queryFn: ({ signal }) => apiFetch<Scope>(`/transitions/${tid(transitionId)}/scope`, { signal }),
  });
}

export function useUpdateScope(transitionId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: { decisions: ScopeDecision[]; source?: 'human' | 'orion_recommendation' }) =>
      apiFetch<Scope>(`/transitions/${tid(transitionId)}/scope`, {
        method: 'PUT',
        body,
      }),
    onSuccess: () => invalidateTransitionData(queryClient, transitionId),
  });
}

export function useLaunchAssessment(transitionId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () =>
      apiFetch<Launch>(`/transitions/${tid(transitionId)}/launch-assessment`, { method: 'POST' }),
    onSuccess: () => invalidateTransitionData(queryClient, transitionId),
  });
}

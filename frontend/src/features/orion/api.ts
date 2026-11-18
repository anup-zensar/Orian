import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiFetch } from '../../api/client';
import { invalidateTransitionData } from '../../api/queryKeys';
import type { components } from '../../api/schema';
import type { Insights } from '../../api/types';
import type { UrlFilters } from '../transitions/useUrlFilters';

/** Orion insights for the dashboard or control tower (FR-010, FR-011). Read-only (BR-050). */
export function useInsights(scope: 'dashboard' | 'control-tower', filters?: UrlFilters) {
  return useQuery({
    queryKey: ['insights', scope, filters ?? {}],
    queryFn: ({ signal }) =>
      apiFetch<Insights>('/orion/insights', { query: { scope, ...filters }, signal }),
    placeholderData: keepPreviousData,
  });
}

// ---- Orion assistant (FR-090) and natural-language actions (CR-02) ----

type S = components['schemas'];
export type OrionMessage = S['ChatOut']['messages'][number];
export type FormMessage = S['FormMessage'];
export type FormField = S['FormField'];
export type QuickActionId = NonNullable<S['ChatIn']['quick_action']>;
export type Proposal = S['ProposalOut'];
export type IntentCatalog = S['IntentCatalogOut'];
export type IntentSpec = S['IntentSpecOut'];
export type AcceptResult = S['AcceptOut'];
export type ExtractResult = S['ExtractOut'];
export type ChatContext = S['ChatContext'];

/** The 7 quick actions of FR-090 (the ids are the API enum; the labels are UI wording). */
export const QUICK_ACTIONS: { id: QuickActionId; label: string }[] = [
  { id: 'start_gate_review', label: 'Start a gate review' },
  { id: 'assess_gate_readiness', label: 'Assess gate readiness' },
  { id: 'track_owner_actions', label: 'Track owner actions' },
  { id: 'draft_owner_reminders', label: 'Draft owner reminders' },
  { id: 'create_leadership_update', label: 'Create a leadership update' },
  { id: 'create_support_model', label: 'Create a support model' },
  { id: 'create_update_ocet', label: 'Create or update OCET' },
];

export interface ChatRequest {
  message?: string;
  quick_action?: QuickActionId;
  form_data?: Record<string, unknown>;
  context: ChatContext;
}

export function useOrionChat() {
  return useMutation({
    mutationFn: (body: ChatRequest) =>
      apiFetch<S['ChatOut']>('/orion/chat', { method: 'POST', body }),
  });
}

export interface ExtractRequest {
  text?: string;
  file?: File;
  transitionId?: string;
}

/** Paste or upload: POST /orion/extract (multipart). Nothing is created, only proposals. */
export function useOrionExtract() {
  return useMutation({
    mutationFn: (req: ExtractRequest) => {
      const fd = new FormData();
      if (req.text !== undefined) fd.append('text', req.text);
      if (req.file) fd.append('file', req.file);
      if (req.transitionId) fd.append('transition_id', req.transitionId);
      return apiFetch<ExtractResult>('/orion/extract', { method: 'POST', formData: fd });
    },
  });
}

/** "Try saying" chips: the intent catalog with what this user may run. */
export function useIntents() {
  return useQuery({
    queryKey: ['orion-intents'],
    queryFn: ({ signal }) => apiFetch<IntentCatalog>('/orion/intents', { signal }),
    staleTime: 5 * 60_000,
    retry: false,
  });
}

/** One proposal in any status (intake page pre-fill, deep links). */
export function useProposal(id: string | null) {
  return useQuery({
    queryKey: ['orion-proposal', id],
    queryFn: ({ signal }) =>
      apiFetch<Proposal>(`/orion/proposals/${encodeURIComponent(id ?? '')}`, { signal }),
    enabled: !!id,
    retry: false,
  });
}

export function useAcceptProposal() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) =>
      apiFetch<AcceptResult>(`/orion/proposals/${id}/accept`, { method: 'POST' }),
    onSuccess: (data) => {
      invalidateTransitionData(queryClient, data.proposal.transition_id);
      void queryClient.invalidateQueries({ queryKey: ['orion-proposal'] });
    },
  });
}

export function useDismissProposal() {
  return useMutation({
    mutationFn: (id: number) =>
      apiFetch<Proposal>(`/orion/proposals/${id}/dismiss`, { method: 'POST' }),
  });
}

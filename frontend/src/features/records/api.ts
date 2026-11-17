// Hooks and type aliases for the M4 records tabs (evidence, gaps/actions, conditions/exceptions/risks,
// hypercare, AI playbook). Types only from the generated schema; every mutation invalidates the
// whole transition (api/queryKeys.ts).
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiFetch } from '../../api/client';
import { invalidateTransitionData, transitionKey } from '../../api/queryKeys';
import type { components } from '../../api/schema';

type S = components['schemas'];

export type Evidence = S['EvidenceOut'];
export type EvidenceType =
  S['Body_add_evidence_api_v1_transitions__transition_id__evidence_post']['type'];
export type ItemList = S['ItemListOut'];
export type Item = S['ItemOut'];
export type ActionRow = S['ActionOut'];
export type ActionCreate = S['ActionCreateIn'];
export type ActionPatch = S['ActionPatchIn'];
export type ConditionRow = S['ConditionOut'];
export type ConditionCreate = S['ConditionCreateIn'];
export type ConditionPatch = S['ConditionPatchIn'];
export type ExceptionRow = S['ExceptionOut'];
export type RiskRow = S['RiskOut'];
export type RiskCreate = S['RiskCreateIn'];
export type Hypercare = S['HypercareOut'];
export type Defect = S['DefectOut'];
export type DefectCreate = S['DefectCreateIn'];
export type DefectPatch = S['DefectPatchIn'];
export type AiProfile = S['AIProfileOut'];
export type AiProfileIn = S['AIProfileIn'];
export type EvalTable = S['EvalTableOut'];
export type EvalRow = S['EvalRowOut'];
export type EvalResultIn = S['EvalResultIn'];
export type Readiness = S['ReadinessCheckOut'];
export type RecommendedAction = S['RecommendedAction'];
export type Draft = S['DraftOut'];

const tid = (id: string) => encodeURIComponent(id);

/** Runs a transition-scoped mutation and refreshes every tab afterwards. */
function useTransitionMutation<TIn, TOut>(transitionId: string, fn: (input: TIn) => Promise<TOut>) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: () => invalidateTransitionData(qc, transitionId),
  });
}

// ---- Items (read-only here) ----
export function useItems(transitionId: string, params: Record<string, string> = {}) {
  return useQuery({
    queryKey: transitionKey(transitionId, 'items', params),
    queryFn: ({ signal }) =>
      apiFetch<ItemList>(`/transitions/${tid(transitionId)}/items`, { query: params, signal }),
  });
}

export function useReadiness(transitionId: string) {
  return useQuery({
    queryKey: transitionKey(transitionId, 'readiness', 'current'),
    queryFn: ({ signal }) =>
      apiFetch<Readiness>(`/transitions/${tid(transitionId)}/readiness`, { signal }),
  });
}

// ---- Evidence ----
export interface EvidenceFilters {
  item?: string;
  type?: string;
  status?: string;
}

export function useEvidence(transitionId: string, filters: EvidenceFilters) {
  return useQuery({
    queryKey: transitionKey(transitionId, 'evidence', filters),
    queryFn: ({ signal }) =>
      apiFetch<Evidence[]>(`/transitions/${tid(transitionId)}/evidence`, {
        query: { ...filters },
        signal,
      }),
  });
}

export function useAddEvidence(transitionId: string) {
  return useTransitionMutation(transitionId, (formData: FormData) =>
    apiFetch<Evidence>(`/transitions/${tid(transitionId)}/evidence`, { method: 'POST', formData }),
  );
}

export function useReviewEvidence(transitionId: string) {
  return useTransitionMutation(
    transitionId,
    (v: { id: string; decision: 'Accept' | 'Reject'; note?: string }) =>
      apiFetch<Evidence>(`/evidence/${encodeURIComponent(v.id)}/review`, {
        method: 'POST',
        body: { decision: v.decision, note: v.note ?? '' },
      }),
  );
}

// ---- Actions ----
export function useActions(transitionId: string) {
  return useQuery({
    queryKey: transitionKey(transitionId, 'actions'),
    queryFn: ({ signal }) =>
      apiFetch<ActionRow[]>(`/transitions/${tid(transitionId)}/actions`, { signal }),
  });
}

export function useCreateAction(transitionId: string) {
  return useTransitionMutation(transitionId, (body: ActionCreate) =>
    apiFetch<ActionRow>(`/transitions/${tid(transitionId)}/actions`, { method: 'POST', body }),
  );
}

export function usePatchAction(transitionId: string) {
  return useTransitionMutation(transitionId, (v: { id: string; patch: ActionPatch }) =>
    apiFetch<ActionRow>(`/actions/${encodeURIComponent(v.id)}`, { method: 'PATCH', body: v.patch }),
  );
}

export function useChaserDraft(transitionId: string) {
  return useTransitionMutation(transitionId, (itemIds: string[]) =>
    apiFetch<Draft>('/orion/drafts/chaser', {
      method: 'POST',
      body: { transition_id: transitionId, item_ids: itemIds },
    }),
  );
}

// ---- Conditions / exceptions / risks ----
export function useConditions(transitionId: string) {
  return useQuery({
    queryKey: transitionKey(transitionId, 'conditions'),
    queryFn: ({ signal }) =>
      apiFetch<ConditionRow[]>(`/transitions/${tid(transitionId)}/conditions`, { signal }),
  });
}

export function useCreateCondition(transitionId: string) {
  return useTransitionMutation(transitionId, (body: ConditionCreate) =>
    apiFetch<ConditionRow>(`/transitions/${tid(transitionId)}/conditions`, {
      method: 'POST',
      body,
    }),
  );
}

export function usePatchCondition(transitionId: string) {
  return useTransitionMutation(transitionId, (v: { id: string; patch: ConditionPatch }) =>
    apiFetch<ConditionRow>(`/conditions/${encodeURIComponent(v.id)}`, {
      method: 'PATCH',
      body: v.patch,
    }),
  );
}

export function useExceptions(transitionId: string) {
  return useQuery({
    queryKey: transitionKey(transitionId, 'exceptions'),
    queryFn: ({ signal }) =>
      apiFetch<ExceptionRow[]>(`/transitions/${tid(transitionId)}/exceptions`, { signal }),
  });
}

export function useRequestException(transitionId: string) {
  return useTransitionMutation(transitionId, (body: { item_id: string; text: string }) =>
    apiFetch<ExceptionRow>(`/transitions/${tid(transitionId)}/exceptions`, {
      method: 'POST',
      body,
    }),
  );
}

export function useRisks(transitionId: string) {
  return useQuery({
    queryKey: transitionKey(transitionId, 'risks'),
    queryFn: ({ signal }) =>
      apiFetch<RiskRow[]>(`/transitions/${tid(transitionId)}/risks`, { signal }),
  });
}

export function useCreateRisk(transitionId: string) {
  return useTransitionMutation(transitionId, (body: RiskCreate) =>
    apiFetch<RiskRow>(`/transitions/${tid(transitionId)}/risks`, { method: 'POST', body }),
  );
}

// ---- Hypercare ----
export function useHypercare(transitionId: string) {
  return useQuery({
    queryKey: transitionKey(transitionId, 'defects'),
    queryFn: ({ signal }) =>
      apiFetch<Hypercare>(`/transitions/${tid(transitionId)}/defects`, { signal }),
  });
}

export function useCreateDefect(transitionId: string) {
  return useTransitionMutation(transitionId, (body: DefectCreate) =>
    apiFetch<Defect>(`/transitions/${tid(transitionId)}/defects`, { method: 'POST', body }),
  );
}

export function usePatchDefect(transitionId: string) {
  return useTransitionMutation(transitionId, (v: { id: string; patch: DefectPatch }) =>
    apiFetch<Defect>(`/defects/${encodeURIComponent(v.id)}`, { method: 'PATCH', body: v.patch }),
  );
}

export function useConfirmNoDefects(transitionId: string) {
  return useTransitionMutation(transitionId, (confirmed: boolean) =>
    apiFetch<Hypercare>(`/transitions/${tid(transitionId)}/defects/confirm-none`, {
      method: 'POST',
      body: { confirmed },
    }),
  );
}

// ---- AI playbook ----
export function useAiProfile(transitionId: string) {
  return useQuery({
    queryKey: transitionKey(transitionId, 'ai-profile'),
    queryFn: ({ signal }) =>
      apiFetch<AiProfile>(`/transitions/${tid(transitionId)}/ai-profile`, { signal }),
  });
}

export function useSaveAiProfile(transitionId: string) {
  return useTransitionMutation(transitionId, (body: AiProfileIn) =>
    apiFetch<AiProfile>(`/transitions/${tid(transitionId)}/ai-profile`, { method: 'PUT', body }),
  );
}

export function useEvalMetrics(transitionId: string) {
  return useQuery({
    queryKey: transitionKey(transitionId, 'eval-metrics'),
    queryFn: ({ signal }) =>
      apiFetch<EvalTable>(`/transitions/${tid(transitionId)}/eval-metrics`, { signal }),
  });
}

export function useSaveEvalResults(transitionId: string) {
  return useTransitionMutation(transitionId, (body: EvalResultIn[]) =>
    apiFetch<EvalTable>(`/transitions/${tid(transitionId)}/eval-results`, { method: 'PUT', body }),
  );
}

export function useImportEvalResults(transitionId: string) {
  return useTransitionMutation(transitionId, () =>
    apiFetch<EvalTable>(`/transitions/${tid(transitionId)}/eval-results/import`, {
      method: 'POST',
    }),
  );
}

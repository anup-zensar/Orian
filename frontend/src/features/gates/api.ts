import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiFetch } from '../../api/client';
import { invalidateTransitionData, transitionKey } from '../../api/queryKeys';
import type { components } from '../../api/schema';

type S = components['schemas'];
export type GatesOverview = S['GatesOverviewOut'];
export type GateOverview = S['GateOverview'];
export type GateReviewRecord = S['GateReviewRecord'];
export type Readiness = S['ReadinessCheckOut'];
export type DecisionOption = S['DecisionOption'];
export type RecommendedAction = S['RecommendedAction'];
export type GateItemRef = S['GateItemRef'];
export type ConditionIn = S['ConditionIn'];
export type GateStepApproval = S['GateApprovalOut'];

export function useGates(transitionId: string) {
  return useQuery({
    queryKey: transitionKey(transitionId, 'gates'),
    queryFn: ({ signal }) =>
      apiFetch<GatesOverview>(`/transitions/${encodeURIComponent(transitionId)}/gates`, { signal }),
  });
}

/** Readiness check for one gate; omit `gate` for the current gate. */
export function useReadiness(transitionId: string, gate: string | undefined) {
  return useQuery({
    queryKey: transitionKey(transitionId, 'readiness', gate ?? 'current'),
    queryFn: ({ signal }) =>
      apiFetch<Readiness>(`/transitions/${encodeURIComponent(transitionId)}/readiness`, {
        query: { gate },
        signal,
      }),
    enabled: !!gate,
  });
}

/** Records a stage review (Proceed / Proceed with conditions / Hold) or a decision/closure outcome. */
export function useRecordGateOutcome(transitionId: string, gate: string, gateType: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v: { outcome: string; note: string; conditions: ConditionIn[] }) => {
      const base = `/transitions/${encodeURIComponent(transitionId)}/gates/${encodeURIComponent(gate)}`;
      return gateType === 'stage_review'
        ? apiFetch<unknown>(`${base}/review`, {
            method: 'POST',
            body: { outcome: v.outcome, note: v.note, conditions: v.conditions },
          })
        : apiFetch<unknown>(`${base}/decision`, {
            method: 'POST',
            body: { decision: v.outcome, note: v.note, conditions: v.conditions },
          });
    },
    onSuccess: () => invalidateTransitionData(qc, transitionId),
  });
}

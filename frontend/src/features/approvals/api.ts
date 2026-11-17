import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiFetch } from '../../api/client';
import { invalidateTransitionData } from '../../api/queryKeys';
import type { components } from '../../api/schema';

type S = components['schemas'];
export type ApprovalRequest = S['ApprovalRequestOut'];
export type ApprovalStep = S['app__schemas__approvals__ApprovalStepOut'];
export type ApprovalScope = 'mine' | 'requested' | 'all';

export function useApprovals(scope: ApprovalScope, enabled = true) {
  return useQuery({
    queryKey: ['approvals', scope],
    queryFn: ({ signal }) =>
      apiFetch<ApprovalRequest[]>('/approvals', { query: { scope }, signal }),
    enabled,
  });
}

/** Approve or reject one step. Reject needs a comment (422 otherwise). */
export function useActOnApproval() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v: {
      request: ApprovalRequest;
      step: number;
      action: 'approve' | 'reject';
      comment: string;
    }) =>
      apiFetch<ApprovalRequest>(
        `/approvals/${encodeURIComponent(v.request.id)}/steps/${v.step}/${v.action}`,
        {
          method: 'POST',
          body: v.action === 'reject' ? { comment: v.comment } : { comment: v.comment || null },
        },
      ),
    onSuccess: (_r, v) => invalidateTransitionData(qc, v.request.transition_id),
  });
}

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiFetch } from '../../api/client';
import type { components } from '../../api/schema';

type S = components['schemas'];
export type PlaybookItem = S['PlaybookItemAdminOut'];
export type PlaybookItemUpdate = S['PlaybookItemUpdateIn'];
export type FlavourRule = S['FlavourRuleOut'];
export type FlavourRulesIn = S['FlavourRulesIn'];
export type GoldenSet = S['GoldenSetOut'];
export type GoldenSetIn = S['GoldenSetIn'];
export type GoldenSetItemIn = S['GoldenSetItemIn'];
export type EvalTargets = S['EvalTargetsOut'];
export type EvalTargetsIn = S['EvalTargetsIn'];
export type EvalMetric = S['EvalMetricOut'];
export type ApprovalChains = S['ApprovalChainsOut'];
export type ApprovalChainsIn = S['ApprovalChainsIn'];
export type ChainStep = S['ChainStep'];
export type ReminderRule = S['app__schemas__admin__ReminderRuleOut'];
export type ReminderRulesIn = S['ReminderRulesIn'];
export type DemoResetOut = S['DemoResetOut'];
export type FastForwardOut = S['FastForwardOut'];
export type TodayOut = S['TodayOut'];

// The three areas are fixed on purpose: the allowed statuses and the readiness maths depend on them.
export const LENSES = ['Business', 'Technical', 'Compliance'] as const;
export const OPERATORS = ['>=', '<=', '<', '>', '==', 'abs<='] as const;

export interface PlaybookFilters {
  q: string;
  source: string;
  gate: string;
  lens: string;
  active: string; // '' | 'true' | 'false'
}

export function usePlaybookItems(f: PlaybookFilters) {
  return useQuery({
    queryKey: ['admin', 'playbook-items', f],
    queryFn: ({ signal }) =>
      apiFetch<PlaybookItem[]>('/admin/playbook-items', {
        signal,
        query: { q: f.q, source: f.source, gate: f.gate, lens: f.lens, active: f.active },
      }),
  });
}

/** PUT helper factory: invalidates every ['admin', ...] query on success. */
function useAdminPut<TIn, TOut>(path: (input: TIn) => string, body: (input: TIn) => unknown) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: TIn) => apiFetch<TOut>(path(input), { method: 'PUT', body: body(input) }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ['admin'] }),
  });
}

export const useUpdatePlaybookItem = () =>
  useAdminPut<{ id: string; body: PlaybookItemUpdate }, PlaybookItem>(
    (i) => `/admin/playbook-items/${encodeURIComponent(i.id)}`,
    (i) => i.body,
  );

export function useGoldenSet(portfolio: string) {
  return useQuery({
    queryKey: ['admin', 'golden-set', portfolio],
    queryFn: ({ signal }) =>
      apiFetch<GoldenSet>(`/admin/portfolios/${encodeURIComponent(portfolio)}/golden-set`, {
        signal,
      }),
    enabled: !!portfolio,
  });
}
export const usePutGoldenSet = () =>
  useAdminPut<{ portfolio: string; body: GoldenSetIn }, GoldenSet>(
    (i) => `/admin/portfolios/${encodeURIComponent(i.portfolio)}/golden-set`,
    (i) => i.body,
  );

export function useEvalTargets() {
  return useQuery({
    queryKey: ['admin', 'eval-targets'],
    queryFn: ({ signal }) => apiFetch<EvalTargets>('/admin/eval-targets', { signal }),
  });
}
export const usePutEvalTargets = () =>
  useAdminPut<EvalTargetsIn, unknown>(
    () => '/admin/eval-targets',
    (b) => b,
  );

export function useApprovalChains() {
  return useQuery({
    queryKey: ['admin', 'approval-chains'],
    queryFn: ({ signal }) => apiFetch<ApprovalChains>('/admin/approval-chains', { signal }),
  });
}
export const usePutApprovalChains = () =>
  useAdminPut<ApprovalChainsIn, unknown>(
    () => '/admin/approval-chains',
    (b) => b,
  );

export function useReminderRules() {
  return useQuery({
    queryKey: ['admin', 'reminder-rules'],
    queryFn: ({ signal }) => apiFetch<ReminderRule[]>('/admin/reminder-rules', { signal }),
  });
}
export const usePutReminderRules = () =>
  useAdminPut<ReminderRulesIn, unknown>(
    () => '/admin/reminder-rules',
    (b) => b,
  );

export function useDemoToday(enabled: boolean) {
  return useQuery({
    queryKey: ['admin', 'demo-today'],
    queryFn: ({ signal }) => apiFetch<TodayOut>('/admin/demo/today', { signal }),
    enabled,
  });
}

/** Reset re-seeds everything, so the whole cache is dropped (the page then refetches on demand). */
export function useDemoReset() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => apiFetch<DemoResetOut>('/admin/demo/reset', { method: 'POST' }),
    onSuccess: () => void qc.resetQueries(),
  });
}

export function useFastForward() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (transition_id: string) =>
      apiFetch<FastForwardOut>('/admin/demo/fast-forward', {
        method: 'POST',
        body: { transition_id },
      }),
    // Changes items, evals and readiness of any transition: refresh all non-admin data.
    onSuccess: () => void qc.invalidateQueries(),
  });
}

export function useSetToday() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (date: string | null) =>
      apiFetch<TodayOut>('/admin/demo/today', { method: 'POST', body: { date } }),
    // "Today" drives due dates, RAG and reminders everywhere.
    onSuccess: () => void qc.invalidateQueries(),
  });
}

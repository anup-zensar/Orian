import { useState } from 'react';
import {
  Badge,
  Field,
  Input,
  MessageBar,
  MessageBarBody,
  Switch,
  Table,
  TableBody,
  TableCell,
  TableHeader,
  TableHeaderCell,
  TableRow,
  Textarea,
} from '@fluentui/react-components';
import { ErrorState } from '../../components/ErrorState';
import { LoadingState } from '../../components/LoadingState';
import { SectionCard } from '../../components/SectionCard';
import { useApiErrorToast } from '../../hooks/useApiErrorToast';
import { formatDate } from '../../lib/format';
import { useReference } from '../reference/api';
import type { TransitionDetail } from '../transition/api';
import {
  useAiProfile,
  useEvalMetrics,
  useImportEvalResults,
  useSaveAiProfile,
  useSaveEvalResults,
  type AiProfile,
  type AiProfileIn,
  type EvalResultIn,
  type EvalRow,
} from './api';
import { GuardedButton } from './common';
import { useRecordStyles, usePerm } from './hooks';

export const TARGETS_BANNER =
  'Targets currently identical for all tiers — tier-specific thresholds to be confirmed by the S&T team (editable in Admin).';

/** Proposed / confirmed tier with rationale and who confirmed (spec 8.7 i). */
export function TierCard({ transition }: { transition: TransitionDetail }) {
  const s = useRecordStyles();
  const ref = useReference();
  const t = transition.tier;
  const shown = t?.confirmed_tier ?? t?.proposed_tier ?? null;
  const tierName = ref.data?.tiers.find((x) => x.tier === shown)?.name;
  return (
    <SectionCard title="Risk tier">
      {shown === null || !t ? (
        <span className={s.muted}>
          No tier proposed yet. The OR focal proposes it from the Tiering page.
        </span>
      ) : (
        <>
          <div className={s.row}>
            <Badge appearance="filled" color={t.confirmed_tier ? 'success' : 'warning'}>
              Tier {shown}
              {tierName ? ` – ${tierName}` : ''}
            </Badge>
            <Badge appearance="outline">{t.confirmed_tier ? 'Confirmed' : 'Proposed'}</Badge>
          </div>
          {t.rationale.length > 0 && (
            <ul style={{ margin: 0, paddingLeft: 20 }}>
              {t.rationale.map((r) => (
                <li key={r}>{r}</li>
              ))}
            </ul>
          )}
          <span className={s.muted}>
            {t.proposed_by ? `Proposed by ${t.proposed_by.name}. ` : ''}
            {t.confirmed_by_or_focal
              ? `Acknowledged by ${t.confirmed_by_or_focal.name} (OR focal). `
              : ''}
            {t.confirmed_by_irm ? `Confirmed by ${t.confirmed_by_irm.name} (IRM). ` : ''}
            {t.confirmed_at ? formatDate(t.confirmed_at) : ''}
          </span>
        </>
      )}
    </SectionCard>
  );
}

type StringKey = Exclude<keyof AiProfileIn, 'multi_agent_orchestration'>;

const PROFILE_FIELDS: { key: StringKey; label: string; multiline?: boolean }[] = [
  { key: 'infrastructure_solution', label: 'Infrastructure solution' },
  { key: 'agentic_framework', label: 'Agentic framework' },
  { key: 'number_of_users', label: 'Number of users' },
  { key: 'models_used', label: 'Models used' },
  { key: 'hosting', label: 'Hosting', multiline: true },
  { key: 'agentic_workflows', label: 'Agentic workflows', multiline: true },
  { key: 'data_sources', label: 'Data sources', multiline: true },
  { key: 'write_actions_detail', label: 'Write actions detail', multiline: true },
];

function ProfileForm({ transitionId, profile }: { transitionId: string; profile: AiProfile }) {
  const s = useRecordStyles();
  const save = useSaveAiProfile(transitionId);
  const showError = useApiErrorToast();
  const perm = usePerm('edit_ai_profile', transitionId);
  const [form, setForm] = useState<AiProfileIn>({
    infrastructure_solution: profile.infrastructure_solution ?? '',
    agentic_framework: profile.agentic_framework ?? '',
    multi_agent_orchestration: profile.multi_agent_orchestration ?? false,
    number_of_users: profile.number_of_users ?? '',
    agentic_workflows: profile.agentic_workflows ?? '',
    models_used: profile.models_used ?? '',
    data_sources: profile.data_sources ?? '',
    hosting: profile.hosting ?? '',
    write_actions_detail: profile.write_actions_detail ?? '',
  });
  const set = (patch: Partial<AiProfileIn>) => setForm((f) => ({ ...f, ...patch }));

  return (
    <div className={s.form}>
      <div className={s.grid}>
        {PROFILE_FIELDS.map((f) => (
          <Field key={f.key} label={f.label}>
            {f.multiline ? (
              <Textarea
                rows={3}
                value={form[f.key]}
                disabled={!!perm.reason}
                onChange={(_, d) => set({ [f.key]: d.value })}
              />
            ) : (
              <Input
                value={form[f.key]}
                disabled={!!perm.reason}
                onChange={(_, d) => set({ [f.key]: d.value })}
              />
            )}
          </Field>
        ))}
      </div>
      <Switch
        label="Multi-agent orchestration"
        checked={form.multi_agent_orchestration}
        disabled={!!perm.reason}
        onChange={(_, d) => set({ multi_agent_orchestration: d.checked })}
      />
      <div className={s.row}>
        <GuardedButton
          appearance="primary"
          reason={perm.reason}
          disabled={save.isPending}
          onClick={() => save.mutate(form, { onError: showError })}
        >
          {save.isPending ? 'Saving…' : 'Save AI profile'}
        </GuardedButton>
        {perm.reason && <span className={s.muted}>{perm.reason}</span>}
      </div>
    </div>
  );
}

/** AI profile form (GET/PUT ai-profile). */
export function AiProfileCard({ transitionId }: { transitionId: string }) {
  const q = useAiProfile(transitionId);
  return (
    <SectionCard title="AI profile">
      {q.isPending ? (
        <LoadingState rows={3} />
      ) : q.isError ? (
        <ErrorState error={q.error} />
      ) : (
        // remount when the server copy changes so the form shows saved values
        <ProfileForm
          key={q.data.updated_at ?? 'new'}
          transitionId={transitionId}
          profile={q.data}
        />
      )}
    </SectionCard>
  );
}

interface Edit {
  num?: string;
  text?: string;
  passed?: boolean;
}

function resultText(r: EvalRow): string {
  if (r.result_number !== null && r.result_number !== undefined)
    return `${r.result_number}${r.unit ?? ''}`;
  return r.result_text ?? '–';
}

function StatusBadge({ status }: { status: EvalRow['status'] }) {
  const color = status === 'pass' ? 'success' : status === 'fail' ? 'danger' : 'informative';
  return (
    <Badge appearance="tint" color={color}>
      {status === 'pass' ? 'Pass' : status === 'fail' ? 'Fail' : 'Not evaluated'}
    </Badge>
  );
}

/** Eval metrics table with manual entry, mock import and the targets banner (spec 8.7 j). */
export function EvalCard({ transitionId }: { transitionId: string }) {
  const s = useRecordStyles();
  const q = useEvalMetrics(transitionId);
  const save = useSaveEvalResults(transitionId);
  const imp = useImportEvalResults(transitionId);
  const showError = useApiErrorToast();
  const perm = usePerm('edit_eval_results', transitionId);
  const [edits, setEdits] = useState<Record<string, Edit>>({});
  const patch = (id: string, e: Edit) =>
    setEdits((all) => ({ ...all, [id]: { ...all[id], ...e } }));
  const dirty = Object.keys(edits).length > 0;

  const saveAll = () => {
    const body: EvalResultIn[] = Object.entries(edits).map(([metric_id, e]) => {
      const row: EvalResultIn = { metric_id };
      if (e.num !== undefined && e.num !== '') row.value_number = Number(e.num);
      if (e.text !== undefined) row.value_text = e.text;
      if (e.passed !== undefined) row.passed = e.passed;
      return row;
    });
    save.mutate(body, { onSuccess: () => setEdits({}), onError: showError });
  };

  return (
    <SectionCard
      title="Evaluation metrics"
      actions={
        <div className={s.row}>
          <GuardedButton
            reason={perm.reason}
            disabled={imp.isPending}
            onClick={() =>
              imp.mutate(undefined, { onSuccess: () => setEdits({}), onError: showError })
            }
          >
            Import eval results (mock)
          </GuardedButton>
          <GuardedButton
            appearance="primary"
            reason={perm.reason}
            disabled={!dirty || save.isPending}
            onClick={saveAll}
          >
            Save results
          </GuardedButton>
        </div>
      }
    >
      {q.isPending ? (
        <LoadingState rows={5} />
      ) : q.isError ? (
        <ErrorState error={q.error} />
      ) : (
        <>
          {!q.data.targets_confirmed && (
            <MessageBar intent="info">
              <MessageBarBody>{TARGETS_BANNER}</MessageBarBody>
            </MessageBar>
          )}
          <span className={s.muted}>
            {q.data.tier
              ? `Targets for tier ${q.data.tier}. `
              : 'No tier yet; showing the lowest tier targets. '}
            {q.data.failed_count} failing, {q.data.not_evaluated_count} not evaluated.
          </span>
          <div className={s.tableWrap}>
            <Table aria-label="Evaluation metrics" size="small">
              <TableHeader>
                <TableRow>
                  {['Metric', 'Target', 'Result', 'Pass / fail', 'Last evaluated'].map((h) => (
                    <TableHeaderCell key={h}>{h}</TableHeaderCell>
                  ))}
                </TableRow>
              </TableHeader>
              <TableBody>
                {q.data.rows.map((r) => {
                  const e = edits[r.metric_id];
                  const isAuto = r.evaluation === 'auto';
                  return (
                    <TableRow key={r.metric_id}>
                      <TableCell>
                        {r.metric_id} – {r.metric}
                      </TableCell>
                      <TableCell>{r.target_text}</TableCell>
                      <TableCell>
                        {perm.reason ? (
                          resultText(r)
                        ) : isAuto ? (
                          <Input
                            type="number"
                            size="small"
                            aria-label={`Result for ${r.metric}`}
                            value={e?.num ?? String(r.result_number ?? '')}
                            onChange={(_, d) => patch(r.metric_id, { num: d.value })}
                          />
                        ) : (
                          <Input
                            size="small"
                            aria-label={`Result for ${r.metric}`}
                            value={e?.text ?? r.result_text ?? ''}
                            onChange={(_, d) => patch(r.metric_id, { text: d.value })}
                          />
                        )}
                      </TableCell>
                      <TableCell>
                        {isAuto ? (
                          <StatusBadge status={e ? 'not evaluated' : r.status} />
                        ) : (
                          <div className={s.row}>
                            <StatusBadge status={e ? 'not evaluated' : r.status} />
                            <Switch
                              label="Passed"
                              checked={e?.passed ?? r.passed ?? false}
                              disabled={!!perm.reason}
                              onChange={(_, d) => patch(r.metric_id, { passed: d.checked })}
                            />
                          </div>
                        )}
                        {isAuto && e && <span className={s.muted}> save to evaluate</span>}
                      </TableCell>
                      <TableCell>{formatDate(r.evaluated_at)}</TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </div>
          {perm.reason && <span className={s.muted}>{perm.reason}</span>}
        </>
      )}
    </SectionCard>
  );
}

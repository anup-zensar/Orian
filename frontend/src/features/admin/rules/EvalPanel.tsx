import { useState } from 'react';
import {
  Button,
  Field,
  Input,
  Select,
  Switch,
  Table,
  TableBody,
  TableCell,
  TableHeader,
  TableHeaderCell,
  TableRow,
  makeStyles,
  tokens,
} from '@fluentui/react-components';
import { DataTable } from '../../../components/DataTable';
import { ErrorState } from '../../../components/ErrorState';
import { LoadingState } from '../../../components/LoadingState';
import { useApiErrorToast } from '../../../hooks/useApiErrorToast';
import {
  OPERATORS,
  useEvalTargets,
  usePutEvalTargets,
  type EvalMetric,
  type EvalTargets,
} from '../api';
import { SaveBar } from '../peopleRulesUi';
import { useDirty } from '../useDirty';
import { useSuccessToast } from '../useSavedToast';
import { AddMetricDialog } from './AddMetricDialog';

type Op = (typeof OPERATORS)[number];
interface Cell {
  target_text: string;
  operator: string;
  value: string;
  unit: string;
}
type Grid = Record<string, Record<number, Cell>>; // metric_id -> tier -> cell

const useStyles = makeStyles({
  toolbar: { display: 'flex', gap: tokens.spacingHorizontalM, alignItems: 'flex-end' },
  metricCol: { minWidth: '200px' },
  cell: {
    display: 'flex',
    flexDirection: 'column',
    gap: tokens.spacingVerticalXS,
  },
  parsed: { display: 'flex', gap: tokens.spacingHorizontalXS },
  small: { width: '72px', minWidth: 0 },
  tiny: { width: '60px', minWidth: 0 },
  meta: { color: tokens.colorNeutralForeground3 },
});

const SYMBOL: Record<string, string> = { '>=': '≥', '<=': '≤', '==': '=', 'abs<=': '|x| ≤' };
const targetTextOf = (c: Cell): string =>
  c.value.trim() === ''
    ? c.target_text
    : `${SYMBOL[c.operator] ?? c.operator} ${c.value.trim()}${c.unit.trim()}`.trim();

const toGrid = (metrics: EvalMetric[]): Grid => {
  const g: Grid = {};
  for (const m of metrics) {
    g[m.metric_id] = {};
    for (const t of m.tiers)
      g[m.metric_id][t.tier] = {
        target_text: t.target_text,
        operator: t.operator ?? '',
        value: t.value === null || t.value === undefined ? '' : String(t.value),
        unit: t.unit ?? '',
      };
  }
  return g;
};

/** Every tier any metric has a target for, in order (follows the tier definitions, not a fixed 1-4). */
const tiersOf = (metrics: EvalMetric[]): number[] =>
  [...new Set(metrics.flatMap((m) => m.tiers.map((t) => t.tier)))].sort((a, b) => a - b);

function Editor({ data }: { data: EvalTargets }) {
  const s = useStyles();
  const [grid, setGrid] = useState<Grid>(() => toGrid(data.metrics));
  const [confirmed, setConfirmed] = useState(data.confirmed);
  const [adding, setAdding] = useState(false);
  const [tier, setTier] = useState<number | null>(null);
  const dirty = useDirty({ grid, confirmed }, 'eval');
  const tiers = tiersOf(data.metrics);
  const save = usePutEvalTargets();
  const showError = useApiErrorToast();
  const ok = useSuccessToast();

  const patch = (id: string, tier: number, p: Partial<Cell>) =>
    setGrid((g) => {
      const next = { ...g[id][tier], ...p };
      // Editing operator/value/unit keeps the readable target text in step (still editable).
      if ('operator' in p || 'value' in p || 'unit' in p) next.target_text = targetTextOf(next);
      return { ...g, [id]: { ...g[id], [tier]: next } };
    });

  const invalid = Object.values(grid).some((tiers) =>
    Object.values(tiers).some(
      (c) =>
        !c.target_text.trim() ||
        (c.value.trim() !== '' && !c.operator) ||
        Number.isNaN(Number(c.value)),
    ),
  );

  const submit = () =>
    save.mutate(
      {
        confirmed,
        metrics: data.metrics.map((m) => ({
          metric_id: m.metric_id,
          tiers: tiers
            .filter((t) => grid[m.metric_id]?.[t])
            .map((t) => {
              const c = grid[m.metric_id][t];
              return {
                tier: t,
                target_text: c.target_text.trim(),
                operator: (c.operator || null) as Op | null,
                value: c.value.trim() === '' ? null : Number(c.value),
                unit: c.unit.trim() || null,
              };
            }),
        })),
      },
      { onSuccess: () => ok('Saved - applies to new transitions'), onError: showError },
    );

  const shown = tier ?? tiers[0];
  return (
    <>
      <div className={s.toolbar}>
        <Field label="Show targets for">
          <Select value={String(shown)} onChange={(_, d) => setTier(Number(d.value))}>
            {tiers.map((t) => (
              <option key={t} value={t}>
                Tier {t}
              </option>
            ))}
          </Select>
        </Field>
        <Button onClick={() => setAdding(true)}>Add metric</Button>
      </div>
      <Switch
        label="Targets confirmed"
        checked={confirmed}
        onChange={(_, d) => setConfirmed(d.checked)}
      />
      <div className={s.meta}>
        Turn this on once the business has agreed these targets. Until then they are shown as draft
        targets.
      </div>
      <DataTable label="Eval targets table" stickyFirstColumn>
        <Table aria-label="Eval targets" size="small">
          <TableHeader>
            <TableRow>
              <TableHeaderCell className={s.metricCol}>Metric</TableHeaderCell>
              <TableHeaderCell>Target for Tier {shown}</TableHeaderCell>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.metrics.map((m) => {
              const c = grid[m.metric_id]?.[shown];
              return (
                <TableRow key={m.metric_id}>
                  <TableCell>
                    {m.metric}
                    <div className={s.meta}>
                      {m.evaluation === 'auto' ? 'Imported automatically' : 'Entered by hand'}
                    </div>
                  </TableCell>
                  <TableCell>
                    {!c ? (
                      '-'
                    ) : c.operator ? (
                      <div className={s.cell}>
                        <div className={s.parsed}>
                          <Select
                            aria-label={`${m.metric} operator`}
                            className={s.small}
                            value={c.operator}
                            onChange={(_, d) => patch(m.metric_id, shown, { operator: d.value })}
                          >
                            {OPERATORS.map((o) => (
                              <option key={o} value={o}>
                                {SYMBOL[o] ?? o}
                              </option>
                            ))}
                          </Select>
                          <Input
                            aria-label={`${m.metric} number`}
                            className={s.tiny}
                            value={c.value}
                            onChange={(_, d) => patch(m.metric_id, shown, { value: d.value })}
                          />
                          <Input
                            aria-label={`${m.metric} unit`}
                            className={s.tiny}
                            value={c.unit}
                            onChange={(_, d) => patch(m.metric_id, shown, { unit: d.value })}
                          />
                        </div>
                        <span className={s.meta}>Reads as: {c.target_text}</span>
                      </div>
                    ) : (
                      <Input
                        aria-label={`${m.metric} target`}
                        value={c.target_text}
                        onChange={(_, d) => patch(m.metric_id, shown, { target_text: d.value })}
                      />
                    )}
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </DataTable>
      <SaveBar
        dirty={dirty}
        saving={save.isPending}
        blockedReason={
          invalid ? 'Every target needs text, and a value needs an operator' : undefined
        }
        onSave={submit}
        onDiscard={() => {
          setGrid(toGrid(data.metrics));
          setConfirmed(data.confirmed);
        }}
      />
      {adding && <AddMetricDialog tiers={tiers} onClose={() => setAdding(false)} />}
    </>
  );
}

export function EvalPanel() {
  const q = useEvalTargets();
  if (q.isLoading) return <LoadingState rows={6} />;
  if (q.isError) return <ErrorState error={q.error} onRetry={() => void q.refetch()} />;
  return q.data ? <Editor key={q.dataUpdatedAt} data={q.data} /> : null;
}

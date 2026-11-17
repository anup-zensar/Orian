import { useState } from 'react';
import {
  Button,
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
import { ErrorState } from '../../components/ErrorState';
import { LoadingState } from '../../components/LoadingState';
import { SectionCard } from '../../components/SectionCard';
import { useApiErrorToast } from '../../hooks/useApiErrorToast';
import {
  OPERATORS,
  useEvalTargets,
  usePutEvalTargets,
  type EvalMetric,
  type EvalTargets,
} from './api';
import { useSuccessToast } from './useSavedToast';

type Op = (typeof OPERATORS)[number];
interface Cell {
  target_text: string;
  operator: string;
  value: string;
  unit: string;
}
type Grid = Record<string, Record<number, Cell>>; // metric_id -> tier -> cell

const useStyles = makeStyles({
  scroll: { overflowX: 'auto' },
  table: { minWidth: '1100px' },
  metricCol: { minWidth: '200px' },
  cell: {
    display: 'flex',
    flexDirection: 'column',
    gap: tokens.spacingVerticalXS,
    minWidth: '210px',
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

function Editor({ data }: { data: EvalTargets }) {
  const s = useStyles();
  const [grid, setGrid] = useState<Grid>(() => toGrid(data.metrics));
  const [confirmed, setConfirmed] = useState(data.confirmed);
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
          tiers: [1, 2, 3, 4]
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
      { onSuccess: () => ok('Eval targets saved'), onError: showError },
    );

  return (
    <SectionCard
      title="Eval metric targets by tier"
      actions={
        <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
          <Switch
            label="Targets confirmed"
            checked={confirmed}
            onChange={(_, d) => setConfirmed(d.checked)}
          />
          <Button appearance="primary" onClick={submit} disabled={save.isPending || invalid}>
            {save.isPending ? 'Saving...' : 'Save targets'}
          </Button>
        </div>
      }
    >
      <div className={s.scroll}>
        <Table aria-label="Eval targets" size="small" className={s.table}>
          <TableHeader>
            <TableRow>
              <TableHeaderCell className={s.metricCol}>Metric</TableHeaderCell>
              {[1, 2, 3, 4].map((t) => (
                <TableHeaderCell key={t}>Tier {t}</TableHeaderCell>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.metrics.map((m) => (
              <TableRow key={m.metric_id}>
                <TableCell>
                  <strong>{m.metric_id}</strong> {m.metric}
                  <div className={s.meta}>{m.evaluation}</div>
                </TableCell>
                {[1, 2, 3, 4].map((t) => {
                  const c = grid[m.metric_id]?.[t];
                  return (
                    <TableCell key={t}>
                      {c ? (
                        <div className={s.cell}>
                          <Input
                            aria-label={`${m.metric_id} tier ${t} target`}
                            value={c.target_text}
                            onChange={(_, d) => patch(m.metric_id, t, { target_text: d.value })}
                          />
                          <div className={s.parsed}>
                            <Select
                              aria-label={`${m.metric_id} tier ${t} operator`}
                              className={s.small}
                              value={c.operator}
                              onChange={(_, d) => patch(m.metric_id, t, { operator: d.value })}
                            >
                              <option value="">-</option>
                              {OPERATORS.map((o) => (
                                <option key={o} value={o}>
                                  {SYMBOL[o] ?? o}
                                </option>
                              ))}
                            </Select>
                            <Input
                              aria-label={`${m.metric_id} tier ${t} value`}
                              className={s.tiny}
                              value={c.value}
                              onChange={(_, d) => patch(m.metric_id, t, { value: d.value })}
                            />
                            <Input
                              aria-label={`${m.metric_id} tier ${t} unit`}
                              className={s.tiny}
                              value={c.unit}
                              onChange={(_, d) => patch(m.metric_id, t, { unit: d.value })}
                            />
                          </div>
                        </div>
                      ) : (
                        '-'
                      )}
                    </TableCell>
                  );
                })}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </SectionCard>
  );
}

export function EvalSection() {
  const q = useEvalTargets();
  if (q.isLoading) return <LoadingState rows={6} />;
  if (q.isError) return <ErrorState error={q.error} onRetry={() => void q.refetch()} />;
  return q.data ? <Editor key={q.dataUpdatedAt} data={q.data} /> : null;
}

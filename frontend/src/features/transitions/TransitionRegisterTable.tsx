// Transition register (spec 8.2 columns, 8.3). Shared by the Transitions page and the Control tower.
import { useMemo, useState, type MouseEvent } from 'react';
import {
  Caption1,
  Table,
  TableBody,
  TableCell,
  TableHeader,
  TableHeaderCell,
  TableRow,
  makeStyles,
  mergeClasses,
  tokens,
  type TableColumnId,
} from '@fluentui/react-components';
import { Star16Filled } from '@fluentui/react-icons';
import { useNavigate } from 'react-router';
import { AppLink } from '../../components/AppLink';
import { RagChip } from '../../components/RagChip';
import { daysLabel, formatDate, toRag } from '../../lib/format';
import { lensColors, ragColors, type Lens } from '../../theme/tokens';
import type { TransitionSummary } from '../../api/types';
import { useReference } from '../reference/api';

const useStyles = makeStyles({
  scroll: {
    overflow: 'auto',
    maxHeight: '70vh',
    border: `1px solid ${tokens.colorNeutralStroke2}`,
    borderRadius: tokens.borderRadiusMedium,
  },
  table: { minWidth: '960px', tableLayout: 'auto' },
  head: {
    position: 'sticky',
    top: 0,
    zIndex: 1,
    backgroundColor: tokens.colorNeutralBackground3,
  },
  row: { cursor: 'pointer' },
  // First and last columns stay visible inside the horizontal scroll (narrow screens).
  stickyLeft: {
    position: 'sticky',
    left: 0,
    zIndex: 1,
    backgroundColor: tokens.colorNeutralBackground1,
    boxShadow: `1px 0 0 ${tokens.colorNeutralStroke2}`,
  },
  stickyRight: {
    position: 'sticky',
    right: 0,
    zIndex: 1,
    backgroundColor: tokens.colorNeutralBackground1,
    boxShadow: `-1px 0 0 ${tokens.colorNeutralStroke2}`,
  },
  headLeft: { left: 0, zIndex: 3 },
  headRight: { right: 0, zIndex: 3 },
  name: { display: 'flex', flexDirection: 'column', minWidth: 0 },
  nameLine: { display: 'inline-flex', alignItems: 'center', gap: tokens.spacingHorizontalXS },
  star: { color: ragColors.Amber.border, display: 'inline-flex' },
  lenses: {
    display: 'flex',
    flexDirection: 'column',
    gap: '2px',
    width: '110px',
    '@media (max-width: 1280px)': { width: 'auto' },
  },
  lens: { display: 'flex', alignItems: 'center', gap: tokens.spacingHorizontalXS },
  lensLetter: {
    width: '12px',
    fontSize: tokens.fontSizeBase100,
    fontWeight: tokens.fontWeightSemibold,
  },
  track: {
    flexGrow: 1,
    height: '6px',
    borderRadius: '3px',
    overflow: 'hidden',
    '@media (max-width: 1280px)': { display: 'none' },
  },
  fill: { height: '100%' },
  pct: { width: '34px', textAlign: 'right', fontSize: tokens.fontSizeBase100 },
  critical: { color: ragColors.Red.foreground, fontWeight: tokens.fontWeightSemibold },
  overdue: { color: ragColors.Red.foreground },
  cell: { display: 'flex', flexDirection: 'column' },
});

interface Column {
  id: string;
  label: string;
  /** Sort key; undefined = not sortable. */
  sort?: (t: TransitionSummary) => string | number;
}

// Columns exactly as spec 8.2: Transition, Portfolio, Region / market, Type, Gate, Lenses, Readiness,
// Gaps, Next decision, OR focal, RAG.
const RAG_ORDER: Record<string, number> = { Red: 0, Amber: 1, Green: 2, Grey: 3 };
const COLUMNS: Column[] = [
  { id: 'name', label: 'Transition', sort: (t) => t.name.toLowerCase() },
  { id: 'portfolio', label: 'Portfolio', sort: (t) => t.portfolio },
  { id: 'region', label: 'Region / market', sort: (t) => `${t.region} ${t.market}` },
  { id: 'type', label: 'Type', sort: (t) => t.project_type },
  { id: 'gate', label: 'Gate', sort: (t) => t.current_gate_short },
  { id: 'lenses', label: 'Lenses (B / T / C)' },
  { id: 'readiness', label: 'Readiness %', sort: (t) => t.overall_readiness },
  { id: 'gaps', label: 'Gaps (open)', sort: (t) => t.critical_gaps * 1000 + t.open_gaps },
  {
    id: 'decision',
    label: 'Next decision',
    sort: (t) => t.days_to_next_decision ?? Number.MAX_SAFE_INTEGER,
  },
  { id: 'focal', label: 'OR focal', sort: (t) => t.or_focal.name },
  { id: 'rag', label: 'RAG', sort: (t) => RAG_ORDER[toRag(t.rag)] },
];

const LENS_LETTERS: [Lens, string][] = [
  ['Business', 'B'],
  ['Technical', 'T'],
  ['Compliance', 'C'],
];

/** Three mini bars; each carries its letter and a % label, so colour is never the only signal. */
function LensBars({ t }: { t: TransitionSummary }) {
  const s = useStyles();
  return (
    <div className={s.lenses} role="group" aria-label="Readiness by lens">
      {LENS_LETTERS.map(([lens, letter]) => {
        const pct = t.lens_readiness[lens];
        const c = lensColors[lens];
        return (
          <div key={lens} className={s.lens} title={`${lens} ${pct}%`}>
            <span className={s.lensLetter} style={{ color: c.foreground }} aria-hidden>
              {letter}
            </span>
            <span className={s.track} style={{ backgroundColor: c.background }} aria-hidden>
              <span
                className={s.fill}
                style={{
                  display: 'block',
                  width: `${Math.min(100, pct)}%`,
                  backgroundColor: c.border,
                }}
              />
            </span>
            <span className={s.pct} aria-hidden>
              {pct}%
            </span>
            <span style={{ position: 'absolute', left: -9999 }}>{`${lens} ${pct}%`}</span>
          </div>
        );
      })}
    </div>
  );
}

export function TransitionRegisterTable({ rows }: { rows: TransitionSummary[] }) {
  const s = useStyles();
  const navigate = useNavigate();
  const [sort, setSort] = useState<{ id: string; dir: 'ascending' | 'descending' } | null>(null);
  // Names set in Admin, also for inactive types and portfolios (an unknown code shows itself).
  const { data: reference } = useReference();
  const typeLabels = new Map(
    (reference?.project_types ?? []).map((p) => [p.code, p.label || p.code]),
  );
  const portfolioLabels = new Map(
    (reference?.portfolio_details ?? []).map((p) => [p.name, p.label || p.name]),
  );

  const sorted = useMemo(() => {
    const col = COLUMNS.find((c) => c.id === sort?.id);
    if (!sort || !col?.sort) return rows;
    const key = col.sort;
    const factor = sort.dir === 'ascending' ? 1 : -1;
    return [...rows].sort((a, b) => {
      const x = key(a);
      const y = key(b);
      return (x < y ? -1 : x > y ? 1 : 0) * factor;
    });
  }, [rows, sort]);

  const open = (id: string) => navigate(`/transitions/${id}/overview`);
  const onRowClick = (e: MouseEvent, id: string) => {
    if ((e.target as HTMLElement).closest('a')) return; // the name link navigates itself
    open(id);
  };
  const onSort = (id: TableColumnId) => {
    const key = String(id);
    setSort((prev) =>
      prev?.id === key
        ? { id: key, dir: prev.dir === 'ascending' ? 'descending' : 'ascending' }
        : { id: key, dir: 'ascending' },
    );
  };

  return (
    <div className={s.scroll}>
      <Table sortable aria-label="Transition register" className={s.table}>
        <TableHeader className={s.head}>
          <TableRow>
            {COLUMNS.map((c) => (
              <TableHeaderCell
                key={c.id}
                className={mergeClasses(
                  s.head,
                  c.id === 'name' && s.headLeft,
                  c.id === 'rag' && s.headRight,
                )}
                sortDirection={sort?.id === c.id ? sort.dir : undefined}
                onClick={c.sort ? () => onSort(c.id) : undefined}
                style={c.sort ? undefined : { cursor: 'default' }}
              >
                {c.label}
              </TableHeaderCell>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {sorted.map((t) => {
            const days = t.days_to_next_decision;
            return (
              <TableRow key={t.id} className={s.row} onClick={(e) => onRowClick(e, t.id)}>
                <TableCell className={s.stickyLeft}>
                  <div className={s.name}>
                    <span className={s.nameLine}>
                      {t.is_flagship && (
                        <span className={s.star} role="img" aria-label="Flagship transition">
                          <Star16Filled />
                        </span>
                      )}
                      <AppLink to={`/transitions/${t.id}/overview`}>{t.name}</AppLink>
                    </span>
                    <Caption1>{t.id}</Caption1>
                  </div>
                </TableCell>
                <TableCell>{portfolioLabels.get(t.portfolio) ?? t.portfolio}</TableCell>
                <TableCell>
                  <div className={s.cell}>
                    <span>{t.region}</span>
                    <Caption1>{t.market}</Caption1>
                  </div>
                </TableCell>
                <TableCell>{typeLabels.get(t.project_type) ?? t.project_type}</TableCell>
                <TableCell>{t.current_gate_short}</TableCell>
                <TableCell>
                  <LensBars t={t} />
                </TableCell>
                <TableCell>
                  <strong>{t.overall_readiness}%</strong>
                </TableCell>
                <TableCell>
                  <div className={s.cell}>
                    <span>{t.open_gaps} open</span>
                    {t.critical_gaps > 0 && (
                      <Caption1 className={s.critical}>{t.critical_gaps} critical</Caption1>
                    )}
                  </div>
                </TableCell>
                <TableCell>
                  <div className={s.cell}>
                    <span>{formatDate(t.next_decision_date)}</span>
                    <Caption1 className={days !== null && days < 0 ? s.overdue : undefined}>
                      {t.next_decision_date ? daysLabel(days) : 'No decision date'}
                    </Caption1>
                  </div>
                </TableCell>
                <TableCell>{t.or_focal.name}</TableCell>
                <TableCell className={s.stickyRight}>
                  <RagChip rag={toRag(t.rag)} />
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </div>
  );
}

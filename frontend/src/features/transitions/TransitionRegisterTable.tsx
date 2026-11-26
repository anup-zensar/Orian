// Transition register (spec 8.2 columns, 8.3; CR-03 item 6). One implementation, used by the Transitions
// page and the Control tower. Columns come from configuration (gate labels, custom fields flagged
// "show in list"); the same column definitions feed the on-screen table and the CSV download.
import { useMemo, useState, type MouseEvent, type ReactNode } from 'react';
import {
  Button,
  Caption1,
  Menu,
  MenuItem,
  MenuList,
  MenuPopover,
  MenuTrigger,
  Table,
  TableBody,
  TableCell,
  TableHeader,
  TableHeaderCell,
  TableRow,
  makeStyles,
  tokens,
  type TableColumnId,
} from '@fluentui/react-components';
import { ArrowDownload16Regular, Star16Filled } from '@fluentui/react-icons';
import { useNavigate } from 'react-router';
import { AppLink } from '../../components/AppLink';
import { DataTable } from '../../components/DataTable';
import { RagChip } from '../../components/RagChip';
import dayjs from 'dayjs';
import { formatDate, plural, toRag } from '../../lib/format';
import { lensColors, ragColors, type Lens } from '../../theme/tokens';
import type { IntakeFieldRef, TransitionSummary } from '../../api/types';
import { useReference } from '../reference/api';
import { useIntakeFields, useOptionLabel } from '../reference/options';

const useStyles = makeStyles({
  // Compact table: tight cell padding, headers and cells wrap, so the whole register fits at 1280px.
  table: {
    tableLayout: 'auto',
    '& th, & td': { paddingInline: '4px', minWidth: 0 },
    // DataTable keeps headers on one line; here they may wrap to two.
    '& th, & th div': { whiteSpace: 'normal', lineHeight: tokens.lineHeightBase200 },
  },
  row: { cursor: 'pointer' },
  toolbar: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: tokens.spacingHorizontalM,
    marginBottom: tokens.spacingVerticalS,
  },
  name: { display: 'flex', flexDirection: 'column', minWidth: 0 },
  nameLine: { display: 'inline-flex', alignItems: 'center', gap: tokens.spacingHorizontalXS },
  star: { color: ragColors.Amber.border, display: 'inline-flex' },
  lenses: { display: 'flex', flexDirection: 'column', gap: '2px', width: '140px' },
  lens: { display: 'flex', alignItems: 'center', gap: tokens.spacingHorizontalXS },
  lensName: {
    width: '62px',
    fontSize: '11px',
    fontWeight: tokens.fontWeightSemibold,
  },
  track: { flexGrow: 1, minWidth: '30px', height: '6px', borderRadius: '3px', overflow: 'hidden' },
  fill: { height: '100%' },
  pct: { width: '32px', textAlign: 'right', fontSize: '11px' },
  critical: { color: ragColors.Red.foreground, fontWeight: tokens.fontWeightSemibold },
  cell: { display: 'flex', flexDirection: 'column' },
  nowrap: { whiteSpace: 'nowrap' },
});

interface Column {
  id: string;
  label: string;
  /** Plain text of the cell: the CSV value and the sort key. */
  text: (t: TransitionSummary) => string;
  /** Numeric sort key when text would sort wrongly; undefined = sort by text. */
  sort?: (t: TransitionSummary) => string | number;
  cell: (t: TransitionSummary) => ReactNode;
  nowrap?: boolean;
  /** On-screen header when it differs from the CSV header. */
  head?: string;
  /** CSV only: its value is shown inside another column on screen (Project ID, Type). */
  csvOnly?: boolean;
}

const RAG_ORDER: Record<string, number> = { Red: 0, Amber: 1, Green: 2, Grey: 3 };

// Written in full, in the order the client asked for.
const LENSES: Lens[] = ['Business', 'Compliance', 'Technical'];

/** Three mini bars; each carries its name and a % label, so colour is never the only signal. */
function LensBars({ t }: { t: TransitionSummary }) {
  const s = useStyles();
  return (
    <div className={s.lenses} role="group" aria-label="Readiness by lens">
      {LENSES.map((lens) => {
        const pct = t.lens_readiness[lens];
        const c = lensColors[lens];
        return (
          <div key={lens} className={s.lens}>
            <span className={s.lensName} style={{ color: c.foreground }}>
              {lens}
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
            <span className={s.pct}>{pct}%</span>
          </div>
        );
      })}
    </div>
  );
}

/** Value of one custom field as text: dropdown -> option label, date -> formatted, yes/no -> Yes / No. */
function customText(
  f: IntakeFieldRef,
  t: TransitionSummary,
  optionLabel: (list: string, value: string) => string,
  short = false,
): string {
  const v = t.custom_fields[f.key];
  if (v === undefined || v === null || v === '') return '–';
  if (f.type === 'boolean') return v ? 'Yes' : 'No';
  if (f.type === 'date') return short ? dayjs(String(v)).format('D MMM YY') : formatDate(String(v));
  const list = f.option_list;
  const one = (x: unknown) =>
    list && f.type !== 'user' ? optionLabel(list, String(x)) : String(x);
  return Array.isArray(v) ? v.map(one).join(', ') : one(v);
}

function useColumns(): Column[] {
  const s = useStyles();
  const { data: reference } = useReference();
  const optionLabel = useOptionLabel();
  // Admin decides which custom fields are columns ("Show it as a column in the transitions list").
  const custom = useIntakeFields().filter((f) => !f.builtin && f.show_in_list);
  // Names set in Admin, also for inactive types and portfolios (an unknown code shows itself).
  const typeLabels = new Map(
    (reference?.project_types ?? []).map((p) => [p.code, p.label || p.code]),
  );
  const portfolioLabels = new Map(
    (reference?.portfolio_details ?? []).map((p) => [p.name, p.label || p.name]),
  );
  const typeLabel = (t: TransitionSummary) => typeLabels.get(t.project_type) ?? t.project_type;
  const portfolioLabel = (t: TransitionSummary) => portfolioLabels.get(t.portfolio) ?? t.portfolio;

  const gateOrder = (reference?.gates ?? []).map((g) => g.code);

  return [
    {
      id: 'name',
      label: 'Transition',
      head: 'Transition · Project ID',
      text: (t) => `${t.name} (${t.id})`,
      sort: (t) => t.name.toLowerCase(),
      cell: (t) => (
        <div className={s.name}>
          <span className={s.nameLine}>
            {t.is_flagship && (
              <span className={s.star} role="img" aria-label="Flagship transition">
                <Star16Filled />
              </span>
            )}
            <AppLink to={`/transitions/${t.id}/overview`}>{t.name}</AppLink>
          </span>
          <Caption1>{[t.id, t.servicenow_project_id].filter(Boolean).join(' · ')}</Caption1>
        </div>
      ),
    },
    {
      id: 'project_id',
      label: 'Project ID',
      text: (t) => t.servicenow_project_id ?? '',
      cell: (t) => t.servicenow_project_id ?? '–',
      csvOnly: true,
    },
    {
      id: 'portfolio',
      label: 'Portfolio',
      head: 'Portfolio · type',
      text: portfolioLabel,
      cell: (t) => (
        <div className={s.cell}>
          <span>{portfolioLabel(t)}</span>
          <Caption1>{typeLabel(t)}</Caption1>
        </div>
      ),
    },
    {
      id: 'region',
      label: 'Region',
      text: (t) => t.region,
      cell: (t) => (
        <div className={s.cell}>
          <span>{t.region}</span>
          <Caption1>{t.market}</Caption1>
        </div>
      ),
    },
    { id: 'type', label: 'Type', text: typeLabel, cell: typeLabel, csvOnly: true },
    {
      id: 'gate',
      label: 'Gate',
      text: (t) => t.current_gate_short,
      cell: (t) => t.current_gate_short,
      sort: (t) => gateOrder.indexOf(t.current_gate),
      nowrap: true,
    },
    ...custom.map((f): Column => ({
      id: f.key,
      label: f.label,
      text: (t) => customText(f, t, optionLabel),
      cell: (t) => customText(f, t, optionLabel, true),
      // ISO dates sort correctly as text; the display text ("9 Mar 2027") does not
      sort: f.type === 'date' ? (t) => String(t.custom_fields[f.key] ?? '') : undefined,
      nowrap: f.type === 'date',
    })),
    {
      id: 'readiness',
      label: 'Readiness',
      text: (t) =>
        `${t.overall_readiness}% (${LENSES.map((l) => `${l} ${t.lens_readiness[l]}%`).join(', ')})`,
      sort: (t) => t.overall_readiness,
      cell: (t) => (
        <div className={s.cell}>
          <strong>{t.overall_readiness}%</strong>
          <LensBars t={t} />
        </div>
      ),
    },
    {
      id: 'gaps',
      label: 'Critical gaps/risks',
      text: (t) => String(t.critical_gaps),
      sort: (t) => t.critical_gaps * 1000 + t.open_gaps,
      cell: (t) => (
        <div className={s.cell}>
          <span className={t.critical_gaps > 0 ? s.critical : undefined}>{t.critical_gaps}</span>
          <Caption1>{t.open_gaps} open</Caption1>
        </div>
      ),
    },
    { id: 'focal', label: 'OR focal', text: (t) => t.or_focal.name, cell: (t) => t.or_focal.name },
    {
      id: 'rag',
      label: 'RAG',
      text: (t) => (toRag(t.rag) === 'Grey' ? 'Not started' : toRag(t.rag)),
      sort: (t) => RAG_ORDER[toRag(t.rag)],
      cell: (t) => <RagChip rag={toRag(t.rag)} />,
      nowrap: true,
    },
  ];
}

// A leading = + - @ would run as a formula in Excel; a leading quote keeps it text.
const csvCell = (v: string) => `"${(/^[=+\-@\t\r]/.test(v) ? "'" + v : v).replace(/"/g, '""')}"`;

/** Excel opens UTF-8 CSV correctly only with a BOM. */
function downloadCsv(columns: Column[], rows: TransitionSummary[]) {
  const lines = [columns.map((c) => c.label), ...rows.map((t) => columns.map((c) => c.text(t)))];
  const blob = new Blob(['﻿' + lines.map((l) => l.map(csvCell).join(',')).join('\r\n')], {
    type: 'text/csv;charset=utf-8',
  });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'transitions.csv';
  a.click();
  URL.revokeObjectURL(url);
}

export function TransitionRegisterTable({ rows }: { rows: TransitionSummary[] }) {
  const s = useStyles();
  const navigate = useNavigate();
  const columns = useColumns();
  const shown = columns.filter((c) => !c.csvOnly);
  const [sort, setSort] = useState<{ id: string; dir: 'ascending' | 'descending' } | null>(null);

  const sorted = useMemo(() => {
    const col = columns.find((c) => c.id === sort?.id);
    if (!sort || !col) return rows;
    const key = col.sort ?? ((t: TransitionSummary) => col.text(t).toLowerCase());
    const factor = sort.dir === 'ascending' ? 1 : -1;
    return [...rows].sort((a, b) => {
      const x = key(a);
      const y = key(b);
      return (x < y ? -1 : x > y ? 1 : 0) * factor;
    });
  }, [rows, columns, sort]);

  const onRowClick = (e: MouseEvent, id: string) => {
    if ((e.target as HTMLElement).closest('a')) return; // the name link navigates itself
    navigate(`/transitions/${id}/overview`);
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
    <>
      <div className={s.toolbar}>
        <Caption1 role="status">{plural(rows.length, 'transition')}</Caption1>
        <Menu>
          <MenuTrigger disableButtonEnhancement>
            <Button className="no-print" size="small" icon={<ArrowDownload16Regular />}>
              Download
            </Button>
          </MenuTrigger>
          <MenuPopover>
            <MenuList>
              <MenuItem onClick={() => downloadCsv(columns, sorted)}>Excel (.csv)</MenuItem>
              <MenuItem onClick={() => window.print()}>PDF (print to PDF)</MenuItem>
            </MenuList>
          </MenuPopover>
        </Menu>
      </div>
      <DataTable label="Transition register" stickyFirstColumn>
        <Table sortable aria-label="Transition register" className={s.table}>
          <TableHeader>
            <TableRow>
              {shown.map((c) => (
                <TableHeaderCell
                  key={c.id}
                  className={c.nowrap ? s.nowrap : undefined}
                  sortDirection={sort?.id === c.id ? sort.dir : undefined}
                  onClick={() => onSort(c.id)}
                >
                  {c.head ?? c.label}
                </TableHeaderCell>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {sorted.map((t) => (
              <TableRow key={t.id} className={s.row} onClick={(e) => onRowClick(e, t.id)}>
                {shown.map((c) => (
                  <TableCell key={c.id} className={c.nowrap ? s.nowrap : undefined}>
                    {c.cell(t)}
                  </TableCell>
                ))}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </DataTable>
    </>
  );
}

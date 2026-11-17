import { useState } from 'react';
import {
  Badge,
  Button,
  Caption1,
  Dialog,
  DialogActions,
  DialogBody,
  DialogContent,
  DialogSurface,
  DialogTitle,
  Field,
  Select,
  makeStyles,
  mergeClasses,
  tokens,
} from '@fluentui/react-components';
import { EmptyState } from '../../components/EmptyState';
import { ErrorState } from '../../components/ErrorState';
import { LoadingState } from '../../components/LoadingState';
import { useCompare, type CompareRow, type OcetVersion } from './api';
import { fmtFull, fmtPct, fmtSigned } from './format';

const useStyles = makeStyles({
  pickers: { display: 'flex', gap: tokens.spacingHorizontalL, flexWrap: 'wrap' },
  wrap: { overflowX: 'auto', maxHeight: '50vh' },
  table: { borderCollapse: 'collapse', width: '100%' },
  th: {
    textAlign: 'right',
    padding: tokens.spacingHorizontalS,
    backgroundColor: tokens.colorNeutralBackground3,
    position: 'sticky',
    top: 0,
  },
  td: {
    textAlign: 'right',
    padding: tokens.spacingHorizontalS,
    borderTop: `1px solid ${tokens.colorNeutralStroke2}`,
    fontVariantNumeric: 'tabular-nums',
  },
  left: { textAlign: 'left' },
  sub: {
    textAlign: 'left',
    padding: tokens.spacingHorizontalS,
    fontWeight: tokens.fontWeightSemibold,
    backgroundColor: tokens.colorNeutralBackground2,
  },
});

const STATUS_COLOR = {
  added: 'success',
  removed: 'danger',
  changed: 'warning',
  same: 'informative',
} as const;

function Rows({ rows, label }: { rows: CompareRow[]; label: string }) {
  const s = useStyles();
  return (
    <>
      <tr>
        <td colSpan={7} className={s.sub}>
          {label}
        </td>
      </tr>
      {rows.map((r) => (
        <tr key={`${label}-${r.key}`}>
          <td className={mergeClasses(s.td, s.left)}>
            {r.description || r.category}
            {r.description && <Caption1 block>{r.category}</Caption1>}
          </td>
          <td className={s.td}>{fmtFull(r.from_total)}</td>
          <td className={s.td}>{fmtFull(r.to_total)}</td>
          <td className={s.td}>{fmtSigned(r.abs_change)}</td>
          <td className={s.td}>{fmtPct(r.pct_change)}</td>
          <td className={mergeClasses(s.td, s.left)}>
            <Badge appearance="tint" color={STATUS_COLOR[r.status]}>
              {r.status}
            </Badge>
          </td>
        </tr>
      ))}
    </>
  );
}

/** Compare two versions of the estimate: diff table by line and by category (spec 8.10). */
export function CompareDialog(props: {
  versions: OcetVersion[];
  initialFrom: number;
  initialTo: number;
  onClose: () => void;
}) {
  const s = useStyles();
  const [from, setFrom] = useState(props.initialFrom);
  const [to, setTo] = useState(props.initialTo);
  const q = useCompare(from === to ? null : from, from === to ? null : to);
  const options = (
    <>
      {props.versions.map((v) => (
        <option key={v.id} value={v.id}>
          {`v${v.version} (${v.status})`}
        </option>
      ))}
    </>
  );
  const d = q.data;
  return (
    <Dialog open onOpenChange={(_, o) => !o.open && props.onClose()}>
      <DialogSurface style={{ maxWidth: 980, width: '95vw' }}>
        <DialogBody>
          <DialogTitle>Compare OCET versions</DialogTitle>
          <DialogContent>
            <div className={s.pickers}>
              <Field label="From (older)">
                <Select value={String(from)} onChange={(_, o) => setFrom(Number(o.value))}>
                  {options}
                </Select>
              </Field>
              <Field label="To (newer)">
                <Select value={String(to)} onChange={(_, o) => setTo(Number(o.value))}>
                  {options}
                </Select>
              </Field>
            </div>
            {from === to ? (
              <EmptyState message="Pick two different versions to compare." />
            ) : q.isLoading ? (
              <LoadingState rows={5} />
            ) : q.isError ? (
              <ErrorState error={q.error} onRetry={() => void q.refetch()} />
            ) : d ? (
              <>
                <p>
                  Total {fmtFull(d.from_total)} to {fmtFull(d.to_total)} {d.currency}:{' '}
                  <strong>
                    {fmtSigned(d.total_abs)} ({fmtPct(d.total_pct)})
                  </strong>
                </p>
                <div className={s.wrap}>
                  <table className={s.table}>
                    <thead>
                      <tr>
                        <th className={mergeClasses(s.th, s.left)}>Line</th>
                        <th className={s.th}>v{d.from_version.version} total</th>
                        <th className={s.th}>v{d.to_version.version} total</th>
                        <th className={s.th}>Change</th>
                        <th className={s.th}>%</th>
                        <th className={mergeClasses(s.th, s.left)}>Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      <Rows rows={d.rows} label="By line" />
                      <Rows rows={d.category_rows} label="By category" />
                    </tbody>
                  </table>
                </div>
              </>
            ) : null}
          </DialogContent>
          <DialogActions>
            <Button appearance="primary" onClick={props.onClose}>
              Close
            </Button>
          </DialogActions>
        </DialogBody>
      </DialogSurface>
    </Dialog>
  );
}

import { Badge, Caption1, Select, makeStyles, tokens } from '@fluentui/react-components';
import { KpiTile } from '../../components/KpiTile';
import type { OcetOut } from './api';
import { fmtFull, fmtK, fmtPct, fmtSigned } from './format';

const useStyles = makeStyles({
  root: { display: 'flex', flexDirection: 'column', gap: tokens.spacingVerticalM },
  row: { display: 'flex', flexWrap: 'wrap', gap: tokens.spacingHorizontalL, alignItems: 'center' },
  facts: { display: 'flex', flexDirection: 'column' },
  tiles: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
    gap: tokens.spacingHorizontalM,
  },
  chain: {
    display: 'flex',
    alignItems: 'center',
    gap: tokens.spacingHorizontalS,
    flexWrap: 'wrap',
  },
});

const VERSION_STATUS_COLOR: Record<
  string,
  'informative' | 'warning' | 'success' | 'danger' | 'brand' | 'subtle'
> = {
  Draft: 'informative',
  'Inputs pending': 'warning',
  Submitted: 'brand',
  'Planner approved': 'brand',
  Approved: 'success',
  Rejected: 'danger',
  Superseded: 'subtle',
};

const STEP_COLOR = {
  Waiting: 'subtle',
  Pending: 'warning',
  Approved: 'success',
  Rejected: 'danger',
  Cancelled: 'subtle',
} as const;

export function StatusChip({ status }: { status: string }) {
  return (
    <Badge appearance="tint" color={VERSION_STATUS_COLOR[status] ?? 'informative'}>
      {status}
    </Badge>
  );
}

/** Header: currency, start year, horizon, version selector + status, chain progress, KPIs. */
export function OcetHeader(props: { data: OcetOut; onPickVersion: (versionId: number) => void }) {
  const s = useStyles();
  const { data } = props;
  const { estimate: e, version: v, variance: va, approval } = data;
  const lastYear = e.start_year + e.horizon_years - 1;
  return (
    <div className={s.root}>
      <div className={s.row}>
        <div className={s.facts}>
          <Caption1>Currency</Caption1>
          <strong>{e.currency}</strong>
        </div>
        <div className={s.facts}>
          <Caption1>Start year</Caption1>
          <strong>{e.start_year}</strong>
        </div>
        <div className={s.facts}>
          <Caption1>Horizon</Caption1>
          <strong>
            {e.horizon_years} years ({e.start_year} to {lastYear})
          </strong>
        </div>
        <div className={s.facts}>
          <Caption1>Version</Caption1>
          <span className={s.chain}>
            <Select
              size="small"
              aria-label="OCET version (choosing an earlier version opens the comparison)"
              value={String(v.id)}
              onChange={(_, d) => props.onPickVersion(Number(d.value))}
            >
              {data.versions.map((x) => (
                <option key={x.id} value={x.id}>
                  {`v${x.version} (${x.status})`}
                </option>
              ))}
            </Select>
            <StatusChip status={v.status} />
          </span>
        </div>
        <div className={s.facts}>
          <Caption1>Approval chain</Caption1>
          {approval ? (
            <span className={s.chain}>
              {approval.steps.map((st, i) => (
                <span key={st.step} className={s.chain}>
                  {i > 0 && <span aria-hidden>{'->'}</span>}
                  <span>{st.label}</span>
                  <Badge appearance="tint" color={STEP_COLOR[st.status]}>
                    {st.status}
                  </Badge>
                </span>
              ))}
            </span>
          ) : (
            <span className={s.chain}>
              <span>Planner</span>
              <span aria-hidden>{'->'}</span>
              <span>OLM</span>
              <Badge appearance="tint" color="subtle">
                Not submitted
              </Badge>
            </span>
          )}
        </div>
      </div>
      <div className={s.tiles}>
        <KpiTile
          label={`${e.horizon_years}-year total (${e.currency})`}
          value={fmtK(data.total)}
          tone="info"
          caption={`${fmtFull(data.total)} in full`}
        />
        <KpiTile
          label={
            va.previous_version === null
              ? 'Variance vs previous version'
              : `Variance vs v${va.previous_version}`
          }
          value={va.previous_version === null ? 'n/a' : fmtSigned(va.total_abs)}
          tone={
            va.previous_version === null || va.total_abs === 0
              ? 'neutral'
              : va.total_abs > 0
                ? 'warning'
                : 'success'
          }
          caption={va.previous_version === null ? 'First version' : fmtPct(va.total_pct)}
        />
      </div>
    </div>
  );
}

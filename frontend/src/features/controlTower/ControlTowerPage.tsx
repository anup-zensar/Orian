// FR-011 Control tower (spec 8.2): filters, KPI tiles, heatmap, readiness by region, register,
// escalation queue, decision calendar, Orion insights and the operating rhythm. Everything is
// computed by the API: the register, regions, escalations and calendar use all filters; the KPI
// tiles ignore the tile filters and the heatmap ignores portfolio and gate (the user keeps context).
import { Button, Caption1, makeStyles, tokens } from '@fluentui/react-components';
import { ErrorState } from '../../components/ErrorState';
import { InsightsCard } from '../../components/InsightsCard';
import { KpiTile } from '../../components/KpiTile';
import { LoadingState } from '../../components/LoadingState';
import { PageHeader } from '../../components/PageHeader';
import { SectionCard } from '../../components/SectionCard';
import { EmptyState } from '../../components/EmptyState';
import { useInsights } from '../orion/api';
import { FilterBar } from '../transitions/FilterBar';
import { TransitionRegisterTable } from '../transitions/TransitionRegisterTable';
import { useUrlFilters, type FilterKey } from '../transitions/useUrlFilters';
import { plural } from '../../lib/format';
import { useControlTower } from './api';
import { Heatmap } from './Heatmap';
import { RegionChart } from './RegionChart';
import { CalendarCard, EscalationCard, OperatingRhythmCard } from './SideCards';

const useStyles = makeStyles({
  tiles: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))',
    gap: tokens.spacingHorizontalM,
    marginBottom: tokens.spacingVerticalL,
  },
  // Columns wrap (single column at ~1024 px) instead of squeezing the content.
  pair: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(540px, 1fr))',
    gap: tokens.spacingHorizontalL,
    marginBottom: tokens.spacingVerticalL,
  },
  triple: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))',
    gap: tokens.spacingHorizontalL,
    margin: `${tokens.spacingVerticalL} 0`,
    alignItems: 'start',
  },
  block: { marginBottom: tokens.spacingVerticalL },
});

export function ControlTowerPage() {
  const s = useStyles();
  const { filters, update, clear, notice } = useUrlFilters();
  const ct = useControlTower(filters);
  const insights = useInsights('control-tower', filters);
  const d = ct.data;

  /** Does the tile's filter match what is currently in the URL? */
  const isActive = (f: Record<string, string>) => {
    const entries = Object.entries(f);
    return entries.length > 0 && entries.every(([k, v]) => filters[k as FilterKey] === v);
  };
  /** Click a tile: apply its filter, or remove it when it is already applied. */
  const toggleTile = (f: Record<string, string>) => {
    const patch: Partial<Record<FilterKey, string | undefined>> = {};
    const active = isActive(f);
    for (const [k, v] of Object.entries(f)) patch[k as FilterKey] = active ? undefined : v;
    update(patch);
  };

  return (
    <>
      <PageHeader
        title="Control tower"
        subtitle="Portfolio-wide readiness: where it is Red, what is blocked and which decisions are next."
      />
      <FilterBar filters={filters} update={update} clear={clear} notice={notice} />

      {ct.isLoading ? (
        <LoadingState rows={8} />
      ) : ct.error || !d ? (
        <ErrorState error={ct.error} onRetry={() => void ct.refetch()} />
      ) : (
        <>
          <div className={s.tiles}>
            {d.kpis.map((k) => {
              const hasFilter = Object.keys(k.filter ?? {}).length > 0;
              return (
                <KpiTile
                  key={k.key}
                  label={k.label}
                  value={k.value}
                  tone={k.tone}
                  hint={k.hint}
                  active={hasFilter ? isActive(k.filter) : undefined}
                  onClick={hasFilter ? () => toggleTile(k.filter) : undefined}
                />
              );
            })}
          </div>

          <div className={s.pair}>
            <SectionCard title="Heatmap: portfolio by gate">
              {filters.portfolio && filters.gate && (
                <Caption1 role="status" style={{ display: 'block', marginBottom: 6 }}>
                  Selected: {filters.portfolio} at{' '}
                  {d.heatmap.gates.find((g) => g.code === filters.gate)?.short ?? filters.gate}{' '}
                  (click the cell again to clear)
                </Caption1>
              )}
              <Heatmap
                data={d.heatmap}
                selectedPortfolio={filters.portfolio}
                selectedGate={filters.gate}
                onSelect={(portfolio, gate) =>
                  filters.portfolio === portfolio && filters.gate === gate
                    ? update({ portfolio: undefined, gate: undefined })
                    : update({ portfolio, gate })
                }
              />
            </SectionCard>
            <SectionCard title="Readiness by region">
              <RegionChart data={d.readiness_by_region} />
            </SectionCard>
          </div>

          <div className={s.block}>
            <SectionCard
              title={`Transition register (${plural(d.transitions.length, 'transition')})`}
            >
              {d.transitions.length === 0 ? (
                <EmptyState
                  message="No transitions match these filters"
                  action={<Button onClick={clear}>Clear filters</Button>}
                />
              ) : (
                <TransitionRegisterTable rows={d.transitions} />
              )}
            </SectionCard>
          </div>

          <div className={s.triple}>
            <EscalationCard rows={d.escalations} />
            <CalendarCard rows={d.calendar} today={d.today} />
            <InsightsCard
              title="Orion: control tower insights"
              data={insights.data}
              isLoading={insights.isLoading}
              error={insights.error}
              onRetry={() => void insights.refetch()}
            />
          </div>

          <OperatingRhythmCard rows={d.operating_rhythm} />
        </>
      )}
    </>
  );
}

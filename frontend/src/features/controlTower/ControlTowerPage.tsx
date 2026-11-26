// FR-011 Control tower (spec 8.2): KPI tiles, heatmap, readiness by region, escalation queue, decision
// calendar, Orion insights and the operating rhythm. Everything is computed by the API. The full
// register (CR-03) sits on this page: a heatmap cell filters it in place; a KPI tile opens /transitions
// with the same URL filters. Old deep links (/control-tower?portfolio=X) still show the filtered tower.
import { useState } from 'react';
import { Button, Caption1, Tag, makeStyles, tokens } from '@fluentui/react-components';
import { ArrowRight16Regular } from '@fluentui/react-icons';
import { useNavigate } from 'react-router';
import { EmptyState } from '../../components/EmptyState';
import { ErrorState } from '../../components/ErrorState';
import { InsightsCard } from '../../components/InsightsCard';
import { KpiTile } from '../../components/KpiTile';
import { LoadingState } from '../../components/LoadingState';
import { PageHeader } from '../../components/PageHeader';
import { SectionCard } from '../../components/SectionCard';
import { useInsights } from '../orion/api';
import { TransitionRegisterTable } from '../transitions/TransitionRegisterTable';
import { useUrlFilters } from '../transitions/useUrlFilters';
import { useControlTower } from './api';
import { Heatmap } from './Heatmap';
import { RegionChart } from './RegionChart';
import { CalendarCard, EscalationCard, OperatingRhythmNote } from './SideCards';

const useStyles = makeStyles({
  tiles: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 125px), 1fr))',
    gap: tokens.spacingHorizontalM,
    marginBottom: tokens.spacingVerticalL,
  },
  // Columns wrap (single column when the content is narrow) instead of squeezing the content.
  pair: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 480px), 1fr))',
    gap: tokens.spacingHorizontalL,
    marginBottom: tokens.spacingVerticalL,
  },
  triple: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 340px), 1fr))',
    gap: tokens.spacingHorizontalL,
    marginBottom: tokens.spacingVerticalL,
    alignItems: 'start',
  },
  register: { marginBottom: tokens.spacingVerticalL },
  filtered: {
    display: 'flex',
    flexWrap: 'wrap',
    alignItems: 'center',
    gap: tokens.spacingHorizontalS,
    marginBottom: tokens.spacingVerticalM,
  },
});

/** URL for /transitions from a set of filter keys (the same keys the register filters use). */
function transitionsLink(filters: Record<string, string | undefined>) {
  const q = new URLSearchParams();
  for (const [k, v] of Object.entries(filters)) if (v) q.set(k, v);
  const text = q.toString();
  return text ? `/transitions?${text}` : '/transitions';
}

export function ControlTowerPage() {
  const s = useStyles();
  const navigate = useNavigate();
  const { filters, clear, notice } = useUrlFilters();
  // Heatmap cell = portfolio + gate, applied to the register below (not to the URL).
  const [cell, setCell] = useState<{ portfolio: string; gate: string } | null>(null);
  const ct = useControlTower(filters);
  const insights = useInsights('control-tower', filters);
  const d = ct.data;
  // a selected cell is dropped when the filters change (it may no longer exist)
  const filterKey = JSON.stringify(filters);
  const [cellKey, setCellKey] = useState(filterKey);
  if (cellKey !== filterKey) {
    setCellKey(filterKey);
    setCell(null);
  }
  const registerRows = (d?.transitions ?? []).filter(
    (t) => !cell || (t.portfolio === cell.portfolio && t.current_gate === cell.gate),
  );
  const gateShort = (code: string) => d?.heatmap.gates.find((g) => g.code === code)?.short ?? code;
  const filterCount = Object.keys(filters).length;
  const filterText = Object.entries(filters)
    .map(([k, v]) => `${k.replace(/_/g, ' ')} ${v}`)
    .join(', ');

  return (
    <>
      <PageHeader
        title="Control tower"
        subtitle="Portfolio-wide readiness: where it is Red, what is blocked and which decisions are next."
        actions={
          <Button
            icon={<ArrowRight16Regular />}
            iconPosition="after"
            onClick={() => navigate(transitionsLink(filters))}
          >
            View all in Transitions
          </Button>
        }
      />
      {(filterCount > 0 || notice) && (
        <div className={s.filtered} role="status">
          {filterCount > 0 && <Caption1>Filtered view: {filterText}</Caption1>}
          {notice && <Caption1>{notice}</Caption1>}
          {filterCount > 0 && (
            <Button size="small" appearance="subtle" onClick={clear}>
              Clear filters
            </Button>
          )}
        </div>
      )}

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
                  caption={hasFilter ? 'Open in Transitions' : undefined}
                  onClick={hasFilter ? () => navigate(transitionsLink(k.filter)) : undefined}
                />
              );
            })}
          </div>

          <div className={s.pair}>
            <SectionCard title="M&C portfolio view – transitions in play">
              <Caption1>
                Portfolio × gate readiness heatmap · count of transitions · colour = worst RAG ·
                click a cell to filter the register
              </Caption1>
              <Heatmap
                data={d.heatmap}
                selectedPortfolio={cell?.portfolio}
                selectedGate={cell?.gate}
                onSelect={(portfolio, gate) => {
                  setCell({ portfolio, gate });
                  document
                    .getElementById('transition-register')
                    ?.scrollIntoView?.({ behavior: 'smooth' });
                }}
              />
            </SectionCard>
            <SectionCard title="Readiness by region">
              <RegionChart data={d.readiness_by_region} />
            </SectionCard>
          </div>

          <div className={s.register}>
            <SectionCard
              id="transition-register"
              title="Transition register"
              actions={
                cell && (
                  <Tag
                    dismissible
                    dismissIcon={{ 'aria-label': 'Clear heatmap filter' }}
                    onClick={() => setCell(null)}
                  >
                    {cell.portfolio} at {gateShort(cell.gate)}
                  </Tag>
                )
              }
            >
              {registerRows.length > 0 ? (
                <TransitionRegisterTable rows={registerRows} />
              ) : (
                <EmptyState message="No transitions in this cell" />
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

          <OperatingRhythmNote rows={d.operating_rhythm} />
        </>
      )}
    </>
  );
}

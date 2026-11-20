import {
  Badge,
  Body1,
  Button,
  Caption1,
  Subtitle2,
  makeStyles,
  tokens,
} from '@fluentui/react-components';
import dayjs from 'dayjs';
import { useState } from 'react';
import { EmptyState } from '../../../components/EmptyState';
import { ErrorState } from '../../../components/ErrorState';
import { LoadingState } from '../../../components/LoadingState';
import { SectionCard } from '../../../components/SectionCard';
import { DecisionPanel } from '../../gates/DecisionPanel';
import { ReadinessCard } from '../../gates/ReadinessCard';
import { useGates, useReadiness, type GateOverview } from '../../gates/api';
import type { TabProps } from '../types';

const useStyles = makeStyles({
  page: { display: 'flex', flexDirection: 'column', gap: tokens.spacingVerticalL },
  head: { display: 'flex', gap: tokens.spacingHorizontalS, alignItems: 'center', flexWrap: 'wrap' },
  history: { margin: 0, paddingLeft: tokens.spacingHorizontalXL },
  body: { display: 'flex', flexDirection: 'column', gap: tokens.spacingVerticalM, minWidth: 0 },
});

const stateColor = (st: string) =>
  st === 'done' ? 'success' : st === 'current' ? 'brand' : 'subtle';
const stateLabel = (st: string) =>
  st === 'done' ? 'Done' : st === 'current' ? 'Current' : 'Upcoming';

function GatePanel(props: {
  transitionId: string;
  gate: GateOverview;
  open: boolean;
  onToggle: () => void;
}) {
  const s = useStyles();
  const { gate } = props;
  const readiness = useReadiness(props.transitionId, props.open ? gate.code : undefined);
  const isCurrent = gate.state === 'current';

  return (
    <SectionCard
      id={`gate-${gate.code}`}
      title={`${gate.short} · ${gate.label}`}
      actions={
        <div className={s.head}>
          <Badge appearance="tint" color={stateColor(gate.state)}>
            {stateLabel(gate.state)}
          </Badge>
          <Badge appearance="outline">{gate.type.replace('_', ' ')}</Badge>
          {gate.carried_items > 0 && (
            <Badge appearance="outline">{gate.carried_items} carried items</Badge>
          )}
          <Button
            size="small"
            aria-expanded={props.open}
            aria-controls={`gate-body-${gate.code}`}
            onClick={props.onToggle}
          >
            {props.open ? 'Hide' : 'Show'}
          </Button>
        </div>
      }
    >
      {props.open && (
        <div id={`gate-body-${gate.code}`} className={s.body}>
          {gate.reviews.length === 0 ? (
            <Caption1>No decisions recorded for this gate yet.</Caption1>
          ) : (
            <ul className={s.history} aria-label={`${gate.short} history`}>
              {gate.reviews.map((r) => (
                <li key={r.id}>
                  <Body1>
                    <strong>{r.outcome}</strong> by {r.decided_by?.name ?? 'unknown'} ·{' '}
                    {dayjs(r.decided_at).format('D MMM YYYY HH:mm')}
                  </Body1>
                  {r.note && <Caption1> · "{r.note}"</Caption1>}
                  {r.conditions_created.length > 0 && (
                    <Caption1> · conditions created: {r.conditions_created.join(', ')}</Caption1>
                  )}
                </li>
              ))}
            </ul>
          )}

          <>
            <Subtitle2 as="h3">Readiness check</Subtitle2>
            {readiness.isLoading && <LoadingState rows={5} />}
            {readiness.isError && <ErrorState error={readiness.error} />}
            {readiness.data && (
              <>
                <ReadinessCard
                  transitionId={props.transitionId}
                  readiness={readiness.data}
                  isCurrent={isCurrent}
                />
                {gate.state !== 'done' && (
                  <DecisionPanel
                    transitionId={props.transitionId}
                    gate={gate}
                    readiness={readiness.data}
                    isCurrent={isCurrent}
                  />
                )}
              </>
            )}
          </>
        </div>
      )}
    </SectionCard>
  );
}

/** Gates & decisions tab (FR-034, spec 8.7e): per-gate panels, readiness check, outcomes, history. */
export function GatesTab({ transitionId }: TabProps) {
  const s = useStyles();
  const gates = useGates(transitionId);
  const [toggled, setToggled] = useState<Record<string, boolean>>({});

  if (gates.isLoading) return <LoadingState rows={6} />;
  if (gates.isError) return <ErrorState error={gates.error} />;
  if (!gates.data || gates.data.gates.length === 0)
    return <EmptyState message="No gates for this transition." />;

  const current = gates.data.current_gate;
  return (
    <div className={s.page}>
      {gates.data.gates.map((g) => (
        <GatePanel
          key={g.code}
          transitionId={transitionId}
          gate={g}
          open={toggled[g.code] ?? g.code === current}
          onToggle={() =>
            setToggled((prev) => ({ ...prev, [g.code]: !(prev[g.code] ?? g.code === current) }))
          }
        />
      ))}
    </div>
  );
}

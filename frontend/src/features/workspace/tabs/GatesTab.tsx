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
  upcoming: { opacity: 0.85 },
});

const stateColor = (st: string) =>
  st === 'done' ? 'success' : st === 'current' ? 'brand' : 'subtle';
const stateLabel = (st: string) =>
  st === 'done' ? 'Done' : st === 'current' ? 'Current' : 'Upcoming';

function GatePanel(props: {
  transitionId: string;
  gate: GateOverview;
  selected: boolean;
  onSelect: () => void;
}) {
  const s = useStyles();
  const { gate } = props;
  const readiness = useReadiness(props.transitionId, props.selected ? gate.code : undefined);
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
          {!props.selected && (
            <Button size="small" onClick={props.onSelect}>
              {isCurrent ? 'Show readiness' : 'Show readiness check'}
            </Button>
          )}
        </div>
      }
    >
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

      {props.selected && (
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
      )}
    </SectionCard>
  );
}

/** Gates & decisions tab (FR-034, spec 8.7e): per-gate panels, readiness check, outcomes, history. */
export function GatesTab({ transitionId }: TabProps) {
  const s = useStyles();
  const gates = useGates(transitionId);
  const [selected, setSelected] = useState<string | null>(null);

  if (gates.isLoading) return <LoadingState rows={6} />;
  if (gates.isError) return <ErrorState error={gates.error} />;
  if (!gates.data || gates.data.gates.length === 0)
    return <EmptyState message="No gates for this transition." />;

  const active = selected ?? gates.data.current_gate;
  return (
    <div className={s.page}>
      {gates.data.gates.map((g) => (
        <GatePanel
          key={g.code}
          transitionId={transitionId}
          gate={g}
          selected={g.code === active}
          onSelect={() => setSelected(g.code)}
        />
      ))}
    </div>
  );
}

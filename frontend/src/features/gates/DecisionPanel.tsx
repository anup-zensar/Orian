import { useState } from 'react';
import { Caption1, Checkbox, Subtitle2, makeStyles, tokens } from '@fluentui/react-components';
import { Toolbar } from '../../components/layout/Toolbar';
import { ReasonButton } from './ReasonButton';
import { DecisionDialog } from './DecisionDialog';
import { usePerm } from './usePerm';
import type { GateOverview, Readiness } from './api';

const useStyles = makeStyles({
  root: {
    display: 'flex',
    flexDirection: 'column',
    gap: tokens.spacingVerticalS,
    paddingTop: tokens.spacingVerticalM,
    borderTop: `1px solid ${tokens.colorNeutralStroke2}`,
  },
});

const TITLES: Record<string, string> = {
  stage_review: 'Stage review outcome',
  decision: 'Gate decision',
  closure: 'Closure',
};

/** Closure checklist (spec 8.7e): derived live from the readiness check. */
function ClosureChecklist({ readiness }: { readiness: Readiness }) {
  const openItems = readiness.blocking.reduce((n, g) => n + g.items.length, 0);
  const rows: Array<{ label: string; ok: boolean }> = [
    { label: 'UD-002 Hypercare tracker complete (no open hypercare items)', ok: openItems === 0 },
    {
      label: 'UD-003 No open defects (Critical gaps cleared)',
      ok: readiness.critical_gaps.length === 0,
    },
    {
      label: 'UD-004 No open actions and no open conditions',
      ok: readiness.open_conditions.length === 0,
    },
    { label: 'All carried items are done', ok: readiness.carried_items.length === 0 },
  ];
  return (
    <div role="group" aria-label="Closure checklist">
      <Subtitle2 as="h4">Closure checklist</Subtitle2>
      {rows.map((r) => (
        <div key={r.label}>
          <Checkbox checked={r.ok} label={r.label} disabled aria-readonly />
        </div>
      ))}
      <Caption1>No conditions can be added at closure.</Caption1>
    </div>
  );
}

/** Outcome buttons for the selected gate; disabled ones explain why in a tooltip (spec 12, AC-08). */
export function DecisionPanel(props: {
  transitionId: string;
  gate: GateOverview;
  readiness: Readiness;
  isCurrent: boolean;
}) {
  const s = useStyles();
  const { gate, readiness } = props;
  const isReview = gate.type === 'stage_review';
  const perm = usePerm(
    isReview ? 'record_stage_review' : 'record_gate_decision',
    props.transitionId,
  );
  const [outcome, setOutcome] = useState<string | null>(null);
  const notCurrent = props.isCurrent ? null : 'Only the current gate can be decided';
  const suggestions = [
    ...readiness.blocking.flatMap((g) => g.items),
    ...readiness.critical_gaps,
  ].map((i) => ({
    id: i.item_id,
    title: i.title,
  }));
  const unique = suggestions.filter((x, i) => suggestions.findIndex((y) => y.id === x.id) === i);

  return (
    <div className={s.root}>
      <Subtitle2 as="h3">{TITLES[gate.type] ?? 'Outcome'}</Subtitle2>
      {gate.type === 'closure' && <ClosureChecklist readiness={readiness} />}
      <Toolbar>
        {readiness.decision_options.map((o) => (
          <ReasonButton
            key={o.outcome}
            appearance={
              o.outcome.startsWith('Proceed') ||
              o.outcome.startsWith('Approve') ||
              o.outcome === 'Close'
                ? 'primary'
                : 'secondary'
            }
            reasons={[
              notCurrent,
              perm.reason,
              ...(o.enabled ? [] : o.reasons.length ? o.reasons : ['Not allowed yet']),
            ]}
            onClick={() => setOutcome(o.outcome)}
          >
            {o.outcome}
          </ReasonButton>
        ))}
      </Toolbar>
      {outcome && (
        <DecisionDialog
          transitionId={props.transitionId}
          gate={gate.code}
          gateShort={gate.short}
          gateType={gate.type}
          outcome={outcome}
          suggestions={unique}
          onClose={() => setOutcome(null)}
        />
      )}
    </div>
  );
}

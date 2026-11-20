import { useEffect, useState } from 'react';
import {
  Body1,
  Button,
  Caption1,
  ProgressBar,
  Spinner,
  makeStyles,
  tokens,
} from '@fluentui/react-components';
import { CheckmarkCircleFilled, CircleRegular } from '@fluentui/react-icons';
import { AiBadge } from '../../../components/AiBadge';
import { useApiErrorToast } from '../../../hooks/useApiErrorToast';
import { useGenerate, type GenerateResult, type SupportModel } from '../api';

const useStyles = makeStyles({
  stack: { display: 'flex', flexDirection: 'column', gap: tokens.spacingVerticalM },
  row: { display: 'flex', gap: tokens.spacingHorizontalS, alignItems: 'center' },
  done: { color: tokens.colorPaletteGreenForeground1 },
});

const STEP_MS = 1500;

/** Step 2: Generate. The API returns three steps; they play client-side (~1.5 s each) before the
 * result is shown. */
export function GenerateStep(props: {
  transitionId: string;
  model: SupportModel;
  onStart: () => void;
  onDone: () => void;
}) {
  const s = useStyles();
  const showError = useApiErrorToast();
  const gen = useGenerate(props.transitionId);
  const [steps, setSteps] = useState<GenerateResult['steps'] | null>(null);
  const [active, setActive] = useState(0);
  const running = gen.isPending || (steps !== null && active < steps.length);

  useEffect(() => {
    if (!steps) return;
    if (active >= steps.length) {
      props.onDone();
      return;
    }
    const t = window.setTimeout(() => setActive((a) => a + 1), STEP_MS);
    return () => window.clearTimeout(t);
    // onDone is intentionally excluded: it only switches the visible step.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [steps, active]);

  const start = () => {
    props.onStart();
    setSteps(null);
    setActive(0);
    gen.mutate(undefined, { onSuccess: (r) => setSteps(r.steps), onError: showError });
  };

  const blockedReason = props.model.can_edit
    ? null
    : (props.model.edit_denied_reason ?? 'The support model cannot be generated in this status.');

  return (
    <div className={s.stack}>
      <Body1>
        Orion reads the Confluence page, transcript, design and diagrams and drafts the application
        landscape, support tiers, contacts and open questions.
      </Body1>
      <div className={s.row}>
        <Button
          appearance="primary"
          disabled={!!blockedReason || running}
          title={blockedReason ?? undefined}
          onClick={start}
        >
          Generate support model
        </Button>
        <AiBadge />
        <Caption1>Orion agent</Caption1>
      </div>
      {blockedReason && <Caption1>{blockedReason}</Caption1>}

      {(gen.isPending || steps) && (
        <div className={s.stack} aria-live="polite">
          <ProgressBar value={steps ? Math.min(active, steps.length) / steps.length : undefined} />
          {gen.isPending && (
            <div className={s.row}>
              <Spinner size="tiny" />
              <Body1>Starting</Body1>
            </div>
          )}
          {steps?.map((st, i) => (
            <div key={st.label} className={s.row}>
              {i < active ? (
                <CheckmarkCircleFilled className={s.done} />
              ) : i === active ? (
                <Spinner size="tiny" />
              ) : (
                <CircleRegular />
              )}
              <Body1>{st.label}</Body1>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

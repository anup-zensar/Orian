import { useState } from 'react';
import { Field, Input, makeStyles, tokens } from '@fluentui/react-components';
import { ErrorState } from '../../../components/ErrorState';
import { LoadingState } from '../../../components/LoadingState';
import type { ThresholdsAdmin } from '../../../api/types';
import { usePutThresholds, useThresholds } from '../peopleRulesApi';
import { ReasonsBar, SaveBar } from '../peopleRulesUi';
import { useDirty } from '../useDirty';
import { useSuccessToast } from '../useSavedToast';

type Rag = ThresholdsAdmin['thresholds']['rag'];
type Key = keyof Rag;

interface FieldDef {
  key: Key;
  label: string;
  min: number;
  max: number;
  unit: string;
}

const FIELDS: FieldDef[] = [
  { key: 'red_critical_gaps', label: 'Red: critical gaps from', min: 1, max: 100, unit: 'gaps' },
  { key: 'red_lens_below', label: 'Red: any area below', min: 0, max: 100, unit: '% ready' },
  {
    key: 'red_near_days',
    label: 'Red: decision within',
    min: 0,
    max: 365,
    unit: 'days (with a critical gap)',
  },
  {
    key: 'amber_critical_gaps',
    label: 'Amber: critical gaps from',
    min: 1,
    max: 100,
    unit: 'gaps',
  },
  { key: 'amber_lens_below', label: 'Amber: any area below', min: 0, max: 100, unit: '% ready' },
];

const useStyles = makeStyles({
  grid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
    gap: tokens.spacingHorizontalM,
  },
  sentence: {
    margin: 0,
    padding: tokens.spacingVerticalM,
    borderRadius: tokens.borderRadiusMedium,
    backgroundColor: tokens.colorNeutralBackground3,
    display: 'flex',
    flexDirection: 'column',
    gap: tokens.spacingVerticalXS,
  },
  note: { color: tokens.colorNeutralForeground3, margin: 0 },
});

const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`;

/** The rule in plain words, built from the numbers being edited. */
function ragSentences(r: Rag): { red: string; amber: string; green: string } {
  return {
    red:
      `Red: ${plural(r.red_critical_gaps, 'critical gap', 'critical gaps')} or more, or any lens ` +
      `below ${r.red_lens_below}% ready, or ${plural(r.amber_critical_gaps, 'critical gap', 'critical gaps')} ` +
      `or more with a decision within ${plural(r.red_near_days, 'day', 'days')}.`,
    amber:
      `Amber: ${plural(r.amber_critical_gaps, 'critical gap', 'critical gaps')} or more, or any ` +
      `area below ${r.amber_lens_below}% ready.`,
    green: 'Green: anything else.',
  };
}

/** Why a value is not allowed, or undefined. Mirrors the server rules so the reason shows early. */
function problem(r: Rag, f: FieldDef): string | undefined {
  const v = r[f.key];
  if (!Number.isInteger(v) || v < f.min || v > f.max)
    return `Whole number from ${f.min} to ${f.max}`;
  if (f.key === 'amber_critical_gaps' && v > r.red_critical_gaps)
    return 'Amber cannot need more gaps than Red';
  if (f.key === 'amber_lens_below' && v < r.red_lens_below)
    return 'Amber cannot be stricter than Red';
  return undefined;
}

function Editor({ data }: { data: ThresholdsAdmin }) {
  const s = useStyles();
  const saved = data.thresholds.rag;
  const [rag, setRag] = useState<Rag>(saved);
  const dirty = useDirty(rag, 'thresholds');
  const save = usePutThresholds();
  const ok = useSuccessToast();
  const problems = FIELDS.map((f) => problem(rag, f));
  const text = ragSentences(rag);

  return (
    <>
      <p className={s.note}>
        These numbers decide the Red / Amber / Green colour of every transition. They apply to all
        active transitions straight away.
      </p>
      <div className={s.grid}>
        {FIELDS.map((f, i) => (
          <Field key={f.key} label={f.label} hint={f.unit} validationMessage={problems[i]}>
            <Input
              type="number"
              min={f.min}
              max={f.max}
              value={String(rag[f.key])}
              onChange={(_, d) => setRag((cur) => ({ ...cur, [f.key]: Number(d.value) }))}
            />
          </Field>
        ))}
      </div>
      <div className={s.sentence} aria-live="polite">
        <span>{text.red}</span>
        <span>{text.amber}</span>
        <span>{text.green}</span>
      </div>
      <ReasonsBar error={save.error} />
      <SaveBar
        dirty={dirty}
        saving={save.isPending}
        blockedReason={problems.find(Boolean)}
        onSave={() =>
          save.mutate(
            { ...data.thresholds, rag },
            { onSuccess: () => ok('Saved - applies immediately') },
          )
        }
        onDiscard={() => {
          setRag(saved);
          save.reset();
        }}
      />
    </>
  );
}

export function ThresholdsPanel() {
  const q = useThresholds();
  if (q.isLoading) return <LoadingState rows={4} />;
  if (q.isError) return <ErrorState error={q.error} onRetry={() => void q.refetch()} />;
  return q.data ? <Editor key={q.dataUpdatedAt} data={q.data} /> : null;
}

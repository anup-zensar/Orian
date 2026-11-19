import { useState } from 'react';
import {
  Button,
  DialogActions,
  DialogBody,
  DialogContent,
  DialogSurface,
  DialogTitle,
  Field,
  Input,
  makeStyles,
  tokens,
} from '@fluentui/react-components';
import { ReturnFocusDialog } from '../../../components/ReturnFocusDialog';
import { useCreateEvalMetric } from '../peopleRulesApi';
import { ReasonsBar } from '../peopleRulesUi';
import { useSuccessToast } from '../useSavedToast';

const useStyles = makeStyles({
  form: { display: 'flex', flexDirection: 'column', gap: tokens.spacingVerticalM },
});

/** Adds an evaluation metric: a name, how it is measured and the target for every tier. */
export function AddMetricDialog({ tiers, onClose }: { tiers: number[]; onClose: () => void }) {
  const s = useStyles();
  const create = useCreateEvalMetric();
  const ok = useSuccessToast();
  const [metric, setMetric] = useState('');
  const [targets, setTargets] = useState<Record<number, string>>({});
  const valid = metric.trim() !== '' && tiers.every((t) => (targets[t] ?? '').trim() !== '');

  const submit = () =>
    create.mutate(
      {
        metric: metric.trim(),
        evaluation: 'manual',
        targets_by_tier: Object.fromEntries(
          tiers.map((t) => [String(t), (targets[t] ?? '').trim()]),
        ),
      },
      {
        onSuccess: () => {
          ok('Saved - applies to new transitions');
          onClose();
        },
      },
    );

  return (
    <ReturnFocusDialog open onOpenChange={(_, d) => !d.open && onClose()}>
      <DialogSurface>
        <DialogBody>
          <DialogTitle>Add an evaluation metric</DialogTitle>
          <DialogContent className={s.form}>
            <p>Someone enters the result by hand for each transition.</p>
            <Field label="Metric name" required>
              <Input value={metric} onChange={(_, d) => setMetric(d.value)} />
            </Field>
            {tiers.map((t) => (
              <Field key={t} label={`Target for Tier ${t}`} required>
                <Input
                  placeholder="for example 95% or Reviewed"
                  value={targets[t] ?? ''}
                  onChange={(_, d) => setTargets((cur) => ({ ...cur, [t]: d.value }))}
                />
              </Field>
            ))}
            <ReasonsBar error={create.error} />
          </DialogContent>
          <DialogActions>
            <Button onClick={onClose}>Cancel</Button>
            <Button appearance="primary" disabled={!valid || create.isPending} onClick={submit}>
              {create.isPending ? 'Saving...' : 'Add metric'}
            </Button>
          </DialogActions>
        </DialogBody>
      </DialogSurface>
    </ReturnFocusDialog>
  );
}

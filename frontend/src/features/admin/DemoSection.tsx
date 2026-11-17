import { useState, type ReactNode } from 'react';
import {
  Body1,
  Button,
  Caption1,
  Dialog,
  DialogActions,
  DialogBody,
  DialogContent,
  DialogSurface,
  DialogTitle,
  Field,
  Input,
  MessageBar,
  MessageBarBody,
  Tooltip,
  makeStyles,
  tokens,
} from '@fluentui/react-components';
import { Link } from 'react-router';
import { ErrorState } from '../../components/ErrorState';
import { LoadingState } from '../../components/LoadingState';
import { SectionCard } from '../../components/SectionCard';
import { useApiErrorToast } from '../../hooks/useApiErrorToast';
import { useReference } from '../reference/api';
import {
  useDemoReset,
  useDemoToday,
  useFastForward,
  useSetToday,
  type DemoResetOut,
  type FastForwardOut,
} from './api';
import { useSuccessToast } from './useSavedToast';

const FLAGSHIP = 'TR-0001';

const useStyles = makeStyles({
  stack: { display: 'flex', flexDirection: 'column', gap: tokens.spacingVerticalL },
  row: { display: 'flex', gap: tokens.spacingHorizontalM, alignItems: 'end', flexWrap: 'wrap' },
});

function Confirm(props: {
  title: string;
  body: string;
  confirmLabel: string;
  trigger: (open: () => void) => ReactNode;
  busy: boolean;
  onConfirm: (close: () => void) => void;
}) {
  const [open, setOpen] = useState(false);
  return (
    <>
      {props.trigger(() => setOpen(true))}
      <Dialog open={open} onOpenChange={(_, d) => !props.busy && setOpen(d.open)}>
        <DialogSurface>
          <DialogBody>
            <DialogTitle>{props.title}</DialogTitle>
            <DialogContent>{props.body}</DialogContent>
            <DialogActions>
              <Button appearance="secondary" disabled={props.busy} onClick={() => setOpen(false)}>
                Cancel
              </Button>
              <Button
                appearance="primary"
                disabled={props.busy}
                onClick={() => props.onConfirm(() => setOpen(false))}
              >
                {props.busy ? 'Working...' : props.confirmLabel}
              </Button>
            </DialogActions>
          </DialogBody>
        </DialogSurface>
      </Dialog>
    </>
  );
}

export function DemoSection() {
  const s = useStyles();
  const ref = useReference();
  const demo = ref.data?.app.demo_mode === true;
  const today = useDemoToday(demo);
  const reset = useDemoReset();
  const ff = useFastForward();
  const setToday = useSetToday();
  const showError = useApiErrorToast();
  const ok = useSuccessToast();
  const [resetResult, setResetResult] = useState<DemoResetOut | null>(null);
  const [ffResult, setFfResult] = useState<FastForwardOut | null>(null);
  const [date, setDate] = useState('');

  if (ref.isLoading) return <LoadingState rows={3} />;
  if (ref.isError) return <ErrorState error={ref.error} onRetry={() => void ref.refetch()} />;
  if (!demo) return null;

  return (
    <div className={s.stack}>
      <SectionCard title="Reset demo data">
        <Body1>Re-seeds all demo data and clears the "today" override.</Body1>
        <div className={s.row}>
          <Confirm
            title="Reset demo data?"
            body="All changes made during the demo will be lost and the seed data restored."
            confirmLabel="Reset demo data"
            busy={reset.isPending}
            trigger={(open) => <Button onClick={open}>Reset demo data</Button>}
            onConfirm={(close) =>
              reset.mutate(undefined, {
                onSuccess: (r) => {
                  setResetResult(r);
                  setFfResult(null);
                  close();
                  ok('Demo data reset');
                },
                onError: (e) => {
                  close();
                  showError(e);
                },
              })
            }
          />
        </div>
        {resetResult && (
          <MessageBar intent="success">
            <MessageBarBody>
              Reset in {resetResult.seconds.toFixed(1)} s: {resetResult.transitions} transitions,{' '}
              {resetResult.items} items.
            </MessageBarBody>
          </MessageBar>
        )}
      </SectionCard>

      <SectionCard title="Fast-forward flagship">
        <Body1>
          Completes every open item due at or before the current gate of {FLAGSHIP}, except items
          linked to the OCET or support-model workflows and items under an exception, and re-imports
          eval results with all metrics passing.
        </Body1>
        <div className={s.row}>
          <Confirm
            title={`Fast-forward ${FLAGSHIP}?`}
            body="Open items due by the current gate will be marked done and eval results re-imported as passing."
            confirmLabel="Fast-forward"
            busy={ff.isPending}
            trigger={(open) => <Button onClick={open}>Fast-forward flagship</Button>}
            onConfirm={(close) =>
              ff.mutate(FLAGSHIP, {
                onSuccess: (r) => {
                  setFfResult(r);
                  close();
                  ok('Flagship fast-forwarded');
                },
                onError: (e) => {
                  close();
                  showError(e);
                },
              })
            }
          />
        </div>
        {ffResult && (
          <MessageBar intent="success">
            <MessageBarBody>
              {ffResult.items_completed} items completed, {ffResult.skipped_linked} left open (OCET
              / support model), {ffResult.skipped_exception} left open (exception),{' '}
              {ffResult.evals_passing} eval metrics passing.
              {ffResult.readiness ? ` Readiness: ${ffResult.readiness}.` : ''}
              <div>
                <Link to={`/transitions/${encodeURIComponent(ffResult.transition_id)}/gates`}>
                  Open {ffResult.transition_id} gates tab
                </Link>
              </div>
            </MessageBarBody>
          </MessageBar>
        )}
      </SectionCard>

      <SectionCard title="Set today">
        {today.isLoading ? (
          <LoadingState rows={1} />
        ) : today.isError ? (
          <ErrorState error={today.error} onRetry={() => void today.refetch()} />
        ) : today.data ? (
          <Body1>
            Effective today: <strong>{today.data.today}</strong>
            {today.data.override
              ? ` (override set; seed date ${today.data.seed_date ?? 'none'})`
              : ` (no override; seed date ${today.data.seed_date ?? 'none'})`}
          </Body1>
        ) : null}
        <div className={s.row}>
          <Field label="Date">
            <Input type="date" value={date} onChange={(_, d) => setDate(d.value)} />
          </Field>
          <Button
            appearance="primary"
            disabled={!date || setToday.isPending}
            onClick={() =>
              setToday.mutate(date, {
                onSuccess: (r) => {
                  ok(`Today is now ${r.today}`);
                  void today.refetch();
                },
                onError: showError,
              })
            }
          >
            Set today
          </Button>
          <Button
            disabled={setToday.isPending || !today.data?.override}
            onClick={() =>
              setToday.mutate(null, {
                onSuccess: (r) => {
                  setDate('');
                  ok(`Override cleared; today is ${r.today}`);
                  void today.refetch();
                },
                onError: showError,
              })
            }
          >
            Clear override
          </Button>
        </div>
      </SectionCard>

      <SectionCard title="Run reminder engine">
        <div className={s.row}>
          <Tooltip content="Reminder engine arrives in M8" relationship="description">
            <Button disabledFocusable>Run reminder engine</Button>
          </Tooltip>
          <Caption1>Not available yet: the reminder engine arrives with a later release.</Caption1>
        </div>
      </SectionCard>
    </div>
  );
}

import { useState } from 'react';
import {
  Caption1,
  MessageBar,
  MessageBarBody,
  Tooltip,
  makeStyles,
  tokens,
} from '@fluentui/react-components';
import dayjs from 'dayjs';
import { AppLink } from '../../components/AppLink';
import { useApiErrorToast } from '../../hooks/useApiErrorToast';
import { ReasonButton } from '../gates/ReasonButton';
import { useSuccessToast } from '../gates/useSuccessToast';
import { usePerm } from '../gates/usePerm';
import { useReminderStatus, useRunReminders, type ReminderRunOut } from './api';

const useStyles = makeStyles({
  line: {
    display: 'flex',
    flexWrap: 'wrap',
    alignItems: 'center',
    columnGap: tokens.spacingHorizontalM,
    rowGap: tokens.spacingVerticalXS,
    minWidth: 0,
  },
  text: { minWidth: 0, overflowWrap: 'anywhere' },
});

const DEFAULT_RULES = ['R1', 'R2', 'R3', 'R4', 'R5', 'R6', 'R7'];

/** One line: when the engine ran and what it drafted, with the per-rule counts as a tooltip. */
export function RunSummary({ run, label }: { run: ReminderRunOut; label: string }) {
  const s = useStyles();
  const ids = Array.from(new Set([...DEFAULT_RULES, ...Object.keys(run.created)])).sort();
  const total = Object.values(run.created).reduce((a, b) => a + b, 0);
  const perRule = ids.map((id) => `${id}: ${run.created[id] ?? 0}`).join(', ');
  return (
    <Tooltip
      content={`Messages created per rule - ${perRule}. Skipped as duplicates: ${run.skipped_duplicates}. Sent autonomously: ${run.sent_autonomously}.`}
      relationship="description"
    >
      <Caption1 className={s.text} tabIndex={0} aria-label="Messages created per rule">
        {label} {dayjs(run.at).format('D MMM YYYY HH:mm')}: {total} drafted, {run.sent_autonomously}{' '}
        sent autonomously, {run.skipped_duplicates} skipped as duplicates.
      </Caption1>
    </Tooltip>
  );
}

/** Button (disabled with the reason when run_reminders is missing) plus last run and result. */
export function RunRemindersControl({ buttonLabel = 'Run reminder engine now' }) {
  const s = useStyles();
  const perm = usePerm('run_reminders');
  const status = useReminderStatus();
  const run = useRunReminders();
  const showError = useApiErrorToast();
  const showSuccess = useSuccessToast();
  const [result, setResult] = useState<ReminderRunOut | null>(null);
  const last = status.data?.last_run ?? null;

  return (
    <div className={s.line}>
      <ReasonButton
        appearance="primary"
        reasons={[perm.reason]}
        onClick={() =>
          run.mutate(undefined, {
            onSuccess: (r) => {
              setResult(r);
              showSuccess(
                `Reminder engine ran: ${r.drafts.length} drafted, ${r.sent_autonomously} sent`,
                r.drafts.length > 0 ? <AppLink to="/drafts">Open drafts</AppLink> : undefined,
              );
            },
            onError: showError,
          })
        }
      >
        {run.isPending ? 'Running...' : buttonLabel}
      </ReasonButton>
      {result && <RunSummary run={result} label="This run" />}
      {!result && last && <RunSummary run={last} label="Last run" />}
      {!result && !last && !status.isLoading && (
        <Caption1>The reminder engine has not run yet.</Caption1>
      )}
      {status.isError && (
        <MessageBar intent="warning" layout="multiline">
          <MessageBarBody>Reminder status is not available right now.</MessageBarBody>
        </MessageBar>
      )}
    </div>
  );
}

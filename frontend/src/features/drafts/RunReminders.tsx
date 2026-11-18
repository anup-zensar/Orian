import { useState } from 'react';
import {
  Body1,
  Caption1,
  MessageBar,
  MessageBarBody,
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
  stack: { display: 'flex', flexDirection: 'column', gap: tokens.spacingVerticalS },
  counts: { display: 'flex', gap: tokens.spacingHorizontalS, flexWrap: 'wrap' },
  chip: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    minWidth: '56px',
    padding: `${tokens.spacingVerticalXS} ${tokens.spacingHorizontalS}`,
    border: `1px solid ${tokens.colorNeutralStroke2}`,
    borderRadius: tokens.borderRadiusMedium,
  },
  num: { fontWeight: tokens.fontWeightSemibold, fontSize: tokens.fontSizeBase400 },
});

const DEFAULT_RULES = ['R1', 'R2', 'R3', 'R4', 'R5', 'R6', 'R7'];

/** Counts per rule R1-R7, skipped duplicates and autonomous sends of one engine run. */
export function RunSummary({ run, label }: { run: ReminderRunOut; label: string }) {
  const s = useStyles();
  const ids = Array.from(new Set([...DEFAULT_RULES, ...Object.keys(run.created)])).sort();
  const total = Object.values(run.created).reduce((a, b) => a + b, 0);
  return (
    <div className={s.stack}>
      <Caption1>
        {label} {dayjs(run.at).format('D MMM YYYY HH:mm')}: {total} drafted, {run.sent_autonomously}{' '}
        sent autonomously, {run.skipped_duplicates} skipped as duplicates.
      </Caption1>
      <div className={s.counts} aria-label="Messages created per rule">
        {ids.map((id) => (
          <div key={id} className={s.chip}>
            <span className={s.num}>{run.created[id] ?? 0}</span>
            <Caption1>{id}</Caption1>
          </div>
        ))}
        <div className={s.chip}>
          <span className={s.num}>{run.skipped_duplicates}</span>
          <Caption1>Skipped</Caption1>
        </div>
        <div className={s.chip}>
          <span className={s.num}>{run.sent_autonomously}</span>
          <Caption1>Sent auto</Caption1>
        </div>
      </div>
    </div>
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
    <div className={s.stack}>
      <div>
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
      </div>
      {result && <RunSummary run={result} label="This run" />}
      {!result && last && <RunSummary run={last} label="Last run" />}
      {!result && !last && !status.isLoading && <Body1>The reminder engine has not run yet.</Body1>}
      {status.isError && (
        <MessageBar intent="warning" layout="multiline">
          <MessageBarBody>Reminder status is not available right now.</MessageBarBody>
        </MessageBar>
      )}
    </div>
  );
}

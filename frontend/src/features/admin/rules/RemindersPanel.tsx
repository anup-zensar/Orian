import { useState } from 'react';
import {
  Badge,
  Field,
  Input,
  Switch,
  Table,
  TableBody,
  TableCell,
  TableHeader,
  TableHeaderCell,
  TableRow,
  Tooltip,
  makeStyles,
  tokens,
} from '@fluentui/react-components';
import { EmptyState } from '../../../components/EmptyState';
import { DataTable } from '../../../components/DataTable';
import { ErrorState } from '../../../components/ErrorState';
import { LoadingState } from '../../../components/LoadingState';
import { useApiErrorToast } from '../../../hooks/useApiErrorToast';
import { usePutReminderRules, useReminderRules, type ReminderRule } from '../api';
import { SaveBar } from '../peopleRulesUi';
import { useDirty } from '../useDirty';
import { useSuccessToast } from '../useSavedToast';

interface Draft {
  enabled: boolean;
  params: Record<string, string>;
}

const useStyles = makeStyles({
  params: { display: 'flex', gap: tokens.spacingHorizontalM, flexWrap: 'wrap' },
  muted: { color: tokens.colorNeutralForeground3 },
});

const draftOf = (rules: ReminderRule[]): Record<string, Draft> =>
  Object.fromEntries(
    rules.map((r) => [
      r.id,
      {
        enabled: r.enabled,
        params: Object.fromEntries(Object.entries(r.params).map(([k, v]) => [k, String(v)])),
      },
    ]),
  );

function Editor({ rules }: { rules: ReminderRule[] }) {
  const s = useStyles();
  const [draft, setDraft] = useState<Record<string, Draft>>(() => draftOf(rules));
  const dirty = useDirty(draft, 'reminders');
  const save = usePutReminderRules();
  const showError = useApiErrorToast();
  const ok = useSuccessToast();

  const invalid = Object.values(draft).some((d) =>
    Object.values(d.params).some((v) => !/^[1-9]\d*$/.test(v.trim())),
  );

  const submit = () =>
    save.mutate(
      {
        rules: rules.map((r) => ({
          id: r.id,
          enabled: draft[r.id].enabled,
          params: Object.fromEntries(
            Object.entries(draft[r.id].params).map(([k, v]) => [k, Number(v)]),
          ),
        })),
      },
      { onSuccess: () => ok('Saved - applies immediately'), onError: showError },
    );

  return (
    <>
      {rules.length === 0 ? (
        <EmptyState message="No reminder rules configured." />
      ) : (
        <DataTable label="Reminder rules table" stickyFirstColumn>
          <Table aria-label="Reminder rules" size="small" style={{ tableLayout: 'auto' }}>
            <TableHeader>
              <TableRow>
                <TableHeaderCell>Rule</TableHeaderCell>
                <TableHeaderCell style={{ minWidth: 260 }}>Description</TableHeaderCell>
                <TableHeaderCell>Enabled</TableHeaderCell>
                <TableHeaderCell style={{ minWidth: 220 }}>Thresholds</TableHeaderCell>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rules.map((r) => {
                const d = draft[r.id];
                return (
                  <TableRow key={r.id}>
                    <TableCell>
                      {r.name}
                      {r.autonomous_eligible && (
                        <Tooltip
                          relationship="description"
                          content="This reminder may be sent without a person reviewing it first, if you allow that."
                        >
                          <Badge appearance="tint" style={{ marginLeft: 6, whiteSpace: 'nowrap' }}>
                            Can be sent without review
                          </Badge>
                        </Tooltip>
                      )}
                    </TableCell>
                    <TableCell className={s.muted} style={{ minWidth: 260 }}>
                      {r.description}
                    </TableCell>
                    <TableCell>
                      <Switch
                        aria-label={`${r.id} enabled`}
                        checked={d.enabled}
                        onChange={(_, x) =>
                          setDraft((cur) => ({
                            ...cur,
                            [r.id]: { ...cur[r.id], enabled: x.checked },
                          }))
                        }
                      />
                    </TableCell>
                    <TableCell style={{ minWidth: 220 }}>
                      <div className={s.params}>
                        {Object.keys(d.params).length === 0 && (
                          <span className={s.muted}>None</span>
                        )}
                        {Object.entries(d.params).map(([k, v]) => (
                          <Field
                            key={k}
                            label={k.replace(/_/g, ' ')}
                            validationMessage={
                              /^[1-9]\d*$/.test(v.trim()) ? undefined : 'Positive whole number'
                            }
                          >
                            <Input
                              type="number"
                              min={1}
                              value={v}
                              onChange={(_, x) =>
                                setDraft((cur) => ({
                                  ...cur,
                                  [r.id]: {
                                    ...cur[r.id],
                                    params: { ...cur[r.id].params, [k]: x.value },
                                  },
                                }))
                              }
                            />
                          </Field>
                        ))}
                      </div>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </DataTable>
      )}
      <SaveBar
        dirty={dirty}
        saving={save.isPending}
        blockedReason={invalid ? 'Every number must be a positive whole number' : undefined}
        onSave={submit}
        onDiscard={() => setDraft(draftOf(rules))}
      />
    </>
  );
}

export function RemindersPanel() {
  const q = useReminderRules();
  if (q.isLoading) return <LoadingState rows={5} />;
  if (q.isError) return <ErrorState error={q.error} onRetry={() => void q.refetch()} />;
  return q.data ? <Editor key={q.dataUpdatedAt} rules={q.data} /> : null;
}

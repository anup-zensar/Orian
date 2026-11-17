import { useState } from 'react';
import {
  Badge,
  Button,
  Field,
  Input,
  Switch,
  Table,
  TableBody,
  TableCell,
  TableHeader,
  TableHeaderCell,
  TableRow,
  makeStyles,
  tokens,
} from '@fluentui/react-components';
import { EmptyState } from '../../components/EmptyState';
import { ErrorState } from '../../components/ErrorState';
import { LoadingState } from '../../components/LoadingState';
import { SectionCard } from '../../components/SectionCard';
import { useApiErrorToast } from '../../hooks/useApiErrorToast';
import { usePutReminderRules, useReminderRules, type ReminderRule } from './api';
import { useSuccessToast } from './useSavedToast';

interface Draft {
  enabled: boolean;
  params: Record<string, string>;
}

const useStyles = makeStyles({
  scroll: { overflowX: 'auto' },
  params: { display: 'flex', gap: tokens.spacingHorizontalM, flexWrap: 'wrap' },
  muted: { color: tokens.colorNeutralForeground3 },
});

function Editor({ rules }: { rules: ReminderRule[] }) {
  const s = useStyles();
  const [draft, setDraft] = useState<Record<string, Draft>>(() =>
    Object.fromEntries(
      rules.map((r) => [
        r.id,
        {
          enabled: r.enabled,
          params: Object.fromEntries(Object.entries(r.params).map(([k, v]) => [k, String(v)])),
        },
      ]),
    ),
  );
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
      { onSuccess: () => ok('Reminder rules saved'), onError: showError },
    );

  return (
    <SectionCard
      title="Reminder rules"
      actions={
        <Button appearance="primary" onClick={submit} disabled={save.isPending || invalid}>
          {save.isPending ? 'Saving...' : 'Save reminder rules'}
        </Button>
      }
    >
      {rules.length === 0 ? (
        <EmptyState message="No reminder rules configured." />
      ) : (
        <div className={s.scroll}>
          <Table
            aria-label="Reminder rules"
            size="small"
            style={{ tableLayout: 'auto', minWidth: '100%' }}
          >
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
                      <strong>{r.id}</strong> {r.name}
                      {r.autonomous_eligible && (
                        <Badge appearance="tint" style={{ marginLeft: 6 }}>
                          autonomous eligible
                        </Badge>
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
        </div>
      )}
    </SectionCard>
  );
}

export function RemindersSection() {
  const q = useReminderRules();
  if (q.isLoading) return <LoadingState rows={5} />;
  if (q.isError) return <ErrorState error={q.error} onRetry={() => void q.refetch()} />;
  return q.data ? <Editor key={q.dataUpdatedAt} rules={q.data} /> : null;
}

import { useState } from 'react';
import {
  Badge,
  Checkbox,
  MessageBar,
  MessageBarBody,
  Table,
  TableBody,
  TableCell,
  TableHeader,
  TableHeaderCell,
  TableRow,
  Tooltip,
} from '@fluentui/react-components';
import { EmptyState } from '../../../components/EmptyState';
import { ErrorState } from '../../../components/ErrorState';
import { LoadingState } from '../../../components/LoadingState';
import { PageHeader } from '../../../components/PageHeader';
import { SectionCard } from '../../../components/SectionCard';
import { useApiErrorToast } from '../../../hooks/useApiErrorToast';
import { useConfirmNoDefects, useHypercare, usePatchDefect, type Defect } from '../../records/api';
import { GuardedButton } from '../../records/common';
import { useRecordStyles, usePerm } from '../../records/hooks';
import { DefectDialog } from '../../records/DefectDialog';
import type { TabProps } from '../types';

/** Hypercare tab (spec 8.7 h): defect tracker plus the "No defects – tracker in place" confirmation. */
export function HypercareTab({ transitionId }: TabProps) {
  const s = useRecordStyles();
  const showError = useApiErrorToast();
  const data = useHypercare(transitionId);
  const manage = usePerm('manage_defects');
  const patch = usePatchDefect(transitionId);
  const confirmNone = useConfirmNoDefects(transitionId);
  const [dialog, setDialog] = useState<{ defect?: Defect } | null>(null);

  const hasDefects = (data.data?.defects.length ?? 0) > 0;
  const checkbox = (
    <Checkbox
      label="No defects – tracker in place"
      checked={data.data?.no_defects_confirmed ?? false}
      disabled={!!manage.reason || hasDefects || confirmNone.isPending}
      onChange={(_, d) => confirmNone.mutate(!!d.checked, { onError: showError })}
    />
  );
  const checkboxReason =
    manage.reason || (hasDefects ? 'Defects are logged, so this cannot be confirmed' : '');

  return (
    <div className={s.stack}>
      <PageHeader
        title="Hypercare"
        subtitle="Defects found after go-live. Open P1/P2 defects hold up closure."
        actions={
          <GuardedButton appearance="primary" reason={manage.reason} onClick={() => setDialog({})}>
            Log defect
          </GuardedButton>
        }
      />
      {data.isPending ? (
        <LoadingState rows={4} />
      ) : data.isError ? (
        <ErrorState error={data.error} />
      ) : (
        <>
          {data.data.open_p1_p2 > 0 && (
            <MessageBar intent="warning">
              <MessageBarBody>
                {data.data.open_p1_p2} open P1/P2 defect{data.data.open_p1_p2 === 1 ? '' : 's'}.
              </MessageBarBody>
            </MessageBar>
          )}
          <SectionCard
            title="Defect tracker"
            actions={
              checkboxReason ? (
                <Tooltip content={checkboxReason} relationship="description">
                  <span>{checkbox}</span>
                </Tooltip>
              ) : (
                checkbox
              )
            }
          >
            {data.data.defects.length === 0 ? (
              <EmptyState
                message={
                  data.data.no_defects_confirmed
                    ? 'No defects – tracker in place (confirmed).'
                    : 'No defects logged yet.'
                }
              />
            ) : (
              <div className={s.tableWrap}>
                <Table aria-label="Defects" size="small">
                  <TableHeader>
                    <TableRow>
                      {['ID', 'Title', 'Priority', 'Status', 'Owner', ''].map((h) => (
                        <TableHeaderCell key={h || 'actions'}>{h}</TableHeaderCell>
                      ))}
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {data.data.defects.map((d) => (
                      <TableRow key={d.id}>
                        <TableCell>{d.id}</TableCell>
                        <TableCell>{d.title}</TableCell>
                        <TableCell>
                          <Badge
                            appearance="tint"
                            color={
                              d.priority === 'P1' || d.priority === 'P2' ? 'danger' : 'informative'
                            }
                          >
                            {d.priority}
                          </Badge>
                        </TableCell>
                        <TableCell>{d.status}</TableCell>
                        <TableCell>{d.owner?.name ?? '–'}</TableCell>
                        <TableCell>
                          <div className={s.row}>
                            <GuardedButton
                              size="small"
                              reason={manage.reason}
                              onClick={() => setDialog({ defect: d })}
                            >
                              Edit
                            </GuardedButton>
                            {d.status === 'Open' && (
                              <GuardedButton
                                size="small"
                                reason={manage.reason}
                                onClick={() =>
                                  patch.mutate(
                                    { id: d.id, patch: { status: 'Resolved' } },
                                    { onError: showError },
                                  )
                                }
                              >
                                Resolve
                              </GuardedButton>
                            )}
                          </div>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            )}
          </SectionCard>
        </>
      )}
      {dialog && (
        <DefectDialog
          transitionId={transitionId}
          defect={dialog.defect}
          onClose={() => setDialog(null)}
        />
      )}
    </div>
  );
}

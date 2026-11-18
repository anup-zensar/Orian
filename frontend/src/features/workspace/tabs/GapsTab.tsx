import { useState } from 'react';
import { useNavigate } from 'react-router';
import dayjs from 'dayjs';
import {
  Badge,
  Body1,
  Caption1,
  Table,
  TableBody,
  TableCell,
  TableHeader,
  TableHeaderCell,
  TableRow,
  Subtitle2,
  mergeClasses,
} from '@fluentui/react-components';
import { AiBadge } from '../../../components/AiBadge';
import { EmptyState } from '../../../components/EmptyState';
import { ErrorState } from '../../../components/ErrorState';
import { LensChip } from '../../../components/LensChip';
import { LoadingState } from '../../../components/LoadingState';
import { PageHeader } from '../../../components/PageHeader';
import { SectionCard } from '../../../components/SectionCard';
import { useApiErrorToast } from '../../../hooks/useApiErrorToast';
import { daysLabel, formatDate } from '../../../lib/format';
import { useReference } from '../../reference/api';
import { useTransition } from '../../transition/api';
import { ActionDialog, type ActionPrefill } from '../../records/ActionDialog';
import {
  useActions,
  useChaserDraft,
  useItems,
  usePatchAction,
  useReadiness,
  type ActionRow,
  type Item,
} from '../../records/api';
import { GuardedButton } from '../../records/common';
import { useRecordStyles, usePerm, useOwnerException, useUrlParams } from '../../records/hooks';
import type { TabProps } from '../types';

const DEFAULT_GAP_STATUSES = ['Gap', 'Non-compliant'];

/** Gaps & actions tab (FR-032, spec 8.7 c): gaps with Orion recommendations, and the action table. */
export function GapsTab({ transitionId }: TabProps) {
  const s = useRecordStyles();
  const navigate = useNavigate();
  const { params, set } = useUrlParams();
  const showError = useApiErrorToast();
  const manage = usePerm('manage_actions', transitionId);
  const rowReason = useOwnerException('manage_actions', manage.reason);
  const ref = useReference();
  const transition = useTransition(transitionId);
  const items = useItems(transitionId);
  const allItems = useItems(transitionId, { all_gates: 'true' });
  const readiness = useReadiness(transitionId);
  const actions = useActions(transitionId);
  const chaser = useChaserDraft(transitionId);
  const patchAction = usePatchAction(transitionId);
  const [prefill, setPrefill] = useState<ActionPrefill | undefined>();

  const gapStatuses = ref.data?.gap_statuses ?? DEFAULT_GAP_STATUSES;
  const gaps = (items.data?.items ?? []).filter((i) => gapStatuses.includes(i.status));
  const daysToDecision = transition.data?.days_to_next_decision;
  const nextDecision = transition.data?.next_decision_date;

  const newOpen = params.get('new') === '1';
  const editId = params.get('action');
  const editing = editId ? actions.data?.find((a) => a.id === editId) : undefined;

  const openCreate = (p?: ActionPrefill) => {
    setPrefill(p);
    set({ new: '1', item: p?.itemId }, false);
  };
  const closeDialog = () => {
    setPrefill(undefined);
    set({ new: undefined, action: undefined, item: undefined });
  };

  const recommendationFor = (item: Item) =>
    (readiness.data?.recommended_actions ?? []).filter((r) => r.item_ids?.includes(item.item_id));

  const closeAction = (a: ActionRow) =>
    patchAction.mutate({ id: a.id, patch: { status: 'Done' } }, { onError: showError });

  const draftChaser = (itemId: string) =>
    chaser.mutate([itemId], {
      onSuccess: (d) => navigate(`/drafts?draft=${d.id}`),
      onError: showError,
    });

  return (
    <div className={s.stack}>
      <PageHeader
        as="h2"
        title="Gaps & actions"
        subtitle="Open gaps up to the current gate, with Orion's suggested next steps, and the action list."
        actions={
          <GuardedButton appearance="primary" reason={manage.reason} onClick={() => openCreate()}>
            Create action
          </GuardedButton>
        }
      />

      <SectionCard title="Gaps">
        {items.isPending ? (
          <LoadingState rows={3} />
        ) : items.isError ? (
          <ErrorState error={items.error} />
        ) : gaps.length === 0 ? (
          <EmptyState message="No gaps up to the current gate. Nice work." />
        ) : (
          <div className={s.stack}>
            {gaps.map((item) => {
              const recs = recommendationFor(item);
              const rec = recs.find((r) => r.kind === 'create_action') ?? recs[0];
              const proposedDue =
                nextDecision && dayjs(nextDecision).isAfter(dayjs())
                  ? nextDecision
                  : dayjs().add(7, 'day').format('YYYY-MM-DD');
              return (
                <div key={item.item_id} className={s.card} id={`gap-${item.item_id}`}>
                  <div className={s.row}>
                    <Subtitle2>
                      {item.item_id} – {item.title}
                    </Subtitle2>
                    <Badge
                      appearance="tint"
                      color={item.gap_severity === 'Critical' ? 'danger' : 'warning'}
                    >
                      {item.gap_severity ?? 'Unrated'} · {item.status}
                    </Badge>
                    <LensChip lens={item.lens} />
                  </div>
                  <Caption1>
                    Owner: {item.owner?.name ?? 'Unassigned'} · Decision {daysLabel(daysToDecision)}
                  </Caption1>
                  <div className={mergeClasses(s.card, s.cardAi)}>
                    <div className={s.row}>
                      <AiBadge />
                      <Body1>
                        <strong>Orion recommendation</strong>
                      </Body1>
                    </div>
                    {readiness.isPending ? (
                      <LoadingState rows={1} />
                    ) : rec ? (
                      <>
                        <Body1>Proposed action: {rec.label}</Body1>
                        <Caption1>
                          Proposed owner: {item.owner?.name ?? 'Unassigned'} · Proposed due:{' '}
                          {formatDate(proposedDue)}
                        </Caption1>
                      </>
                    ) : (
                      <Body1>No specific recommendation; follow up with the owner.</Body1>
                    )}
                    <div className={s.row}>
                      <GuardedButton
                        size="small"
                        reason={manage.reason}
                        onClick={() =>
                          openCreate({
                            title: rec?.label ?? `Close gap on ${item.item_id}`,
                            itemId: item.item_id,
                            ownerId: item.owner?.id,
                            dueDate: proposedDue,
                          })
                        }
                      >
                        Create action
                      </GuardedButton>
                      <GuardedButton
                        size="small"
                        reason={manage.reason}
                        disabled={chaser.isPending}
                        onClick={() => draftChaser(item.item_id)}
                      >
                        Draft chaser
                      </GuardedButton>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </SectionCard>

      <SectionCard title="Actions">
        {actions.isPending ? (
          <LoadingState rows={3} />
        ) : actions.isError ? (
          <ErrorState error={actions.error} />
        ) : actions.data.length === 0 ? (
          <EmptyState
            message="No actions yet."
            action={
              <GuardedButton reason={manage.reason} onClick={() => openCreate()}>
                Create action
              </GuardedButton>
            }
          />
        ) : (
          <div className={s.tableWrap}>
            <Table aria-label="Actions" size="small">
              <TableHeader>
                <TableRow>
                  {[
                    'ID',
                    'Title',
                    'Linked items',
                    'Owner',
                    'Due',
                    'Status',
                    'Priority',
                    'Origin',
                    '',
                  ].map((h) => (
                    <TableHeaderCell key={h || 'actions'}>{h}</TableHeaderCell>
                  ))}
                </TableRow>
              </TableHeader>
              <TableBody>
                {actions.data.map((a) => (
                  <TableRow key={a.id}>
                    <TableCell>{a.id}</TableCell>
                    <TableCell>{a.title}</TableCell>
                    <TableCell>{a.item_ids.join(', ') || '–'}</TableCell>
                    <TableCell>{a.owner?.name ?? '–'}</TableCell>
                    <TableCell>
                      {formatDate(a.due_date)}
                      {a.overdue && (
                        <Badge appearance="tint" color="danger" style={{ marginLeft: 6 }}>
                          Overdue
                        </Badge>
                      )}
                    </TableCell>
                    <TableCell>{a.status}</TableCell>
                    <TableCell>{a.priority}</TableCell>
                    <TableCell>{a.origin}</TableCell>
                    <TableCell>
                      <div className={s.row}>
                        <GuardedButton
                          size="small"
                          reason={rowReason(a.owner?.id)}
                          onClick={() => set({ action: a.id }, false)}
                        >
                          Edit
                        </GuardedButton>
                        {a.status !== 'Done' && a.status !== 'Cancelled' && (
                          <GuardedButton
                            size="small"
                            reason={rowReason(a.owner?.id)}
                            onClick={() => closeAction(a)}
                          >
                            Close
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

      {newOpen && (
        <ActionDialog
          transitionId={transitionId}
          items={allItems.data?.items}
          prefill={{
            ...(prefill ?? {}),
            itemId: prefill?.itemId ?? params.get('item') ?? undefined,
          }}
          onClose={closeDialog}
        />
      )}
      {!newOpen && editing && (
        <ActionDialog
          transitionId={transitionId}
          items={allItems.data?.items}
          action={editing}
          onClose={closeDialog}
        />
      )}
    </div>
  );
}

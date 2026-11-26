import { useState } from 'react';
import {
  Badge,
  Table,
  TableBody,
  TableCell,
  TableHeader,
  TableHeaderCell,
  TableRow,
} from '@fluentui/react-components';
import { AppLink } from '../../../components/AppLink';
import { DataTable } from '../../../components/DataTable';
import { EmptyState } from '../../../components/EmptyState';
import { ErrorState } from '../../../components/ErrorState';
import { LoadingState } from '../../../components/LoadingState';
import { PageHeader } from '../../../components/PageHeader';
import { SectionCard } from '../../../components/SectionCard';
import { useTransition } from '../../transition/api';
import {
  useConditions,
  useExceptions,
  useItems,
  useRisks,
  type ConditionRow,
} from '../../records/api';
import {
  CloseConditionDialog,
  CreateConditionDialog,
  CreateRiskDialog,
  RequestExceptionDialog,
} from '../../records/ConditionDialogs';
import { GuardedButton } from '../../records/common';
import { useRecordStyles, usePerm, useUrlParams } from '../../records/hooks';
import { useOptionLabel } from '../../reference/options';
import type { TabProps } from '../types';

function Head({
  cols,
  widths,
  stickyEnd,
}: {
  cols: string[];
  widths?: Array<number | undefined>;
  /** Class of the sticky last (action) column, when the table has one. */
  stickyEnd?: string;
}) {
  return (
    <TableHeader>
      <TableRow>
        {cols.map((c, i) => (
          <TableHeaderCell
            key={c || 'actions'}
            className={stickyEnd && i === cols.length - 1 ? stickyEnd : undefined}
            style={widths?.[i] ? { width: widths[i] } : undefined}
          >
            {c}
          </TableHeaderCell>
        ))}
      </TableRow>
    </TableHeader>
  );
}

/** Conditions, exceptions & risks tab (FR-035, spec 8.7 g). */
export function ConditionsTab({ transitionId }: TabProps) {
  const optionLabel = useOptionLabel();
  const s = useRecordStyles();
  const { params, set } = useUrlParams();
  const transition = useTransition(transitionId);
  const conditions = useConditions(transitionId);
  const exceptions = useExceptions(transitionId);
  const risks = useRisks(transitionId);
  const items = useItems(transitionId, { all_gates: 'true' });
  const manageCond = usePerm('manage_conditions', transitionId);
  const reqExc = usePerm('request_exception', transitionId);
  const manageRisk = usePerm('manage_risks', transitionId);
  const [closing, setClosing] = useState<ConditionRow | null>(null);
  const [riskOpen, setRiskOpen] = useState(false);

  const condOpen = params.get('new') === '1';
  const excOpen = params.get('exception') === '1';
  const item = params.get('item') ?? undefined;
  const closeUrlDialog = () => set({ new: undefined, exception: undefined, item: undefined });

  return (
    <div className={s.stack}>
      <PageHeader
        as="h2"
        title="Conditions, exceptions & risks"
        subtitle="Conditions carried across gates, approved exceptions and the risk register."
      />

      <SectionCard
        title="Conditions"
        actions={
          <GuardedButton
            appearance="primary"
            reason={manageCond.reason}
            onClick={() => set({ new: '1' }, false)}
          >
            Create condition
          </GuardedButton>
        }
      >
        {conditions.isPending ? (
          <LoadingState rows={3} />
        ) : conditions.isError ? (
          <ErrorState error={conditions.error} />
        ) : conditions.data.length === 0 ? (
          <EmptyState message="No conditions set." />
        ) : (
          <DataTable label="Conditions table">
            <Table aria-label="Conditions" size="small" style={{ minWidth: 620 }}>
              <Head
                cols={['ID / item', 'Set at - due', 'Owner', 'Status', 'Condition', '']}
                widths={[80, 110, 100, 70, undefined, 80]}
                stickyEnd={s.stickyEnd}
              />
              <TableBody>
                {conditions.data.map((c) => (
                  <TableRow key={c.id}>
                    <TableCell>
                      <div>{c.id}</div>
                      <div className={s.muted}>{c.item_id ?? '–'}</div>
                    </TableCell>
                    <TableCell>
                      {c.set_at_gate_short} → {c.due_gate_short}
                    </TableCell>
                    <TableCell>{c.owner?.name ?? '–'}</TableCell>
                    <TableCell>
                      <Badge appearance="tint" color={c.status === 'Open' ? 'warning' : 'success'}>
                        {optionLabel('condition_statuses', c.status)}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      {c.text}
                      {c.close_note && <div className={s.muted}>Closed: {c.close_note}</div>}
                    </TableCell>
                    <TableCell className={s.stickyEnd}>
                      {c.status === 'Open' && (
                        <GuardedButton
                          size="small"
                          reason={manageCond.reason}
                          onClick={() => setClosing(c)}
                        >
                          Close
                        </GuardedButton>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </DataTable>
        )}
      </SectionCard>

      <SectionCard
        title="Exceptions"
        actions={
          <GuardedButton reason={reqExc.reason} onClick={() => set({ exception: '1' }, false)}>
            Request exception
          </GuardedButton>
        }
      >
        {exceptions.isPending ? (
          <LoadingState rows={2} />
        ) : exceptions.isError ? (
          <ErrorState error={exceptions.error} />
        ) : exceptions.data.length === 0 ? (
          <EmptyState message="No exceptions requested." />
        ) : (
          <DataTable label="Exceptions table">
            <Table aria-label="Exceptions" size="small" style={{ minWidth: 640 }}>
              <Head
                cols={['Ref', 'Control item', 'Rationale', 'Status', 'Approval']}
                widths={[70, 220, 260, 120, 140]}
              />
              <TableBody>
                {exceptions.data.map((e) => (
                  <TableRow key={e.ref}>
                    <TableCell>{e.ref}</TableCell>
                    <TableCell>
                      {e.item_id ? `${e.item_id} – ${e.item_title ?? ''}` : '–'}
                    </TableCell>
                    <TableCell>{e.text}</TableCell>
                    <TableCell>{optionLabel('exception_statuses', e.status)}</TableCell>
                    <TableCell>
                      {e.approval_request_id ? (
                        <AppLink
                          to={`/approvals?request=${encodeURIComponent(e.approval_request_id)}`}
                        >
                          View approval chain
                        </AppLink>
                      ) : (
                        '–'
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </DataTable>
        )}
      </SectionCard>

      <SectionCard
        title="Risk register"
        actions={
          <GuardedButton reason={manageRisk.reason} onClick={() => setRiskOpen(true)}>
            Add risk
          </GuardedButton>
        }
      >
        {risks.isPending ? (
          <LoadingState rows={2} />
        ) : risks.isError ? (
          <ErrorState error={risks.error} />
        ) : risks.data.length === 0 ? (
          <EmptyState message="No risks recorded." />
        ) : (
          <DataTable label="Risk register table">
            <Table aria-label="Risk register" size="small" style={{ minWidth: 640 }}>
              <Head
                cols={['ID', 'Title', 'Rating', 'Decision', 'Linked items']}
                widths={[70, 300, 90, 170, 140]}
              />
              <TableBody>
                {risks.data.map((r) => (
                  <TableRow key={r.id}>
                    <TableCell>{r.id}</TableCell>
                    <TableCell>{r.title}</TableCell>
                    <TableCell>{optionLabel('risk_ratings', r.rating)}</TableCell>
                    <TableCell>{r.decision || '–'}</TableCell>
                    <TableCell>{r.item_ids.join(', ') || '–'}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </DataTable>
        )}
      </SectionCard>

      {condOpen && (
        <CreateConditionDialog
          transitionId={transitionId}
          items={items.data?.items}
          initialItem={item}
          currentGate={transition.data?.current_gate}
          onClose={closeUrlDialog}
        />
      )}
      {excOpen && (
        <RequestExceptionDialog
          transitionId={transitionId}
          items={items.data?.items}
          initialItem={item}
          onClose={closeUrlDialog}
        />
      )}
      {closing && (
        <CloseConditionDialog
          transitionId={transitionId}
          condition={closing}
          onClose={() => setClosing(null)}
        />
      )}
      {riskOpen && (
        <CreateRiskDialog
          transitionId={transitionId}
          items={items.data?.items}
          onClose={() => setRiskOpen(false)}
        />
      )}
    </div>
  );
}

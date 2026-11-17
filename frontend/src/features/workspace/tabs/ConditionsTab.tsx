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
import type { TabProps } from '../types';

function Head({ cols }: { cols: string[] }) {
  return (
    <TableHeader>
      <TableRow>
        {cols.map((c) => (
          <TableHeaderCell key={c || 'actions'}>{c}</TableHeaderCell>
        ))}
      </TableRow>
    </TableHeader>
  );
}

/** Conditions, exceptions & risks tab (FR-035, spec 8.7 g). */
export function ConditionsTab({ transitionId }: TabProps) {
  const s = useRecordStyles();
  const { params, set } = useUrlParams();
  const transition = useTransition(transitionId);
  const conditions = useConditions(transitionId);
  const exceptions = useExceptions(transitionId);
  const risks = useRisks(transitionId);
  const items = useItems(transitionId, { all_gates: 'true' });
  const manageCond = usePerm('manage_conditions');
  const reqExc = usePerm('request_exception');
  const manageRisk = usePerm('manage_risks');
  const [closing, setClosing] = useState<ConditionRow | null>(null);
  const [riskOpen, setRiskOpen] = useState(false);

  const condOpen = params.get('new') === '1';
  const excOpen = params.get('exception') === '1';
  const item = params.get('item') ?? undefined;
  const closeUrlDialog = () => set({ new: undefined, exception: undefined, item: undefined });

  return (
    <div className={s.stack}>
      <PageHeader
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
          <div className={s.tableWrap}>
            <Table aria-label="Conditions" size="small">
              <Head cols={['ID', 'Item', 'Set at', 'Due', 'Owner', 'Status', 'Condition', '']} />
              <TableBody>
                {conditions.data.map((c) => (
                  <TableRow key={c.id}>
                    <TableCell>{c.id}</TableCell>
                    <TableCell>{c.item_id ?? '–'}</TableCell>
                    <TableCell>{c.set_at_gate_short}</TableCell>
                    <TableCell>{c.due_gate_short}</TableCell>
                    <TableCell>{c.owner?.name ?? '–'}</TableCell>
                    <TableCell>
                      <Badge appearance="tint" color={c.status === 'Open' ? 'warning' : 'success'}>
                        {c.status}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      {c.text}
                      {c.close_note && <div className={s.muted}>Closed: {c.close_note}</div>}
                    </TableCell>
                    <TableCell>
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
          </div>
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
          <div className={s.tableWrap}>
            <Table aria-label="Exceptions" size="small">
              <Head cols={['Ref', 'Control item', 'Rationale', 'Status', 'Approval']} />
              <TableBody>
                {exceptions.data.map((e) => (
                  <TableRow key={e.ref}>
                    <TableCell>{e.ref}</TableCell>
                    <TableCell>
                      {e.item_id ? `${e.item_id} – ${e.item_title ?? ''}` : '–'}
                    </TableCell>
                    <TableCell>{e.text}</TableCell>
                    <TableCell>{e.status}</TableCell>
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
          </div>
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
          <div className={s.tableWrap}>
            <Table aria-label="Risk register" size="small">
              <Head cols={['ID', 'Title', 'Rating', 'Decision', 'Linked items']} />
              <TableBody>
                {risks.data.map((r) => (
                  <TableRow key={r.id}>
                    <TableCell>{r.id}</TableCell>
                    <TableCell>{r.title}</TableCell>
                    <TableCell>{r.rating}</TableCell>
                    <TableCell>{r.decision || '–'}</TableCell>
                    <TableCell>{r.item_ids.join(', ') || '–'}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
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

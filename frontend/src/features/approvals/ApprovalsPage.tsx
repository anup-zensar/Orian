import { ReturnFocusDialog } from '../../components/ReturnFocusDialog';
import { useEffect, useRef, useState } from 'react';
import {
  Badge,
  Body1,
  Button,
  Caption1,
  DialogActions,
  DialogBody,
  DialogContent,
  DialogSurface,
  DialogTitle,
  Field,
  Table,
  TableBody,
  TableCell,
  TableHeader,
  TableHeaderCell,
  TableRow,
  Tab,
  TabList,
  Textarea,
  MessageBar,
  MessageBarBody,
  makeStyles,
  tokens,
} from '@fluentui/react-components';
import { useSearchParams } from 'react-router';
import { AppLink } from '../../components/AppLink';
import { DataTable } from '../../components/DataTable';
import { EmptyState } from '../../components/EmptyState';
import { ErrorState } from '../../components/ErrorState';
import { LoadingState } from '../../components/LoadingState';
import { PageHeader } from '../../components/PageHeader';
import { Toolbar } from '../../components/layout/Toolbar';
import { palette } from '../../theme/orionTheme';
import { useApiErrorToast } from '../../hooks/useApiErrorToast';
import { ReasonButton } from '../gates/ReasonButton';
import { useSuccessToast } from '../gates/useSuccessToast';
import { useRoleLabel } from '../reference/options';
import { useMe } from '../users/api';
import {
  useActOnApproval,
  useApproval,
  useApprovals,
  type ApprovalRequest,
  type ApprovalScope,
  type ApprovalStep,
} from './api';

const useStyles = makeStyles({
  page: { display: 'flex', flexDirection: 'column', gap: tokens.spacingVerticalL },
  highlight: {
    backgroundColor: tokens.colorBrandBackground2,
    boxShadow: `inset 4px 0 0 ${palette.yellow}`,
  },
  head: { display: 'flex', gap: tokens.spacingHorizontalS, alignItems: 'center', flexWrap: 'wrap' },
  cell: { display: 'flex', flexDirection: 'column', gap: '4px', minWidth: 0, padding: '8px 0' },
  subject: { fontWeight: tokens.fontWeightSemibold },
  muted: { color: tokens.colorNeutralForeground3 },
  chain: {
    display: 'flex',
    gap: tokens.spacingHorizontalS,
    flexWrap: 'wrap',
    alignItems: 'stretch',
  },
  step: {
    display: 'flex',
    flexDirection: 'column',
    gap: '2px',
    padding: tokens.spacingVerticalS,
    border: `1px solid ${tokens.colorNeutralStroke2}`,
    borderRadius: tokens.borderRadiusMedium,
    minWidth: '150px',
    flex: '1 1 150px',
    backgroundColor: tokens.colorNeutralBackground1,
  },
});

const stepColor = (status: string) =>
  status === 'Approved'
    ? 'success'
    : status === 'Rejected'
      ? 'danger'
      : status === 'Pending'
        ? 'warning'
        : 'subtle';

function StepChain({ steps }: { steps: ApprovalStep[] }) {
  const s = useStyles();
  const roleLabel = useRoleLabel();
  return (
    <div className={s.chain} role="list" aria-label="Approval chain">
      {steps.map((st) => (
        <div key={st.step} className={s.step} role="listitem">
          <Caption1>
            Step {st.step} · {st.label}
          </Caption1>
          <span>
            <Badge appearance="tint" color={stepColor(st.status)}>
              {st.status}
            </Badge>
          </span>
          <Caption1>
            {st.decided_by
              ? `${st.decided_by.name}${st.decided_at ? ` · ${st.decided_at.slice(0, 10)}` : ''}`
              : (st.approver?.name ?? roleLabel(st.role))}
          </Caption1>
          {st.comment && <Caption1>"{st.comment}"</Caption1>}
          {st.status === 'Pending' && st.waiting_days > 0 && (
            <Caption1>Waiting {st.waiting_days} d</Caption1>
          )}
        </div>
      ))}
    </div>
  );
}

function ActDialog(props: {
  request: ApprovalRequest;
  action: 'approve' | 'reject';
  onClose: () => void;
}) {
  const { request, action } = props;
  const [comment, setComment] = useState('');
  const act = useActOnApproval();
  const showError = useApiErrorToast();
  const showSuccess = useSuccessToast();
  const reject = action === 'reject';
  const step = request.current_step;
  const invalid = reject && !comment.trim();

  const submit = () => {
    if (step === null) return;
    act.mutate(
      { request, step, action, comment: comment.trim() },
      {
        onSuccess: () => {
          showSuccess(reject ? 'Request rejected' : 'Step approved');
          props.onClose();
        },
        onError: showError,
      },
    );
  };

  return (
    <ReturnFocusDialog open onOpenChange={(_, d) => !d.open && props.onClose()}>
      <DialogSurface>
        <DialogBody>
          <DialogTitle>
            {reject ? 'Reject' : request.is_mock_step ? 'Approve as CISO/BISO (mock)' : 'Approve'}{' '}
            {request.type_label}
          </DialogTitle>
          <DialogContent>
            <Body1>
              {request.transition_name} · {request.subject_label}
            </Body1>
            <Field
              label={reject ? 'Comment (required)' : 'Comment (optional)'}
              required={reject}
              validationMessage={invalid ? 'A comment is required to reject' : undefined}
            >
              <Textarea value={comment} onChange={(_, d) => setComment(d.value)} rows={4} />
            </Field>
          </DialogContent>
          <DialogActions>
            <Button appearance="secondary" onClick={props.onClose}>
              Cancel
            </Button>
            <Button appearance="primary" disabled={invalid || act.isPending} onClick={submit}>
              {act.isPending ? 'Saving...' : reject ? 'Reject' : 'Approve'}
            </Button>
          </DialogActions>
        </DialogBody>
      </DialogSurface>
    </ReturnFocusDialog>
  );
}

const statusColor = (status: string) =>
  status === 'Approved'
    ? 'success'
    : status === 'Rejected'
      ? 'danger'
      : status === 'Pending'
        ? 'warning'
        : 'subtle';

function ApprovalRow(props: { request: ApprovalRequest; highlighted: boolean }) {
  const s = useStyles();
  const r = props.request;
  const ref = useRef<HTMLTableRowElement>(null);
  const [acting, setActing] = useState<'approve' | 'reject' | null>(null);
  const pending = r.status === 'Pending';

  useEffect(() => {
    if (props.highlighted) ref.current?.scrollIntoView({ block: 'center' });
  }, [props.highlighted]);

  const blocked = r.can_act ? null : (r.act_denied_reason ?? 'You cannot act on this step');

  return (
    <TableRow
      ref={ref}
      className={props.highlighted ? s.highlight : undefined}
      aria-label={`${r.type_label} approval ${r.id}`}
    >
      <TableCell style={{ minWidth: 220, alignItems: 'flex-start' }}>
        <div className={s.cell}>
          <span className={s.head}>
            <Badge appearance="filled" color="brand">
              {r.type_label}
            </Badge>
            <Badge appearance="outline" color={statusColor(r.status)}>
              {r.status}
            </Badge>
          </span>
          <span className={s.subject}>{r.subject_label}</span>
          {r.link && r.link.startsWith('/') && <AppLink to={r.link}>Open subject</AppLink>}
        </div>
      </TableCell>
      <TableCell style={{ minWidth: 200, alignItems: 'flex-start' }}>
        <div className={s.cell}>
          <AppLink to={`/transitions/${r.transition_id}/overview`}>{r.transition_name}</AppLink>
          {r.gate_short && <Caption1 className={s.muted}>Gate {r.gate_short}</Caption1>}
          <Caption1 className={s.muted}>
            {r.id} · requested {r.age_days === 0 ? 'today' : `${r.age_days} d ago`}
            {r.created_by ? ` by ${r.created_by.name}` : ''} ({r.created_source})
          </Caption1>
        </div>
      </TableCell>
      <TableCell style={{ minWidth: 340, alignItems: 'flex-start' }}>
        <div className={s.cell}>
          <StepChain steps={r.steps} />
          {pending && r.is_mock_step && (
            <span>
              <Badge appearance="outline" color="informative">
                Mock step: no real CISO/BISO integration
              </Badge>
            </span>
          )}
        </div>
      </TableCell>
      <TableCell style={{ minWidth: 150, alignItems: 'flex-start' }}>
        {pending && (
          <div className={s.cell}>
            <Toolbar>
              <ReasonButton
                appearance="primary"
                reasons={[blocked]}
                onClick={() => setActing('approve')}
              >
                {r.is_mock_step ? 'Approve as CISO/BISO (mock)' : 'Approve'}
              </ReasonButton>
              <ReasonButton reasons={[blocked]} onClick={() => setActing('reject')}>
                Reject
              </ReasonButton>
            </Toolbar>
          </div>
        )}
        {acting && <ActDialog request={r} action={acting} onClose={() => setActing(null)} />}
      </TableCell>
    </TableRow>
  );
}

function ApprovalTable(props: {
  rows: ApprovalRequest[];
  requestId: string | null;
  label: string;
}) {
  return (
    <DataTable label={props.label}>
      <Table aria-label={props.label} size="medium" style={{ minWidth: 760 }}>
        <TableHeader>
          <TableRow>
            <TableHeaderCell>Request</TableHeaderCell>
            <TableHeaderCell>Transition</TableHeaderCell>
            <TableHeaderCell>Approval chain</TableHeaderCell>
            <TableHeaderCell>Decision</TableHeaderCell>
          </TableRow>
        </TableHeader>
        <TableBody>
          {props.rows.map((r) => (
            <ApprovalRow key={r.id} request={r} highlighted={r.id === props.requestId} />
          ))}
        </TableBody>
      </Table>
    </DataTable>
  );
}

/** Approvals inbox (FR-070, spec 8.12): waiting for me / requested by me / all (OR focal, Admin). */
export function ApprovalsPage() {
  const s = useStyles();
  const [params, setParams] = useSearchParams();
  const me = useMe();
  // The All tab is a permission (View all approvals), editable in Admin > People & permissions.
  const canSeeAll = !!me.data?.permissions.includes('view_all_approvals');
  const requestId = params.get('request');
  const raw = params.get('scope');
  const explicit: ApprovalScope | null =
    raw === 'mine' || raw === 'requested' || (raw === 'all' && canSeeAll) ? raw : null;
  const scopeDenied = raw === 'all' && !canSeeAll && !!me.data;

  // No tab in the link: open the first tab that has items for this person.
  const mine = useApprovals('mine', !!me.data);
  const requested = useApprovals('requested', !!me.data && explicit === null);
  const all = useApprovals(
    'all',
    !!me.data &&
      canSeeAll &&
      explicit === null &&
      mine.data?.length === 0 &&
      requested.data?.length === 0,
  );
  let scope: ApprovalScope = 'mine';
  if (explicit) scope = explicit;
  else if (mine.data && mine.data.length > 0) scope = 'mine';
  else if (requested.data && requested.data.length > 0) scope = 'requested';
  else if (canSeeAll && all.data && all.data.length > 0) scope = 'all';
  const q = scope === 'mine' ? mine : scope === 'requested' ? requested : all;
  const settling = explicit === null && (!me.data || mine.isLoading || requested.isLoading);

  // Deep link: fetch the single request so it is found in any tab, then show it above the list.
  const linked = useApproval(requestId);
  const listed = q.data?.some((r) => r.id === requestId) ?? false;

  return (
    <div className={s.page}>
      <PageHeader
        title="Approvals"
        subtitle="Approval chains run in order; a step is only actionable when it is your turn."
      />
      <TabList
        selectedValue={scope}
        onTabSelect={(_, d) => {
          const next = new URLSearchParams(params);
          next.set('scope', String(d.value));
          next.delete('request');
          setParams(next, { replace: true });
        }}
      >
        <Tab value="mine">Waiting for me</Tab>
        <Tab value="requested">Requested by me</Tab>
        {canSeeAll && <Tab value="all">All</Tab>}
      </TabList>

      {scopeDenied && (
        <MessageBar intent="warning">
          <MessageBarBody>
            The All view needs the View all approvals permission, so Waiting for me is shown
            instead.
          </MessageBarBody>
        </MessageBar>
      )}
      {requestId && linked.isError && (
        <MessageBar intent="error">
          <MessageBarBody>
            Request {requestId} could not be opened: it does not exist or you cannot see it.
          </MessageBarBody>
        </MessageBar>
      )}
      {requestId && linked.data && !listed && !q.isLoading && !settling && (
        <>
          <MessageBar intent="info">
            <MessageBarBody>
              Opened from a link: request {linked.data.id} ({linked.data.status}) is shown here and
              is not part of this tab.
            </MessageBarBody>
          </MessageBar>
          <ApprovalTable rows={[linked.data]} requestId={requestId} label="Linked approval" />
        </>
      )}

      {(q.isLoading || settling) && <LoadingState rows={4} />}
      {q.isError && <ErrorState error={q.error} />}
      {!settling && q.data && q.data.length === 0 && (
        <EmptyState
          message={
            scope === 'mine'
              ? 'Nothing is waiting for your approval. Approvals you raised are under Requested by me.'
              : scope === 'requested'
                ? 'You have not requested any approvals.'
                : 'There are no approval requests.'
          }
        />
      )}
      {!settling && q.data && q.data.length > 0 && (
        <ApprovalTable rows={q.data} requestId={requestId} label="Approval requests" />
      )}
    </div>
  );
}

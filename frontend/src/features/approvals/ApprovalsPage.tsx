import { useEffect, useRef, useState } from 'react';
import {
  Badge,
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
  Subtitle2,
  Tab,
  TabList,
  Textarea,
  makeStyles,
  tokens,
} from '@fluentui/react-components';
import { useSearchParams } from 'react-router';
import { AppLink } from '../../components/AppLink';
import { EmptyState } from '../../components/EmptyState';
import { ErrorState } from '../../components/ErrorState';
import { LoadingState } from '../../components/LoadingState';
import { PageHeader } from '../../components/PageHeader';
import { useApiErrorToast } from '../../hooks/useApiErrorToast';
import { ReasonButton } from '../gates/ReasonButton';
import { useMe } from '../users/api';
import {
  useActOnApproval,
  useApprovals,
  type ApprovalRequest,
  type ApprovalScope,
  type ApprovalStep,
} from './api';

const useStyles = makeStyles({
  page: { display: 'flex', flexDirection: 'column', gap: tokens.spacingVerticalL },
  list: { display: 'flex', flexDirection: 'column', gap: tokens.spacingVerticalM },
  card: {
    display: 'flex',
    flexDirection: 'column',
    gap: tokens.spacingVerticalS,
    padding: tokens.spacingVerticalL,
    border: `1px solid ${tokens.colorNeutralStroke2}`,
    borderRadius: tokens.borderRadiusMedium,
    backgroundColor: tokens.colorNeutralBackground1,
  },
  highlight: {
    border: `2px solid ${tokens.colorBrandStroke1}`,
    boxShadow: tokens.shadow8,
  },
  head: { display: 'flex', gap: tokens.spacingHorizontalS, alignItems: 'center', flexWrap: 'wrap' },
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
    minWidth: '170px',
  },
  actions: {
    display: 'flex',
    gap: tokens.spacingHorizontalS,
    flexWrap: 'wrap',
    marginTop: tokens.spacingVerticalS,
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
              : (st.approver?.name ?? st.role)}
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
  const reject = action === 'reject';
  const step = request.current_step;
  const invalid = reject && !comment.trim();

  const submit = () => {
    if (step === null) return;
    act.mutate(
      { request, step, action, comment: comment.trim() },
      { onSuccess: props.onClose, onError: showError },
    );
  };

  return (
    <Dialog open onOpenChange={(_, d) => !d.open && props.onClose()}>
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
    </Dialog>
  );
}

function ApprovalCard(props: { request: ApprovalRequest; highlighted: boolean }) {
  const s = useStyles();
  const r = props.request;
  const ref = useRef<HTMLDivElement>(null);
  const [acting, setActing] = useState<'approve' | 'reject' | null>(null);
  const pending = r.status === 'Pending';

  useEffect(() => {
    if (props.highlighted) ref.current?.scrollIntoView({ block: 'center' });
  }, [props.highlighted]);

  const blocked = r.can_act ? null : (r.act_denied_reason ?? 'You cannot act on this step');

  return (
    <div
      ref={ref}
      className={`${s.card} ${props.highlighted ? s.highlight : ''}`}
      aria-label={`${r.type_label} approval ${r.id}`}
    >
      <div className={s.head}>
        <Badge appearance="filled" color="brand">
          {r.type_label}
        </Badge>
        <Badge
          appearance="outline"
          color={
            r.status === 'Approved'
              ? 'success'
              : r.status === 'Rejected'
                ? 'danger'
                : r.status === 'Pending'
                  ? 'warning'
                  : 'subtle'
          }
        >
          {r.status}
        </Badge>
        <AppLink to={`/transitions/${r.transition_id}/overview`}>{r.transition_name}</AppLink>
        {r.gate_short && <Caption1>Gate {r.gate_short}</Caption1>}
        <Caption1>
          {r.id} · requested {r.age_days === 0 ? 'today' : `${r.age_days} d ago`}
          {r.created_by ? ` by ${r.created_by.name}` : ''} ({r.created_source})
        </Caption1>
      </div>
      <Subtitle2>{r.subject_label}</Subtitle2>
      <StepChain steps={r.steps} />
      {pending && (
        <div className={s.actions}>
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
          {r.is_mock_step && (
            <Badge appearance="outline" color="informative">
              Mock step: no real CISO/BISO integration
            </Badge>
          )}
        </div>
      )}
      {acting && <ActDialog request={r} action={acting} onClose={() => setActing(null)} />}
    </div>
  );
}

/** Approvals inbox (FR-070, spec 8.12): waiting for me / requested by me / all (OR focal, Admin). */
export function ApprovalsPage() {
  const s = useStyles();
  const [params, setParams] = useSearchParams();
  const me = useMe();
  const role = me.data?.user.role;
  const canSeeAll = role === 'OR_FOCAL' || role === 'ADMIN';
  const requestId = params.get('request');
  const raw = params.get('scope');
  const scope: ApprovalScope = raw === 'requested' || (raw === 'all' && canSeeAll) ? raw : 'mine';
  const q = useApprovals(scope, !!me.data);

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

      {q.isLoading && <LoadingState rows={4} />}
      {q.isError && <ErrorState error={q.error} />}
      {q.data && q.data.length === 0 && (
        <EmptyState
          message={
            scope === 'mine'
              ? 'Nothing is waiting for your approval.'
              : scope === 'requested'
                ? 'You have not requested any approvals.'
                : 'There are no approval requests.'
          }
        />
      )}
      {q.data && q.data.length > 0 && (
        <div className={s.list}>
          {q.data.map((r) => (
            <ApprovalCard key={r.id} request={r} highlighted={r.id === requestId} />
          ))}
        </div>
      )}
    </div>
  );
}

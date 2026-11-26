import { useState } from 'react';
import {
  Badge,
  Body1,
  Button,
  Caption1,
  Subtitle2,
  makeStyles,
  tokens,
} from '@fluentui/react-components';
import { Sparkle16Regular } from '@fluentui/react-icons';
import { useNavigate } from 'react-router';
import { Toolbar } from '../../components/layout/Toolbar';
import { ai } from '../../theme/orionTheme';
import { ActorBadge } from '../../components/ActorBadge';
import { AppLink } from '../../components/AppLink';
import { LensChip } from '../../components/LensChip';
import { useApiErrorToast } from '../../hooks/useApiErrorToast';
import { ApprovalDraftDialog } from './ApprovalDraftDialog';
import { useTransitionAccess } from '../transition/api';
import { ReasonButton } from './ReasonButton';
import { useReference } from '../reference/api';
import { itemStatusList, useOptionLabel, useRoleLabel } from '../reference/options';
import type { Readiness, RecommendedAction } from './api';
import { useDraftApprovalRequest, useDraftChaser, type Draft } from '../drafts/api';
import type { Lens } from '../../theme/tokens';

const useStyles = makeStyles({
  root: { display: 'flex', flexDirection: 'column', gap: tokens.spacingVerticalM, minWidth: 0 },
  verdictRow: {
    display: 'flex',
    alignItems: 'center',
    gap: tokens.spacingHorizontalM,
    flexWrap: 'wrap',
  },
  group: { display: 'flex', flexDirection: 'column', gap: tokens.spacingVerticalXS },
  list: {
    margin: 0,
    paddingLeft: tokens.spacingHorizontalXL,
    '& li': { marginBottom: '2px' },
  },
  narrative: {
    display: 'flex',
    flexDirection: 'column',
    gap: tokens.spacingVerticalS,
    padding: tokens.spacingVerticalM,
    borderRadius: tokens.borderRadiusMedium,
    minWidth: 0,
    border: `1px solid ${tokens.colorNeutralStroke2}`,
    borderTop: `3px solid ${ai.main}`,
    backgroundColor: ai.tint,
  },
  row: { display: 'flex', gap: tokens.spacingHorizontalS, flexWrap: 'wrap', alignItems: 'center' },
  chain: { display: 'flex', gap: tokens.spacingHorizontalS, flexWrap: 'wrap', minWidth: 0 },
  actions: { display: 'flex', flexDirection: 'column', gap: tokens.spacingVerticalS },
  step: {
    padding: tokens.spacingVerticalS,
    border: `1px solid ${tokens.colorNeutralStroke2}`,
    borderRadius: tokens.borderRadiusMedium,
    display: 'flex',
    flexDirection: 'column',
    gap: '2px',
    minWidth: '160px',
  },
});

const KIND_ORDER: RecommendedAction['kind'][] = [
  'request_exception',
  'open_ocet',
  'create_support_model',
  'draft_chaser',
  'create_action',
  'request_approval',
  'request_inputs',
];
const KIND_TITLES: Record<string, string> = {
  request_exception: 'Request exceptions',
  open_ocet: 'OCET',
  create_support_model: 'Support model',
  draft_chaser: 'Chasers',
  create_action: 'Actions',
  request_approval: 'Approval',
  request_inputs: 'Inputs',
};
const MAX_ACTIONS = 5;

const LENSES: Lens[] = ['Business', 'Technical', 'Compliance'];
const asLens = (v: string): Lens | null => (LENSES.includes(v as Lens) ? (v as Lens) : null);

const verdictColor = (v: string) =>
  v === 'Ready' ? 'success' : v === 'Ready with conditions' ? 'warning' : 'danger';

const stepColor = (st: string) =>
  st === 'Approved'
    ? 'success'
    : st === 'Rejected'
      ? 'danger'
      : st === 'Pending'
        ? 'warning'
        : 'subtle';

/** Permission that the form behind a recommended action needs (checked per transition). */
const ACTION_PERM: Record<string, string> = {
  create_action: 'manage_actions',
  request_exception: 'request_exception',
  request_inputs: 'edit_ocet',
  create_support_model: 'edit_support_model',
};

/** The severity that counts as critical (severities list setting; Critical today). */
function useCriticalSeverity(): string {
  const { data } = useReference();
  const found = data?.lists?.severities?.find((o) => o.meta?.counts_as_critical === true);
  return found?.value ?? 'Critical';
}

/** Readiness check card (FR-050, spec 8.9): verdict, why, Orion narrative and recommended actions. */
export function ReadinessCard(props: {
  transitionId: string;
  readiness: Readiness;
  isCurrent: boolean;
}) {
  const s = useStyles();
  const r = props.readiness;
  const roleLabel = useRoleLabel();
  const optionLabel = useOptionLabel();
  const criticalSeverity = useCriticalSeverity();
  const reference = useReference();
  // Short gate label from reference data (SG4_ATD -> SG4 (AtD)); falls back to the code.
  const gateShort = (code: string) =>
    reference.data?.gates.find((g) => g.code === code)?.short ?? code;
  const navigate = useNavigate();
  const showError = useApiErrorToast();
  const base = `/transitions/${props.transitionId}`;
  const chaser = useDraftChaser(props.transitionId);
  const approvalDraft = useDraftApprovalRequest(props.transitionId);
  const access = useTransitionAccess(props.transitionId);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [showAll, setShowAll] = useState(false);

  const itemLink = (itemId: string) => `${base}/assessment?item=${encodeURIComponent(itemId)}`;
  const firstItem = (a: RecommendedAction) => a.item_ids[0];

  const runAction = (a: RecommendedAction) => {
    switch (a.kind) {
      case 'draft_chaser': {
        const ids =
          a.item_ids.length > 0
            ? a.item_ids
            : r.blocking.flatMap((g) => g.items.map((i) => i.item_id));
        chaser.mutate(ids, {
          onSuccess: (d) => navigate(`/drafts?draft=${d.id}`),
          onError: showError,
        });
        return;
      }
      case 'create_action':
        navigate(
          `${base}/gaps?new=1${firstItem(a) ? `&item=${encodeURIComponent(firstItem(a))}` : ''}`,
        );
        return;
      case 'request_exception':
        navigate(
          `${base}/conditions?exception=1${firstItem(a) ? `&item=${encodeURIComponent(firstItem(a))}` : ''}`,
        );
        return;
      case 'open_ocet':
      case 'request_inputs':
        navigate(`${base}/ocet`);
        return;
      case 'create_support_model':
        navigate(`${base}/support-model`);
        return;
      case 'request_approval':
        approvalDraft.mutate(r.gate, { onSuccess: setDraft, onError: showError });
        return;
    }
  };

  const isBusy = (a: RecommendedAction) =>
    (a.kind === 'draft_chaser' && chaser.isPending) ||
    (a.kind === 'request_approval' && approvalDraft.isPending);

  const sendDraftsReason = access.reason('send_drafts');
  const reasonsFor = (a: RecommendedAction) => {
    if (a.kind === 'request_approval')
      return [
        sendDraftsReason,
        r.can_request_approval
          ? null
          : (r.request_denied_reason ?? 'Approval cannot be requested yet'),
      ];
    if (a.kind === 'draft_chaser') return [sendDraftsReason];
    const perm = ACTION_PERM[a.kind];
    return perm ? [access.reason(perm)] : [];
  };

  const criticalIds = new Set(
    [...r.blocking.flatMap((g) => g.items), ...r.critical_gaps]
      .filter((i) => i.gap_severity === criticalSeverity || i.status === 'Non-compliant')
      .map((i) => i.item_id),
  );
  const rank = (a: RecommendedAction) => {
    const k = KIND_ORDER.indexOf(a.kind);
    const crit = a.item_ids.some((id) => criticalIds.has(id)) ? 0 : 1;
    // actions that cover a Critical / Non-compliant item come first, whatever their kind
    return crit * 100 + k;
  };
  const sorted = r.recommended_actions
    .map((a, idx) => ({ a, idx }))
    .sort((x, y) => {
      // request_approval first when present (primary), then by importance
      const px = x.a.kind === 'request_approval' ? -1 : 0;
      const py = y.a.kind === 'request_approval' ? -1 : 0;
      return px - py || rank(x.a) - rank(y.a) || x.idx - y.idx;
    })
    .map((x) => x.a);
  const visible = showAll ? [] : sorted.slice(0, MAX_ACTIONS);
  const hidden = sorted.slice(MAX_ACTIONS);
  const hiddenGroups = KIND_ORDER.map((k) => ({
    k,
    list: hidden.filter((a) => a.kind === k),
  })).filter((g) => g.list.length > 0);
  const renderAction = (a: RecommendedAction) => (
    <ReasonButton
      key={a.key}
      appearance={a.kind === 'request_approval' ? 'primary' : 'secondary'}
      reasons={reasonsFor(a)}
      onClick={() => runAction(a)}
    >
      {isBusy(a) ? 'Working...' : a.label}
    </ReasonButton>
  );
  const needsDisabledApproval =
    r.gate_type === 'decision' &&
    r.verdict !== 'Ready' &&
    !r.can_request_approval &&
    !r.recommended_actions.some((a) => a.kind === 'request_approval');

  return (
    <div className={s.root}>
      <div className={s.verdictRow}>
        <Badge size="extra-large" appearance="tint" color={verdictColor(r.verdict)}>
          {r.verdict_label || r.verdict}
        </Badge>
        <Caption1>
          Readiness check for {r.gate_short} · generated by workflow rules from live data
        </Caption1>
        <ActorBadge actor="Workflow rule" />
      </div>

      {r.warnings.length > 0 && (
        <ul className={s.list}>
          {r.warnings.map((w) => (
            <li key={w}>
              <Caption1>{w}</Caption1>
            </li>
          ))}
        </ul>
      )}

      {r.blocking.length > 0 && (
        <div className={s.group}>
          <Subtitle2 as="h4">Blocking items</Subtitle2>
          {r.blocking.map((g) => (
            <div key={g.lens} className={s.group}>
              <div className={s.row}>
                {asLens(g.lens) ? (
                  <LensChip lens={asLens(g.lens) as Lens} />
                ) : (
                  <Badge>{g.lens}</Badge>
                )}
                <Caption1>{g.items.length} item(s)</Caption1>
              </div>
              <ul className={s.list}>
                {g.items.map((i) => (
                  <li key={i.item_id}>
                    <AppLink to={itemLink(i.item_id)}>{i.item_id}</AppLink> {i.title} ·{' '}
                    <Caption1>
                      {optionLabel(itemStatusList(g.lens), i.status)}
                      {i.owner ? ` · ${i.owner.name}` : ''} · {i.reason}
                    </Caption1>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      )}

      {r.critical_gaps.length > 0 && (
        <div className={s.group}>
          <Subtitle2 as="h4">Critical gaps/risks</Subtitle2>
          <ul className={s.list}>
            {r.critical_gaps.map((i) => (
              <li key={i.item_id}>
                <AppLink to={itemLink(i.item_id)}>{i.item_id}</AppLink> {i.title} ·{' '}
                <Caption1>{i.reason}</Caption1>
              </li>
            ))}
          </ul>
        </div>
      )}

      {r.open_conditions.length > 0 && (
        <div className={s.group}>
          <Subtitle2 as="h4">Open conditions</Subtitle2>
          <ul className={s.list}>
            {r.open_conditions.map((c) => (
              <li key={c.id}>
                <AppLink to={`${base}/conditions`}>{c.id}</AppLink> {c.text} ·{' '}
                <Caption1>
                  due {gateShort(c.due_gate)}
                  {c.owner ? ` · ${c.owner.name}` : ''}
                  {c.item_id ? ` · item ${c.item_id}` : ''}
                </Caption1>
              </li>
            ))}
          </ul>
        </div>
      )}

      {r.carried_items.length > 0 && (
        <div className={s.group}>
          <Subtitle2 as="h4">Carried items</Subtitle2>
          <ul className={s.list}>
            {r.carried_items.map((c) => (
              <li key={c.condition_id}>
                <AppLink to={itemLink(c.item_id)}>{c.item_id}</AppLink> {c.title} ·{' '}
                <Caption1>
                  {optionLabel('condition_statuses', c.status)} · {c.condition_id} set at{' '}
                  {gateShort(c.set_at_gate)}, due {gateShort(c.due_gate)}
                </Caption1>
              </li>
            ))}
          </ul>
        </div>
      )}

      {r.pending_exceptions.length > 0 && (
        <div className={s.group}>
          <Subtitle2 as="h4">Pending exceptions</Subtitle2>
          <ul className={s.list}>
            {r.pending_exceptions.map((e) => (
              <li key={e.ref}>
                <AppLink to={`${base}/conditions`}>{e.ref}</AppLink>
                {e.item_id ? ` on ${e.item_id}` : ''} ·{' '}
                <Caption1>{optionLabel('exception_statuses', e.status)}</Caption1>
              </li>
            ))}
          </ul>
        </div>
      )}

      {(r.failed_evals.length > 0 || r.unevaluated_evals > 0) && (
        <div className={s.group}>
          <Subtitle2 as="h4">Evaluation results</Subtitle2>
          <ul className={s.list}>
            {r.failed_evals.map((e) => (
              <li key={e.metric_id}>
                Eval metric below target: {e.metric_id} {e.metric} · result {e.result} (target{' '}
                {e.target_text})
              </li>
            ))}
            {r.unevaluated_evals > 0 && (
              <li>{r.unevaluated_evals} mandatory metric(s) have no result yet</li>
            )}
          </ul>
        </div>
      )}

      <div className={s.row}>
        {r.ocet_status != null && (
          <Badge appearance="outline">
            <span>
              OCET: <AppLink to={`${base}/ocet`}>{r.ocet_status}</AppLink>
            </span>
          </Badge>
        )}
        {r.support_model_status != null && (
          <Badge appearance="outline">
            <span>
              Support model:{' '}
              <AppLink to={`${base}/support-model`}>{r.support_model_status}</AppLink>
            </span>
          </Badge>
        )}
      </div>

      {r.approval && (
        <div className={s.group}>
          <Subtitle2 as="h4">
            Approval chain ({r.approval.request_id} · {r.approval.status})
          </Subtitle2>
          <div className={s.chain}>
            {r.approval.steps.map((st) => (
              <div key={st.step} className={s.step}>
                <Caption1>
                  Step {st.step} · {st.label}
                </Caption1>
                <span>
                  <Badge appearance="tint" color={stepColor(st.status)}>
                    {st.status}
                  </Badge>
                </span>
                <Caption1>{st.approver?.name ?? roleLabel(st.role)}</Caption1>
              </div>
            ))}
          </div>
          <AppLink to={`/approvals?request=${encodeURIComponent(r.approval.request_id)}&scope=all`}>
            Open in Approvals
          </AppLink>
        </div>
      )}

      <div className={s.narrative}>
        <div className={s.row}>
          <Sparkle16Regular />
          <Subtitle2 as="h4">Orion assessment</Subtitle2>
          <ActorBadge actor="Orion agent" />
          <Caption1>by {r.narrative_by}</Caption1>
        </div>
        <Body1 style={{ whiteSpace: 'pre-wrap' }}>{r.narrative}</Body1>
        {(r.recommended_actions.length > 0 || needsDisabledApproval) && (
          <div className={s.actions} role="group" aria-label="Recommended actions">
            <Toolbar>
              {needsDisabledApproval && (
                <ReasonButton
                  appearance="primary"
                  reasons={[
                    sendDraftsReason,
                    r.request_denied_reason ?? 'Approval cannot be requested yet',
                  ]}
                >
                  Request approval
                </ReasonButton>
              )}
              {visible.map(renderAction)}
              {hidden.length > 0 && (
                <Button appearance="subtle" onClick={() => setShowAll((v) => !v)}>
                  {showAll ? 'Show fewer' : `Show all (${sorted.length})`}
                </Button>
              )}
            </Toolbar>
            {showAll && (
              <>
                <Toolbar>{sorted.slice(0, MAX_ACTIONS).map(renderAction)}</Toolbar>
                {hiddenGroups.map((g) => (
                  <div key={g.k} className={s.group}>
                    <Caption1>
                      {KIND_TITLES[g.k] ?? g.k} ({g.list.length})
                    </Caption1>
                    <Toolbar>{g.list.map(renderAction)}</Toolbar>
                  </div>
                ))}
              </>
            )}
          </div>
        )}
        <Caption1>
          Orion only proposes. Each action opens a draft or a form; a person confirms every change.
        </Caption1>
      </div>

      {draft && (
        <ApprovalDraftDialog
          draft={draft}
          sendReason={
            sendDraftsReason ??
            (r.can_request_approval
              ? null
              : (r.request_denied_reason ?? 'Approval cannot be requested yet'))
          }
          onClose={() => setDraft(null)}
        />
      )}
    </div>
  );
}

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
import { ActorBadge } from '../../components/ActorBadge';
import { AppLink } from '../../components/AppLink';
import { LensChip } from '../../components/LensChip';
import { useApiErrorToast } from '../../hooks/useApiErrorToast';
import { ApprovalDraftDialog } from './ApprovalDraftDialog';
import { ReasonButton } from './ReasonButton';
import { roleLabel } from './useSuccessToast';
import type { Readiness, RecommendedAction } from './api';
import { useDraftApprovalRequest, useDraftChaser, type Draft } from '../drafts/api';
import type { Lens } from '../../theme/tokens';

const useStyles = makeStyles({
  root: { display: 'flex', flexDirection: 'column', gap: tokens.spacingVerticalM },
  verdictRow: {
    display: 'flex',
    alignItems: 'center',
    gap: tokens.spacingHorizontalM,
    flexWrap: 'wrap',
  },
  group: { display: 'flex', flexDirection: 'column', gap: tokens.spacingVerticalXS },
  list: { margin: 0, paddingLeft: tokens.spacingHorizontalXL },
  narrative: {
    display: 'flex',
    flexDirection: 'column',
    gap: tokens.spacingVerticalS,
    padding: tokens.spacingVerticalM,
    borderRadius: tokens.borderRadiusMedium,
    border: `1px solid ${tokens.colorNeutralStroke2}`,
    backgroundColor: tokens.colorNeutralBackground2,
  },
  row: { display: 'flex', gap: tokens.spacingHorizontalS, flexWrap: 'wrap', alignItems: 'center' },
  chain: { display: 'flex', gap: tokens.spacingHorizontalS, flexWrap: 'wrap' },
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

/** Readiness check card (FR-050, spec 8.9): verdict, why, Orion narrative and recommended actions. */
export function ReadinessCard(props: {
  transitionId: string;
  readiness: Readiness;
  isCurrent: boolean;
}) {
  const s = useStyles();
  const r = props.readiness;
  const navigate = useNavigate();
  const showError = useApiErrorToast();
  const base = `/transitions/${props.transitionId}`;
  const chaser = useDraftChaser(props.transitionId);
  const approvalDraft = useDraftApprovalRequest(props.transitionId);
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

  const reasonsFor = (a: RecommendedAction) =>
    a.kind === 'request_approval' && !r.can_request_approval
      ? [r.request_denied_reason ?? 'Approval cannot be requested yet']
      : [];

  const criticalIds = new Set(
    [...r.blocking.flatMap((g) => g.items), ...r.critical_gaps]
      .filter((i) => i.gap_severity === 'Critical' || i.status === 'Non-compliant')
      .map((i) => i.item_id),
  );
  const rank = (a: RecommendedAction) => {
    const k = KIND_ORDER.indexOf(a.kind);
    const crit = a.item_ids.some((id) => criticalIds.has(id)) ? 0 : 1;
    return k * 2 + crit;
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
  const hiddenGroups = KIND_ORDER.map((k) => ({ k, list: hidden.filter((a) => a.kind === k) })).filter(
    (g) => g.list.length > 0,
  );
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
        <Badge size="extra-large" appearance="filled" color={verdictColor(r.verdict)}>
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
                      {i.status}
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
          <Subtitle2 as="h4">Critical gaps</Subtitle2>
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
                  due {c.due_gate}
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
                  {c.status} · {c.condition_id} set at {c.set_at_gate}, due {c.due_gate}
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
                {e.item_id ? ` on ${e.item_id}` : ''} · <Caption1>{e.status}</Caption1>
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
            OCET: <AppLink to={`${base}/ocet`}>{r.ocet_status}</AppLink>
          </Badge>
        )}
        {r.support_model_status != null && (
          <Badge appearance="outline">
            Support model: <AppLink to={`${base}/support-model`}>{r.support_model_status}</AppLink>
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
          <div className={s.group}>
            <div className={s.row} role="group" aria-label="Recommended actions">
              {needsDisabledApproval && (
                <ReasonButton
                  appearance="primary"
                  reasons={[r.request_denied_reason ?? 'Approval cannot be requested yet']}
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
            </div>
            {showAll && (
              <>
                <div className={s.row}>{sorted.slice(0, MAX_ACTIONS).map(renderAction)}</div>
                {hiddenGroups.map((g) => (
                  <div key={g.k} className={s.group}>
                    <Caption1>
                      {KIND_TITLES[g.k] ?? g.k} ({g.list.length})
                    </Caption1>
                    <div className={s.row}>{g.list.map(renderAction)}</div>
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
            r.can_request_approval
              ? null
              : (r.request_denied_reason ?? 'Approval cannot be requested yet')
          }
          onClose={() => setDraft(null)}
        />
      )}
    </div>
  );
}

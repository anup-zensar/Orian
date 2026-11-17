import dayjs from 'dayjs';
import {
  Badge,
  Body1,
  Caption1,
  MessageBar,
  MessageBarBody,
  ProgressBar,
  Subtitle2,
  makeStyles,
  tokens,
} from '@fluentui/react-components';
import { ActorBadge } from '../../../components/ActorBadge';
import { AppLink } from '../../../components/AppLink';
import { EmptyState } from '../../../components/EmptyState';
import { ErrorState } from '../../../components/ErrorState';
import { LensChip } from '../../../components/LensChip';
import { LoadingState } from '../../../components/LoadingState';
import { SectionCard } from '../../../components/SectionCard';
import { lensColors, type ActorType, type Lens } from '../../../theme/tokens';
import { useTransition, type TransitionDetail } from '../../transition/api';
import {
  useAudit,
  useGatesOverview,
  useOverviewConditions,
  useOverviewExceptions,
  useOverviewRisks,
} from '../api';
import type { TabProps } from '../types';

const useStyles = makeStyles({
  grid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
    gap: tokens.spacingHorizontalL,
    marginBottom: tokens.spacingVerticalL,
  },
  two: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))',
    gap: tokens.spacingHorizontalL,
    marginBottom: tokens.spacingVerticalL,
  },
  lensCard: {
    display: 'flex',
    flexDirection: 'column',
    gap: tokens.spacingVerticalS,
    padding: tokens.spacingVerticalL,
    borderRadius: tokens.borderRadiusMedium,
    border: `1px solid ${tokens.colorNeutralStroke2}`,
    borderTopWidth: '4px',
  },
  pct: {
    fontSize: tokens.fontSizeHero800,
    lineHeight: tokens.lineHeightHero800,
    fontWeight: tokens.fontWeightSemibold,
  },
  counts: { display: 'flex', flexWrap: 'wrap', gap: tokens.spacingHorizontalS },
  list: {
    listStyle: 'none',
    margin: 0,
    padding: 0,
    display: 'flex',
    flexDirection: 'column',
    gap: tokens.spacingVerticalS,
  },
  li: {
    display: 'flex',
    flexDirection: 'column',
    gap: '2px',
    paddingBottom: tokens.spacingVerticalS,
    borderBottom: `1px solid ${tokens.colorNeutralStroke2}`,
  },
  line: { display: 'flex', gap: tokens.spacingHorizontalS, alignItems: 'center', flexWrap: 'wrap' },
  timeline: { display: 'flex', flexDirection: 'column', gap: tokens.spacingVerticalM },
});

function LensCards({ detail }: { detail: TransitionDetail }) {
  const s = useStyles();
  const base = `/transitions/${encodeURIComponent(detail.id)}`;
  return (
    <div className={s.grid}>
      {detail.lenses.map((l) => {
        const color = lensColors[l.lens as Lens];
        return (
          <section
            key={l.lens}
            className={s.lensCard}
            style={{ borderTopColor: color?.border, backgroundColor: color?.background }}
            aria-label={`${l.lens} lens`}
          >
            <div className={s.line}>
              <LensChip lens={l.lens as Lens} />
              <Caption1>{l.owner_label}</Caption1>
            </div>
            <span className={s.pct}>{l.readiness_pct}%</span>
            <ProgressBar value={l.readiness_pct / 100} aria-label={`${l.lens} readiness`} />
            <div className={s.counts}>
              <Badge appearance="outline">{l.done} done</Badge>
              <Badge appearance="outline">{l.in_progress} in progress</Badge>
              <Badge appearance="outline">{l.not_started} not started</Badge>
              <Badge appearance="outline" color={l.open_gaps ? 'danger' : 'subtle'}>
                {l.open_gaps} gaps
              </Badge>
              <Badge appearance="outline" color={l.critical_gaps ? 'danger' : 'subtle'}>
                {l.critical_gaps} critical
              </Badge>
            </div>
            <Caption1>{l.question}</Caption1>
            <AppLink to={`${base}/assessment?lens=${l.lens}`}>View {l.lens} items</AppLink>
          </section>
        );
      })}
    </div>
  );
}

function ConditionsCard({ id }: { id: string }) {
  const s = useStyles();
  const q = useOverviewConditions(id);
  const open = (q.data ?? []).filter((c) => c.status === 'Open');
  return (
    <SectionCard
      title="Open conditions"
      actions={
        <AppLink to={`/transitions/${encodeURIComponent(id)}/conditions`}>All conditions</AppLink>
      }
    >
      {q.isPending ? (
        <LoadingState rows={2} />
      ) : q.error ? (
        <ErrorState error={q.error} />
      ) : open.length === 0 ? (
        <EmptyState message="No open conditions." />
      ) : (
        <ul className={s.list}>
          {open.map((c) => (
            <li key={c.id} className={s.li}>
              <div className={s.line}>
                <strong>{c.id}</strong>
                {c.item_id && <Caption1>{c.item_id}</Caption1>}
                <Badge appearance="tint">Due {c.due_gate_short}</Badge>
              </div>
              <Body1>{c.text}</Body1>
              <Caption1>Owner {c.owner?.name ?? 'unassigned'}</Caption1>
            </li>
          ))}
        </ul>
      )}
    </SectionCard>
  );
}

function ExceptionsCard({ id }: { id: string }) {
  const s = useStyles();
  const q = useOverviewExceptions(id);
  const pending = (q.data ?? []).filter(
    (e) => e.status.startsWith('Pending') || e.status === 'Draft',
  );
  return (
    <SectionCard title="Pending exceptions">
      {q.isPending ? (
        <LoadingState rows={2} />
      ) : q.error ? (
        <ErrorState error={q.error} />
      ) : pending.length === 0 ? (
        <EmptyState message="No pending exceptions." />
      ) : (
        <ul className={s.list}>
          {pending.map((e) => (
            <li key={e.ref} className={s.li}>
              <div className={s.line}>
                <strong>{e.ref}</strong>
                {e.item_id && <Caption1>{e.item_id}</Caption1>}
                <Badge appearance="tint" color="warning">
                  {e.status}
                </Badge>
              </div>
              <Body1>{e.text}</Body1>
              {e.approval_request_id && (
                <AppLink to="/approvals">Approval {e.approval_request_id}</AppLink>
              )}
            </li>
          ))}
        </ul>
      )}
    </SectionCard>
  );
}

function RisksCard({ id }: { id: string }) {
  const s = useStyles();
  const q = useOverviewRisks(id);
  return (
    <SectionCard title="Risks">
      {q.isPending ? (
        <LoadingState rows={2} />
      ) : q.error ? (
        <ErrorState error={q.error} />
      ) : (q.data ?? []).length === 0 ? (
        <EmptyState message="No risks recorded." />
      ) : (
        <ul className={s.list}>
          {(q.data ?? []).map((r) => (
            <li key={r.id} className={s.li}>
              <div className={s.line}>
                <strong>{r.id}</strong>
                <Badge
                  appearance="tint"
                  color={
                    r.rating === 'High' ? 'danger' : r.rating === 'Medium' ? 'warning' : 'subtle'
                  }
                >
                  {r.rating}
                </Badge>
              </div>
              <Body1>{r.title}</Body1>
              {r.decision && <Caption1>{r.decision}</Caption1>}
            </li>
          ))}
        </ul>
      )}
    </SectionCard>
  );
}

function RecentActivity({ id }: { id: string }) {
  const s = useStyles();
  const q = useAudit({ transition_id: id, limit: 5 }, id);
  return (
    <SectionCard
      title="Recent activity"
      actions={
        <AppLink to={`/transitions/${encodeURIComponent(id)}/activity`}>All activity</AppLink>
      }
    >
      {q.isPending ? (
        <LoadingState rows={3} />
      ) : q.error ? (
        <ErrorState error={q.error} />
      ) : (q.data?.items ?? []).length === 0 ? (
        <EmptyState message="No activity yet." />
      ) : (
        <ul className={s.list}>
          {(q.data?.items ?? []).slice(0, 5).map((e) => (
            <li key={e.id} className={s.li}>
              <div className={s.line}>
                <ActorBadge actor={e.actor_type as ActorType} />
                <Body1>
                  {e.entity} {e.entity_id}: {e.action}
                </Body1>
              </div>
              <Caption1>
                {e.actor_name ?? e.actor_type} · {dayjs(e.at).format('D MMM YYYY HH:mm')}
                {e.note ? ` · ${e.note}` : ''}
              </Caption1>
            </li>
          ))}
        </ul>
      )}
    </SectionCard>
  );
}

function GateHistory({ id }: { id: string }) {
  const s = useStyles();
  const q = useGatesOverview(id);
  const gates = (q.data?.gates ?? []).filter((g) => g.reviews.length > 0);
  return (
    <SectionCard
      title="Gate history"
      actions={<AppLink to={`/transitions/${encodeURIComponent(id)}/gates`}>Gates tab</AppLink>}
    >
      {q.isPending ? (
        <LoadingState rows={3} />
      ) : q.error ? (
        <ErrorState error={q.error} />
      ) : gates.length === 0 ? (
        <EmptyState message="No gate reviews or decisions recorded yet." />
      ) : (
        <ol className={s.list}>
          {gates.map((g) =>
            g.reviews.map((r) => (
              <li key={`${g.code}-${r.id}`} className={s.li}>
                <div className={s.line}>
                  <strong>{g.short}</strong>
                  <Badge
                    appearance="tint"
                    color={
                      r.outcome === 'Hold'
                        ? 'danger'
                        : r.outcome.includes('conditions')
                          ? 'warning'
                          : 'success'
                    }
                  >
                    {r.outcome}
                  </Badge>
                </div>
                <Caption1>
                  {r.decided_by?.name ?? 'Unknown'} ·{' '}
                  {dayjs(r.decided_at).format('D MMM YYYY HH:mm')}
                </Caption1>
                {r.note && <Body1>{r.note}</Body1>}
              </li>
            )),
          )}
        </ol>
      )}
    </SectionCard>
  );
}

/** Overview tab (FR-030 a, spec 8.7 a): lens cards, conditions, exceptions, risks, blocker, activity, gates. */
export function OverviewTab({ transitionId }: TabProps) {
  const s = useStyles();
  const { data: detail, error, isPending } = useTransition(transitionId);
  if (isPending) return <LoadingState rows={5} />;
  if (error || !detail) return <ErrorState error={error} />;
  return (
    <>
      {detail.blocker_note && (
        <MessageBar intent="error" style={{ marginBottom: tokens.spacingVerticalL }}>
          <MessageBarBody>
            <strong>Blocker:</strong> {detail.blocker_note}
          </MessageBarBody>
        </MessageBar>
      )}
      {detail.assessment_launched ? (
        <>
          <Subtitle2 as="h2">Readiness by lens at {detail.current_gate_short}</Subtitle2>
          <LensCards detail={detail} />
        </>
      ) : (
        <EmptyState message="Lens readiness appears once the assessment is launched." />
      )}
      <div className={s.two}>
        <ConditionsCard id={detail.id} />
        <ExceptionsCard id={detail.id} />
        <RisksCard id={detail.id} />
      </div>
      <div className={s.two}>
        <RecentActivity id={detail.id} />
        <GateHistory id={detail.id} />
      </div>
    </>
  );
}

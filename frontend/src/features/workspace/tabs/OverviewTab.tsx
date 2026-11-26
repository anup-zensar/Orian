import dayjs from 'dayjs';
import { useState } from 'react';
import {
  Badge,
  Body1,
  Button,
  Caption1,
  MessageBar,
  MessageBarBody,
  ProgressBar,
  Subtitle2,
  Toast,
  ToastTitle,
  makeStyles,
  tokens,
  useToastController,
} from '@fluentui/react-components';
import { ActorBadge } from '../../../components/ActorBadge';
import { AppLink } from '../../../components/AppLink';
import { EmptyState } from '../../../components/EmptyState';
import { ErrorState } from '../../../components/ErrorState';
import { LensChip } from '../../../components/LensChip';
import { LoadingState } from '../../../components/LoadingState';
import { SectionCard } from '../../../components/SectionCard';
import { plural } from '../../../lib/format';
import { lensColors, type ActorType, type Lens } from '../../../theme/tokens';
import { TOASTER_ID, useApiErrorToast } from '../../../hooks/useApiErrorToast';
import { DynamicField } from '../../intake/DynamicField';
import { useUpdateTransition } from '../../intake/api';
import {
  displayValue,
  emptyValue,
  fromApiValue,
  toApiValue,
  type FieldValue,
} from '../../intake/fieldValues';
import { fieldState, useIntakeFields, useOptionLabel } from '../../reference/options';
import { useUsers } from '../../users/api';
import { useTransition, type TransitionDetail } from '../../transition/api';
import {
  useAudit,
  useGatesOverview,
  useOverviewConditions,
  useOverviewExceptions,
  useOverviewRisks,
} from '../api';
import { itemCountsParts } from '../itemCounts';
import type { TabProps } from '../types';

const useStyles = makeStyles({
  grid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 200px), 1fr))',
    gap: tokens.spacingHorizontalL,
    marginBottom: tokens.spacingVerticalL,
  },
  two: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 340px), 1fr))',
    alignItems: 'start',
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
  attnRow: {
    display: 'flex',
    gap: tokens.spacingHorizontalM,
    alignItems: 'flex-start',
    paddingBottom: tokens.spacingVerticalS,
    borderBottom: `1px solid ${tokens.colorNeutralStroke2}`,
  },
  attnText: { display: 'flex', flexDirection: 'column', minWidth: 0, flex: 1 },
  ellipsis: {
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
    color: tokens.colorNeutralForeground3,
  },
  line: { display: 'flex', gap: tokens.spacingHorizontalS, alignItems: 'center', flexWrap: 'wrap' },
  fieldGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
    gap: tokens.spacingHorizontalM,
  },
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
            <span className={s.pct}>{l.scope === 0 ? '–' : `${l.readiness_pct}%`}</span>
            <ProgressBar value={l.readiness_pct / 100} aria-label={`${l.lens} readiness`} />
            <div className={s.counts}>
              <Badge appearance="outline">{l.done} done</Badge>
              <Badge appearance="outline">{l.in_progress} in progress</Badge>
              <Badge appearance="outline">{l.not_started} not started</Badge>
              <Badge appearance="outline" color={l.open_gaps ? 'danger' : 'informative'}>
                {l.open_gaps} gaps
              </Badge>
              <Badge appearance="outline" color={l.critical_gaps ? 'danger' : 'informative'}>
                {l.critical_gaps} critical gaps/risks
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

/** One card instead of three lists: counts of what still needs a decision, with a link to manage them. */
function NeedsAttention({ id }: { id: string }) {
  const s = useStyles();
  const optionLabel = useOptionLabel();
  const conditions = useOverviewConditions(id);
  const exceptions = useOverviewExceptions(id);
  const risks = useOverviewRisks(id);
  const open = (conditions.data ?? []).filter((c) => c.status === 'Open');
  const pending = (exceptions.data ?? []).filter(
    (e) => e.status.startsWith('Pending') || e.status === 'Draft',
  );
  const riskList = risks.data ?? [];
  const failed = conditions.error ?? exceptions.error ?? risks.error;
  const loading = conditions.isPending || exceptions.isPending || risks.isPending;
  const row = (label: string, count: number, preview?: string) => (
    <li key={label} className={s.attnRow}>
      <Badge
        appearance={count > 0 ? 'filled' : 'outline'}
        color={count > 0 ? 'warning' : 'informative'}
        shape="rounded"
      >
        {count}
      </Badge>
      <div className={s.attnText}>
        <Body1>{label}</Body1>
        {preview && <Caption1 className={s.ellipsis}>{preview}</Caption1>}
      </div>
    </li>
  );
  const topRisk = riskList.find((r) => r.rating === 'High') ?? riskList[0];
  return (
    <SectionCard
      title="Needs attention"
      actions={
        <AppLink to={`/transitions/${encodeURIComponent(id)}/conditions`}>
          Manage in Conditions
        </AppLink>
      }
    >
      {loading ? (
        <LoadingState rows={2} />
      ) : failed ? (
        <ErrorState error={failed} />
      ) : (
        <ul className={s.list}>
          {row(
            'Open conditions',
            open.length,
            open[0] &&
              `${open[0].id}${open[0].item_id ? ` (${open[0].item_id})` : ''}: ${open[0].text}`,
          )}
          {row(
            'Pending exceptions',
            pending.length,
            pending[0] &&
              `${pending[0].ref} (${optionLabel('exception_statuses', pending[0].status)}): ${pending[0].text}`,
          )}
          {row(
            'Risks',
            riskList.length,
            topRisk &&
              `${topRisk.id} (${optionLabel('risk_ratings', topRisk.rating)}): ${topRisk.title}`,
          )}
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

/** One-line gate summary; the full history lives in the Gates tab. */
function GateSummary({ id }: { id: string }) {
  const q = useGatesOverview(id);
  const reviews = (q.data?.gates ?? []).flatMap((g) => g.reviews.map((r) => ({ g, r })));
  const latest = [...reviews].sort((x, y) => dayjs(y.r.decided_at).diff(dayjs(x.r.decided_at)))[0];
  return (
    <SectionCard
      title="Gate history"
      actions={<AppLink to={`/transitions/${encodeURIComponent(id)}/gates`}>Gates tab</AppLink>}
    >
      {q.isPending ? (
        <LoadingState rows={1} />
      ) : q.error ? (
        <ErrorState error={q.error} />
      ) : !latest ? (
        <Body1>No gate reviews or decisions recorded yet.</Body1>
      ) : (
        <Body1>
          {plural(reviews.length, 'gate decision')} recorded. Latest:{' '}
          <strong>{latest.g.short}</strong> {latest.r.outcome} by{' '}
          {latest.r.decided_by?.name ?? 'Unknown'},{' '}
          {dayjs(latest.r.decided_at).format('D MMM YYYY')}.
        </Body1>
      )}
    </SectionCard>
  );
}

/** The custom fields of this transition (set in Admin): those marked "show on overview", editable by
 * whoever may edit the transition, plus read-only "Retired fields" that still hold a value. */
function CustomFieldsCard({ detail }: { detail: TransitionDetail }) {
  const s = useStyles();
  const fields = useIntakeFields({ includeInactive: true, includeHidden: true });
  const optionLabel = useOptionLabel();
  const users = useUsers();
  const update = useUpdateTransition(detail.id);
  const showError = useApiErrorToast();
  const { dispatchToast } = useToastController(TOASTER_ID);
  const [draft, setDraft] = useState<Record<string, FieldValue> | null>(null);

  const stored = (detail as { custom_fields?: Record<string, unknown> | null }).custom_fields ?? {};
  const custom = fields.filter((f) => !f.builtin);
  const current = custom.filter(
    (f) =>
      f.active &&
      f.show_on_overview &&
      fieldState(f, detail.project_type, detail.portfolio).applies,
  );
  const retired = custom.filter((f) => !f.active && stored[f.key] != null && stored[f.key] !== '');
  if (current.length === 0 && retired.length === 0) return null;

  const people = users.data ?? [];
  const valueText = (f: (typeof custom)[number]) =>
    displayValue(f, stored[f.key], (v) =>
      f.type === 'user'
        ? (people.find((u) => u.id === v)?.name ?? v)
        : optionLabel(f.option_list ?? '', v),
    );
  const canEdit = detail.access['edit_transition'] === null && current.length > 0;
  const why = detail.access['edit_transition'];

  const save = () => {
    if (!draft) return;
    // An emptied field is sent as null so the stored value is removed.
    const body = Object.fromEntries(current.map((f) => [f.key, toApiValue(f, draft[f.key])]));
    update.mutate(
      { custom_fields: body },
      {
        onSuccess: () => {
          setDraft(null);
          dispatchToast(
            <Toast>
              <ToastTitle>Details saved</ToastTitle>
            </Toast>,
            { intent: 'success' },
          );
        },
        onError: showError,
      },
    );
  };

  return (
    <SectionCard
      title="Additional details"
      actions={
        draft ? undefined : (
          <Button
            size="small"
            disabledFocusable={!canEdit}
            title={canEdit ? undefined : (why ?? undefined)}
            onClick={() =>
              setDraft(
                Object.fromEntries(
                  current.map((f) => [f.key, fromApiValue(f, stored[f.key] ?? emptyValue(f))]),
                ),
              )
            }
          >
            Edit
          </Button>
        )
      }
    >
      {draft ? (
        <>
          <div className={s.fieldGrid}>
            {current.map((f) => (
              <DynamicField
                key={f.key}
                field={f}
                users={people}
                value={draft[f.key]}
                onChange={(value) => setDraft({ ...draft, [f.key]: value })}
              />
            ))}
          </div>
          <div className={s.line} style={{ marginTop: tokens.spacingVerticalM }}>
            <Button appearance="primary" disabled={update.isPending} onClick={save}>
              Save
            </Button>
            <Button disabled={update.isPending} onClick={() => setDraft(null)}>
              Cancel
            </Button>
          </div>
        </>
      ) : (
        <div className={s.fieldGrid}>
          {current.map((f) => (
            <div key={f.key}>
              <Caption1>{f.label}</Caption1>
              <Body1 block>{valueText(f)}</Body1>
            </div>
          ))}
        </div>
      )}
      {retired.length > 0 && (
        <>
          <Subtitle2 as="h3" style={{ marginTop: tokens.spacingVerticalM }}>
            Retired fields
          </Subtitle2>
          <div className={s.fieldGrid}>
            {retired.map((f) => (
              <div key={f.key}>
                <Caption1>{f.label} (retired, read-only)</Caption1>
                <Body1 block>{valueText(f)}</Body1>
              </div>
            ))}
          </div>
        </>
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
          {detail.item_counts && (
            <Body1
              as="p"
              style={{ margin: `${tokens.spacingVerticalM} 0 ${tokens.spacingVerticalL}` }}
            >
              <strong>Items in scope:</strong>{' '}
              {itemCountsParts(detail.item_counts, detail.risk_tier).join(' · ')} ·{' '}
              <strong>{detail.item_counts.total} applicable</strong>
            </Body1>
          )}
        </>
      ) : (
        <EmptyState message="Lens readiness appears once the assessment is launched." />
      )}
      <div className={s.two}>
        <NeedsAttention id={detail.id} />
        <CustomFieldsCard detail={detail} />
        <RecentActivity id={detail.id} />
        <GateSummary id={detail.id} />
      </div>
    </>
  );
}

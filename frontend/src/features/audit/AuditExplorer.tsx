// Audit table + URL-driven filters, shared by the global Audit page and the workspace Activity tab.
import { Fragment, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router';
import dayjs from 'dayjs';
import {
  Body1,
  Button,
  Caption1,
  Field,
  Input,
  Select,
  makeStyles,
  mergeClasses,
  tokens,
} from '@fluentui/react-components';
import {
  ChevronDown20Regular,
  ChevronRight20Regular,
  ChevronDown16Regular,
  ChevronUp16Regular,
  Dismiss16Regular,
} from '@fluentui/react-icons';
import { ActorBadge } from '../../components/ActorBadge';
import { DataTable } from '../../components/DataTable';
import { SectionCard } from '../../components/SectionCard';
import { palette } from '../../theme/orionTheme';
import { EmptyState } from '../../components/EmptyState';
import { ErrorState } from '../../components/ErrorState';
import { LoadingState } from '../../components/LoadingState';
import type { ActorType } from '../../theme/tokens';
import { useOptions } from '../reference/options';
import { useTransitions } from '../transitions/api';
import { useUsers } from '../users/api';
import { useAudit, type AuditEventOut, type AuditQuery } from '../workspace/api';
import { AuditDiff } from './AuditDiff';

const PAGE_SIZE = 100;

const useStyles = makeStyles({
  root: { display: 'flex', flexDirection: 'column', gap: tokens.spacingVerticalL, minWidth: 0 },
  bar: {
    display: 'flex',
    flexWrap: 'wrap',
    alignItems: 'flex-end',
    gap: tokens.spacingHorizontalM,
  },
  field: { minWidth: '150px' },
  table: { borderCollapse: 'collapse', width: '100%', minWidth: '720px' },
  th: {
    textAlign: 'left',
    padding: tokens.spacingVerticalS,
    borderBottom: `1px solid ${tokens.colorNeutralStroke2}`,
    backgroundColor: tokens.colorNeutralBackground2,
    color: tokens.colorNeutralForeground2,
    fontWeight: tokens.fontWeightSemibold,
    whiteSpace: 'nowrap',
  },
  td: {
    verticalAlign: 'top',
    padding: tokens.spacingVerticalS,
    borderBottom: `1px solid ${tokens.colorNeutralStroke2}`,
  },
  row: { ':hover': { backgroundColor: tokens.colorNeutralBackground1Hover } },
  detail: {
    backgroundColor: tokens.colorNeutralBackground2,
    boxShadow: `inset 3px 0 0 ${palette.yellow}`,
  },
  time: { whiteSpace: 'nowrap' },
  actor: { display: 'flex', flexDirection: 'column', gap: '2px', alignItems: 'flex-start' },
  pager: {
    display: 'flex',
    gap: tokens.spacingHorizontalM,
    alignItems: 'center',
  },
  filterNote: {
    display: 'flex',
    gap: tokens.spacingHorizontalS,
    alignItems: 'center',
  },
});

/** Filters read from / written to the URL. entityId is applied client side (GET /audit has no such filter). */
function useAuditUrl() {
  const [params, setParams] = useSearchParams();
  const get = (k: string) => params.get(k) ?? '';
  const set = (patch: Record<string, string | undefined>, replace = false) =>
    setParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        for (const [k, v] of Object.entries(patch)) {
          if (v) next.set(k, v);
          else next.delete(k);
        }
        if (!('offset' in patch)) next.delete('offset');
        return next;
      },
      { replace },
    );
  return { get, set };
}

/** One audit row plus its expandable before/after diff. */
function AuditRow({ event, showTransition }: { event: AuditEventOut; showTransition: boolean }) {
  const s = useStyles();
  const [open, setOpen] = useState(false);
  const hasDiff = event.before !== null || event.after !== null;
  return (
    <Fragment>
      <tr className={s.row}>
        <td className={s.td}>
          <Button
            appearance="subtle"
            size="small"
            icon={open ? <ChevronDown20Regular /> : <ChevronRight20Regular />}
            aria-expanded={open}
            aria-label={open ? 'Hide changes' : 'Show changes'}
            disabled={!hasDiff}
            onClick={() => setOpen((o) => !o)}
          />
        </td>
        <td className={mergeClasses(s.td, s.time)}>{dayjs(event.at).format('D MMM YYYY HH:mm')}</td>
        <td className={s.td}>
          <div className={s.actor}>
            <Body1>{event.actor_name ?? event.actor_type}</Body1>
            <ActorBadge actor={event.actor_type as ActorType} />
          </div>
        </td>
        <td className={s.td}>{event.action}</td>
        <td className={s.td}>
          {event.entity} <Caption1>{event.entity_id}</Caption1>
          {showTransition && event.transition_id && (
            <div>
              <Caption1>
                {event.transition_id}
                {event.transition_name ? ` · ${event.transition_name}` : ''}
              </Caption1>
            </div>
          )}
        </td>
        <td className={s.td}>{event.note}</td>
      </tr>
      {open && (
        <tr className={s.detail}>
          <td className={s.td} />
          <td className={s.td} colSpan={5}>
            <AuditDiff event={event} />
          </td>
        </tr>
      )}
    </Fragment>
  );
}

/** Filterable audit table. `transitionId` pins the transition (Activity tab); omitted on the audit page. */
export function AuditExplorer({ transitionId }: { transitionId?: string }) {
  const s = useStyles();
  const { get, set } = useAuditUrl();
  const users = useUsers();
  const transitions = useTransitions({});
  const actorTypes = useOptions('actor_types');

  const entityId = get('entityId');
  const offset = Number(get('offset')) || 0;
  const query: AuditQuery = {
    transition_id: transitionId ?? (get('transition') || undefined),
    actor: get('actor') || undefined,
    actor_type: get('actor_type') || undefined,
    entity: get('entity') || undefined,
    from: get('from') || undefined,
    to: get('to') || undefined,
    // an entity-id filter is applied client side, so fetch the maximum page
    limit: entityId ? 500 : PAGE_SIZE,
    offset: entityId ? 0 : offset,
  };
  const [more, setMore] = useState(false);
  const audit = useAudit(query, transitionId);
  // Every entity name in the trail (of this transition) comes with each page, so the Entity filter
  // offers all of them; new record kinds such as config:<section> appear automatically.
  const entities = audit.data?.entities ?? [];

  const rows = useMemo(() => {
    const all = audit.data?.items ?? [];
    return entityId ? all.filter((e) => e.entity_id === entityId) : all;
  }, [audit.data, entityId]);
  const total = entityId ? rows.length : (audit.data?.total ?? 0);
  const dateError = !!query.from && !!query.to && query.from > query.to;

  const moreOpen = more || !!get('entity') || !!get('from') || !!get('to');

  return (
    <div className={s.root}>
      <SectionCard title="Filters">
        <div className={s.bar} role="search" aria-label="Audit filters">
          {!transitionId && (
            <Field label="Transition" className={s.field}>
              <Select
                value={get('transition')}
                onChange={(_, d) => set({ transition: d.value || undefined })}
              >
                <option value="">All</option>
                {(transitions.data ?? []).map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.id} {t.name}
                  </option>
                ))}
              </Select>
            </Field>
          )}
          <Field label="Actor type" className={s.field}>
            <Select
              value={get('actor_type')}
              onChange={(_, d) => set({ actor_type: d.value || undefined })}
            >
              <option value="">All</option>
              {actorTypes.map((a) => (
                <option key={a.value} value={a.value}>
                  {a.label}
                </option>
              ))}
            </Select>
          </Field>
          {!transitionId && (
            <Field label="Actor" className={s.field}>
              <Select
                value={get('actor')}
                onChange={(_, d) => set({ actor: d.value || undefined })}
              >
                <option value="">All</option>
                {(users.data ?? []).map((u) => (
                  <option key={u.id} value={u.id}>
                    {u.name}
                  </option>
                ))}
              </Select>
            </Field>
          )}
          <Button
            appearance="subtle"
            icon={moreOpen ? <ChevronUp16Regular /> : <ChevronDown16Regular />}
            aria-expanded={moreOpen}
            onClick={() => setMore(!moreOpen)}
          >
            More filters
          </Button>
        </div>
        {moreOpen && (
          <div className={s.bar}>
            <Field label="Entity" className={s.field}>
              <Select
                value={get('entity')}
                onChange={(_, d) => set({ entity: d.value || undefined })}
              >
                <option value="">All</option>
                {Array.from(new Set([...entities, get('entity')].filter(Boolean))).map((e) => (
                  <option key={e} value={e}>
                    {e}
                  </option>
                ))}
              </Select>
            </Field>
            {!transitionId && (
              <>
                <Field
                  label="From"
                  className={s.field}
                  validationState={dateError ? 'error' : 'none'}
                  validationMessage={dateError ? 'From is after To' : undefined}
                >
                  <Input
                    type="date"
                    value={get('from')}
                    onChange={(_, d) => set({ from: d.value || undefined })}
                  />
                </Field>
                <Field label="To" className={s.field}>
                  <Input
                    type="date"
                    value={get('to')}
                    onChange={(_, d) => set({ to: d.value || undefined })}
                  />
                </Field>
              </>
            )}
          </div>
        )}
      </SectionCard>
      {entityId && (
        <div className={s.filterNote}>
          <Caption1>
            Showing {get('entity') || 'all entities'} {entityId} only
          </Caption1>
          <Button
            size="small"
            appearance="subtle"
            icon={<Dismiss16Regular />}
            onClick={() => set({ entityId: undefined })}
          >
            Clear
          </Button>
        </div>
      )}

      {audit.isPending ? (
        <LoadingState rows={6} />
      ) : audit.error ? (
        <ErrorState error={audit.error} />
      ) : rows.length === 0 ? (
        <EmptyState message="No audit events match these filters." />
      ) : (
        <>
          <DataTable label="Audit events">
            <table className={s.table}>
              <thead>
                <tr>
                  <th className={s.th} aria-label="Expand" />
                  <th className={s.th}>Time</th>
                  <th className={s.th}>Actor</th>
                  <th className={s.th}>Action</th>
                  <th className={s.th}>Entity</th>
                  <th className={s.th}>Note</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((e) => (
                  <AuditRow key={e.id} event={e} showTransition={!transitionId} />
                ))}
              </tbody>
            </table>
          </DataTable>
          <div className={s.pager}>
            <Caption1>
              {entityId
                ? `${total} events`
                : `${Math.min(offset + 1, total)}-${Math.min(offset + PAGE_SIZE, total)} of ${total}`}
            </Caption1>
            {!entityId && (
              <>
                <Button
                  size="small"
                  disabled={offset === 0}
                  onClick={() =>
                    set({ offset: String(Math.max(0, offset - PAGE_SIZE)) || undefined })
                  }
                >
                  Previous
                </Button>
                <Button
                  size="small"
                  disabled={offset + PAGE_SIZE >= total}
                  onClick={() => set({ offset: String(offset + PAGE_SIZE) })}
                >
                  Next
                </Button>
              </>
            )}
          </div>
        </>
      )}
    </div>
  );
}

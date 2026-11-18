import {
  Badge,
  Button,
  Caption1,
  MessageBar,
  MessageBarBody,
  MessageBarTitle,
  Select,
  Table,
  TableBody,
  TableCell,
  TableHeader,
  TableHeaderCell,
  TableRow,
  Tooltip,
  mergeClasses,
  makeStyles,
  tokens,
} from '@fluentui/react-components';
import dayjs from 'dayjs';
import relativeTime from 'dayjs/plugin/relativeTime';
import { useEffect, useRef } from 'react';
import { useSearchParams } from 'react-router';
import { AppLink } from '../../components/AppLink';
import { EmptyState } from '../../components/EmptyState';
import { ErrorState } from '../../components/ErrorState';
import { LoadingState } from '../../components/LoadingState';
import { PageHeader } from '../../components/PageHeader';
import { SectionCard } from '../../components/SectionCard';
import { useTransitions } from '../transitions/api';
import { useDraft, useDrafts, useReminderStatus } from './api';
import { RunRemindersControl } from './RunReminders';
import { DraftEditor } from './DraftEditor';
import { SourceLabel } from './SourceLabel';

dayjs.extend(relativeTime);

const useStyles = makeStyles({
  page: { display: 'flex', flexDirection: 'column', gap: tokens.spacingVerticalL },
  filters: {
    display: 'flex',
    gap: tokens.spacingHorizontalM,
    flexWrap: 'wrap',
    alignItems: 'center',
  },
  row: { cursor: 'pointer' },
  rowSelected: { backgroundColor: tokens.colorBrandBackground2 },
  subject: { fontWeight: tokens.fontWeightSemibold },
  scroll: { overflowX: 'auto' },
  table: { minWidth: '1040px' },
  cKind: { width: '76px' },
  cTransition: { width: '150px' },
  cTo: { width: '190px', overflowWrap: 'anywhere' },
  cSubject: { minWidth: '260px', overflowWrap: 'anywhere' },
  cSource: { width: '150px', overflow: 'hidden' },
  cStatus: { width: '80px' },
  cCreated: { width: '110px' },
});

function DraftDetail({ draftId, onClose }: { draftId: number; onClose: () => void }) {
  const q = useDraft(draftId);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    // Bring the detail panel into view when a row is opened (the queue can be long).
    ref.current?.scrollIntoView?.({ block: 'nearest', behavior: 'smooth' });
  }, [draftId]);
  return (
    <div ref={ref}>
      <SectionCard
        title={`Draft #${draftId}`}
        actions={
          <Button appearance="subtle" onClick={onClose}>
            Close
          </Button>
        }
      >
        {q.isLoading && <LoadingState rows={5} />}
        {q.isError && <ErrorState error={q.error} />}
        {q.data && <DraftEditor draft={q.data} onSent={onClose} onDiscarded={onClose} />}
      </SectionCard>
    </div>
  );
}

/** Orion drafts (FR-071, spec 8.11): queue of messages for a person to edit and send (BR-050). */
export function DraftsPage() {
  const s = useStyles();
  const [params, setParams] = useSearchParams();
  const status = params.get('status') ?? 'Draft';
  const kind = params.get('kind') ?? '';
  const transition = params.get('transition') ?? '';
  const source = params.get('source') ?? '';
  const draftParam = params.get('draft');
  const draftId = draftParam && /^\d+$/.test(draftParam) ? Number(draftParam) : null;
  const all = useDrafts({});
  const transitions = useTransitions({});
  const reminders = useReminderStatus();

  const isOrion = (label: string) => label.toLowerCase().startsWith('orion');
  const kinds = Array.from(new Set((all.data ?? []).map((d) => d.kind))).sort();
  const rows = (all.data ?? []).filter(
    (d) =>
      (status === 'all' || d.status === status) &&
      (!kind || d.kind === kind) &&
      (!transition || d.transition_id === transition) &&
      (!source || (source === 'orion') === isOrion(d.source_label)),
  );
  const focusTransition =
    transition || (all.data ?? []).find((d) => d.id === draftId)?.transition_id || '';
  const autonomous = reminders.data?.autonomous_transitions ?? [];
  const focusName =
    transitions.data?.find((x) => x.id === focusTransition)?.name ?? focusTransition;

  const setParam = (key: string, value: string | null) => {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    setParams(next, { replace: true });
  };

  return (
    <div className={s.page}>
      <PageHeader
        title="Orion drafts"
        subtitle="Messages Orion or a workflow rule drafted for a person to edit and send."
      />

      <SectionCard title="Reminder engine">
        <RunRemindersControl />
      </SectionCard>

      {focusTransition && autonomous.includes(focusTransition) ? (
        <MessageBar intent="warning" layout="multiline">
          <MessageBarBody>
            <MessageBarTitle>Autonomous mode is on for {focusName}</MessageBarTitle>
            Workflow rules may send chasers and reminders for this transition on their own and log
            them in the Outbox. Orion still never changes a status, approval or gate decision.
          </MessageBarBody>
        </MessageBar>
      ) : (
        <MessageBar intent="info" layout="multiline">
          <MessageBarBody>
            <MessageBarTitle>
              Assistive mode{focusTransition ? ` for ${focusName}` : ''}
            </MessageBarTitle>
            Orion drafts; nothing is sent until a person clicks Send. In autonomous mode (switched
            on per transition by the OR focal) workflow rules may send reminders on their own, but
            Orion still never changes a status, approval or gate decision.
            {!focusTransition && autonomous.length > 0
              ? ` Autonomous now: ${autonomous.length} transition${autonomous.length > 1 ? 's' : ''}.`
              : ''}
          </MessageBarBody>
        </MessageBar>
      )}

      {draftId !== null && (
        <DraftDetail draftId={draftId} onClose={() => setParam('draft', null)} />
      )}

      <div className={s.filters}>
        <Select
          aria-label="Status"
          value={status}
          onChange={(_, d) => setParam('status', d.value || 'all')}
        >
          <option value="Draft">Draft</option>
          <option value="Sent">Sent</option>
          <option value="Discarded">Discarded</option>
          <option value="all">All statuses</option>
        </Select>
        <Select aria-label="Kind" value={kind} onChange={(_, d) => setParam('kind', d.value)}>
          <option value="">All kinds</option>
          {kinds.map((k) => (
            <option key={k} value={k}>
              {k}
            </option>
          ))}
        </Select>
        <Select
          aria-label="Transition"
          value={transition}
          onChange={(_, d) => setParam('transition', d.value)}
        >
          <option value="">All transitions</option>
          {(transitions.data ?? []).map((x) => (
            <option key={x.id} value={x.id}>
              {x.id} {x.name}
            </option>
          ))}
        </Select>
        <Select aria-label="Source" value={source} onChange={(_, d) => setParam('source', d.value)}>
          <option value="">All sources</option>
          <option value="orion">Orion agent</option>
          <option value="rule">Workflow rule</option>
        </Select>
      </div>

      {all.isLoading && <LoadingState rows={6} />}
      {all.isError && <ErrorState error={all.error} />}
      {all.data && rows.length === 0 && (
        <EmptyState message="No drafts match. Drafts appear when Orion or a workflow rule prepares a message." />
      )}
      {all.data && rows.length > 0 && (
        <div className={s.scroll}>
          <Table aria-label="Drafts" size="small" className={s.table}>
            <TableHeader>
              <TableRow>
                <TableHeaderCell className={s.cKind}>Kind</TableHeaderCell>
                <TableHeaderCell className={s.cTransition}>Transition</TableHeaderCell>
                <TableHeaderCell className={s.cTo}>Recipients</TableHeaderCell>
                <TableHeaderCell className={s.cSubject}>Subject</TableHeaderCell>
                <TableHeaderCell className={s.cSource}>Source</TableHeaderCell>
                <TableHeaderCell className={s.cStatus}>Status</TableHeaderCell>
                <TableHeaderCell className={s.cCreated}>Created</TableHeaderCell>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((d) => (
                <TableRow
                  key={d.id}
                  className={mergeClasses(s.row, d.id === draftId && s.rowSelected)}
                  tabIndex={0}
                  onClick={() => setParam('draft', String(d.id))}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      setParam('draft', String(d.id)); // keeps the current filters in the URL
                    }
                  }}
                >
                  <TableCell className={s.cKind}>{d.kind}</TableCell>
                  <TableCell className={s.cTransition}>
                    {d.transition_id ? (
                      <span onClick={(e) => e.stopPropagation()}>
                        <AppLink to={`/transitions/${d.transition_id}/overview`}>
                          {d.transition_name ?? d.transition_id}
                        </AppLink>
                      </span>
                    ) : (
                      '–'
                    )}
                  </TableCell>
                  <TableCell className={s.cTo}>
                    <Caption1>{d.to.join(', ')}</Caption1>
                  </TableCell>
                  <TableCell className={s.cSubject}>
                    <span className={s.subject}>{d.subject}</span>
                  </TableCell>
                  <TableCell className={s.cSource}>
                    <SourceLabel label={d.source_label} />
                  </TableCell>
                  <TableCell className={s.cStatus}>
                    <Badge
                      appearance="outline"
                      color={
                        d.status === 'Sent' ? 'success' : d.status === 'Draft' ? 'brand' : 'subtle'
                      }
                    >
                      {d.status}
                    </Badge>
                  </TableCell>
                  <TableCell className={s.cCreated}>
                    <Tooltip
                      content={dayjs(d.created_at).format('D MMM YYYY HH:mm')}
                      relationship="label"
                    >
                      <span>{dayjs(d.created_at).fromNow()}</span>
                    </Tooltip>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}

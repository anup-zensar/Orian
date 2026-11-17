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
  makeStyles,
  tokens,
} from '@fluentui/react-components';
import dayjs from 'dayjs';
import relativeTime from 'dayjs/plugin/relativeTime';
import { useNavigate, useSearchParams } from 'react-router';
import { AppLink } from '../../components/AppLink';
import { EmptyState } from '../../components/EmptyState';
import { ErrorState } from '../../components/ErrorState';
import { LoadingState } from '../../components/LoadingState';
import { PageHeader } from '../../components/PageHeader';
import { SectionCard } from '../../components/SectionCard';
import { useDraft, useDrafts } from './api';
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
});

const KINDS = ['Chaser', 'Approval request', 'Reminder', 'Escalation', 'Leadership update'];

function DraftDetail({ draftId, onClose }: { draftId: number; onClose: () => void }) {
  const q = useDraft(draftId);
  return (
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
  );
}

/** Orion drafts (FR-071, spec 8.11): queue of messages for a person to edit and send (BR-050). */
export function DraftsPage() {
  const s = useStyles();
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const status = params.get('status') ?? 'Draft';
  const kind = params.get('kind') ?? '';
  const draftParam = params.get('draft');
  const draftId = draftParam && /^\d+$/.test(draftParam) ? Number(draftParam) : null;
  const list = useDrafts({ status: status || undefined, kind: kind || undefined });

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
        actions={
          <Tooltip content="Reminder engine arrives in M8" relationship="description">
            <Button disabledFocusable>Run reminder engine now</Button>
          </Tooltip>
        }
      />

      <MessageBar intent="info">
        <MessageBarBody>
          <MessageBarTitle>Assistive mode</MessageBarTitle>
          Orion drafts; nothing is sent until a person clicks Send. In autonomous mode (switched on
          per transition by the OR focal) workflow rules may send reminders on their own, but Orion
          still never changes a status, approval or gate decision.
        </MessageBarBody>
      </MessageBar>

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
          {KINDS.map((k) => (
            <option key={k} value={k}>
              {k}
            </option>
          ))}
        </Select>
      </div>

      {list.isLoading && <LoadingState rows={6} />}
      {list.isError && <ErrorState error={list.error} />}
      {list.data && list.data.length === 0 && (
        <EmptyState message="No drafts match. Drafts appear when Orion or a workflow rule prepares a message." />
      )}
      {list.data && list.data.length > 0 && (
        <Table aria-label="Drafts" size="small">
          <TableHeader>
            <TableRow>
              <TableHeaderCell>Kind</TableHeaderCell>
              <TableHeaderCell>Transition</TableHeaderCell>
              <TableHeaderCell>Recipients</TableHeaderCell>
              <TableHeaderCell>Subject</TableHeaderCell>
              <TableHeaderCell>Source</TableHeaderCell>
              <TableHeaderCell>Status</TableHeaderCell>
              <TableHeaderCell>Created</TableHeaderCell>
            </TableRow>
          </TableHeader>
          <TableBody>
            {list.data.map((d) => (
              <TableRow
                key={d.id}
                className={`${s.row} ${d.id === draftId ? s.rowSelected : ''}`}
                tabIndex={0}
                onClick={() => setParam('draft', String(d.id))}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') navigate(`/drafts?draft=${d.id}`);
                }}
              >
                <TableCell>{d.kind}</TableCell>
                <TableCell>
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
                <TableCell>
                  <Caption1>{d.to.join(', ')}</Caption1>
                </TableCell>
                <TableCell>
                  <span className={s.subject}>{d.subject}</span>
                </TableCell>
                <TableCell>
                  <SourceLabel label={d.source_label} />
                </TableCell>
                <TableCell>
                  <Badge
                    appearance="outline"
                    color={
                      d.status === 'Sent' ? 'success' : d.status === 'Draft' ? 'brand' : 'subtle'
                    }
                  >
                    {d.status}
                  </Badge>
                </TableCell>
                <TableCell>
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
      )}
    </div>
  );
}

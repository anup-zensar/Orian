// Dashboard sections (spec 8.1): My work, leadership portfolio tiles, recent activity.
import { useState } from 'react';
import dayjs from 'dayjs';
import relativeTime from 'dayjs/plugin/relativeTime';
import {
  Button,
  Caption1,
  Table,
  TableBody,
  TableCell,
  TableHeader,
  TableHeaderCell,
  TableRow,
  makeStyles,
  tokens,
} from '@fluentui/react-components';
import {
  ClipboardTask16Regular,
  DocumentCheckmark16Regular,
  Flash16Regular,
} from '@fluentui/react-icons';
import type { AuditEvent, PortfolioTile, WorkItem } from '../../api/types';
import { ActorBadge } from '../../components/ActorBadge';
import { AppLink } from '../../components/AppLink';
import { EmptyState } from '../../components/EmptyState';
import { RagChip } from '../../components/RagChip';
import { SectionCard } from '../../components/SectionCard';
import { plural } from '../../lib/format';
import type { ActorType } from '../../theme/tokens';

dayjs.extend(relativeTime);

const useStyles = makeStyles({
  titleCell: { minWidth: '220px', overflowWrap: 'anywhere', whiteSpace: 'normal' },
  transitionCell: { minWidth: '140px', overflowWrap: 'anywhere' },
  kind: { display: 'inline-flex', alignItems: 'center', gap: tokens.spacingHorizontalXS },
  tiles: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))',
    gap: tokens.spacingHorizontalM,
  },
  tile: {
    display: 'flex',
    flexDirection: 'column',
    gap: tokens.spacingVerticalS,
    padding: tokens.spacingVerticalM,
    border: `1px solid ${tokens.colorNeutralStroke2}`,
    borderRadius: tokens.borderRadiusMedium,
  },
  chips: { display: 'flex', flexWrap: 'wrap', gap: tokens.spacingHorizontalXS },
  stats: { display: 'flex', flexDirection: 'column', gap: '2px' },
  list: {
    listStyle: 'none',
    margin: 0,
    padding: 0,
    display: 'flex',
    flexDirection: 'column',
    gap: tokens.spacingVerticalM,
  },
  event: { display: 'flex', flexDirection: 'column', gap: tokens.spacingVerticalXXS },
  line: { display: 'flex', alignItems: 'center', gap: tokens.spacingHorizontalS, flexWrap: 'wrap' },
});

const KIND = {
  item: { Icon: ClipboardTask16Regular, label: 'Item' },
  action: { Icon: Flash16Regular, label: 'Action' },
  approval: { Icon: DocumentCheckmark16Regular, label: 'Approval' },
} as const;

const MY_WORK_VISIBLE = 25;

/** "My work": items, actions and approvals assigned to me, most urgent first. */
export function MyWorkCard({ rows, total }: { rows: WorkItem[]; total: number }) {
  const s = useStyles();
  const [showAll, setShowAll] = useState(false);
  const shown = showAll ? rows : rows.slice(0, MY_WORK_VISIBLE);
  const counts = (['item', 'action', 'approval'] as const)
    .map((k) => [k, rows.filter((r) => r.kind === k).length] as const)
    .filter(([, n]) => n > 0)
    .map(([k, n]) => plural(n, k));
  return (
    <SectionCard title="My work" id="my-work">
      {rows.length === 0 ? (
        <EmptyState message="Nothing is assigned to you right now. Browse transitions to find where help is needed." />
      ) : (
        <>
          <div style={{ overflowX: 'auto' }}>
            <Table aria-label="My work" size="small" style={{ minWidth: 760 }}>
              <TableHeader>
                <TableRow>
                  <TableHeaderCell>Type</TableHeaderCell>
                  <TableHeaderCell>Title</TableHeaderCell>
                  <TableHeaderCell>Transition</TableHeaderCell>
                  <TableHeaderCell>Status</TableHeaderCell>
                  <TableHeaderCell>Due</TableHeaderCell>
                  <TableHeaderCell>
                    <span style={{ position: 'absolute', left: -9999 }}>Open</span>
                  </TableHeaderCell>
                </TableRow>
              </TableHeader>
              <TableBody>
                {shown.map((r) => {
                  const k = KIND[r.kind as keyof typeof KIND] ?? KIND.item;
                  return (
                    <TableRow key={`${r.kind}-${r.transition_id}-${r.id}`}>
                      <TableCell>
                        <span className={s.kind}>
                          <k.Icon aria-hidden />
                          {k.label}
                        </span>
                      </TableCell>
                      <TableCell className={s.titleCell}>
                        <strong>{r.id}</strong> {r.title}
                      </TableCell>
                      <TableCell className={s.transitionCell}>
                        <AppLink to={`/transitions/${r.transition_id}/overview`}>
                          {r.transition_name}
                        </AppLink>
                      </TableCell>
                      <TableCell>{r.status}</TableCell>
                      <TableCell>{r.due_label}</TableCell>
                      <TableCell>
                        <AppLink to={r.link} ariaLabel={`Open ${r.id} ${r.title}`}>
                          Open
                        </AppLink>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </div>
          <Caption1 role="status">
            {plural(total, 'work item')}
            {counts.length > 0 ? `: ${counts.join(', ')}` : ''}
            {rows.length < total ? ` (first ${rows.length} listed)` : ''}
          </Caption1>
          {rows.length > MY_WORK_VISIBLE && (
            <Button appearance="subtle" onClick={() => setShowAll((v) => !v)}>
              {showAll ? `Show first ${MY_WORK_VISIBLE}` : `Show all (${rows.length})`}
            </Button>
          )}
        </>
      )}
    </SectionCard>
  );
}

/** LEADERSHIP: one summary tile per portfolio instead of "My work". */
export function PortfolioTiles({ tiles }: { tiles: PortfolioTile[] }) {
  const s = useStyles();
  return (
    <SectionCard title="Portfolio summary">
      {tiles.length === 0 ? (
        <EmptyState message="No portfolio data yet." />
      ) : (
        <div className={s.tiles}>
          {tiles.map((t) => (
            <div key={t.portfolio} className={s.tile}>
              <AppLink to={`/control-tower?portfolio=${encodeURIComponent(t.portfolio)}`}>
                <strong>{t.portfolio}</strong>
              </AppLink>
              <span>{plural(t.transitions, 'transition')}</span>
              <div className={s.chips}>
                <RagChip rag="Red" label={`${t.red} Red`} />
                <RagChip rag="Amber" label={`${t.amber} Amber`} />
                <RagChip rag="Green" label={`${t.green} Green`} />
                {t.grey > 0 && <RagChip rag="Grey" label={`${t.grey} Not started`} />}
              </div>
              <div className={s.stats}>
                <Caption1>
                  Average readiness:{' '}
                  {t.average_readiness === null ? 'n/a' : `${t.average_readiness}%`}
                </Caption1>
                <Caption1>Decisions in 14 days: {t.decisions_14d}</Caption1>
                <Caption1>Critical gaps: {t.critical_gaps}</Caption1>
              </div>
            </div>
          ))}
        </div>
      )}
    </SectionCard>
  );
}

/** Last audit events in my transitions. Times are relative to the server's "today" (A-15). */
export function RecentActivityCard({ events, today }: { events: AuditEvent[]; today: string }) {
  const s = useStyles();
  // Server "today" + the browser's time of day, so a demo-clock override still reads sensibly.
  const now = dayjs(today).hour(dayjs().hour()).minute(dayjs().minute());
  return (
    <SectionCard title="Recent activity">
      {events.length === 0 ? (
        <EmptyState message="No activity yet in your transitions." />
      ) : (
        <ul className={s.list}>
          {events.map((e) => (
            <li key={e.id} className={s.event}>
              <div className={s.line}>
                {e.actor_name && e.actor_name !== e.actor_type && <strong>{e.actor_name}</strong>}
                <ActorBadge actor={e.actor_type as ActorType} />
                <Caption1 title={dayjs(e.at).format('D MMM YYYY HH:mm')}>
                  {dayjs(e.at).from(now)}
                </Caption1>
              </div>
              <span>
                {e.action} {e.entity} {e.entity_id}
              </span>
              {e.transition_id && (
                <Caption1>
                  <AppLink to={`/transitions/${e.transition_id}/overview`}>
                    {e.transition_name ?? e.transition_id}
                  </AppLink>
                </Caption1>
              )}
            </li>
          ))}
        </ul>
      )}
    </SectionCard>
  );
}

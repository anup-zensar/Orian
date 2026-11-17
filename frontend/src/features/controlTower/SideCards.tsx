// Escalation queue, decision calendar and operating rhythm cards (spec 8.2).
import dayjs from 'dayjs';
import {
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
import type { CalendarEntry, Escalation, OperatingRhythmRow } from '../../api/types';
import { AppLink } from '../../components/AppLink';
import { RagChip } from '../../components/RagChip';
import { SectionCard } from '../../components/SectionCard';
import { daysLabel, formatDate, plural, toRag } from '../../lib/format';
import { ragColors } from '../../theme/tokens';

const useStyles = makeStyles({
  list: {
    listStyle: 'none',
    margin: 0,
    padding: 0,
    display: 'flex',
    flexDirection: 'column',
    gap: tokens.spacingVerticalM,
  },
  item: {
    display: 'flex',
    flexDirection: 'column',
    gap: tokens.spacingVerticalXXS,
    paddingBottom: tokens.spacingVerticalM,
    borderBottom: `1px solid ${tokens.colorNeutralStroke2}`,
  },
  line: { display: 'flex', alignItems: 'center', gap: tokens.spacingHorizontalS, flexWrap: 'wrap' },
  blocker: { color: ragColors.Red.foreground },
  week: {
    fontWeight: tokens.fontWeightSemibold,
    margin: `${tokens.spacingVerticalS} 0 ${tokens.spacingVerticalXS}`,
  },
  calRow: {
    display: 'grid',
    gridTemplateColumns: '84px 1fr',
    gap: tokens.spacingHorizontalS,
    alignItems: 'start',
  },
  overdue: { color: ragColors.Red.foreground },
});

export function EscalationCard({ rows }: { rows: Escalation[] }) {
  const s = useStyles();
  return (
    <SectionCard title="Escalation queue">
      {rows.length === 0 ? (
        <Caption1>Nothing to escalate: no Red transitions or blockers in this view.</Caption1>
      ) : (
        <ul className={s.list}>
          {rows.map((e) => (
            <li key={e.transition_id} className={s.item}>
              <div className={s.line}>
                <RagChip rag={toRag(e.rag)} />
                <AppLink to={`/transitions/${e.transition_id}/overview`}>
                  {e.transition_name}
                </AppLink>
                <Caption1>
                  {e.portfolio} · {e.current_gate_short}
                </Caption1>
              </div>
              <span>{e.reason}</span>
              {e.blocker_note && (
                <Caption1 className={s.blocker}>Blocker: {e.blocker_note}</Caption1>
              )}
              <Caption1>
                Owner: {e.owner.name} · Decision {daysLabel(e.days_to_next_decision)}
              </Caption1>
            </li>
          ))}
        </ul>
      )}
    </SectionCard>
  );
}

export function CalendarCard({ rows, today }: { rows: CalendarEntry[]; today: string }) {
  const s = useStyles();
  // Group relative to the server's "today" (demo clock override, A-15), not the browser clock.
  const groups = new Map<number, { label: string; rows: CalendarEntry[] }>();
  for (const r of [...rows].sort((a, b) => a.days - b.days)) {
    const week = r.days < 0 ? -1 : Math.floor(r.days / 7);
    const label =
      week === -1
        ? 'Overdue'
        : week === 0
          ? 'This week'
          : `Week of ${dayjs(today)
              .add(week * 7, 'day')
              .format('D MMM')}`;
    const g = groups.get(week) ?? { label, rows: [] };
    g.rows.push(r);
    groups.set(week, g);
  }
  return (
    <SectionCard title="Decision calendar (next 45 days)">
      {rows.length === 0 ? (
        <Caption1>No decisions due in the next 45 days.</Caption1>
      ) : (
        [...groups.entries()].map(([key, g]) => (
          <div key={key}>
            <div className={s.week}>{g.label}</div>
            <ul className={s.list}>
              {g.rows.map((r) => (
                <li key={`${r.transition_id}-${r.gate}`} className={s.calRow}>
                  <div>
                    <div>{formatDate(r.date)}</div>
                    <Caption1 className={r.days < 0 ? s.overdue : undefined}>
                      {daysLabel(r.days)}
                    </Caption1>
                  </div>
                  <div className={s.line}>
                    <RagChip rag={toRag(r.rag)} />
                    <span>{r.decision}</span>
                    <AppLink to={`/transitions/${r.transition_id}/overview`}>
                      {r.transition_name}
                    </AppLink>
                    <Caption1>{r.or_focal.name}</Caption1>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        ))
      )}
      <Caption1>{plural(rows.length, 'decision')} listed</Caption1>
    </SectionCard>
  );
}

export function OperatingRhythmCard({ rows }: { rows: OperatingRhythmRow[] }) {
  return (
    <SectionCard title="Operating rhythm">
      <div style={{ overflowX: 'auto' }}>
        <Table aria-label="Operating rhythm" size="small">
          <TableHeader>
            <TableRow>
              <TableHeaderCell>Forum</TableHeaderCell>
              <TableHeaderCell>Frequency</TableHeaderCell>
              <TableHeaderCell>Input</TableHeaderCell>
              <TableHeaderCell>Output</TableHeaderCell>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((r) => (
              <TableRow key={r.forum}>
                <TableCell>{r.forum}</TableCell>
                <TableCell>{r.frequency}</TableCell>
                <TableCell>{r.input}</TableCell>
                <TableCell>{r.output}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </SectionCard>
  );
}

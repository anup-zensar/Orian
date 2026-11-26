import {
  Accordion,
  AccordionHeader,
  AccordionItem,
  AccordionPanel,
  Badge,
  Button,
  Caption1,
  MessageBar,
  MessageBarBody,
  Select,
  Subtitle2,
  Table,
  TableBody,
  TableCell,
  TableHeader,
  TableHeaderCell,
  TableRow,
  makeStyles,
  mergeClasses,
  tokens,
} from '@fluentui/react-components';
import { useEffect, useRef } from 'react';
import dayjs from 'dayjs';
import { useSearchParams } from 'react-router';
import { DataTable } from '../../components/DataTable';
import { Toolbar } from '../../components/layout/Toolbar';
import { EmptyState } from '../../components/EmptyState';
import { ErrorState } from '../../components/ErrorState';
import { LoadingState } from '../../components/LoadingState';
import { PageHeader } from '../../components/PageHeader';
import { SectionCard } from '../../components/SectionCard';
import { EmailPreview } from '../drafts/DraftEditor';
import { useOutbox, type OutboxMessage } from './api';
import { AdaptiveCardPreview } from './AdaptiveCardPreview';

const useStyles = makeStyles({
  page: { display: 'flex', flexDirection: 'column', gap: tokens.spacingVerticalL },
  row: { cursor: 'pointer' },
  rowSelected: { backgroundColor: tokens.colorBrandBackground2 },
  meta: { display: 'flex', flexDirection: 'column', gap: '2px' },
  json: {
    margin: 0,
    padding: tokens.spacingVerticalS,
    overflow: 'auto',
    maxHeight: '320px',
    fontFamily: tokens.fontFamilyMonospace,
    fontSize: tokens.fontSizeBase200,
    backgroundColor: tokens.colorNeutralBackground2,
  },
});

function MessageDetail({ msg, onClose }: { msg: OutboxMessage; onClose: () => void }) {
  const s = useStyles();
  return (
    <SectionCard
      title={msg.subject}
      actions={
        <Button appearance="subtle" onClick={onClose}>
          Close
        </Button>
      }
    >
      <div className={s.meta}>
        <Caption1>
          {msg.channel} · from {msg.from_address} · {dayjs(msg.sent_at).format('D MMM YYYY HH:mm')}{' '}
          · {msg.mode}
        </Caption1>
        <Caption1>To: {msg.to.join(', ') || '–'}</Caption1>
        {msg.cc.length > 0 && <Caption1>Cc: {msg.cc.join(', ')}</Caption1>}
      </div>
      {msg.channel === 'Email' && (
        <EmailPreview html={msg.body_html} title={`Email ${msg.subject}`} height={360} />
      )}
      {msg.channel === 'Teams' &&
        (msg.adaptive_card_json ? (
          <>
            <AdaptiveCardPreview card={msg.adaptive_card_json} />
            <Accordion collapsible>
              <AccordionItem value="json">
                <AccordionHeader>Raw Adaptive Card JSON</AccordionHeader>
                <AccordionPanel>
                  <pre className={s.json}>{JSON.stringify(msg.adaptive_card_json, null, 2)}</pre>
                </AccordionPanel>
              </AccordionItem>
            </Accordion>
          </>
        ) : (
          <EmptyState message="This Teams message has no card payload." />
        ))}
    </SectionCard>
  );
}

/** Outbox (FR-072, spec 8.13): everything the mock Mail and Teams services "sent". */
export function OutboxPage() {
  const s = useStyles();
  const [params, setParams] = useSearchParams();
  const channel = params.get('channel') ?? '';
  const transitionId = params.get('transition') ?? '';
  const selected = Number(params.get('message')) || null;
  const q = useOutbox({ channel: channel || undefined, transition_id: transitionId || undefined });

  const setParam = (key: string, value: string | null) => {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    setParams(next, { replace: true });
  };
  const current = q.data?.find((m) => m.id === selected);
  const detailRef = useRef<HTMLDivElement>(null);
  const currentId = current?.id;
  useEffect(() => {
    if (currentId !== undefined) detailRef.current?.scrollIntoView?.({ block: 'start' });
  }, [currentId]);

  return (
    <div className={s.page}>
      <PageHeader title="Outbox" subtitle="Sent emails and Teams cards (mock)." />
      <MessageBar intent="warning" layout="multiline">
        <MessageBarBody>
          Mock mode – in production this calls Microsoft Graph POST /users/{'{orion-mailbox}'}
          /sendMail and the Orion Teams bot.
        </MessageBarBody>
      </MessageBar>

      {current && (
        <div ref={detailRef}>
          <MessageDetail msg={current} onClose={() => setParam('message', null)} />
        </div>
      )}

      <Toolbar>
        <Select
          aria-label="Channel"
          value={channel}
          onChange={(_, d) => setParam('channel', d.value)}
        >
          <option value="">All channels</option>
          <option value="Email">Email</option>
          <option value="Teams">Teams</option>
        </Select>
        {transitionId && (
          <Button onClick={() => setParam('transition', null)}>
            Clear transition filter ({transitionId})
          </Button>
        )}
      </Toolbar>

      {q.isLoading && <LoadingState rows={6} />}
      {q.isError && <ErrorState error={q.error} />}
      {q.data && q.data.length === 0 && (
        <EmptyState message="Nothing has been sent yet. Messages appear here after a person sends a draft or a workflow notifies someone." />
      )}
      {q.data && q.data.length > 0 && (
        <>
          <Subtitle2 as="h2">{q.data.length} messages</Subtitle2>
          <DataTable label="Outbox list">
            <Table aria-label="Outbox messages" size="small">
              <TableHeader>
                <TableRow>
                  <TableHeaderCell>Channel</TableHeaderCell>
                  <TableHeaderCell>From</TableHeaderCell>
                  <TableHeaderCell>To / Cc</TableHeaderCell>
                  <TableHeaderCell>Subject</TableHeaderCell>
                  <TableHeaderCell>Sent</TableHeaderCell>
                </TableRow>
              </TableHeader>
              <TableBody>
                {q.data.map((m) => (
                  <TableRow
                    key={m.id}
                    className={mergeClasses(s.row, m.id === selected && s.rowSelected)}
                    tabIndex={0}
                    onClick={() => setParam('message', String(m.id))}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') setParam('message', String(m.id));
                    }}
                  >
                    <TableCell>
                      <Badge
                        appearance="outline"
                        color={m.channel === 'Teams' ? 'informative' : 'brand'}
                      >
                        {m.channel}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <Caption1>{m.from_address}</Caption1>
                    </TableCell>
                    <TableCell>
                      <Caption1>
                        {m.to.join(', ')}
                        {m.cc.length > 0 ? ` (cc ${m.cc.join(', ')})` : ''}
                      </Caption1>
                    </TableCell>
                    <TableCell>
                      <strong>{m.subject}</strong>
                    </TableCell>
                    <TableCell style={{ whiteSpace: 'nowrap' }}>
                      {dayjs(m.sent_at).format('D MMM HH:mm')}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </DataTable>
        </>
      )}
    </div>
  );
}

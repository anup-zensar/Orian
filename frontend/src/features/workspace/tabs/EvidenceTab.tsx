import { useState } from 'react';
import {
  Badge,
  Button,
  Field,
  Select,
  Table,
  TableBody,
  TableCell,
  TableHeader,
  TableHeaderCell,
  TableRow,
} from '@fluentui/react-components';
import { download } from '../../../api/client';
import { EmptyState } from '../../../components/EmptyState';
import { ErrorState } from '../../../components/ErrorState';
import { LoadingState } from '../../../components/LoadingState';
import { PageHeader } from '../../../components/PageHeader';
import { useApiErrorToast } from '../../../hooks/useApiErrorToast';
import { formatDate } from '../../../lib/format';
import { useEvidence, useItems, type Evidence } from '../../records/api';
import { GuardedButton } from '../../records/common';
import { useRecordStyles, usePerm, useUrlParams } from '../../records/hooks';
import { AddEvidenceDialog, ReviewEvidenceDialog } from '../../records/EvidenceDialogs';
import type { TabProps } from '../types';

const STATUS_COLOR = { Submitted: 'informative', Accepted: 'success', Rejected: 'danger' } as const;
const TYPES = ['Document', 'Link', 'Email sign-off', 'Recording', 'Generated'];
const STATUSES = ['Submitted', 'Accepted', 'Rejected'];

function isHttp(url: string): boolean {
  return /^https?:\/\//i.test(url);
}

/** Evidence tab (FR-033, spec 8.7 d): filterable list, add dialog, accept / reject, download. */
export function EvidenceTab({ transitionId }: TabProps) {
  const s = useRecordStyles();
  const { params, set } = useUrlParams();
  const showError = useApiErrorToast();
  const filters = {
    item: params.get('item') ?? undefined,
    type: params.get('type') ?? undefined,
    status: params.get('status') ?? undefined,
  };
  const list = useEvidence(transitionId, filters);
  const items = useItems(transitionId, { all_gates: 'true', applicability: 'all' });
  const manage = usePerm('manage_evidence');
  const addOpen = params.get('new') === '1';
  const [review, setReview] = useState<{ ev: Evidence; decision: 'Accept' | 'Reject' } | null>(
    null,
  );

  const closeAdd = () => set({ new: undefined });

  return (
    <div className={s.stack}>
      <PageHeader
        title="Evidence"
        subtitle="Files, links and sign-offs that back up checklist items."
        actions={
          <GuardedButton
            appearance="primary"
            reason={manage.reason}
            onClick={() => set({ new: '1' }, false)}
          >
            Add evidence
          </GuardedButton>
        }
      />
      <div className={s.row}>
        <Field label="Checklist item">
          <Select
            style={{ width: 360, maxWidth: '100%' }}
            value={filters.item ?? ''}
            onChange={(_, d) => set({ item: d.value || undefined })}
          >
            <option value="">All items</option>
            {(items.data?.items ?? []).map((i) => (
              <option key={i.item_id} value={i.item_id}>
                {i.item_id} – {i.title}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Type">
          <Select
            value={filters.type ?? ''}
            onChange={(_, d) => set({ type: d.value || undefined })}
          >
            <option value="">All types</option>
            {TYPES.map((t) => (
              <option key={t}>{t}</option>
            ))}
          </Select>
        </Field>
        <Field label="Status">
          <Select
            value={filters.status ?? ''}
            onChange={(_, d) => set({ status: d.value || undefined })}
          >
            <option value="">All statuses</option>
            {STATUSES.map((t) => (
              <option key={t}>{t}</option>
            ))}
          </Select>
        </Field>
      </div>

      {list.isPending ? (
        <LoadingState rows={5} />
      ) : list.isError ? (
        <ErrorState error={list.error} />
      ) : list.data.length === 0 ? (
        <EmptyState
          message="No evidence matches these filters yet."
          action={
            <GuardedButton reason={manage.reason} onClick={() => set({ new: '1' }, false)}>
              Add evidence
            </GuardedButton>
          }
        />
      ) : (
        <div className={s.tableWrap}>
          <Table aria-label="Evidence" size="small">
            <TableHeader>
              <TableRow>
                {['ID', 'Title', 'Item', 'Type', 'Submitted by', 'Status', 'Review', ''].map(
                  (h) => (
                    <TableHeaderCell key={h || 'actions'}>{h}</TableHeaderCell>
                  ),
                )}
              </TableRow>
            </TableHeader>
            <TableBody>
              {list.data.map((ev) => (
                <TableRow key={ev.id}>
                  <TableCell>{ev.id}</TableCell>
                  <TableCell>
                    <div>{ev.title}</div>
                    {ev.type === 'Link' && ev.url && isHttp(ev.url) && (
                      <a href={ev.url} target="_blank" rel="noreferrer noopener">
                        {ev.url}
                      </a>
                    )}
                    {ev.type === 'Email sign-off' && ev.text && (
                      <div className={s.muted}>{ev.text}</div>
                    )}
                  </TableCell>
                  <TableCell>
                    {ev.item_id ? `${ev.item_id} – ${ev.item_title ?? ''}` : '–'}
                  </TableCell>
                  <TableCell>
                    {ev.type === 'Generated' ? (
                      <Badge appearance="tint" color="brand">
                        Generated artefact
                      </Badge>
                    ) : (
                      ev.type
                    )}
                  </TableCell>
                  <TableCell>
                    {ev.submitted_by?.name ?? 'System'}
                    <div className={s.muted}>{formatDate(ev.created_at)}</div>
                  </TableCell>
                  <TableCell>
                    <Badge appearance="tint" color={STATUS_COLOR[ev.status]}>
                      {ev.status}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    {ev.reviewed_by ? `${ev.reviewed_by.name}, ${formatDate(ev.reviewed_at)}` : '–'}
                    {ev.review_note && <div className={s.muted}>{ev.review_note}</div>}
                  </TableCell>
                  <TableCell>
                    <div className={s.row}>
                      <GuardedButton
                        size="small"
                        reason={ev.can_review ? '' : (ev.review_denied_reason ?? 'Cannot review')}
                        onClick={() => setReview({ ev, decision: 'Accept' })}
                      >
                        Accept
                      </GuardedButton>
                      <GuardedButton
                        size="small"
                        reason={ev.can_review ? '' : (ev.review_denied_reason ?? 'Cannot review')}
                        onClick={() => setReview({ ev, decision: 'Reject' })}
                      >
                        Reject
                      </GuardedButton>
                      {ev.has_file && (
                        <Button
                          size="small"
                          appearance="subtle"
                          onClick={() =>
                            download(
                              `/evidence/${encodeURIComponent(ev.id)}/download`,
                              ev.title,
                            ).catch(showError)
                          }
                        >
                          Download
                        </Button>
                      )}
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      {addOpen && (
        <AddEvidenceDialog
          transitionId={transitionId}
          open
          onClose={closeAdd}
          items={items.data?.items}
          initialItem={params.get('item') ?? undefined}
        />
      )}
      {review && (
        <ReviewEvidenceDialog
          transitionId={transitionId}
          evidence={review.ev}
          decision={review.decision}
          onClose={() => setReview(null)}
        />
      )}
    </div>
  );
}

import { useState } from 'react';
import { useNavigate } from 'react-router';
import {
  Badge,
  Body1Strong,
  Button,
  Caption1,
  MessageBar,
  MessageBarBody,
  Toast,
  ToastTitle,
  Tooltip,
  makeStyles,
  tokens,
  useToastController,
} from '@fluentui/react-components';
import { ApiError } from '../../api/client';
import { TOASTER_ID } from '../../hooks/useApiErrorToast';
import { useUsers } from '../users/api';
import { ReasonButton } from '../gates/ReasonButton';
import { useAcceptProposal, useDismissProposal, type Proposal } from './api';
import { chatStore } from './chatStore';

const useStyles = makeStyles({
  root: { display: 'flex', flexDirection: 'column', gap: tokens.spacingVerticalS },
  table: { width: '100%', borderCollapse: 'collapse', fontSize: tokens.fontSizeBase200 },
  th: {
    textAlign: 'left',
    color: tokens.colorNeutralForeground3,
    fontWeight: tokens.fontWeightRegular,
    padding: '2px 8px 2px 0',
    verticalAlign: 'top',
    whiteSpace: 'nowrap',
  },
  td: { padding: '2px 0', verticalAlign: 'top', wordBreak: 'break-word' },
  tag: {
    display: 'inline-flex',
    alignItems: 'center',
    gap: '4px',
    color: tokens.colorNeutralForeground3,
  },
  dot: { width: '8px', height: '8px', borderRadius: '50%', display: 'inline-block' },
  actions: {
    display: 'flex',
    gap: tokens.spacingHorizontalS,
    flexWrap: 'wrap',
    alignItems: 'center',
  },
  excerpt: {
    margin: 0,
    whiteSpace: 'pre-wrap',
    fontSize: tokens.fontSizeBase200,
    color: tokens.colorNeutralForeground2,
    maxHeight: '160px',
    overflow: 'auto',
  },
  missing: { color: tokens.colorPaletteMarigoldForeground2 },
  before: { color: tokens.colorNeutralForeground3, textDecoration: 'line-through' },
});

interface ExtractedField {
  name: string;
  label: string;
  value?: unknown;
  display?: string | null;
  state: string;
  source?: string | null;
  confidence?: number;
  evidence?: string | null;
  note?: string | null;
}

const SOURCE_LABEL: Record<string, string> = {
  servicenow: 'ServiceNow',
  text: 'Your text',
  document: 'Document',
  context: 'You (default)',
  inferred: 'Inferred',
};

const humanize = (key: string) => {
  const t = key
    .replace(/_user_id$/, '')
    .replace(/_id$/, '')
    .replace(/_/g, ' ');
  return t.charAt(0).toUpperCase() + t.slice(1);
};

const KIND_LABEL: Record<string, string> = {
  create_transition: 'New transition',
  update_transition: 'Update transition',
  update_item: 'Update item',
  add_evidence: 'Add evidence',
  create_action: 'Action',
  draft_chaser: 'Chaser draft',
  request_inputs: 'Input request draft',
  request_exception: 'Exception request',
  request_approval: 'Approval request draft',
  accept_applicability: 'Applicability',
};

function confidenceColor(c: number | undefined): string {
  return (c ?? 0) >= 0.9
    ? tokens.colorPaletteGreenForeground1
    : tokens.colorPaletteMarigoldForeground2;
}

/** Orion proposal card (BR-050): Orion drafts, a permitted human accepts or dismisses. */
export function ProposalCard({ proposal }: { proposal: Proposal }) {
  const s = useStyles();
  const navigate = useNavigate();
  const { dispatchToast } = useToastController(TOASTER_ID);
  const accept = useAcceptProposal();
  const dismiss = useDismissProposal();
  const users = useUsers();
  const [error, setError] = useState<string | null>(null);

  const show = (v: unknown): string => {
    if (v === null || v === undefined || v === '') return '–';
    if (typeof v === 'string') return users.data?.find((u) => u.id === v)?.name ?? v;
    if (typeof v === 'number' || typeof v === 'boolean') return String(v);
    if (Array.isArray(v)) return v.map((e) => show(e)).join(', ');
    return JSON.stringify(v);
  };

  const p = proposal.payload;
  const isOpen = proposal.status === 'Open';
  const isCreate = proposal.kind === 'create_transition';
  const busy = accept.isPending || dismiss.isPending;

  const onAccept = () => {
    setError(null);
    accept.mutate(proposal.id, {
      onSuccess: (r) => {
        chatStore.updateProposal(r.proposal);
        dispatchToast(
          <Toast>
            <ToastTitle>
              {isCreate ? 'Opening the pre-filled form' : `Done: ${r.proposal.title}`}
            </ToastTitle>
          </Toast>,
          { intent: 'success' },
        );
        if (r.navigate_to) navigate(r.navigate_to);
      },
      onError: (e) =>
        setError(
          e instanceof ApiError
            ? // The reasons usually repeat or explain the detail: show the detail once.
              [e.detail, ...e.reasons.filter((r) => r !== e.detail)].join(' - ')
            : 'Orion could not run this proposal',
        ),
    });
  };
  const onDismiss = () => {
    setError(null);
    dismiss.mutate(proposal.id, {
      onSuccess: (r) => chatStore.updateProposal(r),
      onError: (e) => setError(e instanceof ApiError ? e.detail : 'Could not dismiss'),
    });
  };

  const isMissing = (f: ExtractedField) => f.state === 'missing' || f.state === 'ambiguous';
  const renderFieldTable = (rows: ExtractedField[]) => (
    <table className={s.table}>
      <tbody>
        {rows.map((f) => {
          const missing = isMissing(f);
          return (
            <tr key={f.name}>
              <th className={s.th} scope="row">
                {f.label}
              </th>
              <td className={s.td}>
                {missing ? (
                  <span className={s.missing}>
                    {f.state === 'ambiguous' ? 'Which one? You choose' : 'Needs your input'}
                  </span>
                ) : (
                  <Tooltip
                    content={f.evidence ? `"${f.evidence}"` : (f.note ?? 'No quoted evidence')}
                    relationship="description"
                  >
                    <span>{f.display ?? show(f.value)}</span>
                  </Tooltip>
                )}{' '}
                {!missing && f.source && (
                  <span className={s.tag}>
                    <span
                      className={s.dot}
                      style={{ backgroundColor: confidenceColor(f.confidence) }}
                      title={`Confidence ${Math.round((f.confidence ?? 0) * 100)}%`}
                    />
                    {SOURCE_LABEL[f.source] ?? f.source}
                  </span>
                )}
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );

  const renderBody = () => {
    if (isCreate) {
      const fields = (Array.isArray(p.fields) ? p.fields : []) as ExtractedField[];
      const summary = typeof p.summary === 'string' ? p.summary : '';
      const excerpt = typeof p.source_excerpt === 'string' ? p.source_excerpt : '';
      const warnings = Array.isArray(p.warnings) ? p.warnings.map(String) : [];
      return (
        <>
          {warnings.length > 0 && (
            <MessageBar intent="warning" layout="multiline" role="status">
              <MessageBarBody>
                {warnings.map((w) => (
                  <div key={w}>{w}</div>
                ))}
              </MessageBarBody>
            </MessageBar>
          )}
          {summary && <Caption1>{summary}</Caption1>}
          {renderFieldTable(fields.filter((f) => !isMissing(f)))}
          {fields.some(isMissing) && (
            <details>
              <summary>
                <Caption1 className={s.missing}>
                  {fields.filter(isMissing).length} fields need your input
                </Caption1>
              </summary>
              {renderFieldTable(fields.filter(isMissing))}
            </details>
          )}
          {excerpt && (
            <details>
              <summary>
                <Caption1>Source excerpt</Caption1>
              </summary>
              <pre className={s.excerpt}>{excerpt}</pre>
            </details>
          )}
        </>
      );
    }
    const changes =
      p.changes && typeof p.changes === 'object' ? (p.changes as Record<string, unknown>) : null;
    const current =
      p.current && typeof p.current === 'object' ? (p.current as Record<string, unknown>) : {};
    if (changes) {
      return (
        <table className={s.table}>
          <tbody>
            {Object.entries(changes).map(([k, v]) => (
              <tr key={k}>
                <th className={s.th} scope="row">
                  {humanize(k)}
                </th>
                <td className={s.td}>
                  {k in current && (
                    <>
                      <span className={s.before}>{show(current[k])}</span>
                      {' → '}
                    </>
                  )}
                  <strong>{show(v)}</strong>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      );
    }
    const rows = Object.entries(p).filter(
      ([k, v]) =>
        v !== null &&
        v !== undefined &&
        v !== '' &&
        k !== 'source_excerpt' &&
        (typeof v !== 'object' || Array.isArray(v)),
    );
    return (
      <table className={s.table}>
        <tbody>
          {rows.map(([k, v]) => (
            <tr key={k}>
              <th className={s.th} scope="row">
                {humanize(k)}
              </th>
              <td className={s.td}>{show(v)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    );
  };

  return (
    <div className={s.root}>
      <div className={s.actions}>
        <Badge appearance="tint" color="brand">
          {KIND_LABEL[proposal.kind] ?? humanize(proposal.kind)}
        </Badge>
        {!isOpen && (
          <Badge appearance="tint" color={proposal.status === 'Accepted' ? 'success' : 'subtle'}>
            {proposal.status}
          </Badge>
        )}
      </div>
      <Body1Strong>{proposal.title}</Body1Strong>
      {renderBody()}
      {error && (
        <MessageBar intent="error" layout="multiline" role="alert">
          <MessageBarBody>{error}</MessageBarBody>
        </MessageBar>
      )}
      {isOpen ? (
        <div className={s.actions}>
          <ReasonButton
            appearance="primary"
            size="small"
            reasons={
              proposal.can_accept
                ? []
                : [proposal.accept_denied_reason ?? 'You cannot accept this proposal']
            }
            onClick={busy ? undefined : onAccept}
          >
            {accept.isPending ? 'Working...' : isCreate ? 'Open pre-filled form' : 'Accept'}
          </ReasonButton>
          <Button size="small" disabled={busy} onClick={onDismiss}>
            Dismiss
          </Button>
        </div>
      ) : (
        isCreate &&
        proposal.status === 'Accepted' && (
          <div className={s.actions}>
            <Button
              size="small"
              onClick={() => navigate(`/transitions/new?proposal=${proposal.id}`)}
            >
              Open pre-filled form
            </Button>
          </div>
        )
      )}
      <Caption1>Orion drafts and recommends. You decide.</Caption1>
    </div>
  );
}

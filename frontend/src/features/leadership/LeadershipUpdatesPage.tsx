import { ReturnFocusDialog } from '../../components/ReturnFocusDialog';
import { useState } from 'react';
import {
  Badge,
  Body1,
  Button,
  Caption1,
  DialogActions,
  DialogBody,
  DialogContent,
  DialogSurface,
  DialogTitle,
  Field,
  Input,
  Select,
  Subtitle2,
  mergeClasses,
  makeStyles,
  tokens,
} from '@fluentui/react-components';
import dayjs from 'dayjs';
import { useSearchParams } from 'react-router';
import { ActorBadge } from '../../components/ActorBadge';
import { AppLink } from '../../components/AppLink';
import { EmptyState } from '../../components/EmptyState';
import { ErrorState } from '../../components/ErrorState';
import { LoadingState } from '../../components/LoadingState';
import { PageHeader } from '../../components/PageHeader';
import { palette } from '../../theme/orionTheme';
import { SectionCard } from '../../components/SectionCard';
import { useApiErrorToast } from '../../hooks/useApiErrorToast';
import { splitAddresses, validateRecipients } from '../drafts/richText';
import { ReasonButton } from '../gates/ReasonButton';
import { usePerm } from '../gates/usePerm';
import { useSuccessToast } from '../gates/useSuccessToast';
import { useReference } from '../reference/api';
import { useTransitions } from '../transitions/api';
import { useUsers } from '../users/api';
import {
  useGenerateLeadershipUpdate,
  useLeadershipUpdate,
  useLeadershipUpdates,
  useSendLeadershipUpdate,
  type LeadershipCreate,
  type LeadershipUpdate,
} from './api';
import { SafeMarkdown } from './SafeMarkdown';

const useStyles = makeStyles({
  page: { display: 'flex', flexDirection: 'column', gap: tokens.spacingVerticalL },
  layout: {
    display: 'flex',
    flexWrap: 'wrap',
    gap: tokens.spacingHorizontalL,
    alignItems: 'flex-start',
    minWidth: 0,
  },
  listCol: { flex: '1 1 260px', maxWidth: '360px', minWidth: 0 },
  detailCol: { flex: '3 1 420px', minWidth: 0 },
  list: { display: 'flex', flexDirection: 'column', gap: tokens.spacingVerticalS },
  item: {
    display: 'flex',
    flexDirection: 'column',
    gap: tokens.spacingVerticalXS,
    padding: tokens.spacingVerticalM,
    textAlign: 'left',
    cursor: 'pointer',
    color: 'inherit',
    font: 'inherit',
    minWidth: 0,
    overflowWrap: 'anywhere',
    border: `1px solid ${tokens.colorNeutralStroke2}`,
    borderRadius: tokens.borderRadiusLarge,
    backgroundColor: tokens.colorNeutralBackground1,
    ':hover': { backgroundColor: tokens.colorNeutralBackground1Hover },
  },
  itemSelected: {
    backgroundColor: tokens.colorBrandBackground2,
    boxShadow: `inset 4px 0 0 ${palette.yellow}`,
    ':hover': { backgroundColor: tokens.colorBrandBackground2 },
  },
  meta: { display: 'flex', gap: tokens.spacingHorizontalS, alignItems: 'center', flexWrap: 'wrap' },
  actions: { display: 'flex', gap: tokens.spacingHorizontalS, flexWrap: 'wrap' },
  form: { display: 'flex', flexDirection: 'column', gap: tokens.spacingVerticalM },
});

const SCOPE_LABEL: Record<LeadershipUpdate['scope'], string> = {
  all: 'All transitions',
  portfolio: 'Portfolio',
  transition: 'Transition',
};

const scopeText = (u: LeadershipUpdate) =>
  u.scope === 'all' ? SCOPE_LABEL.all : `${SCOPE_LABEL[u.scope]} ${u.scope_id ?? ''}`.trim();

function GenerateDialog({ onCreated }: { onCreated: (u: LeadershipUpdate) => void }) {
  const s = useStyles();
  const perm = usePerm('generate_leadership_update');
  const ref = useReference();
  const transitions = useTransitions({});
  const gen = useGenerateLeadershipUpdate();
  const showError = useApiErrorToast();
  const showSuccess = useSuccessToast();
  const [open, setOpen] = useState(false);
  const [scope, setScope] = useState<LeadershipCreate['scope']>('all');
  const [scopeId, setScopeId] = useState('');

  const needsId = scope !== 'all';
  const options =
    scope === 'portfolio'
      ? (ref.data?.portfolios ?? []).map((p) => ({ value: p, label: p }))
      : (transitions.data ?? []).map((t) => ({ value: t.id, label: `${t.id} ${t.name}` }));

  const submit = () =>
    gen.mutate(
      { scope, scope_id: needsId ? scopeId : null },
      {
        onSuccess: (u) => {
          setOpen(false);
          showSuccess('Leadership update drafted by Orion', 'Review it, then send it.');
          onCreated(u);
        },
        onError: showError,
      },
    );

  return (
    <>
      <ReasonButton appearance="primary" reasons={[perm.reason]} onClick={() => setOpen(true)}>
        Generate update
      </ReasonButton>
      <ReturnFocusDialog open={open} onOpenChange={(_, d) => !gen.isPending && setOpen(d.open)}>
        <DialogSurface>
          <DialogBody>
            <DialogTitle>Generate leadership update</DialogTitle>
            <DialogContent className={s.form}>
              <Body1>
                Orion drafts the update from live data. Nothing is sent until you send it.
              </Body1>
              <Field label="Scope">
                <Select
                  value={scope}
                  onChange={(_, d) => {
                    setScope(d.value as LeadershipCreate['scope']);
                    setScopeId('');
                  }}
                >
                  <option value="all">All transitions</option>
                  <option value="portfolio">One portfolio</option>
                  <option value="transition">One transition</option>
                </Select>
              </Field>
              {needsId && (
                <Field label={scope === 'portfolio' ? 'Portfolio' : 'Transition'} required>
                  <Select value={scopeId} onChange={(_, d) => setScopeId(d.value)}>
                    <option value="">Select...</option>
                    {options.map((o) => (
                      <option key={o.value} value={o.value}>
                        {o.label}
                      </option>
                    ))}
                  </Select>
                </Field>
              )}
            </DialogContent>
            <DialogActions>
              <Button
                appearance="secondary"
                disabled={gen.isPending}
                onClick={() => setOpen(false)}
              >
                Cancel
              </Button>
              <Button
                appearance="primary"
                disabled={gen.isPending || (needsId && !scopeId)}
                onClick={submit}
              >
                {gen.isPending ? 'Generating...' : 'Generate'}
              </Button>
            </DialogActions>
          </DialogBody>
        </DialogSurface>
      </ReturnFocusDialog>
    </>
  );
}

function SendDialog({ update }: { update: LeadershipUpdate }) {
  const s = useStyles();
  const perm = usePerm('generate_leadership_update');
  const users = useUsers();
  const send = useSendLeadershipUpdate();
  const showError = useApiErrorToast();
  const showSuccess = useSuccessToast();
  const [open, setOpen] = useState(false);
  const [to, setTo] = useState('');
  const [touched, setTouched] = useState(false);

  const error = validateRecipients(to, true);
  const openDialog = () => {
    const leaders = (users.data ?? []).filter((u) => u.role === 'LEADERSHIP').map((u) => u.email);
    setTo(leaders.join(', '));
    setTouched(false);
    setOpen(true);
  };

  return (
    <>
      <ReasonButton reasons={[perm.reason]} onClick={openDialog}>
        {update.sent_at ? 'Send again' : 'Send'}
      </ReasonButton>
      <ReturnFocusDialog open={open} onOpenChange={(_, d) => !send.isPending && setOpen(d.open)}>
        <DialogSurface>
          <DialogBody>
            <DialogTitle>Send leadership update</DialogTitle>
            <DialogContent className={s.form}>
              <Field
                label="Recipients (comma separated)"
                required
                validationState={touched && error ? 'error' : 'none'}
                validationMessage={touched ? error : null}
              >
                <Input
                  value={to}
                  onChange={(_, d) => {
                    setTo(d.value);
                    setTouched(true);
                  }}
                />
              </Field>
              <Caption1>Sent by you via email and Teams; logged in the Outbox.</Caption1>
            </DialogContent>
            <DialogActions>
              <Button
                appearance="secondary"
                disabled={send.isPending}
                onClick={() => setOpen(false)}
              >
                Cancel
              </Button>
              <Button
                appearance="primary"
                disabled={send.isPending || !!error}
                onClick={() =>
                  send.mutate(
                    { id: update.id, to: splitAddresses(to) },
                    {
                      onSuccess: () => {
                        setOpen(false);
                        showSuccess(
                          'Leadership update sent via email and Teams',
                          <AppLink to="/outbox">View in Outbox</AppLink>,
                        );
                      },
                      onError: showError,
                    },
                  )
                }
              >
                {send.isPending ? 'Sending...' : 'Send'}
              </Button>
            </DialogActions>
          </DialogBody>
        </DialogSurface>
      </ReturnFocusDialog>
    </>
  );
}

function Detail({ id }: { id: number }) {
  const s = useStyles();
  const q = useLeadershipUpdate(id);
  const showSuccess = useSuccessToast();
  const showError = useApiErrorToast();
  if (q.isLoading) return <LoadingState rows={8} />;
  if (q.isError) return <ErrorState error={q.error} onRetry={() => void q.refetch()} />;
  const u = q.data;
  if (!u) return null;

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(`${u.title}\n\n${u.content_md}`);
      showSuccess('Copied to clipboard');
    } catch (e) {
      showError(e);
    }
  };

  return (
    <SectionCard
      tone="ai"
      title={u.title}
      actions={
        <div className={s.actions}>
          <Button onClick={() => void copy()}>Copy to clipboard</Button>
          <SendDialog update={u} />
        </div>
      }
    >
      <div className={s.meta}>
        <ActorBadge actor="Orion agent" />
        <Caption1>
          {scopeText(u)} · generated {dayjs(u.created_at).format('D MMM YYYY HH:mm')}
          {u.generated_by ? ` · requested by ${u.generated_by.name}` : ''}
        </Caption1>
        {u.sent_at ? (
          <Badge appearance="outline" color="success">
            Sent {dayjs(u.sent_at).format('D MMM HH:mm')} to {u.sent_to.length}
          </Badge>
        ) : (
          <Badge appearance="outline" color="brand">
            Not sent
          </Badge>
        )}
      </div>
      <SafeMarkdown source={u.content_md} />
    </SectionCard>
  );
}

/** Leadership updates (FR-080): Orion-generated portfolio updates a person reviews and sends. */
export function LeadershipUpdatesPage() {
  const s = useStyles();
  const [params, setParams] = useSearchParams();
  const list = useLeadershipUpdates();
  const picked = params.get('update');
  const selected = picked && /^\d+$/.test(picked) ? Number(picked) : (list.data?.[0]?.id ?? null);

  const select = (id: number | null) => {
    const next = new URLSearchParams(params);
    if (id === null) next.delete('update');
    else next.set('update', String(id));
    setParams(next, { replace: true });
  };

  return (
    <div className={s.page}>
      <PageHeader
        title="Leadership updates"
        subtitle="Portfolio updates Orion drafts from live data for the OR focal to review and send."
        actions={<GenerateDialog onCreated={(u) => select(u.id)} />}
      />
      {list.isLoading && <LoadingState rows={6} />}
      {list.isError && <ErrorState error={list.error} onRetry={() => void list.refetch()} />}
      {list.data && list.data.length === 0 && (
        <EmptyState message="No leadership updates yet. Use Generate update to have Orion draft one." />
      )}
      {list.data && list.data.length > 0 && (
        <div className={s.layout}>
          <div className={s.listCol}>
            <div className={s.list} role="list" aria-label="Leadership updates">
              <Subtitle2>Newest first</Subtitle2>
              {list.data.map((u) => (
                <button
                  key={u.id}
                  type="button"
                  role="listitem"
                  aria-current={u.id === selected}
                  className={mergeClasses(s.item, u.id === selected && s.itemSelected)}
                  onClick={() => select(u.id)}
                >
                  <strong>{u.title}</strong>
                  <Caption1>
                    {scopeText(u)} · {dayjs(u.created_at).format('D MMM YYYY HH:mm')}
                  </Caption1>
                  <span className={s.meta}>
                    <ActorBadge actor="Orion agent" />
                    <Badge appearance="outline" color={u.sent_at ? 'success' : 'brand'}>
                      {u.sent_at ? 'Sent' : 'Not sent'}
                    </Badge>
                  </span>
                </button>
              ))}
            </div>
          </div>
          <div className={s.detailCol}>{selected !== null && <Detail id={selected} />}</div>
        </div>
      )}
    </div>
  );
}

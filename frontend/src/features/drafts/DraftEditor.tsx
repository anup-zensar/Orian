import { useState } from 'react';
import {
  Button,
  Caption1,
  Field,
  Input,
  Textarea,
  makeStyles,
  tokens,
} from '@fluentui/react-components';
import { useApiErrorToast } from '../../hooks/useApiErrorToast';
import { ReasonButton } from '../gates/ReasonButton';
import { usePerm } from '../gates/usePerm';
import { useDiscardDraft, usePatchDraft, useSendDraft, type Draft } from './api';
import { SourceLabel } from './SourceLabel';

const useStyles = makeStyles({
  root: { display: 'flex', flexDirection: 'column', gap: tokens.spacingVerticalM },
  meta: { display: 'flex', gap: tokens.spacingHorizontalS, alignItems: 'center', flexWrap: 'wrap' },
  split: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))',
    gap: tokens.spacingHorizontalL,
  },
  body: { fontFamily: tokens.fontFamilyMonospace, minHeight: '200px' },
  preview: {
    width: '100%',
    height: '280px',
    border: `1px solid ${tokens.colorNeutralStroke2}`,
    borderRadius: tokens.borderRadiusMedium,
    backgroundColor: '#ffffff',
  },
  actions: { display: 'flex', gap: tokens.spacingHorizontalS, flexWrap: 'wrap' },
});

const splitAddresses = (v: string) =>
  v
    .split(/[,;\s]+/)
    .map((a) => a.trim())
    .filter(Boolean);

/** Sandboxed preview of an email body: never injected into the page DOM (spec 5.5). */
export function EmailPreview({
  html,
  title,
  height,
}: {
  html: string;
  title: string;
  height?: number;
}) {
  const s = useStyles();
  return (
    <iframe
      className={s.preview}
      style={height ? { height } : undefined}
      sandbox=""
      srcDoc={html}
      title={title}
    />
  );
}

/**
 * Draft editor: to/cc, subject, HTML body with live sandboxed preview, Send (send_drafts) / Discard.
 * `sendReasons` lets a caller add extra reasons that block sending (e.g. approval not requestable).
 */
function DraftEditorInner(props: {
  draft: Draft;
  sendReasons?: Array<string | null | undefined>;
  onSent?: (draft: Draft) => void;
  onDiscarded?: () => void;
}) {
  const s = useStyles();
  const { draft } = props;
  const showError = useApiErrorToast();
  const perm = usePerm('send_drafts');
  const patch = usePatchDraft();
  const send = useSendDraft();
  const discard = useDiscardDraft();
  const [to, setTo] = useState(draft.to.join(', '));
  const [cc, setCc] = useState(draft.cc.join(', '));
  const [subject, setSubject] = useState(draft.subject);
  const [body, setBody] = useState(draft.body_html);

  const editable = draft.status === 'Draft';
  const dirty =
    to !== draft.to.join(', ') ||
    cc !== draft.cc.join(', ') ||
    subject !== draft.subject ||
    body !== draft.body_html;
  const busy = patch.isPending || send.isPending || discard.isPending;

  const save = () =>
    patch.mutateAsync({
      id: draft.id,
      patch: { to: splitAddresses(to), cc: splitAddresses(cc), subject, body_html: body },
    });

  const onSave = () => save().catch(showError);
  const onSend = async () => {
    try {
      if (dirty) await save();
      const r = await send.mutateAsync(draft.id);
      props.onSent?.(r.draft);
    } catch (e) {
      showError(e);
    }
  };
  const onDiscard = () =>
    discard.mutate(draft.id, {
      onSuccess: () => props.onDiscarded?.(),
      onError: showError,
    });

  return (
    <div className={s.root}>
      <div className={s.meta}>
        <SourceLabel label={draft.source_label} />
        <Caption1>
          {draft.kind} · {draft.status}
          {draft.transition_name ? ` · ${draft.transition_name}` : ''}
        </Caption1>
      </div>
      <Field label="To (comma separated)" required>
        <Input value={to} disabled={!editable} onChange={(_, d) => setTo(d.value)} />
      </Field>
      <Field label="Cc (comma separated)">
        <Input value={cc} disabled={!editable} onChange={(_, d) => setCc(d.value)} />
      </Field>
      <Field label="Subject" required>
        <Input value={subject} disabled={!editable} onChange={(_, d) => setSubject(d.value)} />
      </Field>
      <div className={s.split}>
        <Field label="Body (HTML source)">
          <Textarea
            textarea={{ className: s.body }}
            value={body}
            disabled={!editable}
            resize="vertical"
            onChange={(_, d) => setBody(d.value)}
          />
        </Field>
        <Field label="Live preview (sandboxed)">
          <EmailPreview html={body} title="Draft preview" />
        </Field>
      </div>
      {editable && (
        <div className={s.actions}>
          <ReasonButton
            appearance="primary"
            reasons={[perm.reason, ...(props.sendReasons ?? [])]}
            onClick={onSend}
          >
            {send.isPending ? 'Sending...' : 'Send'}
          </ReasonButton>
          <Button disabled={!dirty || busy} onClick={onSave}>
            Save changes
          </Button>
          <Button appearance="subtle" disabled={busy} onClick={onDiscard}>
            Discard
          </Button>
        </div>
      )}
    </div>
  );
}

/** Remounts the form whenever the saved draft changes, so local edits always start from the server copy. */
export function DraftEditor(props: Parameters<typeof DraftEditorInner>[0]) {
  const d = props.draft;
  const key = [d.id, d.status, d.subject, d.to.join(), d.cc.join(), d.body_html].join('|');
  return <DraftEditorInner key={key} {...props} />;
}

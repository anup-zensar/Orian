import { useState } from 'react';
import {
  Button,
  Caption1,
  Field,
  Input,
  MessageBar,
  MessageBarBody,
  Textarea,
  makeStyles,
  tokens,
} from '@fluentui/react-components';
import { useApiErrorToast } from '../../hooks/useApiErrorToast';
import { ReasonButton } from '../gates/ReasonButton';
import { useSuccessToast } from '../gates/useSuccessToast';
import { AppLink } from '../../components/AppLink';
import { usePerm } from '../gates/usePerm';
import { useDiscardDraft, usePatchDraft, useSendDraft, type Draft } from './api';
import { SourceLabel } from './SourceLabel';
import { htmlToMarkdown, markdownToHtml, splitAddresses, validateRecipients } from './richText';

const useStyles = makeStyles({
  root: { display: 'flex', flexDirection: 'column', gap: tokens.spacingVerticalM },
  meta: { display: 'flex', gap: tokens.spacingHorizontalS, alignItems: 'center', flexWrap: 'wrap' },
  split: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))',
    gap: tokens.spacingHorizontalL,
  },
  body: { fontFamily: tokens.fontFamilyMonospace, minHeight: '200px' },
  text: { minHeight: '200px' },
  preview: {
    width: '100%',
    height: '280px',
    border: `1px solid ${tokens.colorNeutralStroke2}`,
    borderRadius: tokens.borderRadiusMedium,
    backgroundColor: '#ffffff',
  },
  actions: { display: 'flex', gap: tokens.spacingHorizontalS, flexWrap: 'wrap' },
});

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
  const showSuccess = useSuccessToast();
  const [mode, setMode] = useState<'preview' | 'text' | 'html'>('preview');
  const [md, setMd] = useState('');
  const perm = usePerm('send_drafts');
  const patch = usePatchDraft();
  const send = useSendDraft();
  const discard = useDiscardDraft();
  const [to, setTo] = useState(draft.to.join(', '));
  const [cc, setCc] = useState(draft.cc.join(', '));
  const [subject, setSubject] = useState(draft.subject);
  const [body, setBody] = useState(draft.body_html);

  const canEdit = draft.can_edit !== false;
  const editable = draft.status === 'Draft' && canEdit;
  const editReason = draft.edit_denied_reason ?? 'You cannot edit this draft';
  const dirty =
    to !== draft.to.join(', ') ||
    cc !== draft.cc.join(', ') ||
    subject !== draft.subject ||
    body !== draft.body_html;
  const toError = validateRecipients(to, true);
  const ccError = validateRecipients(cc, false);
  const invalid = [toError, ccError, subject.trim() ? null : 'Add a subject'].filter(
    (r): r is string => !!r,
  );
  const busy = patch.isPending || send.isPending || discard.isPending;

  const save = () =>
    patch.mutateAsync({
      id: draft.id,
      patch: { to: splitAddresses(to), cc: splitAddresses(cc), subject, body_html: body },
    });

  const onSave = () =>
    save()
      .then(() => showSuccess('Draft saved'))
      .catch(showError);
  const onSend = async () => {
    try {
      if (dirty) await save();
      const r = await send.mutateAsync(draft.id);
      showSuccess('Sent via email and Teams', <AppLink to="/outbox">View in Outbox</AppLink>);
      props.onSent?.(r.draft);
    } catch (e) {
      showError(e);
    }
  };
  const onDiscard = () =>
    discard.mutate(draft.id, {
      onSuccess: () => {
        showSuccess('Draft discarded');
        props.onDiscarded?.();
      },
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
      {draft.status === 'Draft' && !canEdit && (
        <MessageBar intent="info">
          <MessageBarBody>You can view but not edit this draft: {editReason}</MessageBarBody>
        </MessageBar>
      )}
      <Field
        label="To (comma separated)"
        required
        validationState={toError && to !== draft.to.join(', ') ? 'error' : 'none'}
        validationMessage={to !== draft.to.join(', ') ? toError : null}
      >
        <Input value={to} disabled={!editable} onChange={(_, d) => setTo(d.value)} />
      </Field>
      <Field
        label="Cc (comma separated)"
        validationState={ccError ? 'error' : 'none'}
        validationMessage={ccError}
      >
        <Input value={cc} disabled={!editable} onChange={(_, d) => setCc(d.value)} />
      </Field>
      <Field label="Subject" required>
        <Input value={subject} disabled={!editable} onChange={(_, d) => setSubject(d.value)} />
      </Field>
      <div className={s.split}>
        {mode === 'text' && (
          <Field
            label="Body (text)"
            hint="Blank line = new paragraph, '- ' = bullet, **bold**, *italic*, [text](https://link)"
          >
            <Textarea
              textarea={{ className: s.text }}
              value={md}
              disabled={!editable}
              resize="vertical"
              onChange={(_, d) => {
                setMd(d.value);
                setBody(markdownToHtml(d.value));
              }}
            />
          </Field>
        )}
        {mode === 'html' && (
          <Field label="Body (HTML source)">
            <Textarea
              textarea={{ className: s.body }}
              value={body}
              disabled={!editable}
              resize="vertical"
              onChange={(_, d) => setBody(d.value)}
            />
          </Field>
        )}
        <Field label="Preview (sandboxed)">
          <EmailPreview html={body} title="Draft preview" />
        </Field>
      </div>
      {draft.status === 'Draft' && (
        <div className={s.actions}>
          <Button
            disabled={!editable}
            appearance={mode === 'text' ? 'primary' : 'secondary'}
            onClick={() => {
              if (mode === 'text') return setMode('preview');
              setMd(htmlToMarkdown(body));
              setMode('text');
            }}
          >
            Edit as text
          </Button>
          <Button
            disabled={!editable}
            appearance={mode === 'html' ? 'primary' : 'secondary'}
            onClick={() => setMode(mode === 'html' ? 'preview' : 'html')}
          >
            Edit HTML
          </Button>
          <ReasonButton
            appearance="primary"
            reasons={[
              perm.reason,
              draft.can_send === false
                ? (draft.send_denied_reason ?? 'You cannot send this draft')
                : null,
              ...invalid,
              ...(props.sendReasons ?? []),
            ]}
            onClick={onSend}
          >
            {send.isPending ? 'Sending...' : 'Send'}
          </ReasonButton>
          <ReasonButton
            reasons={[canEdit ? null : editReason, dirty ? null : 'No changes to save', ...invalid]}
            disabled={busy}
            onClick={onSave}
          >
            Save changes
          </ReasonButton>
          <ReasonButton
            appearance="subtle"
            reasons={[canEdit ? null : editReason]}
            disabled={busy}
            onClick={onDiscard}
          >
            Discard
          </ReasonButton>
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

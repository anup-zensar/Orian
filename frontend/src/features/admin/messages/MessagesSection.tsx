import { useRef, useState } from 'react';
import {
  Button,
  Field,
  Input,
  Select,
  MessageBar,
  MessageBarBody,
  Subtitle2,
  Textarea,
  Tooltip,
  makeStyles,
  tokens,
} from '@fluentui/react-components';
import type { MessageTemplateAdmin } from '../../../api/types';
import { ErrorState } from '../../../components/ErrorState';
import { LoadingState } from '../../../components/LoadingState';
import { SectionCard } from '../../../components/SectionCard';
import { useMessageTemplates, usePreviewTemplate, usePutTemplates } from '../peopleRulesApi';
import { DirtyGuard, Intro, ReasonsBar, SaveBar } from '../peopleRulesUi';
import { useDirty } from '../useDirty';
import { useSuccessToast } from '../useSavedToast';
import { placeholdersIn, toHtml, toText } from './bodyText';

/** What the Admin edits for one template: the subject and the body (as plain text or raw HTML). */
interface Draft {
  subject: string;
  body: string;
  rawHtml: boolean; // true when the body cannot be shown as plain text
}

type Field_ = 'subject' | 'body';

const useStyles = makeStyles({
  page: { display: 'flex', flexDirection: 'column', gap: tokens.spacingVerticalL },
  layout: { display: 'flex', flexDirection: 'column', gap: tokens.spacingVerticalM },
  picker: { maxWidth: '420px' },
  editor: {
    minWidth: 0,
    display: 'flex',
    flexDirection: 'column',
    gap: tokens.spacingVerticalM,
  },
  chips: { display: 'flex', flexWrap: 'wrap', gap: tokens.spacingHorizontalXS },
  note: { color: tokens.colorNeutralForeground3, margin: 0 },
  preview: {
    width: '100%',
    height: '260px',
    border: `1px solid ${tokens.colorNeutralStroke2}`,
    borderRadius: tokens.borderRadiusMedium,
    backgroundColor: tokens.colorNeutralBackground1,
  },
  row: { display: 'flex', gap: tokens.spacingHorizontalS, flexWrap: 'wrap' },
});

/** Template names may start with a rule number ("R2 ..."); admins do not need it. */
const plainName = (name: string): string => name.replace(/^R\d+\s*[-:.]?\s*/, '');

const draftOf = (subject: string, html: string): Draft => {
  const text = toText(html);
  return { subject, body: text ?? html, rawHtml: text === null };
};
const savedDraft = (t: MessageTemplateAdmin): Draft => draftOf(t.subject, t.body);
const htmlOf = (d: Draft): string => (d.rawHtml ? d.body : toHtml(d.body));

function Editor({ templates }: { templates: MessageTemplateAdmin[] }) {
  const s = useStyles();
  const [drafts, setDrafts] = useState<Record<string, Draft>>(() =>
    Object.fromEntries(templates.map((t) => [t.key, savedDraft(t)])),
  );
  const [selected, setSelected] = useState(templates[0]?.key ?? '');
  const dirty = useDirty(drafts, 'messages');
  const save = usePutTemplates();
  const preview = usePreviewTemplate();
  const ok = useSuccessToast();
  const subjectRef = useRef<HTMLInputElement>(null);
  const bodyRef = useRef<HTMLTextAreaElement>(null);
  const [lastField, setLastField] = useState<Field_>('body');

  const tpl = templates.find((t) => t.key === selected);
  const draft = drafts[selected];
  if (!tpl || !draft) return null;

  const edit = (p: Partial<Draft>) => {
    setDrafts((d) => ({ ...d, [selected]: { ...d[selected], ...p } }));
    preview.reset();
  };

  /** Put {{name}} where the cursor was last seen (subject or body). */
  const insert = (name: string) => {
    const field: Field_ = lastField;
    const el = field === 'subject' ? subjectRef.current : bodyRef.current;
    const text = `{{${name}}}`;
    const value = field === 'subject' ? draft.subject : draft.body;
    const at = el?.selectionStart ?? value.length;
    const end = el?.selectionEnd ?? at;
    edit({ [field]: value.slice(0, at) + text + value.slice(end) });
    window.setTimeout(() => {
      el?.focus();
      el?.setSelectionRange(at + text.length, at + text.length);
    }, 0);
  };

  const allowed = new Set(tpl.placeholders.map((p) => p.name));
  const unknown = placeholdersIn(draft.subject, htmlOf(draft)).filter((n) => !allowed.has(n));
  const empty = !draft.subject.trim() || !draft.body.trim();
  const changed = templates.filter(
    (t) => JSON.stringify(drafts[t.key]) !== JSON.stringify(savedDraft(t)),
  );
  const blockedReason = unknown.length
    ? `Unknown value: ${unknown.map((n) => `{{${n}}}`).join(', ')}`
    : empty
      ? 'Subject and message cannot be empty'
      : undefined;

  const submit = () =>
    save.mutate(
      {
        templates: changed.map((t) => ({
          key: t.key,
          subject: drafts[t.key].subject.trim(),
          body: htmlOf(drafts[t.key]),
          enabled: t.enabled ?? true,
        })),
      },
      { onSuccess: () => ok('Saved - applies to new drafts') },
    );

  return (
    <div className={s.layout}>
      <div className={s.picker}>
        <Field label="Message">
          <Select
            value={selected}
            onChange={(_, d) => {
              setSelected(d.value);
              preview.reset();
            }}
          >
            {templates.map((t) => (
              <option key={t.key} value={t.key}>
                {plainName(t.name)}
                {JSON.stringify(drafts[t.key]) !== JSON.stringify(savedDraft(t))
                  ? ' (unsaved)'
                  : t.subject !== t.default_subject || t.body !== t.default_body
                    ? ' (edited)'
                    : ''}
              </option>
            ))}
          </Select>
        </Field>
      </div>
      <div className={s.editor}>
        <SectionCard title={plainName(tpl.name)}>
          <MessageBar layout="multiline" intent="info">
            <MessageBarBody>{tpl.notice}</MessageBarBody>
          </MessageBar>
          <Field label="Subject" validationMessage={draft.subject.trim() ? undefined : 'Required'}>
            <Input
              ref={subjectRef}
              value={draft.subject}
              onFocus={() => setLastField('subject')}
              onChange={(_, d) => edit({ subject: d.value })}
            />
          </Field>
          <Field
            label="Message"
            hint={
              draft.rawHtml
                ? 'This message uses formatting that is edited as HTML.'
                : 'A blank line starts a new paragraph. [text](deep_link) makes a link to the page in Orion.'
            }
            validationMessage={draft.body.trim() ? undefined : 'Required'}
          >
            <Textarea
              ref={bodyRef}
              rows={12}
              resize="vertical"
              value={draft.body}
              onFocus={() => setLastField('body')}
              onChange={(_, d) => edit({ body: d.value })}
            />
          </Field>
          <div>
            <Subtitle2 as="h3">Values you can insert</Subtitle2>
            <p className={s.note}>
              Click one to add it where your cursor is. Text in {'{{ }}'} is filled in
              automatically.
            </p>
            <div className={s.chips}>
              {tpl.placeholders.map((p) => (
                <Tooltip key={p.name} relationship="description" content={p.description || p.name}>
                  <Button size="small" appearance="outline" onClick={() => insert(p.name)}>
                    {p.name.replace(/_/g, ' ')}
                  </Button>
                </Tooltip>
              ))}
            </div>
          </div>
          <div className={s.row}>
            <Button
              disabled={preview.isPending || empty}
              onClick={() =>
                preview.mutate({
                  key: tpl.key,
                  body: { subject: draft.subject, body: htmlOf(draft) },
                })
              }
            >
              {preview.isPending ? 'Preparing...' : 'Preview with sample values'}
            </Button>
            <Button
              onClick={() => edit(draftOf(tpl.default_subject, tpl.default_body))}
              disabled={
                JSON.stringify(draft) ===
                JSON.stringify(draftOf(tpl.default_subject, tpl.default_body))
              }
            >
              Use original wording
            </Button>
          </div>
          {preview.data && (
            <div>
              <strong>{preview.data.subject}</strong>
              <iframe
                title="Message preview"
                className={s.preview}
                sandbox=""
                srcDoc={preview.data.body_html}
              />
            </div>
          )}
          <ReasonsBar error={preview.error ?? save.error} />
        </SectionCard>
        <SaveBar
          dirty={dirty}
          saving={save.isPending}
          blockedReason={blockedReason}
          onSave={submit}
          onDiscard={() => {
            setDrafts(Object.fromEntries(templates.map((t) => [t.key, savedDraft(t)])));
            save.reset();
            preview.reset();
          }}
        />
      </div>
    </div>
  );
}

/** Admin section 7: the wording of the messages Orion drafts. */
export function MessagesSection() {
  const s = useStyles();
  const q = useMessageTemplates();
  return (
    <DirtyGuard>
      <div className={s.page}>
        <Intro>
          Change the wording of the messages Orion drafts for chasers, reminders and approval
          requests. This changes the text only, never who receives a message or when it is sent.
        </Intro>
        {q.isLoading ? (
          <LoadingState rows={6} />
        ) : q.isError ? (
          <ErrorState error={q.error} onRetry={() => void q.refetch()} />
        ) : q.data ? (
          <Editor key={q.dataUpdatedAt} templates={q.data} />
        ) : null}
      </div>
    </DirtyGuard>
  );
}

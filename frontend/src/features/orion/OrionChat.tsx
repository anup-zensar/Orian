import { useEffect, useRef, useState, type KeyboardEvent } from 'react';
import { useMatch, useNavigate } from 'react-router';
import {
  Body1,
  Button,
  Caption1,
  Menu,
  MenuItem,
  MenuList,
  MenuPopover,
  MenuTrigger,
  Spinner,
  Subtitle2,
  Textarea,
  Tag,
  Tooltip,
  makeStyles,
  tokens,
} from '@fluentui/react-components';
import {
  Attach16Regular,
  Dismiss12Regular,
  Delete16Regular,
  Send16Filled,
  Sparkle16Regular,
} from '@fluentui/react-icons';
import { ai } from '../../theme/orionTheme';
import { AiBadge } from '../../components/AiBadge';
import { ErrorState } from '../../components/ErrorState';
import {
  QUICK_ACTIONS,
  useIntents,
  useOrionChat,
  useOrionExtract,
  type ChatContext,
  type OrionMessage,
  type QuickActionId,
} from './api';
import { chatStore, useChatItems, type ChatItem } from './chatStore';
import { OrionMessageView } from './OrionMessages';
import { ApiError } from '../../api/client';
import { useOrionPanel } from './panelContext';
import { usePerm } from '../gates/usePerm';

const CHAT_LIMIT = 2000;
const EXTRACT_LIMIT = 20000;
const MAX_FILE = 5 * 1024 * 1024;
const FILE_TYPES = ['.txt', '.md', '.vtt', '.docx'];

const useStyles = makeStyles({
  root: { display: 'flex', flexDirection: 'column', minHeight: 0, height: '100%', flexGrow: 1 },
  chip: {
    display: 'flex',
    alignItems: 'center',
    gap: tokens.spacingHorizontalS,
    padding: `${tokens.spacingVerticalXS} 0`,
    flexWrap: 'wrap',
  },
  thread: {
    flexGrow: 1,
    minHeight: 0,
    overflowY: 'auto',
    display: 'flex',
    flexDirection: 'column',
    gap: tokens.spacingVerticalM,
    padding: `${tokens.spacingVerticalS} 0`,
  },
  welcome: {
    display: 'flex',
    flexDirection: 'column',
    gap: tokens.spacingVerticalS,
    padding: tokens.spacingVerticalM,
    borderRadius: tokens.borderRadiusMedium,
    border: `1px solid ${tokens.colorNeutralStroke2}`,
    backgroundColor: tokens.colorNeutralBackground1,
    borderTop: `3px solid ${ai.main}`,
    minWidth: 0,
  },
  wrap: { display: 'flex', flexWrap: 'wrap', gap: tokens.spacingHorizontalXS },
  user: {
    alignSelf: 'flex-end',
    maxWidth: '88%',
    padding: `${tokens.spacingVerticalS} ${tokens.spacingHorizontalM}`,
    borderRadius: tokens.borderRadiusLarge,
    backgroundColor: tokens.colorBrandBackground2,
    color: tokens.colorNeutralForeground1,
    whiteSpace: 'pre-wrap',
    overflowWrap: 'anywhere',
  },
  composer: {
    display: 'flex',
    flexDirection: 'column',
    gap: tokens.spacingVerticalXS,
    paddingTop: tokens.spacingVerticalS,
    borderTop: `1px solid ${tokens.colorNeutralStroke2}`,
  },
  box: { display: 'flex', gap: tokens.spacingHorizontalXS, alignItems: 'flex-end' },
  grow: { flexGrow: 1 },
  tools: {
    display: 'flex',
    gap: tokens.spacingHorizontalXS,
    flexWrap: 'wrap',
    alignItems: 'center',
  },
  hidden: { display: 'none' },
  footer: { display: 'flex', alignItems: 'center', gap: tokens.spacingHorizontalS },
});

/** The Orion conversation: quick actions, free text, paste, upload and the message cards (FR-090). */
export function OrionChat() {
  const s = useStyles();
  const panel = useOrionPanel();
  const navigate = useNavigate();
  const routeMatch = useMatch('/transitions/:id/*');
  const routeId =
    routeMatch?.params.id && routeMatch.params.id !== 'new' ? routeMatch.params.id : undefined;
  const items = useChatItems();
  const chat = useOrionChat();
  const extract = useOrionExtract();
  const intents = useIntents();
  const createPerm = usePerm('create_transition');
  const remindPerm = usePerm('run_reminders');
  const leadershipPerm = usePerm('generate_leadership_update');
  const fileRef = useRef<HTMLInputElement>(null);
  const endRef = useRef<HTMLDivElement>(null);

  const [text, setText] = useState('');
  const [showPaste, setShowPaste] = useState(false);
  const [paste, setPaste] = useState('');
  const [chipOff, setChipOff] = useState(false);
  const [seenTarget, setSeenTarget] = useState(panel.target);
  if (seenTarget !== panel.target) {
    setSeenTarget(panel.target);
    setChipOff(false);
    if (panel.target.prompt) setText(panel.target.prompt);
  }

  const transitionId = chipOff ? undefined : (panel.target.transitionId ?? routeId);
  const context: ChatContext = {
    transition_id: transitionId ?? null,
    page: typeof window !== 'undefined' ? window.location.pathname : null,
  };
  const busy = chat.isPending || extract.isPending;
  const hasConversation = items.length > 0;

  useEffect(() => {
    endRef.current?.scrollIntoView?.({ block: 'end' });
  }, [items.length, busy]);

  const pushMessages = (messages: OrionMessage[], tid?: string) => {
    for (const message of messages) {
      chatStore.push({ kind: 'orion', message, transitionId: tid ?? transitionId });
    }
  };

  const runChat = (
    body: Parameters<typeof chat.mutate>[0],
    tid: string | undefined,
    onDone?: () => void,
  ) => {
    chat.mutate(body, {
      onSuccess: (r) => {
        pushMessages(r.messages, tid);
        onDone?.();
      },
      onError: (error) =>
        chatStore.push({ kind: 'error', error, retry: () => runChat(body, tid, onDone) }),
    });
  };

  const runExtract = (req: Parameters<typeof extract.mutate>[0]) => {
    extract.mutate(req, {
      onSuccess: (r) => pushMessages(r.messages, req.transitionId),
      onError: (error) => {
        if (error instanceof ApiError && error.status === 400) {
          // Unreadable input: retrying the same file or text cannot work, so no Retry button.
          const what = req.file ? `"${req.file.name}"` : 'that text';
          chatStore.push({
            kind: 'orion',
            message: {
              type: 'text',
              generated_by: 'Orion agent',
              text: `I could not read any text in ${what}. The file may be empty or damaged. Check it, or paste the text instead.`,
            },
          });
          return;
        }
        chatStore.push({ kind: 'error', error, retry: () => runExtract(req) });
      },
    });
  };

  /** Returns true when the message was sent, so callers only clear the box then. */
  const sendText = (raw: string): boolean => {
    const value = raw.trim();
    if (!value || busy) return false;
    chatStore.push({
      kind: 'user',
      text: value.length > 400 ? `${value.slice(0, 400)}...` : value,
    });
    if (value.length > CHAT_LIMIT) runExtract({ text: value, transitionId });
    else runChat({ message: value, context }, transitionId);
    return true;
  };

  const onKey = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      if (sendText(text)) setText('');
    }
  };

  /** Why a quick action cannot be used by this user (null when it can). */
  // A quick action the user may not run is disabled with the API's reason (it would answer 403).
  const quickReason = (id: QuickActionId): string | null => {
    if (id === 'start_gate_review') return createPerm.reason;
    if (id === 'draft_owner_reminders') return remindPerm.reason;
    if (id === 'create_leadership_update') return leadershipPerm.reason;
    return null;
  };

  const quick = (id: QuickActionId, label: string) => {
    if (busy || quickReason(id)) return;
    if (id === 'start_gate_review') {
      // one click: the intake form has the ServiceNow fetch, so go straight there
      navigate('/transitions/new');
      return;
    }
    chatStore.push({ kind: 'user', text: label });
    runChat({ quick_action: id, context }, transitionId);
  };

  const submitForm = (
    item: Extract<ChatItem, { kind: 'orion' }>,
    values: Record<string, string>,
  ) => {
    if (item.message.type !== 'form') return;
    const tid = values['transition_id'] || transitionId;
    runChat({ quick_action: item.message.quick_action, form_data: values, context }, tid, () =>
      chatStore.markSubmitted(item.id),
    );
  };

  const sendPaste = () => {
    const value = paste.trim();
    if (!value || busy) return;
    chatStore.push({ kind: 'user', text: `Pasted text (${value.length} characters)` });
    runExtract({ text: value, transitionId });
    setPaste('');
    setShowPaste(false);
  };

  const onFile = (file: File | undefined) => {
    if (!file) return;
    const lower = file.name.toLowerCase();
    if (!FILE_TYPES.some((t) => lower.endsWith(t))) {
      chatStore.push({
        kind: 'orion',
        message: {
          type: 'text',
          generated_by: 'Orion agent',
          text: `I can read ${FILE_TYPES.join(', ')} files. "${file.name}" is not one of them.`,
        },
      });
      return;
    }
    if (file.size > MAX_FILE) {
      chatStore.push({
        kind: 'orion',
        message: {
          type: 'text',
          generated_by: 'Orion agent',
          text: `"${file.name}" is larger than 5 MB. Please upload a smaller file.`,
        },
      });
      return;
    }
    chatStore.push({ kind: 'user', text: 'Uploaded a document', fileName: file.name });
    runExtract({ file, transitionId });
  };

  const chips = (intents.data?.intents ?? [])
    .filter((i) => i.result !== 'refusal')
    .map((i) => ({ i, example: i.examples.find((e) => !e.startsWith('(')) }))
    .filter((c): c is { i: (typeof c)['i']; example: string } => !!c.example)
    .slice(0, 3);

  return (
    <div className={s.root}>
      <div className={s.chip}>
        {transitionId ? (
          <Tag
            size="small"
            appearance="brand"
            dismissible
            dismissIcon={{ 'aria-label': 'Remove context', children: <Dismiss12Regular /> }}
            onClick={() => setChipOff(true)}
            title="Click to remove the transition context"
          >
            Context: {transitionId}
          </Tag>
        ) : (
          <Caption1>No transition in context</Caption1>
        )}
        {hasConversation && (
          <Menu>
            <MenuTrigger disableButtonEnhancement>
              <Button size="small" appearance="subtle" icon={<Sparkle16Regular />}>
                Quick actions
              </Button>
            </MenuTrigger>
            <MenuPopover>
              <MenuList>
                {QUICK_ACTIONS.map((a) => {
                  const reason = quickReason(a.id);
                  const item = (
                    <MenuItem
                      key={a.id}
                      disabled={busy || !!reason}
                      onClick={() => quick(a.id, a.label)}
                    >
                      {a.label}
                    </MenuItem>
                  );
                  return reason ? (
                    <Tooltip key={a.id} content={reason} relationship="description">
                      <span>{item}</span>
                    </Tooltip>
                  ) : (
                    item
                  );
                })}
              </MenuList>
            </MenuPopover>
          </Menu>
        )}
        {hasConversation && (
          <Button
            size="small"
            appearance="subtle"
            icon={<Delete16Regular />}
            onClick={() => chatStore.clear()}
          >
            Clear
          </Button>
        )}
      </div>

      <div className={s.thread} role="log" aria-live="polite" aria-label="Orion conversation">
        <div className={s.welcome}>
          {!hasConversation && (
            <>
              <div className={s.footer}>
                <AiBadge />
                <Subtitle2>How can Orion help?</Subtitle2>
              </div>
              <Body1>
                Pick a quick action, ask a question, or describe a new transition in your own words.
              </Body1>
              <div className={s.wrap}>
                {QUICK_ACTIONS.map((a) => {
                  const reason = quickReason(a.id);
                  const btn = (
                    <Button
                      key={a.id}
                      size="small"
                      appearance="outline"
                      disabled={busy && !reason}
                      disabledFocusable={!!reason}
                      onClick={() => quick(a.id, a.label)}
                    >
                      {a.label}
                    </Button>
                  );
                  return reason ? (
                    <Tooltip key={a.id} content={reason} relationship="description">
                      {btn}
                    </Tooltip>
                  ) : (
                    btn
                  );
                })}
              </div>
            </>
          )}
          <Caption1>Try saying</Caption1>
          <div className={s.wrap}>
            {intents.isError && (
              <Caption1>
                Examples are unavailable right now.{' '}
                <Button
                  size="small"
                  appearance="transparent"
                  onClick={() => void intents.refetch()}
                >
                  Retry
                </Button>
              </Caption1>
            )}
            {chips.map(({ i, example }) => {
              const chip = (
                <Button
                  key={i.intent}
                  size="small"
                  shape="circular"
                  appearance="subtle"
                  disabledFocusable={!i.allowed}
                  onClick={() => {
                    if (i.allowed) setText(example);
                  }}
                >
                  {example}
                </Button>
              );
              return i.allowed ? (
                chip
              ) : (
                <Tooltip
                  key={i.intent}
                  content={i.denied_reason ?? 'You cannot run this'}
                  relationship="description"
                >
                  {chip}
                </Tooltip>
              );
            })}
          </div>
        </div>

        {items.map((item) => {
          if (item.kind === 'user') {
            return (
              <div key={item.id} className={s.user}>
                {item.fileName && <Caption1>File: {item.fileName}</Caption1>}
                {item.fileName ? <br /> : null}
                {item.text}
              </div>
            );
          }
          if (item.kind === 'error') {
            return (
              <ErrorState
                key={item.id}
                error={item.error}
                onRetry={
                  item.retry
                    ? () => {
                        const retry = item.retry;
                        chatStore.remove(item.id);
                        retry?.();
                      }
                    : undefined
                }
              />
            );
          }
          return (
            <OrionMessageView
              key={item.id}
              item={item}
              contextTransitionId={transitionId}
              busy={busy}
              onSubmitForm={submitForm}
            />
          );
        })}
        {busy && (
          <div className={s.footer}>
            <Spinner size="tiny" />
            <Caption1>Orion is working...</Caption1>
          </div>
        )}
        <div ref={endRef} />
      </div>

      <div className={s.composer}>
        {showPaste && (
          <>
            <Textarea
              aria-label="Pasted email or description"
              placeholder="Paste an email, notes or a description of the transition"
              rows={6}
              resize="vertical"
              maxLength={EXTRACT_LIMIT}
              value={paste}
              onChange={(_, d) => setPaste(d.value)}
            />
            <div className={s.tools}>
              <Button
                size="small"
                appearance="primary"
                disabled={busy || !paste.trim()}
                onClick={sendPaste}
              >
                Read this
              </Button>
              <Caption1>
                {paste.length} / {EXTRACT_LIMIT}
              </Caption1>
            </div>
          </>
        )}
        <div className={s.box}>
          <Textarea
            className={s.grow}
            aria-label="Message to Orion"
            placeholder="Ask Orion, or describe what you need (Enter to send)"
            rows={2}
            resize="none"
            maxLength={EXTRACT_LIMIT}
            value={text}
            onChange={(_, d) => setText(d.value)}
            onKeyDown={onKey}
          />
          <Button
            appearance="primary"
            aria-label="Send"
            icon={<Send16Filled />}
            disabled={busy || !text.trim()}
            onClick={() => {
              if (sendText(text)) setText('');
            }}
          />
        </div>
        <div className={s.tools}>
          <Button
            size="small"
            appearance="subtle"
            aria-pressed={showPaste}
            onClick={() => setShowPaste((v) => !v)}
          >
            Paste an email or description
          </Button>
          <Button
            size="small"
            appearance="subtle"
            icon={<Attach16Regular />}
            disabled={busy}
            onClick={() => fileRef.current?.click()}
          >
            Upload a document
          </Button>
          <input
            ref={fileRef}
            type="file"
            className={s.hidden}
            accept={FILE_TYPES.join(',')}
            aria-label="Upload a document"
            onChange={(e) => {
              onFile(e.target.files?.[0]);
              e.target.value = '';
            }}
          />
        </div>
        <div className={s.footer}>
          <AiBadge />
          <Caption1>Orion recommends and drafts. People decide.</Caption1>
        </div>
      </div>
    </div>
  );
}

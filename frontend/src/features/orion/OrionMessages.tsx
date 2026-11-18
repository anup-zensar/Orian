import { useState } from 'react';
import {
  Body1,
  Button,
  Caption1,
  Field,
  Input,
  Select,
  Subtitle2,
  mergeClasses,
  makeStyles,
  tokens,
} from '@fluentui/react-components';
import { Open16Regular } from '@fluentui/react-icons';
import { useNavigate } from 'react-router';
import { AiBadge } from '../../components/AiBadge';
import { AppLink } from '../../components/AppLink';
import { SafeMarkdown } from '../leadership/SafeMarkdown';
import { ReadinessCard } from '../gates/ReadinessCard';
import { ProposalCard } from './ProposalCard';
import type { FormMessage, OrionMessage } from './api';
import type { ChatItem } from './chatStore';

const useStyles = makeStyles({
  card: {
    display: 'flex',
    flexDirection: 'column',
    gap: tokens.spacingVerticalS,
    padding: tokens.spacingVerticalM,
    borderRadius: tokens.borderRadiusMedium,
    border: `1px solid ${tokens.colorNeutralStroke2}`,
    backgroundColor: tokens.colorNeutralBackground2,
    minWidth: 0,
  },
  head: { display: 'flex', alignItems: 'center', gap: tokens.spacingHorizontalXS },
  text: { whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' },
  table: { width: '100%', borderCollapse: 'collapse', fontSize: tokens.fontSizeBase200 },
  th: {
    textAlign: 'left',
    padding: '4px 6px',
    borderBottom: `1px solid ${tokens.colorNeutralStroke2}`,
    color: tokens.colorNeutralForeground3,
    fontWeight: tokens.fontWeightSemibold,
  },
  td: {
    padding: '4px 6px',
    borderBottom: `1px solid ${tokens.colorNeutralStroke3}`,
    verticalAlign: 'top',
    overflowWrap: 'break-word',
  },
  nowrap: { whiteSpace: 'nowrap' },
  scroll: { overflowX: 'auto' },
  list: { margin: 0, paddingLeft: '18px' },
  md: {
    overflowWrap: 'anywhere',
    maxHeight: '320px',
    overflow: 'auto',
    fontSize: tokens.fontSizeBase200,
  },
  form: { display: 'flex', flexDirection: 'column', gap: tokens.spacingVerticalS },
  row: { display: 'flex', gap: tokens.spacingHorizontalS, flexWrap: 'wrap', alignItems: 'center' },
});

const cellText = (v: unknown): string => {
  if (v === null || v === undefined) return '';
  if (typeof v === 'string' || typeof v === 'number' || typeof v === 'boolean') return String(v);
  return JSON.stringify(v);
};

function OrionForm(props: {
  message: FormMessage;
  submitted: boolean;
  busy: boolean;
  contextTransitionId?: string;
  onSubmit: (values: Record<string, string>) => void;
}) {
  const s = useStyles();
  const { message: m } = props;
  const [values, setValues] = useState<Record<string, string>>(() => {
    const init: Record<string, string> = {};
    for (const f of m.fields) {
      let v = f.default ?? '';
      if (!v && f.kind === 'transition' && props.contextTransitionId) {
        const known = !f.options || f.options.some((o) => o.value === props.contextTransitionId);
        if (known) v = props.contextTransitionId;
      }
      init[f.name] = v;
    }
    return init;
  });
  const ready = m.fields.every((f) => !f.required || (values[f.name] ?? '').trim() !== '');
  const locked = props.submitted || props.busy;

  return (
    <form
      className={s.form}
      onSubmit={(e) => {
        e.preventDefault();
        if (ready && !locked) props.onSubmit(values);
      }}
    >
      <Subtitle2>{m.title}</Subtitle2>
      {m.fields.map((f) => (
        <Field key={f.name} label={f.label} required={f.required}>
          {f.options ? (
            <Select
              disabled={locked}
              value={values[f.name] ?? ''}
              onChange={(_, d) => setValues((v) => ({ ...v, [f.name]: d.value }))}
            >
              <option value="">Select...</option>
              {f.options.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </Select>
          ) : (
            <Input
              disabled={locked}
              value={values[f.name] ?? ''}
              onChange={(_, d) => setValues((v) => ({ ...v, [f.name]: d.value }))}
            />
          )}
        </Field>
      ))}
      <div className={s.row}>
        <Button appearance="primary" size="small" type="submit" disabled={!ready || locked}>
          {props.busy ? 'Working...' : m.submit_label}
        </Button>
        {props.submitted && <Caption1>Submitted</Caption1>}
      </div>
    </form>
  );
}

/** Renders one Orion output (every OrionMessage type) with the AI badge and "Orion agent" label. */
export function OrionMessageView(props: {
  item: Extract<ChatItem, { kind: 'orion' }>;
  contextTransitionId?: string;
  busy: boolean;
  onSubmitForm: (
    item: Extract<ChatItem, { kind: 'orion' }>,
    values: Record<string, string>,
  ) => void;
}) {
  const s = useStyles();
  const navigate = useNavigate();
  const { item } = props;
  const msg: OrionMessage = item.message;

  const body = () => {
    switch (msg.type) {
      case 'text':
        return <Body1 className={s.text}>{msg.text}</Body1>;
      case 'form':
        return (
          <OrionForm
            message={msg}
            submitted={!!item.submitted}
            busy={props.busy}
            contextTransitionId={props.contextTransitionId}
            onSubmit={(values) => props.onSubmitForm(item, values)}
          />
        );
      case 'readiness': {
        const tid = item.transitionId ?? props.contextTransitionId;
        return (
          <>
            <Subtitle2>Readiness for {msg.check.gate_short}</Subtitle2>
            {tid ? (
              <ReadinessCard transitionId={tid} readiness={msg.check} isCurrent />
            ) : (
              <Body1>{msg.check.narrative}</Body1>
            )}
          </>
        );
      }
      case 'table':
        return (
          <>
            <Subtitle2>{msg.title}</Subtitle2>
            <div className={s.scroll}>
              <table className={s.table}>
                <thead>
                  <tr>
                    {msg.columns.map((c) => (
                      <th key={c.key} className={s.th}>
                        {c.label}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {msg.rows.map((r, i) => (
                    <tr key={i}>
                      {msg.columns.map((c) => (
                        <td
                          key={c.key}
                          className={mergeClasses(
                            s.td,
                            /^[\d\-: ]{8,}$/.test(cellText(r[c.key])) && s.nowrap,
                          )}
                        >
                          {cellText(r[c.key])}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {msg.footnote && <Caption1>{msg.footnote}</Caption1>}
          </>
        );
      case 'drafts':
        return (
          <>
            <Subtitle2>{msg.title}</Subtitle2>
            <ul className={s.list}>
              {msg.drafts.map((d) => (
                <li key={d.id}>
                  <AppLink to={`/drafts?draft=${d.id}`}>{d.subject}</AppLink>{' '}
                  <Caption1>
                    {d.kind}
                    {d.to.length > 0 ? ` to ${d.to.join(', ')}` : ''}
                  </Caption1>
                </li>
              ))}
            </ul>
            <Caption1>Nothing is sent until a person sends the draft.</Caption1>
            <div>
              <Button
                size="small"
                icon={<Open16Regular />}
                onClick={() => navigate(msg.link || '/drafts')}
              >
                Open drafts
              </Button>
            </div>
          </>
        );
      case 'link':
        return (
          <>
            {msg.description && <Body1 className={s.text}>{msg.description}</Body1>}
            <div>
              <Button size="small" icon={<Open16Regular />} onClick={() => navigate(msg.href)}>
                {msg.label}
              </Button>
            </div>
          </>
        );
      case 'proposal':
        return <ProposalCard proposal={msg.proposal} />;
      case 'leadership':
        return (
          <>
            <div className={s.md}>
              <SafeMarkdown source={msg.update.content_md} />
            </div>
            <div>
              <Button
                size="small"
                icon={<Open16Regular />}
                onClick={() => navigate('/leadership-updates')}
              >
                Open leadership updates
              </Button>
            </div>
          </>
        );
      default:
        return null;
    }
  };

  return (
    <div className={s.card}>
      <div className={s.head}>
        <AiBadge />
        <Caption1>{msg.generated_by || 'Orion agent'}</Caption1>
      </div>
      {body()}
    </div>
  );
}

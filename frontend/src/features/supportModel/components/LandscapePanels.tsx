import {
  Badge,
  Body1,
  Button,
  Caption1,
  Dropdown,
  Field,
  Input,
  Option,
  Table,
  TableBody,
  TableCell,
  TableHeader,
  TableHeaderCell,
  TableRow,
  Textarea,
  makeStyles,
  mergeClasses,
  tokens,
} from '@fluentui/react-components';
import { AddRegular, DeleteRegular, MailRegular } from '@fluentui/react-icons';
import { SectionCard } from '../../../components/SectionCard';
import type { Contact, Landscape, Source } from '../api';

const useStyles = makeStyles({
  grid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))',
    gap: tokens.spacingHorizontalL,
    alignItems: 'start',
  },
  stack: { display: 'flex', flexDirection: 'column', gap: tokens.spacingVerticalS },
  question: {
    paddingBottom: tokens.spacingVerticalS,
    borderBottom: `1px solid ${tokens.colorNeutralStroke2}`,
  },
  row: { display: 'flex', gap: tokens.spacingHorizontalS, alignItems: 'center' },
  grow: { flexGrow: 1, minWidth: 0 },
  tableWrap: { overflowX: 'auto' },
});

type Patch = (p: Partial<Landscape>) => void;

function StringList(props: {
  items: string[];
  editable: boolean;
  label: string;
  addLabel: string;
  onChange: (items: string[]) => void;
  extra?: (index: number) => React.ReactNode;
}) {
  const s = useStyles();
  return (
    <div className={s.stack}>
      {props.items.length === 0 && <Caption1>None yet.</Caption1>}
      {props.items.map((it, i) => (
        <div key={i} className={s.row}>
          <Input
            className={s.grow}
            aria-label={`${props.label} ${i + 1}`}
            value={it}
            disabled={!props.editable}
            onChange={(_, d) => props.onChange(props.items.map((x, j) => (j === i ? d.value : x)))}
          />
          {props.extra?.(i)}
          {props.editable && (
            <Button
              appearance="subtle"
              icon={<DeleteRegular />}
              aria-label={`Remove ${props.label} ${i + 1}`}
              onClick={() => props.onChange(props.items.filter((_, j) => j !== i))}
            />
          )}
        </div>
      ))}
      {props.editable && (
        <div>
          <Button icon={<AddRegular />} onClick={() => props.onChange([...props.items, ''])}>
            {props.addLabel}
          </Button>
        </div>
      )}
    </div>
  );
}

const SOURCE_TYPES: Source['type'][] = ['diagram', 'recording', 'document'];

/** Side panels of the review step: hosting & vendor, responsibilities, tiers, contacts & SLA,
 * open questions, sources. */
export function LandscapePanels(props: {
  landscape: Landscape;
  editable: boolean;
  onPatch: Patch;
  /** Draft question i to the architect; undefined reason = allowed. */
  onDraftQuestion: (index: number) => void;
  draftDisabledReason: string | null;
  drafting: boolean;
}) {
  const s = useStyles();
  const { landscape: l, editable, onPatch } = props;

  const setContact = (i: number, patch: Partial<Contact>) =>
    onPatch({ contacts: l.contacts.map((c, j) => (j === i ? { ...c, ...patch } : c)) });
  const setQuestion = (i: number, patch: Partial<Landscape['open_questions'][number]>) =>
    onPatch({
      open_questions: l.open_questions.map((q, j) => (j === i ? { ...q, ...patch } : q)),
    });
  const setSource = (i: number, patch: Partial<Source>) =>
    onPatch({ sources: l.sources.map((c, j) => (j === i ? { ...c, ...patch } : c)) });

  return (
    <div className={s.stack}>
      <div className={s.grid}>
        <SectionCard title="Hosting and vendor">
          <Field label="Hosting">
            <Input
              value={l.hosting}
              disabled={!editable}
              onChange={(_, d) => onPatch({ hosting: d.value })}
            />
          </Field>
          <Field label="Vendor">
            <Input
              value={l.vendor}
              disabled={!editable}
              onChange={(_, d) => onPatch({ vendor: d.value })}
            />
          </Field>
          <Field label="Supplier">
            <Input
              value={l.supplier}
              disabled={!editable}
              onChange={(_, d) => onPatch({ supplier: d.value })}
            />
          </Field>
        </SectionCard>

        <SectionCard title="Vendor and supplier responsibilities">
          <StringList
            items={l.vendor_responsibilities}
            editable={editable}
            label="Responsibility"
            addLabel="Add responsibility"
            onChange={(vendor_responsibilities) => onPatch({ vendor_responsibilities })}
          />
        </SectionCard>

        <SectionCard title="Support tiers">
          {(['L1', 'L2', 'L3'] as const).map((t) => (
            <Field key={t} label={t}>
              <Textarea
                rows={2}
                value={l.support_tiers[t]}
                disabled={!editable}
                onChange={(_, d) =>
                  onPatch({ support_tiers: { ...l.support_tiers, [t]: d.value } })
                }
              />
            </Field>
          ))}
        </SectionCard>
      </div>

      <SectionCard
        title="Contacts and SLA"
        actions={
          editable ? (
            <Button
              icon={<AddRegular />}
              onClick={() =>
                onPatch({ contacts: [...l.contacts, { party: '', role: '', email: '', sla: '' }] })
              }
            >
              Add contact
            </Button>
          ) : undefined
        }
      >
        {l.contacts.length === 0 ? (
          <Caption1>No contacts yet.</Caption1>
        ) : (
          <div className={s.tableWrap}>
            <Table aria-label="Contacts and SLA" size="small">
              <TableHeader>
                <TableRow>
                  <TableHeaderCell>Party</TableHeaderCell>
                  <TableHeaderCell>Role</TableHeaderCell>
                  <TableHeaderCell>Email</TableHeaderCell>
                  <TableHeaderCell>SLA</TableHeaderCell>
                  {editable && <TableHeaderCell />}
                </TableRow>
              </TableHeader>
              <TableBody>
                {l.contacts.map((c, i) => (
                  <TableRow key={i}>
                    {(['party', 'role', 'email', 'sla'] as const).map((k) => (
                      <TableCell key={k}>
                        <Input
                          size="small"
                          aria-label={`${k} of contact ${i + 1}`}
                          value={c[k]}
                          disabled={!editable}
                          contentBefore={k === 'email' ? <MailRegular /> : undefined}
                          onChange={(_, d) => setContact(i, { [k]: d.value })}
                        />
                      </TableCell>
                    ))}
                    {editable && (
                      <TableCell>
                        <Button
                          appearance="subtle"
                          icon={<DeleteRegular />}
                          aria-label={`Remove contact ${i + 1}`}
                          onClick={() =>
                            onPatch({ contacts: l.contacts.filter((_, j) => j !== i) })
                          }
                        />
                      </TableCell>
                    )}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </SectionCard>

      <div className={s.grid}>
        <SectionCard title="Open questions">
          <div className={s.stack}>
            {l.open_questions.length === 0 && <Caption1>None yet.</Caption1>}
            {l.open_questions.map((q, i) => (
              <div key={i} className={mergeClasses(s.stack, s.question)}>
                <div className={s.row}>
                  <Input
                    className={s.grow}
                    aria-label={`Question ${i + 1}`}
                    value={q.question}
                    disabled={!editable}
                    onChange={(_, d) => setQuestion(i, { question: d.value })}
                  />
                  {q.answer.trim() && (
                    <Badge appearance="tint" color="success">
                      Answered
                    </Badge>
                  )}
                  {editable && (
                    <Button
                      appearance="subtle"
                      icon={<DeleteRegular />}
                      aria-label={`Remove Question ${i + 1}`}
                      onClick={() =>
                        onPatch({ open_questions: l.open_questions.filter((_, j) => j !== i) })
                      }
                    />
                  )}
                </div>
                <Textarea
                  aria-label={`Answer to question ${i + 1}`}
                  placeholder={editable ? 'Answer (optional)' : 'No answer yet'}
                  value={q.answer}
                  disabled={!editable}
                  resize="vertical"
                  rows={2}
                  onChange={(_, d) => setQuestion(i, { answer: d.value })}
                />
                <div>
                  <Button
                    size="small"
                    disabled={!!props.draftDisabledReason || props.drafting || !q.question}
                    title={props.draftDisabledReason ?? undefined}
                    onClick={() => props.onDraftQuestion(i)}
                  >
                    Draft question to architect
                  </Button>
                </div>
              </div>
            ))}
            {editable && (
              <div>
                <Button
                  icon={<AddRegular />}
                  onClick={() =>
                    onPatch({ open_questions: [...l.open_questions, { question: '', answer: '' }] })
                  }
                >
                  Add question
                </Button>
              </div>
            )}
          </div>
          {props.draftDisabledReason && <Caption1>{props.draftDisabledReason}</Caption1>}
        </SectionCard>

        <SectionCard
          title="Sources"
          actions={
            editable ? (
              <Button
                icon={<AddRegular />}
                onClick={() => onPatch({ sources: [...l.sources, { type: 'document', ref: '' }] })}
              >
                Add source
              </Button>
            ) : undefined
          }
        >
          {l.sources.length === 0 && <Body1>No sources recorded.</Body1>}
          {l.sources.map((src, i) => (
            <div key={i} className={s.row}>
              <Dropdown
                aria-label={`Source ${i + 1} type`}
                style={{ minWidth: 130 }}
                value={src.type}
                selectedOptions={[src.type]}
                disabled={!editable}
                onOptionSelect={(_, d) => setSource(i, { type: d.optionValue as Source['type'] })}
              >
                {SOURCE_TYPES.map((t) => (
                  <Option key={t} value={t}>
                    {t}
                  </Option>
                ))}
              </Dropdown>
              <Input
                className={s.grow}
                aria-label={`Source ${i + 1} reference`}
                value={src.ref}
                disabled={!editable}
                onChange={(_, d) => setSource(i, { ref: d.value })}
              />
              {editable && (
                <Button
                  appearance="subtle"
                  icon={<DeleteRegular />}
                  aria-label={`Remove source ${i + 1}`}
                  onClick={() => onPatch({ sources: l.sources.filter((_, j) => j !== i) })}
                />
              )}
            </div>
          ))}
        </SectionCard>
      </div>
    </div>
  );
}

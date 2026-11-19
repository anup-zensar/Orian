import { useEffect, useState } from 'react';
import {
  Button,
  Checkbox,
  Field,
  Input,
  Select,
  Switch,
  Textarea,
  makeStyles,
  tokens,
} from '@fluentui/react-components';
import { LockClosed16Regular, Warning16Filled } from '@fluentui/react-icons';
import { ErrorState } from '../../../components/ErrorState';
import { LoadingState } from '../../../components/LoadingState';
import { SectionCard } from '../../../components/SectionCard';
import type { OptionItemAdmin, OptionListAdmin } from '../../../api/types';
import { useReference } from '../../reference/api';
import { useRoles } from '../../reference/options';
import { useLeaveGuard } from '../../ocet/useLeaveGuard';
import { useOptionItemsAdmin, useOptionListsAdmin, usePutOptionItems } from '../catalogApi';
import { DisabledReason } from '../components/DisabledReason';
import { useDiscardGuard } from '../components/DiscardGuard';
import { ReorderableTable, type ReorderColumn } from '../components/ReorderableTable';
import { UsedByBadge } from '../components/UsedByBadge';
import { useSuccessToast } from '../useSavedToast';
import { NewListDialog } from './NewListDialog';

type MetaField = OptionListAdmin['meta_fields'][number];

/** One value of a list while it is being edited. */
interface Row {
  key: string; // stable React key
  value: string; // the stored value; empty for a new row until it is saved
  isNew: boolean;
  label: string;
  description: string;
  meta: Record<string, unknown>;
  active: boolean;
  usedBy: number;
}

const COLORS = [
  'brand',
  'danger',
  'important',
  'informative',
  'severe',
  'subtle',
  'success',
  'warning',
];

/** Plain words for the values of the "Needs" column on evidence types. */
const CHOICE_LABEL: Record<string, string> = {
  file: 'A file upload',
  url: 'A link',
  text: 'Typed text',
  none: 'Nothing',
};

const useStyles = makeStyles({
  bar: { display: 'flex', gap: tokens.spacingHorizontalM, alignItems: 'end', flexWrap: 'wrap' },
  lock: { display: 'flex', alignItems: 'center', gap: tokens.spacingHorizontalXS },
  small: { color: tokens.colorNeutralForeground3 },
  warn: {
    display: 'flex',
    alignItems: 'center',
    gap: tokens.spacingHorizontalXS,
    color: tokens.colorPaletteDarkOrangeForeground1,
    fontSize: tokens.fontSizeBase200,
  },
  input: { minWidth: '140px', width: '100%' },
});

const toRows = (items: OptionItemAdmin[]): Row[] =>
  items.map((i) => ({
    key: i.value,
    value: i.value,
    isNew: false,
    label: i.label,
    description: i.description ?? '',
    meta: (i.meta ?? {}) as Record<string, unknown>,
    active: i.active ?? true,
    usedBy: i.used_by ?? 0,
  }));

/** A cell editing one meta value (colour, number, role ...) according to the list's declared type. */
function MetaInput(props: {
  field: MetaField;
  value: unknown;
  onChange: (value: unknown) => void;
}) {
  const s = useStyles();
  const { field, value, onChange } = props;
  const aria = field.label || field.key;
  const roles = useRoles();
  const { data: ref } = useReference();
  const text = value == null ? '' : String(value);

  switch (field.type) {
    case 'boolean':
      return (
        <Checkbox
          aria-label={aria}
          checked={value === true}
          onChange={(_, d) => onChange(d.checked)}
        />
      );
    case 'number':
      return (
        <Input
          aria-label={aria}
          className={s.input}
          type="number"
          value={text}
          onChange={(_, d) => onChange(d.value === '' ? null : Number(d.value))}
        />
      );
    case 'list':
      return (
        <Input
          aria-label={aria}
          className={s.input}
          placeholder="comma separated"
          value={Array.isArray(value) ? value.join(', ') : text}
          onChange={(_, d) =>
            onChange(
              d.value
                .split(',')
                .map((x) => x.trim())
                .filter(Boolean),
            )
          }
        />
      );
    case 'token':
    case 'select':
    case 'role':
    case 'gate': {
      const choices: { value: string; label: string }[] =
        field.type === 'token'
          ? COLORS.map((c) => ({ value: c, label: c }))
          : field.type === 'select'
            ? field.options.map((o) => ({ value: o, label: CHOICE_LABEL[o] ?? o }))
            : field.type === 'role'
              ? roles.map((r) => ({ value: r.code, label: r.label }))
              : (ref?.gates ?? []).map((g) => ({ value: g.code, label: g.short }));
      return (
        <Select aria-label={aria} value={text} onChange={(_, d) => onChange(d.value || null)}>
          {!choices.some((c) => c.value === 'none') && <option value="">None</option>}
          {choices.map((c) => (
            <option key={c.value} value={c.value}>
              {c.label}
            </option>
          ))}
        </Select>
      );
    }
    default:
      return (
        <Input
          aria-label={aria}
          className={s.input}
          value={text}
          onChange={(_, d) => onChange(d.value)}
        />
      );
  }
}

/** Edits the values of one list: label, order, extra columns, active. Structural lists: label only. */
function ListEditor(props: {
  list: OptionListAdmin;
  items: OptionItemAdmin[];
  onDirty: (dirty: boolean) => void;
}) {
  const s = useStyles();
  const { list, onDirty } = props;
  const save = usePutOptionItems();
  const ok = useSuccessToast();
  const [initial] = useState(() => toRows(props.items));
  const [rows, setRows] = useState<Row[]>(initial);
  const [seq, setSeq] = useState(0);
  const dirty = JSON.stringify(rows) !== JSON.stringify(initial);
  useEffect(() => {
    onDirty(dirty);
    return () => onDirty(false); // an unmounted editor holds no unsaved edits
  }, [dirty, onDirty]);

  const structural = list.structural;
  // Lists whose values carry an answer (the glossary) get a text column; it must not stay empty.
  const hasDescriptions = initial.some((r) => r.description.trim() !== '');
  const lockText =
    list.lock_reason ?? 'Behaviour depends on these values - only the labels can change.';
  const patch = (key: string, p: Partial<Row>) =>
    setRows((rs) => rs.map((r) => (r.key === key ? { ...r, ...p } : r)));
  const setMeta = (key: string, metaKey: string, v: unknown) =>
    setRows((rs) =>
      rs.map((r) => (r.key === key ? { ...r, meta: { ...r.meta, [metaKey]: v } } : r)),
    );

  const valueOf = (r: Row) => (r.isNew ? r.label.trim() : r.value);
  const values = rows.map((r) => valueOf(r).toLowerCase());
  const problem = rows.some((r) => !r.label.trim())
    ? 'Every value needs a label.'
    : hasDescriptions && rows.some((r) => !r.description.trim())
      ? 'Every term needs a description. Orion uses it as the answer.'
      : new Set(values).size !== values.length
        ? 'Two values have the same name. Rename one of them.'
        : null;

  const add = () => {
    setRows((rs) => [
      ...rs,
      {
        key: `new-${seq}`,
        value: '',
        isNew: true,
        label: '',
        description: '',
        meta: {},
        active: true,
        usedBy: 0,
      },
    ]);
    setSeq((n) => n + 1);
  };

  const submit = () =>
    save.mutate(
      {
        key: list.key,
        items: rows.map((r) => ({
          value: valueOf(r),
          label: r.label.trim(),
          description: r.description,
          meta: r.meta,
          active: r.active,
        })),
      },
      { onSuccess: () => ok('Saved - applies immediately') },
    );

  const columns: ReorderColumn<Row>[] = [
    {
      header: 'Label',
      width: 220,
      render: (r) => (
        <div>
          <Input
            aria-label={`Label of ${r.value || 'new value'}`}
            className={s.input}
            title={r.isNew ? undefined : `Code: ${r.value}`}
            value={r.label}
            onChange={(_, d) => patch(r.key, { label: d.value })}
          />
          {!r.active && r.usedBy > 0 && (
            <div className={s.warn} role="status">
              <Warning16Filled />
              {r.usedBy} existing records use this value. It stays on them, but new records can no
              longer pick it.
            </div>
          )}
        </div>
      ),
    },
    ...(hasDescriptions
      ? [
          {
            header: 'Description (the answer Orion gives)',
            width: 320,
            render: (r: Row) => (
              <Textarea
                aria-label={`Description of ${r.label || 'new term'}`}
                value={r.description}
                style={{ width: '100%' }}
                rows={4}
                onChange={(_, d) => patch(r.key, { description: d.value })}
              />
            ),
          },
        ]
      : []),
    ...(structural
      ? []
      : list.meta_fields.map<ReorderColumn<Row>>((mf) => ({
          header: mf.label || mf.key,
          render: (r) => (
            <MetaInput
              field={mf}
              value={r.meta[mf.key]}
              onChange={(v) => setMeta(r.key, mf.key, v)}
            />
          ),
        }))),
    {
      header: 'Active',
      render: (r) => (
        <DisabledReason reason={structural ? lockText : null}>
          <Switch
            aria-label={`Active: ${r.label || r.value}`}
            checked={r.active}
            disabled={structural}
            onChange={(_, d) => patch(r.key, { active: d.checked })}
          />
        </DisabledReason>
      ),
    },
    {
      header: 'Used by',
      render: (r) => (r.isNew ? '-' : <UsedByBadge count={r.usedBy} />),
    },
    {
      header: '',
      render: (r) =>
        r.isNew ? (
          <Button size="small" onClick={() => setRows((rs) => rs.filter((x) => x.key !== r.key))}>
            Remove
          </Button>
        ) : null,
    },
  ];

  return (
    <>
      {structural && (
        <div className={s.lock}>
          <LockClosed16Regular aria-label="Locked list" />
          {lockText}
        </div>
      )}
      <ReorderableTable
        ariaLabel={`Values of ${list.label}`}
        rows={rows}
        rowKey={(r) => r.key}
        columns={columns}
        onReorder={setRows}
        reorderLockedReason={structural ? lockText : null}
      />
      {save.isError && <ErrorState error={save.error} />}
      {problem && dirty && <div className={s.warn}>{problem}</div>}
      <div className={s.bar}>
        <DisabledReason reason={structural ? lockText : null}>
          <Button onClick={add} disabled={structural}>
            Add value
          </Button>
        </DisabledReason>
        <Button
          appearance="primary"
          onClick={submit}
          disabled={!dirty || save.isPending || !!problem}
        >
          {save.isPending ? 'Saving...' : 'Save list'}
        </Button>
        <Button disabled={!dirty} onClick={() => setRows(initial)}>
          Discard changes
        </Button>
      </div>
    </>
  );
}

/** Pick a dropdown list and edit its values. */
export function DropdownListsPanel() {
  const s = useStyles();
  const lists = useOptionListsAdmin();
  const [picked, setPicked] = useState('');
  const [adding, setAdding] = useState(false);
  const [dirty, setDirty] = useState(false);
  const { guard, dialog } = useDiscardGuard(dirty);
  const leaveDialog = useLeaveGuard(dirty);

  const all = lists.data ?? [];
  const list = all.find((l) => l.key === picked) ?? all[0];
  const items = useOptionItemsAdmin(list?.key ?? '');
  // Lists that only drive Orion's own behaviour (labels only) go last, under one heading.
  const INTERNAL = 'Used internally (labels only)';
  const groupOf = (l: OptionListAdmin) => (l.structural ? INTERNAL : l.group || 'Other');
  const groups = [...new Set(all.map(groupOf))].sort(
    (a, b) => Number(a === INTERNAL) - Number(b === INTERNAL),
  );

  return (
    <SectionCard
      title="Dropdown lists"
      actions={<Button onClick={() => guard(() => setAdding(true))}>New list</Button>}
    >
      {lists.isLoading ? (
        <LoadingState rows={5} />
      ) : lists.isError ? (
        <ErrorState error={lists.error} onRetry={() => void lists.refetch()} />
      ) : !list ? null : (
        <>
          <div className={s.bar}>
            <Field label="List">
              <Select
                value={list.key}
                onChange={(_, d) => guard(() => setPicked(d.value))}
                style={{ minWidth: 260 }}
              >
                {groups.map((g) => (
                  <optgroup key={g} label={g}>
                    {all
                      .filter((l) => groupOf(l) === g)
                      .map((l) => (
                        <option key={l.key} value={l.key}>
                          {l.label}
                        </option>
                      ))}
                  </optgroup>
                ))}
              </Select>
            </Field>
            <div className={s.small}>{list.description}</div>
          </div>
          {items.isLoading ? (
            <LoadingState rows={5} />
          ) : items.isError ? (
            <ErrorState error={items.error} onRetry={() => void items.refetch()} />
          ) : items.data ? (
            <ListEditor
              key={`${list.key}-${items.dataUpdatedAt}`}
              list={items.data.option_list}
              items={items.data.items}
              onDirty={setDirty}
            />
          ) : null}
        </>
      )}
      {adding && <NewListDialog onCreated={setPicked} onClose={() => setAdding(false)} />}
      {dialog}
      {leaveDialog}
    </SectionCard>
  );
}

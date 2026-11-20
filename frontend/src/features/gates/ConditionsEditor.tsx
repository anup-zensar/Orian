import {
  Button,
  Combobox,
  Field,
  Input,
  Option,
  Select,
  makeStyles,
  tokens,
} from '@fluentui/react-components';
import { Add16Regular, Delete16Regular } from '@fluentui/react-icons';
import { FormGrid } from '../../components/layout/FormGrid';
import { useReference } from '../reference/api';
import { useUsers } from '../users/api';
import type { ConditionIn } from './api';
import { emptyCondition } from './conditionUtils';

const useStyles = makeStyles({
  root: { display: 'flex', flexDirection: 'column', gap: tokens.spacingVerticalM },
  row: {
    display: 'flex',
    gap: tokens.spacingHorizontalS,
    alignItems: 'flex-start',
    padding: tokens.spacingVerticalS,
    border: `1px solid ${tokens.colorNeutralStroke2}`,
    borderRadius: tokens.borderRadiusMedium,
    minWidth: 0,
  },
  fields: { flex: '1 1 0', minWidth: 0 },
  remove: { flexShrink: 0, marginTop: '22px' },
});

/** Conditions editor for Proceed / Approve with conditions: item, owner, due gate (later), text. */
export function ConditionsEditor(props: {
  gate: string;
  rows: ConditionIn[];
  onChange: (rows: ConditionIn[]) => void;
  /** Items the person is likely to cover (blocking items, critical gaps). */
  suggestions: Array<{ id: string; title: string }>;
}) {
  const s = useStyles();
  const ref = useReference();
  const users = useUsers();
  const gates = ref.data?.gates ?? [];
  const order = gates.find((g) => g.code === props.gate)?.order ?? 0;
  const laterGates = gates.filter((g) => g.order > order);

  const update = (i: number, patch: Partial<ConditionIn>) =>
    props.onChange(props.rows.map((r, idx) => (idx === i ? { ...r, ...patch } : r)));

  return (
    <div className={s.root}>
      {props.rows.map((row, i) => (
        <div key={i} className={s.row}>
          <FormGrid minColWidth={180} className={s.fields}>
            <Field label="Item" required>
              <Combobox
                freeform
                placeholder="Playbook item id"
                value={row.item_id}
                selectedOptions={row.item_id ? [row.item_id] : []}
                onChange={(e) => update(i, { item_id: e.target.value })}
                onOptionSelect={(_, d) => update(i, { item_id: d.optionValue ?? '' })}
              >
                {props.suggestions.map((sg) => (
                  <Option key={sg.id} value={sg.id} text={sg.id}>
                    {sg.id} · {sg.title}
                  </Option>
                ))}
              </Combobox>
            </Field>
            <Field label="Owner" required>
              <Select
                value={row.owner_user_id}
                onChange={(_, d) => update(i, { owner_user_id: d.value })}
              >
                <option value="">Select owner</option>
                {(users.data ?? []).map((u) => (
                  <option key={u.id} value={u.id}>
                    {u.name}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="Due gate (later than this gate)" required>
              <Select value={row.due_gate} onChange={(_, d) => update(i, { due_gate: d.value })}>
                <option value="">Select gate</option>
                {laterGates.map((g) => (
                  <option key={g.code} value={g.code}>
                    {g.short} · {g.label}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="Condition text" required>
              <Input value={row.text} onChange={(_, d) => update(i, { text: d.value })} />
            </Field>
          </FormGrid>
          <Button
            className={s.remove}
            appearance="subtle"
            icon={<Delete16Regular />}
            aria-label="Remove condition"
            onClick={() => props.onChange(props.rows.filter((_, idx) => idx !== i))}
          />
        </div>
      ))}
      <div>
        <Button
          icon={<Add16Regular />}
          onClick={() => props.onChange([...props.rows, emptyCondition()])}
        >
          Add condition
        </Button>
      </div>
    </div>
  );
}

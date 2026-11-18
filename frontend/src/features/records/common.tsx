// Small shared building blocks for the records tabs.
import { useState, type ReactNode } from 'react';
import { Button, Field, Input, Select, Tooltip } from '@fluentui/react-components';
import { useUsers } from '../users/api';
import { useReference } from '../reference/api';
import type { Item } from './api';

/** A button that is disabled with a tooltip reason when `reason` is non-empty. */
export function GuardedButton(props: {
  reason?: string | null;
  onClick?: () => void;
  children: ReactNode;
  appearance?: 'primary' | 'secondary' | 'subtle' | 'outline';
  size?: 'small' | 'medium';
  disabled?: boolean;
  type?: 'button' | 'submit';
}) {
  const blocked = !!props.reason;
  const btn = (
    <Button
      appearance={props.appearance ?? 'secondary'}
      size={props.size}
      type={props.type ?? 'button'}
      disabled={props.disabled}
      disabledFocusable={blocked}
      onClick={blocked ? undefined : props.onClick}
    >
      {props.children}
    </Button>
  );
  if (!blocked) return btn;
  return (
    <Tooltip content={props.reason ?? ''} relationship="description">
      {btn}
    </Tooltip>
  );
}

/** Owner picker over the demo users. */
export function OwnerSelect(props: {
  label: string;
  value: string;
  onChange: (id: string) => void;
  required?: boolean;
  allowEmpty?: boolean;
}) {
  const users = useUsers();
  return (
    <Field label={props.label} required={props.required}>
      <Select value={props.value} onChange={(_, d) => props.onChange(d.value)}>
        {(props.allowEmpty || !props.value) && (
          <option value="">{props.allowEmpty ? 'Unassigned' : 'Select a person'}</option>
        )}
        {(users.data ?? []).map((u) => (
          <option key={u.id} value={u.id}>
            {u.name} ({u.role_label || u.role})
          </option>
        ))}
      </Select>
    </Field>
  );
}

/** Checklist item picker (value = playbook item id such as S3-019). */
export function ItemSelect(props: {
  label: string;
  items: Item[] | undefined;
  value: string;
  onChange: (id: string) => void;
  required?: boolean;
  emptyLabel?: string;
}) {
  const [search, setSearch] = useState('');
  const all = props.items ?? [];
  const q = search.trim().toLowerCase();
  // keep the selected item in the list even when the filter would hide it
  const shown = q
    ? all.filter(
        (i) =>
          i.item_id === props.value ||
          i.item_id.toLowerCase().includes(q) ||
          i.title.toLowerCase().includes(q),
      )
    : all;
  return (
    <Field label={props.label} required={props.required}>
      {all.length > 20 && (
        <Input
          size="small"
          aria-label={`Filter ${props.label.toLowerCase()} list`}
          placeholder={`Type to filter ${all.length} items (id or title)`}
          value={search}
          onChange={(_, d) => setSearch(d.value)}
        />
      )}
      <Select value={props.value} onChange={(_, d) => props.onChange(d.value)}>
        <option value="">{props.emptyLabel ?? 'No linked item'}</option>
        {shown.map((i) => (
          <option key={i.item_id} value={i.item_id}>
            {i.item_id} – {i.title}
          </option>
        ))}
      </Select>
    </Field>
  );
}

/** Gate picker from reference data. */
export function GateSelect(props: {
  label: string;
  value: string;
  onChange: (code: string) => void;
}) {
  const ref = useReference();
  return (
    <Field label={props.label} required>
      <Select value={props.value} onChange={(_, d) => props.onChange(d.value)}>
        {(ref.data?.gates ?? []).map((g) => (
          <option key={g.code} value={g.code}>
            {g.short} – {g.label}
          </option>
        ))}
      </Select>
    </Field>
  );
}

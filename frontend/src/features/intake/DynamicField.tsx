// One custom field of the "Additional details" section (CR-01). The Admin defines these fields in
// Forms & dropdowns; this component draws any of the eight field types so a new field needs no code.
import type { ReactNode } from 'react';
import { Checkbox, Field, Input, Select, Switch, Textarea } from '@fluentui/react-components';
import type { IntakeFieldRef, User } from '../../api/types';
import { useOptions } from '../reference/options';
import type { FieldValue } from './fieldValues';

interface Props {
  field: IntakeFieldRef;
  value: FieldValue | undefined;
  onChange: (value: FieldValue) => void;
  /** People to choose from for a "user" field (the field's option list names the role). */
  users: User[];
  required?: boolean;
  disabled?: boolean;
  error?: string;
  /** Extra marker after the label (the Orion badge). */
  marker?: ReactNode;
  /** Replaces the help text, e.g. "Orion could not find this". */
  hint?: ReactNode;
}

/** A labelled input for one custom field. */
export function DynamicField(props: Props) {
  const { field, value, onChange, users, disabled } = props;
  const current = Array.isArray(value) ? value.join('|') : String(value ?? '');
  const options = useOptions(field.option_list ?? '', {
    include: field.type === 'select' || field.type === 'multiselect' ? current.split('|') : null,
  });
  const people = users.filter((u) => !field.option_list || u.role === field.option_list);
  const text = typeof value === 'string' ? value : '';
  const help = props.hint ?? (field.help || undefined);

  let input: ReactNode;
  switch (field.type) {
    case 'textarea':
      input = (
        <Textarea
          rows={3}
          resize="vertical"
          disabled={disabled}
          maxLength={field.max_length ?? undefined}
          value={text}
          onChange={(_, d) => onChange(d.value)}
        />
      );
      break;
    case 'number':
      input = (
        <Input
          type="number"
          disabled={disabled}
          min={field.min ?? undefined}
          max={field.max ?? undefined}
          value={text}
          onChange={(_, d) => onChange(d.value)}
        />
      );
      break;
    case 'date':
      input = (
        <Input
          type="date"
          disabled={disabled}
          value={text}
          onChange={(_, d) => onChange(d.value)}
        />
      );
      break;
    case 'select':
      input = (
        <Select disabled={disabled} value={text} onChange={(_, d) => onChange(d.value)}>
          <option value="">Select…</option>
          {options.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </Select>
      );
      break;
    case 'user':
      input = (
        <Select disabled={disabled} value={text} onChange={(_, d) => onChange(d.value)}>
          <option value="">Select…</option>
          {people.map((u) => (
            <option key={u.id} value={u.id}>
              {u.name}
            </option>
          ))}
        </Select>
      );
      break;
    case 'multiselect': {
      const chosen = Array.isArray(value) ? value : [];
      input = (
        <div role="group" aria-label={field.label}>
          {options.map((o) => (
            <Checkbox
              key={o.value}
              disabled={disabled}
              label={o.label}
              checked={chosen.includes(o.value)}
              onChange={(_, d) =>
                onChange(d.checked ? [...chosen, o.value] : chosen.filter((v) => v !== o.value))
              }
            />
          ))}
        </div>
      );
      break;
    }
    case 'boolean':
      input = (
        <Switch
          disabled={disabled}
          checked={value === true}
          label={value === true ? 'Yes' : 'No'}
          onChange={(_, d) => onChange(d.checked)}
        />
      );
      break;
    default:
      input = (
        <Input
          disabled={disabled}
          maxLength={field.max_length ?? undefined}
          value={text}
          onChange={(_, d) => onChange(d.value)}
        />
      );
  }

  return (
    <Field
      label={
        <>
          {field.label}
          {props.marker}
        </>
      }
      hint={help ? { children: help } : undefined}
      required={props.required}
      validationMessage={props.error}
      validationState={props.error ? 'error' : 'none'}
    >
      {input}
    </Field>
  );
}

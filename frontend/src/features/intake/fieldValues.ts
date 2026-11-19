// Plain helpers for custom-field values (CR-01): empty values, conversion to and from what the API
// stores, and read-only display text. The input itself is drawn by DynamicField.
import type { IntakeFieldRef } from '../../api/types';

/** What a custom field holds in the form: text, a list (multiselect) or a yes/no. */
export type FieldValue = string | string[] | boolean;

/** The value of an empty field of this type (the form starts with it). */
export function emptyValue(field: IntakeFieldRef): FieldValue {
  if (field.type === 'multiselect') return [];
  if (field.type === 'boolean') return false;
  return '';
}

/** True when the person has not filled the field in (a switch is always "filled in"). */
export function isEmptyValue(field: IntakeFieldRef, value: FieldValue | undefined): boolean {
  if (field.type === 'boolean') return false;
  if (Array.isArray(value)) return value.length === 0;
  return String(value ?? '').trim() === '';
}

/** Turn a value stored by the API (any JSON) into a form value; unknown shapes become empty. */
export function fromApiValue(field: IntakeFieldRef, raw: unknown): FieldValue {
  if (raw == null) return emptyValue(field);
  if (field.type === 'multiselect') return Array.isArray(raw) ? raw.map(String) : [String(raw)];
  if (field.type === 'boolean') return raw === true || raw === 'true';
  return String(raw);
}

/** Turn a form value into what the API stores; null means "nothing entered, send nothing". */
export function toApiValue(
  field: IntakeFieldRef,
  value: FieldValue | undefined,
): string | number | boolean | string[] | null {
  if (field.type === 'boolean') return value === true;
  if (value === undefined || isEmptyValue(field, value)) return null;
  if (field.type === 'number') return Number(value);
  return Array.isArray(value) ? value : String(value).trim();
}

/** Plain-text version of a stored value for read-only display (labels instead of codes). */
export function displayValue(
  field: IntakeFieldRef,
  raw: unknown,
  labelOf: (value: string) => string,
): string {
  if (raw == null || raw === '') return '-';
  if (field.type === 'boolean') return raw === true || raw === 'true' ? 'Yes' : 'No';
  if (Array.isArray(raw))
    return raw.length === 0 ? '-' : raw.map((v) => labelOf(String(v))).join(', ');
  return field.type === 'select' || field.type === 'user' ? labelOf(String(raw)) : String(raw);
}

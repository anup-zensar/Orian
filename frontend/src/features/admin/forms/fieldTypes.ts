import type { IntakeFieldAdmin } from '../../../api/types';

export type FieldType = IntakeFieldAdmin['type'];
export type RequiredMode = IntakeFieldAdmin['required_mode'];

/** Plain-language names of the field types. */
export const TYPE_TEXT: Record<FieldType, string> = {
  text: 'Short text',
  textarea: 'Long text',
  number: 'Number',
  date: 'Date',
  select: 'Pick one from a list',
  multiselect: 'Pick several from a list',
  boolean: 'Yes / no',
  user: 'A person',
};

export const typeText = (t: string) => TYPE_TEXT[t as FieldType] ?? t;

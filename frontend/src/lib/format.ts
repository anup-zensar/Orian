// Small formatting helpers shared by the M2 pages.
import dayjs from 'dayjs';
import type { Rag } from '../theme/tokens';

/** The API sends RAG as a plain string; anything unknown is shown as "Not started" (A-34). */
export function toRag(value: string | null | undefined): Rag {
  return value === 'Red' || value === 'Amber' || value === 'Green' ? value : 'Grey';
}

export function plural(n: number, singular: string, pluralForm = `${singular}s`): string {
  return `${n} ${n === 1 ? singular : pluralForm}`;
}

/** "in 4 days" / "today" / "3 days overdue" (spec 8.2 "Next decision"). */
export function daysLabel(days: number | null | undefined): string {
  if (days === null || days === undefined) return 'No date set';
  if (days === 0) return 'today';
  if (days > 0) return `in ${plural(days, 'day')}`;
  return `${plural(-days, 'day')} overdue`;
}

export function formatDate(date: string | null | undefined): string {
  return date ? dayjs(date).format('D MMM YYYY') : '–';
}

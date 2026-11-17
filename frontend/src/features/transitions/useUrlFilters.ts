// The URL query string is the single source of truth for register filters (spec 8.2, 12): deep
// links work and the browser back button restores the previous filter set. Values the API would
// not understand (unknown RAG or gate, non-integer numbers) are dropped on read, removed from the
// URL and reported in `notice`, so the selects never contradict the URL.
import { useCallback, useEffect, useMemo } from 'react';
import { useLocation, useSearchParams } from 'react-router';
import { useReference } from '../reference/api';

/** Keys of the generated TransitionFilters that the UI can set (mine = "Only mine"). */
export const FILTER_KEYS = [
  'portfolio',
  'region',
  'gate',
  'rag',
  'type',
  'q',
  'status',
  'decision_within_days',
  'has_critical',
  'compliance_below',
  'mine',
] as const;

export type FilterKey = (typeof FILTER_KEYS)[number];
export type UrlFilters = Partial<Record<FilterKey, string>>;

const RAGS = ['Red', 'Amber', 'Green', 'Grey'];
const STATUSES = ['Active', 'Closed'];
const INTEGER = /^\d+$/;

/** Is ``value`` acceptable for ``key``? ``gates`` is undefined until the reference data loads. */
function isValid(key: FilterKey, value: string, gates: string[] | undefined): boolean {
  switch (key) {
    case 'rag':
      return RAGS.includes(value);
    case 'status':
      return STATUSES.includes(value);
    case 'gate':
      return !gates || gates.includes(value);
    case 'decision_within_days':
    case 'compliance_below':
      return INTEGER.test(value);
    case 'has_critical':
    case 'mine':
      return value === 'true' || value === 'false';
    default:
      return true;
  }
}

export function useUrlFilters() {
  const [params, setParams] = useSearchParams();
  const ref = useReference();
  const gates = ref.data?.gates.map((g) => g.code);
  // The dropped keys travel in the (replaced) history entry's state; the next navigation clears them.
  const location = useLocation();
  const removed = ((location.state as { removedFilters?: FilterKey[] } | null)?.removedFilters ??
    []) as FilterKey[];

  const { filters, invalid } = useMemo(() => {
    const out: UrlFilters = {};
    const bad: FilterKey[] = [];
    for (const key of FILTER_KEYS) {
      const value = params.get(key);
      if (!value) continue;
      if (isValid(key, value, gates)) out[key] = value;
      else bad.push(key);
    }
    return { filters: out, invalid: bad };
  }, [params, gates]);

  // Drop the invalid values from the URL (replace: no extra history entry) and remember why.
  useEffect(() => {
    if (invalid.length === 0) return;
    setParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        for (const key of invalid) next.delete(key);
        return next;
      },
      { replace: true, state: { removedFilters: invalid } },
    );
  }, [invalid, setParams]);

  /** Merge a patch into the URL; undefined or '' removes the key. Other params are kept. */
  const update = useCallback(
    (patch: Partial<Record<FilterKey, string | undefined>>, opts?: { replace?: boolean }) => {
      setParams(
        (prev) => {
          const next = new URLSearchParams(prev);
          for (const [key, value] of Object.entries(patch)) {
            if (value) next.set(key, value);
            else next.delete(key);
          }
          return next;
        },
        { replace: opts?.replace },
      );
    },
    [setParams],
  );

  const clear = useCallback(() => {
    setParams((prev) => {
      const next = new URLSearchParams(prev);
      for (const key of FILTER_KEYS) next.delete(key);
      return next;
    });
  }, [setParams]);

  const notice =
    removed.length > 0
      ? `Removed invalid filter: ${removed.map((k) => k.replace(/_/g, ' ')).join(', ')}`
      : undefined;

  return { filters, update, clear, activeCount: Object.keys(filters).length, notice };
}

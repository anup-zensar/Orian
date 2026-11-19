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
interface RemovedFilter {
  key: FilterKey;
  value: string;
}

export type UrlFilters = Partial<Record<FilterKey, string>>;

const RAGS = ['Red', 'Amber', 'Green', 'Grey'];
const STATUSES = ['Active', 'Closed'];
const INTEGER = /^\d+$/;

interface Known {
  gates?: string[];
  portfolios?: string[];
  regions?: string[];
}

/** Is ``value`` acceptable for ``key``? Lists are undefined until the reference data loads. */
function isValid(key: FilterKey, value: string, known: Known): boolean {
  const { gates, portfolios, regions } = known;
  switch (key) {
    case 'portfolio':
      return !portfolios || portfolios.includes(value);
    case 'region':
      return !regions || regions.includes(value);
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
  const portfolios = ref.data?.portfolios;
  const regions = ref.data?.regions;
  // The dropped keys travel in the (replaced) history entry's state; the next navigation clears them.
  const location = useLocation();
  const removed = ((location.state as { removedFilters?: RemovedFilter[] } | null)
    ?.removedFilters ?? []) as RemovedFilter[];

  const { filters, invalid } = useMemo(() => {
    const out: UrlFilters = {};
    const bad: RemovedFilter[] = [];
    for (const key of FILTER_KEYS) {
      const value = params.get(key);
      if (!value) continue;
      if (isValid(key, value, { gates, portfolios, regions })) out[key] = value;
      else bad.push({ key, value });
    }
    return { filters: out, invalid: bad };
  }, [params, gates, portfolios, regions]);

  // Drop the invalid values from the URL (replace: no extra history entry) and remember why.
  useEffect(() => {
    if (invalid.length === 0) return;
    setParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        for (const { key } of invalid) next.delete(key);
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

  // Unknown portfolio/region values get their own wording; the rest keep the generic one.
  const named = removed.filter((r) => r.key === 'portfolio' || r.key === 'region');
  const others = removed.filter((r) => r.key !== 'portfolio' && r.key !== 'region');
  const parts = [
    ...named.map((r) => `Unknown ${r.key} "${r.value}" - showing all.`),
    ...(others.length > 0
      ? [`Removed invalid filter: ${others.map((r) => r.key.replace(/_/g, ' ')).join(', ')}`]
      : []),
  ];
  const notice = parts.length > 0 ? parts.join(' ') : undefined;

  return { filters, update, clear, activeCount: Object.keys(filters).length, notice };
}

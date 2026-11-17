// Assessment filters live in the URL (spec 12): deep links and the back button work.
import { useCallback, useMemo } from 'react';
import { useSearchParams } from 'react-router';
import type { ItemQuery } from '../api';

export interface AssessmentFilterValues {
  gate: string; // '' = current gate and earlier, 'all' = every gate, else a gate code
  lens: string;
  source: string;
  status: string;
  owner: string;
  mine: boolean;
  excluded: boolean;
  q: string;
  item: string; // deep-linked playbook id
}

const KEYS = ['gate', 'lens', 'source', 'status', 'owner', 'q', 'item'] as const;

export function useAssessmentFilters() {
  const [params, setParams] = useSearchParams();

  const values: AssessmentFilterValues = useMemo(
    () => ({
      gate: params.get('gate') ?? '',
      lens: params.get('lens') ?? '',
      source: params.get('source') ?? '',
      status: params.get('status') ?? '',
      owner: params.get('owner') ?? '',
      mine: params.get('mine') === '1',
      excluded: params.get('excluded') === '1',
      q: params.get('q') ?? '',
      item: params.get('item') ?? '',
    }),
    [params],
  );

  const update = useCallback(
    (
      patch: Partial<Record<keyof AssessmentFilterValues, string | boolean | undefined>>,
      replace = false,
    ) => {
      setParams(
        (prev) => {
          const next = new URLSearchParams(prev);
          for (const [k, v] of Object.entries(patch)) {
            if (v === true) next.set(k, '1');
            else if (v) next.set(k, String(v));
            else next.delete(k);
          }
          return next;
        },
        { replace },
      );
    },
    [setParams],
  );

  const clear = useCallback(() => {
    setParams((prev) => {
      const next = new URLSearchParams(prev);
      for (const k of [...KEYS, 'mine', 'excluded']) next.delete(k);
      return next;
    });
  }, [setParams]);

  // A deep link (?item=) must find its row, so widen gate and applicability filters for it.
  const hasItem = !!values.item;
  const query: ItemQuery = useMemo(
    () => ({
      gate: values.gate && values.gate !== 'all' ? values.gate : undefined,
      all_gates: values.gate === 'all' || (hasItem && !values.gate) || undefined,
      lens: values.lens || undefined,
      source: values.source || undefined,
      status: values.status || undefined,
      owner: values.owner || undefined,
      mine: values.mine || undefined,
      applicability: values.excluded || hasItem ? 'all' : 'applies',
      q: values.q || undefined,
    }),
    [values, hasItem],
  );

  const activeCount =
    KEYS.filter((k) => k !== 'item' && values[k]).length +
    (values.mine ? 1 : 0) +
    (values.excluded ? 1 : 0);

  return { values, query, update, clear, activeCount };
}

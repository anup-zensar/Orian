import { useQuery } from '@tanstack/react-query';
import { apiFetch } from '../../api/client';
import type { Reference } from '../../api/types';

/** Query key of the reference data. After ANY admin save call `invalidateReference(queryClient)`. */
export const REFERENCE_KEY = ['reference'] as const;

/**
 * Reference data (gates, lenses, statuses, option lists, project types ...). It changes only when an
 * Admin saves configuration (CR-01), so cache for long. The query asks for INACTIVE values too: each
 * item carries `active` and the hooks in `options.ts` filter them, so a record that still holds an
 * inactive value can show its label.
 */
export function useReference() {
  return useQuery({
    queryKey: REFERENCE_KEY,
    queryFn: ({ signal }) =>
      apiFetch<Reference>('/reference', { signal, query: { include_inactive: true } }),
    staleTime: 5 * 60_000,
  });
}

/** Refetch the reference data after an admin save (project types, lists, roles, thresholds ...). */
export function invalidateReference(queryClient: {
  invalidateQueries: (filters: { queryKey: readonly unknown[] }) => unknown;
}): void {
  void queryClient.invalidateQueries({ queryKey: REFERENCE_KEY });
}

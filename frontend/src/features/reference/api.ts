import { useQuery } from '@tanstack/react-query';
import { apiFetch } from '../../api/client';
import type { Reference } from '../../api/types';

/** Static reference data (gates, lenses, statuses ...) – rarely changes, so cache for long. */
export function useReference() {
  return useQuery({
    queryKey: ['reference'],
    queryFn: ({ signal }) => apiFetch<Reference>('/reference', { signal }),
    staleTime: 5 * 60_000,
  });
}

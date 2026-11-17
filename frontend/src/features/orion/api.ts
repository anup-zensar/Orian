import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { apiFetch } from '../../api/client';
import type { Insights } from '../../api/types';
import type { UrlFilters } from '../transitions/useUrlFilters';

/** Orion insights for the dashboard or control tower (FR-010, FR-011). Read-only (BR-050). */
export function useInsights(scope: 'dashboard' | 'control-tower', filters?: UrlFilters) {
  return useQuery({
    queryKey: ['insights', scope, filters ?? {}],
    queryFn: ({ signal }) =>
      apiFetch<Insights>('/orion/insights', { query: { scope, ...filters }, signal }),
    placeholderData: keepPreviousData,
  });
}

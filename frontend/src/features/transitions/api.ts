import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { apiFetch } from '../../api/client';
import type { TransitionSummary } from '../../api/types';
import type { UrlFilters } from './useUrlFilters';

/** The transition register (FR-012). Filters come straight from the URL (spec 12). */
export function useTransitions(filters: UrlFilters) {
  return useQuery({
    queryKey: ['transitions', filters],
    queryFn: ({ signal }) =>
      apiFetch<TransitionSummary[]>('/transitions', { query: filters, signal }),
    placeholderData: keepPreviousData, // no skeleton flash while typing in the search box
  });
}

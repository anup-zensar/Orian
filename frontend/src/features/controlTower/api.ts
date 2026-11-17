import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { apiFetch } from '../../api/client';
import type { ControlTower } from '../../api/types';
import type { UrlFilters } from '../transitions/useUrlFilters';

/** Control tower for the filtered set of transitions (FR-011). */
export function useControlTower(filters: UrlFilters) {
  return useQuery({
    queryKey: ['control-tower', filters],
    queryFn: ({ signal }) => apiFetch<ControlTower>('/control-tower', { query: filters, signal }),
    placeholderData: keepPreviousData,
  });
}

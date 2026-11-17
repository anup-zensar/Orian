import { useQuery } from '@tanstack/react-query';
import { apiFetch } from '../../api/client';
import type { Dashboard } from '../../api/types';

/** Role-aware home page data (FR-010). Reset on user switch by AuthProvider. */
export function useDashboard() {
  return useQuery({
    queryKey: ['dashboard'],
    queryFn: ({ signal }) => apiFetch<Dashboard>('/dashboard', { signal }),
  });
}

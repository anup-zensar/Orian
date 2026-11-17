import { useQuery } from '@tanstack/react-query';
import { apiFetch } from '../../api/client';
import type { components } from '../../api/schema';

export type OutboxMessage = components['schemas']['OutboxMessageOut'];

export interface OutboxFilters {
  channel?: string;
  transition_id?: string;
}

export function useOutbox(filters: OutboxFilters) {
  return useQuery({
    queryKey: ['outbox', filters],
    queryFn: ({ signal }) =>
      apiFetch<OutboxMessage[]>('/outbox', {
        query: { channel: filters.channel, transition_id: filters.transition_id },
        signal,
      }),
  });
}

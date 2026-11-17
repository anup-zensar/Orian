import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiFetch } from '../../api/client';
import { useAuth } from '../../auth/useAuth';
import type { components } from '../../api/schema';

export type Notification = components['schemas']['NotificationOut'];
export type Notifications = components['schemas']['NotificationsOut'];

/** The current user's notifications; polled every 30 s (spec 8.13). */
export function useNotifications() {
  const { userId } = useAuth();
  return useQuery({
    queryKey: ['notifications'],
    queryFn: ({ signal }) => apiFetch<Notifications>('/notifications', { signal }),
    enabled: !!userId,
    refetchInterval: 30_000,
  });
}

export function useMarkRead() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => apiFetch<unknown>(`/notifications/${id}/read`, { method: 'POST' }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ['notifications'] }),
  });
}

export function useMarkAllRead() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => apiFetch<unknown>('/notifications/read-all', { method: 'POST' }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ['notifications'] }),
  });
}

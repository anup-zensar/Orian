import { useQuery } from '@tanstack/react-query';
import { apiFetch } from '../../api/client';
import { useAuth } from '../../auth/useAuth';
import type { Me, User } from '../../api/types';

/** Demo users for the login page and the Switch user menu (public endpoint, A-27). */
export function useUsers() {
  return useQuery({
    queryKey: ['users'],
    queryFn: ({ signal }) => apiFetch<User[]>('/users', { signal }),
    staleTime: 5 * 60_000,
  });
}

/**
 * Current user + permissions + denied reasons (GET /me). Keyed by the auth-context user id.
 * Other page queries need not include the user in their key: AuthProvider calls
 * queryClient.resetQueries() on every login/switch/logout, so they refetch as the new user.
 */
export function useMe() {
  const { userId } = useAuth();
  return useQuery({
    queryKey: ['me', userId],
    queryFn: ({ signal }) => apiFetch<Me>('/me', { signal }),
    enabled: !!userId,
  });
}

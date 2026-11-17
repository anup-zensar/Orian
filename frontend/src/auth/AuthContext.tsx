import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { getStoredUserId, setStoredUserId } from '../api/client';
import { router } from '../router';
import { AuthContext, type AuthContextValue } from './context';
import { safeNext } from './safeNext';
import { subscribeSessionExpired } from './session';

/** Demo auth (FR-001): the user id is sent as X-Demo-User (memory + best-effort localStorage). */
export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [userId, setUserId] = useState<string | null>(() => getStoredUserId());
  const explicitLogout = useRef(false);

  const apply = useCallback(
    async (id: string | null) => {
      // 1. The stored user first, so refetches send the new X-Demo-User.
      setStoredUserId(id);
      setUserId(id);
      // 2. Stop in-flight requests made as the previous user, then reset: observers are notified
      //    and active queries refetch. (clear() would leave mounted observers with stale data.)
      await queryClient.cancelQueries();
      await queryClient.resetQueries();
    },
    [queryClient],
  );

  const logout = useCallback(
    (opts?: { explicit?: boolean }) => {
      explicitLogout.current = !!opts?.explicit;
      void apply(null);
    },
    [apply],
  );

  // F7: a 401 from any query/mutation while signed in ends the session and returns to /login.
  useEffect(
    () =>
      subscribeSessionExpired(() => {
        const here = safeNext(
          window.location.pathname + window.location.search + window.location.hash,
        );
        logout();
        const to = here === '/' ? '/login' : `/login?next=${encodeURIComponent(here)}`;
        void router.navigate(to, { replace: true });
      }),
    [logout],
  );

  const value = useMemo<AuthContextValue>(
    () => ({
      userId,
      login: (id) => {
        explicitLogout.current = false;
        void apply(id);
      },
      switchUser: (id) => void apply(id),
      logout,
      wasExplicitLogout: () => explicitLogout.current,
    }),
    [userId, apply, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

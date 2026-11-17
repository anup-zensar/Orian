import { ApiError, getStoredUserId } from '../api/client';

// Bridges the QueryClient (created outside React) to the AuthProvider (F7).
const listeners = new Set<() => void>();

export function subscribeSessionExpired(fn: () => void): () => void {
  listeners.add(fn);
  return () => {
    listeners.delete(fn);
  };
}

/**
 * Called from QueryCache/MutationCache onError. A 401 while a user is set means the session is
 * gone (e.g. demo reset). With no user set it is ignored, so the public login page cannot loop.
 */
export function handleQueryError(error: unknown): void {
  if (error instanceof ApiError && error.status === 401 && getStoredUserId()) {
    listeners.forEach((fn) => fn());
  }
}

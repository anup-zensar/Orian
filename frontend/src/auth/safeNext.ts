/**
 * Validates a user-controlled in-app path (?next=, session-expiry return path) so it can never
 * become an open redirect. Same-origin paths only; backslashes and control characters (which
 * browsers normalise into "//host" tricks) are rejected; /login is rejected to avoid loops.
 * Returns pathname + search + hash, or "/" when the input is not acceptable.
 */
export function safeNext(next: string | null | undefined): string {
  if (!next) return '/';
  for (let i = 0; i < next.length; i++) {
    const c = next.charCodeAt(i);
    if (c <= 0x1f || c === 0x7f || c === 0x5c) return '/';
  }
  try {
    const url = new URL(next, window.location.origin);
    if (url.origin !== window.location.origin) return '/';
    if (url.pathname === '/login' || url.pathname.startsWith('/login/')) return '/';
    return url.pathname + url.search + url.hash;
  } catch {
    return '/';
  }
}

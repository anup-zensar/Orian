import { createContext } from 'react';

export interface AuthContextValue {
  /** Id of the logged-in demo user, or null when signed out. */
  userId: string | null;
  login: (id: string) => void;
  /** Change user but stay on the same URL; every page refetches as the new user (FR-001). */
  switchUser: (id: string) => void;
  /** `explicit` marks a user-initiated Sign out, so no ?next= is kept (F8). */
  logout: (opts?: { explicit?: boolean }) => void;
  /** True when the last logout was an explicit Sign out. */
  wasExplicitLogout: () => boolean;
}

export const AuthContext = createContext<AuthContextValue | null>(null);

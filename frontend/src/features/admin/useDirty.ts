import { createContext, useContext, useEffect, useState } from 'react';

/** Lets an editor tell the surrounding DirtyGuard (see peopleRulesUi.tsx) whether it has edits. */
export const DirtyContext = createContext<(id: string, dirty: boolean) => void>(() => {});

/**
 * True once `state` differs from what it was on first render (remount the editor after a save).
 * The result is also reported to the surrounding DirtyGuard under `id`.
 */
export function useDirty(state: unknown, id: string): boolean {
  const [first] = useState(() => JSON.stringify(state));
  const dirty = JSON.stringify(state) !== first;
  const report = useContext(DirtyContext);
  useEffect(() => {
    report(id, dirty);
    return () => report(id, false);
  }, [id, dirty, report]);
  return dirty;
}

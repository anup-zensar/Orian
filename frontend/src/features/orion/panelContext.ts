import { createContext, useContext } from 'react';

/** What the Orion side panel is about (FR-090 context chip). */
export interface OrionPanelTarget {
  /** Transition open in the UI; quick-action forms default to it. */
  transitionId?: string;
  /** Text to place in the chat box, e.g. "Assess readiness of TR-0001 for AtD". */
  prompt?: string;
}

export interface OrionPanelState {
  isOpen: boolean;
  target: OrionPanelTarget;
  open: (target?: OrionPanelTarget) => void;
  close: () => void;
  toggle: () => void;
}

export const OrionPanelContext = createContext<OrionPanelState | null>(null);

/** Open or close the Orion side panel from any page (e.g. "Ask Orion" in the workspace header). */
export function useOrionPanel(): OrionPanelState {
  const ctx = useContext(OrionPanelContext);
  if (!ctx) throw new Error('useOrionPanel must be used inside the AppShell');
  return ctx;
}

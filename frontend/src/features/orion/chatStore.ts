import { useSyncExternalStore } from 'react';
import type { OrionMessage, Proposal } from './api';

/** One entry of the Orion conversation. */
export type ChatItem =
  | { id: number; kind: 'user'; text: string; fileName?: string }
  | {
      id: number;
      kind: 'orion';
      message: OrionMessage;
      /** Transition the answer is about (needed to render readiness cards). */
      transitionId?: string;
      /** Form cards: true once the user submitted them. */
      submitted?: boolean;
    }
  | { id: number; kind: 'error'; error: unknown; retry?: () => void };

// A tiny module-level store so the conversation survives closing the side panel and moving
// between the panel and the /orion page. It is cleared when the demo user changes.
let items: ChatItem[] = [];
let nextId = 1;
let owner: string | null | undefined;
const listeners = new Set<() => void>();

function emit(next: ChatItem[]) {
  items = next;
  listeners.forEach((l) => l());
}

export const chatStore = {
  push(entry: DistributiveOmit<ChatItem, 'id'>): number {
    const id = nextId++;
    emit([...items, { ...entry, id } as ChatItem]);
    return id;
  },
  remove(id: number) {
    emit(items.filter((i) => i.id !== id));
  },
  markSubmitted(id: number) {
    emit(items.map((i) => (i.id === id && i.kind === 'orion' ? { ...i, submitted: true } : i)));
  },
  /** Replace a proposal card with its updated copy (Accepted / Dismissed). */
  updateProposal(proposal: Proposal) {
    emit(
      items.map((i) =>
        i.kind === 'orion' && i.message.type === 'proposal' && i.message.proposal.id === proposal.id
          ? { ...i, message: { ...i.message, proposal } }
          : i,
      ),
    );
  },
  clear() {
    emit([]);
  },
  /** Start a fresh conversation when another demo user signs in. */
  resetFor(userId: string | null) {
    if (owner !== userId) {
      owner = userId;
      emit([]);
    }
  },
};

type DistributiveOmit<T, K extends keyof never> = T extends unknown ? Omit<T, K> : never;

const subscribe = (l: () => void) => {
  listeners.add(l);
  return () => listeners.delete(l);
};

export function useChatItems(): ChatItem[] {
  return useSyncExternalStore(subscribe, () => items);
}

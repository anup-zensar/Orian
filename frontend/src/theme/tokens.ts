import type { CSSProperties } from 'react';

// The only place colours are defined (PLAN.md section 4, spec section 12).

export interface ColorSet {
  foreground: string;
  background: string;
  border: string;
}

export type Lens = 'Business' | 'Technical' | 'Compliance';
export type Rag = 'Red' | 'Amber' | 'Green' | 'Grey';
export type ActorType = 'Human' | 'Workflow rule' | 'Orion agent' | 'System';

/** Lens colours: Business amber, Technical blue, Compliance teal. */
export const lensColors: Record<Lens, ColorSet> = {
  Business: { foreground: '#7a4a00', background: '#fff4ce', border: '#e8b84a' },
  Technical: { foreground: '#0b4a8f', background: '#e6f0fb', border: '#6ea8e6' },
  Compliance: { foreground: '#0b5a55', background: '#e0f4f2', border: '#5cbdb5' },
};

/** RAG colours; Grey means not started. Chips must always also show text. */
export const ragColors: Record<Rag, ColorSet> = {
  Red: { foreground: '#8a1f1f', background: '#fde7e9', border: '#d13438' },
  Amber: { foreground: '#7a4a00', background: '#fff1cc', border: '#e8a317' },
  Green: { foreground: '#0e5a1b', background: '#e3f4e5', border: '#2e9e44' },
  Grey: { foreground: '#4a4a4a', background: '#efefef', border: '#a8a8a8' },
};

/** Actor badges: Human neutral, Workflow rule blue outline, Orion agent purple (+ "AI"). */
export const actorStyles: Record<ActorType, ColorSet> = {
  Human: { foreground: '#323130', background: '#f3f2f1', border: '#c8c6c4' },
  'Workflow rule': { foreground: '#0b4a8f', background: '#ffffff', border: '#2b7de0' },
  'Orion agent': { foreground: '#4b2d8f', background: '#efe9fb', border: '#7c5cd6' },
  System: { foreground: '#605e5c', background: '#faf9f8', border: '#d2d0ce' },
};

export const aiBadgeColors: ColorSet = {
  foreground: '#ffffff',
  background: '#6b46c1',
  border: '#6b46c1',
};

/** Role badge colour (neutral; roles are not a semantic colour family). */
export const roleBadgeColors: ColorSet = {
  foreground: '#3b3a39',
  background: '#edebe9',
  border: '#c8c6c4',
};

/** Inline-style helper so components do not repeat the three properties. */
export function chipStyle(c: ColorSet): CSSProperties {
  return { color: c.foreground, backgroundColor: c.background, borderColor: c.border };
}

import type { CSSProperties } from 'react';
import { ai, palette } from './orionTheme';

// The only place semantic colours (RAG, lens, actor, AI) are defined. Every pairing is WCAG AA
// (4.5:1 text). For ColorSet: `foreground` is safe as TEXT on white and on its own `background`
// tint; `border` is the solid brand colour (icons, accent bars, chip outlines).

export interface ColorSet {
  foreground: string;
  background: string;
  border: string;
}

export type Lens = 'Business' | 'Technical' | 'Compliance';
export type Rag = 'Red' | 'Amber' | 'Green' | 'Grey';
export type ActorType = 'Human' | 'Workflow rule' | 'Orion agent' | 'System';

/** Lens colours: Business brand-yellow family, Technical blue, Compliance teal. */
export const lensColors: Record<Lens, ColorSet> = {
  Business: { foreground: '#5C4400', background: '#FFF4CC', border: palette.yellow },
  Technical: { foreground: '#2F5A8C', background: '#E8EFF7', border: palette.link },
  Compliance: { foreground: '#0B5A55', background: '#E0F4F2', border: '#2E9E96' },
};

/** RAG tints (text-safe). Grey means not started. Chips must always also show text. */
export const ragColors: Record<Rag, ColorSet> = {
  Red: { foreground: palette.redText, background: '#FDECEC', border: palette.red },
  Amber: { foreground: '#7A4300', background: '#FDEBD0', border: '#EB8705' },
  Green: { foreground: '#006B47', background: '#E1F3EC', border: '#008557' },
  Grey: { foreground: '#4A4A4A', background: palette.hover, border: palette.borderMedium },
};

/** RAG solid chips (RagChip): Red white text, Amber dark text, Green white text. */
export const ragSolid: Record<Rag, { background: string; foreground: string }> = {
  Red: { background: palette.red, foreground: '#FFFFFF' },
  Amber: { background: '#EB8705', foreground: palette.onYellow },
  Green: { background: '#008557', foreground: '#FFFFFF' },
  Grey: { background: palette.pressed, foreground: palette.onYellow },
};

/** Actor badges: Human neutral, Workflow rule blue outline, Orion agent purple (+ "AI"). */
export const actorStyles: Record<ActorType, ColorSet> = {
  Human: { foreground: palette.textStrong, background: '#F5F5F5', border: palette.borderMedium },
  'Workflow rule': { foreground: '#2F5A8C', background: '#EEF4FB', border: palette.link },
  'Orion agent': { foreground: ai.text, background: ai.tint, border: ai.main },
  System: { foreground: '#4A4A4A', background: '#FAFAFA', border: '#B0B0B0' },
};

/** The "AI" badge: white on Orion purple (4.6:1). */
export const aiBadgeColors: ColorSet = {
  foreground: '#FFFFFF',
  background: ai.main,
  border: ai.main,
};

/** Role badge colour (neutral; roles are not a semantic colour family). */
export const roleBadgeColors: ColorSet = {
  foreground: palette.textStrong,
  background: palette.hover,
  border: palette.borderMedium,
};

/** Inline-style helper so components do not repeat the three properties. */
export function chipStyle(c: ColorSet): CSSProperties {
  return { color: c.foreground, backgroundColor: c.background, borderColor: c.border };
}

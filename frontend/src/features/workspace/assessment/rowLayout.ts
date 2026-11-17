import type { CSSProperties } from 'react';

export const ROW_GRID =
  '28px 28px 76px minmax(180px, 1fr) 80px 84px 96px 128px 64px 56px 52px 118px 36px';

/** Minimum width of the grid (sum of the columns + gaps + right padding). */
export const ROW_MIN_WIDTH = '1082px';

// Sticky first columns (checkbox, chevron, ID, title) + Status, so they stay visible when the grid scrolls sideways.
const stick = (left: number): CSSProperties => ({
  position: 'sticky',
  left,
  zIndex: 1,
  backgroundColor: 'inherit',
});
export const STICKY = {
  c1: stick(0),
  c2: stick(32),
  c3: stick(64),
  c4: stick(144),
  status: stick(332),
};

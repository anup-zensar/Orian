// Placeholder logo: the Orion constellation drawn from scratch. Swap for the client's picture when it arrives.
const STARS: [number, number, number][] = [
  [21, 5, 1.3], // Meissa (head)
  [10, 10, 2.1], // Betelgeuse
  [30, 9, 1.7], // Bellatrix
  [15, 21, 1.5], // Alnitak
  [20, 19.5, 1.5], // Alnilam
  [25, 18, 1.5], // Mintaka
  [13, 34, 1.7], // Saiph
  [29, 33, 2.1], // Rigel
];
const LINES = 'M10 10L21 5L30 9M10 10L15 21L13 34M30 9L25 18L29 33M15 21L25 18';

/** Dark tile so the yellow stars read on both light and dark themes. */
export function OrionLogo({ size = 28 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 40 40" role="img" aria-label="Orion constellation" style={{ flexShrink: 0 }}>
      <rect width="40" height="40" rx="9" fill="#1A1A1A" />
      <path d={LINES} stroke="#9A9A9A" strokeWidth="0.8" fill="none" />
      {STARS.map(([x, y, r]) => (
        <circle key={`${x}-${y}`} cx={x} cy={y} r={r} fill="#FFC600" />
      ))}
    </svg>
  );
}

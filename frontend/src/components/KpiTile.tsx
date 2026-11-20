import { Caption1, Tooltip, makeStyles, mergeClasses, tokens } from '@fluentui/react-components';
import { lensColors, ragColors } from '../theme/tokens';

const useStyles = makeStyles({
  tile: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'flex-start',
    gap: tokens.spacingVerticalXXS,
    minHeight: '84px',
    padding: `${tokens.spacingVerticalM} ${tokens.spacingHorizontalL}`,
    border: `1px solid ${tokens.colorNeutralStroke2}`,
    borderLeftWidth: '5px',
    borderRadius: tokens.borderRadiusMedium,
    backgroundColor: tokens.colorNeutralBackground1,
    boxShadow: tokens.shadow2,
    textAlign: 'left',
    font: 'inherit',
    color: tokens.colorNeutralForeground1,
  },
  clickable: {
    cursor: 'pointer',
    ':hover': { backgroundColor: tokens.colorNeutralBackground1Hover },
    ':focus-visible': { outline: `2px solid ${tokens.colorStrokeFocus2}`, outlineOffset: '2px' },
  },
  active: {
    outline: `2px solid ${tokens.colorBrandStroke1}`,
    backgroundColor: tokens.colorBrandBackground2,
  },
  value: {
    fontSize: tokens.fontSizeHero800,
    lineHeight: tokens.lineHeightHero800,
    fontWeight: tokens.fontWeightSemibold,
  },
});

/** Tone -> colours. Re-uses the RAG palette (danger/warning/success) and the Technical blue (info). */
const TONES = {
  danger: ragColors.Red,
  warning: ragColors.Amber,
  success: ragColors.Green,
  info: lensColors.Technical,
  neutral: ragColors.Grey,
} as const;

interface KpiTileProps {
  label: string;
  value: number | string;
  tone?: string;
  hint?: string;
  /** Visible small print under the value (e.g. what the tile counts). */
  caption?: string;
  /** When set the tile is a button (filter or link); keyboard accessible. */
  onClick?: () => void;
  /** Marks the tile as the applied filter (also announced as text, not colour only). */
  active?: boolean;
}

/** KPI tile (spec 8.1, 8.2). A tile with a filter or link is a real <button>. */
export function KpiTile({
  label,
  value,
  tone = 'neutral',
  hint,
  caption,
  onClick,
  active,
}: KpiTileProps) {
  const s = useStyles();
  const colors = TONES[tone as keyof typeof TONES] ?? TONES.neutral;
  const className = mergeClasses(s.tile, onClick && s.clickable, active && s.active);
  const style = { borderLeftColor: colors.border };
  const body = (
    <>
      <Caption1>{label}</Caption1>
      <span className={s.value} style={{ color: colors.foreground }}>
        {value}
      </span>
      {caption && <Caption1>{caption}</Caption1>}
      {active && <Caption1>Filter applied (click to remove)</Caption1>}
    </>
  );
  const tile = onClick ? (
    <button
      type="button"
      className={className}
      style={style}
      onClick={onClick}
      aria-pressed={active === undefined ? undefined : active}
    >
      {body}
    </button>
  ) : (
    <div className={className} style={style}>
      {body}
    </div>
  );
  return hint ? (
    <Tooltip content={hint} relationship="description" withArrow>
      {tile}
    </Tooltip>
  ) : (
    tile
  );
}

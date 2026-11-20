import type { ReactNode } from 'react';
import { Caption1, Tooltip, makeStyles, mergeClasses, tokens } from '@fluentui/react-components';
import {
  CheckmarkCircle20Regular,
  ErrorCircle20Regular,
  Info20Regular,
  Warning20Regular,
  DataBarVertical20Regular,
} from '@fluentui/react-icons';
import { cardRadius, cardShadow } from '../theme/orionTheme';
import { lensColors, ragColors } from '../theme/tokens';

const useStyles = makeStyles({
  tile: {
    display: 'flex',
    alignItems: 'center',
    gap: tokens.spacingHorizontalM,
    minHeight: '88px',
    minWidth: 0,
    padding: `${tokens.spacingVerticalM} ${tokens.spacingHorizontalL}`,
    border: `1px solid ${tokens.colorNeutralStroke2}`,
    borderRadius: cardRadius,
    backgroundColor: tokens.colorNeutralBackground1,
    boxShadow: cardShadow,
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
    outline: `2px solid ${tokens.colorNeutralStroke1Pressed}`,
    backgroundColor: tokens.colorBrandBackground2,
  },
  circle: {
    flexShrink: 0,
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    width: '40px',
    height: '40px',
    borderRadius: '50%',
  },
  text: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'flex-start',
    gap: tokens.spacingVerticalXXS,
    minWidth: 0,
  },
  value: {
    fontSize: '28px',
    lineHeight: '34px',
    fontWeight: tokens.fontWeightSemibold,
  },
});

/** Tone -> colours. Re-uses the RAG palette (danger/warning/success) and the Technical blue (info). */
const TONE_ICONS = {
  danger: ErrorCircle20Regular,
  warning: Warning20Regular,
  success: CheckmarkCircle20Regular,
  info: Info20Regular,
  neutral: DataBarVertical20Regular,
} as const;

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
  /** Optional icon for the tinted circle; defaults to one that matches the tone. */
  icon?: ReactNode;
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
  icon,
  onClick,
  active,
}: KpiTileProps) {
  const s = useStyles();
  const colors = TONES[tone as keyof typeof TONES] ?? TONES.neutral;
  const className = mergeClasses(s.tile, onClick && s.clickable, active && s.active);
  const ToneIcon = TONE_ICONS[tone as keyof typeof TONE_ICONS] ?? TONE_ICONS.neutral;
  const body = (
    <>
      <span
        className={s.circle}
        style={{ backgroundColor: colors.background, color: colors.foreground }}
        aria-hidden
      >
        {icon ?? <ToneIcon />}
      </span>
      <span className={s.text}>
        <Caption1>{label}</Caption1>
        <span className={s.value} style={{ color: colors.foreground }}>
          {value}
        </span>
        {caption && <Caption1>{caption}</Caption1>}
        {active && <Caption1>Filter applied (click to remove)</Caption1>}
      </span>
    </>
  );
  const tile = onClick ? (
    <button
      type="button"
      className={className}
      onClick={onClick}
      aria-pressed={active === undefined ? undefined : active}
    >
      {body}
    </button>
  ) : (
    <div className={className}>{body}</div>
  );
  return hint ? (
    <Tooltip content={hint} relationship="description" withArrow>
      {tile}
    </Tooltip>
  ) : (
    tile
  );
}

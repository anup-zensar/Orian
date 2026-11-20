import { createLightTheme, type BrandVariants, type Theme } from '@fluentui/react-components';

/** The Shell palette in one place. Pages import these (or use Fluent tokens), never hex values. */
export const palette = {
  yellow: '#FFC600',
  yellowHover: '#FFCB14',
  yellowPressed: '#EBB600',
  yellowTint: '#FFF5DB',
  yellowTintHover: '#FFEFC4',
  red: '#DD1D21',
  redText: '#B3171A',
  /** Text and icons ON yellow are always this dark colour (white on yellow fails contrast). */
  onYellow: '#292929',
  canvas: '#F5F5F5',
  surface: '#FFFFFF',
  textStrong: '#292929',
  /** Palette #757575 nudged darker so it passes 4.5:1 on the #F5F5F5 canvas as well as on white. */
  textSubtle: '#6B6B6B',
  link: '#4B78AA',
  /** Link hover/pressed are DARKER than the palette hover (#6E94C0 is only 3:1 on white). */
  linkHover: '#3A6190',
  linkPressed: '#2F5380',
  linkVisited: '#9A60A4',
  borderStrong: '#292929',
  borderMedium: '#757575',
  borderSubtle: 'rgba(28, 28, 28, 0.135)',
  hover: '#EBEBEB',
  pressed: '#E0E0E0',
} as const;

/** Orion / AI accent: purple, used ONLY for the AI badge and the Orion panel accent. */
export const ai = {
  main: '#9A60A4',
  strong: '#7F4789',
  tint: '#F4ECF5',
  /** Text on the tint (and on white). */
  text: '#6B3A75',
} as const;

/** Card look from the Shell preview: white, subtle border, 12 px radius, soft shadow. */
export const cardShadow = '0 2px 8px rgba(0, 0, 0, 0.08)';
export const cardRadius = '12px';

/** Kept for existing imports: surface colours that are not Fluent tokens. */
export const surface = {
  canvas: palette.canvas,
  ai: ai.main,
  aiStrong: ai.strong,
  aiTint: ai.tint,
  aiText: ai.text,
} as const;

/** Brand ramp around Shell yellow. Fluent maps step 80 to the brand fill, 90 hover, 70 pressed. */
export const orionBrand: BrandVariants = {
  10: '#1F1800',
  20: '#3A2E00',
  30: '#574500',
  40: '#735C00',
  50: '#8F7400',
  60: '#C99700',
  70: '#EBB600',
  80: '#FFC600',
  90: '#FFCB14',
  100: '#FFD23D',
  110: '#FFD966',
  120: '#FFE08A',
  130: '#FFE8A8',
  140: '#FFEFC4',
  150: '#FFF5DB',
  160: '#FFFAEC',
};

const base = createLightTheme(orionBrand);

/** Light theme used for the whole app (no dark mode, by design). */
export const orionTheme: Theme = {
  ...base,
  fontFamilyBase: 'Arial, "Segoe UI", sans-serif',

  // Neutrals
  colorNeutralBackground1: palette.surface,
  colorNeutralBackground1Hover: palette.hover,
  colorNeutralBackground1Pressed: palette.pressed,
  colorNeutralBackground1Selected: palette.hover,
  colorNeutralBackground2: palette.canvas,
  colorNeutralBackground2Hover: palette.hover,
  colorNeutralBackground2Pressed: palette.pressed,
  colorNeutralBackground3: palette.canvas,
  colorNeutralBackground3Hover: palette.hover,
  colorNeutralBackground3Pressed: palette.pressed,
  colorSubtleBackgroundHover: palette.hover,
  colorSubtleBackgroundPressed: palette.pressed,
  colorSubtleBackgroundSelected: palette.hover,
  colorNeutralBackgroundDisabled: 'rgba(28, 28, 28, 0.04)',
  colorNeutralForeground1: palette.textStrong,
  colorNeutralForeground1Hover: palette.textStrong,
  colorNeutralForeground1Pressed: palette.textStrong,
  colorNeutralForeground1Selected: palette.textStrong,
  colorNeutralForeground2: '#424242',
  colorNeutralForeground2Hover: palette.textStrong,
  colorNeutralForeground2Pressed: palette.textStrong,
  colorNeutralForeground2Selected: palette.textStrong,
  colorNeutralForeground3: palette.textSubtle,
  colorNeutralForeground3Hover: '#424242',
  colorNeutralForeground3Pressed: palette.textStrong,
  colorNeutralForeground3Selected: palette.textStrong,
  colorNeutralForegroundDisabled: 'rgba(28, 28, 28, 0.38)',
  colorNeutralStroke1: palette.borderMedium,
  colorNeutralStroke1Hover: '#424242',
  colorNeutralStroke1Pressed: palette.textStrong,
  colorNeutralStroke1Selected: palette.textStrong,
  colorNeutralStroke2: palette.borderSubtle,
  colorNeutralStroke3: 'rgba(28, 28, 28, 0.08)',
  colorNeutralStrokeAccessible: palette.borderMedium,
  colorNeutralStrokeAccessibleHover: '#424242',
  colorNeutralStrokeAccessiblePressed: palette.textStrong,
  colorNeutralStrokeAccessibleSelected: palette.textStrong,
  colorNeutralStrokeDisabled: palette.borderSubtle,
  colorStrokeFocus1: '#FFFFFF',
  colorStrokeFocus2: palette.textStrong,

  // Brand fills = yellow, with DARK text/icons on them.
  colorBrandBackground: palette.yellow,
  colorBrandBackgroundHover: palette.yellowHover,
  colorBrandBackgroundPressed: palette.yellowPressed,
  colorBrandBackgroundSelected: palette.yellow,
  colorBrandBackgroundStatic: palette.yellow,
  colorBrandBackground2: palette.yellowTint,
  colorBrandBackground2Hover: palette.yellowTintHover,
  colorBrandBackground2Pressed: '#FFE8A8',
  colorBrandBackground3Static: palette.yellow,
  colorBrandBackground4Static: palette.yellowPressed,
  colorNeutralForegroundOnBrand: palette.onYellow,
  colorNeutralForegroundStaticInverted: palette.onYellow,
  colorBrandStroke1: palette.yellow,
  colorBrandStroke2: '#FFE08A',
  colorBrandStroke2Hover: palette.yellow,
  colorBrandStroke2Pressed: palette.yellowPressed,
  colorBrandStroke2Contrast: '#FFE08A',

  // Brand-coloured TEXT = link blue (yellow text on white is unreadable).
  colorBrandForeground1: palette.link,
  colorBrandForeground2: palette.link,
  colorBrandForeground2Hover: palette.linkHover,
  colorBrandForeground2Pressed: palette.linkPressed,
  colorBrandForegroundLink: palette.link,
  colorBrandForegroundLinkHover: palette.linkHover,
  colorBrandForegroundLinkPressed: palette.linkPressed,
  colorBrandForegroundLinkSelected: palette.link,
  colorBrandForegroundOnLight: palette.link,
  colorBrandForegroundOnLightHover: palette.linkHover,
  colorBrandForegroundOnLightPressed: palette.linkPressed,
  colorBrandForegroundOnLightSelected: palette.link,
  colorNeutralForeground2BrandHover: palette.textStrong,
  colorNeutralForeground2BrandPressed: palette.textStrong,
  colorNeutralForeground2BrandSelected: palette.textStrong,
  colorNeutralForeground3BrandHover: palette.textStrong,
  colorNeutralForeground3BrandPressed: palette.textStrong,
  colorNeutralForeground3BrandSelected: palette.textStrong,

  // Checkbox / radio / switch fills and compound strokes: dark, visible on white.
  colorCompoundBrandBackground: palette.textStrong,
  colorCompoundBrandBackgroundHover: '#424242',
  colorCompoundBrandBackgroundPressed: '#1C1C1C',
  colorCompoundBrandForeground1: palette.textStrong,
  colorCompoundBrandForeground1Hover: '#424242',
  colorCompoundBrandForeground1Pressed: '#1C1C1C',
  colorCompoundBrandStroke: palette.textStrong,
  colorCompoundBrandStrokeHover: '#424242',
  colorCompoundBrandStrokePressed: '#1C1C1C',

  // Danger = Shell red.
  colorPaletteRedBackground3: palette.red,
  colorPaletteRedForeground1: palette.redText,
  colorPaletteRedForeground3: palette.red,
  colorPaletteRedBorderActive: palette.red,
  colorStatusDangerBackground3: palette.red,
  colorStatusDangerForeground1: palette.redText,
  colorStatusDangerForeground3: palette.redText,
  colorStatusDangerBorderActive: palette.red,
};

import type { ReactNode } from 'react';
import { makeStyles, mergeClasses, tokens } from '@fluentui/react-components';

const useStyles = makeStyles({
  row: {
    display: 'flex',
    flexWrap: 'wrap',
    alignItems: 'center',
    gap: tokens.spacingHorizontalS,
    minWidth: 0,
  },
  end: { justifyContent: 'flex-end' },
  between: { justifyContent: 'space-between' },
});

/** A row of buttons / filters / chips that wraps onto the next line instead of overflowing.
 * `align="end"` right-aligns (form actions); `"between"` pushes first and last groups apart. */
export function Toolbar(props: {
  children: ReactNode;
  align?: 'start' | 'end' | 'between';
  className?: string;
  /** Accessible name when the row is a toolbar of controls. */
  label?: string;
}) {
  const s = useStyles();
  return (
    <div
      className={mergeClasses(
        s.row,
        props.align === 'end' && s.end,
        props.align === 'between' && s.between,
        props.className,
      )}
      role={props.label ? 'toolbar' : undefined}
      aria-label={props.label}
    >
      {props.children}
    </div>
  );
}

/** Alias with the name used for form footers. */
export const ActionsRow = Toolbar;

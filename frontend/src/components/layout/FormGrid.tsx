import type { CSSProperties, ReactNode } from 'react';
import { makeStyles, mergeClasses, tokens } from '@fluentui/react-components';

const useStyles = makeStyles({
  grid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(min(100%, var(--orion-col, 240px)), 1fr))',
    columnGap: tokens.spacingHorizontalL,
    rowGap: tokens.spacingVerticalM,
    alignItems: 'start',
    minWidth: 0,
  },
  full: { gridColumn: '1 / -1', minWidth: 0 },
});

/** Form columns that follow the width of the CONTENT (not the viewport): as many columns of at
 * least `minColWidth` px as fit, one column when narrow. Wrap a field in <FormFull> to span the row. */
export function FormGrid(props: {
  children: ReactNode;
  /** Minimum column width in px (default 240). */
  minColWidth?: number;
  className?: string;
}) {
  const s = useStyles();
  const style = { '--orion-col': `${props.minColWidth ?? 240}px` } as CSSProperties;
  return (
    <div className={mergeClasses(s.grid, props.className)} style={style}>
      {props.children}
    </div>
  );
}

/** A cell of a FormGrid that spans the full row (names, descriptions, textareas, site lists). */
export function FormFull(props: { children: ReactNode; className?: string }) {
  const s = useStyles();
  return <div className={mergeClasses(s.full, props.className)}>{props.children}</div>;
}

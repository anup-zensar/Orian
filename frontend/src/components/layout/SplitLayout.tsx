import type { ReactNode } from 'react';
import { makeStyles, mergeClasses, tokens } from '@fluentui/react-components';

const useStyles = makeStyles({
  root: {
    display: 'flex',
    flexWrap: 'wrap',
    gap: tokens.spacingHorizontalL,
    alignItems: 'flex-start',
    minWidth: 0,
  },
  main: { flex: '1 1 520px', minWidth: 0 },
  aside: { flex: '1 1 280px', minWidth: 0, maxWidth: '380px' },
  sticky: { position: 'sticky', top: tokens.spacingVerticalL },
});

/** Main column + aside card. The aside sits beside the main column when the CONTENT is wide
 * enough and drops below it when not (flex-wrap, no media query, so the open Orion panel and
 * the left nav are accounted for automatically). */
export function SplitLayout(props: {
  main: ReactNode;
  aside: ReactNode;
  /** Keep the aside in view while the main column scrolls (default true). */
  stickyAside?: boolean;
}) {
  const s = useStyles();
  return (
    <div className={s.root}>
      <div className={s.main}>{props.main}</div>
      <div className={mergeClasses(s.aside, props.stickyAside !== false && s.sticky)}>
        {props.aside}
      </div>
    </div>
  );
}

import type { ReactNode } from 'react';
import { makeStyles, mergeClasses, tokens } from '@fluentui/react-components';
import { cardRadius } from '../theme/orionTheme';

// Soft shadows on the edge that has more columns: the two white gradients scroll with the content
// ("local") and cover the grey shadows ("scroll") once the user reaches that edge.
const edgeShadows = [
  `linear-gradient(to right, ${tokens.colorNeutralBackground1} 30%, transparent)`,
  `linear-gradient(to left, ${tokens.colorNeutralBackground1} 30%, transparent)`,
  'radial-gradient(farthest-side at 0 50%, rgba(0, 0, 0, 0.14), transparent)',
  'radial-gradient(farthest-side at 100% 50%, rgba(0, 0, 0, 0.14), transparent)',
].join(', ');

const useStyles = makeStyles({
  wrap: {
    maxWidth: '100%',
    minWidth: 0,
    overflowX: 'auto',
    borderRadius: cardRadius,
    border: `1px solid ${tokens.colorNeutralStroke2}`,
    backgroundColor: tokens.colorNeutralBackground1,
    backgroundImage: edgeShadows,
    backgroundPosition: 'left center, right center, left center, right center',
    backgroundRepeat: 'no-repeat',
    backgroundSize: '40px 100%, 40px 100%, 14px 100%, 14px 100%',
    backgroundAttachment: 'local, local, scroll, scroll',
    '& table': { width: '100%' },
    '& th': { whiteSpace: 'nowrap' },
    '& .fui-Badge': { whiteSpace: 'nowrap', flexShrink: 0 },
  },
  stickyFirst: {
    '& th:first-child': {
      position: 'sticky',
      left: 0,
      zIndex: 2,
      backgroundColor: tokens.colorNeutralBackground1,
    },
    '& td:first-child:not([colspan])': {
      position: 'sticky',
      left: 0,
      zIndex: 1,
      backgroundColor: tokens.colorNeutralBackground1,
      boxShadow: `1px 0 0 ${tokens.colorNeutralStroke2}`,
    },
  },
});

/** Wraps a wide table so it scrolls inside its own box (never the page), with a soft shadow on the
 * edge that has more columns. `stickyFirstColumn` keeps the first column (the row name) visible
 * while scrolling. Header cells and chips never wrap. The box is keyboard-scrollable. */
export function DataTable(props: {
  children: ReactNode;
  /** Accessible name of the scroll region, e.g. "OCET lines". */
  label: string;
  stickyFirstColumn?: boolean;
  className?: string;
}) {
  const s = useStyles();
  return (
    <div
      role="region"
      aria-label={props.label}
      tabIndex={0}
      className={mergeClasses(s.wrap, props.stickyFirstColumn && s.stickyFirst, props.className)}
    >
      {props.children}
    </div>
  );
}

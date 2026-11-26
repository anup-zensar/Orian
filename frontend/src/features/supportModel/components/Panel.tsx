import type { ReactNode } from 'react';
import { Subtitle2, makeStyles, tokens } from '@fluentui/react-components';

const useStyles = makeStyles({
  panel: {
    display: 'flex',
    flexDirection: 'column',
    gap: tokens.spacingVerticalM,
    minWidth: 0,
    padding: tokens.spacingVerticalM,
    paddingInline: tokens.spacingHorizontalM,
    border: `1px solid ${tokens.colorNeutralStroke2}`,
    borderRadius: tokens.borderRadiusLarge,
    backgroundColor: tokens.colorNeutralBackground1,
  },
  head: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: tokens.spacingHorizontalM,
    flexWrap: 'wrap',
    minWidth: 0,
  },
  title: { fontWeight: tokens.fontWeightSemibold, color: tokens.colorNeutralForeground1 },
});

/** A quiet box inside one of the four support model section cards (no shadow, so cards never
 * look nested). */
export function Panel(props: { title: string; actions?: ReactNode; children: ReactNode }) {
  const s = useStyles();
  return (
    <section className={s.panel} aria-label={props.title}>
      <div className={s.head}>
        <Subtitle2 as="h3" className={s.title}>
          {props.title}
        </Subtitle2>
        {props.actions}
      </div>
      {props.children}
    </section>
  );
}

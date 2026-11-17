import type { ReactNode } from 'react';
import { Subtitle2, makeStyles, tokens } from '@fluentui/react-components';

const useStyles = makeStyles({
  card: {
    display: 'flex',
    flexDirection: 'column',
    gap: tokens.spacingVerticalM,
    minWidth: 0,
    padding: tokens.spacingVerticalL,
    border: `1px solid ${tokens.colorNeutralStroke2}`,
    borderRadius: tokens.borderRadiusMedium,
    backgroundColor: tokens.colorNeutralBackground1,
    boxShadow: tokens.shadow2,
  },
  head: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: tokens.spacingHorizontalM,
    flexWrap: 'wrap',
  },
});

/** Titled card used by every dashboard / control-tower section. */
export function SectionCard(props: {
  title: string;
  actions?: ReactNode;
  children: ReactNode;
  id?: string;
}) {
  const s = useStyles();
  return (
    <section
      className={s.card}
      id={props.id}
      tabIndex={props.id ? -1 : undefined}
      aria-label={props.title}
    >
      <div className={s.head}>
        <Subtitle2 as="h2">{props.title}</Subtitle2>
        {props.actions}
      </div>
      {props.children}
    </section>
  );
}

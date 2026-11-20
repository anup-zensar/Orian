import type { ReactNode } from 'react';
import { Subtitle2, makeStyles, mergeClasses, tokens } from '@fluentui/react-components';
import { ai, cardRadius, cardShadow } from '../theme/orionTheme';

const useStyles = makeStyles({
  card: {
    display: 'flex',
    flexDirection: 'column',
    gap: tokens.spacingVerticalM,
    minWidth: 0,
    padding: tokens.spacingVerticalL,
    paddingInline: tokens.spacingHorizontalXL,
    border: `1px solid ${tokens.colorNeutralStroke2}`,
    borderRadius: cardRadius,
    backgroundColor: tokens.colorNeutralBackground1,
    boxShadow: cardShadow,
  },
  ai: { borderTop: `3px solid ${ai.main}` },
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

/** Titled white card (Shell look: subtle border, 12 px radius, soft shadow). `tone="ai"` adds the
 * purple Orion accent line for cards that Orion wrote. */
export function SectionCard(props: {
  title: string;
  actions?: ReactNode;
  children: ReactNode;
  id?: string;
  tone?: 'ai';
}) {
  const s = useStyles();
  return (
    <section
      className={mergeClasses(s.card, props.tone === 'ai' && s.ai)}
      id={props.id}
      tabIndex={props.id ? -1 : undefined}
      aria-label={props.title}
    >
      <div className={s.head}>
        <Subtitle2 as="h2" className={s.title}>
          {props.title}
        </Subtitle2>
        {props.actions}
      </div>
      {props.children}
    </section>
  );
}

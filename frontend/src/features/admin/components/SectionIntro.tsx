import type { ReactNode } from 'react';
import { Body1, makeStyles, tokens } from '@fluentui/react-components';

const useStyles = makeStyles({
  intro: { color: tokens.colorNeutralForeground2, maxWidth: '80ch' },
});

/** The one plain sentence at the top of every admin section: what you can change and what it affects. */
export function SectionIntro({ children }: { children: ReactNode }) {
  const s = useStyles();
  return <Body1 className={s.intro}>{children}</Body1>;
}

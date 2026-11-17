import type { ReactNode } from 'react';
import { Subtitle1, Body1, makeStyles, tokens } from '@fluentui/react-components';

const useStyles = makeStyles({
  root: {
    display: 'flex',
    alignItems: 'flex-start',
    justifyContent: 'space-between',
    gap: tokens.spacingHorizontalL,
    marginBottom: tokens.spacingVerticalL,
    flexWrap: 'wrap',
  },
  text: { display: 'flex', flexDirection: 'column', gap: tokens.spacingVerticalXS },
  actions: { display: 'flex', gap: tokens.spacingHorizontalS },
});

export function PageHeader(props: { title: string; subtitle?: string; actions?: ReactNode }) {
  const s = useStyles();
  return (
    <div className={s.root}>
      <div className={s.text}>
        <Subtitle1 as="h1">{props.title}</Subtitle1>
        {props.subtitle && <Body1>{props.subtitle}</Body1>}
      </div>
      {props.actions && <div className={s.actions}>{props.actions}</div>}
    </div>
  );
}

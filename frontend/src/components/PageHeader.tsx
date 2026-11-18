import { useEffect, type ReactNode } from 'react';
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

/** Page heading. Top-level pages are the h1 and set the document title; workspace tabs pass as="h2". */
export function PageHeader(props: {
  title: string;
  subtitle?: string;
  actions?: ReactNode;
  as?: 'h1' | 'h2';
}) {
  const s = useStyles();
  const level = props.as ?? 'h1';
  useEffect(() => {
    if (level === 'h1') document.title = `${props.title} - Orion`;
  }, [props.title, level]);
  return (
    <div className={s.root}>
      <div className={s.text}>
        <Subtitle1 as={level}>{props.title}</Subtitle1>
        {props.subtitle && <Body1>{props.subtitle}</Body1>}
      </div>
      {props.actions && <div className={s.actions}>{props.actions}</div>}
    </div>
  );
}

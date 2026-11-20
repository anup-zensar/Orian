import { useEffect, type ReactNode } from 'react';
import { makeStyles, tokens } from '@fluentui/react-components';

const useStyles = makeStyles({
  root: {
    display: 'flex',
    alignItems: 'flex-start',
    justifyContent: 'space-between',
    gap: tokens.spacingHorizontalL,
    rowGap: tokens.spacingVerticalS,
    marginBottom: tokens.spacingVerticalL,
    flexWrap: 'wrap',
    minWidth: 0,
  },
  text: {
    display: 'flex',
    flexDirection: 'column',
    gap: tokens.spacingVerticalXS,
    flex: '1 1 320px',
    minWidth: 0,
  },
  title: {
    margin: 0,
    fontSize: '24px',
    lineHeight: '32px',
    fontWeight: tokens.fontWeightSemibold,
    color: tokens.colorNeutralForeground1,
    overflowWrap: 'anywhere',
  },
  titleSmall: { fontSize: '20px', lineHeight: '28px' },
  subtitle: {
    margin: 0,
    fontSize: tokens.fontSizeBase300,
    lineHeight: tokens.lineHeightBase300,
    color: tokens.colorNeutralForeground3,
  },
  // Actions sit on the right; when the content is narrow they wrap below the title.
  actions: {
    display: 'flex',
    flexWrap: 'wrap',
    gap: tokens.spacingHorizontalS,
    alignItems: 'center',
    minWidth: 0,
  },
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
  const Title = level;
  return (
    <div className={s.root}>
      <div className={s.text}>
        <Title className={level === 'h2' ? `${s.title} ${s.titleSmall}` : s.title}>
          {props.title}
        </Title>
        {props.subtitle && <p className={s.subtitle}>{props.subtitle}</p>}
      </div>
      {props.actions && <div className={s.actions}>{props.actions}</div>}
    </div>
  );
}

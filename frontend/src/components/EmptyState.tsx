import type { ReactNode } from 'react';
import { Body1, makeStyles, tokens } from '@fluentui/react-components';
import { Info20Regular } from '@fluentui/react-icons';

const useStyles = makeStyles({
  root: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    gap: tokens.spacingVerticalM,
    padding: tokens.spacingVerticalXXL,
    color: tokens.colorNeutralForeground2,
    textAlign: 'center',
    minWidth: 0,
  },
  icon: {
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    width: '40px',
    height: '40px',
    borderRadius: '50%',
    backgroundColor: tokens.colorBrandBackground2,
    color: tokens.colorNeutralForeground1,
  },
});

/** Empty list: a helpful message plus an optional next-step action (spec section 12). */
export function EmptyState({ message, action }: { message: string; action?: ReactNode }) {
  const s = useStyles();
  return (
    <div className={s.root}>
      <span className={s.icon} aria-hidden>
        <Info20Regular />
      </span>
      <Body1>{message}</Body1>
      {action}
    </div>
  );
}

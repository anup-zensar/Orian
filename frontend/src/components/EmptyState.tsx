import type { ReactNode } from 'react';
import { Body1, makeStyles, tokens } from '@fluentui/react-components';

const useStyles = makeStyles({
  root: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    gap: tokens.spacingVerticalM,
    padding: tokens.spacingVerticalXXL,
    color: tokens.colorNeutralForeground2,
    textAlign: 'center',
  },
});

/** Empty list: a helpful message plus an optional next-step action (spec section 12). */
export function EmptyState({ message, action }: { message: string; action?: ReactNode }) {
  const s = useStyles();
  return (
    <div className={s.root}>
      <Body1>{message}</Body1>
      {action}
    </div>
  );
}

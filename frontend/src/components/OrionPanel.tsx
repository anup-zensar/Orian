import {
  Body1,
  Button,
  Caption1,
  DrawerBody,
  DrawerFooter,
  DrawerHeader,
  DrawerHeaderTitle,
  InlineDrawer,
  makeStyles,
  tokens,
} from '@fluentui/react-components';
import { Dismiss24Regular } from '@fluentui/react-icons';
import { AiBadge } from './AiBadge';

const useStyles = makeStyles({
  drawer: { width: '420px', flexShrink: 0 },
  footer: { display: 'flex', alignItems: 'center', gap: tokens.spacingHorizontalS },
});

/** Right-side Orion assistant panel (FR-090). Content arrives in M8; the frame is final. */
export function OrionPanel({ open, onClose }: { open: boolean; onClose: () => void }) {
  const s = useStyles();
  return (
    <InlineDrawer
      className={s.drawer}
      position="end"
      open={open}
      separator
      aria-label="Orion assistant"
    >
      <DrawerHeader>
        <DrawerHeaderTitle
          action={
            <Button
              appearance="subtle"
              aria-label="Close Orion panel"
              icon={<Dismiss24Regular />}
              onClick={onClose}
            />
          }
        >
          Orion – Operate Readiness Agent
        </DrawerHeaderTitle>
      </DrawerHeader>
      <DrawerBody>
        <Body1>Quick actions and chat arrive in M8</Body1>
      </DrawerBody>
      <DrawerFooter className={s.footer}>
        <AiBadge />
        <Caption1>Orion recommends and drafts. People decide.</Caption1>
      </DrawerFooter>
    </InlineDrawer>
  );
}

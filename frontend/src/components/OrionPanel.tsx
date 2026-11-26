import {
  Button,
  DrawerBody,
  DrawerHeader,
  DrawerHeaderTitle,
  InlineDrawer,
  OverlayDrawer,
  makeStyles,
  tokens,
} from '@fluentui/react-components';
import { Dismiss24Regular, Sparkle20Filled } from '@fluentui/react-icons';
import { ai } from '../theme/orionTheme';
import { useEffect, useRef, useState } from 'react';
import { OrionChat } from '../features/orion/OrionChat';

const useStyles = makeStyles({
  drawer: {
    width: 'clamp(340px, 28vw, 420px)',
    maxWidth: '100vw',
    flexShrink: 0,
    borderTop: `3px solid ${ai.main}`,
    backgroundColor: tokens.colorNeutralBackground1,
  },
  header: { backgroundColor: ai.tint },
  title: {
    display: 'inline-flex',
    alignItems: 'center',
    gap: tokens.spacingHorizontalS,
    fontSize: tokens.fontSizeBase400,
    lineHeight: tokens.lineHeightBase400,
    fontWeight: tokens.fontWeightSemibold,
  },
  mark: {
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    width: '24px',
    height: '24px',
    flexShrink: 0,
    borderRadius: '50%',
    backgroundColor: ai.main,
    color: tokens.colorNeutralForegroundInverted,
  },
  body: { display: 'flex', flexDirection: 'column', minHeight: 0, overflow: 'hidden' },
});

/** Below 1200 px the panel overlays the page instead of squeezing it (the workspace needs width). */
function useNarrow() {
  const query = '(max-width: 1199px)';
  const [narrow, setNarrow] = useState(
    () => typeof window !== 'undefined' && !!window.matchMedia?.(query).matches,
  );
  useEffect(() => {
    const mq = window.matchMedia?.(query);
    if (!mq) return;
    const on = () => setNarrow(mq.matches);
    mq.addEventListener('change', on);
    return () => mq.removeEventListener('change', on);
  }, []);
  return narrow;
}

/** Right-side Orion assistant panel (FR-090): the shared chat, available on every page. */
export function OrionPanel({ open, onClose }: { open: boolean; onClose: () => void }) {
  const s = useStyles();
  const narrow = useNarrow();
  const wasOpen = useRef(false);
  useEffect(() => {
    // Keyboard users: focus the message box on open, return to the top-bar button on close.
    if (open) {
      const t = window.setTimeout(
        () => document.querySelector<HTMLElement>('[aria-label="Message to Orion"]')?.focus(),
        50,
      );
      wasOpen.current = true;
      return () => window.clearTimeout(t);
    }
    if (wasOpen.current) {
      wasOpen.current = false;
      document.querySelector<HTMLElement>('[data-orion-toggle]')?.focus();
    }
  }, [open]);
  const Drawer = narrow ? OverlayDrawer : InlineDrawer;
  const extra = narrow
    ? { modal: false, onOpenChange: (_: unknown, d: { open: boolean }) => !d.open && onClose() }
    : { separator: true };
  return (
    <Drawer
      className={s.drawer}
      position="end"
      open={open}
      role="complementary"
      aria-label="Orion assistant"
      {...extra}
    >
      <DrawerHeader className={s.header}>
        <DrawerHeaderTitle
          action={
            <>
              <Button
                appearance="subtle"
                aria-label="Close Orion panel"
                icon={<Dismiss24Regular />}
                onClick={onClose}
              />
            </>
          }
        >
          <span className={s.title}>
            <span className={s.mark} aria-hidden>
              <Sparkle20Filled />
            </span>
            Orion – Operate Readiness Intelligence &amp; Orchestration Navigator
          </span>
        </DrawerHeaderTitle>
      </DrawerHeader>
      <DrawerBody className={s.body}>
        <OrionChat />
      </DrawerBody>
    </Drawer>
  );
}

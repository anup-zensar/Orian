import { Suspense, useEffect, useMemo, useState } from 'react';
import { Outlet, useMatch } from 'react-router';
import { Toaster, makeStyles, tokens } from '@fluentui/react-components';
import { useAuth } from '../auth/useAuth';
import { chatStore } from '../features/orion/chatStore';
import { useMe } from '../features/users/api';
import { LoadingState } from '../components/LoadingState';
import { OrionPanel } from '../components/OrionPanel';
import {
  OrionPanelContext,
  type OrionPanelState,
  type OrionPanelTarget,
} from '../features/orion/panelContext';
import { TOASTER_ID } from '../hooks/useApiErrorToast';
import { SideNav } from './SideNav';
import { TopBar } from './TopBar';

const useStyles = makeStyles({
  root: {
    display: 'flex',
    flexDirection: 'column',
    height: '100vh',
    backgroundColor: tokens.colorNeutralBackground3,
  },
  body: { display: 'flex', flexGrow: 1, minHeight: 0 },
  skip: {
    position: 'absolute',
    left: '-9999px',
    top: tokens.spacingVerticalS,
    zIndex: 1000,
    padding: '8px 16px',
    backgroundColor: tokens.colorNeutralBackground1,
    color: tokens.colorBrandForeground1,
    ':focus': { left: tokens.spacingHorizontalS, outline: `2px solid ${tokens.colorStrokeFocus2}` },
  },
  main: {
    flexGrow: 1,
    flexBasis: 0,
    minWidth: 0,
    overflowY: 'auto',
    overflowX: 'hidden',
    padding: '24px',
    '@media (max-width: 700px)': { padding: '16px' },
    // Every direct child of the page may shrink: no content pushes the page wider than the area.
    '> *': { minWidth: 0 },
  },
});

/** True while the media query matches (used for layout decisions that depend on the viewport). */
function useMediaQuery(query: string) {
  const [matches, setMatches] = useState(
    () => typeof window !== 'undefined' && !!window.matchMedia?.(query).matches,
  );
  useEffect(() => {
    const mq = window.matchMedia?.(query);
    if (!mq) return;
    const on = () => setMatches(mq.matches);
    on();
    mq.addEventListener('change', on);
    return () => mq.removeEventListener('change', on);
  }, [query]);
  return matches;
}

/** Global layout (FR-002): left nav + top bar + page outlet + right-side Orion panel. */
export function AppShell() {
  const s = useStyles();
  const inlinePanelRange = useMediaQuery('(min-width: 1200px) and (max-width: 1599px)');
  const railWidth = useMediaQuery('(max-width: 899px)');
  const me = useMe();
  const [orionOpen, setOrionOpen] = useState(false);
  const [orionTarget, setOrionTarget] = useState<OrionPanelTarget>({});
  const { userId } = useAuth();
  const onOrionPage = !!useMatch('/orion');
  useEffect(() => chatStore.resetFor(userId), [userId]);
  const isAdmin = !!me.data?.permissions.includes('admin');
  const orionPanel = useMemo<OrionPanelState>(
    () => ({
      isOpen: orionOpen,
      target: orionTarget,
      open: (target) => {
        setOrionTarget(target ?? {});
        setOrionOpen(true);
      },
      close: () => setOrionOpen(false),
      toggle: () => setOrionOpen((o) => !o),
    }),
    [orionOpen, orionTarget],
  );

  return (
    <OrionPanelContext.Provider value={orionPanel}>
      <div className={s.root}>
        <a href="#main" className={s.skip}>
          Skip to main content
        </a>
        <TopBar orionOpen={orionOpen} onToggleOrion={() => setOrionOpen((o) => !o)} />
        <div className={s.body}>
          <SideNav
            isAdmin={isAdmin}
            collapsed={railWidth || (inlinePanelRange && orionOpen && !onOrionPage)}
          />
          <main id="main" tabIndex={-1} className={s.main}>
            <Suspense fallback={<LoadingState />}>
              <Outlet />
            </Suspense>
          </main>
          <OrionPanel open={orionOpen && !onOrionPage} onClose={() => setOrionOpen(false)} />
        </div>
        <Toaster toasterId={TOASTER_ID} position="top-end" />
      </div>
    </OrionPanelContext.Provider>
  );
}

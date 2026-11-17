import { Suspense, useState } from 'react';
import { Outlet } from 'react-router';
import { Toaster, makeStyles, tokens } from '@fluentui/react-components';
import { useMe } from '../features/users/api';
import { LoadingState } from '../components/LoadingState';
import { OrionPanel } from '../components/OrionPanel';
import { TOASTER_ID } from '../hooks/useApiErrorToast';
import { SideNav } from './SideNav';
import { TopBar } from './TopBar';

const useStyles = makeStyles({
  root: {
    display: 'flex',
    flexDirection: 'column',
    height: '100vh',
    backgroundColor: tokens.colorNeutralBackground1,
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
  main: { flexGrow: 1, minWidth: 0, overflow: 'auto', padding: tokens.spacingHorizontalXXL },
});

/** Global layout (FR-002): left nav + top bar + page outlet + right-side Orion panel. */
export function AppShell() {
  const s = useStyles();
  const me = useMe();
  const [orionOpen, setOrionOpen] = useState(false);
  const isAdmin = me.data?.user.role === 'ADMIN';

  return (
    <div className={s.root}>
      <a href="#main" className={s.skip}>
        Skip to main content
      </a>
      <TopBar orionOpen={orionOpen} onToggleOrion={() => setOrionOpen((o) => !o)} />
      <div className={s.body}>
        <SideNav isAdmin={isAdmin} />
        <main id="main" tabIndex={-1} className={s.main}>
          <Suspense fallback={<LoadingState />}>
            <Outlet />
          </Suspense>
        </main>
        <OrionPanel open={orionOpen} onClose={() => setOrionOpen(false)} />
      </div>
      <Toaster toasterId={TOASTER_ID} position="top-end" />
    </div>
  );
}

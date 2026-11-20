import { lazy, type ComponentType } from 'react';
import { Navigate, createBrowserRouter } from 'react-router';
import { RequireAuth } from './auth/RequireAuth';
import { RequireRole } from './auth/RequireRole';
import { AppShell } from './layout/AppShell';
import { LoginPage } from './pages/LoginPage';

// Route-level code splitting (F9): every page except the login page and the shell is lazy.
// AppShell wraps <Outlet /> in <Suspense fallback={<LoadingState />}>.
const named = <T extends Record<string, ComponentType>>(load: () => Promise<T>, key: keyof T) =>
  lazy(async () => ({ default: (await load())[key] }));

const AdminPage = named(() => import('./features/admin/AdminPage'), 'AdminPage');
const ApprovalsPage = named(() => import('./features/approvals/ApprovalsPage'), 'ApprovalsPage');
const AuditPage = named(() => import('./features/audit/AuditPage'), 'AuditPage');
const DraftsPage = named(() => import('./features/drafts/DraftsPage'), 'DraftsPage');
const LeadershipUpdatesPage = named(
  () => import('./features/leadership/LeadershipUpdatesPage'),
  'LeadershipUpdatesPage',
);
const NewTransitionPage = named(
  () => import('./features/intake/NewTransitionPage'),
  'NewTransitionPage',
);
const OrionPage = named(() => import('./features/orion/OrionPage'), 'OrionPage');
const OutboxPage = named(() => import('./features/outbox/OutboxPage'), 'OutboxPage');
const ScopePage = named(() => import('./features/intake/ScopePage'), 'ScopePage');
const TieringPage = named(() => import('./features/intake/TieringPage'), 'TieringPage');
const DashboardPage = named(() => import('./features/dashboard/DashboardPage'), 'DashboardPage');
const ControlTowerPage = named(
  () => import('./features/controlTower/ControlTowerPage'),
  'ControlTowerPage',
);
const TransitionsPage = named(
  () => import('./features/transitions/TransitionsPage'),
  'TransitionsPage',
);
const NotFoundPage = named(() => import('./pages/NotFoundPage'), 'NotFoundPage');
const RedirectToOverview = named(
  () => import('./features/transitions/RedirectToOverview'),
  'RedirectToOverview',
);
const TransitionWorkspace = named(
  () => import('./features/transitions/TransitionWorkspace'),
  'TransitionWorkspace',
);

export const router = createBrowserRouter([
  { path: '/login', element: <LoginPage /> },
  {
    element: <RequireAuth />,
    children: [
      {
        element: <AppShell />,
        children: [
          { path: '/', element: <DashboardPage /> },
          { path: '/control-tower', element: <ControlTowerPage /> },
          { path: '/transitions', element: <TransitionsPage /> },
          { path: '/transitions/new', element: <NewTransitionPage /> },
          { path: '/transitions/:id/tiering', element: <TieringPage /> },
          { path: '/transitions/:id/scope', element: <ScopePage /> },
          { path: '/transitions/:id', element: <RedirectToOverview /> },
          { path: '/transitions/:id/:tab', element: <TransitionWorkspace /> },
          { path: '/approvals', element: <ApprovalsPage /> },
          { path: '/drafts', element: <DraftsPage /> },
          { path: '/outbox', element: <OutboxPage /> },
          { path: '/leadership-updates', element: <LeadershipUpdatesPage /> },
          { path: '/support-models', element: <Navigate to="/transitions" replace /> },
          {
            // UI guard only; the backend enforces admin access (403).
            path: '/admin/*',
            element: <RequireRole roles={['ADMIN']} />,
            children: [{ path: '*', element: <AdminPage /> }],
          },
          { path: '/audit', element: <AuditPage /> },
          { path: '/orion', element: <OrionPage /> },
          { path: '*', element: <NotFoundPage /> },
        ],
      },
    ],
  },
]);

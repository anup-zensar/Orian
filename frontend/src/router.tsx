import { lazy, type ComponentType } from 'react';
import { createBrowserRouter } from 'react-router';
import { RequireAuth } from './auth/RequireAuth';
import { RequireRole } from './auth/RequireRole';
import { AppShell } from './layout/AppShell';
import { LoginPage } from './pages/LoginPage';

// Route-level code splitting (F9): every page except the login page and the shell is lazy.
// AppShell wraps <Outlet /> in <Suspense fallback={<LoadingState />}>.
const named = <T extends Record<string, ComponentType>>(load: () => Promise<T>, key: keyof T) =>
  lazy(async () => ({ default: (await load())[key] }));

const placeholders = () => import('./pages/placeholders');
const AdminPage = named(placeholders, 'AdminPage');
const ApprovalsPage = named(placeholders, 'ApprovalsPage');
const AuditPage = named(placeholders, 'AuditPage');
const ControlTowerPage = named(placeholders, 'ControlTowerPage');
const DashboardPage = named(placeholders, 'DashboardPage');
const DraftsPage = named(placeholders, 'DraftsPage');
const LeadershipUpdatesPage = named(placeholders, 'LeadershipUpdatesPage');
const NewTransitionPage = named(placeholders, 'NewTransitionPage');
const OrionFullPage = named(placeholders, 'OrionFullPage');
const OutboxPage = named(placeholders, 'OutboxPage');
const ScopePage = named(placeholders, 'ScopePage');
const SupportModelsPage = named(placeholders, 'SupportModelsPage');
const TieringPage = named(placeholders, 'TieringPage');
const TransitionsPage = named(placeholders, 'TransitionsPage');
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
          { path: '/support-models', element: <SupportModelsPage /> },
          {
            // UI guard only; the backend enforces admin access (403).
            path: '/admin/*',
            element: <RequireRole roles={['ADMIN']} />,
            children: [{ path: '*', element: <AdminPage /> }],
          },
          { path: '/audit', element: <AuditPage /> },
          { path: '/orion', element: <OrionFullPage /> },
          { path: '*', element: <NotFoundPage /> },
        ],
      },
    ],
  },
]);

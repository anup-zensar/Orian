import { Suspense } from 'react';
import { NavLink, Navigate, useLocation, useParams } from 'react-router';
import { makeStyles, mergeClasses, tokens } from '@fluentui/react-components';
import { ErrorState } from '../../components/ErrorState';
import { LoadingState } from '../../components/LoadingState';
import { WorkspaceHeader } from '../workspace/header/WorkspaceHeader';
import { TAB_COMPONENTS } from '../workspace/tabRegistry';
import { useTransition } from '../transition/api';
import { useTypeFlags } from './typeFlags';
import { WORKSPACE_TABS, showsAiPlaybook, visibleTabs } from './workspaceTabs';

const useStyles = makeStyles({
  tabs: {
    display: 'flex',
    flexWrap: 'nowrap',
    overflowX: 'auto',
    overflowY: 'hidden',
    gap: tokens.spacingHorizontalXS,
    scrollbarWidth: 'thin',
    // Scroll affordance: soft edge shadows appear only on the side that has more tabs.
    backgroundImage: `linear-gradient(to right, ${tokens.colorNeutralBackground1} 30%, transparent), linear-gradient(to left, ${tokens.colorNeutralBackground1} 30%, transparent), linear-gradient(to right, rgba(0,0,0,0.22), transparent), linear-gradient(to left, rgba(0,0,0,0.22), transparent)`,
    backgroundRepeat: 'no-repeat',
    backgroundSize: '32px 100%, 32px 100%, 12px 100%, 12px 100%',
    backgroundPosition: 'left center, right center, left center, right center',
    backgroundAttachment: 'local, local, scroll, scroll',
    borderBottom: `1px solid ${tokens.colorNeutralStroke2}`,
    marginBottom: tokens.spacingVerticalL,
  },
  tab: {
    flexShrink: 0,
    whiteSpace: 'nowrap',
    padding: '8px 12px',
    color: tokens.colorNeutralForeground2,
    textDecorationLine: 'none',
    borderBottom: '2px solid transparent',
    ':hover': { color: tokens.colorNeutralForeground1 },
    ':focus-visible': { outline: `2px solid ${tokens.colorStrokeFocus2}` },
  },
  active: {
    color: tokens.colorBrandForeground1,
    borderBottomColor: tokens.colorBrandForeground1,
    fontWeight: tokens.fontWeightSemibold,
  },
});

/** Transition workspace (FR-030): header + tabs; each tab is its own lazy module (A-31). */
export function TransitionWorkspace() {
  const s = useStyles();
  const { id = '', tab = 'overview' } = useParams();
  const { search, hash } = useLocation();
  const { data: detail, error, isPending } = useTransition(id);
  const flags = useTypeFlags(detail);
  const current = WORKSPACE_TABS.find((t) => t.key === tab);
  const TabComponent = current ? TAB_COMPONENTS[current.key] : undefined;
  const redirect = (
    <Navigate
      to={{ pathname: `/transitions/${encodeURIComponent(id)}/overview`, search, hash }}
      replace
    />
  );
  if (!current || !TabComponent) return redirect;
  // The AI playbook tab is hidden (and its URL redirected) unless the project type switches it on.
  if (detail && 'aiOnly' in current && !showsAiPlaybook(flags)) return redirect;

  const tabs = visibleTabs(flags);

  return (
    <>
      {isPending ? (
        <LoadingState rows={3} />
      ) : error || !detail ? (
        <ErrorState error={error} />
      ) : (
        <WorkspaceHeader detail={detail} />
      )}
      <nav className={s.tabs} aria-label="Transition tabs">
        {tabs.map((t) => (
          <NavLink
            key={t.key}
            to={`/transitions/${encodeURIComponent(id)}/${t.key}`}
            className={({ isActive }) => mergeClasses(s.tab, isActive && s.active)}
          >
            {t.label}
          </NavLink>
        ))}
      </nav>
      <Suspense fallback={<LoadingState />}>
        <TabComponent transitionId={id} />
      </Suspense>
    </>
  );
}

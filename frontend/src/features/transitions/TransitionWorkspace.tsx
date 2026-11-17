import { NavLink, Navigate, useLocation, useParams } from 'react-router';
import { makeStyles, mergeClasses, tokens } from '@fluentui/react-components';
import { PageHeader } from '../../components/PageHeader';
import { PlaceholderPage } from '../../components/PlaceholderPage';
import { WORKSPACE_TABS } from './workspaceTabs';

const useStyles = makeStyles({
  tabs: {
    display: 'flex',
    flexWrap: 'wrap',
    gap: tokens.spacingHorizontalXS,
    borderBottom: `1px solid ${tokens.colorNeutralStroke2}`,
    marginBottom: tokens.spacingVerticalL,
  },
  tab: {
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

/** Placeholder for the transition workspace (FR-030, built in M2): reads :id and :tab. */
export function TransitionWorkspace() {
  const s = useStyles();
  const { id = '', tab = 'overview' } = useParams();
  const { search, hash } = useLocation();
  const current = WORKSPACE_TABS.find((t) => t.key === tab);
  if (!current)
    return (
      <Navigate
        to={{ pathname: `/transitions/${encodeURIComponent(id)}/overview`, search, hash }}
        replace
      />
    );

  return (
    <>
      <PageHeader title={`Transition ${id}`} />
      <nav className={s.tabs} aria-label="Transition tabs">
        {WORKSPACE_TABS.map((t) => (
          <NavLink
            key={t.key}
            to={`/transitions/${id}/${t.key}`}
            className={({ isActive }) => mergeClasses(s.tab, isActive && s.active)}
          >
            {t.label}
          </NavLink>
        ))}
      </nav>
      <PlaceholderPage
        title={current.label}
        purpose={`The ${current.label} tab of transition ${id}.`}
        spec="FR-030 · built in M2"
      />
    </>
  );
}

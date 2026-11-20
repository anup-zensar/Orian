import { Suspense } from 'react';
import { NavLink, Navigate, useLocation, useNavigate, useParams } from 'react-router';
import {
  Button,
  Menu,
  MenuItem,
  MenuList,
  MenuPopover,
  MenuTrigger,
  Overflow,
  OverflowItem,
  makeStyles,
  mergeClasses,
  tokens,
  useIsOverflowItemVisible,
  useOverflowMenu,
} from '@fluentui/react-components';
import { MoreHorizontal20Regular } from '@fluentui/react-icons';
import { ErrorState } from '../../components/ErrorState';
import { LoadingState } from '../../components/LoadingState';
import { palette } from '../../theme/orionTheme';
import { WorkspaceHeader } from '../workspace/header/WorkspaceHeader';
import { TAB_COMPONENTS } from '../workspace/tabRegistry';
import { useTransition } from '../transition/api';
import { useTypeFlags } from './typeFlags';
import { WORKSPACE_TABS, showsAiPlaybook, visibleTabs } from './workspaceTabs';

const useStyles = makeStyles({
  tabs: {
    display: 'flex',
    alignItems: 'flex-end',
    minWidth: 0,
    gap: tokens.spacingHorizontalXS,
    borderBottom: `1px solid ${tokens.colorNeutralStroke2}`,
    marginBottom: tokens.spacingVerticalL,
  },
  overflowBox: { flex: 1, minWidth: 0, display: 'flex', gap: tokens.spacingHorizontalXS },
  tab: {
    flexShrink: 0,
    whiteSpace: 'nowrap',
    padding: '8px 12px',
    color: tokens.colorNeutralForeground2,
    textDecorationLine: 'none',
    borderBottom: '3px solid transparent',
    marginBottom: '-1px',
    borderTopLeftRadius: '6px',
    borderTopRightRadius: '6px',
    ':hover': {
      color: tokens.colorNeutralForeground1,
      backgroundColor: tokens.colorNeutralBackground1Hover,
    },
    ':focus-visible': { outline: `2px solid ${tokens.colorStrokeFocus2}` },
  },
  active: {
    color: tokens.colorNeutralForeground1,
    borderBottomColor: palette.yellow,
    fontWeight: tokens.fontWeightSemibold,
  },
  more: { flexShrink: 0, marginBottom: '2px' },
});

interface TabLink {
  key: string;
  label: string;
}

/** The "..." menu: lists the tabs that do not fit, so none is ever hidden without a cue. */
function OverflowTabsMenu({
  tabs,
  id,
  active,
}: {
  tabs: readonly TabLink[];
  id: string;
  active: string;
}) {
  const s = useStyles();
  const navigate = useNavigate();
  const { ref, isOverflowing, overflowCount } = useOverflowMenu<HTMLButtonElement>();
  if (!isOverflowing) return null;
  return (
    <Menu>
      <MenuTrigger disableButtonEnhancement>
        <Button
          ref={ref}
          className={s.more}
          appearance="subtle"
          icon={<MoreHorizontal20Regular />}
          aria-label={`More tabs (${overflowCount})`}
        />
      </MenuTrigger>
      <MenuPopover>
        <MenuList>
          <HiddenTabItems tabs={tabs} id={id} active={active} navigate={navigate} />
        </MenuList>
      </MenuPopover>
    </Menu>
  );
}

function HiddenTabItems(props: {
  tabs: readonly TabLink[];
  id: string;
  active: string;
  navigate: (to: string) => void;
}) {
  return (
    <>
      {props.tabs.map((t) => (
        <HiddenTabItem key={t.key} {...props} tab={t} />
      ))}
    </>
  );
}

function HiddenTabItem(p: {
  tab: TabLink;
  id: string;
  active: string;
  navigate: (to: string) => void;
}) {
  const visible = useIsOverflowItemVisible(p.tab.key);
  if (visible) return null;
  return (
    <MenuItem
      onClick={() => p.navigate(`/transitions/${encodeURIComponent(p.id)}/${p.tab.key}`)}
      style={p.active === p.tab.key ? { fontWeight: tokens.fontWeightSemibold } : undefined}
    >
      {p.tab.label}
    </MenuItem>
  );
}

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
        <Overflow minimumVisible={1}>
          <div className={s.overflowBox}>
            {tabs.map((t) => (
              <OverflowItem key={t.key} id={t.key} priority={t.key === current.key ? 100 : 0}>
                <NavLink
                  to={`/transitions/${encodeURIComponent(id)}/${t.key}`}
                  className={({ isActive }) => mergeClasses(s.tab, isActive && s.active)}
                >
                  {t.label}
                </NavLink>
              </OverflowItem>
            ))}
            <OverflowTabsMenu tabs={tabs} id={id} active={current.key} />
          </div>
        </Overflow>
      </nav>
      <Suspense fallback={<LoadingState />}>
        <TabComponent transitionId={id} />
      </Suspense>
    </>
  );
}

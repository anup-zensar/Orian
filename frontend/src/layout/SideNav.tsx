import { NavLink } from 'react-router';
import { makeStyles, mergeClasses, tokens } from '@fluentui/react-components';
import { NAV_ITEMS } from './navItems';

const useStyles = makeStyles({
  nav: {
    width: '220px',
    flexShrink: 0,
    display: 'flex',
    flexDirection: 'column',
    gap: '2px',
    padding: tokens.spacingVerticalS,
    borderRight: `1px solid ${tokens.colorNeutralStroke2}`,
    backgroundColor: tokens.colorNeutralBackground2,
    overflowY: 'auto',
  },
  link: {
    display: 'flex',
    alignItems: 'center',
    gap: tokens.spacingHorizontalS,
    padding: '8px 12px',
    borderRadius: tokens.borderRadiusMedium,
    color: tokens.colorNeutralForeground1,
    textDecorationLine: 'none',
    fontSize: tokens.fontSizeBase300,
    ':hover': { backgroundColor: tokens.colorNeutralBackground2Hover },
    ':focus-visible': { outline: `2px solid ${tokens.colorStrokeFocus2}`, outlineOffset: '-2px' },
  },
  active: {
    backgroundColor: tokens.colorNeutralBackground2Selected,
    fontWeight: tokens.fontWeightSemibold,
  },
});

/** Left navigation (FR-002). Real links, so keyboard Tab/Enter works and the URL is the state. */
export function SideNav({ isAdmin }: { isAdmin: boolean }) {
  const s = useStyles();
  return (
    <nav className={s.nav} aria-label="Main navigation">
      {NAV_ITEMS.filter((i) => !i.adminOnly || isAdmin).map(({ label, to, icon: Icon }) => (
        <NavLink
          key={to}
          to={to}
          // "/" and "/transitions" must not stay highlighted for their children.
          end={to === '/' || to === '/transitions'}
          className={({ isActive }) => mergeClasses(s.link, isActive && s.active)}
        >
          <Icon aria-hidden />
          {label}
        </NavLink>
      ))}
    </nav>
  );
}

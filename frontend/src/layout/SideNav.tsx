import { NavLink } from 'react-router';
import { Tooltip, makeStyles, mergeClasses, tokens } from '@fluentui/react-components';
import { palette } from '../theme/orionTheme';
import { NAV_ITEMS } from './navItems';

const useStyles = makeStyles({
  nav: {
    width: '232px',
    flexShrink: 0,
    display: 'flex',
    flexDirection: 'column',
    gap: '4px',
    padding: tokens.spacingVerticalM,
    borderRight: `1px solid ${tokens.colorNeutralStroke2}`,
    boxSizing: 'border-box',
    backgroundColor: tokens.colorNeutralBackground1,
    overflowY: 'auto',
    overflowX: 'hidden',
  },
  rail: { width: '64px', alignItems: 'center', paddingInline: 0 },
  link: {
    position: 'relative',
    display: 'flex',
    alignItems: 'center',
    gap: tokens.spacingHorizontalM,
    height: '40px',
    padding: `0 ${tokens.spacingHorizontalM}`,
    borderRadius: '8px',
    color: tokens.colorNeutralForeground2,
    textDecorationLine: 'none',
    fontSize: tokens.fontSizeBase300,
    whiteSpace: 'nowrap',
    transitionProperty: 'background-color, color',
    transitionDuration: tokens.durationFast,
    '::before': {
      content: '""',
      position: 'absolute',
      left: 0,
      top: '8px',
      bottom: '8px',
      width: '4px',
      borderRadius: '2px',
      backgroundColor: 'transparent',
    },
    ':hover': {
      backgroundColor: tokens.colorNeutralBackground1Hover,
      color: tokens.colorNeutralForeground1,
    },
    ':focus-visible': { outline: `2px solid ${tokens.colorStrokeFocus2}`, outlineOffset: '-2px' },
  },
  linkRail: { width: '44px', justifyContent: 'center', padding: 0 },
  icon: { flexShrink: 0, display: 'inline-flex', fontSize: '20px' },
  active: {
    backgroundColor: tokens.colorBrandBackground2,
    color: tokens.colorNeutralForeground1,
    fontWeight: tokens.fontWeightSemibold,
    ':hover': {
      backgroundColor: tokens.colorBrandBackground2Hover,
      color: tokens.colorNeutralForeground1,
    },
    '::before': { backgroundColor: palette.yellow },
  },
  hidden: {
    position: 'absolute',
    width: '1px',
    height: '1px',
    overflow: 'hidden',
    clip: 'rect(0 0 0 0)',
    whiteSpace: 'nowrap',
  },
});

/** Left navigation (FR-002). Real links, so keyboard Tab/Enter works and the URL is the state.
 * `collapsed` shows an icon rail (same links, name in a tooltip) so content keeps room. */
export function SideNav({ isAdmin, collapsed }: { isAdmin: boolean; collapsed?: boolean }) {
  const s = useStyles();
  return (
    <nav className={mergeClasses(s.nav, collapsed && s.rail)} aria-label="Main navigation">
      {NAV_ITEMS.filter((i) => !i.adminOnly || isAdmin).map(({ label, to, icon: Icon }) => {
        const link = (
          <NavLink
            key={to}
            to={to}
            // "/" and "/transitions" must not stay highlighted for their children.
            end={to === '/' || to === '/transitions'}
            className={({ isActive }) =>
              mergeClasses(s.link, collapsed && s.linkRail, isActive && s.active)
            }
          >
            <span className={s.icon}>
              <Icon aria-hidden />
            </span>
            <span className={collapsed ? s.hidden : undefined}>{label}</span>
          </NavLink>
        );
        return collapsed ? (
          <Tooltip key={to} content={label} relationship="label" positioning="after">
            {link}
          </Tooltip>
        ) : (
          link
        );
      })}
    </nav>
  );
}

import { useState, type KeyboardEvent } from 'react';
import { useMatch, useNavigate } from 'react-router';
import {
  Avatar,
  Badge,
  Body1Strong,
  Button,
  Caption1,
  Menu,
  MenuDivider,
  MenuItem,
  MenuItemRadio,
  MenuList,
  MenuPopover,
  MenuTrigger,
  SearchBox,
  makeStyles,
  mergeClasses,
  tokens,
} from '@fluentui/react-components';
import { Sparkle20Filled, Sparkle20Regular } from '@fluentui/react-icons';
import { useAuth } from '../auth/useAuth';
import { NotificationsBell } from '../features/notifications/NotificationsBell';
import { useMe, useUsers } from '../features/users/api';
import { ai, palette } from '../theme/orionTheme';
import { chipStyle, roleBadgeColors } from '../theme/tokens';

const useStyles = makeStyles({
  header: {
    flexShrink: 0,
    backgroundColor: tokens.colorNeutralBackground1,
    borderTop: `4px solid ${palette.yellow}`,
    borderBottom: `1px solid ${tokens.colorNeutralStroke2}`,
  },
  bar: {
    display: 'flex',
    alignItems: 'center',
    gap: tokens.spacingHorizontalL,
    height: '56px',
    padding: `0 ${tokens.spacingHorizontalL}`,
    minWidth: 0,
  },
  brand: {
    display: 'flex',
    alignItems: 'center',
    gap: tokens.spacingHorizontalS,
    whiteSpace: 'nowrap',
    flexShrink: 0,
  },
  mark: {
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    width: '28px',
    height: '28px',
    borderRadius: '8px',
    backgroundColor: ai.main,
    color: '#FFFFFF',
  },
  wordmark: {
    fontSize: '20px',
    fontWeight: tokens.fontWeightBold,
    letterSpacing: '0.02em',
    color: tokens.colorNeutralForeground1,
  },
  tagline: {
    color: tokens.colorNeutralForeground3,
    '@media (max-width: 1100px)': { display: 'none' },
  },
  search: { flexGrow: 1, flexShrink: 1, minWidth: 0, maxWidth: '420px' },
  spacer: { flexGrow: 1 },
  orionBtn: { flexShrink: 0, fontWeight: tokens.fontWeightSemibold },
  orionOpen: { outline: `2px solid ${tokens.colorNeutralForeground1}`, outlineOffset: '1px' },
  orionIcon: { color: ai.text, display: 'inline-flex' },
  user: { display: 'flex', alignItems: 'center', gap: tokens.spacingHorizontalS, minWidth: 0 },
  userText: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'flex-start',
    '@media (max-width: 700px)': { display: 'none' },
  },
});

/** Top bar (FR-002): brand, global search, bell, Orion toggle, current user menu (FR-001). */
export function TopBar(props: { orionOpen: boolean; onToggleOrion: () => void }) {
  const s = useStyles();
  const navigate = useNavigate();
  const { userId, switchUser, logout } = useAuth();
  const me = useMe();
  const users = useUsers();
  const [query, setQuery] = useState('');
  const onOrionPage = !!useMatch('/orion');
  const user = me.data?.user;

  const onSearchKey = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key !== 'Enter') return;
    const q = query.trim();
    navigate(q ? `/transitions?q=${encodeURIComponent(q)}` : '/transitions');
  };

  return (
    <header className={s.header}>
      <div className={s.bar}>
        <div className={s.brand}>
          <span className={s.mark} aria-hidden>
            <Sparkle20Filled />
          </span>
          <span className={s.wordmark}>Orion</span>
          <Caption1 className={s.tagline}>Operate Readiness Agent</Caption1>
        </div>

        <SearchBox
          className={s.search}
          placeholder="Search transitions"
          aria-label="Search transitions"
          value={query}
          onChange={(_, d) => setQuery(d.value)}
          onKeyDown={onSearchKey}
        />

        <div className={s.spacer} />

        <NotificationsBell />

        <Button
          className={mergeClasses(s.orionBtn, (props.orionOpen || onOrionPage) && s.orionOpen)}
          appearance="primary"
          icon={
            <span className={s.orionIcon}>
              <Sparkle20Regular />
            </span>
          }
          aria-pressed={props.orionOpen || onOrionPage}
          data-orion-toggle=""
          title={onOrionPage ? 'You are on the full Orion page' : 'Open the Orion assistant'}
          onClick={onOrionPage ? undefined : props.onToggleOrion}
        >
          Orion
        </Button>

        <Menu>
          <MenuTrigger disableButtonEnhancement>
            <Button appearance="subtle" aria-label="User menu">
              <span className={s.user}>
                <Avatar name={user?.name ?? '?'} size={28} color="colorful" />
                <span className={s.userText}>
                  <Body1Strong>{user?.name ?? '…'}</Body1Strong>
                  {user && (
                    <Badge size="small" appearance="outline" style={chipStyle(roleBadgeColors)}>
                      {user.role_label || user.role}
                    </Badge>
                  )}
                </span>
              </span>
            </Button>
          </MenuTrigger>
          <MenuPopover>
            <MenuList>
              <Menu
                checkedValues={{ user: userId ? [userId] : [] }}
                onCheckedValueChange={(_, d) => {
                  const id = d.checkedItems[0];
                  if (id && id !== userId) switchUser(id);
                }}
              >
                <MenuTrigger disableButtonEnhancement>
                  <MenuItem>Switch user</MenuItem>
                </MenuTrigger>
                <MenuPopover>
                  <MenuList>
                    {users.isLoading && <MenuItem disabled>Loading users...</MenuItem>}
                    {users.isError && <MenuItem disabled>Could not load users</MenuItem>}
                    {(users.data ?? []).map((u) => (
                      <MenuItemRadio
                        key={u.id}
                        name="user"
                        value={u.id}
                        secondaryContent={u.role_label || u.role}
                      >
                        {u.name}
                      </MenuItemRadio>
                    ))}
                  </MenuList>
                </MenuPopover>
              </Menu>
              <MenuDivider />
              <MenuItem
                onClick={() => {
                  logout({ explicit: true });
                  navigate('/login', { replace: true });
                }}
              >
                Sign out
              </MenuItem>
            </MenuList>
          </MenuPopover>
        </Menu>
      </div>
    </header>
  );
}

import { useState, type KeyboardEvent } from 'react';
import { useNavigate } from 'react-router';
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
  Tooltip,
  makeStyles,
  tokens,
} from '@fluentui/react-components';
import { Alert20Regular, Sparkle20Regular } from '@fluentui/react-icons';
import { useAuth } from '../auth/useAuth';
import { useMe, useUsers } from '../features/users/api';
import { chipStyle, roleBadgeColors } from '../theme/tokens';

const useStyles = makeStyles({
  bar: {
    display: 'flex',
    alignItems: 'center',
    gap: tokens.spacingHorizontalL,
    height: '52px',
    padding: `0 ${tokens.spacingHorizontalL}`,
    borderBottom: `1px solid ${tokens.colorNeutralStroke2}`,
    backgroundColor: tokens.colorNeutralBackground1,
    flexShrink: 0,
  },
  brand: {
    display: 'flex',
    alignItems: 'baseline',
    gap: tokens.spacingHorizontalS,
    whiteSpace: 'nowrap',
  },
  search: { flexGrow: 1, maxWidth: '420px' },
  spacer: { flexGrow: 1 },
  user: { display: 'flex', alignItems: 'center', gap: tokens.spacingHorizontalS },
  userText: { display: 'flex', flexDirection: 'column', alignItems: 'flex-start' },
});

/** Top bar (FR-002): brand, global search, bell, Orion toggle, current user menu (FR-001). */
export function TopBar(props: { orionOpen: boolean; onToggleOrion: () => void }) {
  const s = useStyles();
  const navigate = useNavigate();
  const { userId, switchUser, logout } = useAuth();
  const me = useMe();
  const users = useUsers();
  const [query, setQuery] = useState('');
  const user = me.data?.user;

  const onSearchKey = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key !== 'Enter') return;
    const q = query.trim();
    navigate(q ? `/transitions?q=${encodeURIComponent(q)}` : '/transitions');
  };

  return (
    <header className={s.bar}>
      <div className={s.brand}>
        <Body1Strong>Orion</Body1Strong>
        <Caption1>Operate Readiness Agent</Caption1>
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

      <Tooltip content="Notifications" relationship="label">
        <Button appearance="subtle" icon={<Alert20Regular />} aria-label="Notifications" />
      </Tooltip>

      <Button
        appearance={props.orionOpen ? 'primary' : 'secondary'}
        icon={<Sparkle20Regular />}
        aria-pressed={props.orionOpen}
        onClick={props.onToggleOrion}
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
    </header>
  );
}

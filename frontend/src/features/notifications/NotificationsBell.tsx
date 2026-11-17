import { useState } from 'react';
import {
  Badge,
  Body1Strong,
  Button,
  Caption1,
  Popover,
  PopoverSurface,
  PopoverTrigger,
  Tooltip,
  makeStyles,
  tokens,
} from '@fluentui/react-components';
import { Alert20Regular } from '@fluentui/react-icons';
import dayjs from 'dayjs';
import relativeTime from 'dayjs/plugin/relativeTime';
import { useNavigate } from 'react-router';
import { useApiErrorToast } from '../../hooks/useApiErrorToast';
import { useMarkAllRead, useMarkRead, useNotifications, type Notification } from './api';

dayjs.extend(relativeTime);

const useStyles = makeStyles({
  wrap: { position: 'relative', display: 'inline-flex' },
  badge: { position: 'absolute', top: '-2px', right: '-2px', pointerEvents: 'none' },
  surface: { width: '360px', maxWidth: '92vw', padding: 0 },
  head: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: `${tokens.spacingVerticalS} ${tokens.spacingHorizontalM}`,
    borderBottom: `1px solid ${tokens.colorNeutralStroke2}`,
  },
  list: { maxHeight: '420px', overflowY: 'auto', margin: 0, padding: 0, listStyle: 'none' },
  item: {
    display: 'flex',
    gap: tokens.spacingHorizontalS,
    alignItems: 'flex-start',
    width: '100%',
    textAlign: 'left',
    padding: `${tokens.spacingVerticalS} ${tokens.spacingHorizontalM}`,
    border: 'none',
    borderBottom: `1px solid ${tokens.colorNeutralStroke3}`,
    backgroundColor: 'transparent',
    color: tokens.colorNeutralForeground1,
    cursor: 'pointer',
    ':hover': { backgroundColor: tokens.colorNeutralBackground1Hover },
  },
  dot: {
    flexShrink: 0,
    width: '8px',
    height: '8px',
    marginTop: '6px',
    borderRadius: '50%',
    backgroundColor: tokens.colorBrandBackground,
  },
  dotRead: { backgroundColor: 'transparent' },
  empty: { padding: tokens.spacingVerticalL, textAlign: 'center' },
});

/** Notifications bell with unread badge and popover list (FR-072, spec 8.13). */
export function NotificationsBell() {
  const s = useStyles();
  const navigate = useNavigate();
  const showError = useApiErrorToast();
  const [open, setOpen] = useState(false);
  const q = useNotifications();
  const markRead = useMarkRead();
  const markAll = useMarkAllRead();
  const unread = q.data?.unread ?? 0;

  const onClick = (n: Notification) => {
    if (!n.read) markRead.mutate(n.id, { onError: showError });
    setOpen(false);
    if (n.link.startsWith('/')) navigate(n.link);
  };

  return (
    <Popover open={open} onOpenChange={(_, d) => setOpen(d.open)} positioning="below-end">
      <PopoverTrigger disableButtonEnhancement>
        <span className={s.wrap}>
          <Tooltip content="Notifications" relationship="label">
            <Button
              appearance="subtle"
              icon={<Alert20Regular />}
              aria-label={unread > 0 ? `Notifications, ${unread} unread` : 'Notifications'}
            />
          </Tooltip>
          {unread > 0 && (
            <Badge className={s.badge} size="small" color="danger" appearance="filled">
              {unread > 99 ? '99+' : unread}
            </Badge>
          )}
        </span>
      </PopoverTrigger>
      <PopoverSurface className={s.surface} aria-label="Notifications">
        <div className={s.head}>
          <Body1Strong>Notifications</Body1Strong>
          <Button
            size="small"
            appearance="transparent"
            disabled={unread === 0 || markAll.isPending}
            onClick={() => markAll.mutate(undefined, { onError: showError })}
          >
            Mark all read
          </Button>
        </div>
        {q.isLoading && <div className={s.empty}>Loading...</div>}
        {q.isError && <div className={s.empty}>Could not load notifications</div>}
        {q.data && q.data.items.length === 0 && (
          <div className={s.empty}>
            <Caption1>You are all caught up.</Caption1>
          </div>
        )}
        {q.data && q.data.items.length > 0 && (
          <ul className={s.list}>
            {q.data.items.map((n) => (
              <li key={n.id}>
                <button type="button" className={s.item} onClick={() => onClick(n)}>
                  <span
                    className={`${s.dot} ${n.read ? s.dotRead : ''}`}
                    aria-label={n.read ? 'Read' : 'Unread'}
                  />
                  <span>
                    <div>{n.text}</div>
                    <Caption1>{dayjs(n.created_at).fromNow()}</Caption1>
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </PopoverSurface>
    </Popover>
  );
}

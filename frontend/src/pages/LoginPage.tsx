import { useState, type ReactNode } from 'react';
import { Navigate, useNavigate, useSearchParams } from 'react-router';
import {
  Avatar,
  Body1,
  Button,
  Caption1,
  Divider,
  MessageBar,
  MessageBarBody,
  Title2,
  makeStyles,
  tokens,
} from '@fluentui/react-components';
import {
  ChevronRight20Regular,
  DataTrending20Regular,
  PersonKey20Regular,
  ShieldCheckmark20Regular,
  Sparkle20Filled,
  Sparkle24Filled,
} from '@fluentui/react-icons';
import { safeNext } from '../auth/safeNext';
import { useAuth } from '../auth/useAuth';
import { useUsers } from '../features/users/api';
import { ErrorState } from '../components/ErrorState';
import { LoadingState } from '../components/LoadingState';
import type { User } from '../api/types';
import { ai, cardRadius, cardShadow, palette } from '../theme/orionTheme';

const useStyles = makeStyles({
  page: {
    minHeight: '100vh',
    display: 'flex',
    backgroundColor: tokens.colorNeutralBackground3,
    boxSizing: 'border-box',
    // The login page has no nav or Orion panel, so the viewport is the content width here.
    '@media (max-width: 860px)': { flexDirection: 'column' },
  },
  brand: {
    flex: '0 0 40%',
    minWidth: '340px',
    maxWidth: '560px',
    boxSizing: 'border-box',
    padding: '48px 44px',
    display: 'flex',
    flexDirection: 'column',
    justifyContent: 'space-between',
    gap: tokens.spacingVerticalXXL,
    backgroundColor: palette.yellow,
    color: palette.onYellow,
    '@media (max-width: 860px)': { flex: '0 0 auto', maxWidth: 'none', padding: '28px 24px' },
  },
  mark: {
    width: '44px',
    height: '44px',
    borderRadius: '50%',
    display: 'grid',
    placeItems: 'center',
    backgroundColor: ai.strong,
    color: tokens.colorNeutralForegroundInverted,
  },
  title: { margin: `${tokens.spacingVerticalL} 0 0`, lineHeight: 1.1 },
  wordmark: { display: 'block', fontSize: '48px', fontWeight: 700, letterSpacing: '-0.5px' },
  tagline: { display: 'block', fontSize: '20px', fontWeight: 600, marginTop: '6px' },
  srOnly: {
    position: 'absolute',
    width: '1px',
    height: '1px',
    overflow: 'hidden',
    clip: 'rect(0 0 0 0)',
    whiteSpace: 'nowrap',
  },
  lead: {
    fontSize: '17px',
    lineHeight: 1.5,
    marginTop: tokens.spacingVerticalL,
    maxWidth: '400px',
  },
  points: {
    listStyle: 'none',
    margin: 0,
    padding: 0,
    display: 'flex',
    flexDirection: 'column',
    gap: tokens.spacingVerticalM,
    '@media (max-width: 860px)': { display: 'none' },
  },
  point: {
    display: 'flex',
    alignItems: 'center',
    gap: tokens.spacingHorizontalM,
    fontSize: '15px',
  },
  pointIcon: {
    flexShrink: 0,
    width: '34px',
    height: '34px',
    borderRadius: '50%',
    display: 'grid',
    placeItems: 'center',
    backgroundColor: tokens.colorNeutralBackgroundAlpha,
  },
  footnote: { fontSize: '13px', fontWeight: 600 },
  main: {
    flex: '1 1 auto',
    minWidth: 0,
    boxSizing: 'border-box',
    padding: '48px 44px',
    display: 'flex',
    flexDirection: 'column',
    gap: tokens.spacingVerticalL,
    '@media (max-width: 860px)': { padding: '24px 16px' },
  },
  inner: {
    width: '100%',
    maxWidth: '900px',
    // auto margins centre the block vertically when there is room and fall back to the top
    // when the content is taller than the screen (unlike justify-content: center)
    marginTop: 'auto',
    marginBottom: 'auto',
    display: 'flex',
    flexDirection: 'column',
    gap: tokens.spacingVerticalL,
  },
  subtitle: { color: tokens.colorNeutralForeground3 },
  sso: {
    alignSelf: 'center',
    width: '100%',
    maxWidth: '420px',
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    gap: tokens.spacingVerticalS,
    textAlign: 'center',
  },
  ssoButton: { width: '100%', marginTop: tokens.spacingVerticalS },
  pickNote: { color: tokens.colorNeutralForeground3, textAlign: 'center' },
  grid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(min(100%, 250px), 1fr))',
    gap: tokens.spacingHorizontalM,
  },
  card: {
    display: 'flex',
    alignItems: 'center',
    gap: tokens.spacingHorizontalM,
    width: '100%',
    minWidth: 0,
    padding: '14px 16px',
    textAlign: 'left',
    fontFamily: 'inherit',
    color: tokens.colorNeutralForeground1,
    backgroundColor: tokens.colorNeutralBackground1,
    border: `1px solid ${palette.borderSubtle}`,
    borderRadius: cardRadius,
    boxShadow: cardShadow,
    cursor: 'pointer',
    transitionProperty: 'border-color, box-shadow, transform',
    transitionDuration: '120ms',
    ':hover': {
      borderTopColor: palette.yellow,
      borderRightColor: palette.yellow,
      borderBottomColor: palette.yellow,
      borderLeftColor: palette.yellow,
      boxShadow: tokens.shadow8,
      transform: 'translateY(-1px)',
    },
    ':focus-visible': { outline: `2px solid ${palette.textStrong}`, outlineOffset: '2px' },
  },
  who: { display: 'flex', flexDirection: 'column', minWidth: 0, flex: '1 1 auto' },
  name: { fontSize: '16px', fontWeight: 600, lineHeight: 1.3 },
  role: { color: tokens.colorNeutralForeground3 },
  chevron: { flexShrink: 0, color: tokens.colorNeutralForeground3 },
});

const POINTS: { icon: ReactNode; text: string }[] = [
  { icon: <DataTrending20Regular />, text: "See every transition's readiness in one place" },
  { icon: <Sparkle20Filled />, text: 'Orion drafts, chases and summarises – people decide' },
  {
    icon: <ShieldCheckmark20Regular />,
    text: 'Gates, approvals and evidence with a full audit trail',
  },
];

/** Demo login (FR-001): pick a user, no password. The "Sign in with Microsoft" button is a
 * placeholder for Entra ID single sign-on and only shows a note until it is connected. */
export function LoginPage() {
  const s = useStyles();
  const { userId, login } = useAuth();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const users = useUsers();
  const next = safeNext(params.get('next'));
  const [ssoNote, setSsoNote] = useState(false);

  if (userId) return <Navigate to={next} replace />;

  const pick = (id: string) => {
    login(id);
    navigate(next, { replace: true });
  };
  const renderCard = (u: User) => (
    <button
      key={u.id}
      type="button"
      className={s.card}
      aria-label={`Log in as ${u.name}, ${u.role_label || u.role}`}
      onClick={() => pick(u.id)}
    >
      <Avatar name={u.name} size={40} color="colorful" idForColor={u.role} aria-hidden />
      <span className={s.who}>
        <span className={s.name}>{u.name}</span>
        <Caption1 className={s.role}>
          {u.role_label || u.role}
          {u.focal_label ? ` · ${u.focal_label}` : ''}
        </Caption1>
      </span>
      <ChevronRight20Regular className={s.chevron} aria-hidden />
    </button>
  );

  return (
    <div className={s.page}>
      <aside className={s.brand}>
        <div>
          <div className={s.mark} aria-hidden>
            <Sparkle24Filled />
          </div>
          <h1 className={s.title}>
            <span className={s.wordmark}>Orion</span>
            <span className={s.srOnly}> – </span>
            <span className={s.tagline}>Operate Readiness Agent</span>
          </h1>
          <p className={s.lead}>
            One place to run every transition to operations: readiness, gates, approvals and the
            support model.
          </p>
        </div>
        <ul className={s.points}>
          {POINTS.map((p) => (
            <li key={p.text} className={s.point}>
              <span className={s.pointIcon} aria-hidden>
                {p.icon}
              </span>
              {p.text}
            </li>
          ))}
        </ul>
        <div className={s.footnote}>Demo environment · synthetic data · no password</div>
      </aside>

      <main className={s.main}>
        <div className={s.inner}>
          {/* Placeholder for Microsoft Entra ID single sign-on; wired up in the real build. */}
          <div className={s.sso}>
            <Title2 as="h2">Sign in</Title2>
            <Button
              appearance="primary"
              size="large"
              icon={<PersonKey20Regular />}
              className={s.ssoButton}
              onClick={() => setSsoNote(true)}
            >
              Sign in with Microsoft
            </Button>
            <Caption1 className={s.subtitle}>
              Single sign-on (Microsoft Entra ID) – placeholder, connected in the real build
            </Caption1>
            {ssoNote && (
              <MessageBar intent="info">
                <MessageBarBody>
                  Single sign-on is not connected in this demo yet. Pick a demo user below.
                </MessageBarBody>
              </MessageBar>
            )}
          </div>
          <Divider>or use a demo user</Divider>
          <Body1 block className={s.pickNote}>
            Demo login – pick a user, no password
          </Body1>
          {users.isLoading && <LoadingState rows={3} />}
          {users.isError && <ErrorState error={users.error} />}
          <div className={s.grid}>{(users.data ?? []).map(renderCard)}</div>
        </div>
      </main>
    </div>
  );
}

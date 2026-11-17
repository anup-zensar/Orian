import { Navigate, useNavigate, useSearchParams } from 'react-router';
import {
  Badge,
  Body1,
  Card,
  CardHeader,
  Caption1,
  Subtitle1,
  Title2,
  makeStyles,
  tokens,
} from '@fluentui/react-components';
import { safeNext } from '../auth/safeNext';
import { useAuth } from '../auth/useAuth';
import { useUsers } from '../features/users/api';
import { ErrorState } from '../components/ErrorState';
import { LoadingState } from '../components/LoadingState';
import { chipStyle, roleBadgeColors } from '../theme/tokens';

const useStyles = makeStyles({
  page: {
    minHeight: '100vh',
    padding: `${tokens.spacingVerticalXXL} ${tokens.spacingHorizontalXXL}`,
    backgroundColor: tokens.colorNeutralBackground2,
    boxSizing: 'border-box',
  },
  inner: {
    maxWidth: '1100px',
    margin: '0 auto',
    display: 'flex',
    flexDirection: 'column',
    gap: tokens.spacingVerticalL,
  },
  grid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))',
    gap: tokens.spacingHorizontalM,
  },
  card: { cursor: 'pointer' },
  meta: { display: 'flex', flexDirection: 'column', gap: tokens.spacingVerticalXS },
});

/** Demo login (FR-001): pick a user, no password. */
export function LoginPage() {
  const s = useStyles();
  const { userId, login } = useAuth();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const users = useUsers();
  const next = safeNext(params.get('next'));

  if (userId) return <Navigate to={next} replace />;

  return (
    <div className={s.page}>
      <div className={s.inner}>
        <div>
          <Title2 as="h1">Orion – Operate Readiness Agent</Title2>
          <Body1 block>Demo login – pick a user, no password</Body1>
        </div>
        {users.isLoading && <LoadingState rows={3} />}
        {users.isError && <ErrorState error={users.error} />}
        <div className={s.grid}>
          {(users.data ?? []).map((u) => (
            <Card
              key={u.id}
              className={s.card}
              role="button"
              tabIndex={0}
              aria-label={`Log in as ${u.name}, ${u.role_label || u.role}`}
              onClick={() => {
                login(u.id);
                navigate(next, { replace: true });
              }}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault();
                  login(u.id);
                  navigate(next, { replace: true });
                }
              }}
            >
              <CardHeader header={<Subtitle1>{u.name}</Subtitle1>} />
              <div className={s.meta}>
                <span>
                  <Badge appearance="outline" style={chipStyle(roleBadgeColors)}>
                    {u.role_label || u.role}
                  </Badge>
                </span>
                {u.focal_label && <Caption1>{u.focal_label}</Caption1>}
                <Caption1>{u.email}</Caption1>
              </div>
            </Card>
          ))}
        </div>
      </div>
    </div>
  );
}

// FR-010 Dashboard (spec 8.1): role-aware home page.
import { makeStyles, tokens } from '@fluentui/react-components';
import { useNavigate } from 'react-router';
import { ErrorState } from '../../components/ErrorState';
import { InsightsCard } from '../../components/InsightsCard';
import { KpiTile } from '../../components/KpiTile';
import { LoadingState } from '../../components/LoadingState';
import { PageHeader } from '../../components/PageHeader';
import { useInsights } from '../orion/api';
import { useReference } from '../reference/api';
import { useDashboard } from './api';
import { MyWorkCard, PortfolioTiles, RecentActivityCard } from './DashboardSections';

const useStyles = makeStyles({
  tiles: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))',
    gap: tokens.spacingHorizontalM,
    marginBottom: tokens.spacingVerticalL,
  },
  pair: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(380px, 1fr))',
    gap: tokens.spacingHorizontalL,
    marginTop: tokens.spacingVerticalL,
    alignItems: 'start',
  },
});

export function DashboardPage() {
  const s = useStyles();
  const navigate = useNavigate();
  const dash = useDashboard();
  const insights = useInsights('dashboard');
  const reference = useReference();
  const d = dash.data;

  if (dash.isLoading) return <LoadingState rows={6} />;
  if (dash.error || !d)
    return <ErrorState error={dash.error} onRetry={() => void dash.refetch()} />;

  const isLeadership = d.user.role === 'LEADERSHIP';
  const firstName = d.user.name.split(' ')[0];
  // /dashboard may leave role_label empty, so fall back to the reference role name.
  const roleLabel =
    d.user.role_label || reference.data?.roles.find((r) => r.code === d.user.role)?.label;
  const subtitle = d.subtitle || [roleLabel, d.user.focal_label].filter(Boolean).join(' · ');

  /** "My open items" scrolls to My work; other tiles with a link navigate there. */
  const tileAction = (key: string, link: string | null | undefined) => {
    if (/open.?items/.test(key) && !isLeadership) {
      return () => {
        const el = document.getElementById('my-work');
        el?.scrollIntoView({ behavior: 'smooth', block: 'start' });
        el?.focus?.();
      };
    }
    return link ? () => navigate(link) : undefined;
  };

  return (
    <>
      <PageHeader title={`Welcome back, ${firstName}`} subtitle={subtitle} />
      <div className={s.tiles}>
        {d.kpis.map((k) => (
          <KpiTile
            key={k.key}
            label={k.label}
            value={k.value}
            tone={k.tone}
            hint={k.hint}
            caption={/open.?items/.test(k.key) ? 'Checklist items only' : undefined}
            onClick={tileAction(k.key, k.link)}
          />
        ))}
      </div>

      {isLeadership ? (
        <PortfolioTiles tiles={d.portfolio_tiles} />
      ) : (
        <MyWorkCard rows={d.my_work} total={d.my_work_total} />
      )}

      <div className={s.pair}>
        <InsightsCard
          title="Orion insights"
          data={insights.data}
          isLoading={insights.isLoading}
          error={insights.error}
          onRetry={() => void insights.refetch()}
        />
        <RecentActivityCard events={d.recent_activity} today={d.today} />
      </div>
    </>
  );
}

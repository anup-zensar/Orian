// FR-010 Dashboard (spec 8.1): role-aware home page.
import { makeStyles, tokens } from '@fluentui/react-components';
import {
  ClipboardTask20Regular,
  DocumentCheckmark20Regular,
  Person20Regular,
} from '@fluentui/react-icons';
import { useNavigate } from 'react-router';
import { ErrorState } from '../../components/ErrorState';
import { InsightsCard } from '../../components/InsightsCard';
import { KpiTile } from '../../components/KpiTile';
import { LoadingState } from '../../components/LoadingState';
import { PageHeader } from '../../components/PageHeader';
import { useInsights } from '../orion/api';
import { useReference } from '../reference/api';
import { useMe } from '../users/api';
import { useDashboard } from './api';
import { MyWorkCard, PortfolioTiles, RecentActivityCard } from './DashboardSections';

const useStyles = makeStyles({
  tiles: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 170px), 1fr))',
    gap: tokens.spacingHorizontalM,
    marginBottom: tokens.spacingVerticalL,
  },
  pair: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 380px), 1fr))',
    gap: tokens.spacingHorizontalL,
    marginTop: tokens.spacingVerticalL,
    alignItems: 'start',
  },
});

/** Distinct icons for the neutral tiles; other tones keep the tone icon. */
function kpiIcon(key: string, tone?: string) {
  if (tone && tone !== 'neutral') return undefined;
  if (/open.?items/.test(key)) return <ClipboardTask20Regular />;
  if (/approval/.test(key)) return <DocumentCheckmark20Regular />;
  if (/own/.test(key)) return <Person20Regular />;
  return undefined;
}

export function DashboardPage() {
  const s = useStyles();
  const navigate = useNavigate();
  const dash = useDashboard();
  const insights = useInsights('dashboard');
  const reference = useReference();
  const me = useMe();
  const d = dash.data;

  if (dash.isLoading) return <LoadingState rows={6} />;
  if (dash.error || !d)
    return <ErrorState error={dash.error} onRetry={() => void dash.refetch()} />;

  // People who may see every transition (a permission, Leadership by default) get portfolio tiles.
  const isLeadership = !!me.data?.permissions.includes('see_all_transitions');
  const ownedKpi = d.kpis.find((k) => k.key === 'transitions_i_own');
  const noTransitions =
    !isLeadership && d.my_work_total === 0 && Number(ownedKpi?.value ?? 0) === 0;
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
    // The full register is the Transitions page; the Control tower keeps the overview.
    return link ? () => navigate(link.replace(/^\/control-tower/, '/transitions')) : undefined;
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
            icon={kpiIcon(k.key, k.tone)}
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
          data={insights.data && { ...insights.data, insights: insights.data.insights.slice(0, 3) }}
          isLoading={insights.isLoading}
          error={insights.error}
          onRetry={() => void insights.refetch()}
          noTransitions={noTransitions}
        />
        <RecentActivityCard events={d.recent_activity} today={d.today} />
      </div>
    </>
  );
}

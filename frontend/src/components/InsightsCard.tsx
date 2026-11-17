import { Caption1, Skeleton, SkeletonItem, makeStyles, tokens } from '@fluentui/react-components';
import {
  CheckmarkCircle20Filled,
  ErrorCircle20Filled,
  Info20Filled,
  Warning20Filled,
} from '@fluentui/react-icons';
import type { Insights } from '../api/types';
import { lensColors, ragColors } from '../theme/tokens';
import { AiBadge } from './AiBadge';
import { AppLink } from './AppLink';
import { ErrorState } from './ErrorState';
import { SectionCard } from './SectionCard';

const useStyles = makeStyles({
  list: {
    listStyle: 'none',
    margin: 0,
    padding: 0,
    display: 'flex',
    flexDirection: 'column',
    gap: tokens.spacingVerticalM,
  },
  item: { display: 'flex', gap: tokens.spacingHorizontalS, alignItems: 'flex-start' },
  icon: { flexShrink: 0, marginTop: '2px', display: 'inline-flex' },
  body: { display: 'flex', flexDirection: 'column', gap: tokens.spacingVerticalXS },
  actions: { display: 'flex', flexWrap: 'wrap', gap: tokens.spacingHorizontalM },
  foot: { color: tokens.colorNeutralForeground3 },
  agent: { display: 'inline-flex', alignItems: 'center', gap: tokens.spacingHorizontalXS },
});

const SEVERITY = {
  critical: { Icon: ErrorCircle20Filled, color: ragColors.Red.border, label: 'Critical' },
  warning: { Icon: Warning20Filled, color: ragColors.Amber.border, label: 'Warning' },
  info: { Icon: Info20Filled, color: lensColors.Technical.border, label: 'Info' },
  success: { Icon: CheckmarkCircle20Filled, color: ragColors.Green.border, label: 'Good news' },
} as const;

interface Props {
  title: string;
  data: Insights | undefined;
  isLoading: boolean;
  error: unknown;
  onRetry?: () => void;
}

/** Orion insights card (spec 8.1, 8.2). Always labelled AI + "Orion agent" (BR-050). Action buttons
 * are navigation links in M2 (A-52); insights never write data. */
export function InsightsCard({ title, data, isLoading, error, onRetry }: Props) {
  const s = useStyles();
  return (
    <SectionCard
      title={title}
      actions={
        <span className={s.agent}>
          <AiBadge />
          <Caption1>Orion agent</Caption1>
        </span>
      }
    >
      {isLoading ? (
        <Skeleton aria-label="Loading insights">
          {[0, 1, 2].map((i) => (
            <SkeletonItem key={i} style={{ height: 40, marginBottom: 10 }} />
          ))}
        </Skeleton>
      ) : error ? (
        <ErrorState error={error} onRetry={onRetry} />
      ) : !data || data.insights.length === 0 ? (
        <Caption1>No insights right now: nothing needs attention.</Caption1>
      ) : (
        <ul className={s.list}>
          {data.insights.map((ins) => {
            const sev = SEVERITY[ins.severity as keyof typeof SEVERITY] ?? SEVERITY.info;
            // Only real navigation links: no disabled look-alike buttons.
            const links = (ins.actions ?? []).filter((a) => a.kind === 'link' && a.href);
            return (
              <li key={ins.id} className={s.item}>
                <span
                  className={s.icon}
                  style={{ color: sev.color }}
                  role="img"
                  aria-label={sev.label}
                >
                  <sev.Icon />
                </span>
                <div className={s.body}>
                  <span>{ins.text}</span>
                  {links.length > 0 && (
                    <div className={s.actions}>
                      {links.map((a) => (
                        <AppLink key={a.label} to={a.href as string}>
                          {a.label}
                        </AppLink>
                      ))}
                    </div>
                  )}
                </div>
              </li>
            );
          })}
        </ul>
      )}
      <Caption1 className={s.foot}>Orion recommends and drafts. People decide.</Caption1>
    </SectionCard>
  );
}

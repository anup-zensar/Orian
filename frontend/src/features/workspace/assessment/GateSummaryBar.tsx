import { useNavigate } from 'react-router';
import {
  Button,
  Caption1,
  ProgressBar,
  Subtitle2,
  makeStyles,
  tokens,
} from '@fluentui/react-components';
import { LensChip } from '../../../components/LensChip';
import { lensColors, type Lens } from '../../../theme/tokens';
import type { GateLensSummary } from '../api';

const useStyles = makeStyles({
  root: {
    display: 'flex',
    flexWrap: 'wrap',
    alignItems: 'stretch',
    gap: tokens.spacingHorizontalL,
    padding: tokens.spacingVerticalM,
    marginBottom: tokens.spacingVerticalM,
    border: `1px solid ${tokens.colorNeutralStroke2}`,
    borderRadius: tokens.borderRadiusMedium,
    backgroundColor: tokens.colorNeutralBackground1,
  },
  head: {
    display: 'flex',
    flexDirection: 'column',
    gap: tokens.spacingVerticalXS,
    justifyContent: 'center',
  },
  lens: {
    display: 'flex',
    flexDirection: 'column',
    gap: tokens.spacingVerticalXXS,
    minWidth: '180px',
    flex: '1 1 180px',
    paddingLeft: tokens.spacingHorizontalM,
    borderLeft: '4px solid',
  },
  pct: {
    fontSize: tokens.fontSizeHero700,
    fontWeight: tokens.fontWeightSemibold,
    lineHeight: tokens.lineHeightHero700,
  },
});

/** Per-lens readiness for the selected gate plus the "Readiness check" shortcut (spec 8.7 b). */
export function GateSummaryBar(props: {
  transitionId: string;
  gateShort: string;
  summary: GateLensSummary[];
}) {
  const s = useStyles();
  const navigate = useNavigate();
  return (
    <div className={s.root} aria-label="Gate summary">
      <div className={s.head}>
        <Subtitle2 as="h2">Gate summary: {props.gateShort}</Subtitle2>
        <Button
          onClick={() => navigate(`/transitions/${encodeURIComponent(props.transitionId)}/gates`)}
        >
          Readiness check
        </Button>
      </div>
      {props.summary.map((l) => (
        <div
          key={l.lens}
          className={s.lens}
          style={{ borderLeftColor: lensColors[l.lens as Lens]?.border }}
        >
          <LensChip lens={l.lens as Lens} />
          <span className={s.pct}>{l.readiness_pct}%</span>
          <ProgressBar value={l.readiness_pct / 100} aria-label={`${l.lens} readiness`} />
          <Caption1>
            {l.done}/{l.scope} done · {l.in_progress} in progress · {l.not_started} not started
          </Caption1>
          <Caption1>
            {l.open_gaps} gaps ({l.critical_gaps} critical)
          </Caption1>
        </div>
      ))}
    </div>
  );
}

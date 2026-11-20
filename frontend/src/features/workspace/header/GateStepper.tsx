import { CheckmarkCircle20Filled, Diamond16Regular } from '@fluentui/react-icons';
import { Caption1, makeStyles, mergeClasses, tokens } from '@fluentui/react-components';
import type { TransitionDetail } from '../../transition/api';

const useStyles = makeStyles({
  list: {
    listStyle: 'none',
    margin: 0,
    padding: 0,
    display: 'grid',
    gridTemplateColumns: 'repeat(7, minmax(80px, 1fr))',
    gap: tokens.spacingHorizontalXS,
    overflowX: 'auto',
  },
  step: {
    display: 'flex',
    flexDirection: 'column',
    gap: '2px',
    minWidth: 0,
    padding: `${tokens.spacingVerticalXS} ${tokens.spacingHorizontalS}`,
    borderTop: `4px solid ${tokens.colorNeutralStroke1}`,
    backgroundColor: tokens.colorNeutralBackground2,
    borderRadius: tokens.borderRadiusSmall,
    color: tokens.colorNeutralForeground3,
  },
  done: {
    borderTopColor: tokens.colorPaletteGreenBorderActive,
    color: tokens.colorNeutralForeground1,
  },
  current: {
    borderTopColor: tokens.colorBrandBackground,
    backgroundColor: tokens.colorBrandBackground2,
    color: tokens.colorNeutralForeground1,
    fontWeight: tokens.fontWeightSemibold,
  },
  line: {
    display: 'flex',
    alignItems: 'center',
    gap: tokens.spacingHorizontalXS,
    whiteSpace: 'nowrap',
  },
  ok: { color: tokens.colorPaletteGreenForeground1 },
  caption: { whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' },
});

/** 7-gate stepper: done gates checked, current highlighted, decision gates marked (spec 8.7). */
export function GateStepper({ gates }: { gates: TransitionDetail['gates'] }) {
  const s = useStyles();
  return (
    <ol className={s.list} aria-label="Gate progress">
      {gates.map((g) => (
        <li
          key={g.code}
          className={mergeClasses(
            s.step,
            g.state === 'done' && s.done,
            g.state === 'current' && s.current,
          )}
          aria-current={g.state === 'current' ? 'step' : undefined}
          title={g.label}
        >
          <span className={s.line}>
            {g.state === 'done' && <CheckmarkCircle20Filled className={s.ok} aria-label="Done" />}
            {g.short}
            {g.type === 'decision' && (
              <Diamond16Regular aria-label="Decision gate" title="Decision gate" />
            )}
          </span>
          <Caption1
            className={s.caption}
            title={g.type === 'decision' ? 'Decision gate' : undefined}
          >
            {g.state === 'done' ? 'Done' : g.state === 'current' ? 'Current' : 'Upcoming'}
          </Caption1>
        </li>
      ))}
    </ol>
  );
}

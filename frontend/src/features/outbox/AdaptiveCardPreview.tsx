import { Body1, Button, Caption1, Text, makeStyles, tokens } from '@fluentui/react-components';

const useStyles = makeStyles({
  card: {
    display: 'flex',
    flexDirection: 'column',
    gap: tokens.spacingVerticalS,
    padding: tokens.spacingVerticalL,
    maxWidth: '480px',
    border: `1px solid ${tokens.colorNeutralStroke1}`,
    borderRadius: tokens.borderRadiusLarge,
    backgroundColor: tokens.colorNeutralBackground2,
    boxShadow: tokens.shadow4,
  },
  container: {
    display: 'flex',
    flexDirection: 'column',
    gap: tokens.spacingVerticalXS,
    padding: tokens.spacingVerticalS,
    borderRadius: tokens.borderRadiusMedium,
    backgroundColor: tokens.colorNeutralBackground3,
  },
  facts: {
    display: 'grid',
    gridTemplateColumns: 'max-content 1fr',
    columnGap: tokens.spacingHorizontalL,
    rowGap: tokens.spacingVerticalXXS,
    margin: 0,
  },
  factTitle: { fontWeight: tokens.fontWeightSemibold, margin: 0 },
  factValue: { margin: 0 },
  actions: { display: 'flex', gap: tokens.spacingHorizontalS, flexWrap: 'wrap' },
});

type Json = Record<string, unknown>;
const isObj = (v: unknown): v is Json => !!v && typeof v === 'object' && !Array.isArray(v);
const str = (v: unknown): string => (typeof v === 'string' ? v : v == null ? '' : String(v));

function ElementView({ el }: { el: unknown }) {
  const s = useStyles();
  if (!isObj(el)) return null;
  switch (el.type) {
    case 'TextBlock': {
      const size = str(el.size).toLowerCase();
      return (
        <Text
          weight={str(el.weight).toLowerCase() === 'bolder' ? 'bold' : 'regular'}
          size={size === 'large' ? 500 : size === 'medium' ? 400 : size === 'small' ? 200 : 300}
          style={{ whiteSpace: 'pre-wrap' }}
        >
          {str(el.text)}
        </Text>
      );
    }
    case 'FactSet': {
      const facts = Array.isArray(el.facts) ? el.facts : [];
      return (
        <dl className={s.facts}>
          {facts.map((f, i) =>
            isObj(f) ? (
              <div key={i} style={{ display: 'contents' }}>
                <dt className={s.factTitle}>{str(f.title)}</dt>
                <dd className={s.factValue}>{str(f.value)}</dd>
              </div>
            ) : null,
          )}
        </dl>
      );
    }
    case 'Container': {
      const items = Array.isArray(el.items) ? el.items : [];
      return (
        <div className={s.container}>
          {items.map((it, i) => (
            <ElementView key={i} el={it} />
          ))}
        </div>
      );
    }
    default:
      return <Caption1>[{str(el.type) || 'element'} not rendered in preview]</Caption1>;
  }
}

/** Minimal Adaptive Card renderer (TextBlock, FactSet, Container, actions) for the mock Teams outbox. */
export function AdaptiveCardPreview({ card }: { card: Record<string, unknown> }) {
  const s = useStyles();
  const body = Array.isArray(card.body) ? card.body : [];
  const actions = Array.isArray(card.actions) ? card.actions : [];
  return (
    <div className={s.card} role="group" aria-label="Adaptive Card preview">
      {body.map((el, i) => (
        <ElementView key={i} el={el} />
      ))}
      {actions.length > 0 && (
        <>
          <div className={s.actions}>
            {actions.map((a, i) => (
              <Button key={i} size="small" disabled>
                {isObj(a) ? str(a.title) || 'Action' : 'Action'}
              </Button>
            ))}
          </div>
          <Body1>
            <Caption1>Preview only: actions are disabled in the outbox.</Caption1>
          </Body1>
        </>
      )}
    </div>
  );
}

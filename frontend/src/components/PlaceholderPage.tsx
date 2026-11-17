import { Badge, Body1, makeStyles, tokens } from '@fluentui/react-components';
import { PageHeader } from './PageHeader';

const useStyles = makeStyles({
  card: {
    padding: tokens.spacingVerticalL,
    border: `1px dashed ${tokens.colorNeutralStroke1}`,
    borderRadius: tokens.borderRadiusMedium,
    display: 'flex',
    flexDirection: 'column',
    gap: tokens.spacingVerticalS,
    alignItems: 'flex-start',
  },
});

/** Shared stand-in for pages not built yet. No fake data (spec reference + milestone only). */
export function PlaceholderPage(props: { title: string; purpose: string; spec: string }) {
  const s = useStyles();
  return (
    <>
      <PageHeader title={props.title} />
      <div className={s.card}>
        <Body1>{props.purpose}</Body1>
        <Badge appearance="tint" color="informative">
          {props.spec}
        </Badge>
      </div>
    </>
  );
}

import { makeStyles, tokens } from '@fluentui/react-components';
import { PageHeader } from '../../components/PageHeader';
import { OrionChat } from './OrionChat';

const useStyles = makeStyles({
  frame: {
    height: 'calc(100vh - 220px)',
    minHeight: '420px',
    maxWidth: '900px',
    display: 'flex',
    flexDirection: 'column',
    padding: tokens.spacingHorizontalL,
    border: `1px solid ${tokens.colorNeutralStroke2}`,
    borderRadius: tokens.borderRadiusLarge,
    backgroundColor: tokens.colorNeutralBackground1,
  },
});

/** Full-page Orion assistant (FR-090) at /orion: the same chat as the side panel. */
export function OrionPage() {
  const s = useStyles();
  return (
    <>
      <PageHeader
        title="Orion"
        subtitle="Ask in plain language, paste an email or upload a document. Orion drafts and proposes; people decide."
      />
      <div className={s.frame}>
        <OrionChat />
      </div>
    </>
  );
}

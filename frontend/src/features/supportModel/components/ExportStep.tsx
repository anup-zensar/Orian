import { Badge, Body1, Button, Caption1, makeStyles, tokens } from '@fluentui/react-components';
import { ArrowDownloadRegular } from '@fluentui/react-icons';
import dayjs from 'dayjs';
import { download } from '../../../api/client';
import { Panel } from './Panel';
import { useSuccessToast } from '../../admin/useSavedToast';
import { useApiErrorToast } from '../../../hooks/useApiErrorToast';
import { usePerm } from '../../gates/usePerm';
import { useGeneratePptx, type SupportModel } from '../api';

const useStyles = makeStyles({
  stack: { display: 'flex', flexDirection: 'column', gap: tokens.spacingVerticalM },
  row: {
    display: 'flex',
    gap: tokens.spacingHorizontalS,
    alignItems: 'center',
    flexWrap: 'wrap',
  },
  grow: { flexGrow: 1, minWidth: 0 },
});

/** Step 4: PowerPoint export and the status of the linked checklist items. */
export function ExportStep(props: { transitionId: string; model: SupportModel }) {
  const s = useStyles();
  const showError = useApiErrorToast();
  const notify = useSuccessToast();
  const { model } = props;
  const gen = useGeneratePptx(props.transitionId);
  // Exporting is allowed after the model is agreed (read-only for editing), so gate on the role only.
  const perm = usePerm('edit_support_model', props.transitionId);
  const pptx = model.pptx;

  return (
    <div className={s.stack}>
      <Panel title="PowerPoint export">
        <div className={s.row}>
          <Button
            appearance="primary"
            disabled={model.id === null || gen.isPending || !perm.allowed}
            onClick={() =>
              model.id !== null &&
              gen.mutate(model.id, {
                onSuccess: () => notify('PowerPoint generated'),
                onError: showError,
              })
            }
          >
            {gen.isPending ? 'Generating' : 'Generate PPT'}
          </Button>
          {pptx && (
            <Button
              icon={<ArrowDownloadRegular />}
              onClick={() =>
                void download(
                  `/evidence/${encodeURIComponent(pptx.evidence_id)}/download`,
                  pptx.filename,
                ).catch(showError)
              }
            >
              Download PPT
            </Button>
          )}
        </div>
        {!perm.allowed && (
          <Caption1>
            Generate PPT is disabled: {perm.reason ?? 'You do not have permission'}
          </Caption1>
        )}
        {pptx ? (
          <Caption1>
            {pptx.filename}, version {pptx.version}, generated{' '}
            {dayjs(pptx.generated_at).format('D MMM YYYY HH:mm')}
          </Caption1>
        ) : (
          <Caption1>No PowerPoint generated yet.</Caption1>
        )}
      </Panel>

      <Panel title="Linked items">
        {model.linked_items.length === 0 && <Caption1>No linked items.</Caption1>}
        {model.linked_items.map((it) => (
          <div key={it.item_id} className={s.row}>
            <Body1 className={s.grow}>
              <strong>{it.item_id}</strong> {it.title}
            </Body1>
            <Badge appearance="tint" color={it.status === 'Complete' ? 'success' : 'informative'}>
              {it.status}
            </Badge>
          </div>
        ))}
        <Caption1>These items become Complete when the support model is agreed.</Caption1>
      </Panel>
    </div>
  );
}

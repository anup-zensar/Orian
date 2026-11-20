import { useRef, useState } from 'react';
import {
  Badge,
  Body1,
  Button,
  Caption1,
  Field,
  Input,
  MessageBar,
  MessageBarBody,
  Spinner,
  makeStyles,
  tokens,
} from '@fluentui/react-components';
import { AttachRegular, DeleteRegular } from '@fluentui/react-icons';
import dayjs from 'dayjs';
import { Panel } from './Panel';
import { useSuccessToast } from '../../admin/useSavedToast';
import { useApiErrorToast } from '../../../hooks/useApiErrorToast';
import { useOptions } from '../../reference/options';
import {
  useConfluenceFetch,
  useSaveInputs,
  type ConfluenceSummary,
  type SupportModel,
} from '../api';

const useStyles = makeStyles({
  stack: { display: 'flex', flexDirection: 'column', gap: tokens.spacingVerticalL },
  row: {
    display: 'flex',
    gap: tokens.spacingHorizontalS,
    alignItems: 'center',
    flexWrap: 'wrap',
  },
  grow: { flexGrow: 1, minWidth: 0 },
  summary: {
    padding: tokens.spacingVerticalM,
    borderRadius: tokens.borderRadiusMedium,
    backgroundColor: tokens.colorNeutralBackground3,
  },
  hidden: { display: 'none' },
});

interface Slot {
  key: 'recording' | 'design' | 'diagram';
  title: string;
  /** Kinds of the support_file_kinds list this slot accepts; their extensions come from the list. */
  kinds: string[];
  hint: string;
  exts: string[];
}

const SLOT_DEFS: Pick<Slot, 'key' | 'title' | 'kinds'>[] = [
  {
    key: 'recording',
    title: 'Walkthrough recording or transcript',
    kinds: ['recording', 'transcript'],
  },
  { key: 'design', title: 'Solution design', kinds: ['design'] },
  { key: 'diagram', title: 'Architecture diagrams', kinds: ['diagram'] },
];

const ext = (name: string) => name.slice(name.lastIndexOf('.')).toLowerCase();
const size = (n: number) =>
  n > 1048576 ? `${(n / 1048576).toFixed(1)} MB` : `${Math.ceil(n / 1024)} KB`;

/** Step 1: Confluence link (looked up on blur) and file uploads (multipart). */
export function InputsStep(props: { transitionId: string; model: SupportModel }) {
  const s = useStyles();
  const showError = useApiErrorToast();
  const notify = useSuccessToast();
  const { model } = props;
  const editable = model.can_edit;
  const fileKinds = useOptions('support_file_kinds');
  const slots: Slot[] = SLOT_DEFS.map((def) => {
    const exts = fileKinds
      .filter((k) => def.kinds.includes(k.value))
      .flatMap((k) => (Array.isArray(k.meta.extensions) ? (k.meta.extensions as string[]) : []));
    return { ...def, exts, hint: exts.join(', ') };
  });
  const save = useSaveInputs(props.transitionId);
  const fetchPage = useConfluenceFetch();

  const serverUrl = model.inputs.confluence_url ?? '';
  const [seenUrl, setSeenUrl] = useState(serverUrl);
  const [url, setUrl] = useState(serverUrl);
  const [lookup, setLookup] = useState<ConfluenceSummary | null>(model.inputs.confluence ?? null);
  if (serverUrl !== seenUrl) {
    setSeenUrl(serverUrl);
    setUrl(serverUrl);
    setLookup(model.inputs.confluence ?? null);
  }
  const [staged, setStaged] = useState<File[]>([]);
  const [fileError, setFileError] = useState<string | null>(null);
  const refs = useRef<Record<string, HTMLInputElement | null>>({});

  const onBlur = () => {
    const u = url.trim();
    if (!u || u === lookup?.title) return;
    fetchPage.mutate(u, { onSuccess: setLookup, onError: showError });
  };

  const pick = (slot: Slot, files: FileList | null) => {
    if (!files) return;
    const ok: File[] = [];
    const bad: File[] = [];
    for (const f of Array.from(files)) (slot.exts.includes(ext(f.name)) ? ok : bad).push(f);
    setFileError(
      bad.length ? `Not allowed here: ${bad.map((f) => f.name).join(', ')} (${slot.hint})` : null,
    );
    if (ok.length) setStaged((cur) => [...cur, ...ok]);
  };

  const urlChanged = url.trim() !== serverUrl.trim();
  const canSave = editable && (staged.length > 0 || urlChanged) && !save.isPending;

  return (
    <div className={s.stack}>
      <MessageBar intent="info">
        <MessageBarBody>{model.info_note}</MessageBarBody>
      </MessageBar>
      {!editable && (
        <MessageBar intent="warning">
          <MessageBarBody>
            {model.edit_denied_reason ?? 'Inputs cannot be changed in the current status.'}
          </MessageBarBody>
        </MessageBar>
      )}

      <Panel title="Confluence / Atlassian link">
        <Field label="Page URL">
          <Input
            value={url}
            disabled={!editable}
            placeholder="https://example.atlassian.net/wiki/spaces/..."
            onChange={(_, d) => setUrl(d.value)}
            onBlur={onBlur}
            contentAfter={fetchPage.isPending ? <Spinner size="tiny" /> : undefined}
          />
        </Field>
        {lookup && (
          <div className={s.summary} aria-live="polite">
            <Body1>
              <strong>{lookup.title}</strong>
            </Body1>
            <div>
              <Caption1>{lookup.summary}</Caption1>
            </div>
            {lookup.diagrams.length > 0 && (
              <Caption1>Diagrams on page: {lookup.diagrams.join(', ')}</Caption1>
            )}
          </div>
        )}
      </Panel>

      <Panel title="Uploads">
        {slots.map((slot) => (
          <div key={slot.key} className={s.row}>
            <Body1 className={s.grow}>
              {slot.title} <Caption1>({slot.hint})</Caption1>
            </Body1>
            <input
              ref={(el) => {
                refs.current[slot.key] = el;
              }}
              className={s.hidden}
              type="file"
              multiple
              accept={slot.exts.join(',')}
              aria-label={slot.title}
              onChange={(e) => {
                pick(slot, e.target.files);
                e.target.value = '';
              }}
            />
            <Button
              icon={<AttachRegular />}
              disabled={!editable}
              onClick={() => refs.current[slot.key]?.click()}
            >
              Choose files
            </Button>
          </div>
        ))}
        {fileError && (
          <MessageBar intent="error">
            <MessageBarBody>{fileError}</MessageBarBody>
          </MessageBar>
        )}
        {staged.map((f, i) => (
          <div key={`${f.name}-${i}`} className={s.row}>
            <Badge appearance="tint" color="brand">
              To upload
            </Badge>
            <Body1 className={s.grow}>
              {f.name} <Caption1>{size(f.size)}</Caption1>
            </Body1>
            <Button
              appearance="subtle"
              icon={<DeleteRegular />}
              aria-label={`Remove ${f.name}`}
              onClick={() => setStaged((cur) => cur.filter((_, j) => j !== i))}
            />
          </div>
        ))}
        {model.inputs.files.length === 0 && staged.length === 0 && (
          <Caption1>No files uploaded yet.</Caption1>
        )}
        {model.inputs.files.map((f) => (
          <div key={`${f.filename}-${f.uploaded_at}`} className={s.row}>
            <Badge appearance="tint">{f.kind}</Badge>
            <Body1 className={s.grow}>
              {f.filename} <Caption1>{size(f.size)}</Caption1>
            </Body1>
            <Caption1>{dayjs(f.uploaded_at).format('D MMM YYYY HH:mm')}</Caption1>
          </div>
        ))}
        <div>
          <Button
            appearance="primary"
            disabled={!canSave}
            onClick={() =>
              save.mutate(
                { confluenceUrl: url, files: staged },
                {
                  onSuccess: () => {
                    notify('Inputs saved');
                    setStaged([]);
                    setFileError(null);
                  },
                  onError: showError,
                },
              )
            }
          >
            {save.isPending ? 'Saving' : 'Save inputs'}
          </Button>
        </div>
      </Panel>
    </div>
  );
}

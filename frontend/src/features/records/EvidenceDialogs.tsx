import { useState } from 'react';
import {
  Button,
  Dialog,
  DialogActions,
  DialogBody,
  DialogContent,
  DialogSurface,
  DialogTitle,
  Field,
  Input,
  Select,
  Textarea,
} from '@fluentui/react-components';
import { useApiErrorToast } from '../../hooks/useApiErrorToast';
import { useAddEvidence, useReviewEvidence, type Evidence, type Item } from './api';
import { ItemSelect } from './common';
import { useRecordStyles } from './hooks';

const TYPES = ['Document', 'Link', 'Email sign-off', 'Recording'] as const;
type Kind = (typeof TYPES)[number];

/** "Add evidence": file upload (multipart), link URL or email sign-off text (spec 8.7 d). */
export function AddEvidenceDialog(props: {
  transitionId: string;
  open: boolean;
  onClose: () => void;
  items: Item[] | undefined;
  initialItem?: string;
}) {
  const s = useRecordStyles();
  const add = useAddEvidence(props.transitionId);
  const showError = useApiErrorToast();
  const [title, setTitle] = useState('');
  const [type, setType] = useState<Kind>('Document');
  const [itemId, setItemId] = useState(props.initialItem ?? '');
  const [url, setUrl] = useState('');
  const [text, setText] = useState('');
  const [file, setFile] = useState<File | null>(null);

  const isLink = type === 'Link';
  const isEmail = type === 'Email sign-off';
  const valid =
    title.trim().length > 0 &&
    (isLink ? url.trim().length > 0 : isEmail ? text.trim().length > 0 : file !== null);

  const submit = () => {
    const fd = new FormData();
    fd.set('title', title.trim());
    fd.set('type', type);
    if (itemId) fd.set('item_id', itemId);
    if (isLink) fd.set('url', url.trim());
    else if (isEmail) fd.set('text', text.trim());
    else if (file) fd.set('file', file);
    add.mutate(fd, {
      onSuccess: () => {
        setTitle('');
        setUrl('');
        setText('');
        setFile(null);
        props.onClose();
      },
      onError: showError,
    });
  };

  return (
    <Dialog open={props.open} onOpenChange={(_, d) => !d.open && props.onClose()}>
      <DialogSurface>
        <DialogBody>
          <DialogTitle>Add evidence</DialogTitle>
          <DialogContent className={s.form}>
            <Field label="Title" required>
              <Input value={title} onChange={(_, d) => setTitle(d.value)} />
            </Field>
            <Field label="Type" required>
              <Select value={type} onChange={(_, d) => setType(d.value as Kind)}>
                {TYPES.map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
              </Select>
            </Field>
            <ItemSelect
              label="Checklist item"
              items={props.items}
              value={itemId}
              onChange={setItemId}
              emptyLabel="General evidence (no item)"
            />
            {isLink && (
              <Field label="Link URL" required>
                <Input value={url} onChange={(_, d) => setUrl(d.value)} placeholder="https://" />
              </Field>
            )}
            {isEmail && (
              <Field label="Sign-off text" required hint="Paste the email sign-off wording.">
                <Textarea value={text} onChange={(_, d) => setText(d.value)} rows={4} />
              </Field>
            )}
            {!isLink && !isEmail && (
              <Field label="File" required>
                <input
                  type="file"
                  aria-label="File"
                  onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                />
              </Field>
            )}
          </DialogContent>
          <DialogActions>
            <Button appearance="secondary" onClick={props.onClose}>
              Cancel
            </Button>
            <Button appearance="primary" disabled={!valid || add.isPending} onClick={submit}>
              {add.isPending ? 'Adding…' : 'Add evidence'}
            </Button>
          </DialogActions>
        </DialogBody>
      </DialogSurface>
    </Dialog>
  );
}

/** Accept / Reject evidence with a note (rejection requires one). */
export function ReviewEvidenceDialog(props: {
  transitionId: string;
  evidence: Evidence | null;
  decision: 'Accept' | 'Reject';
  onClose: () => void;
}) {
  const s = useRecordStyles();
  const review = useReviewEvidence(props.transitionId);
  const showError = useApiErrorToast();
  const [note, setNote] = useState('');
  const ev = props.evidence;
  const needsNote = props.decision === 'Reject';

  return (
    <Dialog open={!!ev} onOpenChange={(_, d) => !d.open && props.onClose()}>
      <DialogSurface>
        <DialogBody>
          <DialogTitle>
            {props.decision === 'Accept' ? 'Accept' : 'Reject'} evidence {ev?.id}
          </DialogTitle>
          <DialogContent className={s.form}>
            <span>{ev?.title}</span>
            <Field label="Note" required={needsNote}>
              <Textarea value={note} onChange={(_, d) => setNote(d.value)} rows={3} />
            </Field>
          </DialogContent>
          <DialogActions>
            <Button appearance="secondary" onClick={props.onClose}>
              Cancel
            </Button>
            <Button
              appearance="primary"
              disabled={review.isPending || (needsNote && !note.trim())}
              onClick={() =>
                ev &&
                review.mutate(
                  { id: ev.id, decision: props.decision, note: note.trim() },
                  {
                    onSuccess: () => {
                      setNote('');
                      props.onClose();
                    },
                    onError: showError,
                  },
                )
              }
            >
              {props.decision}
            </Button>
          </DialogActions>
        </DialogBody>
      </DialogSurface>
    </Dialog>
  );
}

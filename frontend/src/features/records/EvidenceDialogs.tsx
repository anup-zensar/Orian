import { ReturnFocusDialog } from '../../components/ReturnFocusDialog';
import { useState } from 'react';
import {
  Button,
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
import { FormFull, FormGrid } from '../../components/layout/FormGrid';
import { useApiErrorToast } from '../../hooks/useApiErrorToast';
import { useOptions } from '../reference/options';
import { useAddEvidence, useReviewEvidence, type Evidence, type Item } from './api';
import { ItemSelect } from './common';
import { useRecordStyles } from './hooks';

/** "Add evidence": file upload (multipart), link URL or email sign-off text (spec 8.7 d). */
export function AddEvidenceDialog(props: {
  transitionId: string;
  open: boolean;
  onClose: () => void;
  items: Item[] | undefined;
  initialItem?: string;
}) {
  const add = useAddEvidence(props.transitionId);
  const showError = useApiErrorToast();
  const [title, setTitle] = useState('');
  // Types a person can add; system types (Generated) are created by Orion tools only.
  const types = useOptions('evidence_types').filter((o) => !o.meta.system);
  const [chosen, setType] = useState('');
  const type = chosen || types[0]?.value || '';
  // What the type needs: a file, a link URL or pasted text (list setting 'needs').
  const needs = types.find((o) => o.value === type)?.meta.needs;
  const [itemId, setItemId] = useState(props.initialItem ?? '');
  const [url, setUrl] = useState('');
  const [text, setText] = useState('');
  const [file, setFile] = useState<File | null>(null);

  const isLink = needs === 'url';
  const isEmail = needs === 'text';
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
    <ReturnFocusDialog open={props.open} onOpenChange={(_, d) => !d.open && props.onClose()}>
      <DialogSurface style={{ maxWidth: 640, width: '95vw' }}>
        <DialogBody>
          <DialogTitle>Add evidence</DialogTitle>
          <DialogContent>
            <FormGrid minColWidth={220}>
              <FormFull>
                <Field label="Title" required>
                  <Input value={title} onChange={(_, d) => setTitle(d.value)} />
                </Field>
              </FormFull>
              <Field label="Type" required>
                <Select value={type} onChange={(_, d) => setType(d.value)}>
                  {types.map((t) => (
                    <option key={t.value} value={t.value}>
                      {t.label}
                    </option>
                  ))}
                </Select>
              </Field>
              <FormFull>
                <ItemSelect
                  label="Checklist item"
                  items={props.items}
                  value={itemId}
                  onChange={setItemId}
                  emptyLabel="General evidence (no item)"
                />
              </FormFull>
              {isLink && (
                <FormFull>
                  <Field label="Link URL" required>
                    <Input
                      value={url}
                      onChange={(_, d) => setUrl(d.value)}
                      placeholder="https://"
                    />
                  </Field>
                </FormFull>
              )}
              {isEmail && (
                <FormFull>
                  <Field label="Sign-off text" required hint="Paste the email sign-off wording.">
                    <Textarea value={text} onChange={(_, d) => setText(d.value)} rows={4} />
                  </Field>
                </FormFull>
              )}
              {!isLink && !isEmail && (
                <FormFull>
                  <Field label="File" required>
                    <input
                      type="file"
                      aria-label="File"
                      onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                    />
                  </Field>
                </FormFull>
              )}
            </FormGrid>
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
    </ReturnFocusDialog>
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
    <ReturnFocusDialog open={!!ev} onOpenChange={(_, d) => !d.open && props.onClose()}>
      <DialogSurface style={{ maxWidth: 640, width: '95vw' }}>
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
    </ReturnFocusDialog>
  );
}

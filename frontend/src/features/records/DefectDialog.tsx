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
} from '@fluentui/react-components';
import { useApiErrorToast } from '../../hooks/useApiErrorToast';
import { useCreateDefect, usePatchDefect, type Defect } from './api';
import { OwnerSelect } from './common';
import { useRecordStyles } from './hooks';

const PRIORITIES = ['P1', 'P2', 'P3', 'P4'] as const;

/** Create (defect undefined) or edit a hypercare defect. Mount only while open. */
export function DefectDialog(props: {
  transitionId: string;
  defect?: Defect;
  onClose: () => void;
}) {
  const s = useRecordStyles();
  const create = useCreateDefect(props.transitionId);
  const patch = usePatchDefect(props.transitionId);
  const showError = useApiErrorToast();
  const d = props.defect;
  const [title, setTitle] = useState(d?.title ?? '');
  const [priority, setPriority] = useState<(typeof PRIORITIES)[number]>(d?.priority ?? 'P3');
  const [owner, setOwner] = useState(d?.owner?.id ?? '');
  const [status, setStatus] = useState<string>(d?.status ?? 'Open');
  const opts = { onSuccess: props.onClose, onError: showError };

  const submit = () => {
    if (d) {
      patch.mutate(
        {
          id: d.id,
          patch: {
            title: title.trim(),
            priority,
            status: status as 'Open' | 'Resolved',
            owner_user_id: owner || null,
          },
        },
        opts,
      );
    } else {
      create.mutate({ title: title.trim(), priority, owner_user_id: owner || null }, opts);
    }
  };

  return (
    <Dialog open onOpenChange={(_, o) => !o.open && props.onClose()}>
      <DialogSurface>
        <DialogBody>
          <DialogTitle>{d ? `Edit defect ${d.id}` : 'Log defect'}</DialogTitle>
          <DialogContent className={s.form}>
            <Field label="Title" required>
              <Input value={title} onChange={(_, v) => setTitle(v.value)} />
            </Field>
            <Field label="Priority">
              <Select
                value={priority}
                onChange={(_, v) => setPriority(v.value as (typeof PRIORITIES)[number])}
              >
                {PRIORITIES.map((p) => (
                  <option key={p}>{p}</option>
                ))}
              </Select>
            </Field>
            <OwnerSelect label="Owner" value={owner} onChange={setOwner} allowEmpty />
            {d && (
              <Field label="Status">
                <Select value={status} onChange={(_, v) => setStatus(v.value)}>
                  {['Open', 'Resolved'].map((x) => (
                    <option key={x}>{x}</option>
                  ))}
                </Select>
              </Field>
            )}
          </DialogContent>
          <DialogActions>
            <Button appearance="secondary" onClick={props.onClose}>
              Cancel
            </Button>
            <Button
              appearance="primary"
              disabled={!title.trim() || create.isPending || patch.isPending}
              onClick={submit}
            >
              {d ? 'Save' : 'Log defect'}
            </Button>
          </DialogActions>
        </DialogBody>
      </DialogSurface>
    </Dialog>
  );
}

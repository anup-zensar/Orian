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
} from '@fluentui/react-components';
import { FormFull, FormGrid } from '../../components/layout/FormGrid';
import { useApiErrorToast } from '../../hooks/useApiErrorToast';
import { useOptions } from '../reference/options';
import {
  useCreateDefect,
  usePatchDefect,
  type Defect,
  type DefectCreate,
  type DefectPatch,
} from './api';
import { OwnerSelect } from './common';

/** Create (defect undefined) or edit a hypercare defect. Mount only while open. */
export function DefectDialog(props: {
  transitionId: string;
  defect?: Defect;
  onClose: () => void;
}) {
  const create = useCreateDefect(props.transitionId);
  const patch = usePatchDefect(props.transitionId);
  const showError = useApiErrorToast();
  const d = props.defect;
  const [title, setTitle] = useState(d?.title ?? '');
  const priorities = useOptions('defect_priorities', { include: d?.priority });
  const statuses = useOptions('defect_statuses');
  // A new defect starts at the middle priority of the list (P3 today).
  const [priority, setPriority] = useState<string>(
    d?.priority ?? priorities[Math.floor(priorities.length / 2)]?.value ?? '',
  );
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
            priority: priority as DefectPatch['priority'],
            status: status as DefectPatch['status'],
            owner_user_id: owner || null,
          },
        },
        opts,
      );
    } else {
      create.mutate(
        {
          title: title.trim(),
          priority: priority as DefectCreate['priority'],
          owner_user_id: owner || null,
        },
        opts,
      );
    }
  };

  return (
    <ReturnFocusDialog open onOpenChange={(_, o) => !o.open && props.onClose()}>
      <DialogSurface style={{ maxWidth: 640, width: '95vw' }}>
        <DialogBody>
          <DialogTitle>{d ? `Edit defect ${d.id}` : 'Log defect'}</DialogTitle>
          <DialogContent>
            <FormGrid minColWidth={220}>
              <FormFull>
                <Field label="Title" required>
                  <Input value={title} onChange={(_, v) => setTitle(v.value)} />
                </Field>
              </FormFull>
              <Field label="Priority">
                <Select value={priority} onChange={(_, v) => setPriority(v.value)}>
                  {priorities.map((p) => (
                    <option key={p.value} value={p.value}>
                      {p.label}
                    </option>
                  ))}
                </Select>
              </Field>
              <OwnerSelect label="Owner" value={owner} onChange={setOwner} allowEmpty />
              {d && (
                <Field label="Status">
                  <Select value={status} onChange={(_, v) => setStatus(v.value)}>
                    {statuses.map((x) => (
                      <option key={x.value} value={x.value}>
                        {x.label}
                      </option>
                    ))}
                  </Select>
                </Field>
              )}
            </FormGrid>
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
    </ReturnFocusDialog>
  );
}

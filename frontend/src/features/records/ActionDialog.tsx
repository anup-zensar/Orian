import { useState } from 'react';
import dayjs from 'dayjs';
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
import { useAuth } from '../../auth/useAuth';
import {
  useCreateAction,
  usePatchAction,
  type ActionPatch,
  type ActionRow,
  type Item,
} from './api';
import { ItemSelect, OwnerSelect } from './common';
import { useRecordStyles } from './hooks';

export interface ActionPrefill {
  title?: string;
  itemId?: string;
  ownerId?: string;
  dueDate?: string;
}

const PRIORITIES = ['High', 'Medium', 'Low'] as const;
const STATUSES = ['Open', 'In progress', 'Done', 'Cancelled'] as const;

/** Create (action = undefined) or edit an action. Mount it only while open so state starts fresh. */
export function ActionDialog(props: {
  transitionId: string;
  items: Item[] | undefined;
  action?: ActionRow;
  prefill?: ActionPrefill;
  onClose: () => void;
}) {
  const s = useRecordStyles();
  const { userId } = useAuth();
  const create = useCreateAction(props.transitionId);
  const patch = usePatchAction(props.transitionId);
  const showError = useApiErrorToast();
  const a = props.action;
  const p = props.prefill;
  const [title, setTitle] = useState(a?.title ?? p?.title ?? '');
  const [itemId, setItemId] = useState(a?.item_ids[0] ?? p?.itemId ?? '');
  const [owner, setOwner] = useState(a?.owner?.id ?? p?.ownerId ?? userId ?? '');
  const [due, setDue] = useState(
    a?.due_date ?? p?.dueDate ?? dayjs().add(7, 'day').format('YYYY-MM-DD'),
  );
  const [priority, setPriority] = useState<string>(a?.priority ?? 'Medium');
  const [status, setStatus] = useState<string>(a?.status ?? 'Open');

  const valid = title.trim() && owner && due;
  const pending = create.isPending || patch.isPending;
  const done = { onSuccess: props.onClose, onError: showError };

  const submit = () => {
    if (a) {
      patch.mutate(
        {
          id: a.id,
          patch: {
            title: title.trim(),
            owner_user_id: owner,
            due_date: due,
            priority,
            status,
          } as ActionPatch,
        },
        done,
      );
    } else {
      create.mutate(
        {
          title: title.trim(),
          item_ids: itemId ? [itemId] : [],
          owner_user_id: owner,
          due_date: due,
          priority: priority as (typeof PRIORITIES)[number],
        },
        done,
      );
    }
  };

  return (
    <Dialog open onOpenChange={(_, d) => !d.open && props.onClose()}>
      <DialogSurface>
        <DialogBody>
          <DialogTitle>{a ? `Edit action ${a.id}` : 'Create action'}</DialogTitle>
          <DialogContent className={s.form}>
            <Field label="Title" required>
              <Input value={title} onChange={(_, d) => setTitle(d.value)} />
            </Field>
            {a ? (
              <Field label="Linked items">{a.item_ids.join(', ') || 'None'}</Field>
            ) : (
              <ItemSelect
                label="Linked item"
                items={props.items}
                value={itemId}
                onChange={setItemId}
              />
            )}
            <OwnerSelect label="Owner" value={owner} onChange={setOwner} required />
            <Field label="Due date" required>
              <Input type="date" value={due} onChange={(_, d) => setDue(d.value)} />
            </Field>
            <Field label="Priority">
              <Select value={priority} onChange={(_, d) => setPriority(d.value)}>
                {PRIORITIES.map((x) => (
                  <option key={x}>{x}</option>
                ))}
              </Select>
            </Field>
            {a && (
              <Field label="Status">
                <Select value={status} onChange={(_, d) => setStatus(d.value)}>
                  {STATUSES.map((x) => (
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
            <Button appearance="primary" disabled={!valid || pending} onClick={submit}>
              {a ? 'Save' : 'Create action'}
            </Button>
          </DialogActions>
        </DialogBody>
      </DialogSurface>
    </Dialog>
  );
}

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
import { useAuth } from '../../auth/useAuth';
import { useReference } from '../reference/api';
import { useOptions } from '../reference/options';
import {
  useCreateCondition,
  useCreateRisk,
  usePatchCondition,
  useRequestException,
  type ConditionRow,
  type Item,
  type RiskCreate,
} from './api';
import { GateSelect, ItemSelect, OwnerSelect } from './common';

function Shell(props: {
  title: string;
  onClose: () => void;
  submitLabel: string;
  valid: boolean;
  pending: boolean;
  onSubmit: () => void;
  children: React.ReactNode;
}) {
  return (
    <ReturnFocusDialog open onOpenChange={(_, d) => !d.open && props.onClose()}>
      <DialogSurface style={{ maxWidth: 640, width: '95vw' }}>
        <DialogBody>
          <DialogTitle>{props.title}</DialogTitle>
          <DialogContent>
            <FormGrid minColWidth={220}>{props.children}</FormGrid>
          </DialogContent>
          <DialogActions>
            <Button appearance="secondary" onClick={props.onClose}>
              Cancel
            </Button>
            <Button
              appearance="primary"
              disabled={!props.valid || props.pending}
              onClick={props.onSubmit}
            >
              {props.submitLabel}
            </Button>
          </DialogActions>
        </DialogBody>
      </DialogSurface>
    </ReturnFocusDialog>
  );
}

/** Create a condition on a checklist item (spec 8.7 g). Mount only while open. */
export function CreateConditionDialog(props: {
  transitionId: string;
  items: Item[] | undefined;
  initialItem?: string;
  currentGate?: string;
  onClose: () => void;
}) {
  const { userId } = useAuth();
  const create = useCreateCondition(props.transitionId);
  const showError = useApiErrorToast();
  const ref = useReference();
  const [itemId, setItemId] = useState(props.initialItem ?? '');
  const [owner, setOwner] = useState(userId ?? '');
  const [dueGate, setDueGate] = useState(props.currentGate ?? ref.data?.gates[0]?.code ?? '');
  const [text, setText] = useState('');
  return (
    <Shell
      title="Create condition"
      onClose={props.onClose}
      submitLabel="Create condition"
      valid={!!text.trim() && !!owner && !!dueGate}
      pending={create.isPending}
      onSubmit={() =>
        create.mutate(
          {
            item_id: itemId || null,
            owner_user_id: owner,
            due_gate: dueGate,
            text: text.trim(),
          },
          { onSuccess: props.onClose, onError: showError },
        )
      }
    >
      <FormFull>
        <ItemSelect
          label="Checklist item"
          items={props.items}
          value={itemId}
          onChange={setItemId}
        />
      </FormFull>
      <OwnerSelect label="Owner" value={owner} onChange={setOwner} required />
      <GateSelect label="Due gate" value={dueGate} onChange={setDueGate} />
      <FormFull>
        <Field label="Condition" required>
          <Textarea value={text} onChange={(_, d) => setText(d.value)} rows={3} />
        </Field>
      </FormFull>
    </Shell>
  );
}

/** Close a condition with a note. */
export function CloseConditionDialog(props: {
  transitionId: string;
  condition: ConditionRow;
  onClose: () => void;
}) {
  const patch = usePatchCondition(props.transitionId);
  const showError = useApiErrorToast();
  const [note, setNote] = useState('');
  return (
    <Shell
      title={`Close condition ${props.condition.id}`}
      onClose={props.onClose}
      submitLabel="Close condition"
      valid={!!note.trim()}
      pending={patch.isPending}
      onSubmit={() =>
        patch.mutate(
          { id: props.condition.id, patch: { status: 'Closed', close_note: note.trim() } },
          { onSuccess: props.onClose, onError: showError },
        )
      }
    >
      <FormFull>
        <span>{props.condition.text}</span>
      </FormFull>
      <FormFull>
        <Field label="Closing note" required>
          <Textarea value={note} onChange={(_, d) => setNote(d.value)} rows={3} />
        </Field>
      </FormFull>
    </Shell>
  );
}

/** Request an exception for a control item (starts the EXCEPTION approval chain). */
export function RequestExceptionDialog(props: {
  transitionId: string;
  items: Item[] | undefined;
  initialItem?: string;
  onClose: () => void;
}) {
  const req = useRequestException(props.transitionId);
  const showError = useApiErrorToast();
  const [itemId, setItemId] = useState(props.initialItem ?? '');
  const [text, setText] = useState('');
  return (
    <Shell
      title="Request exception"
      onClose={props.onClose}
      submitLabel="Request exception"
      valid={!!itemId && !!text.trim()}
      pending={req.isPending}
      onSubmit={() =>
        req.mutate(
          { item_id: itemId, text: text.trim() },
          { onSuccess: props.onClose, onError: showError },
        )
      }
    >
      <FormFull>
        <ItemSelect
          label="Control item"
          items={props.items}
          value={itemId}
          onChange={setItemId}
          required
          emptyLabel="Select a control item"
        />
      </FormFull>
      <FormFull>
        <Field label="Rationale" required>
          <Textarea value={text} onChange={(_, d) => setText(d.value)} rows={4} />
        </Field>
      </FormFull>
    </Shell>
  );
}

/** Add an entry to the risk register. */
export function CreateRiskDialog(props: {
  transitionId: string;
  items: Item[] | undefined;
  onClose: () => void;
}) {
  const create = useCreateRisk(props.transitionId);
  const showError = useApiErrorToast();
  const [title, setTitle] = useState('');
  const ratings = useOptions('risk_ratings');
  // A new risk starts at the middle rating of the list (Medium today).
  const [rating, setRating] = useState<string>(
    ratings[Math.floor(ratings.length / 2)]?.value ?? '',
  );
  const [decision, setDecision] = useState('');
  const [itemId, setItemId] = useState('');
  return (
    <Shell
      title="Add risk"
      onClose={props.onClose}
      submitLabel="Add risk"
      valid={!!title.trim()}
      pending={create.isPending}
      onSubmit={() =>
        create.mutate(
          {
            title: title.trim(),
            rating: rating as RiskCreate['rating'],
            decision: decision.trim(),
            item_ids: itemId ? [itemId] : [],
          },
          { onSuccess: props.onClose, onError: showError },
        )
      }
    >
      <FormFull>
        <Field label="Title" required>
          <Input value={title} onChange={(_, d) => setTitle(d.value)} />
        </Field>
      </FormFull>
      <Field label="Rating">
        <Select value={rating} onChange={(_, d) => setRating(d.value)}>
          {ratings.map((r) => (
            <option key={r.value} value={r.value}>
              {r.label}
            </option>
          ))}
        </Select>
      </Field>
      <Field label="Decision">
        <Input value={decision} onChange={(_, d) => setDecision(d.value)} />
      </Field>
      <FormFull>
        <ItemSelect label="Linked item" items={props.items} value={itemId} onChange={setItemId} />
      </FormFull>
    </Shell>
  );
}

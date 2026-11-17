// Dialogs opened by the inline status select (spec 8.7 b): gap, N/A reason, condition.
import { useState, type ReactNode } from 'react';
import {
  Button,
  Dialog,
  DialogActions,
  DialogBody,
  DialogContent,
  DialogSurface,
  DialogTitle,
  Field,
  Select,
  Textarea,
} from '@fluentui/react-components';
import { useReference } from '../../reference/api';
import { useUsers } from '../../users/api';
import type { ItemPatchIn } from '../api';

interface ShellProps {
  title: string;
  confirmLabel: string;
  canConfirm: boolean;
  busy?: boolean;
  onConfirm: () => void;
  onClose: () => void;
  children: ReactNode;
}

function DialogShell(p: ShellProps) {
  return (
    <Dialog open onOpenChange={(_, d) => !d.open && p.onClose()}>
      <DialogSurface>
        <DialogBody>
          <DialogTitle>{p.title}</DialogTitle>
          <DialogContent style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {p.children}
          </DialogContent>
          <DialogActions>
            <Button appearance="secondary" onClick={p.onClose}>
              Cancel
            </Button>
            <Button appearance="primary" disabled={!p.canConfirm || p.busy} onClick={p.onConfirm}>
              {p.confirmLabel}
            </Button>
          </DialogActions>
        </DialogBody>
      </DialogSurface>
    </Dialog>
  );
}

/** Gap / Non-compliant: severity and a note are both required (BR-030). */
export function GapDialog(props: {
  title: string;
  status: string;
  initialSeverity?: string | null;
  initialNote?: string;
  busy?: boolean;
  onSubmit: (patch: ItemPatchIn) => void;
  onClose: () => void;
}) {
  const ref = useReference();
  const severities = ref.data?.enums.severities ?? ['Critical', 'Major', 'Minor'];
  const [severity, setSeverity] = useState(props.initialSeverity ?? '');
  const [note, setNote] = useState(props.initialNote ?? '');
  return (
    <DialogShell
      title={props.title}
      confirmLabel={`Set ${props.status}`}
      canConfirm={!!severity && !!note.trim()}
      busy={props.busy}
      onClose={props.onClose}
      onConfirm={() =>
        props.onSubmit({
          status: props.status,
          gap_severity: severity as ItemPatchIn['gap_severity'],
          note: note.trim(),
        })
      }
    >
      <Field label="Severity" required>
        <Select value={severity} onChange={(_, d) => setSeverity(d.value)}>
          <option value="">Select severity</option>
          {severities.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </Select>
      </Field>
      <Field label="Note" required hint="Describe the gap">
        <Textarea value={note} onChange={(_, d) => setNote(d.value)} rows={3} />
      </Field>
    </DialogShell>
  );
}

/** N/A: a reason is required. Used for one item (status N/A) and for the bulk action. */
export function NaDialog(props: {
  title: string;
  confirmLabel?: string;
  busy?: boolean;
  onSubmit: (reason: string) => void;
  onClose: () => void;
}) {
  const [reason, setReason] = useState('');
  return (
    <DialogShell
      title={props.title}
      confirmLabel={props.confirmLabel ?? 'Mark not applicable'}
      canConfirm={!!reason.trim()}
      busy={props.busy}
      onClose={props.onClose}
      onConfirm={() => props.onSubmit(reason.trim())}
    >
      <Field label="Reason it is not applicable" required>
        <Textarea value={reason} onChange={(_, d) => setReason(d.value)} rows={3} />
      </Field>
    </DialogShell>
  );
}

/** Compliant with conditions: creates a condition (owner, due gate, text) with the status change. */
export function ConditionDialog(props: {
  title: string;
  defaultOwnerId?: string;
  gateOptions: { code: string; short: string }[];
  busy?: boolean;
  onSubmit: (patch: ItemPatchIn) => void;
  onClose: () => void;
}) {
  const users = useUsers();
  const [owner, setOwner] = useState(props.defaultOwnerId ?? '');
  const [dueGate, setDueGate] = useState(props.gateOptions[0]?.code ?? '');
  const [text, setText] = useState('');
  return (
    <DialogShell
      title={props.title}
      confirmLabel="Set with condition"
      canConfirm={!!owner && !!dueGate && !!text.trim()}
      busy={props.busy}
      onClose={props.onClose}
      onConfirm={() =>
        props.onSubmit({
          status: 'Compliant with conditions',
          condition: { owner_user_id: owner, due_gate: dueGate, text: text.trim() },
        })
      }
    >
      <Field label="Condition" required>
        <Textarea value={text} onChange={(_, d) => setText(d.value)} rows={3} />
      </Field>
      <Field label="Owner" required>
        <Select value={owner} onChange={(_, d) => setOwner(d.value)}>
          <option value="">Select owner</option>
          {(users.data ?? []).map((u) => (
            <option key={u.id} value={u.id}>
              {u.name}
            </option>
          ))}
        </Select>
      </Field>
      <Field label="Due gate" required>
        <Select value={dueGate} onChange={(_, d) => setDueGate(d.value)}>
          {props.gateOptions.map((g) => (
            <option key={g.code} value={g.code}>
              {g.short}
            </option>
          ))}
        </Select>
      </Field>
    </DialogShell>
  );
}

import { useState } from 'react';
import {
  Button,
  Caption1,
  Dialog,
  DialogActions,
  DialogBody,
  DialogContent,
  DialogSurface,
  DialogTitle,
  Field,
  Textarea,
} from '@fluentui/react-components';
import { useQueryClient } from '@tanstack/react-query';
import { invalidateTransitionData } from '../../api/queryKeys';
import { useApiErrorToast } from '../../hooks/useApiErrorToast';
import { useRecordGateOutcome, type ConditionIn } from './api';
import { ConditionsEditor } from './ConditionsEditor';
import { conditionComplete, emptyCondition } from './conditionUtils';

const NOTE_REQUIRED = new Set(['Hold', 'Return']);

/** Outcome dialog for stage reviews and decisions: note plus (when relevant) a conditions editor. */
export function DecisionDialog(props: {
  transitionId: string;
  gate: string;
  gateShort: string;
  gateType: string;
  outcome: string;
  suggestions: Array<{ id: string; title: string }>;
  onClose: () => void;
}) {
  const { outcome } = props;
  const qc = useQueryClient();
  const showError = useApiErrorToast();
  const mutation = useRecordGateOutcome(props.transitionId, props.gate, props.gateType);
  const [note, setNote] = useState('');
  const withConditions = /conditions/i.test(outcome);
  const noteRequired = NOTE_REQUIRED.has(outcome);
  const [rows, setRows] = useState<ConditionIn[]>(withConditions ? [emptyCondition()] : []);

  const noteMissing = noteRequired && !note.trim();
  const conditionsInvalid = withConditions && (rows.length === 0 || !rows.every(conditionComplete));
  const invalid = noteMissing || conditionsInvalid;

  const submit = () =>
    mutation.mutate(
      { outcome, note: note.trim(), conditions: withConditions ? rows : [] },
      {
        onSuccess: () => {
          invalidateTransitionData(qc, props.transitionId);
          props.onClose();
        },
        onError: showError,
      },
    );

  return (
    <Dialog open onOpenChange={(_, d) => !d.open && props.onClose()}>
      <DialogSurface style={{ maxWidth: 980, width: '95vw' }}>
        <DialogBody>
          <DialogTitle>
            {outcome} · {props.gateShort}
          </DialogTitle>
          <DialogContent style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <Field
              label={noteRequired ? 'Note (required)' : 'Note'}
              required={noteRequired}
              validationMessage={noteMissing ? `A note is required for ${outcome}` : undefined}
            >
              <Textarea value={note} rows={3} onChange={(_, d) => setNote(d.value)} />
            </Field>
            {withConditions && (
              <>
                <Caption1>
                  Each condition becomes an open condition owned by the person you pick and is due
                  at a later gate. Add at least one.
                </Caption1>
                <ConditionsEditor
                  gate={props.gate}
                  rows={rows}
                  onChange={setRows}
                  suggestions={props.suggestions}
                />
              </>
            )}
          </DialogContent>
          <DialogActions>
            <Button appearance="secondary" onClick={props.onClose}>
              Cancel
            </Button>
            <Button appearance="primary" disabled={invalid || mutation.isPending} onClick={submit}>
              {mutation.isPending ? 'Saving...' : `Record: ${outcome}`}
            </Button>
          </DialogActions>
        </DialogBody>
      </DialogSurface>
    </Dialog>
  );
}

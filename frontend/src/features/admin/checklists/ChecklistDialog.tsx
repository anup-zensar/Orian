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
  Switch,
  Textarea,
  makeStyles,
  tokens,
} from '@fluentui/react-components';
import { ErrorState } from '../../../components/ErrorState';
import { ReturnFocusDialog } from '../../../components/ReturnFocusDialog';
import type { ChecklistAdmin } from '../../../api/types';
import { useCreateChecklist, useUpdateChecklist } from '../catalogApi';
import { useSuccessToast } from '../useSavedToast';

const useStyles = makeStyles({
  form: { display: 'flex', flexDirection: 'column', gap: tokens.spacingVerticalM },
});

/** Turns "Security playbook" into the code SECURITY_PLAYBOOK. */
function codeFromName(name: string): string {
  const code = name
    .toUpperCase()
    .replace(/[^A-Z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '')
    .slice(0, 40);
  return /^[0-9]/.test(code) ? `C_${code}`.slice(0, 40) : code;
}

/** Add a checklist (no `checklist`) or edit one. The code is made from the name and never changes. */
export function ChecklistDialog(props: { checklist?: ChecklistAdmin; onClose: () => void }) {
  const s = useStyles();
  const { checklist } = props;
  const create = useCreateChecklist();
  const update = useUpdateChecklist();
  const ok = useSuccessToast();
  const [label, setLabel] = useState(checklist?.label ?? '');
  const [description, setDescription] = useState(checklist?.description ?? '');
  const [tierFiltered, setTierFiltered] = useState(checklist?.tier_filtered ?? false);
  const [active, setActive] = useState(checklist?.active ?? true);
  const mutation = checklist ? update : create;
  const code = checklist?.code ?? codeFromName(label);

  const save = () => {
    const done = () => {
      ok('Saved - applies to new transitions');
      props.onClose();
    };
    if (checklist) {
      update.mutate(
        {
          code: checklist.code,
          body: { label: label.trim(), description, tier_filtered: tierFiltered, active },
        },
        { onSuccess: done },
      );
    } else {
      create.mutate(
        { code, label: label.trim(), description, tier_filtered: tierFiltered },
        { onSuccess: done },
      );
    }
  };

  return (
    <ReturnFocusDialog open onOpenChange={(_, d) => !d.open && props.onClose()}>
      <DialogSurface>
        <DialogBody>
          <DialogTitle>{checklist ? `Edit ${checklist.label}` : 'New checklist'}</DialogTitle>
          <DialogContent className={s.form}>
            <Field
              label="Name"
              required
              hint={code ? `Code: ${code} (fixed once saved)` : 'The code is made from the name.'}
            >
              <Input value={label} onChange={(_, d) => setLabel(d.value)} />
            </Field>
            <Field label="What is this checklist for?">
              <Textarea value={description} rows={2} onChange={(_, d) => setDescription(d.value)} />
            </Field>
            <Switch
              label="Items apply to specific tiers (like the AI Playbook)"
              checked={tierFiltered}
              onChange={(_, d) => setTierFiltered(d.checked)}
            />
            {checklist && (
              <Switch label="Active" checked={active} onChange={(_, d) => setActive(d.checked)} />
            )}
            {mutation.isError && <ErrorState error={mutation.error} />}
          </DialogContent>
          <DialogActions>
            <Button appearance="secondary" onClick={props.onClose}>
              Cancel
            </Button>
            <Button
              appearance="primary"
              onClick={save}
              disabled={mutation.isPending || !label.trim() || !code}
            >
              {mutation.isPending ? 'Saving...' : 'Save'}
            </Button>
          </DialogActions>
        </DialogBody>
      </DialogSurface>
    </ReturnFocusDialog>
  );
}

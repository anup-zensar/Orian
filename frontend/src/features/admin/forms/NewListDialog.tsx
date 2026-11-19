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
  Textarea,
  makeStyles,
  tokens,
} from '@fluentui/react-components';
import { ErrorState } from '../../../components/ErrorState';
import { ReturnFocusDialog } from '../../../components/ReturnFocusDialog';
import { useCreateOptionList } from '../catalogApi';
import { useSuccessToast } from '../useSavedToast';

const useStyles = makeStyles({
  form: { display: 'flex', flexDirection: 'column', gap: tokens.spacingVerticalM },
});

/** "Security level" becomes the key security_level. */
function keyFromName(name: string): string {
  const key = name
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '')
    .slice(0, 40);
  return /^[a-z]/.test(key) ? key : `list_${key}`.slice(0, 40);
}

/** Create an empty dropdown list; its values are added in the editor, and custom fields can use it. */
export function NewListDialog(props: { onCreated: (key: string) => void; onClose: () => void }) {
  const s = useStyles();
  const create = useCreateOptionList();
  const ok = useSuccessToast();
  const [label, setLabel] = useState('');
  const [description, setDescription] = useState('');
  const key = label.trim() ? keyFromName(label) : '';

  const save = () =>
    create.mutate(
      { key, label: label.trim(), description, group: 'Custom lists' },
      {
        onSuccess: () => {
          ok('Saved - applies immediately');
          props.onCreated(key);
          props.onClose();
        },
      },
    );

  return (
    <ReturnFocusDialog open onOpenChange={(_, d) => !d.open && props.onClose()}>
      <DialogSurface>
        <DialogBody>
          <DialogTitle>New dropdown list</DialogTitle>
          <DialogContent className={s.form}>
            <Field
              label="Name"
              required
              hint={key ? `Code: ${key} (fixed once saved)` : 'For example: Security level'}
            >
              <Input value={label} onChange={(_, d) => setLabel(d.value)} />
            </Field>
            <Field label="What is it for?">
              <Textarea value={description} rows={2} onChange={(_, d) => setDescription(d.value)} />
            </Field>
            {create.isError && <ErrorState error={create.error} />}
          </DialogContent>
          <DialogActions>
            <Button appearance="secondary" onClick={props.onClose}>
              Cancel
            </Button>
            <Button appearance="primary" onClick={save} disabled={create.isPending || !key}>
              {create.isPending ? 'Saving...' : 'Create list'}
            </Button>
          </DialogActions>
        </DialogBody>
      </DialogSurface>
    </ReturnFocusDialog>
  );
}

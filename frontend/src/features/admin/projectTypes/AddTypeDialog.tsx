import { useState } from 'react';
import {
  Button,
  DialogActions,
  DialogBody,
  DialogContent,
  DialogSurface,
  DialogTitle,
} from '@fluentui/react-components';
import { ErrorState } from '../../../components/ErrorState';
import { ReturnFocusDialog } from '../../../components/ReturnFocusDialog';
import type { ChecklistAdmin } from '../../../api/types';
import { useCreateProjectType } from '../catalogApi';
import { DisabledReason } from '../components/DisabledReason';
import { useSuccessToast } from '../useSavedToast';
import { TypeFields } from './TypeFields';
import { EMPTY_DRAFT, splitList, type TypeDraft } from './typeDraft';

/** One dialog to add a project type: name, checklists, switches, required fields, synonyms. */
export function AddTypeDialog(props: {
  checklists: ChecklistAdmin[];
  onCreated: (code: string) => void;
  onClose: () => void;
}) {
  const create = useCreateProjectType();
  const ok = useSuccessToast();
  const [draft, setDraft] = useState<TypeDraft>(EMPTY_DRAFT);
  const name = draft.label.trim();

  const save = () =>
    create.mutate(
      {
        code: name, // the name is also the code; the display name can be changed later
        label: name,
        description: draft.description,
        checklists: draft.checklists,
        requires_tiering: draft.requires_tiering,
        has_ai_profile: draft.has_ai_profile,
        has_eval_metrics: draft.has_eval_metrics,
        required_intake_fields: draft.required_intake_fields,
        synonyms: splitList(draft.synonyms),
      },
      {
        onSuccess: () => {
          ok('Saved - applies to new transitions');
          props.onCreated(name);
          props.onClose();
        },
      },
    );

  return (
    <ReturnFocusDialog open onOpenChange={(_, d) => !d.open && props.onClose()}>
      <DialogSurface>
        <DialogBody>
          <DialogTitle>Add project type</DialogTitle>
          <DialogContent>
            <TypeFields
              draft={draft}
              onChange={(p) => setDraft((d) => ({ ...d, ...p }))}
              checklists={props.checklists}
            />
            {create.isError && <ErrorState error={create.error} />}
          </DialogContent>
          <DialogActions>
            <Button appearance="secondary" onClick={props.onClose}>
              Cancel
            </Button>
            <DisabledReason reason={name ? null : 'Enter a display name.'}>
              <Button appearance="primary" onClick={save} disabled={create.isPending || !name}>
                {create.isPending ? 'Saving...' : 'Add project type'}
              </Button>
            </DisabledReason>
          </DialogActions>
        </DialogBody>
      </DialogSurface>
    </ReturnFocusDialog>
  );
}

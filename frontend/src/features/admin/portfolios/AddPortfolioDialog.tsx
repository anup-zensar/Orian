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
  makeStyles,
  tokens,
} from '@fluentui/react-components';
import { ErrorState } from '../../../components/ErrorState';
import { ReturnFocusDialog } from '../../../components/ReturnFocusDialog';
import { useCreatePortfolio } from '../catalogApi';
import { DisabledReason } from '../components/DisabledReason';
import { useSuccessToast } from '../useSavedToast';
import { PortfolioFields } from './PortfolioFields';
import { EMPTY_PORTFOLIO, draftToBody, type PortfolioDraft } from './portfolioDraft';

const useStyles = makeStyles({
  form: { display: 'flex', flexDirection: 'column', gap: tokens.spacingVerticalM },
});

/** A short code from the name, for example "Fuels EU" gives FE. The admin can change it. */
const suggestCode = (name: string) =>
  name
    .split(/\s+/)
    .filter(Boolean)
    .map((w) => w[0].toUpperCase())
    .join('')
    .slice(0, 10);

/** Add a portfolio. Its golden set is edited in the panel that opens afterwards. */
export function AddPortfolioDialog(props: {
  onCreated: (name: string) => void;
  onClose: () => void;
}) {
  const s = useStyles();
  const create = useCreatePortfolio();
  const ok = useSuccessToast();
  const [name, setName] = useState('');
  const [code, setCode] = useState<string | null>(null);
  const [draft, setDraft] = useState<PortfolioDraft>(EMPTY_PORTFOLIO);
  const shownCode = code ?? suggestCode(name);

  const save = () =>
    create.mutate(
      {
        name: name.trim(),
        code: shownCode.trim(),
        ...draftToBody({ ...draft, label: draft.label.trim() || name.trim() }),
      },
      {
        onSuccess: () => {
          ok('Saved - now add its golden-set items below');
          props.onCreated(name.trim());
          props.onClose();
        },
      },
    );

  return (
    <ReturnFocusDialog open onOpenChange={(_, d) => !d.open && props.onClose()}>
      <DialogSurface>
        <DialogBody>
          <DialogTitle>Add portfolio</DialogTitle>
          <DialogContent className={s.form}>
            <Field
              label="Name"
              required
              hint="Shown everywhere. It cannot be changed after you add the portfolio."
            >
              <Input value={name} onChange={(_, d) => setName(d.value)} />
            </Field>
            <Field label="Short code" required hint="Up to 10 characters, used in transition ids.">
              <Input value={shownCode} onChange={(_, d) => setCode(d.value)} maxLength={10} />
            </Field>
            <PortfolioFields
              showLabel={false}
              draft={draft}
              onChange={(p) => setDraft((d) => ({ ...d, ...p }))}
            />
            {create.isError && <ErrorState error={create.error} />}
          </DialogContent>
          <DialogActions>
            <Button appearance="secondary" onClick={props.onClose}>
              Cancel
            </Button>
            <DisabledReason
              reason={!name.trim() || !shownCode.trim() ? 'Enter a name and a short code.' : null}
            >
              <Button
                appearance="primary"
                onClick={save}
                disabled={create.isPending || !name.trim() || !shownCode.trim()}
              >
                {create.isPending ? 'Saving...' : 'Add portfolio'}
              </Button>
            </DisabledReason>
          </DialogActions>
        </DialogBody>
      </DialogSurface>
    </ReturnFocusDialog>
  );
}

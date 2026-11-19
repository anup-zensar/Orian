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
  Switch,
  Textarea,
  makeStyles,
  tokens,
} from '@fluentui/react-components';
import { ErrorState } from '../../../components/ErrorState';
import { ReturnFocusDialog } from '../../../components/ReturnFocusDialog';
import type { Lens } from '../../../theme/tokens';
import { useReference } from '../../reference/api';
import { useProjectTypes, useRoles } from '../../reference/options';
import { LENSES, useUpdatePlaybookItem, type PlaybookItem } from '../api';
import { useChecklists, useCreatePlaybookItem } from '../catalogApi';
import { CheckGroup } from '../components/CheckGroup';
import { useSuccessToast } from '../useSavedToast';

const useStyles = makeStyles({
  form: { display: 'flex', flexDirection: 'column', gap: tokens.spacingVerticalM },
});

/** Create a new item (no `item`) in any checklist, or edit an existing one. */
export function ItemDialog(props: { item?: PlaybookItem; onClose: () => void }) {
  const s = useStyles();
  const { item } = props;
  const { data: ref } = useReference();
  const checklists = useChecklists();
  const roles = useRoles();
  const projectTypes = useProjectTypes();
  const update = useUpdatePlaybookItem();
  const create = useCreatePlaybookItem();
  const ok = useSuccessToast();
  const mutation = item ? update : create;

  const [source, setSource] = useState('');
  const [portfolio, setPortfolio] = useState('');
  const [title, setTitle] = useState(item?.title ?? '');
  const [description, setDescription] = useState(item?.description ?? '');
  const [gate, setGate] = useState(item?.gate ?? ref?.gates[0]?.code ?? '');
  const [lens, setLens] = useState<string>(item?.lens ?? 'Business');
  const [tiers, setTiers] = useState<number[]>(item?.applicable_tiers ?? []);
  const [mandatory, setMandatory] = useState(item?.mandatory ?? true);
  const [active, setActive] = useState(item?.active ?? true);
  const [ownerHint, setOwnerHint] = useState('');
  const [ownerRole, setOwnerRole] = useState('');
  const [types, setTypes] = useState<string[]>([]);

  const choices = (checklists.data ?? []).filter((c) => c.active && c.kind !== 'common');
  const sourceCode = source || choices[0]?.code || '';
  const sourceKind = choices.find((c) => c.code === sourceCode)?.kind;
  const needsPortfolio = !item && sourceKind === 'portfolio_golden';
  const portfolioName = portfolio || ref?.portfolios[0] || '';

  const done = () => {
    ok('Saved - applies to new transitions');
    props.onClose();
  };
  const save = () => {
    if (item) {
      update.mutate(
        {
          id: item.id,
          body: {
            title: title.trim(),
            description,
            gate,
            lens: lens as Lens,
            applicable_tiers: tiers,
            mandatory,
            active,
          },
        },
        { onSuccess: done },
      );
    } else {
      create.mutate(
        {
          source: sourceCode,
          portfolio: needsPortfolio ? portfolioName : null,
          title: title.trim(),
          description,
          gate,
          lens: lens as Lens,
          applicable_tiers: tiers,
          mandatory,
          owner_role_hint: ownerHint,
          default_owner_role: ownerRole || null,
          applies_to_project_types: types,
          detail: '',
          secondary_lens: '',
          category: '',
          kind: 'Deliverable',
          mandatory_rule: 'always',
        },
        { onSuccess: done },
      );
    }
  };

  return (
    <ReturnFocusDialog open onOpenChange={(_, d) => !d.open && props.onClose()}>
      <DialogSurface>
        <DialogBody>
          <DialogTitle>{item ? `Edit ${item.id}` : 'New item'}</DialogTitle>
          <DialogContent className={s.form}>
            {!item && (
              <Field label="Checklist" required>
                <Select value={sourceCode} onChange={(_, d) => setSource(d.value)}>
                  {choices.map((c) => (
                    <option key={c.code} value={c.code}>
                      {c.label}
                    </option>
                  ))}
                </Select>
              </Field>
            )}
            {needsPortfolio && (
              <Field label="Portfolio" required hint="This checklist is chosen by portfolio.">
                <Select value={portfolioName} onChange={(_, d) => setPortfolio(d.value)}>
                  {(ref?.portfolio_details ?? [])
                    .filter((p) => p.active !== false)
                    .map((p) => (
                      <option key={p.name} value={p.name}>
                        {p.label || p.name}
                      </option>
                    ))}
                </Select>
              </Field>
            )}
            <Field label="Title" required>
              <Input value={title} onChange={(_, d) => setTitle(d.value)} />
            </Field>
            <Field label="Description">
              <Textarea value={description} rows={3} onChange={(_, d) => setDescription(d.value)} />
            </Field>
            <Field label="Gate">
              <Select value={gate} onChange={(_, d) => setGate(d.value)}>
                {(ref?.gates ?? []).map((g) => (
                  <option key={g.code} value={g.code}>
                    {g.label}
                  </option>
                ))}
                {!ref?.gates.some((g) => g.code === gate) && <option value={gate}>{gate}</option>}
              </Select>
            </Field>
            <Field
              label="Area (Business, Technical or Compliance)"
              hint={item?.lens_is_suggested ? 'Area suggested - confirm by saving' : undefined}
            >
              <Select value={lens} onChange={(_, d) => setLens(d.value)}>
                {LENSES.map((l) => (
                  <option key={l}>{l}</option>
                ))}
              </Select>
            </Field>
            <CheckGroup
              label="Applicable tiers"
              options={(ref?.tiers ?? []).map((t) => ({
                value: String(t.tier),
                label: `Tier ${t.tier}`,
              }))}
              value={tiers.map(String)}
              onChange={(v) => setTiers(v.map(Number).sort((a, b) => a - b))}
            />
            {!item && (
              <>
                <Field
                  label="Who usually owns it?"
                  hint="Free text, for example Security lead. Orion uses it to suggest an owner."
                >
                  <Input value={ownerHint} onChange={(_, d) => setOwnerHint(d.value)} />
                </Field>
                <Field
                  label="Default owner role"
                  hint="Optional. Picks the person from the transition."
                >
                  <Select value={ownerRole} onChange={(_, d) => setOwnerRole(d.value)}>
                    <option value="">No default</option>
                    {roles.map((r) => (
                      <option key={r.code} value={r.code}>
                        {r.label}
                      </option>
                    ))}
                  </Select>
                </Field>
                <CheckGroup
                  label="Project types"
                  hint="Leave all unticked to include the item for every project type, also future ones."
                  options={projectTypes.map((p) => ({ value: p.code, label: p.label }))}
                  value={types}
                  onChange={setTypes}
                />
              </>
            )}
            <Switch
              label="Mandatory"
              checked={mandatory}
              onChange={(_, d) => setMandatory(d.checked)}
            />
            {item && (
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
              disabled={mutation.isPending || !title.trim() || (!item && !sourceCode)}
            >
              {mutation.isPending ? 'Saving...' : 'Save'}
            </Button>
          </DialogActions>
        </DialogBody>
      </DialogSurface>
    </ReturnFocusDialog>
  );
}

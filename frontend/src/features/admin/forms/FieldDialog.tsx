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
import type { IntakeFieldAdmin } from '../../../api/types';
import { usePortfolios, useProjectTypes, useRoles } from '../../reference/options';
import { useCreateIntakeField, useOptionListsAdmin, useUpdateIntakeField } from '../catalogApi';
import { CheckGroup } from '../components/CheckGroup';
import { DisabledReason } from '../components/DisabledReason';
import { useSuccessToast } from '../useSavedToast';
import { TYPE_TEXT, type FieldType, type RequiredMode } from './fieldTypes';

const useStyles = makeStyles({
  form: { display: 'flex', flexDirection: 'column', gap: tokens.spacingVerticalM },
  row: { display: 'flex', gap: tokens.spacingHorizontalM, flexWrap: 'wrap' },
});

const toNumber = (text: string): number | null => (text.trim() === '' ? null : Number(text));

/**
 * Add a custom field (no `field`) or edit one. Built-in fields can change label, help text and
 * visibility; custom fields can change everything except their code.
 */
export function FieldDialog(props: { field?: IntakeFieldAdmin; onClose: () => void }) {
  const s = useStyles();
  const { field } = props;
  const custom = !field || !field.builtin;
  const create = useCreateIntakeField();
  const update = useUpdateIntakeField();
  const mutation = field ? update : create;
  const ok = useSuccessToast();
  const lists = useOptionListsAdmin();
  const projectTypes = useProjectTypes();
  const portfolios = usePortfolios();
  const roles = useRoles();

  const [label, setLabel] = useState(field?.label ?? '');
  const [help, setHelp] = useState(field?.help ?? '');
  const [type, setType] = useState<FieldType>(field?.type ?? 'text');
  const [optionList, setOptionList] = useState(field?.option_list ?? '');
  const [visible, setVisible] = useState(field?.visible ?? true);
  const [active, setActive] = useState(field?.active ?? true);
  const [requiredMode, setRequiredMode] = useState<RequiredMode>(field?.required_mode ?? 'never');
  const [requiredTypes, setRequiredTypes] = useState(field?.required_for_project_types ?? []);
  const [appliesTypes, setAppliesTypes] = useState(field?.applies_to_project_types ?? []);
  const [appliesPortfolios, setAppliesPortfolios] = useState(field?.applies_to_portfolios ?? []);
  const [onOverview, setOnOverview] = useState(field?.show_on_overview ?? false);
  const [filterable, setFilterable] = useState(field?.filterable ?? false);
  const [inList, setInList] = useState(field?.show_in_list ?? false);
  const [min, setMin] = useState(field?.min != null ? String(field.min) : '');
  const [max, setMax] = useState(field?.max != null ? String(field.max) : '');
  const [maxLength, setMaxLength] = useState(
    field?.max_length != null ? String(field.max_length) : '',
  );

  const isList = type === 'select' || type === 'multiselect';
  const typeReason = field?.type_locked
    ? (field.lock_reason ?? 'Some transitions already hold a value, so the type cannot change.')
    : null;
  const hideReason = field?.structural
    ? 'The app needs this field, so it cannot be hidden. You can still rename it.'
    : null;
  const needsTypes = requiredMode === 'by_project_type' && requiredTypes.length === 0;
  const ready = !!label.trim() && (!isList || !!optionList) && !needsTypes;
  const notReadyReason = !label.trim()
    ? 'Give the field a label.'
    : isList && !optionList
      ? 'Choose a dropdown list.'
      : needsTypes
        ? 'Tick at least one project type that requires this field.'
        : null;

  const done = () => {
    ok('Saved - applies to new transitions');
    props.onClose();
  };
  const save = () => {
    const common = {
      label: label.trim(),
      help,
      required_mode: requiredMode,
      required_for_project_types: requiredMode === 'by_project_type' ? requiredTypes : [],
      applies_to_project_types: appliesTypes,
      applies_to_portfolios: appliesPortfolios,
      show_on_overview: onOverview,
      filterable,
      show_in_list: inList,
      min: type === 'number' ? toNumber(min) : null,
      max: type === 'number' ? toNumber(max) : null,
      max_length: type === 'text' || type === 'textarea' ? toNumber(maxLength) : null,
    };
    if (!field) {
      create.mutate(
        {
          ...common,
          section: 'Additional details',
          form: 'intake',
          type,
          option_list: isList || type === 'user' ? optionList || null : null,
        },
        { onSuccess: done },
      );
    } else if (field.builtin) {
      const body = field.structural
        ? { label: label.trim(), help }
        : { label: label.trim(), help, visible };
      update.mutate({ key: field.key, body }, { onSuccess: done });
    } else {
      update.mutate(
        {
          key: field.key,
          body: {
            ...common,
            ...(type !== field.type ? { type } : {}),
            ...(isList || type === 'user' ? { option_list: optionList || null } : {}),
            active,
          },
        },
        { onSuccess: done },
      );
    }
  };

  return (
    <ReturnFocusDialog open onOpenChange={(_, d) => !d.open && props.onClose()}>
      <DialogSurface>
        <DialogBody>
          <DialogTitle>{field ? `Edit ${field.label}` : 'Add custom field'}</DialogTitle>
          <DialogContent className={s.form}>
            {field && (
              <Field label="Code (cannot change)">
                <code>{field.key}</code>
              </Field>
            )}
            <Field label="Label" required hint="What people see on the form.">
              <Input value={label} onChange={(_, d) => setLabel(d.value)} />
            </Field>
            <Field label="Help text" hint="A short hint shown under the field.">
              <Textarea value={help} rows={2} onChange={(_, d) => setHelp(d.value)} />
            </Field>
            {field?.builtin && (
              <DisabledReason reason={hideReason}>
                <Switch
                  label="Show this field on the form"
                  checked={visible}
                  disabled={!!hideReason}
                  onChange={(_, d) => setVisible(d.checked)}
                />
              </DisabledReason>
            )}
            {custom && (
              <>
                <Field label="Type">
                  <DisabledReason reason={typeReason}>
                    <Select
                      value={type}
                      disabled={!!typeReason}
                      onChange={(_, d) => setType(d.value as FieldType)}
                    >
                      {(Object.keys(TYPE_TEXT) as FieldType[]).map((t) => (
                        <option key={t} value={t}>
                          {TYPE_TEXT[t]}
                        </option>
                      ))}
                    </Select>
                  </DisabledReason>
                </Field>
                {isList && (
                  <Field
                    label="Dropdown list"
                    required
                    hint="The values people can pick. Add or change lists under Dropdown lists below."
                  >
                    <Select value={optionList} onChange={(_, d) => setOptionList(d.value)}>
                      <option value="">Choose a list</option>
                      {(lists.data ?? []).map((l) => (
                        <option key={l.key} value={l.key}>
                          {l.label}
                        </option>
                      ))}
                    </Select>
                  </Field>
                )}
                {type === 'user' && (
                  <Field label="Offer people with this role">
                    <Select value={optionList} onChange={(_, d) => setOptionList(d.value)}>
                      <option value="">Anyone</option>
                      {roles.map((r) => (
                        <option key={r.code} value={r.code}>
                          {r.label}
                        </option>
                      ))}
                    </Select>
                  </Field>
                )}
                {type === 'number' && (
                  <div className={s.row}>
                    <Field label="Smallest allowed">
                      <Input type="number" value={min} onChange={(_, d) => setMin(d.value)} />
                    </Field>
                    <Field label="Largest allowed">
                      <Input type="number" value={max} onChange={(_, d) => setMax(d.value)} />
                    </Field>
                  </div>
                )}
                {(type === 'text' || type === 'textarea') && (
                  <Field label="Longest text allowed (characters)">
                    <Input
                      type="number"
                      value={maxLength}
                      onChange={(_, d) => setMaxLength(d.value)}
                    />
                  </Field>
                )}
                <Field label="Is it required?">
                  <Select
                    value={requiredMode}
                    onChange={(_, d) => setRequiredMode(d.value as RequiredMode)}
                  >
                    <option value="never">No, it is optional</option>
                    <option value="always">Yes, always</option>
                    <option value="by_project_type">Only for some project types</option>
                  </Select>
                </Field>
                {requiredMode === 'by_project_type' && (
                  <CheckGroup
                    label="Required for these project types"
                    hint="Add the project type first, then tick it here."
                    options={projectTypes.map((p) => ({ value: p.code, label: p.label }))}
                    value={requiredTypes}
                    onChange={setRequiredTypes}
                  />
                )}
                <CheckGroup
                  label="Show it only for these project types"
                  hint="Optional. Leave all unticked to show it for every project type."
                  options={projectTypes.map((p) => ({ value: p.code, label: p.label }))}
                  value={appliesTypes}
                  onChange={setAppliesTypes}
                />
                <CheckGroup
                  label="Show it only for these portfolios"
                  hint="Optional. Leave all unticked to show it for every portfolio."
                  options={portfolios.map((p) => ({ value: p.name, label: p.label }))}
                  value={appliesPortfolios}
                  onChange={setAppliesPortfolios}
                />
                <Switch
                  label="Show the answer on the transition overview"
                  checked={onOverview}
                  onChange={(_, d) => setOnOverview(d.checked)}
                />
                <Switch
                  label="Show it as a column in the transitions list"
                  checked={inList}
                  onChange={(_, d) => setInList(d.checked)}
                />
                <DisabledReason
                  reason={
                    isList || type === 'boolean'
                      ? null
                      : 'Filtering works for dropdown lists and yes/no fields only.'
                  }
                >
                  <Switch
                    label="Let people filter the transition list by it"
                    checked={filterable}
                    disabled={!(isList || type === 'boolean')}
                    onChange={(_, d) => setFilterable(d.checked)}
                  />
                </DisabledReason>
                {field && (
                  <Switch
                    label={
                      active
                        ? 'In use on the form'
                        : 'Retired: hidden from the form, old answers stay readable'
                    }
                    checked={active}
                    onChange={(_, d) => setActive(d.checked)}
                  />
                )}
              </>
            )}
            {mutation.isError && <ErrorState error={mutation.error} />}
          </DialogContent>
          <DialogActions>
            <Button appearance="secondary" onClick={props.onClose}>
              Cancel
            </Button>
            <DisabledReason reason={ready ? null : notReadyReason}>
              <Button appearance="primary" onClick={save} disabled={mutation.isPending || !ready}>
                {mutation.isPending ? 'Saving...' : 'Save'}
              </Button>
            </DisabledReason>
          </DialogActions>
        </DialogBody>
      </DialogSurface>
    </ReturnFocusDialog>
  );
}

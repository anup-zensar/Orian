import { Field, Input, Switch, Textarea, makeStyles, tokens } from '@fluentui/react-components';
import type { ChecklistAdmin } from '../../../api/types';
import { useReference } from '../../reference/api';
import { CheckGroup } from '../components/CheckGroup';
import { previewSentence, type TypeDraft } from './typeDraft';

const useStyles = makeStyles({
  form: { display: 'flex', flexDirection: 'column', gap: tokens.spacingVerticalM },
  preview: { color: tokens.colorNeutralForeground2 },
});

/** The shared form body of the Add project type dialog and the side panel. */
export function TypeFields(props: {
  draft: TypeDraft;
  onChange: (patch: Partial<TypeDraft>) => void;
  checklists: ChecklistAdmin[];
}) {
  const s = useStyles();
  const { draft, onChange } = props;
  const { data: ref } = useReference();
  const libraryChecklists = props.checklists.filter((c) => c.kind === 'library' && c.active);
  const requirable = (ref?.intake_fields ?? []).filter((f) => f.active !== false && !f.structural);

  return (
    <div className={s.form}>
      <Field label="Display name" required>
        <Input value={draft.label} onChange={(_, d) => onChange({ label: d.value })} />
      </Field>
      <Field label="Description">
        <Textarea
          value={draft.description}
          rows={2}
          onChange={(_, d) => onChange({ description: d.value })}
        />
      </Field>
      <CheckGroup
        label="Checklists"
        hint="The common checklist and the portfolio golden set are always added."
        options={libraryChecklists.map((c) => ({
          value: c.code,
          label: `${c.label} (${c.item_count})`,
        }))}
        value={draft.checklists}
        onChange={(v) => onChange({ checklists: v })}
      />
      <Field hint="Adds a risk-tier step before scope.">
        <Switch
          label="Requires tiering"
          checked={draft.requires_tiering}
          onChange={(_, d) => onChange({ requires_tiering: d.checked })}
        />
      </Field>
      <Field hint="Adds the AI playbook tab and the AI profile form.">
        <Switch
          label="Has an AI profile"
          checked={draft.has_ai_profile}
          onChange={(_, d) => onChange({ has_ai_profile: d.checked })}
        />
      </Field>
      <Field hint="Adds evaluation targets that are checked per tier.">
        <Switch
          label="Has eval metrics"
          checked={draft.has_eval_metrics}
          onChange={(_, d) => onChange({ has_eval_metrics: d.checked })}
        />
      </Field>
      <CheckGroup
        label="Intake fields that must be filled in"
        hint="A custom field only appears here once it exists. Add the project type first, then tick it on the field if needed."
        options={requirable.map((f) => ({ value: f.key, label: f.label }))}
        value={draft.required_intake_fields}
        onChange={(v) => onChange({ required_intake_fields: v })}
      />
      <Field
        label="Other names Orion understands"
        hint="Comma separated, for example: security review, SecRev"
      >
        <Input value={draft.synonyms} onChange={(_, d) => onChange({ synonyms: d.value })} />
      </Field>
      <div className={s.preview} aria-live="polite">
        {previewSentence(draft.checklists, props.checklists)}
      </div>
    </div>
  );
}

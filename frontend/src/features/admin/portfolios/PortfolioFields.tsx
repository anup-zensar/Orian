import { Field, Input, Switch, Textarea, makeStyles, tokens } from '@fluentui/react-components';
import type { PortfolioDraft } from './portfolioDraft';

const useStyles = makeStyles({
  form: { display: 'flex', flexDirection: 'column', gap: tokens.spacingVerticalM },
});

/** The shared form body of the Add portfolio dialog and the edit panel. */
export function PortfolioFields(props: {
  draft: PortfolioDraft;
  onChange: (patch: Partial<PortfolioDraft>) => void;
  showLabel?: boolean; // false in the Add dialog, which already asks for the name
}) {
  const s = useStyles();
  const { draft, onChange } = props;
  return (
    <div className={s.form}>
      {props.showLabel !== false && (
        <Field label="Display name" required>
          <Input value={draft.label} onChange={(_, d) => onChange({ label: d.value })} />
        </Field>
      )}
      <Field label="Description">
        <Textarea
          value={draft.description}
          rows={2}
          onChange={(_, d) => onChange({ description: d.value })}
        />
      </Field>
      <Field label="Focus areas" hint="One per line.">
        <Textarea
          value={draft.focus_areas}
          rows={3}
          onChange={(_, d) => onChange({ focus_areas: d.value })}
        />
      </Field>
      <Switch
        label="Requires sites (the intake asks for a list of sites)"
        checked={draft.requires_sites}
        onChange={(_, d) => onChange({ requires_sites: d.checked })}
      />
      {draft.requires_sites && (
        <Field label="What are the sites called?" hint="For example: Sites, Stations, Terminals.">
          <Input
            value={draft.sites_label}
            onChange={(_, d) => onChange({ sites_label: d.value })}
          />
        </Field>
      )}
      <Field
        label="Other names Orion understands"
        hint="Comma separated, for example: fuels europe, EU fuels"
      >
        <Input value={draft.synonyms} onChange={(_, d) => onChange({ synonyms: d.value })} />
      </Field>
    </div>
  );
}

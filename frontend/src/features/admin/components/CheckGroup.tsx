import { Checkbox, Label, makeStyles, tokens } from '@fluentui/react-components';

const useStyles = makeStyles({
  group: { display: 'flex', flexDirection: 'column', margin: 0, padding: 0, border: 'none' },
  checks: { display: 'flex', flexWrap: 'wrap', columnGap: tokens.spacingHorizontalL },
  hint: { color: tokens.colorNeutralForeground3, fontSize: tokens.fontSizeBase200 },
});

export interface CheckOption {
  value: string;
  label: string;
}

/**
 * A labelled group of checkboxes that edits a list of values. It is a plain fieldset, not a Fluent
 * Field: a Field hands its single control id to the first checkbox, so every label would toggle it.
 */
export function CheckGroup(props: {
  label: string;
  hint?: string;
  options: CheckOption[];
  value: string[];
  onChange: (value: string[]) => void;
}) {
  const s = useStyles();
  return (
    <fieldset className={s.group}>
      <legend>
        <Label>{props.label}</Label>
      </legend>
      <div className={s.checks}>
        {props.options.map((o) => (
          <Checkbox
            key={o.value}
            label={o.label}
            checked={props.value.includes(o.value)}
            onChange={(_, d) =>
              props.onChange(
                d.checked ? [...props.value, o.value] : props.value.filter((v) => v !== o.value),
              )
            }
          />
        ))}
      </div>
      {props.hint && <span className={s.hint}>{props.hint}</span>}
    </fieldset>
  );
}

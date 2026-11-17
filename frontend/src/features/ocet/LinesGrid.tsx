import {
  Badge,
  Button,
  Caption1,
  Field,
  Input,
  Popover,
  PopoverSurface,
  PopoverTrigger,
  Select,
  Textarea,
  Tooltip,
  makeStyles,
  mergeClasses,
  tokens,
} from '@fluentui/react-components';
import { Delete16Regular, Info16Regular } from '@fluentui/react-icons';
import { fmtFull, OWNER_ROLES } from './format';
import { project, type EditLine } from './lineModel';

const useStyles = makeStyles({
  wrap: {
    overflowX: 'auto',
    border: `1px solid ${tokens.colorNeutralStroke2}`,
    borderRadius: tokens.borderRadiusMedium,
  },
  table: { borderCollapse: 'collapse', width: '100%', minWidth: '1500px' },
  th: {
    textAlign: 'left',
    padding: `${tokens.spacingVerticalS} ${tokens.spacingHorizontalS}`,
    backgroundColor: tokens.colorNeutralBackground3,
    fontWeight: tokens.fontWeightSemibold,
    fontSize: tokens.fontSizeBase200,
    whiteSpace: 'nowrap',
  },
  td: {
    padding: tokens.spacingHorizontalXS,
    borderTop: `1px solid ${tokens.colorNeutralStroke2}`,
    verticalAlign: 'middle',
  },
  num: {
    textAlign: 'right',
    fontVariantNumeric: 'tabular-nums',
    whiteSpace: 'nowrap',
    padding: tokens.spacingHorizontalS,
  },
  calc: { backgroundColor: tokens.colorNeutralBackground2 },
  pop: {
    display: 'flex',
    flexDirection: 'column',
    gap: tokens.spacingVerticalS,
    minWidth: '260px',
  },
  head: { display: 'inline-flex', alignItems: 'center', gap: tokens.spacingHorizontalXS },
});

function StatusChip({ line }: { line: EditLine }) {
  if (line.base_amount !== null || line.input_status === 'Provided')
    return (
      <Badge color="success" appearance="tint">
        Provided
      </Badge>
    );
  if (line.input_status === 'Requested') {
    const d = line.requested_days;
    return (
      <Badge color="warning" appearance="tint">
        {d <= 0 ? 'Requested today' : `Requested ${d} day${d === 1 ? '' : 's'} ago`}
      </Badge>
    );
  }
  return (
    <Badge color="danger" appearance="tint">
      Missing
    </Badge>
  );
}

function OverridePopover(props: {
  line: EditLine;
  rowLabel: string;
  years: number[];
  editable: boolean;
  onChange: (patch: Partial<EditLine>) => void;
}) {
  const s = useStyles();
  const { line, years, editable, onChange } = props;
  const count = Object.keys(line.year_overrides).length;
  const setYear = (y: number, v: string) => {
    const next = { ...line.year_overrides };
    if (v.trim() === '' || Number.isNaN(Number(v))) delete next[String(y)];
    else next[String(y)] = Number(v);
    onChange({ year_overrides: next });
  };
  const needsReason = count > 0 && !line.override_reason.trim();
  return (
    <Popover positioning="below" trapFocus>
      <PopoverTrigger disableButtonEnhancement>
        <Button
          size="small"
          appearance={count ? 'primary' : 'secondary'}
          aria-label={`Year overrides for ${props.rowLabel}`}
        >
          {count ? `${count} override${count === 1 ? '' : 's'}` : editable ? 'Add' : 'None'}
        </Button>
      </PopoverTrigger>
      <PopoverSurface aria-label="Year overrides">
        <div className={s.pop}>
          <Caption1>
            Growth % applied in that year instead of the line rate ({line.growth_pct}%).
          </Caption1>
          {years.slice(1).map((y) => (
            <Field key={y} label={`${y} growth %`} size="small">
              <Input
                type="number"
                size="small"
                disabled={!editable}
                value={line.year_overrides[String(y)]?.toString() ?? ''}
                placeholder={`${line.growth_pct} (default)`}
                onChange={(_, d) => setYear(y, d.value)}
              />
            </Field>
          ))}
          <Field
            label="Reason for override"
            size="small"
            required={count > 0}
            validationState={needsReason ? 'error' : 'none'}
            validationMessage={
              needsReason ? 'A reason is required when overriding a year' : undefined
            }
          >
            <Textarea
              size="small"
              disabled={!editable}
              value={line.override_reason}
              onChange={(_, d) => onChange({ override_reason: d.value })}
            />
          </Field>
        </div>
      </PopoverSurface>
    </Popover>
  );
}

/** Editable (or read-only) OCET lines grid with computed, read-only yearly columns. */
export function LinesGrid(props: {
  lines: EditLine[];
  years: number[];
  editable: boolean;
  categories: string[];
  pricingBases: string[];
  workedExample: string;
  onChange: (key: string, patch: Partial<EditLine>) => void;
  onRemove: (key: string) => void;
}) {
  const s = useStyles();
  const { lines, years, editable } = props;
  return (
    <div className={s.wrap}>
      <table className={s.table}>
        <thead>
          <tr>
            {['Category', 'Description', 'Vendor', 'Pricing basis'].map((h) => (
              <th key={h} className={s.th}>
                {h}
              </th>
            ))}
            <th className={s.th}>Base amount ({years[0]})</th>
            <th className={s.th}>
              <span className={s.head}>
                Growth %/yr
                <Tooltip content={props.workedExample} relationship="description" withArrow>
                  <span tabIndex={0} aria-label={`Growth example: ${props.workedExample}`}>
                    <Info16Regular />
                  </span>
                </Tooltip>
              </span>
            </th>
            <th className={s.th}>Year overrides</th>
            <th className={s.th}>Input owner</th>
            <th className={s.th}>Input status</th>
            {years.map((y) => (
              <th key={y} className={mergeClasses(s.th, s.num)}>
                {y}
              </th>
            ))}
            <th className={mergeClasses(s.th, s.num)}>Line total</th>
            {editable && <th className={s.th} aria-label="Actions" />}
          </tr>
        </thead>
        <tbody>
          {lines.map((l, index) => {
            const yearly = project(l, years);
            const total = yearly.reduce((a, b) => a + b, 0);
            const patch = (p: Partial<EditLine>) => props.onChange(l.key, p);
            const label = l.description || l.category;
            return (
              <tr key={l.key}>
                <td className={s.td}>
                  {editable ? (
                    <Select
                      size="small"
                      aria-label={`Category of ${label}`}
                      value={l.category}
                      onChange={(_, d) => patch({ category: d.value })}
                    >
                      {props.categories.map((c) => (
                        <option key={c}>{c}</option>
                      ))}
                    </Select>
                  ) : (
                    l.category
                  )}
                </td>
                <td className={s.td}>
                  {editable ? (
                    <Input
                      size="small"
                      aria-label={`Description of line ${index + 1} (${l.category})`}
                      value={l.description}
                      onChange={(_, d) => patch({ description: d.value })}
                    />
                  ) : (
                    l.description
                  )}
                </td>
                <td className={s.td}>
                  {editable ? (
                    <Input
                      size="small"
                      aria-label={`Vendor of ${label}`}
                      value={l.vendor}
                      onChange={(_, d) => patch({ vendor: d.value })}
                    />
                  ) : (
                    l.vendor
                  )}
                </td>
                <td className={s.td}>
                  {editable ? (
                    <Select
                      size="small"
                      aria-label={`Pricing basis of ${label}`}
                      value={l.pricing_basis}
                      onChange={(_, d) => patch({ pricing_basis: d.value })}
                    >
                      {props.pricingBases.map((c) => (
                        <option key={c}>{c}</option>
                      ))}
                    </Select>
                  ) : (
                    l.pricing_basis
                  )}
                </td>
                <td className={s.td}>
                  {editable ? (
                    <Input
                      size="small"
                      type="number"
                      min={0}
                      aria-label={`Base amount of ${label}`}
                      value={l.base_amount === null ? '' : String(l.base_amount)}
                      placeholder="Missing"
                      onChange={(_, d) =>
                        patch({
                          base_amount:
                            d.value.trim() === '' || Number.isNaN(Number(d.value))
                              ? null
                              : Number(d.value),
                        })
                      }
                    />
                  ) : l.base_amount === null ? (
                    <Caption1>Missing</Caption1>
                  ) : (
                    fmtFull(l.base_amount)
                  )}
                </td>
                <td className={s.td}>
                  {editable ? (
                    <Input
                      size="small"
                      type="number"
                      aria-label={`Growth percent per year of ${label}`}
                      value={String(l.growth_pct)}
                      onChange={(_, d) =>
                        patch({ growth_pct: d.value.trim() === '' ? 0 : Number(d.value) })
                      }
                    />
                  ) : (
                    `${l.growth_pct}%`
                  )}
                </td>
                <td className={s.td}>
                  <OverridePopover
                    line={l}
                    rowLabel={label}
                    years={years}
                    editable={editable}
                    onChange={patch}
                  />
                </td>
                <td className={s.td}>
                  {editable ? (
                    <Select
                      size="small"
                      aria-label={`Input owner role of ${label}`}
                      value={l.input_owner_role}
                      onChange={(_, d) =>
                        patch({ input_owner_role: d.value, input_owner_user_id: null })
                      }
                    >
                      {OWNER_ROLES.map((r) => (
                        <option key={r}>{r}</option>
                      ))}
                    </Select>
                  ) : (
                    l.input_owner_role
                  )}
                </td>
                <td className={s.td}>
                  <StatusChip line={l} />
                </td>
                {yearly.map((v, i) => (
                  <td key={years[i]} className={mergeClasses(s.td, s.num, s.calc)}>
                    {fmtFull(v)}
                  </td>
                ))}
                <td className={mergeClasses(s.td, s.num, s.calc)}>
                  <strong>{fmtFull(total)}</strong>
                </td>
                {editable && (
                  <td className={s.td}>
                    <Button
                      size="small"
                      appearance="subtle"
                      icon={<Delete16Regular />}
                      aria-label={`Remove line ${label}`}
                      onClick={() => props.onRemove(l.key)}
                    />
                  </td>
                )}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

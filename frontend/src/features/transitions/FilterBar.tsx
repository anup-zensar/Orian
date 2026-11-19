// Filter bar shared by the Transitions page and the Control tower (spec 8.2, 8.3). Every control reads
// and writes the URL query through useUrlFilters, so deep links and the back button work (spec 12).
import { useState } from 'react';
import {
  Button,
  Field,
  Input,
  MessageBar,
  MessageBarActions,
  MessageBarBody,
  Select,
  Switch,
  Tag,
  makeStyles,
  tokens,
} from '@fluentui/react-components';
import { Dismiss12Regular, Search20Regular } from '@fluentui/react-icons';
import type { IntakeFieldRef } from '../../api/types';
import { useReference } from '../reference/api';
import {
  useIntakeFields,
  useOptionLabel,
  useOptions,
  usePortfolios,
  useProjectTypes,
} from '../reference/options';
import { plural } from '../../lib/format';
import type { CustomFilterKey, FilterKey, UrlFilters } from './useUrlFilters';

const useStyles = makeStyles({
  bar: {
    display: 'flex',
    flexWrap: 'wrap',
    alignItems: 'flex-end',
    gap: tokens.spacingHorizontalM,
    marginBottom: tokens.spacingVerticalL,
  },
  search: { minWidth: '220px', flexGrow: 1, maxWidth: '320px' },
  select: { minWidth: '150px' },
  tags: { display: 'flex', flexWrap: 'wrap', gap: tokens.spacingHorizontalS, alignItems: 'center' },
});

type Update = (
  patch: Partial<Record<FilterKey | CustomFilterKey, string | undefined>>,
  opts?: { replace?: boolean },
) => void;

interface Props {
  filters: UrlFilters;
  update: Update;
  clear: () => void;
  /** "Only mine" switch (Transitions page). */
  showMine?: boolean;
  /** Small message when invalid URL filters were dropped (from useUrlFilters). */
  notice?: string;
}

const STATUS_OPTIONS = [
  ['Active', 'Active'],
  ['Closed', 'Closed'],
] as const;

const YES_NO = [
  ['true', 'Yes'],
  ['false', 'No'],
] as const;

/** Describes the filters that have no dropdown (they come from KPI tiles) as removable tags. */
function tileFilterTags(f: UrlFilters): { key: FilterKey; label: string }[] {
  const tags: { key: FilterKey; label: string }[] = [];
  if (f.decision_within_days)
    tags.push({
      key: 'decision_within_days',
      label: `Decision within ${plural(Number(f.decision_within_days), 'day')}`,
    });
  if (f.has_critical === 'true') tags.push({ key: 'has_critical', label: 'Has critical gaps' });
  if (f.compliance_below)
    tags.push({
      key: 'compliance_below',
      label: `Compliance readiness below ${f.compliance_below}%`,
    });
  return tags;
}

type Dropdown = (
  key: FilterKey | CustomFilterKey,
  label: string,
  options: readonly (readonly [string, string])[],
) => React.ReactElement;

/** The filter dropdown of one custom field: its option list, or Yes / No. */
function CustomFilter(props: { field: IntakeFieldRef; filters: UrlFilters; dropdown: Dropdown }) {
  const { field, filters, dropdown } = props;
  const key = field.key as CustomFilterKey;
  // A value in the URL stays selectable even if it has since been switched off.
  const options = useOptions(field.option_list ?? '', { include: filters[key] ?? null });
  const choices: readonly (readonly [string, string])[] =
    field.type === 'boolean' ? YES_NO : options.map((o) => [o.value, o.label] as const);
  return dropdown(key, field.label, choices);
}

export function FilterBar({ filters, update, clear, showMine, notice }: Props) {
  const s = useStyles();
  const ref = useReference();
  const optionLabel = useOptionLabel();
  const regions = useOptions('regions');
  const portfolios = usePortfolios();
  const projectTypes = useProjectTypes();
  // Filter dropdowns for the custom fields an Admin marked filterable (yes/no and dropdown fields).
  const customFilters = useIntakeFields().filter(
    (f) => !f.builtin && f.filterable && (f.type === 'select' || f.type === 'boolean'),
  );
  const ragOptions = ['Red', 'Amber', 'Green', 'Grey'].map(
    (rag) => [rag, rag === 'Grey' ? 'Not started' : optionLabel('rag_words', rag) || rag] as const,
  );
  const [dismissed, setDismissed] = useState<string | null>(null);
  const tags = tileFilterTags(filters);
  const hasAny = Object.keys(filters).length > 0;

  const dropdown = (
    key: FilterKey | CustomFilterKey,
    label: string,
    options: readonly (readonly [string, string])[],
  ) => (
    <Field label={label} className={s.select}>
      <Select
        value={filters[key] ?? ''}
        onChange={(_, d) => update({ [key]: d.value || undefined })}
      >
        <option value="">All</option>
        {options.map(([value, text]) => (
          <option key={value} value={value}>
            {text}
          </option>
        ))}
      </Select>
    </Field>
  );

  return (
    <>
      <div className={s.bar} role="search" aria-label="Filters">
        <Field label="Search" className={s.search}>
          <Input
            type="search"
            contentBefore={<Search20Regular />}
            placeholder="Name, id, market or OR focal"
            value={filters.q ?? ''}
            onChange={(_, d) => update({ q: d.value || undefined }, { replace: true })}
          />
        </Field>
        {dropdown(
          'portfolio',
          'Portfolio',
          portfolios.map((p) => [p.name, p.label] as const),
        )}
        {dropdown(
          'region',
          'Region',
          regions.map((r) => [r.value, r.label] as const),
        )}
        {dropdown(
          'gate',
          'Current gate',
          (ref.data?.gates ?? []).map((g) => [g.code, g.short] as const),
        )}
        {dropdown('rag', 'RAG', ragOptions)}
        {dropdown('status', 'Status', STATUS_OPTIONS)}
        {dropdown(
          'type',
          'Project type',
          projectTypes.map((t) => [t.code, t.label] as const),
        )}
        {customFilters.map((f) => (
          <CustomFilter key={f.key} field={f} filters={filters} dropdown={dropdown} />
        ))}
        {showMine && (
          <Switch
            label="Only mine"
            checked={filters.mine === 'true'}
            onChange={(_, d) => update({ mine: d.checked ? 'true' : undefined })}
          />
        )}
        <Button appearance="subtle" disabled={!hasAny} onClick={clear}>
          Clear filters
        </Button>
      </div>
      {notice && dismissed !== notice && (
        <MessageBar intent="info" role="status" style={{ marginBottom: 8 }}>
          <MessageBarBody>{notice}</MessageBarBody>
          <MessageBarActions
            containerAction={
              <Button
                appearance="transparent"
                size="small"
                aria-label="Dismiss"
                icon={<Dismiss12Regular />}
                onClick={() => setDismissed(notice)}
              />
            }
          />
        </MessageBar>
      )}
      {tags.length > 0 && (
        <div className={s.tags} aria-label="Active tile filters">
          {tags.map((t) => (
            <Tag
              key={t.key}
              dismissible
              dismissIcon={{
                'aria-label': `Remove filter: ${t.label}`,
                children: <Dismiss12Regular />,
              }}
              onClick={() => update({ [t.key]: undefined })}
            >
              {t.label}
            </Tag>
          ))}
        </div>
      )}
    </>
  );
}

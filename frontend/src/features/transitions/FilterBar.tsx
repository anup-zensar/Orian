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
import {
  ChevronDown16Regular,
  ChevronUp16Regular,
  Dismiss12Regular,
  Search20Regular,
} from '@fluentui/react-icons';
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
import { cardRadius, cardShadow } from '../../theme/orionTheme';
import {
  customFilterKey,
  type CustomFilterKey,
  type FilterKey,
  type UrlFilters,
} from './useUrlFilters';

const useStyles = makeStyles({
  // Auto-fill grid: controls share one baseline and wrap with the width of the content.
  bar: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(min(100%, 150px), 1fr))',
    alignItems: 'end',
    gap: tokens.spacingHorizontalM,
    rowGap: tokens.spacingVerticalS,
    marginBottom: tokens.spacingVerticalL,
    minWidth: 0,
    padding: tokens.spacingVerticalM,
    paddingInline: tokens.spacingHorizontalL,
    border: `1px solid ${tokens.colorNeutralStroke2}`,
    borderRadius: cardRadius,
    backgroundColor: tokens.colorNeutralBackground1,
    boxShadow: cardShadow,
  },
  cellEnd: { display: 'flex', alignItems: 'center', minHeight: '32px', minWidth: 0 },
  // More filters + Clear filters share one cell (two columns wide) so Clear never sits alone on a row.
  actions: {
    display: 'flex',
    alignItems: 'center',
    minHeight: '32px',
    '@media (min-width: 700px)': { gridColumn: 'span 2' },
  },
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
  if (f.has_critical === 'true')
    tags.push({ key: 'has_critical', label: 'Has critical gaps/risks' });
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
  const key = customFilterKey(field.key);
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
  // Less-used filters sit behind "More filters"; it opens by itself when the URL sets one of them.
  const moreSet = Object.keys(filters).filter(
    (k) => k === 'region' || k === 'status' || k === 'type' || k.startsWith('cf_'),
  ).length;
  const [more, setMore] = useState<boolean | null>(null);
  const moreOpen = more ?? moreSet > 0;

  const dropdown = (
    key: FilterKey | CustomFilterKey,
    label: string,
    options: readonly (readonly [string, string])[],
  ) => (
    <Field label={label}>
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
        <Field label="Search">
          <Input
            type="search"
            contentBefore={<Search20Regular />}
            placeholder="Name, ID, project ID, focal"
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
          'gate',
          'Current gate',
          (ref.data?.gates ?? []).map((g) => [g.code, g.short] as const),
        )}
        {dropdown('rag', 'RAG', ragOptions)}
        {showMine && (
          <div className={s.cellEnd}>
            <Switch
              label="Only mine"
              checked={filters.mine === 'true'}
              onChange={(_, d) => update({ mine: d.checked ? 'true' : undefined })}
            />
          </div>
        )}
        <div className={s.actions}>
          <Button
            appearance="subtle"
            aria-expanded={moreOpen}
            icon={moreOpen ? <ChevronUp16Regular /> : <ChevronDown16Regular />}
            iconPosition="after"
            onClick={() => setMore(!moreOpen)}
          >
            More filters{moreSet > 0 ? ` (${moreSet})` : ''}
          </Button>
          <Button appearance="subtle" disabled={!hasAny} onClick={clear}>
            Clear filters
          </Button>
        </div>
        {moreOpen && (
          <>
            {dropdown(
              'region',
              'Region',
              regions.map((r) => [r.value, r.label] as const),
            )}
            {dropdown('status', 'Status', STATUS_OPTIONS)}
            {dropdown(
              'type',
              'Project type',
              projectTypes.map((t) => [t.code, t.label] as const),
            )}
            {customFilters.map((f) => (
              <CustomFilter key={f.key} field={f} filters={filters} dropdown={dropdown} />
            ))}
          </>
        )}
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

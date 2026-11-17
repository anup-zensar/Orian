// Filter bar shared by the Transitions page and the Control tower (spec 8.2, 8.3). Every control reads
// and writes the URL query through useUrlFilters, so deep links and the back button work (spec 12).
import {
  Button,
  Caption1,
  Field,
  Input,
  Select,
  Switch,
  Tag,
  makeStyles,
  tokens,
} from '@fluentui/react-components';
import { Dismiss12Regular, Search20Regular } from '@fluentui/react-icons';
import { useReference } from '../reference/api';
import { plural } from '../../lib/format';
import type { FilterKey, UrlFilters } from './useUrlFilters';

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
  patch: Partial<Record<FilterKey, string | undefined>>,
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

const RAG_OPTIONS = [
  ['Red', 'Red'],
  ['Amber', 'Amber'],
  ['Green', 'Green'],
  ['Grey', 'Not started'],
] as const;

const STATUS_OPTIONS = [
  ['Active', 'Active'],
  ['Closed', 'Closed'],
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

export function FilterBar({ filters, update, clear, showMine, notice }: Props) {
  const s = useStyles();
  const ref = useReference();
  const tags = tileFilterTags(filters);
  const hasAny = Object.keys(filters).length > 0;

  const dropdown = (
    key: FilterKey,
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
          (ref.data?.portfolios ?? []).map((p) => [p, p] as const),
        )}
        {dropdown(
          'region',
          'Region',
          (ref.data?.regions ?? []).map((r) => [r, r] as const),
        )}
        {dropdown(
          'gate',
          'Current gate',
          (ref.data?.gates ?? []).map((g) => [g.code, g.short] as const),
        )}
        {dropdown('rag', 'RAG', RAG_OPTIONS)}
        {dropdown('status', 'Status', STATUS_OPTIONS)}
        {dropdown(
          'type',
          'Project type',
          (ref.data?.project_types ?? []).map((t) => [t.code, t.code] as const),
        )}
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
      {notice && (
        <Caption1 role="status" style={{ display: 'block', marginBottom: 8 }}>
          {notice}
        </Caption1>
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

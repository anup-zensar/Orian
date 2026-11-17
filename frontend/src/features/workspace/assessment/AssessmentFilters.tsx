import { useEffect, useState } from 'react';
import {
  Button,
  Field,
  Input,
  Select,
  Switch,
  makeStyles,
  tokens,
} from '@fluentui/react-components';
import { Search20Regular } from '@fluentui/react-icons';
import { useReference } from '../../reference/api';
import { useUsers } from '../../users/api';
import type { AssessmentFilterValues } from './useAssessmentFilters';

const useStyles = makeStyles({
  bar: {
    display: 'flex',
    flexWrap: 'wrap',
    alignItems: 'flex-end',
    gap: tokens.spacingHorizontalM,
    marginBottom: tokens.spacingVerticalM,
  },
  select: { minWidth: '140px' },
  search: { minWidth: '220px', flexGrow: 1, maxWidth: '320px' },
});

type Update = (
  patch: Partial<Record<keyof AssessmentFilterValues, string | boolean | undefined>>,
  replace?: boolean,
) => void;

const SOURCES: [string, string][] = [
  ['FRAMEWORK', 'Framework'],
  ['AI_PLAYBOOK', 'AI playbook'],
  ['PORTFOLIO', 'Portfolio'],
  ['COMMON', 'Common'],
];

export function AssessmentFilters(props: {
  values: AssessmentFilterValues;
  update: Update;
  clear: () => void;
  activeCount: number;
  hasAiPlaybook: boolean;
}) {
  const s = useStyles();
  const { values, update } = props;
  const ref = useReference();
  const users = useUsers();
  // draft is the text being typed; null = show the URL value (so back/clear stay in sync)
  const [draft, setDraft] = useState<string | null>(null);
  const search = draft ?? values.q;

  // debounce typing into the URL
  useEffect(() => {
    if (draft === null) return;
    const t = window.setTimeout(() => {
      update({ q: draft || undefined }, true);
      setDraft(null);
    }, 250);
    return () => window.clearTimeout(t);
  }, [draft, update]);

  const statuses = Array.from(new Set(Object.values(ref.data?.item_statuses ?? {}).flat()));

  return (
    <div className={s.bar} role="search" aria-label="Assessment filters">
      <Field label="Search" className={s.search}>
        <Input
          type="search"
          contentBefore={<Search20Regular />}
          placeholder="Id, title, description or owner"
          value={search}
          onChange={(_, d) => setDraft(d.value)}
        />
      </Field>
      <Field label="Gate" className={s.select}>
        <Select value={values.gate} onChange={(_, d) => update({ gate: d.value || undefined })}>
          <option value="">Current gate and earlier</option>
          {(ref.data?.gates ?? []).map((g) => (
            <option key={g.code} value={g.code}>
              Up to {g.short}
            </option>
          ))}
          <option value="all">All gates</option>
        </Select>
      </Field>
      <Field label="Lens" className={s.select}>
        <Select value={values.lens} onChange={(_, d) => update({ lens: d.value || undefined })}>
          <option value="">All</option>
          {(ref.data?.lenses ?? []).map((l) => (
            <option key={l.code} value={l.code}>
              {l.code}
            </option>
          ))}
        </Select>
      </Field>
      <Field label="Source" className={s.select}>
        <Select value={values.source} onChange={(_, d) => update({ source: d.value || undefined })}>
          <option value="">All</option>
          {SOURCES.filter(([k]) => props.hasAiPlaybook || k !== 'AI_PLAYBOOK').map(([k, label]) => (
            <option key={k} value={k}>
              {label}
            </option>
          ))}
        </Select>
      </Field>
      <Field label="Status" className={s.select}>
        <Select value={values.status} onChange={(_, d) => update({ status: d.value || undefined })}>
          <option value="">All</option>
          {statuses.map((st) => (
            <option key={st} value={st}>
              {st}
            </option>
          ))}
        </Select>
      </Field>
      <Field label="Owner" className={s.select}>
        <Select value={values.owner} onChange={(_, d) => update({ owner: d.value || undefined })}>
          <option value="">All</option>
          {(users.data ?? []).map((u) => (
            <option key={u.id} value={u.id}>
              {u.name}
            </option>
          ))}
        </Select>
      </Field>
      <Switch
        label="Only my items"
        checked={values.mine}
        onChange={(_, d) => update({ mine: d.checked })}
      />
      <Switch
        label="Show excluded items"
        checked={values.excluded}
        onChange={(_, d) => update({ excluded: d.checked })}
      />
      {props.activeCount > 0 && (
        <Button appearance="subtle" onClick={props.clear}>
          Clear filters ({props.activeCount})
        </Button>
      )}
    </div>
  );
}

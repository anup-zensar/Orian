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
import { ChevronDown20Regular, ChevronUp20Regular, Search20Regular } from '@fluentui/react-icons';
import { FormGrid } from '../../../components/layout/FormGrid';
import { cardRadius } from '../../../theme/orionTheme';
import { useReference } from '../../reference/api';
import { useUsers } from '../../users/api';
import type { AssessmentFilterValues } from './useAssessmentFilters';

const useStyles = makeStyles({
  bar: {
    display: 'flex',
    flexDirection: 'column',
    gap: tokens.spacingVerticalS,
    marginBottom: tokens.spacingVerticalM,
    padding: tokens.spacingVerticalM,
    backgroundColor: tokens.colorNeutralBackground1,
    border: `1px solid ${tokens.colorNeutralStroke2}`,
    borderRadius: cardRadius,
  },
  controls: { alignItems: 'end' },
  switchCell: { display: 'flex', alignItems: 'center', minHeight: '32px', minWidth: 0 },
  footer: {
    display: 'flex',
    flexWrap: 'wrap',
    alignItems: 'center',
    gap: tokens.spacingHorizontalM,
  },
});

type Update = (
  patch: Partial<Record<keyof AssessmentFilterValues, string | boolean | undefined>>,
  replace?: boolean,
) => void;

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
  const hasMore = !!(values.source || values.owner || values.excluded);
  const [moreToggled, setMoreToggled] = useState(false);
  // opens by itself when a hidden filter is set (deep link, the 'view' banner link)
  const showMore = moreToggled || hasMore;
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

  // Checklists an item can come from; the tier-filtered one (AI playbook) only when the transition has tiering.
  const checklists = (ref.data?.checklists ?? []).filter(
    (c) => c.active !== false && (props.hasAiPlaybook || !c.tier_filtered),
  );
  const statuses = Array.from(new Set(Object.values(ref.data?.item_statuses ?? {}).flat()));

  const gate = (
    <Field label="Gate">
      <Select value={values.gate} onChange={(_, d) => update({ gate: d.value || undefined })}>
        <option value="">Current gate and earlier</option>
        {(ref.data?.gates ?? []).map((g) => (
          <option key={g.code} value={g.code}>
            Up to {g.short}
          </option>
        ))}
        <option value="all">All gates (incl. upcoming)</option>
      </Select>
    </Field>
  );

  return (
    <div className={s.bar} role="search" aria-label="Assessment filters">
      <FormGrid minColWidth={180} className={s.controls}>
        <Field label="Search">
          <Input
            type="search"
            contentBefore={<Search20Regular />}
            placeholder="Id, title, description or owner"
            value={search}
            onChange={(_, d) => setDraft(d.value)}
          />
        </Field>
        <Field label="Lens">
          <Select value={values.lens} onChange={(_, d) => update({ lens: d.value || undefined })}>
            <option value="">All</option>
            {(ref.data?.lenses ?? []).map((l) => (
              <option key={l.code} value={l.code}>
                {l.code}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Status">
          <Select
            value={values.status}
            onChange={(_, d) => update({ status: d.value || undefined })}
          >
            <option value="">All</option>
            {statuses.map((st) => (
              <option key={st} value={st}>
                {st}
              </option>
            ))}
          </Select>
        </Field>
        {gate}
        <div className={s.switchCell}>
          <Switch
            label="Only my items"
            checked={values.mine}
            onChange={(_, d) => update({ mine: d.checked })}
          />
        </div>
      </FormGrid>
      {showMore && (
        <FormGrid minColWidth={180} className={s.controls}>
          <Field label="Source">
            <Select
              value={values.source}
              onChange={(_, d) => update({ source: d.value || undefined })}
            >
              <option value="">All</option>
              {checklists.map((c) => (
                <option key={c.code} value={c.code}>
                  {c.label}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Owner">
            <Select
              value={values.owner}
              onChange={(_, d) => update({ owner: d.value || undefined })}
            >
              <option value="">All</option>
              {(users.data ?? []).map((u) => (
                <option key={u.id} value={u.id}>
                  {u.name}
                </option>
              ))}
            </Select>
          </Field>
          <div className={s.switchCell}>
            <Switch
              label="Show excluded items"
              checked={values.excluded}
              onChange={(_, d) => update({ excluded: d.checked })}
            />
          </div>
        </FormGrid>
      )}
      <div className={s.footer}>
        <Button
          appearance="subtle"
          size="small"
          aria-expanded={showMore}
          icon={showMore ? <ChevronUp20Regular /> : <ChevronDown20Regular />}
          onClick={() => setMoreToggled(!showMore)}
        >
          More filters
        </Button>
        {props.activeCount > 0 && (
          <Button appearance="subtle" size="small" onClick={props.clear}>
            Clear filters ({props.activeCount})
          </Button>
        )}
      </div>
    </div>
  );
}

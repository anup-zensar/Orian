import { useEffect, useState } from 'react';
import {
  Badge,
  Button,
  Field,
  Input,
  Select,
  Switch,
  makeStyles,
  tokens,
} from '@fluentui/react-components';
import { ErrorState } from '../../../components/ErrorState';
import { LoadingState } from '../../../components/LoadingState';
import { SectionCard } from '../../../components/SectionCard';
import { useReference } from '../../reference/api';
import { LENSES, useGoldenSet, usePutGoldenSet, type GoldenSet } from '../api';
import { useSuccessToast } from '../useSavedToast';

interface Row {
  key: string;
  id: string | null;
  title: string;
  gate: string;
  owner_role_hint: string;
  lens: (typeof LENSES)[number];
  mandatory: boolean;
  active: boolean; // false = already deactivated on the server
  removed: boolean; // marked for deactivation on save
}

const useStyles = makeStyles({
  bar: { display: 'flex', gap: tokens.spacingHorizontalM, alignItems: 'end', flexWrap: 'wrap' },
  list: {
    listStyleType: 'none',
    margin: 0,
    padding: 0,
    display: 'flex',
    flexDirection: 'column',
    gap: tokens.spacingVerticalM,
  },
  rowCard: {
    display: 'flex',
    flexDirection: 'column',
    gap: tokens.spacingVerticalS,
    minWidth: 0,
    padding: tokens.spacingHorizontalM,
    border: `1px solid ${tokens.colorNeutralStroke2}`,
    borderRadius: tokens.borderRadiusLarge,
    backgroundColor: tokens.colorNeutralBackground1,
  },
  rowHead: { display: 'flex', alignItems: 'center', gap: tokens.spacingHorizontalS },
  id: { color: tokens.colorNeutralForeground3, fontSize: tokens.fontSizeBase200 },
  titleInput: { width: '100%' },
  fields: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 130px), 1fr))',
    columnGap: tokens.spacingHorizontalM,
    rowGap: tokens.spacingVerticalS,
    alignItems: 'end',
  },
  action: { display: 'flex', alignItems: 'end', paddingBottom: tokens.spacingVerticalXS },
  removed: { opacity: 0.5, textDecorationLine: 'line-through' },
});

const toRows = (gs: GoldenSet): Row[] =>
  gs.items.map((i) => ({
    key: i.id,
    id: i.id,
    title: i.title,
    gate: i.gate,
    owner_role_hint: i.owner_role_hint,
    lens: (LENSES as readonly string[]).includes(i.lens) ? (i.lens as Row['lens']) : 'Business',
    mandatory: i.mandatory,
    active: i.active,
    removed: false,
  }));

function Editor(props: { data: GoldenSet; portfolio: string; onDirty: (dirty: boolean) => void }) {
  const { data, portfolio, onDirty } = props;
  const s = useStyles();
  const { data: ref } = useReference();
  const [rows, setRows] = useState<Row[]>(() => toRows(data));
  const [seq, setSeq] = useState(0);
  const save = usePutGoldenSet();
  const ok = useSuccessToast();
  const gates = ref?.gates ?? [];
  const patch = (key: string, p: Partial<Row>) =>
    setRows((rs) => rs.map((r) => (r.key === key ? { ...r, ...p } : r)));

  const dirty = JSON.stringify(rows) !== JSON.stringify(toRows(data));
  useEffect(() => {
    onDirty(dirty);
    return () => onDirty(false); // an unmounted editor holds no unsaved edits
  }, [dirty, onDirty]);

  const add = () => {
    setRows((rs) => [
      ...rs,
      {
        key: `new-${seq}`,
        id: null,
        title: '',
        gate: gates[0]?.code ?? '',
        owner_role_hint: '',
        lens: 'Business',
        mandatory: true,
        active: true,
        removed: false,
      },
    ]);
    setSeq((n) => n + 1);
  };
  const remove = (r: Row) =>
    r.id === null
      ? setRows((rs) => rs.filter((x) => x.key !== r.key))
      : patch(r.key, { removed: !r.removed });

  const submit = () =>
    save.mutate(
      {
        portfolio,
        body: {
          items: rows
            .filter((r) => r.active && !r.removed)
            .map((r) => ({
              id: r.id,
              title: r.title.trim(),
              gate: r.gate,
              owner_role_hint: r.owner_role_hint,
              lens: r.lens,
              mandatory: r.mandatory,
            })),
        },
      },
      { onSuccess: () => ok('Saved - applies to new transitions') },
    );

  const invalid = rows.some((r) => r.active && !r.removed && !r.title.trim());

  return (
    <>
      {rows.length === 0 && (
        <p>This portfolio has no golden-set items yet. Add the first one below.</p>
      )}
      {rows.length > 0 && (
        <ul className={s.list} aria-label="Golden set">
          {rows.map((r) => {
            const locked = !r.active || r.removed;
            return (
              <li key={r.key} className={s.rowCard}>
                <div className={s.rowHead}>
                  <span className={locked ? s.removed : s.id}>{r.id ?? 'new'}</span>
                  {!r.active && (
                    <Badge appearance="tint" color="subtle">
                      deactivated
                    </Badge>
                  )}
                </div>
                <Input
                  aria-label="Title"
                  className={s.titleInput}
                  value={r.title}
                  disabled={locked}
                  onChange={(_, d) => patch(r.key, { title: d.value })}
                />
                <div className={s.fields}>
                  <Field label="Gate">
                    <Select
                      aria-label="Gate"
                      value={r.gate}
                      disabled={locked}
                      onChange={(_, d) => patch(r.key, { gate: d.value })}
                    >
                      {gates.map((g) => (
                        <option key={g.code} value={g.code}>
                          {g.short}
                        </option>
                      ))}
                      {!gates.some((g) => g.code === r.gate) && (
                        <option value={r.gate}>{r.gate}</option>
                      )}
                    </Select>
                  </Field>
                  <Field label="Area">
                    <Select
                      aria-label="Area"
                      value={r.lens}
                      disabled={locked}
                      onChange={(_, d) => patch(r.key, { lens: d.value as Row['lens'] })}
                    >
                      {LENSES.map((l) => (
                        <option key={l}>{l}</option>
                      ))}
                    </Select>
                  </Field>
                  <Field label="Owner role">
                    <Input
                      aria-label="Owner role"
                      value={r.owner_role_hint}
                      disabled={locked}
                      onChange={(_, d) => patch(r.key, { owner_role_hint: d.value })}
                    />
                  </Field>
                  <Field label="Mandatory">
                    <Switch
                      aria-label="Mandatory"
                      checked={r.mandatory}
                      disabled={locked}
                      onChange={(_, d) => patch(r.key, { mandatory: d.checked })}
                    />
                  </Field>
                  <div className={s.action}>
                    {r.active ? (
                      <Button size="small" onClick={() => remove(r)}>
                        {r.removed ? 'Undo' : 'Remove'}
                      </Button>
                    ) : (
                      <Button size="small" onClick={() => patch(r.key, { active: true })}>
                        Restore
                      </Button>
                    )}
                  </div>
                </div>
              </li>
            );
          })}
        </ul>
      )}
      {save.isError && <ErrorState error={save.error} />}
      <div className={s.bar}>
        <Button onClick={add}>Add golden-set item</Button>
        <Button
          appearance="primary"
          onClick={submit}
          disabled={!dirty || save.isPending || invalid}
        >
          {save.isPending ? 'Saving...' : 'Save golden set'}
        </Button>
      </div>
    </>
  );
}

/** The golden set of one portfolio: the extra items every transition of that portfolio gets. */
export function GoldenSetPanel(props: {
  portfolio: string;
  title: string;
  onDirty: (dirty: boolean) => void;
}) {
  const q = useGoldenSet(props.portfolio);
  return (
    <SectionCard title={`Golden set: ${props.title}`}>
      {q.isLoading ? (
        <LoadingState rows={4} />
      ) : q.isError ? (
        <ErrorState error={q.error} onRetry={() => void q.refetch()} />
      ) : q.data ? (
        <Editor
          key={`${props.portfolio}-${q.dataUpdatedAt}`}
          data={q.data}
          portfolio={props.portfolio}
          onDirty={props.onDirty}
        />
      ) : null}
    </SectionCard>
  );
}

import { useState } from 'react';
import {
  Badge,
  Button,
  Field,
  Input,
  Select,
  Switch,
  Table,
  TableBody,
  TableCell,
  TableHeader,
  TableHeaderCell,
  TableRow,
  makeStyles,
  tokens,
} from '@fluentui/react-components';
import { ErrorState } from '../../components/ErrorState';
import { LoadingState } from '../../components/LoadingState';
import { SectionCard } from '../../components/SectionCard';
import { useApiErrorToast } from '../../hooks/useApiErrorToast';
import { useReference } from '../reference/api';
import { LENSES, useGoldenSet, usePutGoldenSet, type GoldenSet } from './api';
import { useSuccessToast } from './useSavedToast';

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
  scroll: { overflowX: 'auto' },
  titleInput: { minWidth: '130px', width: '100%' },
  roleInput: { minWidth: '100px', width: '100%' },
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

function Editor({ data, portfolio }: { data: GoldenSet; portfolio: string }) {
  const s = useStyles();
  const { data: ref } = useReference();
  const [rows, setRows] = useState<Row[]>(() => toRows(data));
  const [seq, setSeq] = useState(0);
  const save = usePutGoldenSet();
  const showError = useApiErrorToast();
  const ok = useSuccessToast();
  const gates = ref?.gates ?? [];
  const patch = (key: string, p: Partial<Row>) =>
    setRows((rs) => rs.map((r) => (r.key === key ? { ...r, ...p } : r)));

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
      { onSuccess: () => ok(`${portfolio} golden set saved`), onError: showError },
    );

  const invalid = rows.some((r) => r.active && !r.removed && !r.title.trim());

  return (
    <>
      <div className={s.scroll}>
        <Table
          aria-label="Golden set"
          size="small"
          style={{ tableLayout: 'auto', minWidth: '100%' }}
        >
          <TableHeader>
            <TableRow>
              <TableHeaderCell style={{ width: 96 }}>Id</TableHeaderCell>
              <TableHeaderCell>Title</TableHeaderCell>
              <TableHeaderCell style={{ width: 120 }}>Gate</TableHeaderCell>
              <TableHeaderCell style={{ width: 170 }}>Owner role</TableHeaderCell>
              <TableHeaderCell style={{ width: 125 }}>Lens</TableHeaderCell>
              <TableHeaderCell style={{ minWidth: 0, width: 90 }}>Mandatory</TableHeaderCell>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((r) => {
              const locked = !r.active || r.removed;
              return (
                <TableRow key={r.key}>
                  <TableCell>
                    <span className={locked ? s.removed : undefined}>{r.id ?? 'new'}</span>
                    {!r.active && (
                      <Badge appearance="tint" color="subtle" style={{ marginLeft: 6 }}>
                        deactivated
                      </Badge>
                    )}
                    <div>
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
                  </TableCell>
                  <TableCell>
                    <Input
                      aria-label="Title"
                      className={s.titleInput}
                      value={r.title}
                      disabled={locked}
                      onChange={(_, d) => patch(r.key, { title: d.value })}
                    />
                  </TableCell>
                  <TableCell>
                    <Select
                      aria-label="Gate"
                      style={{ minWidth: 100 }}
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
                  </TableCell>
                  <TableCell>
                    <Input
                      aria-label="Owner role"
                      className={s.roleInput}
                      value={r.owner_role_hint}
                      disabled={locked}
                      onChange={(_, d) => patch(r.key, { owner_role_hint: d.value })}
                    />
                  </TableCell>
                  <TableCell>
                    <Select
                      aria-label="Lens"
                      style={{ minWidth: 100 }}
                      value={r.lens}
                      disabled={locked}
                      onChange={(_, d) => patch(r.key, { lens: d.value as Row['lens'] })}
                    >
                      {LENSES.map((l) => (
                        <option key={l}>{l}</option>
                      ))}
                    </Select>
                  </TableCell>
                  <TableCell style={{ minWidth: 0 }}>
                    <Switch
                      aria-label="Mandatory"
                      checked={r.mandatory}
                      disabled={locked}
                      onChange={(_, d) => patch(r.key, { mandatory: d.checked })}
                    />
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </div>
      <div className={s.bar}>
        <Button onClick={add}>Add row</Button>
        <Button appearance="primary" onClick={submit} disabled={save.isPending || invalid}>
          {save.isPending ? 'Saving...' : 'Save golden set'}
        </Button>
      </div>
    </>
  );
}

export function GoldenSetSection() {
  const s = useStyles();
  const { data: ref } = useReference();
  const [picked, setPicked] = useState('');
  const portfolio = picked || ref?.portfolios[0] || '';
  const q = useGoldenSet(portfolio);

  return (
    <SectionCard title="Portfolio golden sets">
      <div className={s.bar}>
        <Field label="Portfolio">
          <Select value={portfolio} onChange={(_, d) => setPicked(d.value)}>
            {(ref?.portfolios ?? []).map((p) => (
              <option key={p}>{p}</option>
            ))}
          </Select>
        </Field>
      </div>
      {!portfolio || q.isLoading ? (
        <LoadingState rows={4} />
      ) : q.isError ? (
        <ErrorState error={q.error} onRetry={() => void q.refetch()} />
      ) : q.data ? (
        <Editor key={`${portfolio}-${q.dataUpdatedAt}`} data={q.data} portfolio={portfolio} />
      ) : null}
    </SectionCard>
  );
}

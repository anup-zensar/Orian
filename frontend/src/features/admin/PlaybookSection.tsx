import { useState } from 'react';
import {
  Badge,
  Button,
  Checkbox,
  Dialog,
  DialogActions,
  DialogBody,
  DialogContent,
  DialogSurface,
  DialogTitle,
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
  Textarea,
  makeStyles,
  tokens,
} from '@fluentui/react-components';
import { EmptyState } from '../../components/EmptyState';
import { ErrorState } from '../../components/ErrorState';
import { LensChip } from '../../components/LensChip';
import { LoadingState } from '../../components/LoadingState';
import { SectionCard } from '../../components/SectionCard';
import { useApiErrorToast } from '../../hooks/useApiErrorToast';
import { useReference } from '../reference/api';
import type { Lens } from '../../theme/tokens';
import {
  LENSES,
  SOURCES,
  usePlaybookItems,
  useUpdatePlaybookItem,
  type PlaybookFilters,
  type PlaybookItem,
} from './api';
import { useSuccessToast } from './useSavedToast';

const useStyles = makeStyles({
  filters: { display: 'flex', gap: tokens.spacingHorizontalM, flexWrap: 'wrap', alignItems: 'end' },
  grow: { flexGrow: 1, minWidth: '200px' },
  scroll: { overflowX: 'auto' },
  form: { display: 'flex', flexDirection: 'column', gap: tokens.spacingVerticalM },
  tiers: { display: 'flex', gap: tokens.spacingHorizontalM },
});

function EditDialog({ item, onClose }: { item: PlaybookItem; onClose: () => void }) {
  const s = useStyles();
  const { data: ref } = useReference();
  const update = useUpdatePlaybookItem();
  const showError = useApiErrorToast();
  const ok = useSuccessToast();
  const [title, setTitle] = useState(item.title);
  const [description, setDescription] = useState(item.description);
  const [gate, setGate] = useState(item.gate);
  const [lens, setLens] = useState(item.lens);
  const [tiers, setTiers] = useState<number[]>(item.applicable_tiers);
  const [mandatory, setMandatory] = useState(item.mandatory);
  const [active, setActive] = useState(item.active);

  const save = () =>
    update.mutate(
      {
        id: item.id,
        body: {
          title: title.trim(),
          description,
          gate,
          lens: lens as Lens,
          applicable_tiers: tiers,
          mandatory,
          active,
        },
      },
      {
        onSuccess: () => {
          ok(`${item.id} saved`);
          onClose();
        },
        onError: showError,
      },
    );

  return (
    <Dialog open onOpenChange={(_, d) => !d.open && onClose()}>
      <DialogSurface>
        <DialogBody>
          <DialogTitle>Edit {item.id}</DialogTitle>
          <DialogContent className={s.form}>
            <Field label="Title" required>
              <Input value={title} onChange={(_, d) => setTitle(d.value)} />
            </Field>
            <Field label="Description">
              <Textarea value={description} rows={3} onChange={(_, d) => setDescription(d.value)} />
            </Field>
            <Field label="Gate">
              <Select value={gate} onChange={(_, d) => setGate(d.value)}>
                {(ref?.gates ?? []).map((g) => (
                  <option key={g.code} value={g.code}>
                    {g.label}
                  </option>
                ))}
                {!ref?.gates.some((g) => g.code === gate) && <option value={gate}>{gate}</option>}
              </Select>
            </Field>
            <Field
              label="Lens"
              hint={item.lens_is_suggested ? 'Lens suggested – confirm by saving' : undefined}
            >
              <Select value={lens} onChange={(_, d) => setLens(d.value)}>
                {LENSES.map((l) => (
                  <option key={l}>{l}</option>
                ))}
              </Select>
            </Field>
            <Field label="Applicable tiers">
              <div className={s.tiers}>
                {[1, 2, 3, 4].map((t) => (
                  <Checkbox
                    key={t}
                    label={`Tier ${t}`}
                    checked={tiers.includes(t)}
                    onChange={(_, d) =>
                      setTiers((cur) =>
                        d.checked ? [...cur, t].sort((a, b) => a - b) : cur.filter((x) => x !== t),
                      )
                    }
                  />
                ))}
              </div>
            </Field>
            <Switch
              label="Mandatory"
              checked={mandatory}
              onChange={(_, d) => setMandatory(d.checked)}
            />
            <Switch label="Active" checked={active} onChange={(_, d) => setActive(d.checked)} />
          </DialogContent>
          <DialogActions>
            <Button appearance="secondary" onClick={onClose}>
              Cancel
            </Button>
            <Button
              appearance="primary"
              onClick={save}
              disabled={update.isPending || !title.trim()}
            >
              {update.isPending ? 'Saving...' : 'Save'}
            </Button>
          </DialogActions>
        </DialogBody>
      </DialogSurface>
    </Dialog>
  );
}

export function PlaybookSection() {
  const s = useStyles();
  const { data: ref } = useReference();
  const [filters, setFilters] = useState<PlaybookFilters>({
    q: '',
    source: '',
    gate: '',
    lens: '',
    active: '',
  });
  const [editing, setEditing] = useState<PlaybookItem | null>(null);
  const items = usePlaybookItems(filters);
  const set = (k: keyof PlaybookFilters) => (_: unknown, d: { value: string }) =>
    setFilters((f) => ({ ...f, [k]: d.value }));

  return (
    <SectionCard title="Playbook library">
      <div className={s.filters}>
        <Field label="Search" className={s.grow}>
          <Input value={filters.q} onChange={set('q')} placeholder="Id, title or description" />
        </Field>
        <Field label="Source">
          <Select value={filters.source} onChange={set('source')}>
            <option value="">All</option>
            {SOURCES.map((x) => (
              <option key={x}>{x}</option>
            ))}
          </Select>
        </Field>
        <Field label="Gate">
          <Select value={filters.gate} onChange={set('gate')}>
            <option value="">All</option>
            {(ref?.gates ?? []).map((g) => (
              <option key={g.code} value={g.code}>
                {g.short}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Lens">
          <Select value={filters.lens} onChange={set('lens')}>
            <option value="">All</option>
            {LENSES.map((x) => (
              <option key={x}>{x}</option>
            ))}
          </Select>
        </Field>
        <Field label="Active">
          <Select value={filters.active} onChange={set('active')}>
            <option value="">All</option>
            <option value="true">Active</option>
            <option value="false">Inactive</option>
          </Select>
        </Field>
      </div>
      {items.isLoading ? (
        <LoadingState rows={6} />
      ) : items.isError ? (
        <ErrorState error={items.error} onRetry={() => void items.refetch()} />
      ) : !items.data?.length ? (
        <EmptyState message="No playbook items match these filters." />
      ) : (
        <div className={s.scroll}>
          <Table
            aria-label="Playbook items"
            size="small"
            style={{ tableLayout: 'auto', minWidth: '100%' }}
          >
            <TableHeader>
              <TableRow>
                <TableHeaderCell>Id</TableHeaderCell>
                <TableHeaderCell style={{ minWidth: 220 }}>Title</TableHeaderCell>
                <TableHeaderCell>Source</TableHeaderCell>
                <TableHeaderCell>Gate</TableHeaderCell>
                <TableHeaderCell>Lens</TableHeaderCell>
                <TableHeaderCell>Tiers</TableHeaderCell>
                <TableHeaderCell>Mandatory</TableHeaderCell>
                <TableHeaderCell>Active</TableHeaderCell>
                <TableHeaderCell />
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.data.map((it) => (
                <TableRow key={it.id}>
                  <TableCell>{it.id}</TableCell>
                  <TableCell style={{ minWidth: 220 }}>{it.title}</TableCell>
                  <TableCell title={it.source_label || it.source}>{it.source}</TableCell>
                  <TableCell>{it.gate}</TableCell>
                  <TableCell>
                    <LensChip lens={it.lens as Lens} />
                    {it.lens_is_suggested && (
                      <Badge color="warning" appearance="tint" style={{ marginLeft: 6 }}>
                        lens suggested – confirm
                      </Badge>
                    )}
                  </TableCell>
                  <TableCell>
                    {it.applicable_tiers.length ? it.applicable_tiers.join(', ') : '-'}
                  </TableCell>
                  <TableCell>{it.mandatory ? 'Yes' : 'No'}</TableCell>
                  <TableCell>{it.active ? 'Yes' : 'No'}</TableCell>
                  <TableCell>
                    <Button size="small" onClick={() => setEditing(it)}>
                      Edit
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
      {editing && <EditDialog key={editing.id} item={editing} onClose={() => setEditing(null)} />}
    </SectionCard>
  );
}

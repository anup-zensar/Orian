import { useState } from 'react';
import {
  Badge,
  Button,
  Field,
  Input,
  Select,
  Table,
  TableBody,
  TableCell,
  TableHeader,
  TableHeaderCell,
  TableRow,
  makeStyles,
  tokens,
} from '@fluentui/react-components';
import { EmptyState } from '../../../components/EmptyState';
import { ErrorState } from '../../../components/ErrorState';
import { LensChip } from '../../../components/LensChip';
import { LoadingState } from '../../../components/LoadingState';
import { SectionCard } from '../../../components/SectionCard';
import type { Lens } from '../../../theme/tokens';
import { useReference } from '../../reference/api';
import { LENSES, usePlaybookItems, type PlaybookFilters, type PlaybookItem } from '../api';
import { useChecklists } from '../catalogApi';
import { ItemDialog } from './ItemDialog';

const PAGE = 100; // rows shown before "Show more"; the library has hundreds of items

const useStyles = makeStyles({
  filters: { display: 'flex', gap: tokens.spacingHorizontalM, flexWrap: 'wrap', alignItems: 'end' },
  grow: { flexGrow: 1, minWidth: '200px' },
  scroll: { overflowX: 'auto' },
});

/** Browse, search and edit the library items; New item adds one to any checklist. */
export function ItemsPanel() {
  const s = useStyles();
  const { data: ref } = useReference();
  const checklists = useChecklists();
  const [filters, setFilters] = useState<PlaybookFilters>({
    q: '',
    source: '',
    gate: '',
    lens: '',
    active: '',
  });
  const [dialog, setDialog] = useState<PlaybookItem | 'new' | null>(null);
  const [limit, setLimit] = useState(PAGE);
  const items = usePlaybookItems(filters);
  const set = (k: keyof PlaybookFilters) => (_: unknown, d: { value: string }) => {
    setFilters((f) => ({ ...f, [k]: d.value }));
    setLimit(PAGE);
  };

  return (
    <SectionCard
      title="Items"
      actions={
        <Button appearance="primary" onClick={() => setDialog('new')}>
          New item
        </Button>
      }
    >
      <div className={s.filters}>
        <Field label="Search" className={s.grow}>
          <Input value={filters.q} onChange={set('q')} placeholder="Id, title or description" />
        </Field>
        <Field label="Checklist">
          <Select value={filters.source} onChange={set('source')}>
            <option value="">All</option>
            {(checklists.data ?? []).map((c) => (
              <option key={c.code} value={c.code}>
                {c.label}
              </option>
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
        <Field label="Area">
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
        <EmptyState message="No items match these filters." />
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
                <TableHeaderCell>Checklist</TableHeaderCell>
                <TableHeaderCell>Gate</TableHeaderCell>
                <TableHeaderCell>Area</TableHeaderCell>
                <TableHeaderCell>Tiers</TableHeaderCell>
                <TableHeaderCell>Mandatory</TableHeaderCell>
                <TableHeaderCell>Active</TableHeaderCell>
                <TableHeaderCell />
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.data.slice(0, limit).map((it) => (
                <TableRow key={it.id}>
                  <TableCell>{it.id}</TableCell>
                  <TableCell style={{ minWidth: 220 }}>{it.title}</TableCell>
                  <TableCell title={it.source}>{it.source_label || it.source}</TableCell>
                  <TableCell>
                    {ref?.gates.find((g) => g.code === it.gate)?.short ?? it.gate}
                  </TableCell>
                  <TableCell>
                    <LensChip lens={it.lens as Lens} />
                    {it.lens_is_suggested && (
                      <Badge color="warning" appearance="tint" style={{ marginLeft: 6 }}>
                        area suggested - please confirm
                      </Badge>
                    )}
                  </TableCell>
                  <TableCell>
                    {it.applicable_tiers.length ? it.applicable_tiers.join(', ') : '-'}
                  </TableCell>
                  <TableCell>{it.mandatory ? 'Yes' : 'No'}</TableCell>
                  <TableCell>{it.active ? 'Yes' : 'No'}</TableCell>
                  <TableCell>
                    <Button size="small" onClick={() => setDialog(it)}>
                      Edit
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          <p>
            Showing {Math.min(limit, items.data.length)} of {items.data.length} items.{' '}
            {limit < items.data.length && (
              <Button size="small" onClick={() => setLimit((n) => n + PAGE)}>
                Show more
              </Button>
            )}
          </p>
        </div>
      )}
      {dialog && (
        <ItemDialog
          key={dialog === 'new' ? 'new' : dialog.id}
          item={dialog === 'new' ? undefined : dialog}
          onClose={() => setDialog(null)}
        />
      )}
    </SectionCard>
  );
}

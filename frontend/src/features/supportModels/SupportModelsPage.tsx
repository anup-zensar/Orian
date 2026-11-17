import { useMemo, useState } from 'react';
import {
  Badge,
  Field,
  Input,
  Table,
  TableBody,
  TableCell,
  TableHeader,
  TableHeaderCell,
  TableRow,
  makeStyles,
  tokens,
} from '@fluentui/react-components';
import dayjs from 'dayjs';
import { AppLink } from '../../components/AppLink';
import { EmptyState } from '../../components/EmptyState';
import { ErrorState } from '../../components/ErrorState';
import { LoadingState } from '../../components/LoadingState';
import { PageHeader } from '../../components/PageHeader';
import { SectionCard } from '../../components/SectionCard';
import { useSupportModels } from '../supportModel/api';
import { statusColor } from '../supportModel/status';

const useStyles = makeStyles({
  page: { display: 'flex', flexDirection: 'column', gap: tokens.spacingVerticalL },
  wrap: { overflowX: 'auto' },
});

/** All generated support models (FR-040 · M7). */
export function SupportModelsPage() {
  const s = useStyles();
  const q = useSupportModels();
  const [filter, setFilter] = useState('');

  const rows = useMemo(() => {
    const f = filter.trim().toLowerCase();
    return (q.data ?? []).filter(
      (r) =>
        !f ||
        r.transition_name.toLowerCase().includes(f) ||
        r.transition_id.toLowerCase().includes(f) ||
        r.central_app.toLowerCase().includes(f),
    );
  }, [q.data, filter]);

  return (
    <div className={s.page}>
      <PageHeader
        title="Support models"
        subtitle="Generated support models across all transitions."
      />
      <SectionCard title="Support models">
        <Field label="Filter by name">
          <Input
            value={filter}
            placeholder="Transition or application name"
            onChange={(_, d) => setFilter(d.value)}
          />
        </Field>
        {q.isPending ? (
          <LoadingState rows={5} />
        ) : q.isError ? (
          <ErrorState error={q.error} onRetry={() => void q.refetch()} />
        ) : rows.length === 0 ? (
          <EmptyState
            message={
              (q.data ?? []).length === 0
                ? 'No support models yet. Open a transition and use its Support model tab to generate one.'
                : 'No support model matches this filter.'
            }
          />
        ) : (
          <div className={s.wrap}>
            <Table aria-label="Support models">
              <TableHeader>
                <TableRow>
                  <TableHeaderCell>Transition</TableHeaderCell>
                  <TableHeaderCell>Portfolio</TableHeaderCell>
                  <TableHeaderCell>Central app</TableHeaderCell>
                  <TableHeaderCell>Version</TableHeaderCell>
                  <TableHeaderCell>Status</TableHeaderCell>
                  <TableHeaderCell>Updated</TableHeaderCell>
                  <TableHeaderCell>PPT available</TableHeaderCell>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map((r) => (
                  <TableRow key={r.id}>
                    <TableCell>
                      <AppLink to={`/transitions/${r.transition_id}/support-model`}>
                        {r.transition_name} ({r.transition_id})
                      </AppLink>
                    </TableCell>
                    <TableCell>{r.portfolio}</TableCell>
                    <TableCell>{r.central_app}</TableCell>
                    <TableCell>v{r.version}</TableCell>
                    <TableCell>
                      <Badge appearance="tint" color={statusColor(r.status)}>
                        {r.status}
                      </Badge>
                    </TableCell>
                    <TableCell>{dayjs(r.updated_at).format('D MMM YYYY HH:mm')}</TableCell>
                    <TableCell>{r.pptx_available ? 'Yes' : 'No'}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </SectionCard>
    </div>
  );
}

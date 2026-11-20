import { useState } from 'react';
import {
  Badge,
  Button,
  Table,
  TableBody,
  TableCell,
  TableHeader,
  TableHeaderCell,
  TableRow,
} from '@fluentui/react-components';
import { DataTable } from '../../../components/DataTable';
import { ErrorState } from '../../../components/ErrorState';
import { LoadingState } from '../../../components/LoadingState';
import { SectionCard } from '../../../components/SectionCard';
import type { ChecklistAdmin } from '../../../api/types';
import { useReference } from '../../reference/api';
import { useChecklists } from '../catalogApi';
import { ChecklistDialog } from './ChecklistDialog';

const KIND_TEXT: Record<string, string> = {
  library: 'Chosen per project type',
  portfolio_golden: 'Chosen by portfolio',
  common: 'Always included',
};

/** The checklists (FRAMEWORK, AI_PLAYBOOK ...) with a New checklist button. */
export function ChecklistsPanel() {
  const q = useChecklists();
  const { data: ref } = useReference();
  const [dialog, setDialog] = useState<ChecklistAdmin | 'new' | null>(null);
  const typeLabel = (code: string) =>
    ref?.project_types.find((p) => p.code === code)?.label || code;

  return (
    <SectionCard
      title="Checklists"
      actions={
        <Button appearance="primary" onClick={() => setDialog('new')}>
          New checklist
        </Button>
      }
    >
      {q.isLoading ? (
        <LoadingState rows={4} />
      ) : q.isError ? (
        <ErrorState error={q.error} onRetry={() => void q.refetch()} />
      ) : (
        <DataTable label="Checklists table" stickyFirstColumn>
          <Table
            aria-label="Checklists"
            size="small"
            style={{ tableLayout: 'auto', minWidth: '100%' }}
          >
            <TableHeader>
              <TableRow>
                <TableHeaderCell style={{ width: 72 }} />
                <TableHeaderCell>Name</TableHeaderCell>
                <TableHeaderCell>How it is used</TableHeaderCell>
                <TableHeaderCell>Items</TableHeaderCell>
                <TableHeaderCell>Project types</TableHeaderCell>
              </TableRow>
            </TableHeader>
            <TableBody>
              {(q.data ?? []).map((c) => (
                <TableRow key={c.code}>
                  <TableCell>
                    <Button size="small" onClick={() => setDialog(c)}>
                      Edit
                    </Button>
                  </TableCell>
                  <TableCell>
                    <div title={`Code: ${c.code}`}>{c.label}</div>
                    {!c.active && (
                      <Badge appearance="tint" color="subtle" style={{ marginLeft: 6 }}>
                        inactive
                      </Badge>
                    )}
                  </TableCell>
                  <TableCell>{KIND_TEXT[c.kind] ?? c.kind}</TableCell>
                  <TableCell>{c.item_count}</TableCell>
                  <TableCell>{c.project_types.map(typeLabel).join(', ') || '-'}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </DataTable>
      )}
      {dialog && (
        <ChecklistDialog
          key={dialog === 'new' ? 'new' : dialog.code}
          checklist={dialog === 'new' ? undefined : dialog}
          onClose={() => setDialog(null)}
        />
      )}
    </SectionCard>
  );
}

import { useState } from 'react';
import {
  Button,
  Checkbox,
  Switch,
  Table,
  TableBody,
  TableCell,
  TableHeader,
  TableHeaderCell,
  TableRow,
  makeStyles,
} from '@fluentui/react-components';
import { EmptyState } from '../../components/EmptyState';
import { ErrorState } from '../../components/ErrorState';
import { LoadingState } from '../../components/LoadingState';
import { SectionCard } from '../../components/SectionCard';
import { useApiErrorToast } from '../../hooks/useApiErrorToast';
import { useFlavourRules, usePutFlavourRules, type FlavourRule } from './api';
import { useSuccessToast } from './useSavedToast';

const CHECKLISTS = ['FRAMEWORK', 'AI_PLAYBOOK'] as const;
type Source = 'FRAMEWORK' | 'AI_PLAYBOOK' | 'PORTFOLIO' | 'COMMON';
const useStyles = makeStyles({ scroll: { overflowX: 'auto' } });

function Editor({ initial }: { initial: FlavourRule[] }) {
  const s = useStyles();
  const [rules, setRules] = useState(initial);
  const save = usePutFlavourRules();
  const showError = useApiErrorToast();
  const ok = useSuccessToast();
  const patch = (code: string, p: Partial<FlavourRule>) =>
    setRules((rs) => rs.map((r) => (r.project_type === code ? { ...r, ...p } : r)));

  return (
    <SectionCard
      title="Flavour rules"
      actions={
        <Button
          appearance="primary"
          disabled={save.isPending}
          onClick={() =>
            save.mutate(
              {
                rules: rules.map((r) => ({
                  project_type: r.project_type,
                  checklists: r.checklists as Source[],
                  requires_tiering: r.requires_tiering,
                  note: r.note,
                })),
              },
              { onSuccess: () => ok('Flavour rules saved'), onError: showError },
            )
          }
        >
          {save.isPending ? 'Saving...' : 'Save flavour rules'}
        </Button>
      }
    >
      {rules.length === 0 ? (
        <EmptyState message="No project types configured." />
      ) : (
        <div className={s.scroll}>
          <Table aria-label="Flavour rules" size="small">
            <TableHeader>
              <TableRow>
                <TableHeaderCell>Project type</TableHeaderCell>
                <TableHeaderCell>Checklists</TableHeaderCell>
                <TableHeaderCell>Requires tiering</TableHeaderCell>
                <TableHeaderCell>Note</TableHeaderCell>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rules.map((r) => (
                <TableRow key={r.project_type}>
                  <TableCell>{r.project_type}</TableCell>
                  <TableCell>
                    {CHECKLISTS.map((c) => (
                      <Checkbox
                        key={c}
                        label={c === 'FRAMEWORK' ? 'Framework' : 'AI Playbook'}
                        checked={r.checklists.includes(c)}
                        onChange={(_, d) =>
                          patch(r.project_type, {
                            checklists: d.checked
                              ? [...r.checklists, c]
                              : r.checklists.filter((x) => x !== c),
                          })
                        }
                      />
                    ))}
                  </TableCell>
                  <TableCell>
                    <Switch
                      aria-label={`${r.project_type} requires tiering`}
                      checked={r.requires_tiering}
                      onChange={(_, d) => patch(r.project_type, { requires_tiering: d.checked })}
                    />
                  </TableCell>
                  <TableCell>{r.note ?? ''}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </SectionCard>
  );
}

export function FlavourSection() {
  const q = useFlavourRules();
  if (q.isLoading) return <LoadingState rows={5} />;
  if (q.isError) return <ErrorState error={q.error} onRetry={() => void q.refetch()} />;
  // key re-initialises local edits after a successful save refetch
  return <Editor key={JSON.stringify(q.data?.rules)} initial={q.data?.rules ?? []} />;
}

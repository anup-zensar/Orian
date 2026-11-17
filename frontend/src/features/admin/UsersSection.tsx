import {
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
import { useAdminUsers } from './api';

const useStyles = makeStyles({ scroll: { overflowX: 'auto' } });

export function UsersSection() {
  const s = useStyles();
  const q = useAdminUsers();
  return (
    <SectionCard title="Users (read-only)">
      {q.isLoading ? (
        <LoadingState rows={6} />
      ) : q.isError ? (
        <ErrorState error={q.error} onRetry={() => void q.refetch()} />
      ) : !q.data?.length ? (
        <EmptyState message="No users." />
      ) : (
        <div className={s.scroll}>
          <Table aria-label="Users" size="small">
            <TableHeader>
              <TableRow>
                <TableHeaderCell>Id</TableHeaderCell>
                <TableHeaderCell>Name</TableHeaderCell>
                <TableHeaderCell>Email</TableHeaderCell>
                <TableHeaderCell>Role</TableHeaderCell>
              </TableRow>
            </TableHeader>
            <TableBody>
              {q.data.map((u) => (
                <TableRow key={u.id}>
                  <TableCell>{u.id}</TableCell>
                  <TableCell>{u.name}</TableCell>
                  <TableCell>{u.email}</TableCell>
                  <TableCell>{u.role_label || u.role}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </SectionCard>
  );
}

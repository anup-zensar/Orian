// FR-012 Transitions list: searchable, filterable register of all transitions (spec 8.3).
import { Button, Caption1, Tooltip } from '@fluentui/react-components';
import { Add20Regular } from '@fluentui/react-icons';
import { useNavigate } from 'react-router';
import { EmptyState } from '../../components/EmptyState';
import { ErrorState } from '../../components/ErrorState';
import { LoadingState } from '../../components/LoadingState';
import { PageHeader } from '../../components/PageHeader';
import { plural } from '../../lib/format';
import { useMe } from '../users/api';
import { useTransitions } from './api';
import { FilterBar } from './FilterBar';
import { TransitionRegisterTable } from './TransitionRegisterTable';
import { useUrlFilters } from './useUrlFilters';

export function TransitionsPage() {
  const navigate = useNavigate();
  const { filters, update, clear, notice } = useUrlFilters();
  const me = useMe();
  const canCreate = me.data?.permissions.includes('create_transition') ?? false;
  const denied =
    me.data?.denied_reasons?.create_transition ??
    'You do not have permission to create transitions';
  const q = useTransitions(filters);

  return (
    <>
      <PageHeader
        title="Transitions"
        subtitle="Every transition with live readiness, gaps and RAG."
        actions={
          <Tooltip
            content={canCreate ? 'Start a new transition' : denied}
            relationship="description"
          >
            <Button
              appearance="primary"
              icon={<Add20Regular />}
              disabledFocusable={!canCreate}
              onClick={canCreate ? () => navigate('/transitions/new') : undefined}
            >
              New transition
            </Button>
          </Tooltip>
        }
      />
      <FilterBar filters={filters} update={update} clear={clear} showMine notice={notice} />
      {q.isLoading ? (
        <LoadingState rows={6} />
      ) : q.error ? (
        <ErrorState error={q.error} onRetry={() => void q.refetch()} />
      ) : q.data && q.data.length > 0 ? (
        <>
          <Caption1 role="status" style={{ display: 'block', marginBottom: 8 }}>
            {plural(q.data.length, 'transition')}
          </Caption1>
          <TransitionRegisterTable rows={q.data} />
        </>
      ) : (
        <EmptyState
          message="No transitions match these filters"
          action={<Button onClick={clear}>Clear filters</Button>}
        />
      )}
    </>
  );
}

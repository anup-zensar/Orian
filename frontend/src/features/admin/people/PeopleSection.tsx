import { makeStyles, tokens } from '@fluentui/react-components';
import { ErrorState } from '../../../components/ErrorState';
import { LoadingState } from '../../../components/LoadingState';
import { usePermissionMatrix } from '../peopleRulesApi';
import { DirtyGuard, Intro } from '../peopleRulesUi';
import { PermissionsPanel } from './PermissionsPanel';
import { RolesPanel } from './RolesPanel';
import { UsersPanel } from './UsersPanel';

const useStyles = makeStyles({
  page: { display: 'flex', flexDirection: 'column', gap: tokens.spacingVerticalL },
});

/** Admin section 5: who is in Orion, what the roles are called and what each role may do. */
export function PeopleSection() {
  const s = useStyles();
  const matrix = usePermissionMatrix();
  return (
    <DirtyGuard>
      <div className={s.page}>
        <Intro>
          Add or deactivate people, rename roles and decide what each role may do. This changes who
          can sign in and what they are allowed to do straight away; it does not change
          anyone&apos;s assignments on transitions unless you move them when deactivating.
        </Intro>
        <UsersPanel />
        {matrix.isLoading ? (
          <LoadingState rows={6} />
        ) : matrix.isError ? (
          <ErrorState error={matrix.error} onRetry={() => void matrix.refetch()} />
        ) : matrix.data ? (
          <>
            <RolesPanel roles={matrix.data.roles} />
            <PermissionsPanel matrix={matrix.data} />
          </>
        ) : null}
      </div>
    </DirtyGuard>
  );
}

import { useState } from 'react';
import {
  Badge,
  Button,
  DialogActions,
  DialogBody,
  DialogContent,
  DialogSurface,
  DialogTitle,
  Field,
  Input,
  Select,
  Table,
  TableBody,
  TableCell,
  TableHeader,
  TableHeaderCell,
  TableRow,
  Tooltip,
  makeStyles,
  mergeClasses,
  tokens,
} from '@fluentui/react-components';
import type { UserAdmin } from '../../../api/types';
import { useAuth } from '../../../auth/useAuth';
import { EmptyState } from '../../../components/EmptyState';
import { ErrorState } from '../../../components/ErrorState';
import { LoadingState } from '../../../components/LoadingState';
import { ReturnFocusDialog } from '../../../components/ReturnFocusDialog';
import { DataTable } from '../../../components/DataTable';
import { SectionCard } from '../../../components/SectionCard';
import { useRoles } from '../../reference/options';
import { useCreateUser, useDeactivateUser, useUpdateUser, useUsersList } from '../peopleRulesApi';
import { ReasonsBar } from '../peopleRulesUi';
import { useSuccessToast } from '../useSavedToast';

const useStyles = makeStyles({
  form: { display: 'flex', flexDirection: 'column', gap: tokens.spacingVerticalM },
  nowrap: { whiteSpace: 'nowrap' },
  muted: { color: tokens.colorNeutralForeground3 },
  actions: { display: 'flex', flexWrap: 'wrap', gap: tokens.spacingHorizontalXS },
});

/** Add (user = null) or edit one person. The id is assigned by the server and never changes. */
function UserDialog({ user, onClose }: { user: UserAdmin | null; onClose: () => void }) {
  const s = useStyles();
  const roles = useRoles({ include: user?.role });
  const create = useCreateUser();
  const update = useUpdateUser();
  const ok = useSuccessToast();
  const [name, setName] = useState(user?.name ?? '');
  const [email, setEmail] = useState(user?.email ?? '');
  const [pickedRole, setRole] = useState(user?.role ?? '');
  const role = pickedRole || roles[0]?.code || ''; // the first role until one is picked
  const [title, setTitle] = useState(user?.title ?? '');
  const [focal, setFocal] = useState(user?.focal_label ?? '');
  const pending = create.isPending || update.isPending;
  const error = create.error ?? update.error;
  const valid = name.trim() !== '' && email.includes('@') && role !== '';

  const submit = () => {
    const fields = {
      name: name.trim(),
      email: email.trim(),
      role,
      title: title.trim() || null,
      focal_label: role === 'OR_FOCAL' ? focal.trim() || null : null,
    };
    const done = () => {
      ok('Saved - applies immediately');
      onClose();
    };
    if (user) update.mutate({ id: user.id, body: fields }, { onSuccess: done });
    else create.mutate(fields, { onSuccess: done });
  };

  return (
    <ReturnFocusDialog open onOpenChange={(_, d) => !d.open && onClose()}>
      <DialogSurface>
        <DialogBody>
          <DialogTitle>{user ? `Edit ${user.name}` : 'Add a person'}</DialogTitle>
          <DialogContent className={s.form}>
            <Field label="Id" hint="Assigned automatically and never changes.">
              <Input readOnly value={user?.id ?? 'Next free number (for example U17)'} />
            </Field>
            <Field label="Name" required>
              <Input value={name} onChange={(_, d) => setName(d.value)} />
            </Field>
            <Field label="Email" required>
              <Input value={email} onChange={(_, d) => setEmail(d.value)} />
            </Field>
            <Field label="Role" required>
              <Select value={role} onChange={(_, d) => setRole(d.value)}>
                {roles.map((r) => (
                  <option key={r.code} value={r.code}>
                    {r.label}
                  </option>
                ))}
              </Select>
            </Field>
            {role === 'OR_FOCAL' && (
              <Field
                label="Focus area (optional)"
                hint="Shown next to the name, for example a portfolio."
              >
                <Input value={focal} onChange={(_, d) => setFocal(d.value)} />
              </Field>
            )}
            <Field label="Job title (optional)">
              <Input value={title} onChange={(_, d) => setTitle(d.value)} />
            </Field>
            <ReasonsBar error={error} />
          </DialogContent>
          <DialogActions>
            <Button onClick={onClose}>Cancel</Button>
            <Button appearance="primary" disabled={!valid || pending} onClick={submit}>
              {pending ? 'Saving...' : user ? 'Save' : 'Add person'}
            </Button>
          </DialogActions>
        </DialogBody>
      </DialogSurface>
    </ReturnFocusDialog>
  );
}

/** Deactivate one person; their transition assignments can move to a colleague in the same role. */
function DeactivateDialog(props: { user: UserAdmin; all: UserAdmin[]; onClose: () => void }) {
  const { user, all, onClose } = props;
  const s = useStyles();
  const deactivate = useDeactivateUser();
  const ok = useSuccessToast();
  const count = user.assigned_transitions ?? 0;
  const colleagues = all.filter(
    (u) => u.id !== user.id && u.role === user.role && u.active !== false,
  );
  const [target, setTarget] = useState('');
  const mustPick = count > 0 && colleagues.length > 0;

  const submit = () =>
    deactivate.mutate(
      { id: user.id, body: { reassign_to: target || null } },
      {
        onSuccess: (r) => {
          ok(
            r.reassigned > 0
              ? `Deactivated - ${r.reassigned} assignments moved`
              : 'Deactivated - applies immediately',
          );
          onClose();
        },
      },
    );

  return (
    <ReturnFocusDialog open onOpenChange={(_, d) => !d.open && onClose()}>
      <DialogSurface>
        <DialogBody>
          <DialogTitle>Deactivate {user.name}?</DialogTitle>
          <DialogContent className={s.form}>
            <span>
              {user.name} can no longer sign in or be picked for new work. Old records keep their
              name.
            </span>
            {count > 0 && (
              <span>
                Assigned on <strong>{count}</strong> active{' '}
                {count === 1 ? 'transition' : 'transitions'}.
              </span>
            )}
            <Field
              label="Move their assignments to"
              hint={
                colleagues.length === 0
                  ? `There is no other active ${user.role_label || user.role}.`
                  : 'Only people with the same role are offered.'
              }
            >
              <Select value={target} onChange={(_, d) => setTarget(d.value)}>
                <option value="">{mustPick ? 'Choose a person' : 'Nobody'}</option>
                {colleagues.map((u) => (
                  <option key={u.id} value={u.id}>
                    {u.name}
                  </option>
                ))}
              </Select>
            </Field>
            <ReasonsBar error={deactivate.error} />
          </DialogContent>
          <DialogActions>
            <Button onClick={onClose}>Cancel</Button>
            <Button
              appearance="primary"
              disabled={deactivate.isPending || (mustPick && !target)}
              onClick={submit}
            >
              {deactivate.isPending ? 'Working...' : 'Deactivate'}
            </Button>
          </DialogActions>
        </DialogBody>
      </DialogSurface>
    </ReturnFocusDialog>
  );
}

/** The users table with Add, Edit and Deactivate. */
export function UsersPanel() {
  const s = useStyles();
  const q = useUsersList();
  const { userId } = useAuth();
  const [editing, setEditing] = useState<UserAdmin | 'new' | null>(null);
  const [removing, setRemoving] = useState<UserAdmin | null>(null);

  return (
    <SectionCard
      title="People"
      actions={
        <Button appearance="primary" onClick={() => setEditing('new')}>
          Add person
        </Button>
      }
    >
      {q.isLoading ? (
        <LoadingState rows={6} />
      ) : q.isError ? (
        <ErrorState error={q.error} onRetry={() => void q.refetch()} />
      ) : !q.data?.length ? (
        <EmptyState message="No users." />
      ) : (
        <DataTable label="People table" stickyFirstColumn>
          <Table aria-label="People" size="small" style={{ tableLayout: 'auto' }}>
            <TableHeader>
              <TableRow>
                <TableHeaderCell>Person</TableHeaderCell>
                <TableHeaderCell>Email</TableHeaderCell>
                <TableHeaderCell>Role</TableHeaderCell>
                <TableHeaderCell />
              </TableRow>
            </TableHeader>
            <TableBody>
              {q.data.map((u) => {
                const inactive = u.active === false;
                const self = u.id === userId;
                return (
                  <TableRow key={u.id}>
                    <TableCell>
                      <div className={mergeClasses(s.nowrap, inactive && s.muted)}>{u.name}</div>
                      <div className={s.muted}>
                        {u.id}
                        {inactive && (
                          <Badge
                            appearance="tint"
                            color="subtle"
                            size="small"
                            style={{ marginLeft: 6 }}
                          >
                            Inactive
                          </Badge>
                        )}
                      </div>
                    </TableCell>
                    <TableCell>{u.email}</TableCell>
                    <TableCell>{u.role_label || u.role}</TableCell>
                    <TableCell>
                      <div className={s.actions}>
                        <Button
                          size="small"
                          aria-label={`Edit ${u.name}`}
                          onClick={() => setEditing(u)}
                        >
                          Edit
                        </Button>
                        <Tooltip
                          relationship="description"
                          content={
                            inactive
                              ? 'Already inactive'
                              : self
                                ? 'You cannot deactivate yourself'
                                : 'Stop this person signing in; assignments can move to a colleague'
                          }
                        >
                          <Button
                            size="small"
                            aria-label={`Deactivate ${u.name}`}
                            disabledFocusable={inactive || self}
                            onClick={() => setRemoving(u)}
                          >
                            Deactivate
                          </Button>
                        </Tooltip>
                      </div>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </DataTable>
      )}
      {editing && (
        <UserDialog user={editing === 'new' ? null : editing} onClose={() => setEditing(null)} />
      )}
      {removing && q.data && (
        <DeactivateDialog user={removing} all={q.data} onClose={() => setRemoving(null)} />
      )}
    </SectionCard>
  );
}

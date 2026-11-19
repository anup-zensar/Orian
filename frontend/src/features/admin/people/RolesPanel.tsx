import { useState } from 'react';
import {
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
import type { RoleAdmin } from '../../../api/types';
import { SectionCard } from '../../../components/SectionCard';
import { useApiErrorToast } from '../../../hooks/useApiErrorToast';
import { useUpdateRole } from '../peopleRulesApi';
import { ReasonsBar, SaveBar } from '../peopleRulesUi';
import { useDirty } from '../useDirty';
import { useSuccessToast } from '../useSavedToast';

interface Texts {
  label: string;
  short_label: string;
  description: string;
}

const useStyles = makeStyles({
  scroll: { overflowX: 'auto' },
  note: { color: tokens.colorNeutralForeground3, margin: 0 },
  wide: { minWidth: '200px' },
});

const textsOf = (r: RoleAdmin): Texts => ({
  label: r.label,
  short_label: r.short_label,
  description: r.description ?? '',
});

/** The 8 built-in roles: their names and descriptions are editable, their codes are not. */
function Editor({ roles }: { roles: RoleAdmin[] }) {
  const s = useStyles();
  const [draft, setDraft] = useState<Record<string, Texts>>(() =>
    Object.fromEntries(roles.map((r) => [r.code, textsOf(r)])),
  );
  const dirty = useDirty(draft, 'roles');
  const update = useUpdateRole();
  const showError = useApiErrorToast();
  const ok = useSuccessToast();
  const [error, setError] = useState<unknown>(null);

  const changed = roles.filter((r) => JSON.stringify(textsOf(r)) !== JSON.stringify(draft[r.code]));
  const blank = roles.some((r) => !draft[r.code].label.trim() || !draft[r.code].short_label.trim());

  const edit = (code: string, p: Partial<Texts>) =>
    setDraft((d) => ({ ...d, [code]: { ...d[code], ...p } }));

  /** One call per changed role; stops at the first refusal and shows its reasons. */
  const save = async () => {
    setError(null);
    try {
      for (const r of changed) {
        const t = draft[r.code];
        await update.mutateAsync({
          code: r.code,
          body: {
            label: t.label.trim(),
            short_label: t.short_label.trim(),
            description: t.description.trim(),
          },
        });
      }
      ok('Saved - applies immediately');
    } catch (e) {
      setError(e);
      showError(e);
    }
  };

  return (
    <SectionCard title="Roles">
      <p className={s.note}>
        Everyone has one of these roles. Change how a role is named and described; the role itself
        stays fixed.
      </p>
      <div className={s.scroll}>
        <Table aria-label="Roles" size="small" style={{ tableLayout: 'auto', minWidth: '100%' }}>
          <TableHeader>
            <TableRow>
              <TableHeaderCell>Name</TableHeaderCell>
              <TableHeaderCell>Short name</TableHeaderCell>
              <TableHeaderCell>Description</TableHeaderCell>
              <TableHeaderCell>People</TableHeaderCell>
            </TableRow>
          </TableHeader>
          <TableBody>
            {roles.map((r) => (
              <TableRow key={r.code}>
                <TableCell>
                  <Input
                    aria-label={`${r.code} name`}
                    title={`Code: ${r.code} (fixed)`}
                    value={draft[r.code].label}
                    onChange={(_, d) => edit(r.code, { label: d.value })}
                  />
                </TableCell>
                <TableCell>
                  <Input
                    aria-label={`${r.code} short name`}
                    value={draft[r.code].short_label}
                    onChange={(_, d) => edit(r.code, { short_label: d.value })}
                  />
                </TableCell>
                <TableCell className={s.wide}>
                  <Input
                    aria-label={`${r.code} description`}
                    style={{ width: '100%' }}
                    placeholder="What can this role do?"
                    value={draft[r.code].description}
                    onChange={(_, d) => edit(r.code, { description: d.value })}
                  />
                </TableCell>
                <TableCell>{r.user_count ?? 0}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
      <ReasonsBar error={error} />
      <SaveBar
        dirty={dirty}
        saving={update.isPending}
        blockedReason={blank ? 'Every role needs a name and a short name' : undefined}
        onSave={() => void save()}
        onDiscard={() => setDraft(Object.fromEntries(roles.map((r) => [r.code, textsOf(r)])))}
      />
    </SectionCard>
  );
}

export function RolesPanel({ roles }: { roles: RoleAdmin[] }) {
  // key: a fresh editor (and a fresh "unsaved" baseline) whenever the saved roles change
  return <Editor key={JSON.stringify(roles.map(textsOf))} roles={roles} />;
}

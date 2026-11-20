import { Fragment, useState } from 'react';
import {
  Badge,
  Button,
  Checkbox,
  DialogActions,
  DialogBody,
  DialogContent,
  DialogSurface,
  DialogTitle,
  Field,
  MessageBar,
  MessageBarBody,
  Textarea,
  Tooltip,
  makeStyles,
  tokens,
} from '@fluentui/react-components';
import { Edit16Regular } from '@fluentui/react-icons';
import { LockClosedRegular } from '@fluentui/react-icons';
import type { PermissionMatrix, PermissionRow } from '../../../api/types';
import { DataTable } from '../../../components/DataTable';
import { ReturnFocusDialog } from '../../../components/ReturnFocusDialog';
import { SectionCard } from '../../../components/SectionCard';
import { usePutPermissions } from '../peopleRulesApi';
import { ReasonsBar, SaveBar } from '../peopleRulesUi';
import { useDirty } from '../useDirty';
import { useSuccessToast } from '../useSavedToast';

interface Draft {
  grants: Record<string, string[]>; // permission code -> role codes that hold it
  denial: Record<string, string>; // permission code -> message shown when refused
}

const useStyles = makeStyles({
  note: { color: tokens.colorNeutralForeground3, margin: 0 },
  grid: { borderCollapse: 'collapse', width: '100%' },
  th: {
    textAlign: 'center',
    padding: tokens.spacingVerticalXS,
    fontWeight: tokens.fontWeightSemibold,
    fontSize: tokens.fontSizeBase200,
    borderBottom: `1px solid ${tokens.colorNeutralStroke1}`,
    maxWidth: '84px',
  },
  thLeft: {
    textAlign: 'left',
    minWidth: '200px',
  },
  area: {
    padding: `${tokens.spacingVerticalS} ${tokens.spacingHorizontalS}`,
    backgroundColor: tokens.colorNeutralBackground3,
    fontWeight: tokens.fontWeightSemibold,
  },
  cell: {
    textAlign: 'center',
    padding: 0,
    borderBottom: `1px solid ${tokens.colorNeutralStroke2}`,
  },
  name: {
    minWidth: '200px',
    padding: `${tokens.spacingVerticalXS} ${tokens.spacingHorizontalS}`,
    borderBottom: `1px solid ${tokens.colorNeutralStroke2}`,
  },
  nameLine: {
    display: 'flex',
    alignItems: 'center',
    flexWrap: 'wrap',
    columnGap: tokens.spacingHorizontalS,
  },
  desc: { color: tokens.colorNeutralForeground3, fontSize: tokens.fontSizeBase200 },
  lock: {
    display: 'inline-flex',
    alignItems: 'center',
    gap: '2px',
    padding: '6px',
    color: tokens.colorNeutralForeground3,
  },
});

/** Groups the permission rows by their area, keeping the server's order. */
function byArea(rows: PermissionRow[]): [string, PermissionRow[]][] {
  const groups = new Map<string, PermissionRow[]>();
  for (const r of rows)
    groups.set(r.area || 'Other', [...(groups.get(r.area || 'Other') ?? []), r]);
  return [...groups.entries()];
}

/** Dialog that edits the sentence a person sees when they are not allowed to do something. */
function DenialDialog(props: {
  row: PermissionRow;
  value: string;
  onSave: (text: string) => void;
  onClose: () => void;
}) {
  const { row } = props;
  const [text, setText] = useState(props.value);
  return (
    <ReturnFocusDialog open onOpenChange={(_, d) => !d.open && props.onClose()}>
      <DialogSurface>
        <DialogBody>
          <DialogTitle>Message when {row.label.toLowerCase()} is not allowed</DialogTitle>
          <DialogContent>
            <Field
              label="What the person sees"
              hint="Shown as the reason on a disabled button or after a refused action."
            >
              <Textarea
                rows={3}
                value={text}
                onChange={(_, d) => setText(d.value)}
                aria-label="Refusal message"
              />
            </Field>
          </DialogContent>
          <DialogActions>
            <Button onClick={() => setText(row.default_denial_reason)}>Use generated text</Button>
            <Button onClick={props.onClose}>Cancel</Button>
            <Button
              appearance="primary"
              disabled={!text.trim()}
              onClick={() => {
                props.onSave(text.trim());
                props.onClose();
              }}
            >
              Done
            </Button>
          </DialogActions>
        </DialogBody>
      </DialogSurface>
    </ReturnFocusDialog>
  );
}

function Editor({ matrix }: { matrix: PermissionMatrix }) {
  const s = useStyles();
  const initial = (): Draft => ({
    grants: Object.fromEntries(matrix.permissions.map((p) => [p.perm, [...p.roles]])),
    denial: Object.fromEntries(matrix.permissions.map((p) => [p.perm, p.denial_reason])),
  });
  const [draft, setDraft] = useState<Draft>(initial);
  const [editing, setEditing] = useState<PermissionRow | null>(null);
  const dirty = useDirty(draft, 'permissions');
  const save = usePutPermissions();
  const ok = useSuccessToast();

  const toggle = (perm: string, role: string, on: boolean) =>
    setDraft((d) => ({
      ...d,
      grants: {
        ...d.grants,
        [perm]: on ? [...d.grants[perm], role] : d.grants[perm].filter((r) => r !== role),
      },
    }));

  const submit = () => {
    const texts = Object.fromEntries(
      matrix.permissions
        .filter((p) => draft.denial[p.perm] !== p.denial_reason)
        .map((p) => [p.perm, { denial_reason: draft.denial[p.perm] }]),
    );
    save.mutate(
      { matrix: draft.grants, texts },
      { onSuccess: () => ok('Saved - applies immediately') },
    );
  };

  return (
    <SectionCard title="Permissions">
      <p className={s.note}>
        Tick what each role may do. Greyed cells are fixed for safety; hover one to see why.
      </p>
      {matrix.notices.map((n) => (
        <MessageBar key={n} intent="info">
          <MessageBarBody>{n.replace(/\s*\(BR-\d+\)/g, '')}</MessageBarBody>
        </MessageBar>
      ))}
      <DataTable label="Permissions table" stickyFirstColumn>
        <table className={s.grid} aria-label="Permissions by role">
          <thead>
            <tr>
              <th className={`${s.th} ${s.thLeft}`}>What</th>
              {matrix.roles.map((r) => (
                <th key={r.code} className={s.th} title={r.label}>
                  {r.short_label || r.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {byArea(matrix.permissions).map(([area, rows]) => (
              <Fragment key={area}>
                <tr>
                  <td className={s.area} colSpan={matrix.roles.length + 1}>
                    {area}
                  </td>
                </tr>
                {rows.map((p) => (
                  <tr key={p.perm}>
                    <td className={s.name}>
                      <div className={s.nameLine}>
                        <span>{p.label}</span>
                        <Tooltip
                          relationship="description"
                          content={
                            p.scope === 'transition'
                              ? 'Also needs the person to be assigned on the transition'
                              : 'Works on every transition and page'
                          }
                        >
                          <Badge
                            appearance="tint"
                            size="small"
                            color={p.scope === 'transition' ? 'informative' : 'brand'}
                          >
                            {p.scope === 'transition' ? 'Own transitions' : 'Everywhere'}
                          </Badge>
                        </Tooltip>
                      </div>
                      {p.description && <div className={s.desc}>{p.description}</div>}
                      <Tooltip
                        relationship="label"
                        content={
                          draft.denial[p.perm] !== p.denial_reason
                            ? 'Refusal message (edited)'
                            : 'Edit the message shown when this is refused'
                        }
                      >
                        <Button
                          size="small"
                          appearance="transparent"
                          icon={<Edit16Regular />}
                          aria-label={`Edit refusal message for ${p.label}`}
                          onClick={() => setEditing(p)}
                        />
                      </Tooltip>
                    </td>
                    {matrix.roles.map((r) => {
                      const locked = p.locked_roles.includes(r.code);
                      const checked = draft.grants[p.perm].includes(r.code);
                      const label = `${p.label} for ${r.short_label || r.label}`;
                      return (
                        <td key={r.code} className={s.cell}>
                          {locked ? (
                            <Tooltip
                              relationship="description"
                              content={p.lock_reasons[r.code] ?? 'This cell is fixed'}
                            >
                              <span
                                className={s.lock}
                                tabIndex={0}
                                role="img"
                                aria-label={`${label}: ${checked ? 'allowed' : 'not allowed'}, fixed`}
                              >
                                <Checkbox checked={checked} disabled aria-hidden tabIndex={-1} />
                                <LockClosedRegular fontSize={12} />
                              </span>
                            </Tooltip>
                          ) : (
                            <Checkbox
                              aria-label={label}
                              checked={checked}
                              onChange={(_, d) => toggle(p.perm, r.code, d.checked === true)}
                            />
                          )}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </Fragment>
            ))}
          </tbody>
        </table>
      </DataTable>
      <ReasonsBar error={save.error} />
      <SaveBar
        dirty={dirty}
        saving={save.isPending}
        onSave={submit}
        onDiscard={() => {
          setDraft(initial());
          save.reset();
        }}
      />
      {editing && (
        <DenialDialog
          row={editing}
          value={draft.denial[editing.perm]}
          onSave={(text) =>
            setDraft((d) => ({ ...d, denial: { ...d.denial, [editing.perm]: text } }))
          }
          onClose={() => setEditing(null)}
        />
      )}
    </SectionCard>
  );
}

export function PermissionsPanel({ matrix }: { matrix: PermissionMatrix }) {
  // key: a fresh editor (and a fresh "unsaved" baseline) whenever the saved matrix changes
  return <Editor key={JSON.stringify(matrix.permissions)} matrix={matrix} />;
}

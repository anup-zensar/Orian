import { useEffect, useState } from 'react';
import {
  Badge,
  Button,
  Field,
  Switch,
  Table,
  TableBody,
  TableCell,
  TableHeader,
  TableHeaderCell,
  TableRow,
  makeStyles,
  mergeClasses,
  tokens,
} from '@fluentui/react-components';
import { EmptyState } from '../../../components/EmptyState';
import { ErrorState } from '../../../components/ErrorState';
import { LoadingState } from '../../../components/LoadingState';
import { SectionCard } from '../../../components/SectionCard';
import type { ChecklistAdmin, ProjectTypeAdmin } from '../../../api/types';
import { useLeaveGuard } from '../../ocet/useLeaveGuard';
import { useChecklists, useProjectTypesAdmin, useUpdateProjectType } from '../catalogApi';
import { DisabledReason } from '../components/DisabledReason';
import { useDiscardGuard } from '../components/DiscardGuard';
import { SectionIntro } from '../components/SectionIntro';
import { UsedByBadge } from '../components/UsedByBadge';
import { useSuccessToast } from '../useSavedToast';
import { AddTypeDialog } from './AddTypeDialog';
import { TypeFields } from './TypeFields';
import { draftFromType, splitList, type TypeDraft } from './typeDraft';

const useStyles = makeStyles({
  layout: {
    display: 'flex',
    gap: tokens.spacingHorizontalL,
    flexWrap: 'wrap',
    alignItems: 'flex-start',
  },
  table: { flexGrow: 2, flexBasis: '460px', minWidth: 0, overflowX: 'auto' },
  panel: { flexGrow: 1, flexBasis: '340px', minWidth: 0 },
  row: { cursor: 'pointer' },
  selected: { backgroundColor: tokens.colorBrandBackground2 },
  chips: { display: 'flex', gap: tokens.spacingHorizontalXS, flexWrap: 'wrap' },
  bar: { display: 'flex', gap: tokens.spacingHorizontalM, alignItems: 'center', flexWrap: 'wrap' },
});

/** The side panel: edit one project type. Reports unsaved edits through `onDirty`. */
function TypePanel(props: {
  type: ProjectTypeAdmin;
  checklists: ChecklistAdmin[];
  isLastActive: boolean;
  onDirty: (dirty: boolean) => void;
}) {
  const s = useStyles();
  const { type } = props;
  const update = useUpdateProjectType();
  const ok = useSuccessToast();
  const [draft, setDraft] = useState<TypeDraft>(() => draftFromType(type));
  const [active, setActive] = useState(type.active);
  const dirty =
    JSON.stringify([draft, active]) !== JSON.stringify([draftFromType(type), type.active]);
  const { onDirty } = props;
  useEffect(() => {
    onDirty(dirty);
    return () => onDirty(false); // an unmounted editor holds no unsaved edits
  }, [dirty, onDirty]);

  const save = () =>
    update.mutate(
      {
        code: type.code,
        body: {
          label: draft.label.trim(),
          description: draft.description,
          active,
          checklists: draft.checklists,
          requires_tiering: draft.requires_tiering,
          has_ai_profile: draft.has_ai_profile,
          has_eval_metrics: draft.has_eval_metrics,
          required_intake_fields: draft.required_intake_fields,
          synonyms: splitList(draft.synonyms),
        },
      },
      { onSuccess: () => ok('Saved - applies to new transitions') },
    );

  const lastActiveReason =
    props.isLastActive && active ? 'At least one project type must stay active.' : null;

  return (
    <SectionCard title={`Edit ${type.label}`}>
      <div className={s.bar}>
        <Field label="Code (cannot change)">
          <code>{type.code}</code>
        </Field>
        <UsedByBadge count={type.used_by} noun="transitions" />
      </div>
      <TypeFields
        draft={draft}
        onChange={(p) => setDraft((d) => ({ ...d, ...p }))}
        checklists={props.checklists}
      />
      <DisabledReason reason={lastActiveReason}>
        <Switch
          label={
            active
              ? 'Active: offered for new transitions'
              : 'Inactive: not offered for new transitions'
          }
          checked={active}
          disabled={!!lastActiveReason}
          onChange={(_, d) => setActive(d.checked)}
        />
      </DisabledReason>
      {!active && type.used_by > 0 && (
        <Badge appearance="tint" color="warning">
          {type.used_by} existing transitions keep this type; it just stops being offered for new
          ones.
        </Badge>
      )}
      {update.isError && <ErrorState error={update.error} />}
      <div className={s.bar}>
        <Button
          appearance="primary"
          onClick={save}
          disabled={!dirty || update.isPending || !draft.label.trim()}
        >
          {update.isPending ? 'Saving...' : 'Save changes'}
        </Button>
        <Button
          disabled={!dirty}
          onClick={() => {
            setDraft(draftFromType(type));
            setActive(type.active);
          }}
        >
          Discard changes
        </Button>
      </div>
    </SectionCard>
  );
}

/** Admin section 2: the project types and what each one gets. */
export function ProjectTypesSection() {
  const s = useStyles();
  const types = useProjectTypesAdmin();
  const checklists = useChecklists();
  const [picked, setPicked] = useState('');
  const [adding, setAdding] = useState(false);
  const [dirty, setDirty] = useState(false);
  const { guard, dialog } = useDiscardGuard(dirty);
  const leaveDialog = useLeaveGuard(dirty);

  const rows = types.data ?? [];
  const selected = rows.find((t) => t.code === picked) ?? rows[0];
  const labelOf = (code: string) => checklists.data?.find((c) => c.code === code)?.label ?? code;
  const activeCount = rows.filter((t) => t.active).length;

  const add = (
    <Button appearance="primary" onClick={() => guard(() => setAdding(true))}>
      Add project type
    </Button>
  );

  return (
    <>
      <SectionIntro>
        Change which checklists, switches and required fields each project type has, or add a new
        project type. New transitions use it from now on; existing transitions are not touched.
      </SectionIntro>
      <SectionCard title="Project types" actions={add}>
        {types.isLoading || checklists.isLoading ? (
          <LoadingState rows={4} />
        ) : types.isError ? (
          <ErrorState error={types.error} onRetry={() => void types.refetch()} />
        ) : !rows.length || !selected ? (
          <EmptyState message="No project types yet. Add the first one." />
        ) : (
          <div className={s.layout}>
            <div className={s.table}>
              <Table
                aria-label="Project types"
                size="small"
                style={{ tableLayout: 'auto', minWidth: '100%' }}
              >
                <TableHeader>
                  <TableRow>
                    <TableHeaderCell>Project type</TableHeaderCell>
                    <TableHeaderCell>Checklists</TableHeaderCell>
                    <TableHeaderCell>Switches</TableHeaderCell>
                    <TableHeaderCell>Used by</TableHeaderCell>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {rows.map((t) => (
                    <TableRow
                      key={t.code}
                      className={mergeClasses(s.row, t.code === selected.code && s.selected)}
                      aria-selected={t.code === selected.code}
                      tabIndex={0}
                      onClick={() => guard(() => setPicked(t.code))}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' || e.key === ' ') {
                          e.preventDefault();
                          guard(() => setPicked(t.code));
                        }
                      }}
                    >
                      <TableCell>
                        <div>{t.label}</div>
                        <code>{t.code}</code>
                        {!t.active && (
                          <Badge appearance="tint" color="subtle" style={{ marginLeft: 6 }}>
                            inactive
                          </Badge>
                        )}
                      </TableCell>
                      <TableCell>{t.checklists.map(labelOf).join(', ') || '-'}</TableCell>
                      <TableCell>
                        <div className={s.chips}>
                          {t.requires_tiering && <Badge appearance="outline">Tiering</Badge>}
                          {t.has_ai_profile && <Badge appearance="outline">AI profile</Badge>}
                          {t.has_eval_metrics && <Badge appearance="outline">Eval metrics</Badge>}
                        </div>
                      </TableCell>
                      <TableCell>{t.used_by}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
            <div className={s.panel}>
              <TypePanel
                key={`${selected.code}-${JSON.stringify(selected)}`}
                type={selected}
                checklists={checklists.data ?? []}
                isLastActive={activeCount <= 1}
                onDirty={setDirty}
              />
            </div>
          </div>
        )}
      </SectionCard>
      {adding && (
        <AddTypeDialog
          checklists={checklists.data ?? []}
          onCreated={setPicked}
          onClose={() => setAdding(false)}
        />
      )}
      {dialog}
      {leaveDialog}
    </>
  );
}

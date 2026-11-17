import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  Body1,
  Button,
  Caption1,
  Link,
  Select,
  Toast,
  ToastBody,
  ToastTitle,
  makeStyles,
  mergeClasses,
  tokens,
  useToastController,
} from '@fluentui/react-components';
import { ChevronDown20Regular, ChevronRight20Regular } from '@fluentui/react-icons';
import { EmptyState } from '../../../components/EmptyState';
import { ErrorState } from '../../../components/ErrorState';
import { LensChip } from '../../../components/LensChip';
import { LoadingState } from '../../../components/LoadingState';
import { useApiErrorToast, TOASTER_ID } from '../../../hooks/useApiErrorToast';
import { plural } from '../../../lib/format';
import type { Lens } from '../../../theme/tokens';
import { useReference } from '../../reference/api';
import { useTransition } from '../../transition/api';
import { useMe } from '../../users/api';
import { useUsers } from '../../users/api';
import { useBulkItems, useItems, usePatchItem, type ItemOut, type ItemPatchIn } from '../api';
import { AssessmentFilters } from '../assessment/AssessmentFilters';
import { GateSummaryBar } from '../assessment/GateSummaryBar';
import { ItemRow, ROW_GRID, type RowPermissions } from '../assessment/ItemRow';
import { ConditionDialog, GapDialog, NaDialog } from '../assessment/StatusDialogs';
import { useAssessmentFilters } from '../assessment/useAssessmentFilters';
import type { TabProps } from '../types';

const useStyles = makeStyles({
  scroller: {
    overflowX: 'auto',
    border: `1px solid ${tokens.colorNeutralStroke2}`,
    borderRadius: tokens.borderRadiusMedium,
  },
  inner: { minWidth: '1400px' },
  head: {
    display: 'grid',
    gridTemplateColumns: ROW_GRID,
    columnGap: tokens.spacingHorizontalS,
    padding: `${tokens.spacingVerticalS} ${tokens.spacingHorizontalS}`,
    backgroundColor: tokens.colorNeutralBackground3,
    fontWeight: tokens.fontWeightSemibold,
    fontSize: tokens.fontSizeBase200,
  },
  gateHead: {
    display: 'flex',
    alignItems: 'center',
    gap: tokens.spacingHorizontalS,
    padding: `${tokens.spacingVerticalXS} ${tokens.spacingHorizontalS}`,
    backgroundColor: tokens.colorBrandBackground2,
    borderBottom: `1px solid ${tokens.colorNeutralStroke2}`,
    fontWeight: tokens.fontWeightSemibold,
  },
  lensHead: {
    display: 'flex',
    alignItems: 'center',
    gap: tokens.spacingHorizontalS,
    padding: `${tokens.spacingVerticalXXS} ${tokens.spacingHorizontalL}`,
    backgroundColor: tokens.colorNeutralBackground2,
    borderBottom: `1px solid ${tokens.colorNeutralStroke2}`,
  },
  bulk: {
    display: 'flex',
    flexWrap: 'wrap',
    alignItems: 'center',
    gap: tokens.spacingHorizontalM,
    padding: tokens.spacingVerticalS,
    marginBottom: tokens.spacingVerticalM,
    backgroundColor: tokens.colorNeutralBackground3,
    borderRadius: tokens.borderRadiusMedium,
  },
  note: { marginBottom: tokens.spacingVerticalS },
});

interface GateGroup {
  gate: string;
  short: string;
  lenses: { lens: string; items: ItemOut[] }[];
  count: number;
}

/** Items arrive sorted by gate, lens, sort order; group them without re-sorting. */
function groupItems(items: ItemOut[]): GateGroup[] {
  const groups: GateGroup[] = [];
  for (const it of items) {
    let g = groups[groups.length - 1];
    if (!g || g.gate !== it.gate) {
      g = { gate: it.gate, short: it.gate_short, lenses: [], count: 0 };
      groups.push(g);
    }
    let l = g.lenses[g.lenses.length - 1];
    if (!l || l.lens !== it.lens) {
      l = { lens: it.lens, items: [] };
      g.lenses.push(l);
    }
    l.items.push(it);
    g.count += 1;
  }
  return groups;
}

type Dialog =
  | { kind: 'gap'; item: ItemOut; status: string }
  | { kind: 'na'; item: ItemOut; status: string }
  | { kind: 'condition'; item: ItemOut }
  | { kind: 'bulk-na' }
  | null;

const LARGE_LIST = 120;

/** Assessment tab (FR-031, spec 8.7 b): filterable checklist grouped by gate and lens. */
export function AssessmentTab({ transitionId }: TabProps) {
  const s = useStyles();
  const { values, query, update, clear, activeCount } = useAssessmentFilters();
  const detail = useTransition(transitionId);
  const ref = useReference();
  const me = useMe();
  const users = useUsers();
  const items = useItems(transitionId, query);
  const patch = usePatchItem(transitionId);
  const bulk = useBulkItems(transitionId);
  const showError = useApiErrorToast();
  const { dispatchToast } = useToastController(TOASTER_ID);

  const [dialog, setDialog] = useState<Dialog>(null);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({});
  const [bulkOwner, setBulkOwner] = useState('');

  const list = items.data?.items;
  const groups = useMemo(() => groupItems(list ?? []), [list]);
  const defaultCollapsed = useCallback(
    (g: GateGroup) =>
      (list?.length ?? 0) > LARGE_LIST &&
      g.gate !== detail.data?.current_gate &&
      !g.lenses.some((l) => l.items.some((i) => i.item_id === values.item)),
    [list, detail.data?.current_gate, values.item],
  );
  const isCollapsed = (g: GateGroup) => collapsed[g.gate] ?? defaultCollapsed(g);

  // deep link: scroll to the row once it is rendered
  const scrolledFor = useRef('');
  useEffect(() => {
    if (!values.item || !list || scrolledFor.current === values.item) return;
    if (!list.some((i) => i.item_id === values.item)) return;
    const t = window.setTimeout(() => {
      document
        .getElementById(`item-${values.item}`)
        ?.scrollIntoView({ block: 'center', behavior: 'smooth' });
      scrolledFor.current = values.item;
    }, 50);
    return () => window.clearTimeout(t);
  }, [values.item, list]);

  const perms: RowPermissions = useMemo(
    () => ({ permissions: me.data?.permissions ?? [], denied: me.data?.denied_reasons ?? {} }),
    [me.data],
  );
  const isFocal = perms.permissions.includes('confirm_scope');
  const deOptions = ref.data?.design_effectiveness_options ?? ['–', 'Yes', 'No', 'N/A'];

  const doPatch = useCallback(
    (item: ItemOut, body: ItemPatchIn) =>
      patch.mutate({ id: item.id, body }, { onSuccess: () => setDialog(null), onError: showError }),
    [patch, showError],
  );

  const onStatus = useCallback(
    (item: ItemOut, status: string) => {
      if (status === 'Gap' || status === 'Non-compliant') setDialog({ kind: 'gap', item, status });
      else if (status === 'N/A' || status === 'Not applicable')
        setDialog({ kind: 'na', item, status });
      else if (status === 'Compliant with conditions') setDialog({ kind: 'condition', item });
      else doPatch(item, { status });
    },
    [doPatch],
  );
  const onDe = useCallback(
    (item: ItemOut, value: string) =>
      doPatch(item, { design_effectiveness: value as ItemPatchIn['design_effectiveness'] }),
    [doPatch],
  );
  const onSelect = useCallback((id: number, checked: boolean) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (checked) next.add(id);
      else next.delete(id);
      return next;
    });
  }, []);

  const runBulk = (body: { owner_user_id?: string; mark_na?: { reason: string } }) =>
    bulk.mutate(
      { item_ids: [...selected], ...body },
      {
        onSuccess: (res) => {
          setSelected(new Set());
          setDialog(null);
          setBulkOwner('');
          dispatchToast(
            <Toast>
              <ToastTitle>{plural(res.updated.length, 'item')} updated</ToastTitle>
              {res.skipped.length > 0 && (
                <ToastBody>
                  <ul style={{ margin: 0, paddingLeft: 18 }}>
                    {res.skipped.map((k) => (
                      <li key={k.id}>
                        #{k.id}: {k.reason}
                      </li>
                    ))}
                  </ul>
                </ToastBody>
              )}
            </Toast>,
            { intent: res.skipped.length ? 'warning' : 'success', timeout: 8000 },
          );
        },
        onError: showError,
      },
    );

  const gateShort = (code: string) => ref.data?.gates.find((g) => g.code === code)?.short ?? code;
  const currentOrder =
    ref.data?.gates.find((g) => g.code === detail.data?.current_gate)?.order ?? 0;
  const dueGateOptions = (ref.data?.gates ?? [])
    .filter((g) => g.order >= currentOrder)
    .map((g) => ({ code: g.code, short: g.short }));

  const busyId = patch.isPending ? patch.variables?.id : undefined;
  const allShownIds = (list ?? []).map((i) => i.id);

  if (detail.data && !detail.data.assessment_launched)
    return (
      <EmptyState message="The assessment has not been launched yet, so there are no checklist items. Confirm scope from the header to launch it." />
    );

  const data = items.data;
  const tier = detail.data?.risk_tier;
  const dialogItem = dialog && dialog.kind !== 'bulk-na' ? dialog.item : null;

  return (
    <>
      <AssessmentFilters
        values={values}
        update={update}
        clear={clear}
        activeCount={activeCount}
        hasAiPlaybook={!!detail.data?.requires_tiering}
      />

      {data && (
        <GateSummaryBar
          transitionId={transitionId}
          gateShort={gateShort(data.gate)}
          summary={data.summary}
        />
      )}

      {data && data.excluded_count > 0 && !values.excluded && (
        <Body1 className={s.note}>
          {plural(data.excluded_by_tier_count || data.excluded_count, 'item')} not applicable
          {data.excluded_by_tier_count && tier ? ` for Tier ${tier}` : ''}{' '}
          <Link as="button" onClick={() => update({ excluded: true })}>
            (view)
          </Link>
        </Body1>
      )}

      {isFocal && selected.size > 0 && (
        <div className={s.bulk} role="region" aria-label="Bulk actions">
          <Body1>{plural(selected.size, 'item')} selected</Body1>
          <Select
            aria-label="Set owner for selected items"
            value={bulkOwner}
            onChange={(_, d) => setBulkOwner(d.value)}
          >
            <option value="">Set owner...</option>
            {(users.data ?? []).map((u) => (
              <option key={u.id} value={u.id}>
                {u.name}
              </option>
            ))}
          </Select>
          <Button
            disabled={!bulkOwner || bulk.isPending}
            onClick={() => runBulk({ owner_user_id: bulkOwner })}
          >
            Apply owner
          </Button>
          <Button disabled={bulk.isPending} onClick={() => setDialog({ kind: 'bulk-na' })}>
            Mark N/A
          </Button>
          <Button appearance="subtle" onClick={() => setSelected(new Set())}>
            Clear selection
          </Button>
        </div>
      )}
      {isFocal && selected.size === 0 && allShownIds.length > 0 && (
        <Button
          appearance="subtle"
          size="small"
          style={{ marginBottom: 8 }}
          onClick={() => setSelected(new Set(allShownIds))}
        >
          Select all {allShownIds.length} shown
        </Button>
      )}

      {items.isPending ? (
        <LoadingState rows={8} />
      ) : items.error ? (
        <ErrorState error={items.error} />
      ) : groups.length === 0 ? (
        <EmptyState
          message="No checklist items match these filters."
          action={activeCount > 0 ? <Button onClick={clear}>Clear filters</Button> : undefined}
        />
      ) : (
        <div className={s.scroller}>
          <div className={s.inner} role="table" aria-label="Checklist items">
            <div className={s.head} role="row">
              <span />
              <span />
              <span>ID</span>
              <span>Item</span>
              <span>Source</span>
              <span>Lens</span>
              <span>Owner</span>
              <span>Status</span>
              <span>Severity</span>
              <span>DE</span>
              <span>Evid.</span>
              <span>Updated by</span>
              <span />
            </div>
            {groups.map((g) => {
              const hidden = isCollapsed(g);
              return (
                <div key={g.gate} role="rowgroup">
                  <div className={s.gateHead}>
                    <Button
                      appearance="transparent"
                      size="small"
                      icon={hidden ? <ChevronRight20Regular /> : <ChevronDown20Regular />}
                      aria-expanded={!hidden}
                      onClick={() => setCollapsed((c) => ({ ...c, [g.gate]: !hidden }))}
                    >
                      {g.short}
                    </Button>
                    <Caption1>{plural(g.count, 'item')} due at this gate</Caption1>
                  </div>
                  {!hidden &&
                    g.lenses.map((l) => (
                      <div key={l.lens}>
                        <div className={mergeClasses(s.lensHead)}>
                          <LensChip lens={l.lens as Lens} />
                          <Caption1>{plural(l.items.length, 'item')}</Caption1>
                        </div>
                        {l.items.map((it) => (
                          <ItemRow
                            key={it.id}
                            item={it}
                            transitionId={transitionId}
                            selectable={isFocal}
                            selected={selected.has(it.id)}
                            highlighted={it.item_id === values.item}
                            autoOpen={it.item_id === values.item}
                            busy={busyId === it.id}
                            deOptions={deOptions}
                            perms={perms}
                            onSelect={onSelect}
                            onStatus={onStatus}
                            onDesignEffectiveness={onDe}
                          />
                        ))}
                      </div>
                    ))}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {dialog?.kind === 'gap' && (
        <GapDialog
          title={`${dialog.status}: ${dialog.item.item_id}`}
          status={dialog.status}
          initialSeverity={dialog.item.gap_severity}
          initialNote={dialog.item.note}
          busy={patch.isPending}
          onClose={() => setDialog(null)}
          onSubmit={(body) => doPatch(dialog.item, body)}
        />
      )}
      {dialog?.kind === 'na' && dialogItem && (
        <NaDialog
          title={`Mark ${dialogItem.item_id} as not applicable`}
          busy={patch.isPending}
          onClose={() => setDialog(null)}
          onSubmit={(reason) => doPatch(dialogItem, { status: dialog.status, na_reason: reason })}
        />
      )}
      {dialog?.kind === 'condition' && (
        <ConditionDialog
          title={`Compliant with conditions: ${dialog.item.item_id}`}
          defaultOwnerId={dialog.item.owner?.id}
          gateOptions={dueGateOptions}
          busy={patch.isPending}
          onClose={() => setDialog(null)}
          onSubmit={(body) => doPatch(dialog.item, body)}
        />
      )}
      {dialog?.kind === 'bulk-na' && (
        <NaDialog
          title={`Mark ${plural(selected.size, 'item')} as not applicable`}
          busy={bulk.isPending}
          onClose={() => setDialog(null)}
          onSubmit={(reason) => runBulk({ mark_na: { reason } })}
        />
      )}
    </>
  );
}

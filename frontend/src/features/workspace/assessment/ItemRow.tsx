// One checklist row. Memoised so a 300-row list stays fast (only rows whose props change re-render).
import { memo, useState } from 'react';
import { useNavigate } from 'react-router';
import dayjs from 'dayjs';
import {
  Badge,
  Button,
  Caption1,
  Checkbox,
  Menu,
  MenuItem,
  MenuList,
  MenuPopover,
  MenuTrigger,
  Select,
  Tooltip,
  makeStyles,
  mergeClasses,
  tokens,
} from '@fluentui/react-components';
import {
  ChevronDown20Regular,
  ChevronRight20Regular,
  MoreHorizontal20Regular,
} from '@fluentui/react-icons';
import { ActorBadge } from '../../../components/ActorBadge';
import { LensChip } from '../../../components/LensChip';
import type { ActorType, Lens } from '../../../theme/tokens';
import { useReference } from '../../reference/api';
import {
  colorForOption,
  itemStatusList,
  optionLabelFrom,
  useOptionLabel,
} from '../../reference/options';
import type { ItemOut } from '../api';
import { ROW_GRID, STICKY } from './rowLayout';

const useStyles = makeStyles({
  row: {
    display: 'grid',
    gridTemplateColumns: ROW_GRID,
    alignItems: 'center',
    columnGap: tokens.spacingHorizontalXS,
    padding: `${tokens.spacingVerticalXS} ${tokens.spacingHorizontalS} ${tokens.spacingVerticalXS} 0`,
    backgroundColor: tokens.colorNeutralBackground1,
    borderBottom: `1px solid ${tokens.colorNeutralStroke2}`,
  },
  highlight: {
    backgroundColor: tokens.colorPaletteYellowBackground1,
    outline: `2px solid ${tokens.colorPaletteYellowBorderActive}`,
  },
  excluded: { color: tokens.colorNeutralForeground3 },
  title: { display: 'flex', flexDirection: 'column', gap: '2px', minWidth: 0 },
  titleText: { overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' },
  cell: { minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' },
  marks: { display: 'flex', gap: tokens.spacingHorizontalXS, flexWrap: 'wrap' },
  detail: {
    display: 'grid',
    gridTemplateColumns: 'max-content 1fr',
    gap: `${tokens.spacingVerticalXS} ${tokens.spacingHorizontalL}`,
    padding: tokens.spacingVerticalM,
    paddingLeft: '150px',
    backgroundColor: tokens.colorNeutralBackground2,
    borderBottom: `1px solid ${tokens.colorNeutralStroke2}`,
  },
  label: { color: tokens.colorNeutralForeground3 },
  updated: { display: 'flex', flexDirection: 'column', gap: '2px', alignItems: 'flex-start' },
});

export interface RowPermissions {
  permissions: readonly string[];
  denied: Readonly<Record<string, string>>;
}

export interface ItemRowProps {
  item: ItemOut;
  transitionId: string;
  selectable: boolean;
  selected: boolean;
  highlighted: boolean;
  autoOpen: boolean;
  busy: boolean;
  deOptions: readonly string[];
  perms: RowPermissions;
  onSelect: (id: number, checked: boolean) => void;
  onStatus: (item: ItemOut, status: string) => void;
  onDesignEffectiveness: (item: ItemOut, value: string) => void;
}

function ItemRowImpl(p: ItemRowProps) {
  const s = useStyles();
  const optionLabel = useOptionLabel();
  const navigate = useNavigate();
  const { item } = p;
  const { data: reference } = useReference();
  const sourceLabel =
    reference?.checklists?.find((c) => c.code === item.source)?.label ?? item.source;
  const [open, setOpen] = useState(p.autoOpen);
  const excluded = item.applicability === 'Not applicable';
  const base = `/transitions/${encodeURIComponent(p.transitionId)}`;
  const pid = encodeURIComponent(item.item_id);
  const go = (path: string) => navigate(`${base}/${path}`);
  const can = (perm: string) => p.perms.permissions.includes(perm);
  const menuItem = (perm: string, label: string, path: string) => (
    <MenuItem
      key={label}
      disabled={!can(perm)}
      secondaryContent={can(perm) ? undefined : (p.perms.denied[perm] ?? 'Not permitted')}
      onClick={() => go(path)}
    >
      {label}
    </MenuItem>
  );

  const statusSelect = (
    <Select
      size="small"
      aria-label={`Status of ${item.item_id}`}
      value={item.status}
      disabled={!item.can_edit || p.busy}
      title={item.can_edit ? undefined : (item.edit_denied_reason ?? undefined)}
      onChange={(_, d) => d.value !== item.status && p.onStatus(item, d.value)}
    >
      {item.allowed_statuses.map((st) => (
        <option key={st} value={st}>
          {optionLabel(itemStatusList(item.lens), st)}
        </option>
      ))}
    </Select>
  );

  return (
    <>
      <div
        id={`item-${item.item_id}`}
        className={mergeClasses(s.row, p.highlighted && s.highlight, excluded && s.excluded)}
        role="row"
      >
        <div style={STICKY.c1}>
          {p.selectable && (
            <Checkbox
              aria-label={`Select ${item.item_id}`}
              checked={p.selected}
              onChange={(_, d) => p.onSelect(item.id, !!d.checked)}
            />
          )}
        </div>
        <Button
          appearance="subtle"
          size="small"
          icon={open ? <ChevronDown20Regular /> : <ChevronRight20Regular />}
          style={STICKY.c2}
          aria-expanded={open}
          aria-label={open ? `Collapse ${item.item_id}` : `Expand ${item.item_id}`}
          onClick={() => setOpen((o) => !o)}
        />
        <strong style={STICKY.c3}>{item.item_id}</strong>
        <div className={s.title} style={STICKY.c4}>
          <span className={s.titleText} title={item.title}>
            {item.title}
          </span>
          <div className={s.marks}>
            {item.tier_to_confirm && (
              <Badge size="small" appearance="tint" color="warning">
                tier to confirm
              </Badge>
            )}
            {item.lens_is_suggested && (
              <Badge size="small" appearance="tint" color="informative">
                lens suggested
              </Badge>
            )}
            {excluded && (
              <Badge size="small" appearance="outline">
                excluded{item.excluded_by ? ` by ${item.excluded_by.replace('_', ' ')}` : ''}
              </Badge>
            )}
            {item.covered && (
              <Badge size="small" appearance="tint" color="success">
                {item.exception_status === 'Approved' && !item.open_condition_id
                  ? `covered by approved exception${item.exception_ref ? ` ${item.exception_ref}` : ''}`
                  : `covered by condition${item.open_condition_id ? ` ${item.open_condition_id}` : ''}`}
              </Badge>
            )}
          </div>
        </div>
        <Badge
          appearance="outline"
          shape="rounded"
          size="small"
          title={sourceLabel}
          style={{
            maxWidth: '100%',
            display: 'block',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
          }}
        >
          {sourceLabel}
        </Badge>
        <LensChip lens={item.lens as Lens} />
        <Caption1 className={s.cell} title={item.owner?.name ?? 'Unassigned'}>
          {item.owner?.name ?? 'Unassigned'}
        </Caption1>
        <div style={STICKY.status}>
          {item.can_edit ? (
            statusSelect
          ) : (
            <Tooltip
              content={item.edit_denied_reason ?? 'You cannot edit this item'}
              relationship="description"
            >
              <span>{statusSelect}</span>
            </Tooltip>
          )}
        </div>
        <div>
          {item.gap_severity && (
            <Badge
              appearance="tint"
              color={colorForOption(reference, 'severities', item.gap_severity)}
            >
              {optionLabelFrom(reference, 'severities', item.gap_severity)}
            </Badge>
          )}
        </div>
        <div>
          {item.lens === 'Compliance' && (
            <Select
              size="small"
              aria-label={`Design effectiveness of ${item.item_id}`}
              value={item.design_effectiveness ?? '–'}
              disabled={!item.can_edit || p.busy}
              title={item.can_edit ? undefined : (item.edit_denied_reason ?? undefined)}
              onChange={(_, d) => p.onDesignEffectiveness(item, d.value)}
            >
              {p.deOptions.map((o) => (
                <option key={o} value={o}>
                  {o}
                </option>
              ))}
            </Select>
          )}
        </div>
        <Button
          appearance="transparent"
          size="small"
          aria-label={`${item.evidence_count} evidence for ${item.item_id}`}
          onClick={() => go(`evidence?item=${pid}`)}
        >
          {item.evidence_count}
        </Button>
        <div className={s.updated}>
          <Caption1>
            {item.last_updated_by?.name ?? '–'} · {dayjs(item.updated_at).format('D MMM HH:mm')}
          </Caption1>
          <ActorBadge actor={item.last_updated_source as ActorType} />
        </div>
        <Menu>
          <MenuTrigger disableButtonEnhancement>
            <Button
              appearance="subtle"
              size="small"
              icon={<MoreHorizontal20Regular />}
              aria-label={`Actions for ${item.item_id}`}
            />
          </MenuTrigger>
          <MenuPopover>
            <MenuList>
              {menuItem('manage_evidence', 'Add evidence', `evidence?item=${pid}&new=1`)}
              {menuItem('manage_actions', 'Create action', `gaps?new=1&item=${pid}`)}
              {menuItem('manage_conditions', 'Add condition', `conditions?new=1&item=${pid}`)}
              {item.lens === 'Compliance' &&
                menuItem(
                  'request_exception',
                  'Request exception',
                  `conditions?exception=1&item=${pid}`,
                )}
              <MenuItem onClick={() => go(`activity?entity=TransitionItem&entityId=${item.id}`)}>
                View audit
              </MenuItem>
            </MenuList>
          </MenuPopover>
        </Menu>
      </div>
      {open && (
        <div className={s.detail}>
          <span className={s.label}>Item</span>
          <span>{item.title}</span>
          <span className={s.label}>Description</span>
          <span>{item.description || '–'}</span>
          {item.detail && (
            <>
              <span className={s.label}>Detail</span>
              <span>{item.detail}</span>
            </>
          )}
          <span className={s.label}>Source</span>
          <span>
            {item.source_label}
            {item.source_sheet ? ` · sheet ${item.source_sheet}` : ''}
            {item.source_cell ? ` · cell ${item.source_cell}` : ''}
          </span>
          <span className={s.label}>Category</span>
          <span>
            {item.category} · {item.kind} · due {item.gate_short} · {item.tier_label}
          </span>
          {item.note && (
            <>
              <span className={s.label}>Note</span>
              <span>{item.note}</span>
            </>
          )}
          {item.na_reason && (
            <>
              <span className={s.label}>N/A reason</span>
              <span>{item.na_reason}</span>
            </>
          )}
          {item.open_condition_id && (
            <>
              <span className={s.label}>Condition</span>
              <span>{item.open_condition_id} (open)</span>
            </>
          )}
          {item.exception_ref && (
            <>
              <span className={s.label}>Exception</span>
              <span>
                {item.exception_ref}
                {item.exception_status ? ` · ${item.exception_status}` : ''}
              </span>
            </>
          )}
          {item.linked_module && (
            <>
              <span className={s.label}>Linked module</span>
              <span>{item.linked_module}</span>
            </>
          )}
        </div>
      )}
    </>
  );
}

export const ItemRow = memo(ItemRowImpl);

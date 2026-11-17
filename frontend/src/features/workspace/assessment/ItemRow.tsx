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
import type { ItemOut } from '../api';

export const ROW_GRID =
  '32px 28px 84px minmax(260px, 1fr) 96px 104px 130px 190px 80px 70px 64px 170px 40px';

const useStyles = makeStyles({
  row: {
    display: 'grid',
    gridTemplateColumns: ROW_GRID,
    alignItems: 'center',
    columnGap: tokens.spacingHorizontalS,
    padding: `${tokens.spacingVerticalXS} ${tokens.spacingHorizontalS}`,
    borderBottom: `1px solid ${tokens.colorNeutralStroke2}`,
  },
  highlight: {
    backgroundColor: tokens.colorPaletteYellowBackground1,
    outline: `2px solid ${tokens.colorPaletteYellowBorderActive}`,
  },
  excluded: { color: tokens.colorNeutralForeground3 },
  title: { display: 'flex', flexDirection: 'column', gap: '2px', minWidth: 0 },
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

const SOURCE_LABEL: Record<string, string> = {
  FRAMEWORK: 'Framework',
  AI_PLAYBOOK: 'AI playbook',
  PORTFOLIO: 'Portfolio',
  COMMON: 'Common',
};

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

const SEVERITY_COLOR = { Critical: 'danger', Major: 'warning', Minor: 'informative' } as const;

function ItemRowImpl(p: ItemRowProps) {
  const s = useStyles();
  const navigate = useNavigate();
  const { item } = p;
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
      onChange={(_, d) => d.value !== item.status && p.onStatus(item, d.value)}
    >
      {item.allowed_statuses.map((st) => (
        <option key={st} value={st}>
          {st}
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
        <div>
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
          aria-expanded={open}
          aria-label={open ? `Collapse ${item.item_id}` : `Expand ${item.item_id}`}
          onClick={() => setOpen((o) => !o)}
        />
        <strong>{item.item_id}</strong>
        <div className={s.title}>
          <span>{item.title}</span>
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
                covered by condition
              </Badge>
            )}
          </div>
        </div>
        <Badge appearance="outline" shape="rounded">
          {SOURCE_LABEL[item.source] ?? item.source}
        </Badge>
        <LensChip lens={item.lens as Lens} />
        <Caption1>{item.owner?.name ?? 'Unassigned'}</Caption1>
        <div>
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
            <Badge appearance="tint" color={SEVERITY_COLOR[item.gap_severity]}>
              {item.gap_severity}
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

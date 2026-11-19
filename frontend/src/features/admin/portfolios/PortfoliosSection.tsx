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
import type { PortfolioAdmin } from '../../../api/types';
import { useLeaveGuard } from '../../ocet/useLeaveGuard';
import { usePortfoliosAdmin, useUpdatePortfolio } from '../catalogApi';
import { DisabledReason } from '../components/DisabledReason';
import { useDiscardGuard } from '../components/DiscardGuard';
import { SectionIntro } from '../components/SectionIntro';
import { UsedByBadge } from '../components/UsedByBadge';
import { useSuccessToast } from '../useSavedToast';
import { AddPortfolioDialog } from './AddPortfolioDialog';
import { GoldenSetPanel } from './GoldenSetPanel';
import { PortfolioFields } from './PortfolioFields';
import { draftFromPortfolio, draftToBody, type PortfolioDraft } from './portfolioDraft';

const useStyles = makeStyles({
  row: { cursor: 'pointer' },
  selected: { backgroundColor: tokens.colorBrandBackground2 },
  scroll: { overflowX: 'auto' },
  clamp: {
    display: '-webkit-box',
    WebkitLineClamp: '2',
    WebkitBoxOrient: 'vertical',
    overflow: 'hidden',
  },
  bar: { display: 'flex', gap: tokens.spacingHorizontalM, alignItems: 'center', flexWrap: 'wrap' },
});

/** Edit one portfolio. Reports unsaved edits through `onDirty`. */
function PortfolioPanel(props: {
  portfolio: PortfolioAdmin;
  isLastActive: boolean;
  onDirty: (dirty: boolean) => void;
}) {
  const s = useStyles();
  const { portfolio } = props;
  const update = useUpdatePortfolio();
  const ok = useSuccessToast();
  const [draft, setDraft] = useState<PortfolioDraft>(() => draftFromPortfolio(portfolio));
  const [active, setActive] = useState(portfolio.active);
  const dirty =
    JSON.stringify([draft, active]) !==
    JSON.stringify([draftFromPortfolio(portfolio), portfolio.active]);
  const { onDirty } = props;
  useEffect(() => {
    onDirty(dirty);
    return () => onDirty(false); // an unmounted editor holds no unsaved edits
  }, [dirty, onDirty]);

  const save = () =>
    update.mutate(
      { name: portfolio.name, body: { ...draftToBody(draft), active } },
      { onSuccess: () => ok('Saved - applies to new transitions') },
    );
  const lastActiveReason =
    props.isLastActive && active ? 'At least one portfolio must stay active.' : null;

  return (
    <SectionCard title={`Edit ${portfolio.label || portfolio.name}`}>
      <div className={s.bar}>
        <Field label="Name and code (cannot change)">
          <code>
            {portfolio.name} / {portfolio.code}
          </code>
        </Field>
        <UsedByBadge count={portfolio.used_by} noun="transitions" />
      </div>
      <PortfolioFields draft={draft} onChange={(p) => setDraft((d) => ({ ...d, ...p }))} />
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
            setDraft(draftFromPortfolio(portfolio));
            setActive(portfolio.active);
          }}
        >
          Discard changes
        </Button>
      </div>
    </SectionCard>
  );
}

/** Admin section 3: the portfolios, and the golden set of each. */
export function PortfoliosSection() {
  const s = useStyles();
  const q = usePortfoliosAdmin();
  const [picked, setPicked] = useState('');
  const [adding, setAdding] = useState(false);
  const [panelDirty, setPanelDirty] = useState(false);
  const [goldenDirty, setGoldenDirty] = useState(false);
  const dirty = panelDirty || goldenDirty;
  const { guard, dialog } = useDiscardGuard(dirty);
  const leaveDialog = useLeaveGuard(dirty);

  const rows = q.data ?? [];
  const selected = rows.find((p) => p.name === picked) ?? rows[0];
  const activeCount = rows.filter((p) => p.active).length;

  return (
    <>
      <SectionIntro>
        Add or change portfolios and the golden set of extra items each one brings. New transitions
        use it from now on; existing transitions keep what they have.
      </SectionIntro>
      <SectionCard
        title="Portfolios"
        actions={
          <Button appearance="primary" onClick={() => guard(() => setAdding(true))}>
            Add portfolio
          </Button>
        }
      >
        {q.isLoading ? (
          <LoadingState rows={4} />
        ) : q.isError ? (
          <ErrorState error={q.error} onRetry={() => void q.refetch()} />
        ) : !selected ? (
          <EmptyState message="No portfolios yet. Add the first one." />
        ) : (
          <div className={s.scroll}>
            <Table
              aria-label="Portfolios"
              size="small"
              style={{ tableLayout: 'auto', minWidth: '100%' }}
            >
              <TableHeader>
                <TableRow>
                  <TableHeaderCell>Portfolio</TableHeaderCell>
                  <TableHeaderCell>Focus areas</TableHeaderCell>
                  <TableHeaderCell>Sites</TableHeaderCell>
                  <TableHeaderCell>Golden set</TableHeaderCell>
                  <TableHeaderCell>Used by</TableHeaderCell>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map((p) => (
                  <TableRow
                    key={p.name}
                    className={mergeClasses(s.row, p.name === selected.name && s.selected)}
                    aria-selected={p.name === selected.name}
                    tabIndex={0}
                    onClick={() => guard(() => setPicked(p.name))}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault();
                        guard(() => setPicked(p.name));
                      }
                    }}
                  >
                    <TableCell>
                      <div>{p.label || p.name}</div>
                      <code>{p.code}</code>
                      {!p.active && (
                        <Badge appearance="tint" color="subtle" style={{ marginLeft: 6 }}>
                          inactive
                        </Badge>
                      )}
                    </TableCell>
                    <TableCell>
                      <div className={s.clamp} title={p.focus_areas.join(', ')}>
                        {p.focus_areas.join(', ') || '-'}
                      </div>
                    </TableCell>
                    <TableCell>{p.requires_sites ? p.sites_label || 'Yes' : 'No'}</TableCell>
                    <TableCell>{p.golden_set_count} items</TableCell>
                    <TableCell>{p.used_by}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </SectionCard>
      {selected && (
        <>
          <PortfolioPanel
            key={`${selected.name}-${JSON.stringify(selected)}`}
            portfolio={selected}
            isLastActive={activeCount <= 1}
            onDirty={setPanelDirty}
          />
          <GoldenSetPanel
            key={selected.name}
            portfolio={selected.name}
            title={selected.label || selected.name}
            onDirty={setGoldenDirty}
          />
        </>
      )}
      {adding && <AddPortfolioDialog onCreated={setPicked} onClose={() => setAdding(false)} />}
      {dialog}
      {leaveDialog}
    </>
  );
}

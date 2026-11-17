import { Link, useNavigate, useParams } from 'react-router';
import {
  Badge,
  Body1,
  Button,
  Caption1,
  MessageBar,
  MessageBarBody,
  Select,
  Subtitle2,
  Table,
  TableBody,
  TableCell,
  TableHeader,
  TableHeaderCell,
  TableRow,
  Toast,
  ToastBody,
  ToastTitle,
  Tooltip,
  makeStyles,
  tokens,
  useToastController,
} from '@fluentui/react-components';
import { LockClosed16Regular } from '@fluentui/react-icons';
import { PageHeader } from '../../components/PageHeader';
import { SectionCard } from '../../components/SectionCard';
import { LoadingState } from '../../components/LoadingState';
import { ErrorState } from '../../components/ErrorState';
import { EmptyState } from '../../components/EmptyState';
import { LensChip } from '../../components/LensChip';
import { AiBadge } from '../../components/AiBadge';
import { ActorBadge } from '../../components/ActorBadge';
import type { Me } from '../../api/types';
import type { Lens } from '../../theme/tokens';
import { TOASTER_ID, useApiErrorToast } from '../../hooks/useApiErrorToast';
import { useMe } from '../users/api';
import { useTransition } from '../transition/api';
import {
  useLaunchAssessment,
  useScope,
  useUpdateScope,
  type Scope,
  type ScopeDecision,
  type ScopeRow,
} from './api';

const useStyles = makeStyles({
  stack: { display: 'flex', flexDirection: 'column', gap: tokens.spacingVerticalL },
  counts: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))',
    gap: tokens.spacingHorizontalM,
  },
  tile: {
    display: 'flex',
    flexDirection: 'column',
    padding: tokens.spacingVerticalM,
    border: `1px solid ${tokens.colorNeutralStroke2}`,
    borderRadius: tokens.borderRadiusMedium,
    backgroundColor: tokens.colorNeutralBackground1,
  },
  tileNum: { fontSize: tokens.fontSizeHero700, fontWeight: tokens.fontWeightSemibold },
  list: { margin: 0, paddingLeft: '20px' },
  head: { display: 'flex', alignItems: 'center', gap: tokens.spacingHorizontalS },
  tableWrap: { overflowX: 'auto' },
  lock: { display: 'inline-flex', alignItems: 'center', gap: tokens.spacingHorizontalXS },
  lensCell: {
    display: 'flex',
    alignItems: 'center',
    gap: tokens.spacingHorizontalXS,
    flexWrap: 'wrap',
  },
});

const LENSES: string[] = ['Business', 'Technical', 'Compliance'];

function Tile(props: { label: string; value: number | string; hint?: string }) {
  const s = useStyles();
  return (
    <div className={s.tile}>
      <Caption1>{props.label}</Caption1>
      <span className={s.tileNum}>{props.value}</span>
      {props.hint && <Caption1>{props.hint}</Caption1>}
    </div>
  );
}

function ScopeTable(props: {
  title: string;
  rows: ScopeRow[];
  canEdit: boolean;
  denied: string;
  pending: boolean;
  onChange: (row: ScopeRow, applies: ScopeDecision['applies']) => void;
}) {
  const s = useStyles();
  return (
    <SectionCard title={props.title}>
      {props.rows.length === 0 ? (
        <EmptyState message="No requirements in this list." />
      ) : (
        <div className={s.tableWrap}>
          <Table aria-label={props.title} size="small">
            <TableHeader>
              <TableRow>
                <TableHeaderCell>ID</TableHeaderCell>
                <TableHeaderCell>Requirement</TableHeaderCell>
                <TableHeaderCell>Type</TableHeaderCell>
                <TableHeaderCell>Gate</TableHeaderCell>
                <TableHeaderCell>Owner hint</TableHeaderCell>
                <TableHeaderCell>Lens</TableHeaderCell>
                <TableHeaderCell>Applies?</TableHeaderCell>
              </TableRow>
            </TableHeader>
            <TableBody>
              {props.rows.map((r) => {
                const select = (
                  <Select
                    size="small"
                    aria-label={`Applies for ${r.id}`}
                    value={r.applies}
                    disabled={!props.canEdit || props.pending}
                    onChange={(_, d) => props.onChange(r, d.value as ScopeDecision['applies'])}
                  >
                    <option>Yes</option>
                    <option>No</option>
                    <option>To confirm</option>
                  </Select>
                );
                return (
                  <TableRow key={r.id}>
                    <TableCell>{r.id}</TableCell>
                    <TableCell>
                      {r.requirement}
                      {r.reason && <Caption1 block>{r.reason}</Caption1>}
                    </TableCell>
                    <TableCell>{r.type}</TableCell>
                    <TableCell>{r.gate_short}</TableCell>
                    <TableCell>{r.owner_hint}</TableCell>
                    <TableCell>
                      <div className={s.lensCell}>
                        {LENSES.includes(r.lens) ? (
                          <LensChip lens={r.lens as Lens} />
                        ) : (
                          <Badge appearance="outline">{r.lens}</Badge>
                        )}
                        {r.lens_is_suggested && (
                          <Badge appearance="tint" size="small" color="informative">
                            lens suggested
                          </Badge>
                        )}
                      </div>
                    </TableCell>
                    <TableCell>
                      {r.locked ? (
                        <Tooltip
                          content="Mandatory requirement – always applies and cannot be changed"
                          relationship="description"
                        >
                          <span className={s.lock} tabIndex={0}>
                            <LockClosed16Regular aria-label="Locked" /> Yes
                          </span>
                        </Tooltip>
                      ) : props.canEdit ? (
                        select
                      ) : (
                        <Tooltip content={props.denied} relationship="description">
                          <span>{select}</span>
                        </Tooltip>
                      )}
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </div>
      )}
    </SectionCard>
  );
}

function ScopeContent(props: {
  id: string;
  scope: Scope;
  me: Me;
  requiresTiering: boolean;
  tierProposed: boolean;
}) {
  const { id, scope, me } = props;
  const s = useStyles();
  const navigate = useNavigate();
  const showError = useApiErrorToast();
  const { dispatchToast } = useToastController(TOASTER_ID);
  const update = useUpdateScope(id);
  const launch = useLaunchAssessment(id);

  const canEdit = me.permissions.includes('confirm_scope');
  const denied = me.denied_reasons['confirm_scope'] ?? 'You cannot confirm scope';
  const all = [...scope.golden_set, ...scope.common];
  const reqName = (itemId: string) => all.find((r) => r.id === itemId)?.requirement ?? itemId;

  const change = (row: ScopeRow, applies: ScopeDecision['applies']) =>
    update.mutate(
      { decisions: [{ item_id: row.id, applies }], source: 'human' },
      { onError: showError },
    );

  const acceptAll = () =>
    update.mutate(
      {
        decisions: scope.recommendations.map((r) => ({
          item_id: r.item_id,
          applies: r.recommendation,
          reason: r.reason,
        })),
        source: 'orion_recommendation',
      },
      {
        onSuccess: () =>
          dispatchToast(
            <Toast>
              <ToastTitle>Orion recommendations accepted</ToastTitle>
            </Toast>,
            { intent: 'success' },
          ),
        onError: showError,
      },
    );

  const doLaunch = () =>
    launch.mutate(undefined, {
      onSuccess: (r) => {
        dispatchToast(
          <Toast>
            <ToastTitle>Readiness assessment launched</ToastTitle>
            <ToastBody>
              {Object.entries(r.counts)
                .map(([k, v]) => `${k.replace(/_/g, ' ')}: ${v}`)
                .join(' · ')}
            </ToastBody>
          </Toast>,
          { intent: 'success', timeout: 8000 },
        );
        navigate(r.redirect);
      },
      onError: showError,
    });

  const launchReason = !canEdit
    ? denied
    : scope.launched
      ? 'Assessment already launched'
      : props.requiresTiering && !props.tierProposed
        ? 'Propose a tier before launching'
        : null;
  const launchBtn = (
    <Button appearance="primary" disabled={!!launchReason || launch.isPending} onClick={doLaunch}>
      {launch.isPending ? 'Launching…' : 'Launch readiness assessment'}
    </Button>
  );
  const c = scope.counts;

  return (
    <div className={s.stack}>
      {scope.tier_banner && (
        <MessageBar intent={scope.tier_banner.status === 'Confirmed' ? 'success' : 'warning'}>
          <MessageBarBody>
            {scope.tier_banner.text} <Link to={`/transitions/${id}/tiering`}>Open tiering</Link>
          </MessageBarBody>
        </MessageBar>
      )}
      {scope.launched && (
        <MessageBar intent="info">
          <MessageBarBody>
            Assessment launched – applicability changes below apply to the checklist items.{' '}
            <Link to={`/transitions/${id}/assessment`}>Open assessment</Link>
          </MessageBarBody>
        </MessageBar>
      )}
      <SectionCard title={`${scope.portfolio} operating set-up`}>
        {scope.focus_areas.length === 0 ? (
          <Body1>No focus areas defined for this portfolio.</Body1>
        ) : (
          <ul className={s.list}>
            {scope.focus_areas.map((f) => (
              <li key={f}>{f}</li>
            ))}
          </ul>
        )}
      </SectionCard>

      <div className={s.counts} aria-label="Scope summary">
        <Tile label="Framework" value={c.framework} />
        <Tile
          label="AI Playbook"
          value={c.ai_applicable}
          hint={`${c.ai_excluded} excluded by tier`}
        />
        <Tile
          label="Golden set"
          value={c.golden_set_applies}
          hint={`${c.golden_set_to_confirm} to confirm`}
        />
        <Tile label="Common" value={c.common} />
        <Tile label="Total applicable" value={c.total} />
      </div>

      <SectionCard
        title="Orion agent – recommended applicability"
        actions={
          <span className={s.head}>
            <AiBadge />
            <ActorBadge actor="Orion agent" />
          </span>
        }
      >
        {scope.recommendations.length === 0 ? (
          <Body1>No open "To confirm" rows – nothing to recommend.</Body1>
        ) : (
          <>
            <ul className={s.list}>
              {scope.recommendations.map((r) => (
                <li key={r.item_id}>
                  <strong>
                    {r.item_id} {reqName(r.item_id)}
                  </strong>
                  : {r.recommendation} – {r.reason}
                </li>
              ))}
            </ul>
            <Caption1>
              Advisory only. Nothing changes until you accept; you can still edit every row.
            </Caption1>
            <div>
              {canEdit ? (
                <Button appearance="primary" disabled={update.isPending} onClick={acceptAll}>
                  Accept all recommendations
                </Button>
              ) : (
                <Tooltip content={denied} relationship="description">
                  <span>
                    <Button appearance="primary" disabled>
                      Accept all recommendations
                    </Button>
                  </span>
                </Tooltip>
              )}
            </div>
          </>
        )}
      </SectionCard>

      <ScopeTable
        title={`${scope.portfolio} golden set`}
        rows={scope.golden_set}
        canEdit={canEdit}
        denied={denied}
        pending={update.isPending}
        onChange={change}
      />
      <ScopeTable
        title="Common items"
        rows={scope.common}
        canEdit={canEdit}
        denied={denied}
        pending={update.isPending}
        onChange={change}
      />

      <div>
        {launchReason ? (
          <Tooltip content={launchReason} relationship="description">
            <span>{launchBtn}</span>
          </Tooltip>
        ) : (
          launchBtn
        )}
      </div>
    </div>
  );
}

/** Portfolio scope – FR-022 (spec 8.6): confirm applicability, then launch the assessment. */
export function ScopePage() {
  const { id } = useParams();
  const tq = useTransition(id);
  const sq = useScope(id ?? '');
  const me = useMe();
  const err = tq.error ?? sq.error ?? me.error;
  const t = tq.data;
  return (
    <>
      <PageHeader
        title="Portfolio scope"
        subtitle={
          t
            ? `${t.id} · ${t.name} · ${t.flavour_label}. Confirm applicability before launching the assessment.`
            : 'Confirm applicability before launching the assessment.'
        }
      />
      {err ? (
        <ErrorState error={err} />
      ) : !t || !sq.data || !me.data || !id ? (
        <LoadingState rows={6} />
      ) : (
        <>
          <Subtitle2 as="h2" style={{ display: 'none' }}>
            Scope
          </Subtitle2>
          <ScopeContent
            id={id}
            scope={sq.data}
            me={me.data}
            requiresTiering={t.requires_tiering}
            tierProposed={t.tier?.proposed_tier != null}
          />
        </>
      )}
    </>
  );
}

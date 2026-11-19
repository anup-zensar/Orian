import { useEffect, useState } from 'react';
import {
  Badge,
  Body1,
  Button,
  Caption1,
  Input,
  MessageBar,
  MessageBarActions,
  MessageBarBody,
  Popover,
  PopoverSurface,
  PopoverTrigger,
  Subtitle1,
  Switch,
  Tooltip,
  makeStyles,
  tokens,
} from '@fluentui/react-components';
import { Sparkle20Regular } from '@fluentui/react-icons';
import { AppLink } from '../../../components/AppLink';
import { RagChip } from '../../../components/RagChip';
import { useApiErrorToast } from '../../../hooks/useApiErrorToast';
import { daysLabel, formatDate, toRag } from '../../../lib/format';
import { useTransitionAccess, type TransitionDetail } from '../../transition/api';
import { useOrionPanel } from '../../orion/panelContext';
import { useUpdateTransition } from '../../intake/api';
import { useSetAutonomous } from '../api';
import { GateStepper } from './GateStepper';

const useStyles = makeStyles({
  root: {
    display: 'flex',
    flexDirection: 'column',
    gap: tokens.spacingVerticalM,
    marginBottom: tokens.spacingVerticalM,
  },
  top: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    gap: tokens.spacingHorizontalL,
    flexWrap: 'wrap',
  },
  chips: {
    display: 'flex',
    gap: tokens.spacingHorizontalS,
    flexWrap: 'wrap',
    marginTop: tokens.spacingVerticalXS,
    alignItems: 'center',
  },
  actions: {
    display: 'flex',
    gap: tokens.spacingHorizontalL,
    alignItems: 'center',
    flexWrap: 'wrap',
  },
  facts: {
    display: 'flex',
    gap: tokens.spacingHorizontalXXL,
    flexWrap: 'wrap',
    alignItems: 'center',
  },
  fact: { display: 'flex', flexDirection: 'column' },
  big: {
    fontSize: tokens.fontSizeHero700,
    lineHeight: tokens.lineHeightHero700,
    fontWeight: tokens.fontWeightSemibold,
  },
});

/** "Set date" link next to an empty Next decision (A-79): a small popover calling PATCH. */
function SetDecisionDate({ transitionId }: { transitionId: string }) {
  const [open, setOpen] = useState(false);
  const [value, setValue] = useState('');
  const update = useUpdateTransition(transitionId);
  const showError = useApiErrorToast();
  const save = () =>
    update.mutate(
      { next_decision_date: value },
      {
        onSuccess: () => setOpen(false),
        onError: showError,
      },
    );
  return (
    <Popover open={open} onOpenChange={(_, d) => setOpen(d.open)} positioning="below-start">
      <PopoverTrigger disableButtonEnhancement>
        <Button
          appearance="transparent"
          style={{
            minWidth: 0,
            padding: 0,
            height: 'auto',
            font: 'inherit',
            color: tokens.colorBrandForegroundLink,
          }}
        >
          Set date
        </Button>
      </PopoverTrigger>
      <PopoverSurface>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <Input
            type="date"
            aria-label="Next decision date"
            value={value}
            onChange={(_, d) => setValue(d.value)}
          />
          <Button appearance="primary" disabled={!value || update.isPending} onClick={save}>
            Save
          </Button>
        </div>
      </PopoverSurface>
    </Popover>
  );
}

/** Workspace header (spec 8.7): identity, flavour chips, gate stepper, readiness, decision, actions. */
export function WorkspaceHeader({ detail }: { detail: TransitionDetail }) {
  const s = useStyles();
  const orion = useOrionPanel();
  const showError = useApiErrorToast();
  const setAutonomous = useSetAutonomous(detail.id);

  useEffect(() => {
    document.title = `${detail.name} - Orion`;
  }, [detail.name]);

  const access = useTransitionAccess(detail.id);
  const can = access.can('toggle_autonomous');
  const reason = can
    ? 'Orion may auto-send chasers and reminders, never approval requests'
    : (access.reason('toggle_autonomous') ?? 'Only the OR focal can change autonomous mode');
  const tierLabel =
    detail.risk_tier != null ? `Tier ${detail.risk_tier} ${detail.tier_status ?? ''}`.trim() : null;
  const entryPath =
    detail.requires_tiering && !detail.tier?.confirmed_tier && !detail.tier?.proposed_tier
      ? 'tiering'
      : 'scope';
  const base = `/transitions/${encodeURIComponent(detail.id)}`;

  return (
    <header className={s.root}>
      <div className={s.top}>
        <div>
          <Subtitle1 as="h1">{detail.name}</Subtitle1>
          <div className={s.chips}>
            <Badge appearance="tint" color="informative">
              {detail.project_type}
            </Badge>
            <Badge appearance="outline">{detail.portfolio}</Badge>
            <Badge appearance="outline">
              {detail.region} / {detail.market}
            </Badge>
            {tierLabel && (
              <Badge
                appearance="tint"
                color={detail.tier_status === 'Confirmed' ? 'success' : 'warning'}
              >
                {tierLabel}
              </Badge>
            )}
            {detail.status === 'Closed' && (
              <Badge appearance="filled" color="subtle">
                Closed
              </Badge>
            )}
            <Caption1>{detail.id}</Caption1>
          </div>
        </div>
        <div className={s.actions}>
          <Tooltip content={reason} relationship="description">
            <span>
              <Switch
                label="Autonomous mode"
                checked={detail.autonomous_mode}
                disabled={!can || setAutonomous.isPending}
                onChange={(_, d) => setAutonomous.mutate(d.checked, { onError: showError })}
              />
            </span>
          </Tooltip>
          <Button
            icon={<Sparkle20Regular />}
            onClick={() => orion.open({ transitionId: detail.id })}
          >
            Ask Orion
          </Button>
        </div>
      </div>

      <GateStepper gates={detail.gates} />

      <div className={s.facts}>
        <div className={s.fact}>
          <Caption1>Overall readiness at {detail.current_gate_short}</Caption1>
          <span className={s.big}>
            {detail.assessment_launched ? `${detail.overall_readiness}%` : '–'}
          </span>
        </div>
        <RagChip
          rag={
            // A just-launched assessment is "Not started", not an alarm (nothing done or in progress).
            detail.assessment_launched &&
            detail.lenses.every((l) => l.done === 0 && l.in_progress === 0)
              ? 'Grey'
              : toRag(detail.rag)
          }
        />
        <div className={s.fact}>
          <Caption1>Next decision</Caption1>
          {detail.next_decision_date ? (
            <Body1>
              {formatDate(detail.next_decision_date)} ({daysLabel(detail.days_to_next_decision)})
            </Body1>
          ) : (
            <Body1>
              Not set
              {access.can('edit_transition') && detail.status !== 'Closed' && (
                <>
                  {' '}
                  <SetDecisionDate transitionId={detail.id} />
                </>
              )}
            </Body1>
          )}
        </div>
        <div className={s.fact}>
          <Caption1>OR focal</Caption1>
          <Body1>{detail.or_focal.name}</Body1>
        </div>
      </div>

      {detail.checklist_banner && (
        <MessageBar intent="warning">
          <MessageBarBody>{detail.checklist_banner}</MessageBarBody>
          <MessageBarActions>
            <AppLink to={`${base}/tiering`}>Review tier</AppLink>
          </MessageBarActions>
        </MessageBar>
      )}
      {!detail.assessment_launched && detail.status !== 'Closed' && (
        <MessageBar intent="info">
          <MessageBarBody>
            The readiness assessment has not been launched yet, so there are no checklist items.
          </MessageBarBody>
          <MessageBarActions>
            <AppLink to={`${base}/${entryPath}`}>
              {entryPath === 'tiering' ? 'Start tiering' : 'Confirm scope and launch'}
            </AppLink>
          </MessageBarActions>
        </MessageBar>
      )}
    </header>
  );
}

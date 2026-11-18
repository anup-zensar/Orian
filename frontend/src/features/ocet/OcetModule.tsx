import { ReturnFocusDialog } from '../../components/ReturnFocusDialog';
import React, { useState } from 'react';
import {
  Button,
  Caption1,
  Checkbox,
  DialogActions,
  DialogBody,
  DialogContent,
  DialogSurface,
  DialogTitle,
  MessageBar,
  MessageBarBody,
  Toast,
  ToastBody,
  ToastFooter,
  ToastTitle,
  Tooltip,
  makeStyles,
  tokens,
  useToastController,
} from '@fluentui/react-components';
import { Add16Regular } from '@fluentui/react-icons';
import { AiBadge } from '../../components/AiBadge';
import { AppLink } from '../../components/AppLink';
import { EmptyState } from '../../components/EmptyState';
import { ErrorState } from '../../components/ErrorState';
import { LoadingState } from '../../components/LoadingState';
import { SectionCard } from '../../components/SectionCard';
import { TOASTER_ID, useApiErrorToast } from '../../hooks/useApiErrorToast';
import { usePerm } from '../gates/usePerm';
import type { TabProps } from '../workspace/types';
import {
  useCreateOcet,
  useNewVersion,
  useOcet,
  useRequestInputs,
  useSaveLines,
  useSubmitVersion,
  type OcetOut,
} from './api';
import { CompareDialog } from './CompareDialog';
import { useSuccessToast } from '../admin/useSavedToast';
import { LinesGrid } from './LinesGrid';
import { fromServer, newLine, toInput, type EditLine } from './lineModel';
import { OcetHeader } from './OcetHeader';
import { SummaryCharts } from './SummaryCharts';
import { useLeaveGuard } from './useLeaveGuard';

const useStyles = makeStyles({
  root: { display: 'flex', flexDirection: 'column', gap: tokens.spacingVerticalL },
  bar: { display: 'flex', flexWrap: 'wrap', gap: tokens.spacingHorizontalS, alignItems: 'center' },
  orion: { display: 'flex', flexDirection: 'column', gap: tokens.spacingVerticalS },
  orionHead: { display: 'flex', alignItems: 'center', gap: tokens.spacingHorizontalS },
  reasons: { margin: 0, paddingLeft: '20px' },
});

function RequestInputsDialog(props: { data: OcetOut; transitionId: string; onClose: () => void }) {
  const { data } = props;
  const showError = useApiErrorToast();
  const { dispatchToast } = useToastController(TOASTER_ID);
  const mutation = useRequestInputs(props.transitionId, data.version.id);
  const candidates = data.lines.filter((l) => l.base_amount === null);
  const [picked, setPicked] = useState<number[]>(
    candidates
      .filter((l) => l.input_status === 'Missing' || l.input_status === 'Requested')
      .map((l) => l.id),
  );
  const toggle = (id: number, on: boolean) =>
    setPicked((p) => (on ? [...p, id] : p.filter((x) => x !== id)));
  const send = () =>
    mutation.mutate(picked, {
      onSuccess: (r) => {
        dispatchToast(
          <Toast>
            <ToastTitle>
              Inputs requested for {r.lines_requested.length} line
              {r.lines_requested.length === 1 ? '' : 's'}
            </ToastTitle>
            <ToastBody>
              Orion prepared {r.draft_ids.length} draft{r.draft_ids.length === 1 ? '' : 's'}.
              Nothing is sent until you review it.
            </ToastBody>
            <ToastFooter>
              <AppLink to="/drafts">Open drafts</AppLink>
            </ToastFooter>
          </Toast>,
          { intent: 'success', timeout: 10000 },
        );
        props.onClose();
      },
      onError: showError,
    });
  return (
    <ReturnFocusDialog open onOpenChange={(_, d) => !d.open && props.onClose()}>
      <DialogSurface>
        <DialogBody>
          <DialogTitle>Request inputs</DialogTitle>
          <DialogContent>
            <Caption1>
              Orion drafts one message per input owner with a link to this estimate.
            </Caption1>
            {candidates.length === 0 ? (
              <EmptyState message="Every line already has a base amount." />
            ) : (
              candidates.map((l) => (
                <div key={l.id}>
                  <Checkbox
                    checked={picked.includes(l.id)}
                    onChange={(_, d) => toggle(l.id, !!d.checked)}
                    label={`${l.description || l.category} (owner ${l.input_owner?.name ?? l.input_owner_role}, ${
                      l.input_status === 'Requested'
                        ? `requested ${l.requested_days} day${l.requested_days === 1 ? '' : 's'} ago`
                        : 'missing'
                    })`}
                  />
                </div>
              ))
            )}
          </DialogContent>
          <DialogActions>
            <Button onClick={props.onClose}>Cancel</Button>
            <Button
              appearance="primary"
              disabled={picked.length === 0 || mutation.isPending}
              onClick={send}
            >
              {picked.length > 0 ? `Request inputs (${picked.length})` : 'Request inputs'}
            </Button>
          </DialogActions>
        </DialogBody>
      </DialogSurface>
    </ReturnFocusDialog>
  );
}

function OcetBody({ data, transitionId }: { data: OcetOut; transitionId: string }) {
  const s = useStyles();
  const showError = useApiErrorToast();
  const notify = useSuccessToast();
  const edit = usePerm('edit_ocet', transitionId);
  const save = useSaveLines(transitionId, data.version.id);
  const submit = useSubmitVersion(transitionId, data.version.id);
  const newVersion = useNewVersion(transitionId);

  // null = no local edits: the grid shows the server lines. Reset after every successful save.
  const [edits, setEdits] = useState<EditLine[] | null>(null);
  const [removed, setRemoved] = useState<number[]>([]);
  const [compare, setCompare] = useState<{ from: number; to: number } | null>(null);
  const [requesting, setRequesting] = useState(false);

  const { version } = data;
  const editable = version.can_edit;
  const lines = edits ?? data.lines.map(fromServer);
  const dirty = edits !== null;
  const years = data.years;
  const leaveGuard = useLeaveGuard(dirty);

  const setLines = (next: EditLine[]) => setEdits(next);
  const onChange = (key: string, patch: Partial<EditLine>) =>
    setLines(lines.map((l) => (l.key === key ? { ...l, ...patch } : l)));
  const onRemove = (key: string) => {
    const l = lines.find((x) => x.key === key);
    if (l?.id != null) setRemoved((r) => [...r, l.id!]);
    setLines(lines.filter((x) => x.key !== key));
  };
  const onAdd = () =>
    setLines([
      ...lines,
      newLine(
        data.categories[0] ?? '',
        data.pricing_bases[0] ?? '',
        data.default_growth_pct[data.categories[0] ?? ''] ?? 0,
      ),
    ]);

  const lineProblems = (() => {
    const out: string[] = [];
    lines.forEach((l, i) => {
      const n = `Line ${i + 1}`;
      if (!l.description.trim()) out.push(`${n}: enter a description`);
      if (l.base_amount !== null && l.base_amount < 0)
        out.push(`${n}: base amount cannot be negative`);
      if (l.growth_pct < -100 || l.growth_pct > 1000)
        out.push(`${n}: growth must be between -100% and 1000%`);
      if (Object.keys(l.year_overrides).length > 0 && !l.override_reason.trim())
        out.push(`${n}: add a reason for the year overrides`);
    });
    return out;
  })();
  const saveBlock = lineProblems.length > 0 ? lineProblems.join('. ') : null;

  const doSave = () =>
    save.mutate(
      { lines: lines.map(toInput), deleted_line_ids: removed },
      {
        onSuccess: () => {
          setEdits(null);
          setRemoved([]);
          notify('Estimate lines saved');
        },
        onError: showError,
      },
    );

  const submitReasons = [
    ...(dirty ? ['Save your changes first'] : []),
    ...(edit.allowed ? [] : [edit.reason ?? 'You do not have permission']),
    ...(version.can_submit ? [] : version.submit_denied_reasons),
  ];
  const canSubmit = submitReasons.length === 0;

  const requestReasons = [
    ...(dirty ? ['Save your changes first'] : []),
    ...(edit.allowed ? [] : [edit.reason ?? 'You do not have permission']),
    ...(editable ? [] : ['Only a Draft or Inputs pending version can request inputs']),
    ...(data.lines.some((l) => l.base_amount === null) ? [] : ['No line is missing an input']),
  ];

  const newVersionReasons = [
    ...(edit.allowed ? [] : [edit.reason ?? 'You do not have permission']),
    ...(editable ? ['The current version is still editable: edit it instead'] : []),
    ...(version.status === 'Submitted' || version.status === 'Planner approved'
      ? ['The approval chain is still running']
      : []),
  ];

  const withReason = (reasons: string[], btn: React.ReactElement) =>
    reasons.length > 0 ? (
      <Tooltip content={reasons.join('. ')} relationship="description" withArrow>
        {React.cloneElement(btn as React.ReactElement<{ disabledFocusable?: boolean }>, {
          disabledFocusable: true,
        })}
      </Tooltip>
    ) : (
      btn
    );

  const pickVersion = (id: number) => {
    if (id === version.id) return;
    const other = data.versions.find((v) => v.id === id);
    if (!other) return;
    setCompare(
      other.version < version.version
        ? { from: other.id, to: version.id }
        : { from: version.id, to: other.id },
    );
  };
  const previous = data.versions.filter((v) => v.id !== version.id);
  const olderFirst = [...data.versions].sort((a, b) => a.version - b.version);

  return (
    <div className={s.root}>
      <SectionCard title="Operating cost estimate">
        <OcetHeader data={data} onPickVersion={pickVersion} />
      </SectionCard>

      {data.explanation && (
        <SectionCard title="Orion explanation">
          <div className={s.orion}>
            <div className={s.orionHead}>
              <AiBadge />
              <strong>Orion agent</strong>
            </div>
            <span>{data.explanation}</span>
          </div>
        </SectionCard>
      )}

      <MessageBar intent="info">
        <MessageBarBody>{data.info_note}</MessageBarBody>
      </MessageBar>

      <SectionCard
        title="Estimate lines"
        actions={
          <div className={s.bar}>
            {editable && (
              <Button icon={<Add16Regular />} onClick={onAdd} disabled={!edit.allowed}>
                Add line
              </Button>
            )}
            {editable &&
              withReason(
                [
                  ...(edit.allowed ? [] : [edit.reason ?? 'You do not have permission']),
                  ...(dirty ? [] : ['No changes to save']),
                  ...(saveBlock ? [saveBlock] : []),
                ],
                <Button
                  appearance="primary"
                  disabled={!edit.allowed || !dirty || !!saveBlock || save.isPending}
                  onClick={doSave}
                >
                  {save.isPending ? 'Saving...' : 'Save'}
                </Button>,
              )}
          </div>
        }
      >
        {!editable && (
          <MessageBar intent="warning">
            <MessageBarBody>
              Read-only:{' '}
              {version.edit_denied_reason ??
                `v${version.version} is ${version.status}. Create a new version to change it.`}
            </MessageBarBody>
          </MessageBar>
        )}
        {lines.length === 0 ? (
          <EmptyState
            message="No lines yet."
            action={
              editable && edit.allowed ? <Button onClick={onAdd}>Add the first line</Button> : null
            }
          />
        ) : (
          <LinesGrid
            lines={lines}
            years={years}
            editable={editable && edit.allowed}
            categories={data.categories}
            pricingBases={data.pricing_bases}
            workedExample={data.worked_example}
            onChange={onChange}
            onRemove={onRemove}
          />
        )}
        <div className={s.bar}>
          {withReason(
            requestReasons,
            <Button disabled={requestReasons.length > 0} onClick={() => setRequesting(true)}>
              Request inputs
            </Button>,
          )}
          {withReason(
            submitReasons,
            <Button
              appearance="primary"
              disabled={!canSubmit || submit.isPending}
              onClick={() =>
                submit.mutate(undefined, {
                  onSuccess: () => notify('Submitted for approval'),
                  onError: showError,
                })
              }
            >
              Submit for approval
            </Button>,
          )}
          {withReason(
            newVersionReasons,
            <Button
              disabled={newVersionReasons.length > 0 || newVersion.isPending}
              onClick={() =>
                newVersion.mutate(undefined, {
                  onSuccess: () => notify('New draft version created'),
                  onError: showError,
                })
              }
            >
              Create new version
            </Button>,
          )}
          {withReason(
            previous.length === 0 ? ['Only one version exists'] : [],
            <Button
              disabled={previous.length === 0}
              onClick={() => {
                const a = olderFirst[olderFirst.length - 2];
                const b = olderFirst[olderFirst.length - 1];
                if (a && b) setCompare({ from: a.id, to: b.id });
              }}
            >
              Compare versions
            </Button>,
          )}
        </div>
        {!edit.allowed && (
          <Caption1>
            Request inputs, Submit for approval and Create new version are disabled:{' '}
            {edit.reason ?? 'You do not have permission'}
          </Caption1>
        )}
        {dirty && saveBlock && (
          <MessageBar intent="warning">
            <MessageBarBody>Save is disabled: {saveBlock}</MessageBarBody>
          </MessageBar>
        )}
        {submitReasons.length > 0 && editable && (
          <MessageBar intent="warning">
            <MessageBarBody>
              Submit for approval is disabled:
              <ul className={s.reasons}>
                {submitReasons.map((r) => (
                  <li key={r}>{r}</li>
                ))}
              </ul>
            </MessageBarBody>
          </MessageBar>
        )}
      </SectionCard>

      <SectionCard title="Summary">
        <SummaryCharts data={data} />
      </SectionCard>

      {leaveGuard}
      {compare && (
        <CompareDialog
          versions={olderFirst}
          initialFrom={compare.from}
          initialTo={compare.to}
          onClose={() => setCompare(null)}
        />
      )}
      {requesting && (
        <RequestInputsDialog
          data={data}
          transitionId={transitionId}
          onClose={() => setRequesting(false)}
        />
      )}
    </div>
  );
}

/** OCET module (FR-060, spec 8.10) rendered as the workspace "OCET" tab (A-31). */
export function OcetModule({ transitionId }: TabProps) {
  const s = useStyles();
  const q = useOcet(transitionId);
  const create = useCreateOcet(transitionId);
  const showError = useApiErrorToast();
  const edit = usePerm('edit_ocet', transitionId);

  if (q.isLoading) return <LoadingState rows={6} />;
  if (q.isError) return <ErrorState error={q.error} onRetry={() => void q.refetch()} />;
  if (!q.data)
    return (
      <div className={s.root}>
        <EmptyState
          message="No OCET exists for this transition yet."
          action={
            <Tooltip
              content={edit.reason ?? ''}
              relationship="description"
              visible={edit.allowed ? false : undefined}
              withArrow
            >
              <span>
                <Button
                  appearance="primary"
                  disabled={!edit.allowed || create.isPending}
                  onClick={() => create.mutate(undefined, { onError: showError })}
                >
                  Create OCET
                </Button>
              </span>
            </Tooltip>
          }
        />
      </div>
    );
  // key = version id so local edits never leak across versions
  return <OcetBody key={q.data.version.id} data={q.data} transitionId={transitionId} />;
}

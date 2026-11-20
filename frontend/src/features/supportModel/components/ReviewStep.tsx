import { useState } from 'react';
import {
  Badge,
  Body1,
  Button,
  Caption1,
  Dropdown,
  Field,
  Input,
  MessageBar,
  MessageBarBody,
  Option,
  makeStyles,
  tokens,
} from '@fluentui/react-components';
import { AddRegular, DeleteRegular, SaveRegular, SendRegular } from '@fluentui/react-icons';
import { useNavigate } from 'react-router';
import { AiBadge } from '../../../components/AiBadge';
import { Panel } from './Panel';
import { useSuccessToast } from '../../admin/useSavedToast';
import { useApiErrorToast } from '../../../hooks/useApiErrorToast';
import {
  useDraftQuestion,
  useSaveLandscape,
  useSendForReview,
  type Landscape,
  type SupportModel,
} from '../api';
import {
  APP_NODE_ID,
  directionOf,
  nextComponentId,
  targetNameOf,
  useDirections,
  withEdge,
  type Direction,
} from '../graph';
import { useOptions } from '../../reference/options';
import { statusColor } from '../status';
import { SplitLayout } from '../../../components/layout/SplitLayout';
import { LandscapeCanvas, type CanvasSelection } from './LandscapeCanvas';
import { LandscapePanels } from './LandscapePanels';
import { useLeaveGuard } from '../../ocet/useLeaveGuard';

const useStyles = makeStyles({
  stack: { display: 'flex', flexDirection: 'column', gap: tokens.spacingVerticalL },
  bar: {
    display: 'flex',
    gap: tokens.spacingHorizontalM,
    alignItems: 'center',
    flexWrap: 'wrap',
  },
  spacer: { flexGrow: 1 },
  inspector: { display: 'flex', flexDirection: 'column', gap: tokens.spacingVerticalS },
  row: { display: 'flex', gap: tokens.spacingHorizontalS, alignItems: 'center' },
  steps: { display: 'flex', flexDirection: 'column', gap: tokens.spacingVerticalXS },
});

/** Step 3: edit the landscape (canvas + side panels), save, send for review (Architect -> OLM). */
export function ReviewStep(props: {
  transitionId: string;
  model: SupportModel;
  landscape: Landscape;
}) {
  const s = useStyles();
  const navigate = useNavigate();
  const showError = useApiErrorToast();
  const notify = useSuccessToast();
  const { model, transitionId } = props;
  const save = useSaveLandscape(transitionId);
  const send = useSendForReview(transitionId);
  const draftQ = useDraftQuestion(transitionId);

  const [base, setBase] = useState(props.landscape);
  const [draft, setDraft] = useState(props.landscape);
  // Adopt server data when it changes (after save, regenerate, approval).
  const dirtyNow = JSON.stringify(draft) !== JSON.stringify(base);
  const leaveGuard = useLeaveGuard(dirtyNow);
  if (props.landscape !== base) {
    setBase(props.landscape);
    // Never overwrite unsaved local edits with a background refetch.
    if (!dirtyNow) setDraft(props.landscape);
  }
  const [selection, setSelection] = useState<CanvasSelection>(null);
  const [newName, setNewName] = useState('');
  // Component types are suggestions from the support_component_types list; free text is still allowed.
  const typeOptions = useOptions('support_component_types');
  const directions = useDirections();
  const [chosenType, setNewType] = useState<string | null>(null);
  const newType = chosenType ?? typeOptions[0]?.value ?? '';

  const editable = model.can_edit && model.status === 'Draft';
  const dirty = JSON.stringify(draft) !== JSON.stringify(base);
  const patch = (p: Partial<Landscape>) => setDraft((d) => ({ ...d, ...p }));
  const app = draft.central_app;

  const selComp =
    selection?.kind === 'node' && selection.id !== APP_NODE_ID
      ? draft.components.find((c) => c.id === selection.id)
      : undefined;
  const selEdge =
    selection?.kind === 'edge' ? draft.components.find((c) => c.id === selection.id) : undefined;
  const selApp = selection?.kind === 'node' && selection.id === APP_NODE_ID;

  const setComponent = (
    id: string,
    fn: (c: Landscape['components'][number]) => Landscape['components'][number],
  ) => patch({ components: draft.components.map((c) => (c.id === id ? fn(c) : c)) });

  /** Rename keeps the edges that reference the component by name intact. */
  const rename = (id: string, name: string) => {
    const old = draft.components.find((c) => c.id === id)?.name;
    patch({
      components: draft.components.map((c) => {
        if (c.id === id) return { ...c, name };
        if (old === undefined) return c;
        const next = { ...c };
        if (c.target === old) next.target = name;
        if (c.relation === `child_of:${old}`) next.relation = `child_of:${name}`;
        return next;
      }),
    });
  };

  const deleteComponent = (id: string) => {
    const gone = draft.components.find((c) => c.id === id);
    if (!gone) return;
    // Edges that pointed at it fall back to the central app.
    patch({
      components: draft.components
        .filter((c) => c.id !== id)
        .map((c) => {
          if (c.target === gone.name) return { ...c, target: null };
          if (c.relation === `child_of:${gone.name}`) return { ...c, relation: 'bidirectional' };
          return c;
        }),
    });
    setSelection(null);
  };

  const addComponent = () => {
    const name = newName.trim();
    if (!name) return;
    const id = nextComponentId(draft.components);
    patch({
      components: [
        ...draft.components,
        {
          id,
          name,
          type: newType.trim() || typeOptions[0]?.value || 'Other',
          relation: 'bidirectional',
          target: null,
        },
      ],
    });
    setNewName('');
    setSelection({ kind: 'node', id });
  };

  const nameClash = (id: string, name: string) =>
    name === app || draft.components.some((c) => c.id !== id && c.name === name);
  const invalid =
    !app.trim() ||
    draft.components.some((c) => !c.name.trim() || !c.type.trim() || nameClash(c.id, c.name));

  const connect = (componentId: string, targetNodeId: string) => {
    const tName =
      targetNodeId === APP_NODE_ID
        ? app
        : (draft.components.find((c) => c.id === targetNodeId)?.name ?? app);
    setComponent(componentId, (c) => withEdge(c, directionOf(c), tName, app));
    setSelection({ kind: 'edge', id: componentId });
  };

  const targetOptions = (id: string) => [
    app,
    ...draft.components.filter((c) => c.id !== id).map((c) => c.name),
  ];

  const onSave = () =>
    model.id !== null &&
    save.mutate(
      { id: model.id, landscape: draft },
      { onSuccess: () => notify('Support model saved'), onError: showError },
    );
  const onSend = () =>
    model.id !== null &&
    send.mutate(model.id, {
      onSuccess: () => notify('Sent for review'),
      onError: showError,
    });
  const onDraftQuestion = (index: number) =>
    model.id !== null &&
    draftQ.mutate(
      { id: model.id, index },
      { onSuccess: (r) => navigate(`/drafts?draft=${r.draft_id}`), onError: showError },
    );

  const sendBlock = !editable
    ? null
    : dirty
      ? invalid
        ? 'Fix the highlighted names or types, then save'
        : 'Save your changes before sending for review'
      : null;

  return (
    <div className={s.stack}>
      {leaveGuard}
      {!editable && (
        <MessageBar intent={model.status === 'Draft' ? 'warning' : 'info'}>
          <MessageBarBody>
            {model.edit_denied_reason ??
              (model.status === 'In review'
                ? 'This support model is in review and cannot be edited.'
                : model.status === 'Agreed'
                  ? 'This support model is agreed and cannot be edited.'
                  : 'You cannot edit this support model.')}
          </MessageBarBody>
        </MessageBar>
      )}

      <div className={s.bar}>
        <Badge appearance="filled" color={statusColor(model.status)} size="large">
          {model.status}
        </Badge>
        <Caption1>Version {model.version}</Caption1>
        <AiBadge />
        <Caption1>Generated by Orion agent, review before sending</Caption1>
        <span className={s.spacer} />
        {editable && (
          <>
            <Button
              icon={<SaveRegular />}
              appearance="primary"
              disabled={!dirty || invalid || save.isPending}
              onClick={onSave}
            >
              {save.isPending ? 'Saving' : dirty ? 'Save' : 'Saved'}
            </Button>
            <Button
              icon={<SendRegular />}
              disabled={!!sendBlock || send.isPending || model.id === null}
              title={sendBlock ?? undefined}
              onClick={onSend}
            >
              Send for review
            </Button>
          </>
        )}
      </div>
      {sendBlock && <Caption1>{sendBlock}</Caption1>}

      {model.approval && (
        <Panel title={`Review chain, ${model.approval.status}`}>
          <div className={s.steps}>
            {model.approval.steps.map((st) => (
              <div key={st.step} className={s.row}>
                <Badge
                  appearance="tint"
                  color={
                    st.status === 'Approved'
                      ? 'success'
                      : st.status === 'Rejected'
                        ? 'danger'
                        : st.status === 'Pending'
                          ? 'warning'
                          : 'subtle'
                  }
                >
                  {st.status}
                </Badge>
                <Body1>
                  {st.step}. {st.label}
                  {st.approver ? ` (${st.approver.name})` : ''}
                </Body1>
              </div>
            ))}
          </div>
          <Caption1>Approve or reject from the Approvals page.</Caption1>
        </Panel>
      )}

      <SplitLayout
        stickyAside={false}
        main={
          <LandscapeCanvas
            landscape={draft}
            editable={editable}
            selection={selection}
            onSelect={setSelection}
            onConnect={connect}
          />
        }
        aside={
          <Panel title="Selection">
            <div className={s.inspector}>
              {!selComp && !selEdge && !selApp && (
                <Caption1>
                  Click a node or an edge to edit it.
                  {editable && ' Drag from one node to another to connect them.'}
                </Caption1>
              )}
              {selApp && (
                <Field label="Central application">
                  <Input
                    value={draft.central_app}
                    disabled={!editable}
                    onChange={(_, d) => {
                      const old = draft.central_app;
                      patch({
                        central_app: d.value,
                        components: draft.components.map((c) =>
                          c.target === old ? { ...c, target: d.value } : c,
                        ),
                      });
                    }}
                  />
                </Field>
              )}
              {selComp && (
                <>
                  <Field
                    label="Name"
                    validationState={nameClash(selComp.id, selComp.name) ? 'error' : undefined}
                    validationMessage={
                      nameClash(selComp.id, selComp.name) ? 'Names must be unique' : undefined
                    }
                  >
                    <Input
                      value={selComp.name}
                      disabled={!editable}
                      onChange={(_, d) => rename(selComp.id, d.value)}
                    />
                  </Field>
                  <Field label="Type">
                    <datalist id="support-component-types">
                      {typeOptions.map((o) => (
                        <option key={o.value} value={o.value} />
                      ))}
                    </datalist>
                    <Input
                      value={selComp.type}
                      input={{ list: 'support-component-types' }}
                      disabled={!editable}
                      onChange={(_, d) =>
                        setComponent(selComp.id, (c) => ({ ...c, type: d.value }))
                      }
                    />
                  </Field>
                  {editable && (
                    <Button icon={<DeleteRegular />} onClick={() => deleteComponent(selComp.id)}>
                      Delete component
                    </Button>
                  )}
                </>
              )}
              {selEdge && (
                <>
                  <Body1>
                    <strong>{selEdge.name}</strong> relation
                  </Body1>
                  <Field label="Connects to">
                    <Dropdown
                      value={targetNameOf(selEdge, app)}
                      selectedOptions={[targetNameOf(selEdge, app)]}
                      disabled={!editable}
                      onOptionSelect={(_, d) =>
                        d.optionValue &&
                        setComponent(selEdge.id, (c) =>
                          withEdge(c, directionOf(c), d.optionValue ?? app, app),
                        )
                      }
                    >
                      {targetOptions(selEdge.id).map((n) => (
                        <Option key={n} value={n}>
                          {n}
                        </Option>
                      ))}
                    </Dropdown>
                  </Field>
                  <Field label="Direction">
                    <Dropdown
                      value={directions.find((d) => d.value === directionOf(selEdge))?.label ?? ''}
                      selectedOptions={[directionOf(selEdge)]}
                      disabled={!editable}
                      onOptionSelect={(_, d) =>
                        d.optionValue &&
                        setComponent(selEdge.id, (c) =>
                          withEdge(c, d.optionValue as Direction, targetNameOf(c, app), app),
                        )
                      }
                    >
                      {directions.map((d) => (
                        <Option key={d.value} value={d.value}>
                          {d.label}
                        </Option>
                      ))}
                    </Dropdown>
                  </Field>
                  {editable && (
                    <Button
                      icon={<DeleteRegular />}
                      disabled={
                        targetNameOf(selEdge, app) === app &&
                        directionOf(selEdge) === 'bidirectional'
                      }
                      onClick={() =>
                        setComponent(selEdge.id, (c) => withEdge(c, 'bidirectional', app, app))
                      }
                    >
                      Remove edge (reconnect to {app})
                    </Button>
                  )}
                  {editable && (
                    <Caption1>
                      Each component has one edge. To drop a connection entirely, delete the
                      component.
                    </Caption1>
                  )}
                </>
              )}
              {editable && (
                <div className={s.inspector} style={{ marginTop: tokens.spacingVerticalM }}>
                  <Body1>
                    <strong>Add component</strong>
                  </Body1>
                  <Input
                    placeholder="Name"
                    aria-label="New component name"
                    value={newName}
                    onChange={(_, d) => setNewName(d.value)}
                  />
                  <Input
                    placeholder="Type"
                    input={{ list: 'support-component-types' }}
                    aria-label="New component type"
                    value={newType}
                    onChange={(_, d) => setNewType(d.value)}
                  />
                  <Button
                    icon={<AddRegular />}
                    disabled={!newName.trim() || nameClash('', newName.trim())}
                    onClick={addComponent}
                  >
                    Add
                  </Button>
                </div>
              )}
            </div>
          </Panel>
        }
      />

      <LandscapePanels
        landscape={draft}
        editable={editable}
        onPatch={patch}
        onDraftQuestion={onDraftQuestion}
        draftDisabledReason={
          !model.can_edit
            ? (model.edit_denied_reason ?? 'You do not have permission')
            : dirty
              ? 'Save your changes before drafting a question'
              : null
        }
        drafting={draftQ.isPending}
      />
    </div>
  );
}

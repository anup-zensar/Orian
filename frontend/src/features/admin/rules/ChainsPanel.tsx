import { useState } from 'react';
import {
  Button,
  Input,
  Select,
  Subtitle2,
  Switch,
  Tooltip,
  makeStyles,
  tokens,
} from '@fluentui/react-components';
import { ErrorState } from '../../../components/ErrorState';
import { LoadingState } from '../../../components/LoadingState';
import { useRoleLabel } from '../../reference/options';
import { useApprovalChains, usePutApprovalChains, type ApprovalChains } from '../api';
import { ReasonsBar, SaveBar } from '../peopleRulesUi';
import { useDirty } from '../useDirty';
import { useSuccessToast } from '../useSavedToast';

type Chains = ApprovalChains['chains'];
type Steps = Chains[number]['steps'];

const useStyles = makeStyles({
  chain: {
    display: 'flex',
    flexDirection: 'column',
    gap: tokens.spacingVerticalS,
    paddingBottom: tokens.spacingVerticalM,
    borderBottom: `1px solid ${tokens.colorNeutralStroke2}`,
  },
  step: { display: 'flex', gap: tokens.spacingHorizontalS, alignItems: 'center', flexWrap: 'wrap' },
  num: { width: '24px', textAlign: 'right' },
  role: { minWidth: '180px' },
  label: { flexGrow: 1, minWidth: '200px' },
  actions: { display: 'flex', gap: tokens.spacingHorizontalS },
  chainName: { maxWidth: '360px' },
});

function Editor({ initial, roles }: { initial: Chains; roles: string[] }) {
  const s = useStyles();
  const [chains, setChains] = useState<Chains>(initial);
  const dirty = useDirty(chains, 'chains');
  const save = usePutApprovalChains();
  const ok = useSuccessToast();
  const roleLabel = useRoleLabel();

  const edit = (type: string, fn: (steps: Steps) => Steps) =>
    setChains((cs) =>
      cs.map((c) =>
        c.type === type ? { ...c, steps: fn(c.steps).map((st, i) => ({ ...st, step: i + 1 })) } : c,
      ),
    );
  const editStep = (type: string, i: number, patch: Partial<Steps[number]>) =>
    edit(type, (ss) => ss.map((x, j) => (j === i ? { ...x, ...patch } : x)));
  const swap = (type: string, i: number, j: number) =>
    edit(type, (ss) => {
      const a = [...ss];
      [a[i], a[j]] = [a[j], a[i]];
      return a;
    });

  const invalid = chains.some(
    (c) =>
      c.steps.length === 0 || !(c.label ?? 'x').trim() || c.steps.some((st) => !st.label.trim()),
  );

  return (
    <>
      {chains.map((c) => (
        <div key={c.type} className={s.chain}>
          <Subtitle2 as="h3">{c.label || c.type}</Subtitle2>
          <Input
            aria-label={`${c.type} chain name`}
            className={s.chainName}
            value={c.label ?? ''}
            onChange={(_, d) =>
              setChains((cs) => cs.map((x) => (x.type === c.type ? { ...x, label: d.value } : x)))
            }
          />
          {c.steps.map((st, i) => (
            <div key={i} className={s.step}>
              <span className={s.num}>{st.step}.</span>
              <Select
                aria-label={`${c.type} step ${st.step} role`}
                className={s.role}
                value={st.role}
                onChange={(_, d) => editStep(c.type, i, { role: d.value })}
              >
                {(roles.includes(st.role) ? roles : [...roles, st.role]).map((r) => (
                  <option key={r} value={r}>
                    {roleLabel(r)}
                  </option>
                ))}
              </Select>
              <Input
                aria-label={`${c.type} step ${st.step} label`}
                className={s.label}
                value={st.label}
                onChange={(_, d) => editStep(c.type, i, { label: d.value })}
              />
              <Tooltip
                relationship="description"
                content="Demo only: a stand-in approves this step until the real system is connected. Turning it on removes a real approval."
              >
                <Switch
                  label="Simulated approver (demo only)"
                  checked={st.is_mock === true}
                  onChange={(_, d) => editStep(c.type, i, { is_mock: d.checked })}
                />
              </Tooltip>
              <div className={s.actions}>
                <Button size="small" disabled={i === 0} onClick={() => swap(c.type, i - 1, i)}>
                  Up
                </Button>
                <Button
                  size="small"
                  disabled={i === c.steps.length - 1}
                  onClick={() => swap(c.type, i, i + 1)}
                >
                  Down
                </Button>
                <Button
                  size="small"
                  disabled={c.steps.length <= 1}
                  onClick={() => edit(c.type, (ss) => ss.filter((_, j) => j !== i))}
                >
                  Remove
                </Button>
              </div>
            </div>
          ))}
          <div>
            <Button
              size="small"
              onClick={() =>
                edit(c.type, (ss) => [
                  ...ss,
                  { step: ss.length + 1, role: roles[0] ?? '', label: '', is_mock: false },
                ])
              }
            >
              Add step
            </Button>
          </div>
        </div>
      ))}
      <ReasonsBar error={save.error} />
      <SaveBar
        dirty={dirty}
        saving={save.isPending}
        blockedReason={
          invalid ? 'Every chain needs at least one step and every step a label' : undefined
        }
        onSave={() =>
          save.mutate({ chains }, { onSuccess: () => ok('Saved - applies to new transitions') })
        }
        onDiscard={() => {
          setChains(initial);
          save.reset();
        }}
      />
    </>
  );
}

export function ChainsPanel() {
  const q = useApprovalChains();
  if (q.isLoading) return <LoadingState rows={5} />;
  if (q.isError) return <ErrorState error={q.error} onRetry={() => void q.refetch()} />;
  return q.data ? (
    <Editor key={q.dataUpdatedAt} initial={q.data.chains} roles={q.data.roles} />
  ) : null;
}

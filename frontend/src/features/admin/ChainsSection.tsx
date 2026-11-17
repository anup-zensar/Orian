import { useState } from 'react';
import { Button, Input, Select, Subtitle2, makeStyles, tokens } from '@fluentui/react-components';
import { ErrorState } from '../../components/ErrorState';
import { LoadingState } from '../../components/LoadingState';
import { SectionCard } from '../../components/SectionCard';
import { useApiErrorToast } from '../../hooks/useApiErrorToast';
import { useApprovalChains, usePutApprovalChains, type ApprovalChains } from './api';
import { useSuccessToast } from './useSavedToast';

type Chains = ApprovalChains['chains'];

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
});

function Editor({ initial, roles }: { initial: Chains; roles: string[] }) {
  const s = useStyles();
  const [chains, setChains] = useState<Chains>(initial);
  const save = usePutApprovalChains();
  const showError = useApiErrorToast();
  const ok = useSuccessToast();

  const edit = (type: string, fn: (steps: Chains[number]['steps']) => Chains[number]['steps']) =>
    setChains((cs) =>
      cs.map((c) =>
        c.type === type ? { ...c, steps: fn(c.steps).map((st, i) => ({ ...st, step: i + 1 })) } : c,
      ),
    );

  const invalid = chains.some(
    (c) => c.steps.length === 0 || c.steps.some((st) => !st.label.trim()),
  );

  return (
    <SectionCard
      title="Approval chains"
      actions={
        <Button
          appearance="primary"
          disabled={save.isPending || invalid}
          onClick={() =>
            save.mutate(
              { chains },
              { onSuccess: () => ok('Approval chains saved'), onError: showError },
            )
          }
        >
          {save.isPending ? 'Saving...' : 'Save approval chains'}
        </Button>
      }
    >
      {chains.map((c) => (
        <div key={c.type} className={s.chain}>
          <Subtitle2 as="h3">{c.type}</Subtitle2>
          {c.steps.map((st, i) => (
            <div key={i} className={s.step}>
              <span className={s.num}>{st.step}.</span>
              <Select
                aria-label={`${c.type} step ${st.step} role`}
                className={s.role}
                value={st.role}
                onChange={(_, d) =>
                  edit(c.type, (ss) => ss.map((x, j) => (j === i ? { ...x, role: d.value } : x)))
                }
              >
                {(roles.includes(st.role) ? roles : [...roles, st.role]).map((r) => (
                  <option key={r}>{r}</option>
                ))}
              </Select>
              <Input
                aria-label={`${c.type} step ${st.step} label`}
                className={s.label}
                value={st.label}
                onChange={(_, d) =>
                  edit(c.type, (ss) => ss.map((x, j) => (j === i ? { ...x, label: d.value } : x)))
                }
              />
              <div className={s.actions}>
                <Button
                  size="small"
                  disabled={i === 0}
                  onClick={() =>
                    edit(c.type, (ss) => {
                      const a = [...ss];
                      [a[i - 1], a[i]] = [a[i], a[i - 1]];
                      return a;
                    })
                  }
                >
                  Up
                </Button>
                <Button
                  size="small"
                  disabled={i === c.steps.length - 1}
                  onClick={() =>
                    edit(c.type, (ss) => {
                      const a = [...ss];
                      [a[i + 1], a[i]] = [a[i], a[i + 1]];
                      return a;
                    })
                  }
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
                  { step: ss.length + 1, role: roles[0] ?? '', label: '' },
                ])
              }
            >
              Add step
            </Button>
          </div>
        </div>
      ))}
    </SectionCard>
  );
}

export function ChainsSection() {
  const q = useApprovalChains();
  if (q.isLoading) return <LoadingState rows={5} />;
  if (q.isError) return <ErrorState error={q.error} onRetry={() => void q.refetch()} />;
  return q.data ? (
    <Editor key={q.dataUpdatedAt} initial={q.data.chains} roles={q.data.roles} />
  ) : null;
}

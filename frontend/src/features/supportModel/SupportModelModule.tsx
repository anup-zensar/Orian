import { useState } from 'react';
import { Badge, Tab, TabList, makeStyles, tokens } from '@fluentui/react-components';
import { EmptyState } from '../../components/EmptyState';
import { ErrorState } from '../../components/ErrorState';
import { LoadingState } from '../../components/LoadingState';
import { PageHeader } from '../../components/PageHeader';
import { useTransition } from '../transition/api';
import type { TabProps } from '../workspace/types';
import { useSupportModel } from './api';
import { ExportStep } from './components/ExportStep';
import { GenerateStep } from './components/GenerateStep';
import { InputsStep } from './components/InputsStep';
import { ReviewStep } from './components/ReviewStep';
import { statusColor } from './status';

const useStyles = makeStyles({
  page: { display: 'flex', flexDirection: 'column', gap: tokens.spacingVerticalL },
});

type Step = 'inputs' | 'generate' | 'review' | 'export';

/** Support model generator (FR-040 · M7) as a workspace tab: Inputs, Generate, Review and edit,
 * Export (spec 8.8). */
export function SupportModelModule({ transitionId }: TabProps) {
  const s = useStyles();
  const q = useSupportModel(transitionId);
  const transition = useTransition(transitionId);
  const [step, setStep] = useState<Step | null>(null);

  if (q.isPending) return <LoadingState rows={5} />;
  if (q.isError) return <ErrorState error={q.error} onRetry={() => void q.refetch()} />;

  const model = q.data;
  const landscape = model.landscape;
  const current: Step = step ?? (landscape ? 'review' : 'inputs');

  return (
    <div className={s.page}>
      <PageHeader
        title="Support model"
        subtitle={transition.data?.name ?? model.transition_name}
        actions={
          <Badge appearance="filled" color={statusColor(model.status)} size="large">
            {model.status}
          </Badge>
        }
      />
      <TabList
        selectedValue={current}
        onTabSelect={(_, d) => setStep(d.value as Step)}
        aria-label="Support model steps"
      >
        <Tab value="inputs">1. Inputs</Tab>
        <Tab value="generate">2. Generate</Tab>
        <Tab value="review" disabled={!landscape}>
          3. Review and edit
        </Tab>
        <Tab value="export" disabled={!landscape}>
          4. Export
        </Tab>
      </TabList>

      {current === 'inputs' && <InputsStep transitionId={transitionId} model={model} />}
      {current === 'generate' && (
        <GenerateStep transitionId={transitionId} model={model} onDone={() => setStep('review')} />
      )}
      {current === 'review' &&
        (landscape && model.id !== null ? (
          <ReviewStep
            key={`${model.id}-${model.version}`}
            transitionId={transitionId}
            model={model}
            landscape={landscape}
          />
        ) : (
          <EmptyState message="Nothing generated yet. Add inputs and generate the support model." />
        ))}
      {current === 'export' && <ExportStep transitionId={transitionId} model={model} />}
    </div>
  );
}

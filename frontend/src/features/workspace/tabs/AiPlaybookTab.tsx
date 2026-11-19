import { EmptyState } from '../../../components/EmptyState';
import { ErrorState } from '../../../components/ErrorState';
import { LoadingState } from '../../../components/LoadingState';
import { PageHeader } from '../../../components/PageHeader';
import { useTransition } from '../../transition/api';
import { AiProfileCard, EvalCard, TierCard } from '../../records/AiPlaybookParts';
import { useRecordStyles } from '../../records/hooks';
import type { TabProps } from '../types';

/** AI playbook tab (FR-037, spec 8.7 i/j): tier card, AI profile form and eval metrics. */
export function AiPlaybookTab({ transitionId }: TabProps) {
  const s = useRecordStyles();
  const transition = useTransition(transitionId);

  return (
    <div className={s.stack}>
      <PageHeader
        as="h2"
        title="AI playbook"
        subtitle="Risk tier, AI profile and evaluation results for this AI transition."
      />
      {transition.isPending ? (
        <LoadingState rows={4} />
      ) : transition.isError ? (
        <ErrorState error={transition.error} />
      ) : !transition.data.has_ai_profile && !transition.data.has_eval_metrics ? (
        <EmptyState message="The AI playbook applies to AI project types only." />
      ) : (
        <>
          {transition.data.requires_tiering && <TierCard transition={transition.data} />}
          {transition.data.has_ai_profile && <AiProfileCard transitionId={transitionId} />}
          {transition.data.has_eval_metrics && <EvalCard transitionId={transitionId} />}
        </>
      )}
    </div>
  );
}

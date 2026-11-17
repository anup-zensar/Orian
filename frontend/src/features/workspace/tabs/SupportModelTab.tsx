import { ModuleLinkCard } from '../../records/ModuleLinkCard';
import type { TabProps } from '../types';

const SUPPORT_MODEL_ITEMS = Array.from(
  { length: 9 },
  (_, i) => `FW-${String(27 + i).padStart(3, '0')}`,
);

/** Support model tab (FR-065): link card until the generator and PPT export ship in M7. */
export function SupportModelTab({ transitionId }: TabProps) {
  return (
    <ModuleLinkCard
      transitionId={transitionId}
      title="Support model"
      description="Who supports this solution after go-live, and how."
      bullets={[
        'A support model generator that drafts the model from the transition facts.',
        'A PowerPoint export of the support model for the gate pack.',
        'Status of the support model checklist items that it satisfies.',
      ]}
      itemIds={SUPPORT_MODEL_ITEMS}
      milestone="M7"
    />
  );
}

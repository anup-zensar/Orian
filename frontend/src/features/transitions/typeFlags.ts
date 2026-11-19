// What a transition's project type switches on (CR-01). The transition detail carries these flags;
// while it loads, the project type in the reference data says the same. Never compare type names.
import type { TransitionDetail } from '../transition/api';
import { useProjectType } from '../reference/options';

export interface TypeFlags {
  /** The type asks for a risk tier (tiering page, tier card). */
  requiresTiering: boolean;
  /** The type has an AI profile questionnaire. */
  hasAiProfile: boolean;
  /** The type has evaluation metrics. */
  hasEvalMetrics: boolean;
}

/** The flags of a transition (all false while it loads). */
export function useTypeFlags(detail: TransitionDetail | undefined): TypeFlags {
  const projectType = useProjectType(detail?.project_type);
  return {
    requiresTiering: detail?.requires_tiering ?? projectType?.requires_tiering ?? false,
    hasAiProfile: detail?.has_ai_profile ?? projectType?.has_ai_profile ?? false,
    hasEvalMetrics: detail?.has_eval_metrics ?? projectType?.has_eval_metrics ?? false,
  };
}

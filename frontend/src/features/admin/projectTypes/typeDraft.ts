import type { ChecklistAdmin, ProjectTypeAdmin } from '../../../api/types';

/** What the admin edits for a project type. `synonyms` is one comma separated line. */
export interface TypeDraft {
  label: string;
  description: string;
  checklists: string[];
  requires_tiering: boolean;
  has_ai_profile: boolean;
  has_eval_metrics: boolean;
  required_intake_fields: string[];
  synonyms: string;
}

export const EMPTY_DRAFT: TypeDraft = {
  label: '',
  description: '',
  checklists: [],
  requires_tiering: false,
  has_ai_profile: false,
  has_eval_metrics: false,
  required_intake_fields: [],
  synonyms: '',
};

export const draftFromType = (t: ProjectTypeAdmin): TypeDraft => ({
  label: t.label,
  description: t.description,
  checklists: t.checklists,
  requires_tiering: t.requires_tiering,
  has_ai_profile: t.has_ai_profile,
  has_eval_metrics: t.has_eval_metrics,
  required_intake_fields: t.required_intake_fields,
  synonyms: t.synonyms.join(', '),
});

export const splitList = (text: string): string[] =>
  text
    .split(',')
    .map((x) => x.trim())
    .filter(Boolean);

/** The one-line preview: "A transition of this type gets about 52 items: ...". */
export function previewSentence(selected: string[], checklists: ChecklistAdmin[]): string {
  const chosen = checklists.filter((c) => selected.includes(c.code));
  const common = checklists.filter((c) => c.kind === 'common' && c.active);
  const parts = [...chosen, ...common].map((c) => `${c.item_count} ${c.label}`);
  const total = [...chosen, ...common].reduce((sum, c) => sum + c.item_count, 0);
  const tierNote = chosen.some((c) => c.tier_filtered) ? ' (fewer once its tier is known)' : '';
  if (chosen.length === 0) {
    return 'No checklist ticked: a transition of this type gets only the common checklist and the golden set of its portfolio.';
  }
  return `A transition of this type gets ${total} items${tierNote}: ${parts.join(', ')}, plus the golden set of its portfolio.`;
}

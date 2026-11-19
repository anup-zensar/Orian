import type { TypeFlags } from './typeFlags';

/** Workspace tabs (A-31). The tab is part of the URL so every tab is deep-linkable. */
export const WORKSPACE_TABS = [
  { key: 'overview', label: 'Overview' },
  { key: 'assessment', label: 'Assessment' },
  { key: 'gaps', label: 'Gaps' },
  { key: 'evidence', label: 'Evidence' },
  { key: 'conditions', label: 'Conditions' },
  { key: 'gates', label: 'Gates' },
  { key: 'hypercare', label: 'Hypercare' },
  { key: 'ocet', label: 'OCET' },
  { key: 'support-model', label: 'Support model' },
  { key: 'ai-playbook', label: 'AI playbook', aiOnly: true },
  { key: 'activity', label: 'Activity' },
] as const;

export type WorkspaceTab = (typeof WORKSPACE_TABS)[number];

/** The AI playbook tab (AI profile, evaluation) exists only when the project type switches on an AI
 * profile or evaluation metrics (spec 8.7). A type with tiering only shows its tier in the header. */
export function showsAiPlaybook(flags: TypeFlags): boolean {
  return flags.hasAiProfile || flags.hasEvalMetrics;
}

export function visibleTabs(flags: TypeFlags): readonly WorkspaceTab[] {
  return WORKSPACE_TABS.filter((t) => !('aiOnly' in t) || showsAiPlaybook(flags));
}

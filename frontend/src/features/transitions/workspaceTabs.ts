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
  { key: 'ai-playbook', label: 'AI playbook', requiresTiering: true },
  { key: 'activity', label: 'Activity' },
] as const;

export type WorkspaceTab = (typeof WORKSPACE_TABS)[number];

/** The AI playbook tab only exists for project types that require tiering (spec 8.7). */
export function visibleTabs(requiresTiering: boolean): readonly WorkspaceTab[] {
  return WORKSPACE_TABS.filter((t) => !('requiresTiering' in t) || requiresTiering);
}

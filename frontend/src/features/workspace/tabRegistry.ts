import { lazy, type ComponentType, type LazyExoticComponent } from 'react';
import type { TabProps } from './types';

/**
 * Workspace tab key -> lazily loaded tab component (A-31). Each tab lives in its own module under
 * ./tabs so tabs can be built and code-split independently. Keys match WORKSPACE_TABS and the URL
 * (/transitions/:id/:tab).
 */
export const TAB_COMPONENTS: Record<string, LazyExoticComponent<ComponentType<TabProps>>> = {
  overview: lazy(() => import('./tabs/OverviewTab').then((m) => ({ default: m.OverviewTab }))),
  assessment: lazy(() =>
    import('./tabs/AssessmentTab').then((m) => ({ default: m.AssessmentTab })),
  ),
  gaps: lazy(() => import('./tabs/GapsTab').then((m) => ({ default: m.GapsTab }))),
  evidence: lazy(() => import('./tabs/EvidenceTab').then((m) => ({ default: m.EvidenceTab }))),
  conditions: lazy(() =>
    import('./tabs/ConditionsTab').then((m) => ({ default: m.ConditionsTab })),
  ),
  gates: lazy(() => import('./tabs/GatesTab').then((m) => ({ default: m.GatesTab }))),
  hypercare: lazy(() => import('./tabs/HypercareTab').then((m) => ({ default: m.HypercareTab }))),
  ocet: lazy(() => import('./tabs/OcetTab').then((m) => ({ default: m.OcetTab }))),
  'support-model': lazy(() =>
    import('./tabs/SupportModelTab').then((m) => ({ default: m.SupportModelTab })),
  ),
  'ai-playbook': lazy(() =>
    import('./tabs/AiPlaybookTab').then((m) => ({ default: m.AiPlaybookTab })),
  ),
  activity: lazy(() => import('./tabs/ActivityTab').then((m) => ({ default: m.ActivityTab }))),
};

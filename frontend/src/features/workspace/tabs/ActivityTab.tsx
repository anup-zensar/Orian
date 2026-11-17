import { AuditExplorer } from '../../audit/AuditExplorer';
import type { TabProps } from '../types';

/** Activity tab (FR-110, spec 8.7 k): this transition's audit events. Filters live in the URL. */
export function ActivityTab({ transitionId }: TabProps) {
  return <AuditExplorer transitionId={transitionId} />;
}

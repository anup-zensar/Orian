import type { FluentIcon } from '@fluentui/react-icons';
import {
  Add20Regular,
  Board20Regular,
  Building20Regular,
  CheckmarkCircle20Regular,
  DataBarVertical20Regular,
  DocumentBulletList20Regular,
  DocumentEdit20Regular,
  Gauge20Regular,
  History20Regular,
  Mail20Regular,
  PersonSettings20Regular,
} from '@fluentui/react-icons';

export interface NavItem {
  label: string;
  to: string;
  icon: FluentIcon;
  adminOnly?: boolean;
}

/** Left navigation, in the order of FR-002. Teams preview is SHOULD and omitted (A-13). */
export const NAV_ITEMS: NavItem[] = [
  { label: 'Dashboard', to: '/', icon: Board20Regular },
  { label: 'Control tower', to: '/control-tower', icon: Gauge20Regular },
  { label: 'Transitions', to: '/transitions', icon: DocumentBulletList20Regular },
  { label: 'New transition', to: '/transitions/new', icon: Add20Regular },
  { label: 'Approvals', to: '/approvals', icon: CheckmarkCircle20Regular },
  { label: 'Orion drafts', to: '/drafts', icon: DocumentEdit20Regular },
  { label: 'Outbox', to: '/outbox', icon: Mail20Regular },
  { label: 'Leadership updates', to: '/leadership-updates', icon: DataBarVertical20Regular },
  { label: 'Support models', to: '/support-models', icon: Building20Regular },
  { label: 'Admin', to: '/admin', icon: PersonSettings20Regular, adminOnly: true },
  { label: 'Audit trail', to: '/audit', icon: History20Regular },
];

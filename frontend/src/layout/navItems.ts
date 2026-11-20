import type { FluentIcon } from '@fluentui/react-icons';
import {
  Board20Regular,
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
  /** Shown when the user holds at least one of these permission codes (GET /me). Always shown if omitted. */
  anyPermission?: string[];
}

/** Left navigation, in the order of FR-002. Teams preview is SHOULD and omitted (A-13). */
export const NAV_ITEMS: NavItem[] = [
  { label: 'Dashboard', to: '/', icon: Board20Regular },
  { label: 'Control tower', to: '/control-tower', icon: Gauge20Regular },
  { label: 'Transitions', to: '/transitions', icon: DocumentBulletList20Regular },
  { label: 'Approvals', to: '/approvals', icon: CheckmarkCircle20Regular },
  {
    label: 'Orion drafts',
    to: '/drafts',
    icon: DocumentEdit20Regular,
    anyPermission: ['send_drafts', 'run_reminders'],
  },
  {
    label: 'Outbox',
    to: '/outbox',
    icon: Mail20Regular,
    anyPermission: ['send_drafts', 'run_reminders'],
  },
  {
    label: 'Leadership updates',
    to: '/leadership-updates',
    icon: DataBarVertical20Regular,
    anyPermission: ['generate_leadership_update', 'see_all_transitions'],
  },
  { label: 'Admin', to: '/admin', icon: PersonSettings20Regular, anyPermission: ['admin'] },
  { label: 'Audit trail', to: '/audit', icon: History20Regular },
];

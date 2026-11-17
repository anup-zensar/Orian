import { PlaceholderPage } from '../components/PlaceholderPage';

// One tiny component per not-yet-built route. Spec ids + milestone only, no fake data.

export const DashboardPage = () => (
  <PlaceholderPage
    title="Dashboard"
    purpose="Your work, decisions due and Orion insights."
    spec="FR-010 · built in M2"
  />
);
export const ControlTowerPage = () => (
  <PlaceholderPage
    title="Control tower"
    purpose="Portfolio heatmap, register and escalation queue."
    spec="FR-011 · built in M2"
  />
);
export const TransitionsPage = () => (
  <PlaceholderPage
    title="Transitions"
    purpose="Searchable, filterable list of all transitions."
    spec="FR-012 · built in M2"
  />
);
export const NewTransitionPage = () => (
  <PlaceholderPage
    title="New transition"
    purpose="Intake form that starts a transition."
    spec="FR-020 · built in M3"
  />
);
export const TieringPage = () => (
  <PlaceholderPage
    title="AI tiering"
    purpose="Questionnaire that proposes an AI risk tier for IRM to confirm."
    spec="FR-021 · built in M3"
  />
);
export const ScopePage = () => (
  <PlaceholderPage
    title="Portfolio scope"
    purpose="Confirm which portfolio scope requirements apply."
    spec="FR-022 · built in M3"
  />
);
export const ApprovalsPage = () => (
  <PlaceholderPage
    title="Approvals"
    purpose="Inbox of approvals waiting for you."
    spec="FR-070 · built in M5"
  />
);
export const DraftsPage = () => (
  <PlaceholderPage
    title="Orion drafts"
    purpose="Queue of messages Orion drafted for a person to edit and send."
    spec="FR-071 · built in M5"
  />
);
export const OutboxPage = () => (
  <PlaceholderPage
    title="Outbox"
    purpose="Sent emails and Teams cards (mock)."
    spec="FR-072 · built in M5"
  />
);
export const LeadershipUpdatesPage = () => (
  <PlaceholderPage
    title="Leadership updates"
    purpose="Portfolio updates for leadership."
    spec="FR-080 · built in M6"
  />
);
export const SupportModelsPage = () => (
  <PlaceholderPage
    title="Support models"
    purpose="Generate and review support models."
    spec="FR-040 · built in M4"
  />
);
export const AdminPage = () => (
  <PlaceholderPage
    title="Admin"
    purpose="Playbook and configuration (admins only)."
    spec="FR-100 · built in M7"
  />
);
export const AuditPage = () => (
  <PlaceholderPage
    title="Audit trail"
    purpose="Who did what: Human, Workflow rule or Orion agent."
    spec="FR-110 · built in M7"
  />
);
export const OrionFullPage = () => (
  <PlaceholderPage title="Orion" purpose="Full-page Orion assistant." spec="FR-090 · built in M8" />
);

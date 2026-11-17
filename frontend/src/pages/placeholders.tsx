import { PlaceholderPage } from '../components/PlaceholderPage';

// One tiny component per not-yet-built route. Spec ids + milestone only, no fake data.

export const LeadershipUpdatesPage = () => (
  <PlaceholderPage
    title="Leadership updates"
    purpose="Portfolio updates for leadership."
    spec="FR-080 · built in M6"
  />
);
export const OrionFullPage = () => (
  <PlaceholderPage title="Orion" purpose="Full-page Orion assistant." spec="FR-090 · built in M8" />
);
export const SupportModelsPage = () => (
  <PlaceholderPage
    title="Support models"
    purpose="Generate and review support models."
    spec="FR-040 · built in M7"
  />
);
export const AdminPage = () => (
  <PlaceholderPage
    title="Admin"
    purpose="Playbook configuration and demo controls."
    spec="FR-100 · built in M9"
  />
);

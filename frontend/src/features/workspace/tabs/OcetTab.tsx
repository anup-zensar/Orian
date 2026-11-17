import { PlaceholderPage } from '../../../components/PlaceholderPage';
import type { TabProps } from '../types';

/** OCET tab until the OCET module is built (M6, A-59). */
export function OcetTab({ transitionId }: TabProps) {
  return (
    <PlaceholderPage
      title="OCET"
      purpose={`5-year run-and-maintain projection, versions and the Planner -> OLM approval for ${transitionId}.`}
      spec="FR-060 · built in M6"
    />
  );
}

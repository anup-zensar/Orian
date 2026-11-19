import { SectionIntro } from '../components/SectionIntro';
import { ChecklistsPanel } from './ChecklistsPanel';
import { ItemsPanel } from './ItemsPanel';

/** Admin section 1: the checklists and the items inside them. */
export function ChecklistsSection() {
  return (
    <>
      <SectionIntro>
        Change the checklists and the items in them. This decides what new transitions have to do;
        transitions that already exist keep the items they were launched with.
      </SectionIntro>
      <ChecklistsPanel />
      <ItemsPanel />
    </>
  );
}

import { SectionIntro } from '../components/SectionIntro';
import { DropdownListsPanel } from './DropdownListsPanel';
import { FormFieldsPanel } from './FormFieldsPanel';

/** Admin section 4: the intake form fields and the dropdown lists behind them. */
export function FormsSection() {
  return (
    <>
      <SectionIntro>
        Rename form fields, add your own fields, and edit the values in dropdown lists. Renaming
        changes only what people see; saved records keep working. Dropdown changes apply
        immediately.
      </SectionIntro>
      <FormFieldsPanel />
      <DropdownListsPanel />
    </>
  );
}

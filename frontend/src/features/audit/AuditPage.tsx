import { PageHeader } from '../../components/PageHeader';
import { AuditExplorer } from './AuditExplorer';

/** Global audit trail (FR-110, spec 8.17): every change with its actor type. Filters live in the URL. */
export function AuditPage() {
  return (
    <>
      <PageHeader
        title="Audit trail"
        subtitle="Every change with who or what made it: Human, Workflow rule, Orion agent or System."
      />
      <AuditExplorer />
    </>
  );
}

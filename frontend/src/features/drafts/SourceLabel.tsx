import { Badge } from '@fluentui/react-components';
import { ActorBadge } from '../../components/ActorBadge';
import { actorStyles, chipStyle } from '../../theme/tokens';

/** "Workflow rule R1" (blue outline) or "Orion agent" (purple + AI badge). */
export function SourceLabel({ label }: { label: string }) {
  if (label.toLowerCase().startsWith('orion')) return <ActorBadge actor="Orion agent" />;
  return (
    <Badge appearance="outline" shape="rounded" style={chipStyle(actorStyles['Workflow rule'])}>
      {label}
    </Badge>
  );
}

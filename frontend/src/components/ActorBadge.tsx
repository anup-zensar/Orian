import { Badge } from '@fluentui/react-components';
import { actorStyles, chipStyle, type ActorType } from '../theme/tokens';
import { AiBadge } from './AiBadge';

/** Who did it: Human (neutral), Workflow rule (blue outline), Orion agent (purple + AI). */
export function ActorBadge({ actor }: { actor: ActorType }) {
  return (
    <span style={{ display: 'inline-flex', gap: 4, alignItems: 'center' }}>
      <Badge appearance="outline" shape="rounded" style={chipStyle(actorStyles[actor])}>
        {actor}
      </Badge>
      {actor === 'Orion agent' && <AiBadge />}
    </span>
  );
}

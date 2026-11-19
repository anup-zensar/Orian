import { Badge } from '@fluentui/react-components';
import { useOptionLabel } from '../features/reference/options';
import { actorStyles, chipStyle, type ActorType } from '../theme/tokens';
import { AiBadge } from './AiBadge';

/** Who did it: Human (neutral), Workflow rule (blue outline), Orion agent (purple + AI). */
export function ActorBadge({ actor }: { actor: ActorType }) {
  const optionLabel = useOptionLabel();
  // An actor type nobody styled (a new list value) shows in the neutral System style.
  const style = actorStyles[actor] ?? actorStyles.System;
  return (
    <span style={{ display: 'inline-flex', gap: 4, alignItems: 'center' }}>
      <Badge appearance="outline" shape="rounded" style={chipStyle(style)}>
        {optionLabel('actor_types', actor) || actor}
      </Badge>
      {actor === 'Orion agent' && <AiBadge />}
    </span>
  );
}

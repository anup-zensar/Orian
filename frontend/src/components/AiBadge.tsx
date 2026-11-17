import { Badge } from '@fluentui/react-components';
import { aiBadgeColors, chipStyle } from '../theme/tokens';

/** Small purple "AI" marker for anything Orion generated. */
export function AiBadge() {
  return (
    <Badge size="small" shape="rounded" style={chipStyle(aiBadgeColors)} aria-label="AI generated">
      AI
    </Badge>
  );
}

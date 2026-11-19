import { Badge } from '@fluentui/react-components';
import { chipStyle, lensColors, ragColors, type Lens } from '../theme/tokens';

/** Lens label chip (Business amber, Technical blue, Compliance teal). */
export function LensChip({ lens }: { lens: Lens }) {
  return (
    <Badge
      appearance="outline"
      shape="rounded"
      style={chipStyle(lensColors[lens] ?? ragColors.Grey)}
    >
      {lens}
    </Badge>
  );
}

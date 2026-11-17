import { Badge } from '@fluentui/react-components';
import { chipStyle, ragColors, type Rag } from '../theme/tokens';

const LABELS: Record<Rag, string> = {
  Red: 'Red',
  Amber: 'Amber',
  Green: 'Green',
  Grey: 'Not started',
};

/** RAG chip. Colour is never the only signal, so the text is always shown (spec section 12). */
export function RagChip({ rag, label }: { rag: Rag; label?: string }) {
  return (
    <Badge appearance="outline" shape="rounded" style={chipStyle(ragColors[rag])}>
      {label ?? LABELS[rag]}
    </Badge>
  );
}

import { Badge } from '@fluentui/react-components';
import { useOptionLabel } from '../features/reference/options';
import { chipStyle, ragColors, type Rag } from '../theme/tokens';

/** RAG chip. Colour is never the only signal, so the text is always shown (spec section 12). */
export function RagChip({ rag, label }: { rag: Rag; label?: string }) {
  const optionLabel = useOptionLabel();
  // Red / Amber / Green words come from the rag_words list; Grey always reads "Not started" (A-34).
  const text = rag === 'Grey' ? 'Not started' : optionLabel('rag_words', rag) || rag;
  return (
    <Badge appearance="outline" shape="rounded" style={chipStyle(ragColors[rag])}>
      {label ?? text}
    </Badge>
  );
}

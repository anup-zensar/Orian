import {
  Button,
  MessageBar,
  MessageBarActions,
  MessageBarBody,
  MessageBarTitle,
} from '@fluentui/react-components';
import { ApiError } from '../api/client';

/** Shows an API error: the detail plus every reasons[] line, and a Retry button when ``onRetry``
 * is given. */
export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const detail = error instanceof ApiError ? error.detail : 'Something went wrong';
  const reasons = error instanceof ApiError ? error.reasons : [];
  return (
    <MessageBar intent="error" role="alert" style={{ borderRadius: 8 }}>
      <MessageBarBody>
        <MessageBarTitle>{detail}</MessageBarTitle>
        {reasons.length > 0 && (
          <ul style={{ margin: '4px 0 0', paddingLeft: 20 }}>
            {reasons.map((r) => (
              <li key={r}>{r}</li>
            ))}
          </ul>
        )}
      </MessageBarBody>
      {onRetry && (
        <MessageBarActions>
          <Button onClick={onRetry}>Retry</Button>
        </MessageBarActions>
      )}
    </MessageBar>
  );
}

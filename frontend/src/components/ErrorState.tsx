import { MessageBar, MessageBarBody, MessageBarTitle } from '@fluentui/react-components';
import { ApiError } from '../api/client';

/** Shows an API error: the detail plus every reasons[] line. */
export function ErrorState({ error }: { error: unknown }) {
  const detail = error instanceof ApiError ? error.detail : 'Something went wrong';
  const reasons = error instanceof ApiError ? error.reasons : [];
  return (
    <MessageBar intent="error" role="alert">
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
    </MessageBar>
  );
}

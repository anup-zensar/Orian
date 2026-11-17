import { useCallback } from 'react';
import { Toast, ToastBody, ToastTitle, useToastController } from '@fluentui/react-components';
import { ApiError } from '../api/client';

export const TOASTER_ID = 'orion-toaster';

/** Returns showError(err): an error toast with the API detail and every reasons[] line. */
export function useApiErrorToast() {
  const { dispatchToast } = useToastController(TOASTER_ID);
  return useCallback(
    (error: unknown) => {
      const detail = error instanceof ApiError ? error.detail : 'Something went wrong';
      const reasons = error instanceof ApiError ? error.reasons : [];
      dispatchToast(
        <Toast>
          <ToastTitle>{detail}</ToastTitle>
          {reasons.length > 0 && (
            <ToastBody>
              <ul style={{ margin: 0, paddingLeft: 18 }}>
                {reasons.map((r) => (
                  <li key={r}>{r}</li>
                ))}
              </ul>
            </ToastBody>
          )}
        </Toast>,
        { intent: 'error', timeout: 8000 },
      );
    },
    [dispatchToast],
  );
}

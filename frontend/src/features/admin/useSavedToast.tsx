import { useCallback } from 'react';
import { Toast, ToastTitle, useToastController } from '@fluentui/react-components';
import { TOASTER_ID } from '../../hooks/useApiErrorToast';

/** Returns notify(message): a success toast. */
export function useSuccessToast() {
  const { dispatchToast } = useToastController(TOASTER_ID);
  return useCallback(
    (message: string) =>
      dispatchToast(
        <Toast>
          <ToastTitle>{message}</ToastTitle>
        </Toast>,
        { intent: 'success' },
      ),
    [dispatchToast],
  );
}

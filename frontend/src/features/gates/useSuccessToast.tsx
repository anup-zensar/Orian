import { useCallback, type ReactNode } from 'react';
import { Toast, ToastBody, ToastTitle, useToastController } from '@fluentui/react-components';
import { TOASTER_ID } from '../../hooks/useApiErrorToast';

/** Returns showSuccess(title, body?): a short success toast. */
export function useSuccessToast() {
  const { dispatchToast } = useToastController(TOASTER_ID);
  return useCallback(
    (title: string, body?: ReactNode) => {
      dispatchToast(
        <Toast>
          <ToastTitle>{title}</ToastTitle>
          {body && <ToastBody>{body}</ToastBody>}
        </Toast>,
        { intent: 'success', timeout: 4000 },
      );
    },
    [dispatchToast],
  );
}

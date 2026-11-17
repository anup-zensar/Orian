import { useCallback, type ReactNode } from 'react';
import { Toast, ToastBody, ToastTitle, useToastController } from '@fluentui/react-components';
import { TOASTER_ID } from '../../hooks/useApiErrorToast';

const ROLE_LABELS: Record<string, string> = {
  CISO_BISO: 'CISO/BISO (mock)',
  OLM: 'SOM OLM',
  IRM: 'IRM',
  PLANNER: 'Planner',
  ARCHITECT: 'Architect',
};

/** Friendly label for an approver role code (falls back to the raw value). */
export const roleLabel = (role: string): string => ROLE_LABELS[role] ?? role;

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

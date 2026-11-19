import { useCallback, useState, type ReactNode } from 'react';
import {
  Button,
  DialogActions,
  DialogBody,
  DialogContent,
  DialogSurface,
  DialogTitle,
} from '@fluentui/react-components';
import { ReturnFocusDialog } from '../../../components/ReturnFocusDialog';

/**
 * Guards an in-page action (picking another row or list) while the form has unsaved edits.
 * `guard(action)` runs the action at once when nothing is dirty, otherwise asks first.
 * Render `dialog` somewhere in the component. Leaving the page is guarded by useLeaveGuard.
 */
export function useDiscardGuard(dirty: boolean): {
  guard: (action: () => void) => void;
  dialog: ReactNode;
} {
  const [pending, setPending] = useState<(() => void) | null>(null);
  const guard = useCallback(
    (action: () => void) => {
      if (dirty) setPending(() => action);
      else action();
    },
    [dirty],
  );
  const dialog = pending ? (
    <ReturnFocusDialog open onOpenChange={(_, d) => !d.open && setPending(null)}>
      <DialogSurface>
        <DialogBody>
          <DialogTitle>Discard unsaved changes?</DialogTitle>
          <DialogContent>
            You have edits that are not saved. Continuing discards them.
          </DialogContent>
          <DialogActions>
            <Button appearance="primary" onClick={() => setPending(null)}>
              Keep editing
            </Button>
            <Button
              onClick={() => {
                pending();
                setPending(null);
              }}
            >
              Discard changes
            </Button>
          </DialogActions>
        </DialogBody>
      </DialogSurface>
    </ReturnFocusDialog>
  ) : null;
  return { guard, dialog };
}

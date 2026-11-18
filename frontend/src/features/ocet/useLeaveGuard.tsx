import { ReturnFocusDialog } from '../../components/ReturnFocusDialog';
import { useEffect } from 'react';
import {
  Button,
  DialogActions,
  DialogBody,
  DialogContent,
  DialogSurface,
  DialogTitle,
} from '@fluentui/react-components';
import { useBlocker } from 'react-router';

/** Asks before leaving the page (route change, reload, tab close) while there are unsaved edits. */
export function useLeaveGuard(dirty: boolean) {
  const blocker = useBlocker(dirty);
  useEffect(() => {
    if (!dirty) return;
    const handler = (e: BeforeUnloadEvent) => {
      e.preventDefault();
    };
    window.addEventListener('beforeunload', handler);
    return () => window.removeEventListener('beforeunload', handler);
  }, [dirty]);
  if (blocker.state !== 'blocked') return null;
  return (
    <ReturnFocusDialog open onOpenChange={(_, d) => !d.open && blocker.reset()}>
      <DialogSurface>
        <DialogBody>
          <DialogTitle>Discard unsaved changes?</DialogTitle>
          <DialogContent>
            You have edits that are not saved. Leaving now discards them.
          </DialogContent>
          <DialogActions>
            <Button appearance="primary" onClick={() => blocker.reset()}>
              Stay and keep editing
            </Button>
            <Button onClick={() => blocker.proceed()}>Discard and leave</Button>
          </DialogActions>
        </DialogBody>
      </DialogSurface>
    </ReturnFocusDialog>
  );
}

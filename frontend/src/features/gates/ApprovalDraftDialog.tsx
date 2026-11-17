import {
  Button,
  Dialog,
  DialogActions,
  DialogBody,
  DialogContent,
  DialogSurface,
  DialogTitle,
  MessageBar,
  MessageBarBody,
} from '@fluentui/react-components';
import { DraftEditor } from '../drafts/DraftEditor';
import { useDraft, type Draft } from '../drafts/api';

/** Shows Orion's approval-request draft; Send (POST /orion/drafts/{id}/send) starts the chain. */
export function ApprovalDraftDialog(props: {
  draft: Draft;
  sendReason: string | null;
  onClose: () => void;
}) {
  const live = useDraft(props.draft.id);
  return (
    <Dialog open onOpenChange={(_, d) => !d.open && props.onClose()}>
      <DialogSurface style={{ maxWidth: 980, width: '95vw' }}>
        <DialogBody>
          <DialogTitle>Approval request draft</DialogTitle>
          <DialogContent>
            <MessageBar intent="info">
              <MessageBarBody>
                Orion drafted this request. Nothing is sent and no approval starts until you click
                Send.
              </MessageBarBody>
            </MessageBar>
            <DraftEditor
              draft={live.data ?? props.draft}
              sendReasons={[props.sendReason]}
              onSent={props.onClose}
              onDiscarded={props.onClose}
            />
          </DialogContent>
          <DialogActions>
            <Button appearance="secondary" onClick={props.onClose}>
              Close
            </Button>
          </DialogActions>
        </DialogBody>
      </DialogSurface>
    </Dialog>
  );
}

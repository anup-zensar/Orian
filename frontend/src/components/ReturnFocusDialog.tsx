import { useEffect, useRef, useState } from 'react';
import { Dialog, type DialogProps } from '@fluentui/react-components';

function focusBack(el: HTMLElement | null) {
  if (el && el.isConnected && el !== document.body) el.focus();
}

/**
 * Fluent Dialog that gives focus back to whatever opened it once it closes (or unmounts).
 * Our dialogs are controlled or mounted on demand without a DialogTrigger, so Fluent cannot
 * restore focus itself and keyboard users would otherwise land on <body>.
 */
export function ReturnFocusDialog(props: DialogProps) {
  const open = props.open ?? false;
  const [prevOpen, setPrevOpen] = useState(false);
  const [opener, setOpener] = useState<HTMLElement | null>(null);
  const latest = useRef<HTMLElement | null>(null);
  const alive = useRef(true);

  if (open !== prevOpen) {
    // runs during render, before Fluent moves focus into the dialog
    setPrevOpen(open);
    if (open) setOpener(document.activeElement as HTMLElement | null);
  }

  useEffect(() => {
    latest.current = opener;
  }, [opener]);

  useEffect(() => {
    // closed: send focus back to the opener (it is replaced on the next open)
    if (!open) focusBack(latest.current);
  }, [open]);

  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
      // on-demand dialogs unmount while open; the timeout lets a StrictMode remount cancel this
      window.setTimeout(() => {
        if (!alive.current) focusBack(latest.current);
      }, 0);
    };
  }, []);

  return <Dialog {...props} />;
}

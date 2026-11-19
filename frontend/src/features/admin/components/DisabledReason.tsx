import type { ReactNode } from 'react';
import { Tooltip } from '@fluentui/react-components';

/**
 * Wrap a control that may be disabled. When `reason` is set the control stays visible and a
 * tooltip explains why it cannot be used. Browsers send no hover events from a disabled control,
 * so the tooltip hangs on a wrapper that catches the pointer instead.
 */
export function DisabledReason({
  reason,
  children,
}: {
  reason?: string | null;
  children: ReactNode;
}) {
  if (!reason) return <>{children}</>;
  return (
    <Tooltip content={reason} relationship="description" withArrow>
      <span style={{ display: 'inline-flex', cursor: 'not-allowed' }}>
        <span style={{ display: 'inline-flex', pointerEvents: 'none' }}>{children}</span>
      </span>
    </Tooltip>
  );
}

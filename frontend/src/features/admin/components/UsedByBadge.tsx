import { Badge } from '@fluentui/react-components';

/** "Used by 3" next to something an admin can deactivate; tells them what a change touches. */
export function UsedByBadge({ count, noun }: { count: number; noun?: string }) {
  if (count <= 0) {
    return (
      <Badge appearance="tint" color="subtle" style={{ whiteSpace: 'nowrap' }}>
        Not used yet
      </Badge>
    );
  }
  return (
    <Badge appearance="tint" color="informative" style={{ whiteSpace: 'nowrap' }}>
      {noun ? `Used by ${count} ${noun}` : `Used by ${count}`}
    </Badge>
  );
}

import { Skeleton, SkeletonItem } from '@fluentui/react-components';

/** Skeleton rows shown while a list or page loads. */
export function LoadingState({ rows = 4 }: { rows?: number }) {
  return (
    <Skeleton aria-label="Loading">
      {Array.from({ length: rows }, (_, i) => (
        <SkeletonItem key={i} style={{ height: 32, marginBottom: 12 }} />
      ))}
    </Skeleton>
  );
}
